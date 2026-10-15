"""
TransitIQ - optimizer.py  (PulseRescue)
Greedy, constraint-aware optimizer:

  1. cancel trips of unavailable buses (the disruption) -> baseline plan
  2. find routes with the most unmet demand
  3. generate candidate fixes: add_trip / reassign_trip / swap_vehicle / shift_departure
  4. REJECT candidates that break any hard constraint (constraints.validate_plan)
  5. simulate the survivors, score with objective J (evaluation.py), keep the best
  6. repeat up to max_steps while J keeps improving; explain trade-offs

`run_sim(schedules_df) -> sim_result dict` is injected (orchestrator wraps simulation.run_simulation
with fixed vehicles/demand/routes/scenario/seed). The optimizer never edits the simulator.
"""
from __future__ import annotations

import math
from collections import Counter

import pandas as pd

from backend.constraints import PlanContext, cancel_unavailable_trips, fmt_time, validate_plan
from backend.evaluation import DEFAULT_WEIGHTS, compare_metrics, compute_metrics, objective

ADD_OFFSETS = (-6, -3, 3, 6)
SHIFT_OFFSETS = (-5, 5)


# ------------------------------------------------------------------------ analysis helpers
def route_unmet(sim: dict, schedules: pd.DataFrame) -> pd.Series:
    """Unmet passengers per route (left behind + completely unserved windows)."""
    trip_route = dict(zip(schedules.trip_id, schedules.route_id))
    occ = sim["occupancy"]
    left = occ.groupby(occ.trip_id.map(trip_route)).left_behind.sum() if len(occ) else pd.Series(dtype=float)
    uns = sim.get("unserved")
    uns_s = uns.groupby("route_id").passengers.sum() if uns is not None and len(uns) else pd.Series(dtype=float)
    return left.add(uns_s, fill_value=0.0).sort_values(ascending=False)


def _next_trip_id(schedules: pd.DataFrame, route_id: str, dep: float) -> str:
    base = f"NEW_{route_id}_{int(dep)}"
    existing = set(schedules.trip_id)
    tid, n = base, 1
    while tid in existing:
        n += 1
        tid = f"{base}_{n}"
    return tid


def _new_row(schedules, vid, route, dep):
    return {"trip_id": _next_trip_id(schedules, route, dep), "vehicle_id": vid,
            "route_id": route, "departure_time": float(dep)}


def _candidate_departures(route, plan, ctx, sim, cancelled) -> list[int]:
    """Departure times worth trying for an extra trip on `route`."""
    times = set()
    occ = sim["occupancy"]
    dep_of = dict(zip(plan.trip_id, plan.departure_time))
    route_trips = set(plan[plan.route_id == route].trip_id)
    if len(occ):
        for tid in occ[(occ.left_behind > 0) & occ.trip_id.isin(route_trips)].trip_id.unique():
            times.update(dep_of[tid] + o for o in ADD_OFFSETS)
    uns = sim.get("unserved")
    w = ctx.p("demand_window")
    if uns is not None and len(uns):
        for r in uns[uns.route_id == route].itertuples(index=False):
            idx = ctx.route_stops[route].index(r.stop_id)
            cum = ctx.route_cum[route][idx]
            times.update(r.window_start + f * w - cum for f in (0.25, 0.75))
    if cancelled is not None and len(cancelled):
        for t in cancelled[cancelled.route_id == route].itertuples(index=False):
            times.update((t.departure_time, t.departure_time + 3))
    lo, hi = ctx.p("service_start"), ctx.p("service_end")
    return sorted(int(round(t)) for t in times if lo <= t <= hi)


