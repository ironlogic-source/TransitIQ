
from __future__ import annotations

import math
from collections import namedtuple
from dataclasses import dataclass, field

import pandas as pd

DEFAULT_PARAMS = {
    "min_turnaround": 5.0,      # min idle minutes between two trips of one bus (after deadhead)
    "max_shift": 10.0,          # max allowed departure shift vs original timetable (minutes)
    "speed_m_per_min": 400.0,   # deadhead (empty bus) speed, ~24 km/h
    "service_start": 360.0,     # 06:00 - first allowed departure
    "service_end": 1200.0,      # 20:00 - last allowed departure
    "demand_window": 30,        # minutes per demand window (must match passenger_demand.csv)
}
EPS = 1e-6


def normalize_unavailable(scenario: dict | None) -> dict[str, float]:
    """scenario['unavailable_vehicles'] may be a list (unavailable all day) or
    a dict {vehicle_id: minute_from_which_unavailable}. Returns the dict form."""
    raw = (scenario or {}).get("unavailable_vehicles", [])
    if isinstance(raw, dict):
        return {str(k): float(v) for k, v in raw.items()}
    return {str(v): 0.0 for v in raw}


def fmt_time(minutes: float) -> str:
    m = int(round(minutes))
    return f"{(m // 60) % 24:02d}:{m % 60:02d}"


@dataclass
class PlanContext:

    vehicles: pd.DataFrame            # vehicle_id, capacity, available, depot_stop_id, [allowed_routes]
    routes: pd.DataFrame              # route_id, seq, stop_id, seg_time_min
    stops: pd.DataFrame               # stop_id, name, x, y   (metres)
    baseline_schedules: pd.DataFrame  # trip_id, vehicle_id, route_id, departure_time
    scenario: dict = field(default_factory=dict)
    params: dict = field(default_factory=dict)

    def __post_init__(self):
        self.params = {**DEFAULT_PARAMS, **(self.params or {})}
        self.scenario = self.scenario or {}
        self.coords = {r.stop_id: (float(r.x), float(r.y)) for r in self.stops.itertuples()}
        self.route_stops, self.route_cum = {}, {}
        for rid, g in self.routes.groupby("route_id"):
            g = g.sort_values("seq")
            self.route_stops[rid] = g.stop_id.tolist()
            self.route_cum[rid] = g.seg_time_min.cumsum().tolist()
        self.unavailable = normalize_unavailable(self.scenario)
        self.vehicle_info = self.vehicles.set_index("vehicle_id").to_dict("index")
        self.baseline_dep = dict(zip(self.baseline_schedules.trip_id,
                                     self.baseline_schedules.departure_time))

    def p(self, key):
        return self.params[key]

    def duration(self, route_id) -> float:
        return float(self.route_cum[route_id][-1])

    def first_stop(self, route_id):
        return self.route_stops[route_id][0]

    def last_stop(self, route_id):
        return self.route_stops[route_id][-1]

    def deadhead(self, stop_a, stop_b) -> float:
        """Minutes for an empty bus to drive stop_a -> stop_b (straight line / speed)."""
        if stop_a == stop_b:
            return 0.0
        (xa, ya), (xb, yb) = self.coords[stop_a], self.coords[stop_b]
        return math.hypot(xa - xb, ya - yb) / self.p("speed_m_per_min")



Trip = namedtuple("Trip", "trip_id vehicle_id route_id departure_time")


def _rows(schedules: pd.DataFrame) -> list:

    return [Trip(*r) for r in zip(schedules.trip_id, schedules.vehicle_id,
                                  schedules.route_id, schedules.departure_time)]


def _by_vehicle(schedules: pd.DataFrame) -> dict:
    out: dict = {}
    for t in sorted(_rows(schedules), key=lambda t: (t.departure_time, t.trip_id)):
        out.setdefault(t.vehicle_id, []).append(t)
    return out


def _consecutive(schedules, ctx):

    for vid, trips in _by_vehicle(schedules).items():
        for a, b in zip(trips, trips[1:]):
            end_a = a.departure_time + ctx.duration(a.route_id)
            dh = ctx.deadhead(ctx.last_stop(a.route_id), ctx.first_stop(b.route_id))
            yield vid, a, b, end_a, dh, b.departure_time - end_a


def cancel_unavailable_trips(schedules: pd.DataFrame, ctx: PlanContext):
   
    mask = []
    for t in _rows(schedules):
        start = ctx.unavailable.get(t.vehicle_id)
        mask.append(start is not None and t.departure_time >= start)
    mask = pd.Series(mask, index=schedules.index, dtype=bool)
    return schedules[~mask].copy(), schedules[mask].copy()


def total_deadhead_minutes(schedules: pd.DataFrame, ctx: PlanContext) -> float:
    total = 0.0
    for vid, trips in _by_vehicle(schedules).items():
        depot = ctx.vehicle_info.get(vid, {}).get("depot_stop_id")
        if depot in ctx.coords:
            total += ctx.deadhead(depot, ctx.first_stop(trips[0].route_id))
        for a, b in zip(trips, trips[1:]):
            total += ctx.deadhead(ctx.last_stop(a.route_id), ctx.first_stop(b.route_id))
    return total



