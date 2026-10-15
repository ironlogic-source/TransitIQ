import { useEffect, useState, useCallback } from "react";
import {
  Activity, Bus, Users, Clock, MapPin, RefreshCw,
  Plus, Play, CheckCircle, AlertTriangle, Gauge, ToggleLeft, ToggleRight
} from "lucide-react";
import { MapContainer, TileLayer, Marker, Popup, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "./App.css";

// Fix for Leaflet default marker icon in React
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png",
  iconUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png",
  shadowUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png",
});

const API = "http://127.0.0.1:5000";

// NEW COMPONENT: Auto-Zooms the map based on bus locations
function AutoZoomMap({ gpsData }) {
  const map = useMap();
  useEffect(() => {
    if (gpsData && gpsData.length > 0) {
      const bounds = L.latLngBounds(gpsData.map(b => [b.latitude, b.longitude]));
      map.fitBounds(bounds, { padding: [50, 50], maxZoom: 15 });
    }
  }, [gpsData, map]);
  return null;
}

export default function App() {
  const [routes, setRoutes] = useState([]);
  const [buses, setBuses] = useState([]);
  const [live, setLive] = useState({
    gps: [],
    traffic: [],
    passenger_checkins: [],
    data_sources: {}
  });
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [isAutoUpdate, setIsAutoUpdate] = useState(false);

  const [routeForm, setRouteForm] = useState({ id: "", passengers: 20, capacity: 40, delay: 0 });
  const [busForm, setBusForm] = useState({ id: "", capacity: 40, available: 1 });
  const [checkin, setCheckin] = useState({ route_id: "R1", passenger_count: 1 });

  const request = async (path, options = {}) => {
    const response = await fetch(`${API}${path}`, {
      ...options,
      headers: { "Content-Type": "application/json", ...options.headers }
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || data.message || "Request failed");
    return data;
  };

  const loadAll = useCallback(async (isSilent = false) => {
    if (!isSilent) setLoading(true);
    try {
      const [dashboard, liveData] = await Promise.all([
        request("/api/dashboard"),
        request("/api/live")
      ]);

      setRoutes(Array.isArray(dashboard.routes) ? dashboard.routes : []);
      setBuses(Array.isArray(dashboard.buses) ? dashboard.buses : []);
      setLive({
        gps: Array.isArray(liveData.gps) ? liveData.gps : [],
        traffic: Array.isArray(liveData.traffic) ? liveData.traffic : [],
        passenger_checkins: Array.isArray(liveData.passenger_checkins) ? liveData.passenger_checkins : [],
        data_sources: liveData.data_sources || {}
      });
      if (!isSilent) setMessage("");
    } catch (error) {
      if (!isSilent) setMessage(`Could not load data: ${error.message}`);
    } finally {
      if (!isSilent) setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  // Auto-Update Logic (Polling every 3 seconds)
  useEffect(() => {
    let interval;
    if (isAutoUpdate) {
      interval = setInterval(() => {
        loadAll(true);
      }, 3000); 
    }
    return () => clearInterval(interval);
  }, [isAutoUpdate, loadAll]);

  const saveRoute = async (event) => {
    event.preventDefault();
    try {
      await request("/api/routes", {
        method: "POST",
        body: JSON.stringify({
          ...routeForm,
          id: routeForm.id.trim(),
          passengers: Number(routeForm.passengers),
          capacity: Number(routeForm.capacity),
          delay: Number(routeForm.delay)
        })
      });
      setRouteForm({ id: "", passengers: 20, capacity: 40, delay: 0 });
      setMessage("Route saved successfully.");
      await loadAll();
    } catch (error) {
      setMessage(`Route error: ${error.message}`);
    }
  };

  const saveBus = async (event) => {
    event.preventDefault();
    try {
      await request("/api/buses", {
        method: "POST",
        body: JSON.stringify({
          ...busForm,
          id: busForm.id.trim(),
          capacity: Number(busForm.capacity),
          available: Number(busForm.available)
        })
      });
      setBusForm({ id: "", capacity: 40, available: 1 });
      setMessage("Bus saved successfully.");
      await loadAll();
    } catch (error) {
      setMessage(`Bus error: ${error.message}`);
    }
  };

  const saveCheckin = async (event) => {
    event.preventDefault();
    try {
      await request("/api/checkin", {
        method: "POST",
        body: JSON.stringify({
          route_id: checkin.route_id,
          passenger_count: Number(checkin.passenger_count)
        })
      });
      setMessage("Passenger check-in saved.");
      await loadAll();
    } catch (error) {
      setMessage(`Check-in error: ${error.message}`);
    }
  };

  const runSimulation = async () => {
    try {
      await request("/api/simulate/live", { method: "POST" });
      setMessage("Simulation triggered.");
      await loadAll();
    } catch (error) {
      setMessage(`Simulation error: ${error.message}`);
    }
  };

  const badge = (value) => {
    const level = String(value || "Normal").toLowerCase();
    const color = level === "heavy" || level === "high"
      ? ["#fee2e2", "#b91c1c"] : level === "moderate" || level === "medium"
      ? ["#fef3c7", "#92400e"] : ["#dcfce7", "#166534"];
    return {
      background: color[0], color: color[1], borderRadius: 20, padding: "5px 10px", fontSize: 12, fontWeight: 700, display: "inline-block"
    };
  };

  const mapCenter = live.gps.length > 0 && live.gps[0].latitude 
  ? [live.gps[0].latitude, live.gps[0].longitude] 
  : [28.5440, 77.1920]; 

  const totalPassengers = routes.reduce((sum, route) => sum + Number(route.passengers || 0), 0);
  const totalCapacity = routes.reduce((sum, route) => sum + Number(route.capacity || 0), 0);
  const heavyTraffic = live.traffic.filter(item => String(item.level || "").toLowerCase() === "heavy").length;

  const cardStyle = { background: "#fff", border: "1px solid #e5eaf0", borderRadius: 16, padding: 20, boxShadow: "0 4px 16px rgba(20,40,70,.04)" };
  const fieldStyle = { width: "100%", boxSizing: "border-box", padding: "10px 12px", border: "1px solid #d8e0e9", borderRadius: 9, marginTop: 6, marginBottom: 12, fontSize: 14 };
  const buttonStyle = { display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 7, border: 0, borderRadius: 9, padding: "10px 14px", background: "#2563eb", color: "#fff", fontWeight: 600, cursor: "pointer" };
  const headingStyle = { fontSize: 18, fontWeight: 700, margin: "0 0 16px", color: "#172033" };

  return (
    <div style={{ minHeight: "100vh", background: "#f4f7fb", color: "#172033", fontFamily: "Inter, Arial, sans-serif" }}>
      <header style={{ background: "#fff", borderBottom: "1px solid #e5eaf0", padding: "18px 4%", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 14 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ background: "#2563eb", color: "#fff", borderRadius: 12, padding: 11 }}><Bus size={25} /></div>
          <div>
            <h1 style={{ margin: 0, fontSize: 24 }}>RoutePulse</h1>
            <p style={{ margin: "4px 0 0", color: "#64748b", fontSize: 13 }}>Smart Campus Transport Management</p>
          </div>
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <button style={{ padding: "10px 14px", borderRadius: 9, border: "1px solid #d8e0e9", background: isAutoUpdate ? "#dcfce7" : "#fff", cursor: "pointer", display: "flex", alignItems: "center", gap: 7 }} onClick={() => setIsAutoUpdate(!isAutoUpdate)}>
            {isAutoUpdate ? <ToggleRight color="#166534" /> : <ToggleLeft color="#64748b" />}
            {isAutoUpdate ? "Auto-Sync On" : "Auto-Sync Off"}
          </button>
          <button style={buttonStyle} onClick={() => loadAll(false)} disabled={loading}>
            <RefreshCw size={16} /> {loading ? "Refreshing..." : "Refresh"}
          </button>
        </div>
      </header>

      <main style={{ maxWidth: 1400, margin: "auto", padding: "28px 4%" }}>
        {message && (
          <div style={{ ...cardStyle, marginBottom: 20, padding: 14, color: message.toLowerCase().includes("error") ? "#b91c1c" : "#166534" }}>
            {message}
          </div>
        )}

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(190px,1fr))", gap: 16, marginBottom: 24 }}>
          {[
            { label: "Total Routes", value: routes.length, icon: MapPin },
            { label: "Total Buses", value: buses.length, icon: Bus },
            { label: "Passengers", value: totalPassengers, icon: Users },
            { label: "Heavy Traffic", value: heavyTraffic, icon: AlertTriangle }
          ].map((stat) => {
            const Icon = stat.icon;
            return (
              <div key={stat.label} style={cardStyle}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span style={{ color: "#64748b", fontSize: 14 }}>{stat.label}</span>
                  <Icon color="#2563eb" size={21} />
                </div>
                <div style={{ fontSize: 30, fontWeight: 750, marginTop: 14 }}>{stat.value}</div>
              </div>
            );
          })}
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(300px,1fr))", gap: 20, marginBottom: 24 }}>
          <section style={cardStyle}>
            <h3 style={headingStyle}><Plus size={18} /> Add Route</h3>
            <form onSubmit={saveRoute}>
              <label>Route ID</label><input style={fieldStyle} required value={routeForm.id} onChange={(e) => setRouteForm({ ...routeForm, id: e.target.value })} />
              <label>Passengers</label><input style={fieldStyle} type="number" required value={routeForm.passengers} onChange={(e) => setRouteForm({ ...routeForm, passengers: e.target.value })} />
              <label>Capacity</label><input style={fieldStyle} type="number" required value={routeForm.capacity} onChange={(e) => setRouteForm({ ...routeForm, capacity: e.target.value })} />
              <label>Delay (min)</label><input style={fieldStyle} type="number" required value={routeForm.delay} onChange={(e) => setRouteForm({ ...routeForm, delay: e.target.value })} />
              <button style={buttonStyle} type="submit"><Plus size={16} /> Save</button>
            </form>
          </section>

          <section style={cardStyle}>
            <h3 style={headingStyle}><Bus size={18} /> Add Bus</h3>
            <form onSubmit={saveBus}>
              <label>Bus ID</label><input style={fieldStyle} required value={busForm.id} onChange={(e) => setBusForm({ ...busForm, id: e.target.value })} />
              <label>Capacity</label><input style={fieldStyle} type="number" required value={busForm.capacity} onChange={(e) => setBusForm({ ...busForm, capacity: e.target.value })} />
              <label>Availability</label>
              <select style={fieldStyle} value={busForm.available} onChange={(e) => setBusForm({ ...busForm, available: e.target.value })}>
                <option value={1}>Available</option><option value={0}>Unavailable</option>
              </select>
              <button style={buttonStyle} type="submit"><Plus size={16} /> Save</button>
            </form>
          </section>

          <section style={cardStyle}>
            <h3 style={headingStyle}><Users size={18} /> Check-in</h3>
            <form onSubmit={saveCheckin}>
              <label>Route</label>
              <select style={fieldStyle} required value={checkin.route_id} onChange={(e) => setCheckin({ ...checkin, route_id: e.target.value })}>
                {routes.length === 0 && <option value="R1">R1</option>}
                {routes.map((route) => <option key={route.id} value={route.id}>{route.id}</option>)}
              </select>
              <label>Passengers</label><input style={fieldStyle} type="number" required value={checkin.passenger_count} onChange={(e) => setCheckin({ ...checkin, passenger_count: e.target.value })} />
              <button style={buttonStyle} type="submit"><CheckCircle size={16} /> Check-in</button>
            </form>
          </section>
        </div>

        <section style={{ ...cardStyle, marginBottom: 24 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", marginBottom: 20 }}>
            <div>
              <h3 style={{ fontSize: 18, margin: "0 0 6px" }}><Activity size={19} /> Live Transport Monitor</h3>
              <p style={{ margin: 0, color: "#64748b", fontSize: 13 }}>GPS & Map are live. Auto-sync is {isAutoUpdate ? "Active" : "Paused"}.</p>
            </div>
            <button style={buttonStyle} onClick={runSimulation}><Play size={16} /> Run Simulation</button>
          </div>

          <div style={{ height: 350, borderRadius: 12, overflow: "hidden", border: "1px solid #e5eaf0", marginBottom: 24, zIndex: 0 }}>
            <MapContainer center={mapCenter} zoom={13} style={{ height: "100%", width: "100%", zIndex: 1 }}>
              <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
              <AutoZoomMap gpsData={live.gps} />
              {live.gps.map((bus) => (
                <Marker key={bus.bus_id} position={[bus.latitude, bus.longitude]}>
                  <Popup>
                    <strong>Bus {bus.bus_id}</strong><br/>Route: {bus.route_id}<br/>Speed: {bus.speed_kmh} km/h
                  </Popup>
                </Marker>
              ))}
            </MapContainer>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(260px,1fr))", gap: 18 }}>
            <div>
              <h4>Bus GPS Locations</h4>
              {live.gps.map((bus, index) => (
                <div key={index} style={{ background: "#f8fafc", padding: 13, borderRadius: 10, marginBottom: 10 }}>
                  <strong><MapPin size={15} /> {bus.bus_id}</strong>
                  <p style={{ margin: "5px 0", fontSize: 13 }}>Route: {bus.route_id}</p>
                  <p style={{ margin: "5px 0", fontSize: 13, color: bus.speed_kmh === 0 ? "#b91c1c" : "#172033" }}><Gauge size={14} /> Speed: {bus.speed_kmh} km/h</p>
                </div>
              ))}
            </div>
            <div>
              <h4>Traffic Conditions</h4>
              {live.traffic.map((item, index) => (
                <div key={index} style={{ background: "#f8fafc", padding: 13, borderRadius: 10, marginBottom: 10 }}>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <strong>{item.route_id}</strong><span style={badge(item.level)}>{item.level}</span>
                  </div>
                  <div style={{ marginTop: 10, background: "#e5eaf0", height: 6, borderRadius: 3, overflow: "hidden" }}>
                     <div style={{ background: item.level === "Heavy" ? "#b91c1c" : item.level === "Moderate" ? "#f59e0b" : "#10b981", width: `${Math.min(item.delay_min * 10, 100)}%`, height: "100%" }}></div>
                  </div>
                  <p style={{ marginBottom: 0, fontSize: 12, marginTop: 4, color: "#64748b" }}>Delay: {item.delay_min ?? 0} mins</p>
                </div>
              ))}
            </div>
            <div>
              <h4>Recent Passenger Check-ins</h4>
              {live.passenger_checkins.map((item, index) => (
                <div key={index} style={{ background: "#f8fafc", padding: 13, borderRadius: 10, marginBottom: 10 }}>
                  <strong>{item.route_id}</strong>
                  <p style={{ margin: "7px 0", fontSize: 13, fontWeight: "bold" }}>Passengers: {item.passenger_count != null ? item.passenger_count : "0"}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section style={cardStyle}>
          <h3 style={headingStyle}><MapPin size={18} /> Route Overview</h3>
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: 14 }}>
              <thead>
                <tr style={{ background: "#f8fafc" }}>
                  {["Route", "Passengers", "Capacity", "Occupancy", "Delay"].map(label => <th key={label} style={{ padding: 12, borderBottom: "1px solid #e5eaf0" }}>{label}</th>)}
                </tr>
              </thead>
              <tbody>
                {routes.map((route) => {
                  const occupancy = route.capacity ? Math.round((route.passengers / route.capacity) * 100) : 0;
                  return (
                    <tr key={route.id}>
                      <td style={{ padding: 12, borderBottom: "1px solid #edf0f5" }}><strong>{route.id}</strong></td>
                      <td style={{ padding: 12, borderBottom: "1px solid #edf0f5" }}>{route.passengers ?? 0}</td>
                      <td style={{ padding: 12, borderBottom: "1px solid #edf0f5" }}>{route.capacity ?? 0}</td>
                      <td style={{ padding: 12, borderBottom: "1px solid #edf0f5" }}><span style={badge(occupancy >= 90 ? "Heavy" : occupancy >= 60 ? "Moderate" : "Normal")}>{occupancy}%</span></td>
                      <td style={{ padding: 12, borderBottom: "1px solid #edf0f5" }}><Clock size={14} /> {route.delay ?? 0} min</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      </main>
    </div>
  );
}