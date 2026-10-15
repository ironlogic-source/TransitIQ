// IIT Delhi campus stops (lat, lng)
export const STOPS = {
  S_METRO:          { name: 'IIT Metro Station',          lat: 28.5430, lng: 77.1930 },
  S_MAIN_GATE:      { name: 'IIT Main Gate',              lat: 28.5440, lng: 77.1920 },
  S_ACAD_BLOCK:     { name: 'Academic Area (Dogra Hall)', lat: 28.5450, lng: 77.1900 },
  S_HOSTEL_ZANSKAR: { name: 'Zanskar Hostel',            lat: 28.5470, lng: 77.1880 },
  S_HOSPITAL:       { name: 'IIT Hospital',               lat: 28.5410, lng: 77.1850 },
}

export const ROUTE_SEQUENCE = [
  'S_METRO', 'S_MAIN_GATE', 'S_ACAD_BLOCK', 'S_HOSTEL_ZANSKAR', 'S_HOSPITAL',
]

export const MAP_CENTER = [28.5445, 77.1890]
export const MAP_ZOOM   = 15

export const SCENARIOS = [
  { value: 'normal',    label: 'Normal Day',              body: null },
  { value: 'peak',      label: 'Peak Surge (1.5x)',        body: { demand_multiplier: { '*': 1.5 } } },
  { value: 'breakdown', label: 'Vehicle Breakdown',        body: { unavailable_vehicles: ['V_ERICK_1'] } },
  { value: 'delay',     label: 'Road Delay (+8 min)',       body: { route_delays: { IIT_CIRCULAR: 8 } } },
  { value: 'combined',  label: 'Combined Disruption',       body: {
    unavailable_vehicles: ['V_ERICK_1'],
    demand_multiplier: { 'S_HOSTEL_ZANSKAR': 2.0 },
    route_delays: { IIT_CIRCULAR: 5 },
  }},
]

export function fmtMin(min) {
  if (min === null || min === undefined) return '--:--'
  const m = Math.round(min)
  return `${String(Math.floor(m / 60) % 24).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`
}
