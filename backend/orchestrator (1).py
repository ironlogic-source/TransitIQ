
from __future__ import annotations

import argparse
import json
import logging
import math
import time
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

from backend.constraints import PlanContext, cancel_unavailable_trips, fmt_time, validate_plan
from backend.demand_engine import build_demand_model, forecast_trip_loads, forecast_unserved, rank_routes_by_excess
from backend.eta_engine import ETAModel, evaluate_eta, predict_all_etas
from backend.evaluation import DEFAULT_WEIGHTS, compare_metrics, compute_metrics
from backend.optimizer import optimize_plan
from backend.risk_engine import detect_risks, summarize_alerts

log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = REPO_ROOT / "data"

DEFAULT_SEED = 42
DEFAULT_HISTORY_DAYS = 10
DEFAULT_MAX_STEPS = 3

SCENARIO_KEYS = {"unavailable_vehicles", "demand_multiplier", "route_delays"}
WEIGHT_KEYS = set(DEFAULT_WEIGHTS)

CSV_FILES = {"vehicles": "vehicles.csv", "routes": "routes.csv", "stops": "stops.csv",
             "schedules": "schedules.csv", "demand": "passenger_demand.csv"}

SCHEDULE_COLS = ["trip_id", "vehicle_id", "route_id", "departure_time"]
ARRIVAL_COLS = ["trip_id", "vehicle_id", "route_id", "stop_id", "seq", "scheduled", "actual"]
LOAD_COLS = ["trip_id", "vehicle_id", "route_id", "stop_id", "seq", "sched_arrival", "window_start",
             "expected_boarding", "available_seats", "excess_demand", "onboard_after", "capacity", "load_factor"]
ETA_COLS = ["trip_id", "vehicle_id", "route_id", "stop_id", "seq", "scheduled",
            "eta", "eta_lo", "eta_hi", "predicted_delay"]


class OrchestratorError(Exception):
    """Base class for all orchestrator problems."""


class DataValidationError(OrchestratorError):
    """The input tables are missing, malformed or inconsistent."""


class ScenarioError(OrchestratorError):
    """The scenario / current_time / weights passed in are invalid."""



@dataclass
class DataBundle:
    vehicles: pd.DataFrame
    routes: pd.DataFrame
    stops: pd.DataFrame
    schedules: pd.DataFrame
    demand: pd.DataFrame
    params: dict = field(default_factory=dict)
    scenarios: dict = field(default_factory=dict)
    source: str = "unknown"
    warnings: list = field(default_factory=list)


def _require(df: pd.DataFrame, cols: list[str], table: str) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise DataValidationError(f"{table}: missing column(s) {missing}; found {list(df.columns)}")


def _as_ids(df: pd.DataFrame, cols: list[str], table: str) -> None:
    for c in cols:
        if df[c].isna().any():
            raise DataValidationError(f"{table}.{c}: contains empty values")
        df[c] = df[c].astype(str).str.strip()


def _as_numbers(df: pd.DataFrame, cols: list[str], table: str, minimum: float | None = None,
                strictly_positive: bool = False) -> None:
    for c in cols:
        s = pd.to_numeric(df[c], errors="coerce")
        if s.isna().any() or not np.isfinite(s.to_numpy(dtype=float)).all():
            raise DataValidationError(f"{table}.{c}: must be numeric with no empty/invalid values")
        if strictly_positive and (s <= 0).any():
            raise DataValidationError(f"{table}.{c}: must be > 0")
        if minimum is not None and (s < minimum).any():
            raise DataValidationError(f"{table}.{c}: must be >= {minimum}")
        df[c] = s


def _unique(df: pd.DataFrame, col: str, table: str) -> None:
    dup = df[col][df[col].duplicated()].unique().tolist()
    if dup:
        raise DataValidationError(f"{table}.{col}: duplicate value(s) {dup[:5]}")


