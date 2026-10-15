"""
TransitIQ - pipeline_demo.py
End-to-end flow:  history -> ETA model -> forecast -> risks -> optimizer -> before/after.
This is the TEMPLATE for orchestrator.py (the junior copies the calls, app.py calls the orchestrator).

Run from repo root:   python -m backend.pipeline_demo
With real data:       swap the loaders for pd.read_csv("data/....csv") and import backend.simulation.
"""
from __future__ import annotations

from functools import partial

import pandas as pd

from backend.constraints import PlanContext, cancel_unavailable_trips
from backend.demand_engine import build_demand_model, forecast_trip_loads, forecast_unserved, rank_routes_by_excess
from backend.eta_engine import evaluate_eta, predict_all_etas
from backend.evaluation import compute_metrics
from backend.optimizer import optimize_plan
from backend.risk_engine import detect_risks, summarize_alerts

try:                                                   # real simulator from the sim teammate
    from backend.simulation import run_simulation
except ImportError:                                    # fallback so you can develop before it exists
    from tests.mock_sim import run_simulation


def load_data():
    try:
        d = "data/"
        return (pd.read_csv(d + "vehicles.csv"), pd.read_csv(d + "routes.csv"), pd.read_csv(d + "stops.csv"),
                pd.read_csv(d + "schedules.csv"), pd.read_csv(d + "passenger_demand.csv"), {})
    except FileNotFoundError:
        from tests import toy_data as T
        return T.VEHICLES, T.ROUTES, T.STOPS, T.SCHEDULES, T.DEMAND, T.PARAMS


def run_pipeline(scenario: dict | None = None, current_time: float = 490.0, verbose: bool = True) -> dict:
    vehicles, routes, stops, schedules, demand, params = load_data()
    scenario = scenario or {}
    ctx = PlanContext(vehicles, routes, stops, schedules, scenario=scenario, params=params)
    sim_fn = partial(run_simulation, vehicles=vehicles, demand=demand, routes=routes, scenario=scenario)

    # 1) ETA model: trained on NORMAL-operation history only (several seeds = several "days"), tested held-out
    frames = []
    for d in range(10):
        a = run_simulation(schedules, vehicles, demand, routes, scenario={}, seed=d)["arrivals"].copy()
        a["trip_id"] = f"d{d}_" + a.trip_id
        frames.append(a)
    eta_eval = evaluate_eta(pd.concat(frames, ignore_index=True), routes)
    model = eta_eval["model"]

    # 2) Live state under the scenario: ETAs only use observations <= current_time
    plan, _ = cancel_unavailable_trips(schedules, ctx)
    live = sim_fn(plan)
    etas = predict_all_etas(model, live["arrivals"], current_time)

    # 3) Forecast + risks (what the dashboard shows BEFORE optimizing)
    dmodel = build_demand_model(demand)
    loads = forecast_trip_loads(schedules, ctx, dmodel)
    unserved = forecast_unserved(schedules, ctx, dmodel)
    ranking = rank_routes_by_excess(loads, unserved)
    alerts = detect_risks(loads, etas)

    # 4) Optimize + prove
    result = optimize_plan(sim_fn, schedules, ctx, hot_routes=ranking.route_id.tolist())
    result["optimized_metrics"]["eta_mae"] = result["baseline_metrics"]["eta_mae"] = eta_eval["mae_eta"]

    out = {"eta_eval": eta_eval, "etas": etas, "loads": loads, "alerts": alerts,
           "kpis": summarize_alerts(alerts), "route_ranking": ranking, "result": result}
    if verbose:
        print(f"ETA MAE: model {eta_eval['mae_eta']} min vs timetable {eta_eval['mae_scheduled_baseline']} min "
              f"({eta_eval['improvement_pct']}% better, window coverage {eta_eval['window_coverage']:.0%})")
        print("KPIs:", out["kpis"])
        for a in alerts[:4]:
            print(" ALERT", a["severity"].upper(), "-", a["message"])
        print("\nSTATUS:", result["status"], "|", result["message"])
        for a in result["actions"]:
            print(" *", a["description"], "\n   ", a["reason"], "\n   ", a["tradeoff"])
        print(pd.DataFrame(result["comparison"])[["metric", "baseline", "optimized", "improvement_pct"]].to_string(index=False))
        print("Final plan feasible:", result["validation"]["feasible"])
    return out


if __name__ == "__main__":
    from tests.toy_data import DISRUPTION
    run_pipeline(DISRUPTION)
