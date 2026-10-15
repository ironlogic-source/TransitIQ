import pandas as pd

from backend.constraints import cancel_unavailable_trips, validate_plan, check_capacity


def add(sched, tid, vid, route, dep):
    return pd.concat([sched, pd.DataFrame([dict(trip_id=tid, vehicle_id=vid, route_id=route, departure_time=dep)])],
                     ignore_index=True)


def test_baseline_plan_is_feasible(ctx, sched):
    r = validate_plan(sched, ctx)
    assert r["feasible"], r["violations"]


def test_overlapping_trip_rejected(ctx, sched):
    r = validate_plan(add(sched, "X", "B1", "A", 485), ctx)       # B1 is busy 480-495
    assert not r["details"]["no_trip_overlap"]["ok"]
    assert not r["feasible"]


def test_unavailable_vehicle_rejected(ctx_disrupted, sched):
    r = validate_plan(sched, ctx_disrupted)                        # B1 broken down, still scheduled
    assert not r["details"]["vehicle_availability"]["ok"]


def test_cancel_unavailable_trips(ctx_disrupted, sched):
    kept, cancelled = cancel_unavailable_trips(sched, ctx_disrupted)
    assert set(cancelled.vehicle_id) == {"B1"} and len(cancelled) == 3
    assert validate_plan(kept, ctx_disrupted)["feasible"]


def test_reachability_rejected(ctx, sched):
    # B3 ends route C at S6 at 491; route A starts at S1 (~2.5+ min deadhead is not enough here: S6->S1 far)
    r = validate_plan(add(sched, "X", "B3", "A", 493), ctx)
    assert not r["details"]["travel_time_reachability"]["ok"]


def test_turnaround_rejected(ctx, sched):
    # B2 ends route B at S6 at 490; route C starts at S3 (2.5 min away). 490+2.5+2 < 5 min turnaround
    r = validate_plan(add(sched, "X", "B2", "C", 495), ctx)
    assert not r["details"]["turnaround_time"]["ok"]


def test_departure_window_rejected(ctx, sched):
    s = sched.copy()
    s.loc[s.trip_id == "A1", "departure_time"] += 15               # max shift is 10
    assert not validate_plan(s, ctx)["details"]["departure_window"]["ok"]


def test_new_trip_outside_service_hours_rejected(ctx, sched):
    assert not validate_plan(add(sched, "X", "B4", "A", 300), ctx)["details"]["departure_window"]["ok"]


def test_capacity_violation_detected(ctx, sched):
    sim = {"occupancy": pd.DataFrame([dict(trip_id="A0", stop_id="S2", seq=1, onboard=45, boarded=45, left_behind=0)])}
    ok, msgs = check_capacity(sim, sched, ctx)                      # B1 capacity = 40
    assert not ok and "45" in msgs[0]
    assert not validate_plan(sched, ctx, sim)["feasible"]


def test_spare_bus_can_take_new_trip(ctx, sched):
    assert validate_plan(add(sched, "X", "B4", "A", 485), ctx)["feasible"]
