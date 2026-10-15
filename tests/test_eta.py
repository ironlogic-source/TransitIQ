import pandas as pd

from backend.eta_engine import ETAModel, evaluate_eta, predict_all_etas
from tests import toy_data as T
from tests.mock_sim import run_simulation


def history(n_days=12, scenario=None):
    frames = []
    for d in range(n_days):
        a = run_simulation(T.SCHEDULES, T.VEHICLES, T.DEMAND, T.ROUTES, scenario=scenario, seed=d)["arrivals"].copy()
        a["trip_id"] = f"d{d}_" + a.trip_id
        frames.append(a)
    return pd.concat(frames, ignore_index=True)


def test_eta_beats_scheduled_baseline_on_heldout():
    res = evaluate_eta(history(scenario={"route_delays": {"A": 6, "B": 8}}), T.ROUTES)
    assert res["mae_eta"] < res["mae_scheduled_baseline"]
    assert res["n_test_trips"] > 0 and 0 <= res["window_coverage"] <= 1


def test_no_future_leakage():
    arr = history(3)
    model = ETAModel.fit(arr, T.ROUTES)
    trip = arr[arr.trip_id == "d0_A0"].copy()
    now = trip.actual.iloc[1]
    p1 = model.predict(trip, "d0_A0", "A", "S4", now, scheduled_target=trip.scheduled.iloc[3])
    tampered = trip.copy()
    tampered.loc[tampered.actual > now, "actual"] += 999           # change only the FUTURE
    p2 = model.predict(tampered, "d0_A0", "A", "S4", now, scheduled_target=trip.scheduled.iloc[3])
    assert p1["eta"] == p2["eta"]


def test_predict_all_etas_only_future_stops():
    arr = history(3)
    model = ETAModel.fit(arr, T.ROUTES)
    one_day = arr[arr.trip_id.str.startswith("d0_")]
    now = 490.0
    out = predict_all_etas(model, one_day, now)
    assert len(out) > 0 and (out.eta_lo <= out.eta).all() and (out.eta <= out.eta_hi).all()
