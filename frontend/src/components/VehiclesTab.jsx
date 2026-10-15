import React from 'react'
import { STOPS, fmtMin } from '../constants.js'

export default function VehiclesTab({ arrivals }) {
  const map = {}
  for (const a of arrivals) {
    if (!map[a.vehicle_id] || a.seq > map[a.vehicle_id].seq) map[a.vehicle_id] = a
  }
  const list = Object.values(map)

  if (!list.length) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: 140, textAlign: 'center' }}>
        <span style={{ fontSize: 32, marginBottom: 8 }}>&#128652;</span>
        <p style={{ color: '#6b7280', fontSize: 13 }}>No vehicle data yet</p>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {list.map(v => {
        const delay = (v.actual || 0) - (v.scheduled || 0)
        const dotColor = delay > 8 ? '#ef4444' : delay > 3 ? '#f59e0b' : '#10b981'
        const delayLabel = delay > 0 ? `+${delay.toFixed(1)} min late` : 'On time'

        return (
          <div key={v.vehicle_id}
               style={{ background: '#111f3a', border: '1px solid #1a2540', borderRadius: 12, padding: '12px 14px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <div style={{ width: 10, height: 10, borderRadius: '50%', background: dotColor, flexShrink: 0 }} />
                <strong style={{ color: '#f9fafb', fontSize: 13 }}>{v.vehicle_id}</strong>
              </div>
              <span style={{ fontSize: 10, fontWeight: 600, padding: '2px 8px', borderRadius: 20, background: 'rgba(37,99,235,0.2)', color: '#93c5fd', border: '1px solid rgba(37,99,235,0.3)' }}>
                {v.route_id}
              </span>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '3px 0', fontSize: 11 }}>
              <Row label="Trip"       val={v.trip_id} />
              <Row label="Stop seq"   val={`#${v.seq}`} />
              <Row label="Location"   val={STOPS[v.stop_id]?.name || v.stop_id} />
              <Row label="Scheduled"  val={fmtMin(v.scheduled)} />
              <Row label="Actual"     val={fmtMin(v.actual)} />
              <Row label="Status"     val={<span style={{ color: dotColor, fontWeight: 600 }}>{delayLabel}</span>} />
            </div>
          </div>
        )
      })}
    </div>
  )
}

function Row({ label, val }) {
  return (
    <>
      <span style={{ color: '#4b5563' }}>{label}</span>
      <span style={{ color: '#d1d5db' }}>{val}</span>
    </>
  )
}
