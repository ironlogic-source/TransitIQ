import React from 'react'
import { AlertTriangle, Users, Clock, TrendingDown, Zap } from 'lucide-react'

function Card({ icon: Icon, label, value, sub, iconBg, iconColor, prev, unit = '' }) {
  const hasComp  = prev !== undefined && prev !== null
  const numVal   = parseFloat(value)
  const numPrev  = parseFloat(prev)
  const improved = hasComp && numVal < numPrev
  const worsened = hasComp && numVal > numPrev
  const pct      = hasComp && numPrev > 0
    ? Math.abs(((numVal - numPrev) / numPrev) * 100).toFixed(0)
    : null

  return (
    <div
      className="flex-1 rounded-xl p-4 border hover:border-blue-900/40 transition-colors"
      style={{ background: '#0d1526', borderColor: '#1a2540', minWidth: 0 }}
    >
      <div className="flex items-center justify-between mb-3">
        <span style={{ color: '#6b7280', fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
          {label}
        </span>
        <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: iconBg }}>
          <Icon size={13} color={iconColor} />
        </div>
      </div>

      <div className="flex items-end gap-2">
        <span style={{ fontSize: 26, fontWeight: 800, color: '#f9fafb', fontVariantNumeric: 'tabular-nums' }}>
          {value}{unit}
        </span>
        {hasComp && pct && (
          <span style={{
            fontSize: 10, fontWeight: 700, padding: '2px 6px', borderRadius: 20, marginBottom: 2,
            background: improved ? 'rgba(16,185,129,0.15)' : worsened ? 'rgba(239,68,68,0.15)' : 'rgba(107,114,128,0.15)',
            color:      improved ? '#10b981'               : worsened ? '#ef4444'               : '#9ca3af',
          }}>
            {improved ? '\u2193' : '\u2191'}{pct}%
          </span>
        )}
      </div>

      {sub && (
        <p style={{ color: '#4b5563', fontSize: 10, marginTop: 4, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {sub}
        </p>
      )}
      {hasComp && (
        <p style={{ color: '#374151', fontSize: 10, marginTop: 2 }}>
          was {prev}{unit}
        </p>
      )}
    </div>
  )
}

export default function KPIBar({ kpis, afterKpis, etaEval }) {
  if (!kpis) return null
  const a = afterKpis

  return (
    <div className="flex gap-3 px-4 pt-3 pb-2 flex-none">
      <Card
        icon={AlertTriangle} label="Total Alerts"
        value={a ? a.total_alerts : kpis.total_alerts}
        prev={a ? kpis.total_alerts : undefined}
        iconBg="rgba(239,68,68,0.15)" iconColor="#ef4444"
        sub="Risk events detected"
      />
      <Card
        icon={Users} label="Overcrowded Stops"
        value={a ? a.overcrowded_stops : kpis.overcrowded_stops}
        prev={a ? kpis.overcrowded_stops : undefined}
        iconBg="rgba(245,158,11,0.15)" iconColor="#f59e0b"
        sub="Stop-trip pairs over capacity"
      />
      <Card
        icon={Clock} label="Delayed Trips"
        value={a ? a.delayed_trips : kpis.delayed_trips}
        prev={a ? kpis.delayed_trips : undefined}
        iconBg="rgba(59,130,246,0.15)" iconColor="#3b82f6"
        sub="Trips predicted late"
      />
      <Card
        icon={TrendingDown} label="Unmet Demand"
        value={a
          ? Math.round(a.forecast_total_unmet ?? 0)
          : Math.round(kpis.forecast_total_unmet ?? 0)}
        prev={a ? Math.round(kpis.forecast_total_unmet ?? 0) : undefined}
        iconBg="rgba(139,92,246,0.15)" iconColor="#8b5cf6"
        sub="Passengers without seats"
      />
      {etaEval && (
        <Card
          icon={Zap} label="ETA Accuracy"
          value={etaEval.improvement_pct} unit="%"
          iconBg="rgba(16,185,129,0.15)" iconColor="#10b981"
          sub={`MAE: ${etaEval.mae_eta} min vs ${etaEval.mae_scheduled_baseline} min timetable`}
        />
      )}
    </div>
  )
}
