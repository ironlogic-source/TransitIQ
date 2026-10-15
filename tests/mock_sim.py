"""
Mock of backend/simulation.run_simulation with the SAME signature/output contract.
Used only for tests / until the real simulator is ready. Deterministic for a given seed.
"""
import math
import zlib

import numpy as np
import pandas as pd

from backend.constraints import normalize_unavailable


def run_simulation(schedules, vehicles, demand, routes, scenario=None, seed=42, window=30, alight_frac=0.25):
    scenario = scenario or {}
    unavail = normalize_unavailable(scenario)
    mult, delays = scenario.get("demand_multiplier", {}), scenario.get("route_delays", {})
    cap = vehicles.set_index("vehicle_id").capacity.to_dict()
    rinfo = {r: g.sort_values("seq") for r, g in routes.groupby("route_id")}

    arr, trips = [], []
    for t in schedules.sort_values(["departure_time", "trip_id"]).itertuples(index=False):
        if t.vehicle_id in unavail and t.departure_time >= unavail[t.vehicle_id]:
            continue                                            # cancelled trip
        rng = np.random.default_rng(seed + zlib.crc32(t.trip_id.encode()) % 100000)
        sched, actual = float(t.departure_time), float(t.departure_time) + delays.get(t.route_id, 0.0)
        for r in rinfo[t.route_id].itertuples(index=False):
            if r.seq > 0:
                sched += r.seg_time_min
                actual += r.seg_time_min * max(0.5, 1 + rng.normal(0, 0.12))
            arr.append((t.trip_id, t.vehicle_id, t.route_id, r.stop_id, r.seq, sched, actual))
        trips.append(t)
    arrivals = pd.DataFrame(arr, columns=["trip_id", "vehicle_id", "route_id", "stop_id", "seq", "scheduled", "actual"])

    serving = {}
    for r in arr:
        key = (r[2], r[3], math.floor(r[5] / window) * window)
        serving.setdefault(key, []).append(r[0])
    share, wait_rows, unserved = {}, [], []
    for d in demand.itertuples(index=False):
        n = d.passenger_count * mult.get(d.stop_id, 1.0)
        trips_here = serving.get((d.route_id, d.stop_id, d.window_start), [])
        if not trips_here:
            unserved.append((d.route_id, d.stop_id, d.window_start, round(n)))
            wait_rows.append((d.stop_id, round(n), float(window)))
        else:
            share[(d.route_id, d.stop_id, d.window_start)] = n / len(trips_here)

    sched_at = {(r[0], r[4]): r[5] for r in arr}
    occ = []
    for t in trips:
        onboard = 0.0
        for r in rinfo[t.route_id].itertuples(index=False):
            s = sched_at[(t.trip_id, r.seq)]
            ws = math.floor(s / window) * window
            n_trips = len(serving[(t.route_id, r.stop_id, ws)])
            want = round(share.get((t.route_id, r.stop_id, ws), 0.0))
            if r.seq > 0:
                onboard -= round(onboard * alight_frac)
            boarded = min(want, cap[t.vehicle_id] - onboard)
            left = want - boarded
            onboard += boarded
            occ.append((t.trip_id, t.vehicle_id, r.stop_id, r.seq, onboard, boarded, left, cap[t.vehicle_id]))
            if boarded:
                wait_rows.append((r.stop_id, boarded, window / n_trips / 2))
            if left:
                wait_rows.append((r.stop_id, left, window / n_trips))
    return {
        "arrivals": arrivals,
        "occupancy": pd.DataFrame(occ, columns=["trip_id", "vehicle_id", "stop_id", "seq", "onboard", "boarded", "left_behind", "capacity"]),
        "waiting": pd.DataFrame(wait_rows, columns=["stop_id", "passengers", "wait_min"]),
        "unserved": pd.DataFrame(unserved, columns=["route_id", "stop_id", "window_start", "passengers"]),
    }
