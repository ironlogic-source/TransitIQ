import React from 'react'
import { CheckCircle, XCircle, ArrowRight, TrendingUp, TrendingDown, Minus } from 'lucide-react'

export default function OptimizePanel({ result, afterKpis, beforeKpis }) {
  if (!result) return null

  const { status, message, actions, comparison, validation } = result
  const feasible = validation?.feasible
  const improved = status === 'improved'

  return (
    <div style={{ background: '#0d1526', border: '1px solid #1a2540', borderRadius: 14, overflow: 'hidden' }}>

      {/* Header */}
      <div style={{
        padding: '12px 18px', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        background: improved ? 'rgba(6,78,59,0.15)' : 'rgba(120,53,15,0.1)',
        borderBottom: '1px solid #1a2540',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {improved
            ? <CheckCircle size={18} color="#10b981" />
            : <XCircle    size={18} color="#f59e0b" />
          }
          <div>
            <h2 style={{ color: '#f9fafb', fontSize: 13, fontWeight: 700, margin: 0 }}>Optimisation Results</h2>
            <p style={{ color: '#9ca3af', fontSize: 11, margin: '2px 0 0' }}>{message}</p>
          </div>
        </div>
        <span style={{
          fontSize: 10, fontWeight: 700, padding: '4px 10px', borderRadius: 20,
          background: feasible ? 'rgba(6,78,59,0.3)'  : 'rgba(127,29,29,0.3)',
          color:      feasible ? '#34d399'             : '#f87171',
          border:     feasible ? '1px solid rgba(6,78,59,0.5)' : '1px solid rgba(127,29,29,0.5)',
        }}>
          {feasible ? 'Plan Feasible \u2713' : 'Constraint Violation \u2717'}
        </span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', borderTop: 'none' }}>

        {/* Actions */}
        <div style={{ padding: '14px 16px', borderRight: '1px solid #1a2540' }}>
          <p style={{ color: '#6b7280', fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 10 }}>
            Recommended Actions ({actions?.length ?? 0})
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: 190, overflowY: 'auto' }}>
            {(!actions || actions.length === 0) && (
              <p style={{ color: '#4b5563', fontSize: 12 }}>No actions required — plan is optimal.</p>
            )}
            {actions?.map((a, i) => (
              <div key={i} style={{ background: '#111f3a', border: '1px solid #1a2540', borderRadius: 10, padding: '10px 12px' }}>
                <p style={{ color: '#f9fafb', fontSize: 12, fontWeight: 600, margin: '0 0 4px' }}>{a.description}</p>
                <p style={{ color: '#9ca3af', fontSize: 11, margin: '0 0 6px' }}>{a.reason}</p>
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 5 }}>
                  <ArrowRight size={11} color="#f59e0b" style={{ marginTop: 1, flexShrink: 0 }} />
                  <p style={{ color: '#fbbf24', fontSize: 11, fontStyle: 'italic', margin: 0 }}>{a.tradeoff}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Comparison table */}
        <div style={{ padding: '14px 16px' }}>
          <p style={{ color: '#6b7280', fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 10 }}>
            Before &rarr; After
          </p>
          <div style={{ borderRadius: 10, border: '1px solid #1a2540', overflow: 'hidden' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
              <thead>
                <tr style={{ background: '#111f3a' }}>
                  {['Metric', 'Before', 'After', 'Improvement'].map(h => (
                    <th key={h} style={{ color: '#6b7280', fontWeight: 600, padding: '7px 10px', textAlign: h === 'Metric' ? 'left' : 'right', borderBottom: '1px solid #1a2540', fontSize: 10 }}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {comparison?.map((row, i) => {
                  const pct = row.improvement_pct ?? 0
                  const dir = pct > 0.5 ? 'up' : pct < -0.5 ? 'down' : 'flat'
                  const color = dir === 'up' ? '#10b981' : dir === 'down' ? '#ef4444' : '#6b7280'
                  return (
                    <tr key={i} style={{ borderBottom: i < comparison.length - 1 ? '1px solid #1a2540' : 'none' }}>
                      <td style={{ padding: '7px 10px', color: '#d1d5db', fontWeight: 500, textTransform: 'capitalize' }}>
                        {row.metric.replace(/_/g, ' ')}
                      </td>
                      <td style={{ padding: '7px 10px', color: '#6b7280', textAlign: 'right' }}>
                        {fmt(row.baseline)}
                      </td>
                      <td style={{ padding: '7px 10px', color: '#f9fafb', fontWeight: 600, textAlign: 'right' }}>
                        {fmt(row.optimized)}
                      </td>
                      <td style={{ padding: '7px 10px', textAlign: 'right' }}>
                        <span style={{ color, fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 3 }}>
                          {dir === 'up'   ? <TrendingUp   size={10} /> :
                           dir === 'down' ? <TrendingDown size={10} /> :
                                           <Minus        size={10} />}
                          {pct > 0 ? '+' : ''}{pct.toFixed(1)}%
                        </span>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}

function fmt(v) {
  if (v === null || v === undefined) return '—'
  return typeof v === 'number' ? v.toFixed(2) : v
}
