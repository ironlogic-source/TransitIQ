import React, { useState, useEffect, useRef, useMemo } from 'react'
import { MapContainer, TileLayer, CircleMarker, Polyline, Popup, Marker } from 'react-leaflet'
import L from 'leaflet'
import { STOPS, ROUTE_SEQUENCE, MAP_CENTER, MAP_ZOOM, fmtMin } from '../constants.js'

// Circuit waypoints for bidirectional loop along IIT Delhi campus route
const CIRCUIT_WAYPOINTS = [
  { stopId: 'S_METRO',          lat: 28.5430, lng: 77.1930, name: 'IIT Metro Station' },
  { stopId: 'S_MAIN_GATE',      lat: 28.5440, lng: 77.1920, name: 'IIT Main Gate' },
  { stopId: 'S_ACAD_BLOCK',     lat: 28.5450, lng: 77.1900, name: 'Academic Area (Dogra Hall)' },
  { stopId: 'S_HOSTEL_ZANSKAR', lat: 28.5470, lng: 77.1880, name: 'Zanskar Hostel' },
  { stopId: 'S_HOSPITAL',       lat: 28.5410, lng: 77.1850, name: 'IIT Hospital' },
  { stopId: 'S_HOSTEL_ZANSKAR', lat: 28.5470, lng: 77.1880, name: 'Zanskar Hostel' },
  { stopId: 'S_ACAD_BLOCK',     lat: 28.5450, lng: 77.1900, name: 'Academic Area (Dogra Hall)' },
  { stopId: 'S_MAIN_GATE',      lat: 28.5440, lng: 77.1920, name: 'IIT Main Gate' },
  { stopId: 'S_METRO',          lat: 28.5430, lng: 77.1930, name: 'IIT Metro Station' },
]

// Base fleet configuration
const FLEET_DEFAULTS = [
  {
    vehicle_id: 'V_ERICK_1',
    name: 'E-Rickshaw 1',
    type: 'E-Rickshaw',
    capacity: 4,
    baseSpeed: 19.5,
    color: '#10b981', // emerald
    initialOffset: 0.08,
  },
  {
    vehicle_id: 'V_ERICK_2',
    name: 'E-Rickshaw 2',
    type: 'E-Rickshaw',
    capacity: 4,
    baseSpeed: 21.0,
    color: '#3b82f6', // blue
    initialOffset: 0.42,
  },
  {
    vehicle_id: 'V_MINIBUS_1',
    name: 'Minibus 1',
    type: 'Minibus',
    capacity: 20,
    baseSpeed: 23.5,
    color: '#a855f7', // purple
    initialOffset: 0.76,
  },
]

// Precompute cumulative distance metrics along the circuit
function buildCircuitMetrics(waypoints) {
  const segments = []
  let totalDist = 0

  for (let i = 0; i < waypoints.length - 1; i++) {
    const from = waypoints[i]
    const to   = waypoints[i + 1]
    const dLat = to.lat - from.lat
    const dLng = (to.lng - from.lng) * Math.cos(((from.lat + to.lat) / 2) * (Math.PI / 180))
    const dist = Math.hypot(dLat, dLng)

    let bearing = Math.atan2(dLng, dLat) * (180 / Math.PI)
    if (bearing < 0) bearing += 360

    segments.push({
      from,
      to,
      dist,
      bearing,
      startCum: totalDist,
      endCum: totalDist + dist,
    })
    totalDist += dist
  }

  return { segments, totalDist }
}

const CIRCUIT_DATA = buildCircuitMetrics(CIRCUIT_WAYPOINTS)

// Given normalized progress p in [0, 1), compute current lat, lng, bearing, approaching stop
function interpolateVehiclePosition(p, circuitData) {
  const { segments, totalDist } = circuitData
  if (totalDist === 0) {
    return { lat: 28.5445, lng: 77.1890, bearing: 0, fromStop: null, toStop: null, progress: 0 }
  }

  let norm = p % 1
  if (norm < 0) norm += 1
  const targetDist = norm * totalDist

  for (let i = 0; i < segments.length; i++) {
    const seg = segments[i]
    if (targetDist <= seg.endCum || i === segments.length - 1) {
      const alpha = seg.dist > 0 ? (targetDist - seg.startCum) / seg.dist : 0
      const clamped = Math.max(0, Math.min(1, alpha))
      return {
        lat: seg.from.lat + clamped * (seg.to.lat - seg.from.lat),
        lng: seg.from.lng + clamped * (seg.to.lng - seg.from.lng),
        bearing: seg.bearing,
        fromStop: seg.from,
        toStop: seg.to,
        progress: norm,
      }
    }
  }

  const last = segments[segments.length - 1]
  return {
    lat: last.to.lat,
    lng: last.to.lng,
    bearing: last.bearing,
    fromStop: last.from,
    toStop: last.to,
    progress: 1,
  }
}

