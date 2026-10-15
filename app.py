import os
import sqlite3
from flask import Flask, jsonify, request
from flask_cors import CORS
from datetime import datetime, timezone
import random

app = Flask(__name__)
CORS(app)

# Naya database path set kar rahe hain (data/transitiq.db)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "data", "transitiq.db")

def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def utc_now():
    return datetime.now(timezone.utc).isoformat()

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "project": "RoutePulse (IIT Delhi)",
        "status": "API running",
        "endpoint": "/api/dashboard"
    })

@app.route("/api/dashboard", methods=["GET"])
def dashboard():
    try:
        conn = get_connection()
        
        # Naye schema se routes aur passenger demand ka data nikalna
        routes_data = conn.execute("""
            SELECT r.route_id, IFNULL(SUM(pd.passenger_count), 0) as passengers
            FROM routes r
            LEFT JOIN passenger_demand pd ON r.route_id = pd.route_id
            GROUP BY r.route_id
        """).fetchall()
        
        
        buses_data = conn.execute("SELECT vehicle_id as id, capacity, available FROM vehicles").fetchall()
        
        route_results = []
        for r in routes_data:
            route_results.append({
                "id": r["route_id"],
                "passengers": r["passengers"],
                "capacity": 50, # Frontend UI ke liye default capacity
                "delay": 0
            })

        return jsonify({
            "routes": route_results,
            "buses": [dict(b) for b in buses_data]
        })
    except Exception as e:
        app.logger.exception("Dashboard error")
        return jsonify({"error": str(e)}), 500
    finally:
        if 'conn' in locals(): conn.close()

@app.route("/api/live", methods=["GET"])
def get_live_data():
    try:
        conn = get_connection()
        
        # gps_traces (x, y) ko frontend (latitude, longitude) mein map karna
        gps = conn.execute("""
            SELECT vehicle_id as bus_id, trip_id as route_id, 
                   x as latitude, y as longitude, 20 as speed_kmh
            FROM gps_traces
        """).fetchall()

        
        checkins = conn.execute("""
            SELECT route_id, SUM(passenger_count) as passenger_count 
            FROM passenger_demand 
            GROUP BY route_id
        """).fetchall()

        return jsonify({
            "gps": [dict(g) for g in gps],
            "traffic": [{"route_id": "IIT_CIRCULAR", "level": "Normal", "delay_min": 2}],
            "passenger_checkins": [dict(c) for c in checkins],
            "data_sources": {
                "gps": "SIMULATED", 
                "traffic": "SIMULATED", 
                "passengers": "USER_CHECKIN"
            }
        })
    finally:
        if 'conn' in locals(): conn.close()

@app.route("/api/simulate/live", methods=["POST"])
def simulate_live():
    try:
        conn = get_connection()
        
        # Har simulation run par purani locations hatayein
        conn.execute("DELETE FROM gps_traces")
        
        # IIT Delhi ke stops aur vehicles ko match karke movement dikhana
        vehicles = conn.execute("SELECT vehicle_id, allowed_routes FROM vehicles").fetchall()
        stops = conn.execute("SELECT x, y FROM stops").fetchall()
        
        for v in vehicles:
            stop = random.choice(stops)
            route = v["allowed_routes"] or "IIT_CIRCULAR"
            
            # x ko latitude aur y ko longitude ki tarah DB mein save karna
            conn.execute("""
                INSERT INTO gps_traces (vehicle_id, trip_id, timestamp, x, y)
                VALUES (?, ?, ?, ?, ?)
            """, (v["vehicle_id"], route, 0, stop["x"], stop["y"]))
            
        conn.commit()
        return jsonify({"message": "IIT Delhi Simulation updated"})
    finally:
        if 'conn' in locals(): conn.close()
        

@app.route("/api/routes", methods=["POST"])
def save_route(): 
    return jsonify({"message": "Saved (Simulated for new schema)"}), 200

@app.route("/api/buses", methods=["POST"])
def save_bus(): 
    return jsonify({"message": "Saved (Simulated for new schema)"}), 200

@app.route("/api/checkin", methods=["POST"])
def checkin(): 
    return jsonify({"message": "Check-in received"}), 200

if __name__ == "__main__":
    app.run(debug=True, port=5000)
