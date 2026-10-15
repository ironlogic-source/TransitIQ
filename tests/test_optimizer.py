import pandas as pd

from backend.constraints import PlanContext, validate_plan
from backend.demand_engine import build_demand_model, forecast_trip_loads, forecast_unserved, rank_routes_by_excess
from backend.eta_engine import ETAModel, predict_all_etas
from backend.optimizer import optimize_plan
from backend.risk_engine import detect_risks, summarize_alerts
from tests import toy_data as T


def test_optimizer_recovers_from_breakdown(ctx_disrupted, sched, run_sim_disrupted):
    res = optimize_plan(run_sim_disrupted, sched, ctx_disrupted, max_steps=3)
    assert res["status"] == "improved"
    assert res["objective_optimized"] < res["objective_baseline"]
    assert res["optimized_metrics"]["unmet_demand"] < res["baseline_metrics"]["unmet_demand"]
    assert res["validation"]["feasible"]                          # final plan obeys every hard constraint
    assert res["optimized_metrics"]["capacity_violations"] == 0
    assert all(a["constraints_satisfied"] for a in res["actions"])


def test_optimizer_is_deterministic(ctx_disrupted, sched, run_sim_disrupted):
    a = optimize_plan(run_sim_disrupted, sched, ctx_disrupted)
    b = optimize_plan(run_sim_disrupted, sched, ctx_disrupted)
    assert a["actions"] == b["actions"] and a["objective_optimized"] == b["objective_optimized"]


def test_no_feasible_solution_message(sched, run_sim_disrupted):
    # every bus unavailable -> nothing can legally be added
    scen = {"unavailable_vehicles": ["B1", "B2", "B3", "B4"]}
    ctx = PlanContext(T.VEHICLES, T.ROUTES, T.STOPS, T.SCHEDULES, scenario=scen, params=T.PARAMS)
    from functools import partial
    from tests.mock_sim import run_simulation
    sim = partial(run_simulation, vehicles=T.VEHICLES, demand=T.DEMAND, routes=T.ROUTES, scenario=scen)
    res = optimize_plan(sim, sched, ctx, hot_routes=["A"])
    assert res["status"] in ("no_feasible_candidates", "no_improvement")
    assert res["action"] is None
    assert res["validation"]["feasible"]


def test_never_returns_invalid_plan(ctx_disrupted, sched, run_sim_disrupted):
    res = optimize_plan(run_sim_disrupted, sched, ctx_disrupted, max_steps=3)
    plan = pd.DataFrame(res["proposed_plan"])
    assert validate_plan(plan, ctx_disrupted)["feasible"]


def test_demand_and_risk_flags_overcrowding(ctx_disrupted, sched):
    model = build_demand_model(T.DEMAND)
    loads = forecast_trip_loads(sched, ctx_disrupted, model)
    assert not loads.empty and "B1" not in set(loads.vehicle_id)  # B1 cancelled
    alerts = detect_risks(loads)
    assert any(a["type"] == "OVERCROWDING" for a in alerts)
    assert summarize_alerts(alerts)["predicted_unmet_demand"] > 0
    unserved = forecast_unserved(sched, ctx_disrupted, model)
    assert set(unserved.route_id) == {"A"}                           # every A trip was cancelled
    assert rank_routes_by_excess(loads, unserved).route_id.tolist()[0] == "A"
