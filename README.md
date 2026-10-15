<div align="center">

# 🚌 TransitIQ — RoutePulse
### Intelligent Campus Transport Planning · IIT Delhi
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.x-009688?logo=fastapi&logoColor=white)][def]
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![Branch](https://img.shields.io/badge/Branch-transitiq--clean-orange?logo=github)](https://github.com/ironlogic-source/TransitIQ/tree/transitiq-clean)

> **PS — RoutePulse**: Optimise Campus Transport Under Real Constraints  
> A transport-planning system that estimates arrival windows, forecasts passenger demand, and recommends feasible vehicle and schedule adjustments — while respecting hard operational constraints.

</div>

---

## 📋 Table of Contents

- [Problem Statement](#-problem-statement)
- [What TransitIQ Does](#-what-transitiq-does)
- [Architecture](#-architecture)
- [Project Structure](#-project-structure)
- [Data Model](#-data-model)
- [Pipeline: Predict → Optimize → Prove](#-pipeline-predict--optimize--prove)
- [Simulation Engine](#-simulation-engine)
- [Evaluation Criteria Coverage](#-evaluation-criteria-coverage)
- [Quickstart](#-quickstart)
- [API Reference](#-api-reference)
- [Scenarios & Disruption Testing](#-scenarios--disruption-testing)
- [Baseline vs Optimised Comparison](#-baseline-vs-optimised-comparison)
- [Assumptions](#-assumptions)
- [Team](#-team)

---

## 🎯 Problem Statement

Large institutional campuses — like IIT Delhi — operate multiple shuttle routes with:
- **Fixed departure windows** and capacity-limited vehicles
- **Uneven passenger demand** across stops and time windows
- **Hard constraints**: turnaround times, travel reachability, service hours, vehicle availability

A system that only shows vehicle locations does not solve the underlying planning problem.

**TransitIQ** addresses this by running a full **Predict → Optimize → Prove** pipeline — estimating arrival windows, detecting overcrowding and missed connections, recommending feasible adjustments, and quantitatively proving improvement against a baseline.

---

## ✨ What TransitIQ Does

| Capability | Description |
|---|---|
| 📍 **ETA Estimation** | Per-stop arrival windows with confidence intervals, trained from simulated GPS history |
| 👥 **Demand Forecasting** | Per-stop, per-window passenger load forecasting with scenario multipliers |
| ⚠️ **Risk Detection** | Overcrowding, near-capacity, delays, and missed connections — prioritised by severity |
| 🔧 **Schedule Optimisation** | Feasible trip re-timing and vehicle reallocation under hard constraints |
| 📊 **Before / After Comparison** | Measurable improvement in waiting time, unmet demand, and fleet utilisation |
| 🌩️ **Disruption Scenarios** | Vehicle breakdown, demand spikes, route delays — all tested |
| 🗺️ **IIT Delhi Map** | Real stop coordinates, routes, and fleet data modelled from campus layout |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        app.py  (FastAPI)                  │
│    GET /api/run  ·  GET /api/predict  ·  GET /api/meta      │
└────────────────────────┬────────────────────────────────────┘
                         │
              ┌──────────▼──────────┐
              │    orchestrator.py  │  ← master pipeline controller
              │  load → predict     │
              │  → optimize → prove │
              └──┬──────┬──────┬───┘
                 │      │      │
     ┌───────────▼─┐ ┌──▼───┐ ┌▼──────────┐
     │ simulation  │ │ eta  │ │ optimizer │
     │    .py      │ │engine│ │   .py     │
     │  (NEW ✅)   │ └──────┘ └───────────┘
     └─────────────┘
         │
  ┌──────▼──────────────────────────────────────┐
  │  demand_engine · risk_engine · constraints  │
  │           evaluation · orchestrator         │
  └─────────────────────────────────────────────┘
         │
  ┌──────▼──────┐
  │  data/      │
  │  *.csv      │  ← routes, stops, vehicles, schedules,
  │  *.db       │     passenger_demand, gps_traces
  └─────────────┘
```

---

## 📁 Project Structure

```
TransitIQ/
│
├── app.py                     # Flask REST API — entry point
│
├── backend/
│   ├── simulation.py          # ✅ Simulation engine (GPS replay + statistical model)
│   ├── orchestrator.py        # Master pipeline: load → predict → optimize → prove
│   ├── eta_engine.py          # ETA model (log-normal, trained from history)
│   ├── demand_engine.py       # Demand forecasting per stop/window
│   ├── risk_engine.py         # Overcrowding, delay, missed-connection detection
│   ├── optimizer.py           # Schedule & vehicle allocation optimiser
│   ├── constraints.py         # Hard constraint checkers (PlanContext)
│   └── evaluation.py          # Before/after metrics computation
│
├── data/
│   ├── routes.csv             # IIT Delhi route topology (route_id, seq, stop_id, seg_time_min)
│   ├── stops.csv              # Stop coordinates (x, y in metres / lat-lon)
│   ├── vehicles.csv           # Fleet: capacity, availability, depot, allowed routes
│   ├── schedules.csv          # Planned trips (trip_id, vehicle_id, route_id, departure_time)
│   ├── passenger_demand.csv   # Demand per (route, stop, 30-min window)
│   ├── gps_traces.csv         # Simulated GPS positions for live replay
│   └── transitiq.db           # SQLite master database (same data, relational)
│
├── tests/
│   ├── toy_data.py            # Minimal synthetic dataset for unit tests
│   ├── mock_sim.py            # Lightweight simulator (used if simulation.py missing)
│   ├── conftest.py            # Pytest fixtures
│   ├── test_eta.py
│   ├── test_constraints.py
│   └── test_optimizer.py
│
├── requirements.txt
└── README.md
```

---

## 🗄️ Data Model

### `stops.csv`
| Column | Type | Description |
|---|---|---|
| `stop_id` | str | Unique stop identifier (e.g. `S_MAIN_GATE`) |
| `name` | str | Human-readable stop name |
| `x` | float | Easting / longitude |
| `y` | float | Northing / latitude |

### `routes.csv`
| Column | Type | Description |
|---|---|---|
| `route_id` | str | Route identifier (e.g. `IIT_CIRCULAR`) |
| `seq` | int | Stop sequence (0-indexed) |
| `stop_id` | str | Stop at this position |
| `seg_time_min` | float | Scheduled travel time from previous stop (min) |

### `vehicles.csv`
| Column | Type | Description |
|---|---|---|
| `vehicle_id` | str | Vehicle identifier |
| `capacity` | int | Passenger capacity |
| `available` | 0/1 | Whether available today |
| `depot_stop_id` | str | Home depot stop |
| `allowed_routes` | str | Semicolon-separated allowed route IDs |

### `schedules.csv`
| Column | Type | Description |
|---|---|---|
| `trip_id` | str | Unique trip identifier |
| `vehicle_id` | str | Assigned vehicle |
| `route_id` | str | Route to run |
| `departure_time` | float | Minutes since midnight (e.g. 480 = 08:00) |

### `passenger_demand.csv`
| Column | Type | Description |
|---|---|---|
| `route_id` | str | Route |
| `stop_id` | str | Stop |
| `window_start` | float | Start of 30-min window (minutes since midnight) |
| `passenger_count` | float | Expected boarding passengers |

---

## 🔄 Pipeline: Predict → Optimize → Prove

```
Phase A — PREDICT
  ├── Load & validate 5 data tables
  ├── Run simulation.py → arrivals, occupancy, waiting, unserved
  ├── Train ETA model on simulated history (10 days)
  ├── Forecast per-trip passenger loads
  ├── Detect risks: overcrowding · delays · missed connections
  └── Output: KPIs, alerts, ETAs, route ranking

Phase B — OPTIMIZE
  ├── Rank routes by excess demand
  ├── Generate candidate re-timings / vehicle swaps
  ├── Validate each candidate against ALL hard constraints
  └── Output: proposed_plan, actions with trade-off explanations

Phase C — PROVE
  ├── Re-simulate proposed plan
  ├── Compute Before / After metrics
  └── Output: comparison table, feasibility verdict
```

**Sample terminal output:**
```
Scenario: normal | time 08:10 | simulator: backend.simulation
ETA MAE: model 1.649 min vs timetable 6.077 min (72.9% better, window coverage 79%)
KPIs (before): total_alerts=34, overcrowded_stops=30, predicted_unmet_demand=98.8
 ALERT HIGH  - 12 passengers left at S_HOSTEL_ZANSKAR (08:58)
 ALERT MEDIUM - Trip T001 predicted 10 min late at S_HOSPITAL
```

---

## ⚙️ Simulation Engine

`backend/simulation.py` is the core physics layer that every other module depends on.

### Travel Time Model
Segment travel times follow a **log-normal distribution** — always positive, right-skewed like real traffic:

$$t_{seg} \sim \text{LogNormal}\!\left(\ln(\mu \cdot c) - \frac{\sigma^2}{2},\ \sigma\right)$$

where:
- $\mu$ = scheduled segment time (minutes)
- $c$ = peak-hour congestion multiplier
- $\sigma = 0.14$ (≈ 15% coefficient of variation, IIT Delhi campus calibration)

### Peak-Hour Congestion
| Window | Multiplier | Reason |
|---|---|---|
| 08:00 – 10:00 | **1.35×** | Morning rush to classes |
| 12:00 – 14:00 | **1.20×** | Lunch hour |
| 17:00 – 19:00 | **1.15×** | Evening dispersal |

### GPS-Trace Replay
If live `gps_traces` data is provided, the simulator **interpolates real vehicle positions** to derive actual arrival times — overriding the statistical model for trips with coverage. Trips without traces fall back to the log-normal model.

### Scenario Handling
| Scenario Key | Effect |
|---|---|
| `unavailable_vehicles` | Cancels all trips assigned to listed vehicles |
| `demand_multiplier` | Scales per-stop or global passenger counts |
| `route_delays` | Adds a fixed offset to actual arrival times on a route |

### Output Contract
```python
run_simulation(...) -> {
    "arrivals":  DataFrame[trip_id, vehicle_id, route_id, stop_id, seq, scheduled, actual],
    "occupancy": DataFrame[trip_id, vehicle_id, stop_id, seq, onboard, boarded, left_behind, capacity],
    "waiting":   DataFrame[stop_id, passengers, wait_min],
    "unserved":  DataFrame[route_id, stop_id, window_start, passengers],
}
```

---

## 📊 Evaluation Criteria Coverage

| Criterion | Weight | How TransitIQ addresses it |
|---|---|---|
| **Plan feasibility & constraint compliance** | 20% | `constraints.py` enforces 7 hard checks: no overlap, turnaround, reachability, departure window, capacity, vehicle availability, route compatibility |
| **ETA quality** | 15% | `eta_engine.py` trains a log-normal + auto-regressive ETA model; evaluated via held-out MAE vs timetable baseline |
| **Demand & capacity handling** | 15% | `demand_engine.py` forecasts per-stop loads; `risk_engine.py` flags overcrowding and left-behind passengers |
| **Operational improvement** | 20% | `evaluation.py` computes Before/After: waiting time, unmet demand, fleet utilisation, missed connections |
| **Robustness to disruptions** | 10% | `scenarios.json` supports vehicle breakdown, demand spike (×1.5), route delays; all tested |
| **Engineering & reproducibility** | 10% | Seeded RNG (`seed=42`), deterministic per-trip hash, reproducible CSV + SQLite data, full pytest suite |
| **Explainability & commercial relevance** | 10% | Every optimizer action includes `description`, `reason`, `tradeoff`; REST API suitable for operator dashboard |

---

## 🚀 Quickstart

### 1. Clone & install
```bash
git clone https://github.com/ironlogic-source/TransitIQ.git
cd TransitIQ
git checkout transitiq-clean

pip install -r requirements.txt
```

### 2. Run the full pipeline (CLI)
```bash
python -m backend.orchestrator
```

### 3. Start the API server
```bash
python app.py
# → http://localhost:5000
```

### 4. Run tests
```bash
pytest tests/ -v
```

---

## 🌐 API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Health check + fleet summary |
| `GET` | `/api/meta` | Network stats (routes, stops, vehicles, trips) |
| `GET` | `/api/scenarios` | List available disruption scenarios |
| `GET/POST` | `/api/predict` | Predict-only: ETAs, loads, alerts, KPIs |
| `GET/POST` | `/api/run` | Full pipeline: Predict + Optimize + Prove |

### Example: Run with disruption scenario
```bash
curl "http://localhost:5000/api/run?scenario=disruption"
```

### Example: POST with custom weights
```bash
curl -X POST http://localhost:5000/api/run \
  -H "Content-Type: application/json" \
  -d '{"scenario": {"demand_multiplier": {"*": 1.5}}, "weights": {"unmet_demand": 2.0}}'
```

### Response shape (`/api/run`)
```json
{
  "scenario_name": "custom",
  "current_time_label": "08:10",
  "kpis": { "total_alerts": 12, "overcrowded_stops": 3, "predicted_unmet_demand": 42.1 },
  "alerts": [ { "type": "OVERCROWDING", "severity": "high", "message": "..." } ],
  "result": {
    "status": "improved",
    "actions": [ { "description": "...", "reason": "...", "tradeoff": "..." } ],
    "comparison": [ { "metric": "unmet_demand", "baseline": 98.8, "optimized": 41.2, "improvement_pct": 58.3 } ]
  },
  "after": { "kpis": { ... } },
  "timings": { "total": 0.21 }
}
```

---

## 🌩️ Scenarios & Disruption Testing

Define scenarios in `data/scenarios.json` or pass inline:

```json
{
  "normal":     {},
  "peak_surge": { "demand_multiplier": { "*": 1.5 } },
  "breakdown":  { "unavailable_vehicles": ["V_ERICK_1"] },
  "road_block": { "route_delays": { "IIT_CIRCULAR": 8 } },
  "combined":   {
    "unavailable_vehicles": ["V_ERICK_1"],
    "demand_multiplier": { "S_HOSTEL_ZANSKAR": 2.0 },
    "route_delays": { "IIT_CIRCULAR": 5 }
  }
}
```

---

## 📈 Baseline vs Optimised Comparison

| Metric | Baseline | Optimised | Δ |
|---|---|---|---|
| Unmet demand (passengers) | 98.8 | ~41 | ↓ ~58% |
| ETA MAE (minutes) | 6.1 (timetable) | 1.6 (model) | ↓ 72.9% |
| Overcrowded stop events | 30 | reduced | ↓ |
| Plan feasibility | ✅ Pass | ✅ Pass | — |

> Numbers are from the IIT Delhi campus dataset, normal-day scenario, `seed=42`.

---

## 📌 Assumptions

1. **Coordinate system**: Stop `x`, `y` fields use decimal degrees (lat/lon) matching IIT Delhi campus geography.
2. **Demand windows**: 30-minute buckets, aligned to `passenger_demand.csv` `window_start`.
3. **Travel time variability**: Log-normal with σ = 0.14 (≈ 15% CV) calibrated to narrow campus roads with speed-bumps; adjustable via constructor.
4. **Alighting fraction**: 25% of onboard passengers alight at every intermediate stop (uniform model).
5. **Deadhead speed**: 280 m/min (~17 km/h) for empty-bus repositioning between routes.
6. **Service hours**: 06:00 – 20:00 (360 – 1200 minutes since midnight).
7. **GPS replay**: When `gps_traces` covers a trip, actual positions override the statistical model for those segments only.
8. **ETA training**: 10 simulated history days (seeds 0–41, excluding the live seed 42) used to train the segment-time model.

---

## 👥 Team

> **TransitIQ** — built for PS 02 · RoutePulse

| Role | Contribution |
|---|---|
| Backend / Simulation | `backend/simulation.py`, orchestrator, pipeline |
| Data & Infrastructure | IIT Delhi data model, SQLite schema, CSV generation |
| Frontend | Dashboard UI *(in progress — separate branch)* |
| Optimisation | `optimizer.py`, `constraints.py`, `evaluation.py` |

---

<div align="center">

Made with ☕ for **PS 02 — RoutePulse**

[🔗 GitHub](https://github.com/ironlogic-source/TransitIQ) · [📦 Branch: transitiq-clean](https://github.com/ironlogic-source/TransitIQ/tree/transitiq-clean)

</div>


[def]: https://fastapi.tiangolo.com