def clean_data(vehicles: pd.DataFrame, routes: pd.DataFrame, stops: pd.DataFrame,
               schedules: pd.DataFrame, demand: pd.DataFrame) -> tuple[pd.DataFrame, ...]:
    """Validate + normalise the five tables (ids -> stripped str, numbers -> numeric). Returns NEW frames."""
    v, r, s, sc, d = (x.copy() for x in (vehicles, routes, stops, schedules, demand))
    for df in (v, r, s, sc, d):
        df.columns = [str(c).strip() for c in df.columns]

    # stops
    _require(s, ["stop_id", "x", "y"], "stops")
    _as_ids(s, ["stop_id"], "stops")
    _as_numbers(s, ["x", "y"], "stops")
    _unique(s, "stop_id", "stops")
    if "name" not in s.columns:
        s["name"] = s.stop_id
    stop_ids = set(s.stop_id)

    # routes
    _require(r, ["route_id", "seq", "stop_id", "seg_time_min"], "routes")
    _as_ids(r, ["route_id", "stop_id"], "routes")
    _as_numbers(r, ["seq", "seg_time_min"], "routes", minimum=0)
    r["seq"] = r["seq"].astype(int)
    if r.empty:
        raise DataValidationError("routes: table is empty")
    if r.duplicated(["route_id", "seq"]).any():
        raise DataValidationError("routes: duplicate (route_id, seq) rows")
    for rid, g in r.groupby("route_id"):
        if sorted(g.seq.tolist()) != list(range(len(g))):
            raise DataValidationError(f"routes: route {rid} must have seq = 0..{len(g) - 1} without gaps")
    unknown = sorted(set(r.stop_id) - stop_ids)
    if unknown:
        raise DataValidationError(f"routes: unknown stop_id(s) {unknown[:5]} (not in stops.csv)")
    r = r.sort_values(["route_id", "seq"]).reset_index(drop=True)
    route_ids = set(r.route_id)

    # vehicles
    _require(v, ["vehicle_id", "capacity"], "vehicles")
    _as_ids(v, ["vehicle_id"], "vehicles")
    _as_numbers(v, ["capacity"], "vehicles", strictly_positive=True)
    _unique(v, "vehicle_id", "vehicles")
    if "available" not in v.columns:
        v["available"] = 1
    _as_numbers(v, ["available"], "vehicles", minimum=0)
    v["available"] = (v["available"] > 0).astype(int)
    vehicle_ids = set(v.vehicle_id)

    # schedules
    _require(sc, SCHEDULE_COLS, "schedules")
    _as_ids(sc, ["trip_id", "vehicle_id", "route_id"], "schedules")
    _as_numbers(sc, ["departure_time"], "schedules", minimum=0)
    _unique(sc, "trip_id", "schedules")
    bad_v = sorted(set(sc.vehicle_id) - vehicle_ids)
    bad_r = sorted(set(sc.route_id) - route_ids)
    if bad_v:
        raise DataValidationError(f"schedules: unknown vehicle_id(s) {bad_v[:5]} (not in vehicles.csv)")
    if bad_r:
        raise DataValidationError(f"schedules: unknown route_id(s) {bad_r[:5]} (not in routes.csv)")
    sc = sc.reset_index(drop=True)

    # demand
    _require(d, ["route_id", "stop_id", "window_start", "passenger_count"], "passenger_demand")
    _as_ids(d, ["route_id", "stop_id"], "passenger_demand")
    _as_numbers(d, ["window_start", "passenger_count"], "passenger_demand", minimum=0)
    bad_r = sorted(set(d.route_id) - route_ids)
    bad_s = sorted(set(d.stop_id) - stop_ids)
    if bad_r:
        raise DataValidationError(f"passenger_demand: unknown route_id(s) {bad_r[:5]}")
    if bad_s:
        raise DataValidationError(f"passenger_demand: unknown stop_id(s) {bad_s[:5]}")
    d = d.reset_index(drop=True)
    return v.reset_index(drop=True), r, s.reset_index(drop=True), sc, d


def _read_json(path: Path, what: str):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise DataValidationError(f"{what} ({path.name}) could not be read: {exc}") from exc


