from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.orchestrator import (
    OrchestratorError,
    ScenarioError,
    get_orchestrator,
    make_json_safe,
)

# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent / "data"

app = FastAPI(
    title="TransitIQ — RoutePulse API",
    description=(
        "Campus transport planning system for IIT Delhi. "
        "Estimates arrival windows, forecasts demand, detects overcrowding/delays, "
        "and recommends feasible schedule optimisations under hard constraints."
    ),
    version="1.0.0",
    contact={"name": "TransitIQ Team", "url": "https://github.com/ironlogic-source/TransitIQ"},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
class PredictRequest(BaseModel):
    scenario: dict | str | None = None
    current_time: float | None = None

    model_config = {"json_schema_extra": {
        "examples": [
            {"scenario": None, "current_time": None},
            {"scenario": {"demand_multiplier": {"*": 1.5}}, "current_time": 490.0},
        ]
    }}
class RunRequest(BaseModel):
    scenario: dict | str | None = None
    current_time: float | None = None
    optimize: bool = True
    max_steps: int = 3
    weights: dict | None = None

    model_config = {"json_schema_extra": {
        "examples": [
            {"scenario": None, "optimize": True, "max_steps": 3},
            {
                "scenario": {"unavailable_vehicles": ["V_ERICK_1"], "demand_multiplier": {"*": 1.5}},
                "optimize": True,
                "max_steps": 3,
                "weights": {"unmet_demand": 2.0},
            },
        ]
    }}
def _orc():
    return get_orchestrator(DATA_DIR)


def _safe(obj: Any) -> Any:
    return make_json_safe(obj)


def _handle(exc: Exception) -> HTTPException:
    if isinstance(exc, (OrchestratorError, ScenarioError)):
        raise HTTPException(status_code=400, detail=str(exc))
    log.exception("Unexpected error")
    raise HTTPException(status_code=500, detail=str(exc))

@app.get("/", tags=["Health"], summary="Health check")
def health():
    """Returns project info and fleet/network summary."""
    return {"project": "TransitIQ — RoutePulse", "status": "running", "meta": _orc()._meta()}


@app.get("/api/meta", tags=["Info"], summary="Network metadata")
def meta():
    """Returns fleet and network statistics: vehicles, routes, stops, trips."""
    return _orc()._meta()


@app.get("/api/scenarios", tags=["Info"], summary="Available scenarios")
def scenarios():
    """Lists all named disruption scenarios loaded from data/scenarios.json."""
    return {"scenarios": _orc().scenario_names()}


# ── Predict ──────────────────────────────────────────────────────────────────

@app.get("/api/predict", tags=["Pipeline"], summary="Predict phase (GET)")
def predict_get(
    scenario: str | None = Query(None, description="Scenario name or inline JSON string"),
    time: float | None = Query(None, description="Current time in minutes since midnight (e.g. 490 = 08:10)"),
):
    try:
        out = _orc().predict(scenario, time)
        return _safe(out)
    except Exception as exc:
        _handle(exc)


@app.post("/api/predict", tags=["Pipeline"], summary="Predict phase (POST)")
def predict_post(body: PredictRequest):
    try:
        out = _orc().predict(body.scenario, body.current_time)
        return _safe(out)
    except Exception as exc:
        _handle(exc)


# ── Run (full pipeline) ───────────────────────────────────────────────────────

@app.get("/api/run", tags=["Pipeline"], summary="Full pipeline (GET)")
def run_get(
    scenario: str | None = Query(None, description="Scenario name or inline JSON string"),
    time: float | None = Query(None, description="Current time in minutes since midnight"),
    optimize: bool = Query(True, description="Run optimiser (set false for predict-only)"),
    max_steps: int = Query(3, description="Max optimisation iterations"),
):
    try:
        out = _orc().run(
            scenario=scenario,
            current_time=time,
            optimize=optimize,
            max_steps=max_steps,
        )
        return _safe(out)
    except Exception as exc:
        _handle(exc)


@app.post("/api/run", tags=["Pipeline"], summary="Full pipeline (POST)")
def run_post(body: RunRequest):
    """Same as GET /api/run but accepts a full JSON body with custom weights."""
    try:
        out = _orc().run(
            scenario=body.scenario,
            current_time=body.current_time,
            optimize=body.optimize,
            weights=body.weights,
            max_steps=body.max_steps,
        )
        return _safe(out)
    except Exception as exc:
        _handle(exc)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
