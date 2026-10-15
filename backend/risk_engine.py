
from __future__ import annotations

import pandas as pd

from backend.constraints import fmt_time

DEFAULT_RISK_PARAMS = {
    "delay_warn": 5.0, "delay_high": 10.0,       # predicted delay thresholds (min)
    "near_capacity": 0.9,                         # load factor warning
    "excess_high": 10.0,                          # excess passengers -> HIGH
    "connection_window": 10.0,                    # min between scheduled arrival A and departure B
}
_SEV = {"high": 0, "medium": 1, "low": 2}


def detect_risks(loads: pd.DataFrame, etas: pd.DataFrame | None = None, params: dict | None = None) -> list[dict]:
    p = {**DEFAULT_RISK_PARAMS, **(params or {})}
    alerts: list[dict] = []

    for r in loads.itertuples(index=False):
        if r.excess_demand > 0:
            alerts.append({
                "type": "OVERCROWDING", "severity": "high" if r.excess_demand >= p["excess_high"] else "medium",
                "trip_id": r.trip_id, "route_id": r.route_id, "stop_id": r.stop_id, "value": r.excess_demand,
                "message": f"{r.excess_demand:.0f} passengers expected to be left at {r.stop_id}: "
                           f"{r.expected_boarding:.0f} waiting vs {r.available_seats:.0f} free seats "
                           f"on trip {r.trip_id} ({fmt_time(r.sched_arrival)})"})
        elif r.load_factor >= p["near_capacity"]:
            alerts.append({
                "type": "NEAR_CAPACITY", "severity": "low", "trip_id": r.trip_id, "route_id": r.route_id,
                "stop_id": r.stop_id, "value": r.load_factor,
                "message": f"Trip {r.trip_id} will be {r.load_factor:.0%} full after {r.stop_id}"})

    if etas is not None and len(etas):
        worst = etas.loc[etas.groupby("trip_id").predicted_delay.idxmax()]
        for r in worst.itertuples(index=False):
            if r.predicted_delay >= p["delay_warn"]:
                alerts.append({
                    "type": "DELAY", "severity": "high" if r.predicted_delay >= p["delay_high"] else "medium",
                    "trip_id": r.trip_id, "route_id": r.route_id, "stop_id": r.stop_id, "value": r.predicted_delay,
                    "message": f"Trip {r.trip_id} predicted {r.predicted_delay:.0f} min late at {r.stop_id} "
                               f"(arrival window {fmt_time(r.eta_lo)}-{fmt_time(r.eta_hi)} vs timetable {fmt_time(r.scheduled)})"})
        for _, g in etas.groupby("stop_id"):
            rows = list(g.itertuples(index=False))
            for a in rows:
                for b in rows:
                    if a.route_id != b.route_id and 0 <= b.scheduled - a.scheduled <= p["connection_window"] \
                            and a.eta > b.eta:
                        alerts.append({
                            "type": "MISSED_CONNECTION", "severity": "high",
                            "trip_id": a.trip_id, "route_id": a.route_id, "stop_id": a.stop_id,
                            "value": a.eta - b.eta,
                            "message": f"Passengers on {a.trip_id} (route {a.route_id}) will likely miss "
                                       f"{b.trip_id} (route {b.route_id}) at {a.stop_id}: arrives {fmt_time(a.eta)}, "
                                       f"connection leaves {fmt_time(b.eta)}"})
    alerts.sort(key=lambda a: (_SEV[a["severity"]], -float(a["value"])))
    return alerts


def summarize_alerts(alerts: list[dict]) -> dict:

    return {
        "total_alerts": len(alerts),
        "overcrowded_stops": len({(a["trip_id"], a["stop_id"]) for a in alerts if a["type"] == "OVERCROWDING"}),
        "delayed_trips": len({a["trip_id"] for a in alerts if a["type"] == "DELAY"}),
        "routes_delayed": sorted({a["route_id"] for a in alerts if a["type"] == "DELAY"}),
        "predicted_missed_connections": sum(1 for a in alerts if a["type"] == "MISSED_CONNECTION"),
        "predicted_unmet_demand": round(sum(a["value"] for a in alerts if a["type"] == "OVERCROWDING"), 1),
    }
