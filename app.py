"""
app.py – iRoutePulse Flask API
=================================
REST backend for the iRoutePulse dashboard.

Endpoints
---------
GET  /                          → health-check
GET  /api/run                   → full Predict → Optimize → Prove pipeline
GET  /api/predict               → predict-only (no optimizer)
POST /api/run                   → same as GET /api/run but accepts JSON body
GET  /api/meta                  → fleet / network summary
GET  /api/scenarios             → list available scenarios
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from flask import Flask, jsonify, request
from flask_cors import CORS

from backend.orchestrator import (
    Orchestrator,
    OrchestratorError,
    ScenarioError,
    make_json_safe,
    get_orchestrator,
)

# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"


def _orc() -> Orchestrator:
    return get_orchestrator(DATA_DIR)


# ---------------------------------------------------------------------------

@app.route("/", methods=["GET"])
def health():
    meta = _orc()._meta()
    return jsonify({"project": "iRoutePulse", "status": "running", "meta": meta})


@app.route("/api/scenarios", methods=["GET"])
def scenarios():
    return jsonify({"scenarios": _orc().scenario_names()})


@app.route("/api/meta", methods=["GET"])
def meta():
    return jsonify(_orc()._meta())


def _parse_body() -> dict:
    if request.is_json and request.data:
        return request.get_json(silent=True) or {}
    return {}


@app.route("/api/predict", methods=["GET", "POST"])
def predict():
    body = _parse_body()
    scenario = request.args.get("scenario") or body.get("scenario")
    current_time = request.args.get("time", type=float) or body.get("current_time")
    try:
        out = _orc().predict(scenario, current_time)
        return jsonify(make_json_safe(out))
    except (OrchestratorError, ScenarioError) as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        log.exception("predict error")
        return jsonify({"error": str(exc)}), 500


@app.route("/api/run", methods=["GET", "POST"])
def run():
    body = _parse_body()
    scenario = request.args.get("scenario") or body.get("scenario")
    current_time = request.args.get("time", type=float) or body.get("current_time")
    optimize = request.args.get("optimize", "true").lower() != "false"
    max_steps = int(request.args.get("max_steps", body.get("max_steps", 3)))
    weights = body.get("weights")
    try:
        out = _orc().run(
            scenario=scenario,
            current_time=current_time,
            optimize=optimize,
            weights=weights,
            max_steps=max_steps,
        )
        return jsonify(make_json_safe(out))
    except (OrchestratorError, ScenarioError) as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        log.exception("run error")
        return jsonify({"error": str(exc)}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000, host="0.0.0.0")
