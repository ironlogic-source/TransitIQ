"""
TransitIQ - evaluation.py
Turns a simulation result into the metrics shown in the Before-vs-After table,
plus the optimizer objective J.

Simulation result contract (dict of DataFrames, see CONTRACT.md):
  arrivals  : trip_id, vehicle_id, route_id, stop_id, seq, scheduled, actual
  occupancy : trip_id, stop_id, seq, onboard, boarded, left_behind   (optional: capacity)
  waiting   : stop_id, passengers, wait_min        (wait per passenger for that group)
  unserved  : route_id, stop_id, window_start, passengers   (demand with NO trip at all)
"""
from __future__ import annotations

import pandas as pd

from backend.constraints import PlanContext, total_deadhead_minutes

# J = w_wait*avg_wait_min + w_unmet*unmet_passengers + w_missed*missed_connections + w_cost*vehicle_minutes
# Chosen BEFORE looking at results (document these in the README):
#   1 unmet passenger = 1 pt | 1 missed connection = 2 pts | +1 min avg wait = 10 pts
#   (avg over everyone, so one minute is a big deal) | 1 extra vehicle-minute = 0.05 pts
DEFAULT_WEIGHTS = {"wait": 10.0, "unmet": 1.0, "missed": 2.0, "cost": 0.05}

# metric -> True if "lower is better"
DIRECTION = {
    "avg_wait_min": True, "unmet_demand": True, "missed_connections": True,
    "capacity_violations": True, "fleet_utilization": False, "avg_delay_min": True,
    "operational_cost": True, "passengers_served": False, "eta_mae": True,
}


def count_missed_connections(arrivals: pd.DataFrame, window: float = 10.0) -> int:
    """A connection = trip A (route X) scheduled to arrive at a stop, and trip B (route Y != X)
    scheduled to depart that stop 0..window min later. Missed if A actually arrives after B."""
    if arrivals is None or len(arrivals) == 0:
        return 0
    missed = 0
    for _, g in arrivals.groupby("stop_id"):
        rows = sorted(zip(g.scheduled, g.actual, g.route_id))
        for i, (sa, aa, ra) in enumerate(rows):
            for sb, ab, rb in rows[i:]:
                if sb - sa > window:
                    break
                if ra != rb and aa > ab:
                    missed += 1
    return missed


def _horizon_minutes(ctx: PlanContext, vehicles_unavail) -> float:
    start, end = ctx.p("service_start"), ctx.p("service_end")
    total = 0.0
    for vid in ctx.vehicle_info:
        if not int(ctx.vehicle_info[vid].get("available", 1)):
            continue
        until = min(vehicles_unavail.get(vid, end), end)
        total += max(0.0, until - start)
    return total


def compute_metrics(sim: dict, schedules: pd.DataFrame, ctx: PlanContext,
                    conn_window: float = 10.0, eta_mae: float | None = None) -> dict:
    arr, occ, wait = sim["arrivals"], sim["occupancy"], sim["waiting"]
    uns = sim.get("unserved", pd.DataFrame(columns=["passengers"]))

    pax = float(wait.passengers.sum()) if len(wait) else 0.0
    avg_wait = float((wait.passengers * wait.wait_min).sum() / pax) if pax > 0 else 0.0
    unmet = float(occ.left_behind.sum() if len(occ) else 0) + float(uns.passengers.sum() if len(uns) else 0)

    trip_vehicle = dict(zip(schedules.trip_id, schedules.vehicle_id))
    violations = 0
    for tid, onboard in zip(occ.trip_id, occ.onboard):
        cap = ctx.vehicle_info.get(trip_vehicle.get(tid), {}).get("capacity")
        if cap is not None and onboard > cap + 1e-6:
            violations += 1

    if len(arr):
        g = arr.groupby("trip_id").actual
        productive = float((g.max() - g.min()).sum())
        avg_delay = float((arr.actual - arr.scheduled).mean())
    else:
        productive, avg_delay = 0.0, 0.0
    avail_minutes = _horizon_minutes(ctx, ctx.unavailable)
    utilization = min(1.0, productive / avail_minutes) if avail_minutes > 0 else 0.0

    m = {
        "avg_wait_min": round(avg_wait, 2),
        "unmet_demand": round(unmet, 1),
        "missed_connections": count_missed_connections(arr, conn_window),
        "capacity_violations": violations,
        "fleet_utilization": round(utilization, 3),
        "avg_delay_min": round(avg_delay, 2),
        "operational_cost": round(productive + total_deadhead_minutes(schedules, ctx), 1),
        "passengers_served": float(occ.boarded.sum()) if len(occ) else 0.0,
    }
    if eta_mae is not None:
        m["eta_mae"] = round(eta_mae, 2)
    return m


def objective(metrics: dict, weights: dict | None = None) -> float:
    w = weights or DEFAULT_WEIGHTS
    return (w["wait"] * metrics["avg_wait_min"] + w["unmet"] * metrics["unmet_demand"]
            + w["missed"] * metrics["missed_connections"] + w["cost"] * metrics["operational_cost"])


def compare_metrics(baseline: dict, optimized: dict) -> pd.DataFrame:
    """Before-vs-After table for the dashboard (honest: shows regressions too)."""
    rows = []
    for k, lower_better in DIRECTION.items():
        if k in baseline and k in optimized:
            b, o = baseline[k], optimized[k]
            pct = None if b == 0 else round(100.0 * (b - o) / abs(b) * (1 if lower_better else -1), 1)
            rows.append({"metric": k, "baseline": b, "optimized": o,
                         "change": round(o - b, 3), "improvement_pct": pct,
                         "better": (o < b) if lower_better else (o > b)})
    return pd.DataFrame(rows)
