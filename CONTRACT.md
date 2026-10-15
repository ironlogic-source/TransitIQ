# TransitIQ Data & Interface Contract (v1)
Time = **simulated minutes from 00:00** (08:00 = 480). Distances in **metres**. One name per concept: `vehicle_id`, `route_id`, `stop_id`, `trip_id` (never `bus_id`).

## CSV files (data/)
| File | Columns |
|---|---|
| stops.csv | stop_id, name, x, y |
| routes.csv | route_id, seq (0..n), stop_id, seg_time_min (timetable minutes from previous stop; 0 for seq 0) |
| vehicles.csv | vehicle_id, capacity, available (1/0), depot_stop_id, [allowed_routes = "A;B" optional] |
| schedules.csv | trip_id, vehicle_id, route_id, departure_time |
| passenger_demand.csv | route_id, stop_id, window_start, passenger_count  (30-min windows; may have extra `day` column) |
| gps_traces.csv | vehicle_id, trip_id, timestamp, lat/x, y  (optional, ETA uses `arrivals` below) |

## Scenario dict (scenarios.json -> dict)
```json
{"unavailable_vehicles": ["B1"],            // or {"B1": 495} = unavailable from 08:15
 "demand_multiplier": {"S1": 1.4},          // or {"*": 1.2} for all stops
 "route_delays": {"B": 6}}                  // minutes added at trip start
```

## Simulator function (simulation.py, owned by sim teammate)
```python
run_simulation(schedules, vehicles, demand, routes, scenario=None, seed=42) -> dict
```
Must be **deterministic** for the same inputs+seed, **fast** (<0.1 s; the optimizer calls it ~200x), and must **skip trips of unavailable vehicles**. Returns DataFrames:
- `arrivals`: trip_id, vehicle_id, route_id, stop_id, seq, scheduled, actual   (one row per trip x stop)
- `occupancy`: trip_id, stop_id, seq, onboard, boarded, left_behind  (+ vehicle_id, capacity optional)
- `waiting`: stop_id, passengers, wait_min   (wait per passenger of that group)
- `unserved`: route_id, stop_id, window_start, passengers   (demand in windows with no trip at all; empty if none)

Reference implementation: `tests/mock_sim.py` (same contract).

## Functions the algorithm side exposes (used by orchestrator.py)
| Module | Call | Returns |
|---|---|---|
| eta_engine | `evaluate_eta(history_arrivals, routes)` -> `["model"]`, MAE numbers | dict |
| eta_engine | `predict_all_etas(model, arrivals, current_time)` | DataFrame (eta, eta_lo, eta_hi, predicted_delay) |
| demand_engine | `build_demand_model(demand)`, `forecast_trip_loads(schedules, ctx, model)`, `forecast_unserved(...)`, `rank_routes_by_excess(loads, unserved)` | DataFrames |
| risk_engine | `detect_risks(loads, etas)`, `summarize_alerts(alerts)` | list[dict], KPI dict |
| optimizer | `optimize_plan(run_sim, schedules, ctx, hot_routes=[...])` | result dict (below) |
| constraints | `PlanContext(...)`, `validate_plan(schedules, ctx, sim=None)`, `cancel_unavailable_trips` | dict / tuples |

### optimize_plan result keys
`status` (improved | no_improvement | no_feasible_candidates | no_action_needed), `message`, `actions[]` (description, reason, tradeoff, constraints_satisfied), `baseline_metrics`, `optimized_metrics`, `comparison[]` (metric, baseline, optimized, improvement_pct, better), `original_plan[]`, `proposed_plan[]`, `cancelled_trips[]`, `validation` {feasible, details{check:{ok,violations}}}, `candidates_evaluated`, `candidates_rejected`, `rejection_examples`, `_baseline_sim` / `_optimized_sim` (DataFrames for charts).