def _parse_scenarios_file(raw: Any) -> dict[str, dict]:
    
    if isinstance(raw, dict) and raw and set(raw) <= SCENARIO_KEYS | {"name", "description"}:
        return {str(raw.get("name", "scenario")): dict(raw)}
    if isinstance(raw, dict):
        out = {}
        for k, v in raw.items():
            if not isinstance(v, dict):
                raise DataValidationError(f"scenarios.json: entry '{k}' must be an object")
            out[str(k)] = dict(v)
        return out
    if isinstance(raw, list):
        out = {}
        for i, v in enumerate(raw):
            if not isinstance(v, dict):
                raise DataValidationError(f"scenarios.json: item {i} must be an object")
            out[str(v.get("name", f"scenario_{i + 1}"))] = dict(v)
        return out
    raise DataValidationError("scenarios.json: expected an object or a list")


def load_data(data_dir: str | Path | None = None, allow_toy_fallback: bool = True) -> DataBundle:

    folder = Path(data_dir) if data_dir is not None else DEFAULT_DATA_DIR
    present = {k: (folder / f).is_file() for k, f in CSV_FILES.items()}
    warnings: list[str] = []

    if all(present.values()):
        try:
            frames = {k: pd.read_csv(folder / f, skipinitialspace=True) for k, f in CSV_FILES.items()}
        except (OSError, ValueError, pd.errors.ParserError) as exc:
            raise DataValidationError(f"could not read CSV files in {folder}: {exc}") from exc
        params = _read_json(folder / "params.json", "params") if (folder / "params.json").is_file() else {}
        if not isinstance(params, dict):
            raise DataValidationError("params.json must be an object")
        scenarios = (_parse_scenarios_file(_read_json(folder / "scenarios.json", "scenarios"))
                     if (folder / "scenarios.json").is_file() else {})
        source = str(folder)
    elif not any(present.values()):
        if not allow_toy_fallback:
            raise DataValidationError(f"no data files found in {folder}")
        try:
            from tests import toy_data as T
        except ImportError as exc:                                   # pragma: no cover
            raise DataValidationError(f"no data in {folder} and toy data is unavailable: {exc}") from exc
        frames = {"vehicles": T.VEHICLES, "routes": T.ROUTES, "stops": T.STOPS,
                  "schedules": T.SCHEDULES, "demand": T.DEMAND}
        params, scenarios = dict(T.PARAMS), {"normal": {}, "disruption": dict(T.DISRUPTION)}
        source = "toy_data"
        warnings.append(f"No data found in {folder}: using built-in TOY data (tests/toy_data.py). "
                        "Do not report these numbers as results.")
    else:
        missing = [CSV_FILES[k] for k, ok in present.items() if not ok]
        raise DataValidationError(f"incomplete dataset in {folder}: missing {missing}")

    v, r, s, sc, d = clean_data(frames["vehicles"], frames["routes"], frames["stops"],
                                frames["schedules"], frames["demand"])
    return DataBundle(v, r, s, sc, d, params=params, scenarios=scenarios, source=source, warnings=warnings)


def _import_simulator() -> tuple[Callable, str]:
    """Real simulator if the sim teammate has delivered it, otherwise the mock (same contract)."""
    try:
        from backend.simulation import run_simulation
        return run_simulation, "backend.simulation"
    except ModuleNotFoundError as exc:
        if exc.name != "backend.simulation":                        
            raise
    try:
        from tests.mock_sim import run_simulation
    except ImportError as exc:                                     
        raise OrchestratorError("No simulator available: backend/simulation.py is missing and "
                                "tests/mock_sim.py could not be imported") from exc
    return run_simulation, "tests.mock_sim (FALLBACK - backend/simulation.py not found)"



def _finite_float(value: Any, what: str, error=ScenarioError) -> float:
    if isinstance(value, bool):
        raise error(f"{what}: must be a number, got {value!r}")
    try:
        f = float(value)
    except (TypeError, ValueError):
        raise error(f"{what}: must be a number, got {value!r}") from None
    if not math.isfinite(f):
        raise error(f"{what}: must be finite, got {value!r}")
    return f


def _plan_df(records) -> pd.DataFrame:
   
    if isinstance(records, pd.DataFrame):
        df = records.copy()
    else:
        df = pd.DataFrame(list(records), columns=SCHEDULE_COLS)
    return df[SCHEDULE_COLS].reset_index(drop=True)


