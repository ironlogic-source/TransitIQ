import React from 'react'
import { Activity, Play, Loader2, CheckCircle, ChevronDown } from 'lucide-react'
import { SCENARIOS } from '../constants.js'

const STATUS = {
  idle:       { dot: '#4b5563', text: '#6b7280', label: 'Offline'        },
  loading:    { dot: '#f59e0b', text: '#f59e0b', label: 'Loading...'     },
  ready:      { dot: '#10b981', text: '#10b981', label: 'Live',  pulse: true },
  optimizing: { dot: '#3b82f6', text: '#60a5fa', label: 'Optimising...'  },
  done:       { dot: '#10b981', text: '#10b981', label: 'Optimised', pulse: true },
}

export default function Header({
  status, scenarioKey, onScenarioChange, onRun, meta, currentTimeLabel, warnings,
}) {
  const busy = status === 'loading' || status === 'optimizing'
  const cfg  = STATUS[status] || STATUS.idle

  return (
    <header
      className="flex-none flex items-center justify-between gap-4 px-5 py-3 border-b border-[#1a2540]"
      style={{ background: '#0d1526' }}
    >
      {/* Logo */}
      <div className="flex items-center gap-3 flex-none">
        <div className="w-9 h-9 rounded-xl flex items-center justify-center shadow-lg"
             style={{ background: 'linear-gradient(135deg,#2563eb,#1d4ed8)' }}>
          <Activity size={16} color="#fff" />
        </div>
        <div>
          <h1 className="text-white font-extrabold text-sm leading-tight tracking-tight">TransitIQ</h1>
          <p className="text-[11px]" style={{ color: '#4b5563' }}>RoutePulse &middot; IIT Delhi</p>
        </div>
      </div>

      {/* Network stats */}
      {meta && (
        <div className="hidden lg:flex items-center gap-4 text-[11px]" style={{ color: '#6b7280' }}>
          {[
            ['Vehicles', meta.n_vehicles],
            ['Routes',   meta.n_routes],
            ['Stops',    meta.n_stops],
            ['Trips',    meta.n_trips],
          ].map(([label, val]) => (
            <span key={label}>
              {label}{' '}
              <strong style={{ color: '#d1d5db' }}>{val}</strong>
            </span>
          ))}
          {currentTimeLabel && (
            <span className="font-bold" style={{ color: '#60a5fa' }}>&#9201; {currentTimeLabel}</span>
          )}
          {warnings?.length > 0 && (
            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold"
                  style={{ background: '#451a03', color: '#fb923c', border: '1px solid #7c2d12' }}>
              &#9888; {warnings.length} warning{warnings.length > 1 ? 's' : ''}
            </span>
          )}
        </div>
      )}

      {/* Controls */}
      <div className="flex items-center gap-3 flex-none">

        {/* Status dot */}
        <div className="flex items-center gap-1.5 text-[11px] font-semibold" style={{ color: cfg.text }}>
          <span
            className={cfg.pulse ? 'live-pulse' : ''}
            style={{ width: 8, height: 8, borderRadius: '50%', background: cfg.dot, display: 'inline-block' }}
          />
          {cfg.label}
        </div>

        {/* Scenario picker */}
        <div className="relative">
          <select
            value={scenarioKey}
            onChange={e => onScenarioChange(e.target.value)}
            disabled={busy}
            style={{
              background: '#111f3a', border: '1px solid #1a2540', color: '#d1d5db',
              fontSize: 11, borderRadius: 8, padding: '6px 28px 6px 10px',
              outline: 'none', cursor: 'pointer', appearance: 'none',
            }}
          >
            {SCENARIOS.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
          </select>
          <ChevronDown size={11} color="#6b7280"
            style={{ position: 'absolute', right: 8, top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none' }} />
        </div>

        {/* Run button */}
        <button
          onClick={onRun}
          disabled={busy}
          style={{
            display: 'flex', alignItems: 'center', gap: 6,
            padding: '7px 16px', borderRadius: 8, fontSize: 12, fontWeight: 700,
            background: busy ? '#1e3a5f' : '#2563eb',
            color: busy ? '#4b7ccc' : '#fff',
            cursor: busy ? 'not-allowed' : 'pointer',
            border: 'none',
            boxShadow: busy ? 'none' : '0 4px 16px rgba(37,99,235,0.4)',
            transition: 'all 0.2s',
          }}
        >
          {status === 'optimizing' ? (
            <><Loader2 size={13} className="animate-spin" />Optimising...</>
          ) : status === 'done' ? (
            <><CheckCircle size={13} />Re-run</>
          ) : (
            <><Play size={13} />Run Simulation</>
          )}
        </button>
      </div>
    </header>
  )
}