function stopSeverity(sid, alerts) {
  const sa = alerts.filter(a => a.stop_id === sid)
  if (sa.some(a => a.severity === 'high'))   return 'high'
  if (sa.some(a => a.severity === 'medium')) return 'medium'
  return 'ok'
}

const SEV_COLOR = {
  high:   { fill: '#ef4444', stroke: '#fca5a5' },
  medium: { fill: '#f59e0b', stroke: '#fcd34d' },
  ok:     { fill: '#3b82f6', stroke: '#93c5fd' },
}

// Custom Leaflet DivIcon for Moving Bus with heading rotation and speed tag
function createMovingBusIcon(vehicleId, color, speedKmh, bearingDeg, isBroken) {
  const isMini = vehicleId.includes('MINIBUS')
  const statusColor = isBroken ? '#ef4444' : color
  const statusText = isBroken ? 'MAINTENANCE' : `${speedKmh.toFixed(0)} km/h`

  return L.divIcon({
    html: `
      <div style="
        position: relative;
        display: flex;
        flex-direction: column;
        align-items: center;
        pointer-events: auto;
        transform: translate(-50%, -50%);
        cursor: pointer;
      ">
        <!-- Floating Tag: Vehicle ID + Speed -->
        <div style="
          background: rgba(13, 21, 38, 0.94);
          border: 1px solid ${statusColor};
          color: #f9fafb;
          font-family: 'Inter', system-ui, sans-serif;
          font-size: 9px;
          font-weight: 700;
          padding: 2px 7px;
          border-radius: 6px;
          white-space: nowrap;
          box-shadow: 0 4px 14px rgba(0,0,0,0.8);
          margin-bottom: 5px;
          display: flex;
          align-items: center;
          gap: 4px;
          pointer-events: none;
        ">
          <span style="
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background: ${statusColor};
            display: inline-block;
          "></span>
          <span>${vehicleId}</span>
          <span style="color: ${isBroken ? '#fca5a5' : '#93c5fd'}; font-size: 8.5px; font-weight: 600;">
            ${statusText}
          </span>
        </div>

        <!-- Bus Marker Box with pulse ring -->
        <div style="
          position: relative;
          width: 30px;
          height: 30px;
          display: flex;
          align-items: center;
          justify-content: center;
        ">
          <!-- Pulse halo -->
          <div style="
            position: absolute;
            inset: -4px;
            border-radius: 50%;
            background: ${statusColor};
            opacity: ${isBroken ? 0.15 : 0.35};
            animation: bus-pulse-ring 2s ease-out infinite;
          "></div>

          <!-- Solid bus body icon with bearing direction -->
          <div style="
            width: 26px;
            height: 26px;
            background: linear-gradient(135deg, ${statusColor}, #0b1329);
            border: 2px solid #ffffff;
            border-radius: ${isMini ? '8px' : '50% 50% 50% 0'};
            transform: ${isMini ? `rotate(${bearingDeg}deg)` : `rotate(${bearingDeg - 45}deg)`};
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 4px 12px rgba(0,0,0,0.7);
            transition: transform 0.12s linear;
          ">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              ${isMini
                ? '<rect x="3" y="3" width="18" height="18" rx="4"/><path d="M7 8h10M7 12h10M7 16h2M15 16h2"/>'
                : '<path d="M12 2L19 21L12 17L5 21L12 2Z"/>'
              }
            </svg>
          </div>
        </div>
      </div>
    `,
    className: 'leaflet-bus-icon-container',
    iconSize: [0, 0],
    iconAnchor: [0, 0],
  })
}