def check_vehicle_available(schedules, ctx):
    msgs = []
    for t in _rows(schedules):
        info = ctx.vehicle_info.get(t.vehicle_id)
        if info is None:
            msgs.append(f"Trip {t.trip_id}: unknown vehicle {t.vehicle_id}")
        elif not int(info.get("available", 1)):
            msgs.append(f"Trip {t.trip_id}: vehicle {t.vehicle_id} is out of service")
        elif t.vehicle_id in ctx.unavailable and t.departure_time >= ctx.unavailable[t.vehicle_id]:
            msgs.append(f"Trip {t.trip_id}: vehicle {t.vehicle_id} is unavailable from "
                        f"{fmt_time(ctx.unavailable[t.vehicle_id])}")
    return not msgs, msgs


def check_route_compatibility(schedules, ctx):
    msgs = []
    for t in _rows(schedules):
        allowed = ctx.vehicle_info.get(t.vehicle_id, {}).get("allowed_routes")
        if isinstance(allowed, str) and allowed.strip():
            if t.route_id not in {a.strip() for a in allowed.split(";")}:
                msgs.append(f"Trip {t.trip_id}: vehicle {t.vehicle_id} cannot serve route {t.route_id}")
    return not msgs, msgs


def check_no_overlap(schedules, ctx):
    msgs = [f"Vehicle {vid}: trip {b.trip_id} departs {fmt_time(b.departure_time)} before "
            f"trip {a.trip_id} ends {fmt_time(end_a)}"
            for vid, a, b, end_a, dh, gap in _consecutive(schedules, ctx) if gap < -EPS]
    return not msgs, msgs


def check_reachability(schedules, ctx):
    """Bus must physically reach the next route's first stop (and the first trip from its depot)."""
    msgs = []
    for vid, a, b, end_a, dh, gap in _consecutive(schedules, ctx):
        if gap >= -EPS and dh > EPS and gap < dh - EPS:
            msgs.append(f"Vehicle {vid}: needs {dh:.1f} min to drive to start of route {b.route_id} "
                        f"but only {gap:.1f} min available before trip {b.trip_id}")
    for vid, trips in _by_vehicle(schedules).items():
        depot = ctx.vehicle_info.get(vid, {}).get("depot_stop_id")
        if depot in ctx.coords:
            first = trips[0]
            need = ctx.deadhead(depot, ctx.first_stop(first.route_id))
            have = first.departure_time - ctx.p("service_start")
            if have < need - EPS:
                msgs.append(f"Vehicle {vid}: cannot reach {ctx.first_stop(first.route_id)} from depot "
                            f"{depot} in time for trip {first.trip_id}")
    return not msgs, msgs


def check_turnaround(schedules, ctx):
    msgs = []
    for vid, a, b, end_a, dh, gap in _consecutive(schedules, ctx):
        if gap >= dh - EPS and gap < dh + ctx.p("min_turnaround") - EPS:
            msgs.append(f"Vehicle {vid}: only {gap - dh:.1f} min turnaround between {a.trip_id} and "
                        f"{b.trip_id} (min {ctx.p('min_turnaround'):.0f})")
    return not msgs, msgs


def check_departure_window(schedules, ctx):
    msgs = []
    for t in _rows(schedules):
        if t.trip_id in ctx.baseline_dep:
            shift = abs(t.departure_time - ctx.baseline_dep[t.trip_id])
            if shift > ctx.p("max_shift") + EPS:
                msgs.append(f"Trip {t.trip_id}: shifted {shift:.0f} min (max {ctx.p('max_shift'):.0f})")
        elif not (ctx.p("service_start") - EPS <= t.departure_time <= ctx.p("service_end") + EPS):
            msgs.append(f"Trip {t.trip_id}: departure {fmt_time(t.departure_time)} outside service hours")
    return not msgs, msgs


def check_capacity(sim_result, schedules, ctx):
    """Post-simulation check: onboard passengers must never exceed vehicle capacity."""
    occ = sim_result.get("occupancy")
    if occ is None or len(occ) == 0:
        return True, []
    trip_vehicle = dict(zip(schedules.trip_id, schedules.vehicle_id))
    msgs = []
    for tid, stop, onboard in zip(occ.trip_id, occ.stop_id, occ.onboard):
        cap = ctx.vehicle_info.get(trip_vehicle.get(tid), {}).get("capacity")
        if cap is not None and onboard > cap + EPS:
            msgs.append(f"Trip {tid} at {stop}: {onboard:.0f} onboard > capacity {cap}")
    return not msgs, msgs


PRE_SIM_CHECKS = {
    "vehicle_availability": check_vehicle_available,
    "route_compatibility": check_route_compatibility,
    "no_trip_overlap": check_no_overlap,
    "travel_time_reachability": check_reachability,
    "turnaround_time": check_turnaround,
    "departure_window": check_departure_window,
}


def validate_plan(schedules: pd.DataFrame, ctx: PlanContext, sim_result: dict | None = None) -> dict:
    """Run all hard constraints. Pass sim_result to also check capacity."""
    details = {}
    for name, fn in PRE_SIM_CHECKS.items():
        ok, msgs = fn(schedules, ctx)
        details[name] = {"ok": ok, "violations": msgs}
    if sim_result is not None:
        ok, msgs = check_capacity(sim_result, schedules, ctx)
        details["vehicle_capacity"] = {"ok": ok, "violations": msgs}
    return {
        "feasible": all(d["ok"] for d in details.values()),
        "details": details,
        "violations": [m for d in details.values() for m in d["violations"]],
    }
