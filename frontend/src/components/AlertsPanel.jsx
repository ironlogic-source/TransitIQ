import React from 'react'

const SEV = {
  high:   { bg: 'rgba(127,29,29,0.3)',  border: 'rgba(153,27,27,0.5)',  badge: { bg: 'rgba(127,29,29,0.6)', color: '#fca5a5' } },
  medium: { bg: 'rgba(120,53,15,0.25)', border: 'rgba(146,64,14,0.4)',  badge: { bg: 'rgba(120,53,15,0.5)', color: '#fcd34d' } },
  low:    { bg: 'rgba(23,37,84,0.25)',  border: 'rgba(30,58,138,0.4)',  badge: { bg: 'rgba(23,37,84,0.5)',  color: '#93c5fd' } },
}

const TYPE_ICON = {
  OVERCROWDING:      '\uD83D\uDC65',
  DELAY:             '\u23F1',
  NEAR_CAPACITY:     '\u26A1',
  MISSED_CONNECTION: '\uD83D\uDD04',
}

export default function AlertsPanel({ alerts }) {
  if (!alerts.length) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: 160, textAlign: 'center' }}>
        <div style={{ width: 44, height: 44, borderRadius: '50%', background: 'rgba(16,185,129,0.1)', border: '1px solid rgba(16,185,129,0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 20, marginBottom: 10 }}>
          &#9989;
        </div>
        <p style={{ color: '#10b981', fontSize: 13, fontWeight: 600 }}>No Active Alerts</p>
        <p style={{ color: '#4b5563', fontSize: 11, marginTop: 4 }}>All routes operating normally</p>
      </div>
    )
  }

  const counts = { high: 0, medium: 0, low: 0 }
  for (const a of alerts) counts[a.severity] = (counts[a.severity] || 0) + 1

  return (
    <div>
      {/* Summary badges */}
      <div style={{ display: 'flex', gap: 6, marginBottom: 10 }}>
        {counts.high   > 0 && <Badge label={`${counts.high} High`}   bg="rgba(127,29,29,0.5)"  color="#fca5a5" />}
        {counts.medium > 0 && <Badge label={`${counts.medium} Med`}  bg="rgba(120,53,15,0.5)"  color="#fcd34d" />}
        {counts.low    > 0 && <Badge label={`${counts.low} Low`}     bg="rgba(23,37,84,0.5)"   color="#93c5fd" />}
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {alerts.map((a, i) => {
          const s = SEV[a.severity] || SEV.low
          return (
            <div key={i} style={{ background: s.bg, border: `1px solid ${s.border}`, borderRadius: 10, padding: '10px 12px' }}>
              <div style={{ display: 'flex', gap: 8 }}>
                <span style={{ fontSize: 16, flexShrink: 0, marginTop: 1 }}>{TYPE_ICON[a.type] || '\u26A0\uFE0F'}</span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 5, flexWrap: 'wrap' }}>
                    <span style={{ fontSize: 10, fontWeight: 700, padding: '2px 7px', borderRadius: 20, background: s.badge.bg, color: s.badge.color }}>
                      {a.severity.toUpperCase()}
                    </span>
                    <span style={{ fontSize: 10, color: '#6b7280', fontWeight: 500 }}>
                      {a.type.replace(/_/g, ' ')}
                    </span>
                  </div>
                  <p style={{ color: '#d1d5db', fontSize: 11, lineHeight: 1.5, margin: 0 }}>{a.message}</p>
                  <div style={{ display: 'flex', gap: 10, marginTop: 5 }}>
                    {a.route_id && <Tag label="Route" val={a.route_id} />}
                    {a.trip_id  && <Tag label="Trip"  val={a.trip_id}  />}
                    {a.stop_id  && <Tag label="Stop"  val={a.stop_id}  />}
                  </div>
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function Badge({ label, bg, color }) {
  return (
    <span style={{ fontSize: 10, fontWeight: 700, padding: '3px 8px', borderRadius: 20, background: bg, color }}>
      {label}
    </span>
  )
}

function Tag({ label, val }) {
  return (
    <span style={{ fontSize: 10, color: '#4b5563' }}>
      {label}: <span style={{ color: '#6b7280' }}>{val}</span>
    </span>
  )
}
