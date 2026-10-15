import React from 'react'
import { fmtMin } from '../constants.js'

export default function ETAsTab({ etas }) {
  if (!etas.length) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: 140, textAlign: 'center' }}>
        <span style={{ fontSize: 32, marginBottom: 8 }}>&#9201;</span>
        <p style={{ color: '#6b7280', fontSize: 13 }}>No ETA predictions</p>
        <p style={{ color: '#374151', fontSize: 11, marginTop: 4 }}>Run simulation to generate ETAs</p>
      </div>
    )
  }

  const shown = etas.slice(0, 30)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      {shown.map((e, i) => {
        const delay = e.predicted_delay ?? 0
        const [bg, border, color] =
          delay > 8 ? ['rgba(127,29,29,0.25)', 'rgba(153,27,27,0.4)',  '#f87171'] :
          delay > 3 ? ['rgba(120,53,15,0.2)',  'rgba(146,64,14,0.35)', '#fbbf24'] :
                      ['rgba(6,28,19,0.3)',    'rgba(6,78,59,0.3)',    '#34d399']

        return (
          <div key={i} style={{ background: '#111f3a', border: '1px solid #1a2540', borderRadius: 8, padding: '8px 10px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
            <div style={{ minWidth: 0, flex: 1 }}>
              <p style={{ color: '#e5e7eb', fontSize: 11, fontWeight: 600, margin: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {e.trip_id} &rarr; <span style={{ color: '#9ca3af' }}>{e.stop_id}</span>
              </p>
              <p style={{ color: '#4b5563', fontSize: 10, margin: '2px 0 0' }}>
                ETA {fmtMin(e.eta)} &middot; {fmtMin(e.eta_lo)}&ndash;{fmtMin(e.eta_hi)}
              </p>
            </div>
            <span style={{ fontSize: 10, fontWeight: 700, padding: '3px 8px', borderRadius: 20, background: bg, border: `1px solid ${border}`, color, flexShrink: 0 }}>
              {delay > 0 ? '+' : ''}{delay.toFixed(1)} min
            </span>
          </div>
        )
      })}
      {etas.length > 30 && (
        <p style={{ textAlign: 'center', color: '#4b5563', fontSize: 10, paddingTop: 4 }}>
          + {etas.length - 30} more predictions
        </p>
      )}
    </div>
  )
}
