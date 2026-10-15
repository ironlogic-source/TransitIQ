import sqlite3
import os
from contextlib import closing

# Script jahan save hai, uska exact rasta (path) nikalna
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_NAME = os.path.join(DATA_DIR, "transitiq.db")

def get_connection():
    # Yeh automatically check karega aur 'data' folder bana dega exact location par
    os.makedirs(DATA_DIR, exist_ok=True)
    
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def create_tables():
    with closing(get_connection()) as conn:
        with conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS stops (
                    stop_id TEXT PRIMARY KEY, 
                    name TEXT, 
                    x REAL, 
                    y REAL
                );
                
                CREATE TABLE IF NOT EXISTS routes (
                    route_id TEXT, 
                    seq INTEGER, 
                    stop_id TEXT, 
                    seg_time_min REAL,
                    PRIMARY KEY (route_id, seq)
                );
                
                CREATE TABLE IF NOT EXISTS vehicles (
                    vehicle_id TEXT PRIMARY KEY, 
                    capacity INTEGER, 
                    available INTEGER CHECK(available IN (0, 1)),
                    depot_stop_id TEXT, 
                    allowed_routes TEXT
                );
                
                CREATE TABLE IF NOT EXISTS schedules (
                    trip_id TEXT PRIMARY KEY, 
                    vehicle_id TEXT, 
                    route_id TEXT, 
                    departure_time REAL
                );
                
                CREATE TABLE IF NOT EXISTS passenger_demand (
                    route_id TEXT, 
                    stop_id TEXT, 
                    window_start INTEGER,
                    passenger_count REAL, 
                    day INTEGER
                );
                
                CREATE TABLE IF NOT EXISTS gps_traces (
                    vehicle_id TEXT, 
                    trip_id TEXT, 
                    timestamp REAL, 
                    x REAL, 
                    y REAL
                );
                
                CREATE TABLE IF NOT EXISTS simulation_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    before_data TEXT NOT NULL,
                    after_data TEXT NOT NULL
                );
            """)

def add_stop(stop_id, name, x, y):
    with closing(get_connection()) as conn:
        with conn:
            conn.execute(
                """INSERT INTO stops (stop_id, name, x, y) VALUES (?, ?, ?, ?)""",
                (stop_id, name, x, y)
            )

def add_route_stop(route_id, seq, stop_id, seg_time_min):
    with closing(get_connection()) as conn:
        with conn:
            conn.execute(
                """INSERT INTO routes (route_id, seq, stop_id, seg_time_min)
                   VALUES (?, ?, ?, ?)""",
                (route_id, seq, stop_id, seg_time_min)
            )

def add_vehicle(vehicle_id, capacity, available, depot_stop_id, allowed_routes):
    with closing(get_connection()) as conn:
        with conn:
            conn.execute(
                """INSERT INTO vehicles (vehicle_id, capacity, available, depot_stop_id, allowed_routes)
                   VALUES (?, ?, ?, ?, ?)""",
                (vehicle_id, capacity, available, depot_stop_id, allowed_routes)
            )

def show_data():
    with closing(get_connection()) as conn:
        print("\n--- STOPS ---")
        for row in conn.execute("SELECT * FROM stops"):
            print(dict(row))

        print("\n--- ROUTES ---")
        for row in conn.execute("SELECT * FROM routes"):
            print(dict(row))

        print("\n--- VEHICLES ---")
        for row in conn.execute("SELECT * FROM vehicles"):
            print(dict(row))

def seed_sample_data():
    with closing(get_connection()) as conn:
        with conn:
            count = conn.execute("SELECT COUNT(*) FROM stops").fetchone()[0]

            if count > 0:
                print("Existing data found. Sample data not added again.")
                return

            
            conn.executemany(
                """INSERT INTO stops (stop_id, name, x, y) VALUES (?, ?, ?, ?)""",
                [
                    ("S_MAIN_GATE", "IIT Main Gate", 28.544, 77.192),
                    ("S_ACAD_BLOCK", "Academic Area (Dogra Hall)", 28.545, 77.190),
                    ("S_HOSPITAL", "IIT Hospital", 28.541, 77.185),
                    ("S_HOSTEL_ZANSKAR", "Zanskar Hostel", 28.547, 77.188),
                    ("S_METRO", "IIT Metro Station", 28.543, 77.193)
                ]
            )

            
            conn.executemany(
                """INSERT INTO routes (route_id, seq, stop_id, seg_time_min) VALUES (?, ?, ?, ?)""",
                [
                    ("IIT_CIRCULAR", 0, "S_METRO", 0.0),
                    ("IIT_CIRCULAR", 1, "S_MAIN_GATE", 2.5),
                    ("IIT_CIRCULAR", 2, "S_ACAD_BLOCK", 5.0),
                    ("IIT_CIRCULAR", 3, "S_HOSTEL_ZANSKAR", 8.0),
                    ("IIT_CIRCULAR", 4, "S_HOSPITAL", 12.0)
                ]
            )

            
            conn.executemany(
                """INSERT INTO vehicles (vehicle_id, capacity, available, depot_stop_id, allowed_routes)
                   VALUES (?, ?, ?, ?, ?)""",
                [
                    ("V_ERICK_1", 4, 1, "S_MAIN_GATE", "IIT_CIRCULAR"),
                    ("V_ERICK_2", 4, 1, "S_METRO", "IIT_CIRCULAR"),
                    ("V_MINIBUS_1", 20, 1, "S_HOSTEL_ZANSKAR", "IIT_CIRCULAR")
                ]
            )

            
            conn.executemany(
                """INSERT INTO passenger_demand (route_id, stop_id, window_start, passenger_count, day)
                   VALUES (?, ?, ?, ?, ?)""",
                [
                    ("IIT_CIRCULAR", "S_METRO", 480, 15.0, 1),
                    ("IIT_CIRCULAR", "S_HOSTEL_ZANSKAR", 510, 25.0, 1)
                ]
            )

            print("IIT Delhi sample routes and vehicles added successfully!")

if __name__ == "__main__":
    create_tables()
    seed_sample_data()
    show_data()