# ------------------------------------------------------------------------ candidate generators
def generate_candidates(plan, ctx, hot_routes, sim, cancelled):
    """Yield (new_plan, action_dict). Nothing is validated here."""
    vehicles = [v for v, i in ctx.vehicle_info.items() if int(i.get("available", 1))]
    seen = set()

    def emit(new, action):
        key = tuple(sorted(map(tuple, new[["trip_id", "vehicle_id", "route_id", "departure_time"]].values.tolist())))
        if key not in seen:
            seen.add(key)
            return [(new, action)]
        return []

    occ = sim["occupancy"]
    for route in hot_routes:
        # (a) add an extra trip using any vehicle
        for dep in _candidate_departures(route, plan, ctx, sim, cancelled):
            for vid in vehicles:
                row = _new_row(plan, vid, route, dep)
                new = pd.concat([plan, pd.DataFrame([row])], ignore_index=True)
                yield from emit(new, {"action": "add_trip", "vehicle_id": vid, "to_route": route,
                                      "from_route": None, "trip_id": row["trip_id"], "departure_time": dep})
        # (b) re-route an existing trip of another route to the hot route
        for t in plan[plan.route_id != route].itertuples(index=False):
            new = plan.copy()
            new.loc[new.trip_id == t.trip_id, "route_id"] = route
            yield from emit(new, {"action": "reassign_trip", "vehicle_id": t.vehicle_id, "to_route": route,
                                  "from_route": t.route_id, "trip_id": t.trip_id,
                                  "departure_time": t.departure_time})
        # (c) give a hot trip a bigger bus (swap with that bus's nearest trip, or plain assign)
        hot_trips = plan[plan.route_id == route]
        if len(occ):
            hot_trips = hot_trips[hot_trips.trip_id.isin(occ[occ.left_behind > 0].trip_id)]
        for t in hot_trips.itertuples(index=False):
            cap = ctx.vehicle_info[t.vehicle_id]["capacity"]
            for vid in vehicles:
                if vid == t.vehicle_id or ctx.vehicle_info[vid]["capacity"] <= cap:
                    continue
                new = plan.copy()
                other = plan[plan.vehicle_id == vid]
                if len(other):
                    near = other.iloc[(other.departure_time - t.departure_time).abs().argsort()[:1]]
                    new.loc[new.trip_id == near.trip_id.iloc[0], "vehicle_id"] = t.vehicle_id
                new.loc[new.trip_id == t.trip_id, "vehicle_id"] = vid
                yield from emit(new, {"action": "swap_vehicle", "vehicle_id": vid, "to_route": route,
                                      "from_route": route, "trip_id": t.trip_id,
                                      "departure_time": t.departure_time, "replaces_vehicle": t.vehicle_id})
        # (d) shift a hot trip's departure inside the allowed window
        for t in hot_trips.itertuples(index=False):
            for off in SHIFT_OFFSETS:
                new = plan.copy()
                new.loc[new.trip_id == t.trip_id, "departure_time"] = t.departure_time + off
                yield from emit(new, {"action": "shift_departure", "vehicle_id": t.vehicle_id,
                                      "to_route": route, "from_route": route, "trip_id": t.trip_id,
                                      "departure_time": t.departure_time + off, "shift_min": off})


# ------------------------------------------------------------------------ explanation
def _describe(action: dict) -> str:
    a, t = action["action"], fmt_time(action["departure_time"])
    if a == "add_trip":
        return f"Add a trip on Route {action['to_route']} departing {t} using bus {action['vehicle_id']}"
    if a == "reassign_trip":
        return (f"Reassign bus {action['vehicle_id']} ({t}) from Route {action['from_route']} "
                f"to Route {action['to_route']}")
    if a == "swap_vehicle":
        return (f"Put larger bus {action['vehicle_id']} on Route {action['to_route']} trip {action['trip_id']} "
                f"({t}) instead of {action['replaces_vehicle']}")
    return f"Shift trip {action['trip_id']} on Route {action['to_route']} by {action['shift_min']:+d} min to {t}"


def _explain(action, before_m, after_m, before_unmet, after_unmet, hot_total):
    target = action["to_route"]
    gains = [f"unmet demand {before_m['unmet_demand']:.0f} -> {after_m['unmet_demand']:.0f}",
             f"avg wait {before_m['avg_wait_min']:.1f} -> {after_m['avg_wait_min']:.1f} min"]
    reason = (f"Route {target} had the highest unmet demand ({hot_total:.0f} passengers). "
              f"All hard constraints satisfied; " + ", ".join(gains) + ".")
    trade = []
    for r in sorted(set(before_unmet.index) | set(after_unmet.index)):
        d = after_unmet.get(r, 0.0) - before_unmet.get(r, 0.0)
        if d > 0.5:
            trade.append(f"Route {r} unmet demand rises by {d:.0f}")
    dc = after_m["operational_cost"] - before_m["operational_cost"]
    if abs(dc) >= 0.5:
        trade.append(f"operational cost {dc:+.0f} vehicle-minutes")
    return reason, ("Trade-offs: " + "; ".join(trade) + ".") if trade else "No adverse trade-offs detected."


