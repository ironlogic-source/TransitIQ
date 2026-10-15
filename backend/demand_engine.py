
from __future__ import annotations

import math

import pandas as pd

from backend.constraints import PlanContext, cancel_unavailable_trips


def build_demand_model(history: pd.DataFrame) -> dict:

    g = history.groupby(["route_id", "stop_id", "window_start"]).passenger_count.mean()
    return g.to_dict()


def scenario_multiplier(scenario: dict | None, stop_id: str) -> float:
    m = (scenario or {}).get("demand_multiplier", {})
    return float(m.get(stop_id, m.get("*", 1.0)))


def forecast_demand(model: dict, route_id: str, stop_id: str, window_start: float,
                    scenario: dict | None = None) -> float:
    return model.get((route_id, stop_id, window_start), 0.0) * scenario_multiplier(scenario, stop_id)


def forecast_trip_loads(schedules: pd.DataFrame, ctx: PlanContext, model: dict,
                        alight_frac: float = 0.25) -> pd.DataFrame:
    window = ctx.p("demand_window")
    plan, _ = cancel_unavailable_trips(schedules, ctx)
    rows, share_count = [], {}
    for t in plan.itertuples(index=False):
        for stop, cum in zip(ctx.route_stops[t.route_id], ctx.route_cum[t.route_id]):
            key = (t.route_id, stop, math.floor((t.departure_time + cum) / window) * window)
            share_count[key] = share_count.get(key, 0) + 1
    for t in plan.sort_values(["departure_time", "trip_id"]).itertuples(index=False):
        cap = ctx.vehicle_info[t.vehicle_id]["capacity"]
        onboard = 0.0
        for seq, (stop, cum) in enumerate(zip(ctx.route_stops[t.route_id], ctx.route_cum[t.route_id])):
            arr = t.departure_time + cum
            ws = math.floor(arr / window) * window
            n = share_count[(t.route_id, stop, ws)]
            want = forecast_demand(model, t.route_id, stop, ws, ctx.scenario) / n
            if seq > 0:
                onboard -= onboard * alight_frac
            seats = cap - onboard
            excess = max(0.0, want - seats)
            boarded = min(want, seats)
            onboard += boarded
            rows.append({"trip_id": t.trip_id, "vehicle_id": t.vehicle_id, "route_id": t.route_id,
                         "stop_id": stop, "seq": seq, "sched_arrival": arr, "window_start": ws,
                         "expected_boarding": round(want, 1), "available_seats": round(seats, 1),
                         "excess_demand": round(excess, 1), "onboard_after": round(onboard, 1),
                         "capacity": cap, "load_factor": round(onboard / cap, 2)})
    return pd.DataFrame(rows)


def forecast_unserved(schedules: pd.DataFrame, ctx: PlanContext, model: dict) -> pd.DataFrame:

    window = ctx.p("demand_window")
    plan, _ = cancel_unavailable_trips(schedules, ctx)
    served = set()
    for t in plan.itertuples(index=False):
        for stop, cum in zip(ctx.route_stops[t.route_id], ctx.route_cum[t.route_id]):
            served.add((t.route_id, stop, math.floor((t.departure_time + cum) / window) * window))
    rows = [{"route_id": r, "stop_id": s, "window_start": w,
             "passengers": round(forecast_demand(model, r, s, w, ctx.scenario), 1)}
            for (r, s, w) in model if (r, s, w) not in served]
    return pd.DataFrame(rows, columns=["route_id", "stop_id", "window_start", "passengers"])


def rank_routes_by_excess(loads: pd.DataFrame, unserved: pd.DataFrame | None = None) -> pd.DataFrame:

    excess = loads.groupby("route_id").excess_demand.sum() if not loads.empty else pd.Series(dtype=float)
    if unserved is not None and len(unserved):
        excess = excess.add(unserved.groupby("route_id").passengers.sum(), fill_value=0.0)
    r = excess.sort_values(ascending=False).rename("excess_demand").reset_index()
    r.columns = ["route_id", "excess_demand"]
    return r[r.excess_demand > 0].reset_index(drop=True)
