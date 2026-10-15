import React from 'react'
import { MapContainer, TileLayer, CircleMarker, Polyline, Popup, Marker } from 'react-leaflet'
import L from 'leaflet'
import { STOPS, ROUTE_SEQUENCE, MAP_CENTER, MAP_ZOOM, fmtMin } from '../constants.js'

function getVehiclePositions(arrivals) {
  const map = {}
  for (const a of arrivals) {
    if (!map[a.vehicle_id] || a.seq > map[a.vehicle_id].seq) map[a.vehicle_id] = a
  }
  return Object.values(map)
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

function makeBusIcon(color) {
  return L.divIcon({
    html: `<div style="width:26px;height:26px;background:${color};border:2.5px solid rgba(255,255,255,0.85);border-radius:50% 50% 50% 0;transform:rotate(-45deg);box-shadow:0 3px 12px rgba(0,0,0,0.6)"></div>`,
    iconSize: [26, 26],
    iconAnchor: [13, 26],
    className: '',
  })
}

const popupStyle = { fontFamily: 'Inter,sans-serif', minWidth: 170 }
const pHead      = { color: '#f9fafb', fontSize: 13, fontWeight: 700, margin: '0 0 4px' }
const pSub       = { color: '#6b7280', fontSize: 11, margin: '2px 0' }

export default function MapView({ arrivals, etas, alerts }) {
  const routeCoords = ROUTE_SEQUENCE.filter(s => STOPS[s]).map(s => [STOPS[s].lat, STOPS[s].lng])
  const vehicles    = getVehiclePositions(arrivals)

  return (
    <MapContainer center={MAP_CENTER} zoom={MAP_ZOOM} style={{ height: '100%', width: '100%' }}>
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

      {/* Route line */}
      <Polyline positions={routeCoords}
        pathOptions={{ color: '#3b82f6', weight: 3, opacity: 0.65, dashArray: '10 6' }} />
      <Polyline positions={[...routeCoords].reverse()}
        pathOptions={{ color: '#1d4ed8', weight: 2, opacity: 0.3,  dashArray: '4 10' }} />

      {/* Stops */}
      {ROUTE_SEQUENCE.map((sid, idx) => {
        const s   = STOPS[sid]
        if (!s) return null
        const sev = stopSeverity(sid, alerts)
        const col = SEV_COLOR[sev]
        const stopAlerts = alerts.filter(a => a.stop_id === sid)
        const etasHere   = etas.filter(e => e.stop_id === sid)

        return (
          <CircleMarker key={sid}
            center={[s.lat, s.lng]}
            radius={sev === 'high' ? 13 : sev === 'medium' ? 11 : 9}
            pathOptions={{ color: col.stroke, fillColor: col.fill, fillOpacity: 0.9, weight: 2.5 }}
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
                    <p style={{ color: '#9ca3af', fontSize: 10, fontWeight: 700, marginBottom: 4, letterSpacing: '0.06em' }}>ALERTS</p>
                    {stopAlerts.slice(0, 3).map((a, i) => (
                      <p key={i} style={{ color: a.severity === 'high' ? '#f87171' : '#fbbf24', fontSize: 10, margin: '2px 0' }}>
                        &#9888; {a.type.replace(/_/g, ' ')}
                      </p>
                    ))}
                  </div>
                )}

                {etasHere.length > 0 && (
                  <div style={{ marginTop: 8 }}>
                    <p style={{ color: '#9ca3af', fontSize: 10, fontWeight: 700, marginBottom: 4, letterSpacing: '0.06em' }}>NEXT ARRIVALS</p>
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

      {/* Vehicle markers */}
      {vehicles.map((v, idx) => {
        const stop = STOPS[v.stop_id]
        if (!stop) return null
        const delay = (v.actual || 0) - (v.scheduled || 0)
        const color = delay > 8 ? '#ef4444' : delay > 3 ? '#f59e0b' : '#10b981'
        const off   = idx * 0.0005

        return (
          <Marker key={v.vehicle_id}
            position={[stop.lat + off, stop.lng + off]}
            icon={makeBusIcon(color)}
          >
            <Popup>
              <div style={popupStyle}>
                <strong style={pHead}>{v.vehicle_id}</strong>
                <p style={pSub}>Route: {v.route_id}</p>
                <p style={pSub}>Trip: {v.trip_id}</p>
                <p style={pSub}>At: {STOPS[v.stop_id]?.name || v.stop_id}</p>
                <p style={{ fontSize: 11, fontWeight: 700, color, marginTop: 6 }}>
                  {delay > 0 ? `+${delay.toFixed(1)} min late` : 'On time'}
                </p>
              </div>
            </Popup>
          </Marker>
        )
      })}
    </MapContainer>
  )
}
