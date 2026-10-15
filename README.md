# 🚌 TransitIQ — RoutePulse

<div align="center">

### Intelligent Campus Transport Planning

**Smarter Routes. Smoother Rides.**

[![Live Demo](https://img.shields.io/badge/Live%20Demo-Open%20TransitIQ-2563EB?style=for-the-badge&logo=vercel)](https://transit-iq-eta.vercel.app/)

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Vercel](https://img.shields.io/badge/Frontend-Deployed%20on%20Vercel-black?logo=vercel)](https://vercel.com/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

**[🚀 Live Application](https://transit-iq-eta.vercel.app/) · [💻 GitHub Repository](https://github.com/ironlogic-source/TransitIQ)**

</div>

---

## 📋 Table of Contents

- [Live Demo](#-live-demo)
- [Problem Statement](#-problem-statement)
- [What TransitIQ Does](#-what-transitiq-does)
- [Architecture](#-architecture)
- [Project Structure](#-project-structure)
- [Data Model](#-data-model)
- [Pipeline: Predict → Optimize → Prove](#-pipeline-predict--optimize--prove)
- [Simulation Engine](#-simulation-engine)
- [Evaluation Criteria Coverage](#-evaluation-criteria-coverage)
- [Quickstart](#-quickstart)
- [Deployment](#-deployment)
- [API Reference](#-api-reference)
- [Scenarios and Disruption Testing](#-scenarios-and-disruption-testing)
- [Baseline vs Optimized Comparison](#-baseline-vs-optimized-comparison)
- [Assumptions and Limitations](#-assumptions-and-limitations)
- [Challenges Faced](#-challenges-faced)
- [Team](#-team)

---

## 🌐 Live Demo

**Try TransitIQ:** [https://transit-iq-eta.vercel.app/](https://transit-iq-eta.vercel.app/)

TransitIQ has a deployed web frontend hosted on Vercel and a separately hosted backend API.

The application demonstrates how campus transport operations can be analysed and improved through arrival-time estimation, passenger-demand analysis, risk detection, and schedule and vehicle-allocation optimization.

> **Note:** TransitIQ uses a simulation-based approach where real-time GPS feeds or verified operational data are not available. Its estimates and comparisons depend on the supplied dataset, simulation assumptions, and selected scenario.

---

## 🎯 Problem Statement

**PS 02 — RoutePulse: Optimise Campus Transport Under Real Constraints**

Large institutional campuses can face transport challenges such as:

- Fixed departure schedules and capacity-limited vehicles.
- Uneven passenger demand across stops and time windows.
- Delayed arrivals and missed connections.
- Overcrowding and passengers left behind.
- Inefficient vehicle allocation and schedule conflicts.

A system that only displays vehicle locations does not solve the underlying planning problem.

TransitIQ addresses this challenge through a **Predict → Optimize → Prove** pipeline. It estimates arrival windows, analyses passenger demand, detects operational risks, recommends feasible adjustments, and compares proposed plans against a baseline.

The goal is to help campus transport operators make more informed, efficient, and reliable planning decisions.

---

## ✨ What TransitIQ Does

| Capability | Description |
|---|---|
| 📍 ETA Estimation | Estimates arrival times at stops using available schedule and simulated travel-time history. |
| 👥 Demand Forecasting | Analyses passenger demand by route, stop, and time window. |
| ⚠️ Risk Detection | Identifies overcrowding, capacity violations, delays, and potential missed connections. |
| 🔧 Schedule Optimization | Evaluates feasible trip re-timing and vehicle reallocation options. |
| 📊 Before/After Comparison | Compares baseline and proposed plans using operational metrics. |
| 🌩️ Disruption Scenarios | Simulates demand surges, vehicle unavailability, and route delays. |
| 🗺️ Campus Route Modelling | Represents routes, stops, vehicles, schedules, and passenger demand in a structured data model. |

---

## 🏗️ Architecture

TransitIQ separates the user interface from the backend processing and optimization logic.

```text
                  USER
                   |
                   v
       +-------------------------+
       |     Frontend (Vite)     |
       |       React UI          |
       |   Deployed on Vercel    |
       +------------+------------+
                    |
                    | HTTP / JSON
                    v
       +-------------------------+
       |      Backend API        |
       |      FastAPI / Uvicorn  |
       |       Hosted on Render  |
       +------------+------------+
                    |
                    v
       +-------------------------+
       |   Planning Pipeline     |
       |                         |
       |  Data Validation        |
       |  ETA Estimation         |
       |  Demand Analysis        |
       |  Risk Detection         |
       |  Schedule Optimization  |
       |  Before/After Evaluation|
       +------------+------------+
                    |
                    v
       +-------------------------+
       |     Data Sources        |
       | CSV / SQLite / Simulated|
       | GPS and demand history  |
       +-------------------------+
```

### Technology Stack

| Component | Technology |
|---|---|
| Frontend | React, Vite, JavaScript |
| Backend API | Python, FastAPI, Uvicorn |
| Data Processing | Python and Pandas |
| Data Storage | CSV and SQLite, where configured |
| Optimization | Greedy candidate selection with operational constraint checks |
| Frontend Hosting | Vercel |
| Backend Hosting | Render |
| Version Control | Git and GitHub |

---

## 📁 Project Structure

The repository contains the frontend, backend logic, data, and tests. The exact modules may evolve as development continues.

```text
TransitIQ/
│
├── frontend/
│   ├── src/
│   │   └── App.jsx
│   ├── public/
│   ├── package.json
│   ├── vercel.json
│   └── vite.config.js
│
├── backend/
│   ├── simulation.py
│   ├── orchestrator.py
│   ├── eta_engine.py
│   ├── demand_engine.py
│   ├── risk_engine.py
│   ├── optimizer.py
│   ├── constraints.py
│   └── evaluation.py
│
├── data/
│   ├── routes.csv
│   ├── stops.csv
│   ├── vehicles.csv
│   ├── schedules.csv
│   ├── passenger_demand.csv
│   └── gps_traces.csv
│
├── tests/
│   ├── conftest.py
│   ├── toy_data.py
│   ├── test_eta.py
│   ├── test_constraints.py
│   └── test_optimizer.py
│
├── app.py
├── requirements.txt
├── README.md
└── LICENSE
```

*Note: Some optional files and module names may differ between branches. Check the repository for the latest implementation.*

---

## 🗄️ Data Model

TransitIQ represents the main entities involved in campus transport planning.

### `stops.csv`

| Column | Description |
|---|---|
| `stop_id` | Unique identifier for a stop |
| `name` | Human-readable stop name |
| `x` | Stop coordinate or east-west position |
| `y` | Stop coordinate or north-south position |

### `routes.csv`

| Column | Description |
|---|---|
| `route_id` | Route identifier |
| `seq` | Stop sequence along the route |
| `stop_id` | Stop associated with the sequence |
| `seg_time_min` | Expected travel time from the previous stop, in minutes |

### `vehicles.csv`

| Column | Description |
|---|---|
| `vehicle_id` | Unique vehicle identifier |
| `capacity` | Maximum passenger capacity |
| `available` | Vehicle availability indicator |
| `depot_stop_id` | Vehicle's home depot |
| `allowed_routes` | Routes the vehicle can operate |

### `schedules.csv`

| Column | Description |
|---|---|
| `trip_id` | Unique trip identifier |
| `vehicle_id` | Assigned vehicle |
| `route_id` | Assigned route |
| `departure_time` | Scheduled departure, represented as minutes since midnight |

### `passenger_demand.csv`

| Column | Description |
|---|---|
| `route_id` | Associated route |
| `stop_id` | Associated stop |
| `window_start` | Start of the demand time window |
| `passenger_count` | Expected passenger demand |

### `gps_traces.csv`

When supplied, GPS traces can be used to replay vehicle movement and derive observed or simulated arrival times. If historical or live GPS observations are unavailable, the simulation uses its configured travel-time model instead.

---

## 🔄 Pipeline: Predict → Optimize → Prove

TransitIQ structures the planning process into three stages.

### Phase A — Predict

- Load and validate the available transport data.
- Simulate trips and estimate arrival times.
- Estimate passenger demand and vehicle occupancy.
- Detect capacity issues, delays, and missed connections.
- Generate operational indicators and alerts.

### Phase B — Optimize

- Identify routes and time windows with excess demand.
- Generate candidate schedule adjustments or vehicle reallocations.
- Check candidate plans against operational constraints.
- Explain recommended changes and their trade-offs.

### Phase C — Prove

- Evaluate the proposed plan against the baseline.
- Recalculate operational metrics using the same evaluation approach.
- Compare passenger waiting, unmet demand, fleet utilization, and other supported metrics.
- Report whether the proposed plan is feasible and whether it improves the selected objectives.

---

## ⚙️ Simulation Engine

The simulation layer provides a controlled way to evaluate transport plans without depending entirely on live vehicle feeds.

### Travel-Time Modelling

A configurable statistical model can represent variation in segment travel times. A log-normal distribution is one option because it produces positive travel times with a longer upper tail.

\[
T_{\text{segment}} \sim \operatorname{LogNormal}(\mu_{\log}, \sigma)
\]

The parameters can represent scheduled travel time and traffic conditions. They should be calibrated against reliable historical observations when those observations are available.

### Peak-Hour Congestion

Peak-hour multipliers can be used to represent increased travel times during busy periods.

| Example Time Window | Illustrative Multiplier | Intended Scenario |
|---|---:|---|
| 08:00–10:00 | 1.35× | Morning rush |
| 12:00–14:00 | 1.20× | Lunch period |
| 17:00–19:00 | 1.15× | Evening dispersal |

These are simulation parameters, not claims about measured campus traffic.

### Scenario Handling

| Scenario Input | Intended Effect |
|---|---|
| `unavailable_vehicles` | Marks selected vehicles as unavailable. |
| `demand_multiplier` | Increases or decreases demand for selected stops or across the network. |
| `route_delays` | Adds a delay to trips on selected routes. |

The simulator can then evaluate the resulting impact on service and candidate plans.

---

## 📊 Evaluation Criteria Coverage

TransitIQ is designed around the main requirements of a constrained campus transport optimization problem.

| Criterion | How TransitIQ Addresses It |
|---|---|
| Plan feasibility | Checks vehicle availability, route compatibility, capacity, and schedule constraints supported by the implementation. |
| ETA quality | Evaluates arrival-time estimates against an appropriate baseline where reference data is available. |
| Demand and capacity | Analyses passenger loads and identifies capacity risks. |
| Operational improvement | Compares baseline and proposed plans using supported performance metrics. |
| Disruption robustness | Tests configured demand spikes, delays, and vehicle-unavailability scenarios. |
| Engineering and reproducibility | Uses structured data, version control, and tests where implemented. |
| Explainability | Presents the reasons and trade-offs behind proposed changes where supported. |

---

## 🚀 Quickstart

### Prerequisites

- Python 3.10 or later.
- Node.js and npm for running the frontend.
- Git.

### 1. Clone the repository

```bash
git clone https://github.com/ironlogic-source/TransitIQ.git
cd TransitIQ
```

### 2. Install backend dependencies

```bash
pip install -r requirements.txt
```

### 3. Start the backend

The deployed backend uses Uvicorn. For a FastAPI application exposed as `app` in `app.py`, run:

```bash
uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

If the application entry point or exported ASGI object differs in your checked-out branch, use the matching configuration from that branch.

### 4. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Vite will print the local development URL in the terminal.

### 5. Open the deployed application

Prefer the public demo if you just want to try the project:

**[Launch TransitIQ](https://transit-iq-eta.vercel.app/)**

---

## ☁️ Deployment

TransitIQ is deployed as a frontend and a separate backend service.

| Component | Platform | Link |
|---|---|---|
| Frontend | Vercel | [Open TransitIQ](https://transit-iq-eta.vercel.app/) |
| Source Code | GitHub | [ironlogic-source/TransitIQ](https://github.com/ironlogic-source/TransitIQ) |
| Backend API | Render | [Backend service](https://transitiq-a3tm.onrender.com/) |

The frontend uses Vercel rewrites to forward `/api/...` requests to the backend service.

The backend may take some time to respond after inactivity if hosted on a free instance. Availability depends on the hosting platform and service configuration.

---

## 🌐 API Reference

The API exposes the following routes where implemented by the deployed backend.

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/` | Root endpoint or service response |
| `GET` | `/api/meta` | Network or application metadata |
| `GET` | `/api/scenarios` | Available disruption scenarios |
| `GET` / `POST` | `/api/predict` | Prediction and risk-analysis request |
| `GET` / `POST` | `/api/run` | Run the planning and evaluation pipeline |

### Example Requests

Inspect application metadata:

```bash
curl https://transitiq-a3tm.onrender.com/api/meta
```

Request a prediction:

```bash
curl https://transitiq-a3tm.onrender.com/api/predict
```

Run the planning pipeline:

```bash
curl "https://transitiq-a3tm.onrender.com/api/run?scenario=normal"
```

The exact accepted query parameters, request body, and response fields depend on the backend version deployed. Refer to the implementation or its generated API documentation for the definitive contract.

---

## 🌩️ Scenarios and Disruption Testing

TransitIQ can use configurable scenarios to explore different operating conditions.

| Scenario | Example |
|---|---|
| Normal operations | Standard demand and vehicle availability |
| Peak demand | Increase passenger demand in selected time windows |
| Vehicle breakdown | Make a vehicle unavailable |
| Route delay | Add a delay to a selected route |
| Combined disruption | Combine a demand spike, a delay, and vehicle unavailability |

Example scenario configuration:

```json
{
  "normal": {},
  "peak_surge": {
    "demand_multiplier": {
      "*": 1.5
    }
  },
  "breakdown": {
    "unavailable_vehicles": ["V_ERICK_1"]
  },
  "road_block": {
    "route_delays": {
      "IIT_CIRCULAR": 8
    }
  }
}
```

Scenario names and vehicle or route identifiers must match the data and configuration supported by the application.

---

## 📈 Baseline vs Optimized Comparison

A central feature of TransitIQ is comparing a baseline plan with a proposed plan.

| Metric | What It Measures |
|---|---|
| Passenger waiting time | How long passengers wait for service |
| Unmet demand | Passenger demand that available service cannot accommodate |
| Overcrowding | Events where passenger loads exceed or approach vehicle capacity |
| ETA error | Difference between estimated and reference arrival times |
| Fleet utilization | How effectively available vehicles are used |
| Plan feasibility | Whether the proposed plan satisfies the configured constraints |

The goal is to reduce waiting and unmet demand while respecting vehicle capacities, service requirements, and operational constraints.

**Important:** Any numerical improvement shown by the application should be interpreted in the context of the selected dataset and simulation scenario. Do not treat illustrative example figures as independently verified real-world results.

---

## 📌 Assumptions and Limitations

- Transport routes, schedules, vehicle capacities, and passenger demand must be supplied by the configured dataset.
- Simulated GPS traces are not the same as live GPS tracking.
- Travel-time variability and congestion depend on configured model parameters.
- Demand forecasts depend on the available historical data or simulation assumptions.
- The optimizer can only enforce constraints that are represented in its model.
- Improvements in a simulation do not guarantee identical improvements in real operations.
- The project is intended as a planning and decision-support prototype, not a replacement for a live operational dispatch system.

---

## 🧩 Challenges Faced

During development, the team worked through several practical challenges:

- **Simulation integration:** Making simulated transport activity behave consistently with the available campus routes, stops, schedules, and demand data.
- **ETA and rule-engine logic:** Handling delays, capacity limits, missed connections, and different operating scenarios.
- **Greedy optimization:** Finding useful schedule and vehicle-allocation changes while respecting hard constraints and balancing trade-offs.
- **Git collaboration:** Resolving merge conflicts and integrating contributions from different branches without losing working functionality.
- **Frontend and backend integration:** Connecting the user interface to the API and ensuring requests were routed to the correct deployed service.
- **Deployment and testing:** Configuring separate hosting environments and troubleshooting issues that appeared after deployment.

These challenges highlighted the importance of not only implementing algorithms, but also validating assumptions, integrating components, and testing the complete application.

---

## 👥 Team

**TransitIQ — built for PS 02 · RoutePulse**

| Area | Contribution |
|---|---|
| Backend and Simulation | Transport simulation and planning pipeline |
| Data and Infrastructure | Transport data modelling and data preparation |
| Frontend and Deployment | Web dashboard, API integration, and deployment |
| Optimization and Evaluation | Constraint checks, candidate plan evaluation, and before/after comparison |

---

## 🔗 Project Links

- **Live Application:** [https://transit-iq-eta.vercel.app/](https://transit-iq-eta.vercel.app/)
- **GitHub Repository:** [https://github.com/ironlogic-source/TransitIQ](https://github.com/ironlogic-source/TransitIQ)
- **Backend Service:** [https://transitiq-a3tm.onrender.com/](https://transitiq-a3tm.onrender.com/)

---

<div align="center">

### TransitIQ

**Smarter Routes. Smoother Rides.**

Made with ☕ for **PS 02 — RoutePulse**

</div>