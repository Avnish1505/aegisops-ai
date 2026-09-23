import { useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import type { Assignment, Decision, Location, Scenario, SelectedEntity } from '../types'
import { humanize } from '../lib/format'

// Marker colours mirror the sev.*/status.* tokens in tailwind.config.js; Leaflet markers are
// plain HTML/SVG outside React, so they can't read Tailwind classes. Keep them in sync.
const SEV_COLOURS = { critical: '#a13a24', high: '#95541a', medium: '#8a6a12', low: '#2f5478' } as const
const RESOURCE_AVAILABLE = '#3f6b46'
const RESOURCE_UNAVAILABLE = '#a89572'
const ROUTE_LINE = '#5b6f74'
const ROUTE_LINE_ACTIVE = '#241d13'

/** OpenStreetMap's public tiles by default; set VITE_TILE_URL for heavier or offline use. */
const TILE_URL = import.meta.env.VITE_TILE_URL ?? 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'
const ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'

interface OperationalMapProps {
  scenario: Scenario
  decision: Decision | null
  selected: SelectedEntity
  activeAssignment: Assignment | null
  onSelect: (entity: SelectedEntity) => void
}

const latLng = (location: Location): L.LatLngTuple => [location.lat, location.lon]

function markerIcon(shape: string, colour: string, selected: boolean, dimmed = false) {
  const ring = selected ? 'box-shadow:0 0 0 3px #fffdf8,0 0 0 5px #241d13;' : ''
  const base = `display:block;width:14px;height:14px;background:${colour};border:2px solid #fffdf8;${ring}opacity:${dimmed ? 0.55 : 1};`
  const shapes: Record<string, string> = {
    square: `${base}border-radius:2px;`,
    diamond: `${base}transform:rotate(45deg);`,
    circle: `${base}border-radius:50%;`,
  }
  return L.divIcon({ className: 'aegis-marker', html: `<span style="${shapes[shape]}"></span>`, iconSize: [18, 18] })
}

/** Real WGS84 positions on an OpenStreetMap basemap. Every marker is a selectable,
 * keyboard-reachable entity (Leaflet markers take focus and respond to Enter). */
export function OperationalMap({ scenario, decision, selected, activeAssignment, onSelect }: OperationalMapProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<L.Map | null>(null)
  const layerRef = useRef<L.LayerGroup | null>(null)

  useEffect(() => {
    if (!containerRef.current) return
    const map = L.map(containerRef.current, { scrollWheelZoom: false })
    L.tileLayer(TILE_URL, { attribution: ATTRIBUTION, maxZoom: 19 }).addTo(map)
    layerRef.current = L.layerGroup().addTo(map)
    mapRef.current = map
    return () => {
      map.remove()
      mapRef.current = null
    }
  }, [])

  useEffect(() => {
    const points = [...scenario.incidents, ...scenario.resources].map((item) => latLng(item.location))
    if (points.length) mapRef.current?.fitBounds(L.latLngBounds(points), { padding: [24, 24] })
  }, [scenario])

  useEffect(() => {
    const layer = layerRef.current
    if (!layer) return
    layer.clearLayers()
    const incidents = new Map(scenario.incidents.map((item) => [item.id, item]))
    const resources = new Map(scenario.resources.map((item) => [item.id, item]))
    const activeKey = activeAssignment ? `${activeAssignment.incident_id}:${activeAssignment.resource_id}` : null

    decision?.assignments.forEach((assignment) => {
      const incident = incidents.get(assignment.incident_id)
      const resource = resources.get(assignment.resource_id)
      if (!incident || !resource) return
      const isActive = activeKey === `${assignment.incident_id}:${assignment.resource_id}`
      L.polyline([latLng(resource.location), latLng(incident.location)], {
        color: isActive ? ROUTE_LINE_ACTIVE : ROUTE_LINE,
        weight: isActive ? 4 : 2,
        opacity: isActive ? 1 : activeAssignment ? 0.2 : 0.6,
        dashArray: '6 4',
        interactive: false,
      }).addTo(layer)
    })

    scenario.resources.forEach((resource) => {
      const isSelected = selected?.kind === 'resource' && selected.entity.id === resource.id
      L.marker(latLng(resource.location), {
        icon: markerIcon('square', resource.available ? RESOURCE_AVAILABLE : RESOURCE_UNAVAILABLE, isSelected, !resource.available),
        title: `Resource ${resource.id}: ${humanize(resource.type)}, ${resource.available ? 'available' : 'unavailable'}`,
        alt: `Resource ${resource.id}`,
      })
        .on('click', () => onSelect({ kind: 'resource', entity: resource }))
        .addTo(layer)
    })

    scenario.incidents.forEach((incident) => {
      const isSelected = selected?.kind === 'incident' && selected.entity.id === incident.id
      L.marker(latLng(incident.location), {
        icon: markerIcon(incident.severity === 'critical' ? 'diamond' : 'circle', SEV_COLOURS[incident.severity], isSelected),
        title: `Incident ${incident.id}: ${humanize(incident.type)}, ${incident.severity} severity`,
        alt: `Incident ${incident.id}`,
        zIndexOffset: 1000,
      })
        .on('click', () => onSelect({ kind: 'incident', entity: incident }))
        .addTo(layer)
    })
  }, [scenario, decision, selected, activeAssignment, onSelect])

  return (
    <div className="relative overflow-hidden border border-ink-300 bg-paper-sunken">
      <div ref={containerRef} className="aspect-[1.28/1] w-full" aria-label="Operational map of incidents and resources" />
      <div className="absolute bottom-6 left-2 z-[1000] flex flex-wrap gap-x-3 gap-y-1 border border-ink-300 bg-paper-raised/95 px-2.5 py-1.5 text-[10px] text-ink-600 shadow-soft">
        <span className="flex items-center gap-1"><span className="inline-block h-2 w-2 rotate-45" style={{ background: SEV_COLOURS.critical }} />Critical</span>
        <span className="flex items-center gap-1"><span className="inline-block h-2 w-2 rounded-full" style={{ background: SEV_COLOURS.high }} />High</span>
        <span className="flex items-center gap-1"><span className="inline-block h-2 w-2 rounded-full" style={{ background: SEV_COLOURS.medium }} />Medium</span>
        <span className="flex items-center gap-1"><span className="inline-block h-2 w-2 rounded-full" style={{ background: SEV_COLOURS.low }} />Low</span>
        <span className="flex items-center gap-1"><span className="inline-block h-2 w-2" style={{ background: RESOURCE_AVAILABLE }} />Resource</span>
        <span>Dashed lines connect a unit to its incident; ETAs follow roads.</span>
      </div>
    </div>
  )
}
