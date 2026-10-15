"""
TransitIQ - eta_engine.py
Explainable ETA: anchor on the last observed arrival, add historical mean segment times,
plus a decaying carry-over of the most recent segment's deviation (current congestion).

    ETA(target) = actual_last + sum_j [ mean_seg_j + residual_last * rho**j ]
    window      = ETA +/- z * sqrt(sum_j std_j^2)

NO LEAKAGE: only rows with actual <= current_time are ever used; stats are fit on train trips only.
Input `arrivals`: trip_id, vehicle_id, route_id, stop_id, seq, scheduled, actual.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd


class ETAModel:
    def __init__(self, stats: dict, default_seg: dict, stop_seq: dict,
                 rho: float = 0.5, z: float = 1.28, min_std: float = 0.5, prior_std: float = 2.0):
        self.stats, self.default_seg, self.stop_seq = stats, default_seg, stop_seq
        self.rho, self.z, self.min_std, self.prior_std = rho, z, min_std, prior_std

    # ------------------------------------------------------------------ fitting
    @classmethod
    def fit(cls, train_arrivals: pd.DataFrame, routes: pd.DataFrame, **kw) -> "ETAModel":
        df = train_arrivals.sort_values(["trip_id", "seq"]).copy()
        df["seg"] = df.groupby("trip_id").actual.diff()
        seg = df.dropna(subset=["seg"])
        g = seg.groupby(["route_id", "seq"]).seg.agg(["mean", "std"]).reset_index()
        stats = {(r.route_id, int(r.seq)): (float(r["mean"]), float(r["std"]) if pd.notna(r["std"]) else None)
                 for _, r in g.iterrows()}
        default_seg = {(r.route_id, int(r.seq)): float(r.seg_time_min) for r in routes.itertuples()}
        stop_seq = {(r.route_id, r.stop_id): int(r.seq) for r in routes.itertuples()}
        return cls(stats, default_seg, stop_seq, **kw)

    def _seg(self, route_id, seq):
        mean, std = self.stats.get((route_id, seq), (None, None))
        if mean is None:                          # never seen in training -> timetable value
            mean = self.default_seg.get((route_id, seq), 3.0)
        return mean, max(std if std is not None else self.prior_std, self.min_std)

    # ------------------------------------------------------------------ prediction
    def _predict_from_obs(self, obs: pd.DataFrame, route_id, target_seq, scheduled_target):
        """obs = already-filtered observed rows (actual <= now) of ONE trip."""
        if obs.empty:                              # trip not started: fall back to timetable
            if scheduled_target is None:
                raise ValueError("scheduled_target required for a trip with no observations")
            var = sum(self._seg(route_id, j)[1] ** 2 for j in range(1, target_seq + 1))
            sd = math.sqrt(var + self.prior_std ** 2)
            eta = float(scheduled_target)
            return {"eta": eta, "eta_lo": eta - self.z * sd, "eta_hi": eta + self.z * sd, "std": sd}
        obs = obs.sort_values("seq")
        last = obs.iloc[-1]
        k = int(last.seq)
        if target_seq <= k:                        # already happened
            a = float(obs[obs.seq == target_seq].actual.iloc[0]) if (obs.seq == target_seq).any() else float(last.actual)
            return {"eta": a, "eta_lo": a, "eta_hi": a, "std": 0.0}
        resid = 0.0
        if k > 0 and len(obs) >= 2 and int(obs.iloc[-2].seq) == k - 1:
            resid = float(last.actual - obs.iloc[-2].actual) - self._seg(route_id, k)[0]
        eta, var = float(last.actual), 0.0
        for n, j in enumerate(range(k + 1, target_seq + 1), start=1):
            mean, std = self._seg(route_id, j)
            eta += mean + resid * (self.rho ** n)
            var += std ** 2
        sd = math.sqrt(var)
        return {"eta": eta, "eta_lo": eta - self.z * sd, "eta_hi": eta + self.z * sd, "std": sd}

    def predict(self, observed: pd.DataFrame, trip_id, route_id, stop_id, current_time,
                scheduled_target=None) -> dict:
        """Public API: predicted arrival of `trip_id` at `stop_id` using info available at current_time."""
        target = self.stop_seq[(route_id, stop_id)]
        obs = observed[(observed.trip_id == trip_id) & (observed.actual <= current_time)]
        out = self._predict_from_obs(obs, route_id, target, scheduled_target)
        if scheduled_target is not None:
            out["scheduled"] = float(scheduled_target)
            out["predicted_delay"] = out["eta"] - float(scheduled_target)
        return out


def predict_eta(model: ETAModel, observed, trip_id, route_id, stop_id, current_time, scheduled_target=None):
    return model.predict(observed, trip_id, route_id, stop_id, current_time, scheduled_target)


def predict_all_etas(model: ETAModel, arrivals_full: pd.DataFrame, current_time: float) -> pd.DataFrame:
    """ETA for every not-yet-reached stop of every trip, as of `current_time`.
    `arrivals_full` may contain the future (simulator output) - only rows <= current_time are used
    as observations; the other rows are used just for the trip/stop list and the timetable."""
    rows = []
    for trip_id, g in arrivals_full.groupby("trip_id"):
        g = g.sort_values("seq")
        obs = g[g.actual <= current_time]
        k = int(obs.seq.max()) if len(obs) else -1
        for r in g[g.seq > k].itertuples(index=False):
            p = model._predict_from_obs(obs[["trip_id", "seq", "actual", "scheduled"]], r.route_id, int(r.seq), r.scheduled)
            rows.append({"trip_id": trip_id, "vehicle_id": r.vehicle_id, "route_id": r.route_id,
                         "stop_id": r.stop_id, "seq": int(r.seq), "scheduled": r.scheduled,
                         "eta": p["eta"], "eta_lo": p["eta_lo"], "eta_hi": p["eta_hi"],
                         "predicted_delay": p["eta"] - r.scheduled})
    return pd.DataFrame(rows, columns=["trip_id", "vehicle_id", "route_id", "stop_id", "seq",
                                       "scheduled", "eta", "eta_lo", "eta_hi", "predicted_delay"])


# ---------------------------------------------------------------------- evaluation
def split_trips(arrivals: pd.DataFrame, test_frac: float = 0.3, seed: int = 42):
    ids = np.array(sorted(arrivals.trip_id.unique()))
    rng = np.random.default_rng(seed)
    rng.shuffle(ids)
    n_test = max(1, int(len(ids) * test_frac))
    test_ids = set(ids[:n_test])
    return arrivals[~arrivals.trip_id.isin(test_ids)], arrivals[arrivals.trip_id.isin(test_ids)]


def evaluate_eta(arrivals: pd.DataFrame, routes: pd.DataFrame, test_frac: float = 0.3,
                 seed: int = 42, **model_kw) -> dict:
    """Held-out evaluation. Compares ETA model vs the 'scheduled arrival' baseline using MAE.
    Each test trip is observed up to stop k, then every later stop is predicted."""
    train, test = split_trips(arrivals, test_frac, seed)
    model = ETAModel.fit(train, routes, **model_kw)
    recs = []
    for trip_id, g in test.groupby("trip_id"):
        g = g.sort_values("seq").reset_index(drop=True)
        for k in range(len(g) - 1):
            now = g.loc[k, "actual"]
            obs = g[g.actual <= now]
            for j in range(k + 1, len(g)):
                p = model._predict_from_obs(obs, g.loc[j, "route_id"], int(g.loc[j, "seq"]), g.loc[j, "scheduled"])
                actual = g.loc[j, "actual"]
                recs.append({"trip_id": trip_id, "stops_ahead": j - k, "actual": actual,
                             "err_eta": abs(actual - p["eta"]),
                             "err_sched": abs(actual - g.loc[j, "scheduled"]),
                             "in_window": p["eta_lo"] <= actual <= p["eta_hi"]})
    d = pd.DataFrame(recs)
    mae_eta, mae_sched = float(d.err_eta.mean()), float(d.err_sched.mean())
    return {
        "mae_eta": round(mae_eta, 3), "mae_scheduled_baseline": round(mae_sched, 3),
        "improvement_pct": round(100 * (mae_sched - mae_eta) / mae_sched, 1) if mae_sched > 0 else 0.0,
        "window_coverage": round(float(d.in_window.mean()), 3),
        "n_predictions": int(len(d)), "n_test_trips": int(test.trip_id.nunique()),
        "by_horizon": d.groupby("stops_ahead")[["err_eta", "err_sched"]].mean().round(3).reset_index(),
        "model": model,
    }
