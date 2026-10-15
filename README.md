# TransitIQ

AI-assisted campus transport optimization: **Predict -> Optimize -> Prove**.
TransitIQ simulates a campus bus network, predicts problems (delays, overcrowding, missed connections),
recommends a constraint-checked fix, and shows a Before-vs-After comparison from the same simulation.

> **Status: TEMPORARY README.** Placeholders marked `TODO` will be filled in as the project is finalized.

## Team
| Role | Owner | Files |
|---|---|---|
| Data & simulation | TODO | `backend/simulation.py`, `data/` |
| ETA, demand, risk, optimizer | TODO | `backend/eta_engine.py`, `demand_engine.py`, `risk_engine.py`, `constraints.py`, `optimizer.py`, `evaluation.py` |
| Orchestration / backend structure | TODO | `backend/orchestrator.py` |
| Frontend & demo | TODO | `app.py` |

## Project structure
```
TransitIQ/
├── app.py                  # Streamlit dashboard
├── backend/
│   ├── orchestrator.py     # glue: calls the modules below
│   ├── simulation.py       # run_simulation(...)
│   ├── eta_engine.py       # ETA + arrival windows, MAE evaluation
│   ├── demand_engine.py    # demand forecast, per-trip capacity gap
│   ├── risk_engine.py      # alerts (overcrowding, delay, missed connection)
│   ├── constraints.py      # hard-constraint validation
│   ├── optimizer.py        # greedy constraint-aware optimizer (PulseRescue)
│   ├── evaluation.py       # metrics + objective J + before/after table
│   └── pipeline_demo.py    # end-to-end example / orchestrator template
├── data/                   # routes, stops, vehicles, schedules, passenger_demand, gps_traces
├── tests/                  # pytest suite + toy data + mock simulator
├── CONTRACT.md             # data and function contract between teammates
├── INTEGRATION_GUIDE.md    # how the modules connect
└── requirements.txt
```

## How it works
1. **Predict:** ETA model (historical segment means + recent-delay carry-over) with arrival windows; demand forecast from historical averages; risk engine flags overcrowding, delays, and likely missed connections before boarding.
2. **Optimize:** greedy search over candidate actions (add trip, reassign trip, swap to larger bus, shift departure). Any candidate that breaks a hard constraint is rejected; survivors are simulated and scored.
3. **Prove:** baseline and optimized plans run on identical demand and disruptions; metrics are compared side by side. If nothing feasible helps, the system says so and lists why.

### Hard constraints
Vehicle availability, route compatibility, no overlapping trips, travel-time reachability, turnaround time, departure window, vehicle capacity.

### Objective
`J = w_wait * avg_wait_min + w_unmet * unmet_passengers + w_missed * missed_connections + w_cost * vehicle_minutes`
Default weights: wait 10, unmet 1, missed 2, cost 0.05 (set before final evaluation; see `backend/evaluation.py`). Constraint violations are prohibited, never penalized.

### Metrics
Average waiting time, unmet demand, missed connections, capacity violations, fleet utilization (productive vehicle-minutes / available vehicle-minutes), average delay, operational cost, ETA MAE vs timetable baseline.

## Setup
```bash
pip install -r requirements.txt
python -m pytest -q                 # run tests (from repo root)
python -m backend.pipeline_demo     # end-to-end demo in the terminal
streamlit run app.py                # dashboard (TODO: once app.py is ready)
```

## Data & reproducibility
- Time is simulated minutes from 00:00; distances in metres. Full schema in `CONTRACT.md`.
- Fixed random seed for every scenario; the optimizer is deterministic for a given input.
- Scenarios: normal, demand surge, bus breakdown / delay (TODO: finalize in `scenarios.json`).

## Results
TODO: fill in real baseline-vs-optimized numbers from the final simulation (do not use the toy-data numbers).

| Metric | Baseline | Optimized |
|---|---|---|
| Avg waiting time (min) | TODO | TODO |
| Unmet demand | TODO | TODO |
| Missed connections | TODO | TODO |
| Capacity violations | TODO | TODO |
| Fleet utilization | TODO | TODO |
| ETA MAE (min) | TODO | TODO |

## Known limitations
Greedy (not globally optimal) search; straight-line deadhead times; demand split equally between trips in a window; fixed alighting fraction; historical-average demand model.

## Demo script
TODO: normal day -> simulate disruption -> optimize -> apply plan -> show before/after and constraint checks.
