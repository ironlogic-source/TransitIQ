"""Tiny hand-made network (6 stops, 3 routes, 4 buses) for tests and for developing before the real sim exists."""
import pandas as pd

STOPS = pd.DataFrame([
    ("S1", "Hostel", 0, 0), ("S2", "Library", 1000, 0), ("S3", "Academic Block", 2000, 0),
    ("S4", "Sports", 3000, 0), ("S5", "Canteen", 1000, 1000), ("S6", "Gate", 2000, 1000)],
    columns=["stop_id", "name", "x", "y"])

_R = {"A": [("S1", 0), ("S2", 5), ("S3", 5), ("S4", 5)],
      "B": [("S5", 0), ("S2", 5), ("S6", 5)],
      "C": [("S3", 0), ("S4", 5), ("S6", 6)]}
ROUTES = pd.DataFrame([(r, i, s, t) for r, lst in _R.items() for i, (s, t) in enumerate(lst)],
                      columns=["route_id", "seq", "stop_id", "seg_time_min"])

VEHICLES = pd.DataFrame([("B1", 40, 1, "S1"), ("B2", 40, 1, "S5"), ("B3", 30, 1, "S3"), ("B4", 50, 1, "S2")],
                        columns=["vehicle_id", "capacity", "available", "depot_stop_id"])

SCHEDULES = pd.DataFrame(
    [(f"A{i}", "B1", "A", 480 + 30 * i) for i in range(3)]
    + [(f"B{i}", "B2", "B", 480 + 30 * i) for i in range(3)]
    + [(f"C{i}", "B3", "C", 480 + 30 * i) for i in range(3)],
    columns=["trip_id", "vehicle_id", "route_id", "departure_time"])

_DEM = {"A": {"S1": 60, "S2": 30, "S3": 20}, "B": {"S5": 30, "S2": 20, "S6": 10}, "C": {"S3": 25, "S4": 20, "S6": 10}}
DEMAND = pd.DataFrame([(r, s, ws, n) for r, d in _DEM.items() for s, n in d.items() for ws in (480, 510, 540)],
                      columns=["route_id", "stop_id", "window_start", "passenger_count"])

PARAMS = {"service_start": 420, "service_end": 600}
DISRUPTION = {"unavailable_vehicles": ["B1"], "demand_multiplier": {"S1": 1.4}, "route_delays": {"B": 6}}