# ------------------------------------------------------------------------ main entry point
def optimize_plan(run_sim, schedules: pd.DataFrame, ctx: PlanContext, weights: dict | None = None,
                  hot_routes: list | None = None, max_steps: int = 3, top_routes: int = 3,
                  max_candidates: int = 400, min_gain: float = 1e-6) -> dict:
    weights = weights or DEFAULT_WEIGHTS
    plan, cancelled = cancel_unavailable_trips(schedules, ctx)
    plan = plan.reset_index(drop=True)
    original_plan = plan.copy()

    sim = run_sim(plan)
    base_m = compute_metrics(sim, plan, ctx)
    base_J = objective(base_m, weights)
    cur_sim, cur_m, cur_J = sim, base_m, base_J

    actions, rejected, examples, n_eval = [], Counter(), [], 0
    for _ in range(max_steps):
        unmet = route_unmet(cur_sim, plan)
        ordered = list(dict.fromkeys(list(hot_routes or []) + unmet[unmet > 0].index.tolist()))[:top_routes]
        ordered = [r for r in ordered if r in ctx.route_stops]
        if not ordered:
            break

        feasible = []
        for new, act in generate_candidates(plan, ctx, ordered, cur_sim, cancelled):
            v = validate_plan(new, ctx)
            if v["feasible"]:
                feasible.append((new, act))
            else:
                for name, d in v["details"].items():
                    if not d["ok"]:
                        rejected[name] += 1
                        if len(examples) < 6:
                            examples.append(f"{_describe(act)} -> REJECTED: {d['violations'][0]}")
        best = None
        for new, act in feasible[:max_candidates]:
            s = run_sim(new)
            n_eval += 1
            v = validate_plan(new, ctx, s)             # adds the capacity check on simulated occupancy
            if not v["feasible"]:
                for name, d in v["details"].items():
                    if not d["ok"]:
                        rejected[name] += 1
                continue
            m = compute_metrics(s, new, ctx)
            J = objective(m, weights)
            if best is None or J < best[0]:
                best = (J, new, act, s, m)
        if best is None or best[0] >= cur_J - min_gain:
            break
        J, new, act, s, m = best
        before_unmet, after_unmet = route_unmet(cur_sim, plan), route_unmet(s, new)
        reason, tradeoff = _explain(act, cur_m, m, before_unmet, after_unmet, float(unmet.get(act["to_route"], 0.0)))
        actions.append({**act, "description": _describe(act), "reason": reason, "tradeoff": tradeoff,
                        "constraints_satisfied": True, "objective_before": round(cur_J, 2),
                        "objective_after": round(J, 2)})
        plan, cur_sim, cur_m, cur_J = new, s, m, J

    final_validation = validate_plan(plan, ctx, cur_sim)
    if actions:
        status = "improved"
        message = " | ".join(a["description"] for a in actions)
    elif base_m["unmet_demand"] <= 0 and not (hot_routes or []):
        status, message = "no_action_needed", "No unmet demand detected; the current plan is kept."
    elif not n_eval and rejected:
        status = "no_feasible_candidates"
        message = ("No valid adjustment is available. Every candidate violated a hard constraint: "
                   + ", ".join(f"{k} ({v})" for k, v in rejected.most_common()) + ".")
    else:
        status = "no_improvement"
        message = (f"{n_eval} feasible candidates were simulated but none improved the objective; "
                   "the current plan is kept.")

    return {
        "status": status, "message": message, "actions": actions,
        "action": actions[0] if actions else None,
        "baseline_metrics": base_m, "optimized_metrics": cur_m,
        "objective_baseline": round(base_J, 2), "objective_optimized": round(cur_J, 2),
        "comparison": compare_metrics(base_m, cur_m).to_dict("records"),
        "original_plan": original_plan.to_dict("records"),
        "proposed_plan": plan.to_dict("records"),
        "cancelled_trips": cancelled.to_dict("records"),
        "validation": final_validation,
        "candidates_evaluated": n_eval, "candidates_rejected": dict(rejected),
        "rejection_examples": examples, "weights": weights,
        "_baseline_sim": sim, "_optimized_sim": cur_sim,     # DataFrames for plotting (not JSON)
    }