def _with_columns(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:

    if df is None:
        return pd.DataFrame(columns=cols)
    if len(df) == 0 and list(df.columns) != cols:
        return pd.DataFrame(columns=cols)
    return df


# ============================================================================================ orchestrator
class Orchestrator:


    def __init__(self, data_dir: str | Path | None = None, data: DataBundle | None = None,
                 simulator: Callable | None = None, seed: int = DEFAULT_SEED,
                 n_history_days: int = DEFAULT_HISTORY_DAYS, allow_toy_fallback: bool = True):
        if not isinstance(n_history_days, int) or n_history_days < 2:
            raise OrchestratorError("n_history_days must be an integer >= 2 (ETA needs train and test trips)")
        self.data = data if data is not None else load_data(data_dir, allow_toy_fallback)
        if simulator is not None:
            self._sim, self.simulator_name = simulator, getattr(simulator, "__name__", "custom simulator")
        else:
            self._sim, self.simulator_name = _import_simulator()
        self.seed = int(seed)
        self.n_history_days = n_history_days

        d = self.data
        self.vehicles, self.routes, self.stops, self.schedules = d.vehicles, d.routes, d.stops, d.schedules
        self.params = dict(d.params)
        # One row per (route, stop, window): several days (extra `day` column) are averaged, exactly what
        # build_demand_model does, so the simulator and the forecast always see the same demand.
        key = ["route_id", "stop_id", "window_start"]
        dem = d.demand
        if "day" in dem.columns or dem.duplicated(key).any():
            dem = dem.groupby(key, as_index=False, sort=False).passenger_count.mean()
        self.demand = dem[key + ["passenger_count"]].reset_index(drop=True)
        self._demand_model = build_demand_model(self.demand)
        self._unavailable_by_data = {str(r.vehicle_id): 0.0 for r in self.vehicles.itertuples()
                                     if not int(r.available)}
        self._eta_eval: dict | None = None
        self._eta_model: ETAModel | None = None
        self._eta_warnings: list[str] = []

    # ------------------------------------------------------------------ scenarios
    @property
    def scenarios(self) -> dict[str, dict]:
        return self.data.scenarios

    def scenario_names(self) -> list[str]:
        return list(self.data.scenarios)

    def resolve_scenario(self, scenario: dict | str | None) -> tuple[dict, str, list[str]]:
      
        warnings: list[str] = []
        name = "normal"
        if isinstance(scenario, str):
            if scenario not in self.data.scenarios:
                raise ScenarioError(f"unknown scenario '{scenario}'. Available: {self.scenario_names() or 'none'}")
            name, scenario = scenario, self.data.scenarios[scenario]
        if scenario is None:
            scenario = {}
        if not isinstance(scenario, dict):
            raise ScenarioError(f"scenario must be a dict, a scenario name or None, got {type(scenario).__name__}")
        scn = dict(scenario)
        if name == "normal" and scn:
            name = str(scn.get("name", "custom"))

        known_vehicles = set(self.vehicles.vehicle_id)
        known_stops = set(self.stops.stop_id)
        known_routes = set(self.routes.route_id)

        # unavailable vehicles
        raw = scn.get("unavailable_vehicles")
        unavailable: dict[str, float] = {}
        if raw is None:
            pass
        elif isinstance(raw, dict):
            for k, v in raw.items():
                unavailable[str(k).strip()] = _finite_float(v, f"unavailable_vehicles[{k}]")
        elif isinstance(raw, str):
            unavailable[raw.strip()] = 0.0
        elif isinstance(raw, (list, tuple, set)):
            unavailable.update({str(v).strip(): 0.0 for v in raw})
        else:
            raise ScenarioError("unavailable_vehicles must be a list of vehicle_ids or {vehicle_id: minute}")
        unknown = sorted(set(unavailable) - known_vehicles)
        if unknown:
            warnings.append(f"Scenario lists unknown vehicle(s) {unknown}; ignored.")
            unavailable = {k: v for k, v in unavailable.items() if k in known_vehicles}
        for vid in self._unavailable_by_data:                       # available=0 in vehicles.csv
            unavailable[vid] = 0.0
        if unavailable:
            scn["unavailable_vehicles"] = unavailable
        else:
            scn.pop("unavailable_vehicles", None)

        # demand multiplier
        dm = scn.get("demand_multiplier")
        if dm is not None:
            if not isinstance(dm, dict):
                dm = {"*": dm}
            mult: dict[str, float] = {}
            star = dm.get("*")
            if star is not None:
                star = _finite_float(star, "demand_multiplier['*']")
                if star < 0:
                    raise ScenarioError("demand_multiplier['*'] must be >= 0")
                mult = {s: star for s in known_stops}
            for k, v in dm.items():
                if k == "*":
                    continue
                f = _finite_float(v, f"demand_multiplier[{k}]")
                if f < 0:
                    raise ScenarioError(f"demand_multiplier[{k}] must be >= 0")
                if str(k) not in known_stops:
                    warnings.append(f"demand_multiplier refers to unknown stop '{k}'; ignored.")
                    continue
                mult[str(k)] = f
            scn["demand_multiplier"] = mult

        # route delays
        rd = scn.get("route_delays")
        if rd is not None:
            if not isinstance(rd, dict):
                raise ScenarioError("route_delays must be {route_id: minutes}")
            delays = {}
            for k, v in rd.items():
                f = _finite_float(v, f"route_delays[{k}]")
                if str(k) not in known_routes:
                    warnings.append(f"route_delays refers to unknown route '{k}'; ignored.")
                    continue
                delays[str(k)] = f
            scn["route_delays"] = delays
        return scn, name, warnings

    def _context(self, scenario: dict) -> PlanContext:
        return PlanContext(self.vehicles, self.routes, self.stops, self.schedules,
                           scenario=scenario, params=self.params)

    def _sim_fn(self, scenario: dict) -> Callable[[pd.DataFrame], dict]:
        """run_sim(schedules) -> sim dict, with data/scenario/seed frozen (what optimize_plan expects)."""
        return partial(self._sim, vehicles=self.vehicles, demand=self.demand, routes=self.routes,
                       scenario=scenario, seed=self.seed)

    def _resolve_time(self, current_time: float | None) -> float:
        if current_time is None:                                     # 10 min after the first departure
            return float(self.schedules.departure_time.min()) + 10.0 if len(self.schedules) else 0.0
        return _finite_float(current_time, "current_time")


    def _history_seeds(self) -> list[int]:
        seeds, s = [], 0
        while len(seeds) < self.n_history_days:
            if s != self.seed:                                       # never train on the live day
                seeds.append(s)
            s += 1
        return seeds

    def _train_eta(self) -> None:
        hist_scn = {"unavailable_vehicles": dict(self._unavailable_by_data)} if self._unavailable_by_data else {}
        frames = []
        for d in self._history_seeds():
            a = self._sim(self.schedules, self.vehicles, self.demand, self.routes,
                          scenario=hist_scn, seed=d)["arrivals"]
            if len(a):
                a = a.copy()
                a["trip_id"] = f"d{d}_" + a["trip_id"].astype(str)
                frames.append(a)
        eta_eval = None
        if frames:
            try:
                eta_eval = evaluate_eta(pd.concat(frames, ignore_index=True), self.routes)
            except Exception as exc:                                 # degrade, never crash the dashboard
                log.exception("ETA evaluation failed")
                self._eta_warnings.append(f"ETA evaluation failed ({type(exc).__name__}: {exc}); "
                                          "using timetable-based ETAs without learned statistics.")
        else:
            self._eta_warnings.append("No simulated history available; using timetable-based ETAs.")
        if eta_eval is not None:
            self._eta_eval, self._eta_model = eta_eval, eta_eval["model"]
        else:                                                        # untrained model == timetable + prior std
            default_seg = {(r.route_id, int(r.seq)): float(r.seg_time_min) for r in self.routes.itertuples()}
            stop_seq = {(r.route_id, r.stop_id): int(r.seq) for r in self.routes.itertuples()}
            self._eta_eval, self._eta_model = None, ETAModel({}, default_seg, stop_seq)

    @property
    def eta_model(self) -> ETAModel:
        if self._eta_model is None:
            self._train_eta()
        return self._eta_model

    @property
    def eta_eval(self) -> dict | None:
        if self._eta_model is None:
            self._train_eta()
        return self._eta_eval


    def _forecast(self, plan: pd.DataFrame, ctx: PlanContext, sim: dict, now: float) -> dict:
        etas = _with_columns(predict_all_etas(self.eta_model, sim["arrivals"], now), ETA_COLS)
        loads = _with_columns(forecast_trip_loads(plan, ctx, self._demand_model), LOAD_COLS)
        unserved = forecast_unserved(plan, ctx, self._demand_model)
        ranking = rank_routes_by_excess(loads, unserved)
        alerts = detect_risks(loads, etas if len(etas) else None)
        kpis = summarize_alerts(alerts)

        unserved_pax = round(float(unserved.passengers.sum()), 1) if len(unserved) else 0.0
        kpis["forecast_unserved_passengers"] = unserved_pax
        kpis["forecast_total_unmet"] = round(kpis["predicted_unmet_demand"] + unserved_pax, 1)
        return {"etas": etas, "loads": loads, "unserved": unserved, "route_ranking": ranking,
                "alerts": alerts, "kpis": kpis}


    def predict(self, scenario: dict | str | None = None, current_time: float | None = None) -> dict:
        """Predict stage only (no optimizer): ETAs + arrival windows, per-trip loads, alerts, KPIs, ranking."""
        t0 = time.perf_counter()
        scn, name, warns = self.resolve_scenario(scenario)
        now = self._resolve_time(current_time)
        ctx = self._context(scn)
        timings: dict[str, float] = {}

        t = time.perf_counter()
        eta_eval = self.eta_eval                                  
        timings["eta_training"] = round(time.perf_counter() - t, 3)

        t = time.perf_counter()
        plan, _ = cancel_unavailable_trips(self.schedules, ctx)
        plan = plan.reset_index(drop=True)
        live = self._sim_fn(scn)(plan)
        timings["live_simulation"] = round(time.perf_counter() - t, 3)

        base_check = validate_plan(plan, ctx)
        if not base_check["feasible"]:
            warns.append("The baseline timetable already violates hard constraints: "
                         + "; ".join(base_check["violations"][:3])
                         + (" ..." if len(base_check["violations"]) > 3 else ""))

        t = time.perf_counter()
        fc = self._forecast(plan, ctx, live, now)
        timings["forecast_and_risk"] = round(time.perf_counter() - t, 3)
        timings["total"] = round(time.perf_counter() - t0, 3)

        return {"scenario": scn, "scenario_name": name, "current_time": now, "current_time_label": fmt_time(now),
                "eta_eval": eta_eval, **fc, "result": None, "after": None,
                "warnings": list(self.data.warnings) + self._eta_warnings + warns,
                "meta": self._meta(), "timings": timings, "_ctx": ctx, "_live_sim": live}

 
    def run(self, scenario: dict | str | None = None, current_time: float | None = None, optimize: bool = True,
            weights: dict | None = None, max_steps: int = DEFAULT_MAX_STEPS, verbose: bool = False,
            **optimizer_kwargs) -> dict:
        """Full pipeline. `optimizer_kwargs` go straight to optimizer.optimize_plan (top_routes, max_candidates...)."""
        t0 = time.perf_counter()
        out = self.predict(scenario, current_time)
        if optimize:
            w = self._resolve_weights(weights)
            if not isinstance(max_steps, int) or max_steps < 1:
                raise ScenarioError("max_steps must be an integer >= 1")
            ctx, scn = out["_ctx"], out["scenario"]

            t = time.perf_counter()
            result = optimize_plan(self._sim_fn(scn), self.schedules, ctx, weights=w,
                                   hot_routes=out["route_ranking"].route_id.tolist(),
                                   max_steps=max_steps, **optimizer_kwargs)
            out["timings"]["optimization"] = round(time.perf_counter() - t, 3)
            self._attach_eta_metric(result, out["eta_eval"])
            out["result"] = result

            if not result["validation"]["feasible"]:
                out["warnings"].append("Final plan violates hard constraints: "
                                       + "; ".join(result["validation"]["violations"][:3]))

            t = time.perf_counter()
            proposed = _plan_df(result["proposed_plan"])
            out["after"] = self._forecast(proposed, ctx, result["_optimized_sim"], out["current_time"])
            out["timings"]["after_forecast"] = round(time.perf_counter() - t, 3)
        out["timings"]["total"] = round(time.perf_counter() - t0, 3)
        if verbose:
            print(format_report(out))
        return out

    def optimize(self, scenario: dict | str | None = None, **kw) -> dict:
        """Convenience: run() and return just the optimizer result."""
        return self.run(scenario, **kw)["result"]

 
    def apply_plan(self, run_output: dict, scenario: dict | str | None = None) -> dict:
        """'Apply' the proposed plan: re-simulate it and re-validate every hard constraint (incl. capacity).
        Pass the dict returned by run(); `scenario` defaults to the one used in that run."""
        result = run_output["result"] if "result" in run_output and run_output.get("result") else run_output
        if "proposed_plan" not in result:
            raise OrchestratorError("apply_plan needs the output of run() (or an optimizer result)")
        scn_in = scenario if scenario is not None else run_output.get("scenario")
        scn, _, _ = self.resolve_scenario(scn_in)
        ctx = self._context(scn)
        plan = _plan_df(result["proposed_plan"])
        sim = self._sim_fn(scn)(plan)
        return {"schedules": plan, "sim": sim, "metrics": compute_metrics(sim, plan, ctx),
                "validation": validate_plan(plan, ctx, sim)}


    @staticmethod
    def _resolve_weights(weights: dict | None) -> dict:
        if weights is None:
            return dict(DEFAULT_WEIGHTS)
        if not isinstance(weights, dict):
            raise ScenarioError("weights must be a dict")
        bad = set(weights) - WEIGHT_KEYS
        if bad:
            raise ScenarioError(f"unknown weight(s) {sorted(bad)}; allowed: {sorted(WEIGHT_KEYS)}")
        w = {**DEFAULT_WEIGHTS, **{k: _finite_float(v, f"weights[{k}]") for k, v in weights.items()}}
        if any(v < 0 for v in w.values()):
            raise ScenarioError("weights must be >= 0")
        return w

    @staticmethod
    def _attach_eta_metric(result: dict, eta_eval: dict | None) -> None:
        """ETA MAE row of the Before/After table: baseline = timetable arrival time, optimized = our ETA model
        (held-out MAE, same test trips). Rebuilds result['comparison'] so the row appears in it."""
        if not eta_eval:
            return
        result["baseline_metrics"]["eta_mae"] = float(eta_eval["mae_scheduled_baseline"])
        result["optimized_metrics"]["eta_mae"] = float(eta_eval["mae_eta"])
        result["comparison"] = compare_metrics(result["baseline_metrics"],
                                               result["optimized_metrics"]).to_dict("records")

    def _meta(self) -> dict:
        return {"data_source": self.data.source, "simulator": self.simulator_name, "seed": self.seed,
                "n_history_days": self.n_history_days, "n_vehicles": len(self.vehicles),
                "n_routes": int(self.routes.route_id.nunique()), "n_stops": len(self.stops),
                "n_trips": len(self.schedules), "scenarios_available": self.scenario_names()}



def make_json_safe(obj: Any) -> Any:
    """Recursively convert pipeline output to plain JSON types: DataFrames -> list of records, numpy -> python,
    NaN/inf -> None. Drops underscore keys (live objects) and the fitted ETA model."""
    if isinstance(obj, ETAModel):
        return None
    if isinstance(obj, dict):
        return {str(k): make_json_safe(v) for k, v in obj.items()
                if not (isinstance(k, str) and k.startswith("_")) and not isinstance(v, ETAModel)}
    if isinstance(obj, pd.DataFrame):
        return make_json_safe(obj.to_dict("records"))
    if isinstance(obj, pd.Series):
        return make_json_safe(obj.to_dict())
    if isinstance(obj, (list, tuple)):
        return [make_json_safe(v) for v in obj]
    if isinstance(obj, (set, frozenset)):
        return [make_json_safe(v) for v in sorted(obj, key=str)]
    if isinstance(obj, (bool, np.bool_)):
        return bool(obj)
    if isinstance(obj, (int, np.integer)):
        return int(obj)
    if isinstance(obj, (float, np.floating)):
        f = float(obj)
        return f if math.isfinite(f) else None
    if obj is None or isinstance(obj, str):
        return obj
    if obj is pd.NA or obj is pd.NaT:
        return None
    if isinstance(obj, Path):
        return str(obj)
    return str(obj)



def format_report(out: dict) -> str:
    """Human-readable terminal summary of a run()/predict() output."""
    lines = [f"Scenario: {out['scenario_name']} | time {out['current_time_label']} | "
             f"data: {out['meta']['data_source']} | simulator: {out['meta']['simulator']}"]
    for w in out["warnings"]:
        lines.append(f"WARNING: {w}")
    ev = out["eta_eval"]
    if ev:
        lines.append(f"ETA MAE: model {ev['mae_eta']} min vs timetable {ev['mae_scheduled_baseline']} min "
                     f"({ev['improvement_pct']}% better, window coverage {ev['window_coverage']:.0%})")
    lines.append(f"KPIs (before): {out['kpis']}")
    for a in out["alerts"][:4]:
        lines.append(f" ALERT {a['severity'].upper()} - {a['message']}")
    res = out["result"]
    if res is not None:
        lines += ["", f"STATUS: {res['status']} | {res['message']}"]
        for a in res["actions"]:
            lines += [f" * {a['description']}", f"     {a['reason']}", f"     {a['tradeoff']}"]
        if res["comparison"]:
            lines.append(pd.DataFrame(res["comparison"])[["metric", "baseline", "optimized",
                                                         "improvement_pct"]].to_string(index=False))
        lines.append(f"Final plan feasible: {res['validation']['feasible']}")
        if out["after"] is not None:
            lines.append(f"KPIs (after):  {out['after']['kpis']}")
    lines.append("Timings (s): " + ", ".join(f"{k}={v}" for k, v in out["timings"].items()))
    return "\n".join(lines)


_DEFAULT: dict[Any, Orchestrator] = {}


def get_orchestrator(data_dir: str | Path | None = None, refresh: bool = False, **kw) -> Orchestrator:
    """Shared Orchestrator per data folder (keeps the trained ETA model between dashboard reruns)."""
    key = str(Path(data_dir).resolve()) if data_dir is not None else "default"
    if refresh or key not in _DEFAULT:
        _DEFAULT[key] = Orchestrator(data_dir=data_dir, **kw)
    return _DEFAULT[key]


def run_pipeline(scenario: dict | str | None = None, current_time: float | None = None, verbose: bool = True,
                 data_dir: str | Path | None = None, **kw) -> dict:
    """Drop-in successor of pipeline_demo.run_pipeline (same output keys, plus after/warnings/meta/timings)."""
    return get_orchestrator(data_dir).run(scenario, current_time, verbose=verbose, **kw)



def _parse_scenario_arg(arg: str | None):
    if not arg:
        return None
    p = Path(arg)
    if p.is_file():
        return _read_json(p, "scenario file")
    if arg.lstrip().startswith("{"):
        try:
            return json.loads(arg)
        except ValueError as exc:
            raise ScenarioError(f"--scenario is not valid JSON: {exc}") from exc
    return arg                                                 


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="TransitIQ orchestrator: Predict -> Optimize -> Prove")
    ap.add_argument("--scenario", help="name from scenarios.json, a JSON file, or inline JSON (default: normal day)")
    ap.add_argument("--time", type=float, default=None, help="current simulated minute (default: first departure + 10)")
    ap.add_argument("--data-dir", default=None)
    ap.add_argument("--no-optimize", action="store_true", help="predict/alerts only")
    ap.add_argument("--json", metavar="FILE", help="also write the full output as JSON")
    args = ap.parse_args(argv)
    try:
        out = get_orchestrator(args.data_dir).run(_parse_scenario_arg(args.scenario), args.time,
                                                  optimize=not args.no_optimize)
    except OrchestratorError as exc:
        print(f"ERROR: {exc}")
        return 2
    print(format_report(out))
    if args.json:
        Path(args.json).write_text(json.dumps(make_json_safe(out), indent=2), encoding="utf-8")
        print(f"JSON written to {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