const popupStyle = { fontFamily: 'Inter,sans-serif', minWidth: 180 }
const pHead      = { color: '#f9fafb', fontSize: 13, fontWeight: 700, margin: '0 0 4px' }
const pSub       = { color: '#6b7280', fontSize: 11, margin: '2px 0' }

export default function MapView({
  arrivals = [],
  etas = [],
  alerts = [],
  isSimulating = false,
  status = 'ready',
  scenarioKey = 'normal',
}) {
  // Speed multiplier toggle state
  const [speedMultiplier, setSpeedMultiplier] = useState(1)
  const [isPlaying, setIsPlaying] = useState(true)

  // Track progress of each vehicle in normalized [0, 1) loop
  const [vehicleProgress, setVehicleProgress] = useState(() => ({
    V_ERICK_1: FLEET_DEFAULTS[0].initialOffset,
    V_ERICK_2: FLEET_DEFAULTS[1].initialOffset,
    V_MINIBUS_1: FLEET_DEFAULTS[2].initialOffset,
  }))

  const lastFrameTimeRef = useRef(performance.now())

  // Dynamic animation frame loop for smooth 60fps bus movement
  useEffect(() => {
    let animId

    const loop = (currentTime) => {
      const deltaMs = currentTime - lastFrameTimeRef.current
      lastFrameTimeRef.current = currentTime

      if (isPlaying && deltaMs > 0 && deltaMs < 1000) {
        // Boost simulation speed when "Run Simulation" is actively optimizing (4x fast-forward)
        const effectiveSpeed = isSimulating ? 3.5 : speedMultiplier

        // Nominal circuit transit duration: ~45 seconds for full loop at 1x
        const progressDelta = (deltaMs / (45000 / effectiveSpeed))

        setVehicleProgress(prev => {
          const next = { ...prev }
          FLEET_DEFAULTS.forEach(v => {
            // If vehicle is in breakdown scenario, keep it parked at depot
            const isBroken = (scenarioKey === 'breakdown' || scenarioKey === 'combined') && v.vehicle_id === 'V_ERICK_1'
            if (!isBroken) {
              next[v.vehicle_id] = (prev[v.vehicle_id] + progressDelta) % 1
            }
          })
          return next
        })
      }

      animId = requestAnimationFrame(loop)
    }

    animId = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(animId)
  }, [isPlaying, isSimulating, speedMultiplier, scenarioKey])

  // Extract latest telemetry delays from arrivals
  const vehicleArrivalInfo = useMemo(() => {
    const map = {}
    for (const a of arrivals) {
      if (!map[a.vehicle_id] || a.seq > map[a.vehicle_id].seq) {
        map[a.vehicle_id] = a
      }
    }
    return map
  }, [arrivals])

  // Route polyline coordinates for map drawing
  const routeCoords = useMemo(() => {
    return ROUTE_SEQUENCE.filter(s => STOPS[s]).map(s => [STOPS[s].lat, STOPS[s].lng])
  }, [])

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      {/* Interactive Map HUD Overlay */}
      <div style={{
        position: 'absolute',
        top: 12,
        right: 12,
        zIndex: 1000,
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        background: 'rgba(13, 21, 38, 0.92)',
        backdropFilter: 'blur(8px)',
        border: '1px solid #1a2540',
        borderRadius: 10,
        padding: '6px 10px',
        boxShadow: '0 8px 24px rgba(0,0,0,0.6)',
        pointerEvents: 'auto',
      }}>
        {/* Status Indicator */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, paddingRight: 6, borderRight: '1px solid #1a2540' }}>
          <span style={{
            width: 7,
            height: 7,
            borderRadius: '50%',
            background: isSimulating ? '#60a5fa' : isPlaying ? '#10b981' : '#f59e0b',
            boxShadow: `0 0 8px ${isSimulating ? '#60a5fa' : isPlaying ? '#10b981' : '#f59e0b'}`,
          }} className="live-pulse" />
          <span style={{
            color: isSimulating ? '#93c5fd' : '#e2e8f0',
            fontSize: 10,
            fontWeight: 700,
            letterSpacing: '0.04em',
            textTransform: 'uppercase',
          }}>
            {isSimulating ? 'Simulating Transit...' : isPlaying ? 'Live Transit' : 'Paused'}
          </span>
        </div>

        {/* Speed Multiplier Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          {[1, 2, 4].map(s => (
            <button
              key={s}
              onClick={() => setSpeedMultiplier(s)}
              style={{
                background: speedMultiplier === s ? '#2563eb' : '#111f3a',
                color: speedMultiplier === s ? '#ffffff' : '#94a3b8',
                border: '1px solid',
                borderColor: speedMultiplier === s ? '#3b82f6' : '#1e293b',
                borderRadius: 5,
                padding: '2px 7px',
                fontSize: 9.5,
                fontWeight: 700,
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
            >
              {s}x
            </button>
          ))}
        </div>

        {/* Play/Pause Button */}
        <button
          onClick={() => setIsPlaying(p => !p)}
          style={{
            background: '#111f3a',
            color: '#cbd5e1',
            border: '1px solid #1e293b',
            borderRadius: 5,
            padding: '2px 8px',
            fontSize: 9.5,
            fontWeight: 700,
            cursor: 'pointer',
          }}
          title={isPlaying ? 'Pause transit animation' : 'Resume transit animation'}
        >
          {isPlaying ? '⏸' : '▶'}
        </button>
      </div>

      {/* Leaflet Map */}
      <MapContainer
        center={MAP_CENTER}
        zoom={MAP_ZOOM}
        style={{ height: '100%', width: '100%', background: '#060b18' }}
      >
        {/* Base Dark Map (No API Key Required) */}
        <TileLayer
          url="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}"
          attribution='Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ'
          maxZoom={19}
          maxNativeZoom={16}
        />
        {/* Dark Reference Layer for Labels & Road Names */}
        <TileLayer
          url="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}"
          maxZoom={19}
          maxNativeZoom={16}
        />

        {/* Route Polylines */}
        <Polyline
          positions={routeCoords}
          pathOptions={{
            color: '#3b82f6',
            weight: 3.5,
            opacity: 0.75,
            dashArray: isSimulating ? '6 6' : '10 6',
          }}
        />
        <Polyline
          positions={[...routeCoords].reverse()}
          pathOptions={{
            color: '#1d4ed8',
            weight: 2,
            opacity: 0.35,
            dashArray: '4 10',
          }}
        />

        {/* Stops */}
        {ROUTE_SEQUENCE.map((sid, idx) => {
          const s = STOPS[sid]
          if (!s) return null
          const sev = stopSeverity(sid, alerts)
          const col = SEV_COLOR[sev]
          const stopAlerts = alerts.filter(a => a.stop_id === sid)
          const etasHere   = etas.filter(e => e.stop_id === sid)

          return (
            <CircleMarker
              key={sid}
              center={[s.lat, s.lng]}
              radius={sev === 'high' ? 13 : sev === 'medium' ? 11 : 9}
              pathOptions={{
                color: col.stroke,
                fillColor: col.fill,
                fillOpacity: 0.92,
                weight: 2.5,
              }}
            >
              <Popup>
                <div style={popupStyle}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                    <div style={{ width: 10, height: 10, borderRadius: '50%', background: col.fill, flexShrink: 0 }} />
                    <strong style={pHead}>{s.name}</strong>
                  </div>
                  <p style={pSub}>Stop: {sid} &middot; Seq {idx}</p>

                  {stopAlerts.length > 0 && (
                    <div style={{ marginTop: 8 }}>
                      <p style={{ color: '#9ca3af', fontSize: 10, fontWeight: 700, marginBottom: 4, letterSpacing: '0.06em' }}>
                        ACTIVE ALERTS
                      </p>
                      {stopAlerts.slice(0, 3).map((a, i) => (
                        <p key={i} style={{ color: a.severity === 'high' ? '#f87171' : '#fbbf24', fontSize: 10, margin: '2px 0' }}>
                          &#9888; {a.type.replace(/_/g, ' ')}: {a.message?.slice(0, 50)}...
                        </p>
                      ))}
                    </div>
                  )}

                  {etasHere.length > 0 && (
                    <div style={{ marginTop: 8 }}>
                      <p style={{ color: '#9ca3af', fontSize: 10, fontWeight: 700, marginBottom: 4, letterSpacing: '0.06em' }}>
                        UPCOMING ARRIVALS
                      </p>
                      {etasHere.slice(0, 3).map((e, i) => {
                        const d = e.predicted_delay ?? 0
                        return (
                          <p key={i} style={{ fontSize: 10, color: '#d1d5db', margin: '2px 0' }}>
                            {e.trip_id}: {fmtMin(e.eta)}{' '}
                            <span style={{ color: d > 5 ? '#f87171' : '#34d399', fontWeight: 600 }}>
                              ({d > 0 ? '+' : ''}{d.toFixed(1)} min)
                            </span>
                          </p>
                        )
                      })}
                    </div>
                  )}
                </div>
              </Popup>
            </CircleMarker>
          )
        })}

        {/* Animated Moving Shuttles / Vehicles */}
        {FLEET_DEFAULTS.map(fleetItem => {
          const vid = fleetItem.vehicle_id
          const isBroken = (scenarioKey === 'breakdown' || scenarioKey === 'combined') && vid === 'V_ERICK_1'
          const progress = vehicleProgress[vid] ?? fleetItem.initialOffset
          const pos = interpolateVehiclePosition(progress, CIRCUIT_DATA)

          // If broken down, hold at depot (S_MAIN_GATE)
          const actualLat = isBroken ? STOPS.S_MAIN_GATE.lat : pos.lat
          const actualLng = isBroken ? STOPS.S_MAIN_GATE.lng : pos.lng
          const speed = isBroken ? 0 : fleetItem.baseSpeed * (isSimulating ? 1.5 : 1)
          const info = vehicleArrivalInfo[vid]
          const delay = info ? (info.actual || 0) - (info.scheduled || 0) : 0
          const tripId = info?.trip_id || (vid === 'V_MINIBUS_1' ? 'T007' : vid === 'V_ERICK_2' ? 'T004' : 'T001')

          // Estimated load based on progress & capacity
          const loadFraction = vid === 'V_MINIBUS_1' ? 0.75 : 0.65
          const currentLoad = isBroken ? 0 : Math.round(fleetItem.capacity * loadFraction)

          const icon = createMovingBusIcon(
            vid,
            fleetItem.color,
            speed,
            pos.bearing,
            isBroken
          )

          return (
            <Marker
              key={vid}
              position={[actualLat, actualLng]}
              icon={icon}
            >
              <Popup>
                <div style={popupStyle}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
                    <strong style={pHead}>{fleetItem.name} ({vid})</strong>
                    <span style={{
                      fontSize: 9,
                      fontWeight: 700,
                      padding: '2px 6px',
                      borderRadius: 4,
                      background: isBroken ? 'rgba(239, 68, 68, 0.2)' : 'rgba(16, 185, 129, 0.2)',
                      color: isBroken ? '#f87171' : '#34d399',
                      border: `1px solid ${isBroken ? '#ef4444' : '#10b981'}`,
                    }}>
                      {isBroken ? 'OFFLINE' : 'ACTIVE'}
                    </span>
                  </div>

                  <p style={pSub}>Type: {fleetItem.type} &middot; Route: IIT_CIRCULAR</p>
                  <p style={pSub}>Current Trip: <strong>{tripId}</strong></p>
                  <p style={pSub}>
                    Speed: <strong style={{ color: isBroken ? '#ef4444' : '#60a5fa' }}>{speed.toFixed(1)} km/h</strong>
                  </p>
                  <p style={pSub}>
                    Approaching: <strong>{isBroken ? 'Depot (Halted)' : pos.toStop?.name || 'Next Station'}</strong>
                  </p>
                  <p style={pSub}>
                    Occupancy: <strong>{currentLoad} / {fleetItem.capacity} seats</strong> ({Math.round((currentLoad / fleetItem.capacity) * 100)}%)
                  </p>
                  <p style={{
                    fontSize: 11,
                    fontWeight: 700,
                    color: isBroken ? '#ef4444' : delay > 4 ? '#f59e0b' : '#10b981',
                    marginTop: 6,
                  }}>
                    {isBroken
                      ? '⚠ Breakdown Scenario: Vehicle offline for repair'
                      : delay > 0
                      ? `+${delay.toFixed(1)} min schedule variance`
                      : 'On timetable schedule'
                    }
                  </p>
                </div>
              </Popup>
            </Marker>
          )
        })}
      </MapContainer>
    </div>
  )
}
