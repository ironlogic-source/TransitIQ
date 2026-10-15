import React, { useState, useEffect, useCallback } from 'react'
import Header from './components/Header.jsx'
import KPIBar from './components/KPIBar.jsx'
import MapView from './components/MapView.jsx'
import AlertsPanel from './components/AlertsPanel.jsx'
import VehiclesTab from './components/VehiclesTab.jsx'
import ETAsTab from './components/ETAsTab.jsx'
import OptimizePanel from './components/OptimizePanel.jsx'
import { SCENARIOS } from './constants.js'

const TABS = [
  { key: 'alerts',   label: (d) => `Alerts (${d?.alerts?.length ?? 0})` },
  { key: 'vehicles', label: () => 'Vehicles' },
  { key: 'etas',     label: () => 'ETAs' },
]

export default function App() {
  const [status,      setStatus]      = useState('idle')
  const [data,        setData]        = useState(null)
  const [runData,     setRunData]     = useState(null)
  const [error,       setError]       = useState(null)
  const [scenarioKey, setScenarioKey] = useState('normal')
  const [activeTab,   setActiveTab]   = useState('alerts')

  const scenarioBody = SCENARIOS.find(s => s.value === scenarioKey)?.body ?? null

  const fetchPredict = useCallback(async (body = null) => {
    setStatus('loading')
    setError(null)
    setRunData(null)
    try {
      const res  = await fetch('/api/predict', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario: body }),
      })
      const json = await res.json()
      if (!res.ok) throw new Error(json.detail || 'Prediction failed')
      setData(json)
      setStatus('ready')
    } catch (e) {
      setError(e.message)
      setStatus('idle')
    }
  }, [])

  const runSimulation = useCallback(async () => {
    setStatus('optimizing')
    setError(null)
    try {
      const res  = await fetch('/api/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario: scenarioBody, optimize: true, max_steps: 3 }),
      })
      const json = await res.json()
      if (!res.ok) throw new Error(json.detail || 'Simulation failed')
      setData(json)
      setRunData(json)
      setStatus('done')
    } catch (e) {
      setError(e.message)
      setStatus('ready')
    }
  }, [scenarioBody])

  useEffect(() => { fetchPredict(null) }, [fetchPredict])

  const handleScenarioChange = (key) => {
    setScenarioKey(key)
    const body = SCENARIOS.find(s => s.value === key)?.body ?? null
    fetchPredict(body)
  }

  const d       = data
  const loading = status === 'loading' || status === 'optimizing'

  return (
    <div className="flex flex-col bg-[#060b18]" style={{ height: '100vh', overflow: 'hidden' }}>

      <Header
        status={status}
        scenarioKey={scenarioKey}
        onScenarioChange={handleScenarioChange}
        onRun={runSimulation}
        meta={d?.meta}
        currentTimeLabel={d?.current_time_label}
        warnings={d?.warnings || []}
      />

      {/* Error banner */}
      {error && (
        <div className="mx-4 mt-2 px-4 py-2 bg-red-950/60 border border-red-800/60 rounded-lg
                        text-red-400 text-xs flex items-center gap-2 flex-none">
          <span>&#9888;</span>
          <span className="flex-1">{error}</span>
          <button onClick={() => setError(null)} className="text-red-600 hover:text-red-400 text-base leading-none">&#x2715;</button>
        </div>
      )}

      {/* Loading splash */}
      {!d && loading && (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <div className="w-10 h-10 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
            <p className="text-gray-400 text-sm font-medium">Initialising TransitIQ pipeline...</p>
            <p className="text-gray-600 text-xs mt-1">Training ETA model · Forecasting demand</p>
          </div>
        </div>
      )}

      {d && (
        <>
          <KPIBar kpis={d.kpis} afterKpis={runData?.after?.kpis} etaEval={d.eta_eval} />

          {/* Main grid: map + right panel */}
          <div className="flex gap-3 px-4 pb-2 flex-1 min-h-0">

            {/* Map — 60% */}
            <div className="rounded-xl overflow-hidden border border-[#1a2540] flex-none"
                 style={{ width: '60%' }}>
              <MapView
                arrivals={d.arrivals || []}
                etas={d.etas || []}
                alerts={d.alerts || []}
              />
            </div>

            {/* Right panel — 40% */}
            <div className="flex-1 flex flex-col bg-[#0d1526] rounded-xl border border-[#1a2540] overflow-hidden min-w-0">

              {/* Tabs */}
              <div className="flex border-b border-[#1a2540] flex-none">
                {TABS.map(tab => (
                  <button
                    key={tab.key}
                    onClick={() => setActiveTab(tab.key)}
                    className={`flex-1 py-2.5 text-[10px] font-bold uppercase tracking-widest transition-all ${
                      activeTab === tab.key
                        ? 'text-blue-400 border-b-2 border-blue-500 bg-blue-950/20'
                        : 'text-gray-600 hover:text-gray-400 hover:bg-white/5'
                    }`}
                  >
                    {tab.label(d)}
                  </button>
                ))}
              </div>

              {/* Tab content */}
              <div className="flex-1 overflow-y-auto p-3">
                {activeTab === 'alerts'   && <AlertsPanel   alerts={d.alerts || []} />}
                {activeTab === 'vehicles' && <VehiclesTab   arrivals={d.arrivals || []} />}
                {activeTab === 'etas'     && <ETAsTab       etas={d.etas || []} />}
              </div>
            </div>
          </div>

          {/* Optimization results */}
          {runData?.result && (
            <div className="px-4 pb-3 flex-none" style={{ maxHeight: '280px', overflowY: 'auto' }}>
              <OptimizePanel
                result={runData.result}
                afterKpis={runData.after?.kpis}
                beforeKpis={d.kpis}
              />
            </div>
          )}
        </>
      )}
    </div>
  )
}
