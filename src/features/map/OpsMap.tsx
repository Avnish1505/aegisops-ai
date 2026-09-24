import type { Layer, PickingInfo } from '@deck.gl/core'
import { IconLayer, PathLayer, PolygonLayer, ScatterplotLayer, TextLayer } from '@deck.gl/layers'
import type { MapboxOverlay } from '@deck.gl/mapbox'
import type { Map as MapLibreMap, StyleSpecification } from 'maplibre-gl'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useAlerts, useRoutes } from '../../api/queries'
import { THEMES, rgb } from '../../design/tokens'
import { SEVERITY_TEXT } from '../../components/ui/SeverityGlyph'
import { useResolvedTheme } from '../../lib/theme'
import type { Incident, Resource } from '../../types'
import type { MapSlotProps } from '../ops/OpsBoard'
import { ICON_MAPPING, iconAtlas, type IconName } from './icons'

/** Keyless OpenStreetMap vector tiles from OpenFreeMap, shown in greyscale (see index.css). */
const TILE_STYLE = {
  dark: 'https://tiles.openfreemap.org/styles/dark',
  light: 'https://tiles.openfreemap.org/styles/positron',
}

/** VITE_MAP_STYLE=blank draws no basemap (end-to-end tests run without tile servers). */
function mapStyle(theme: 'dark' | 'light'): string | StyleSpecification {
  if (import.meta.env.VITE_MAP_STYLE !== 'blank') return TILE_STYLE[theme]
  return {
    version: 8,
    sources: {},
    layers: [{ id: 'background', type: 'background', paint: { 'background-color': THEMES[theme].surface } }],
  }
}

type Picked = { kind: 'incident'; incident: Incident } | { kind: 'unit'; unit: Resource }

function bounds(points: { lat: number; lon: number }[]): [[number, number], [number, number]] {
  const lons = points.map((p) => p.lon)
  const lats = points.map((p) => p.lat)
  return [
    [Math.min(...lons), Math.min(...lats)],
    [Math.max(...lons), Math.max(...lats)],
  ]
}

export default function OpsMap({ scenario, plan, labels, selectedId, onSelect }: MapSlotProps) {
  const container = useRef<HTMLDivElement>(null)
  const map = useRef<MapLibreMap | null>(null)
  const overlay = useRef<MapboxOverlay | null>(null)
  const [ready, setReady] = useState(false)
  const [failure, setFailure] = useState<string | null>(null)
  const theme = useResolvedTheme()
  const colours = THEMES[theme]
  const routes = useRoutes(plan?.decision_id).data
  const alerts = useAlerts().data
  const atlas = useMemo(() => (typeof document === 'undefined' ? undefined : iconAtlas()), [])

  // Create the map once; tear it down on unmount.
  useEffect(() => {
    let cancelled = false
    let created: MapLibreMap | null = null
    ;(async () => {
      try {
        const [maplibre, { MapboxOverlay: Overlay }, { default: workerUrl }] = await Promise.all([
          import('maplibre-gl'),
          import('@deck.gl/mapbox'),
          // Vite bundles the worker (and the chunk it imports); MapLibre's own lookup uses a
          // computed URL that the bundler cannot follow.
          import('maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'),
          import('maplibre-gl/dist/maplibre-gl.css'),
        ])
        maplibre.setWorkerUrl(workerUrl)
        if (cancelled || !container.current) return
        const instance = new maplibre.Map({
          container: container.current,
          style: mapStyle(theme),
          bounds: bounds([...scenario.incidents.map((i) => i.location), ...scenario.resources.map((r) => r.location)]),
          fitBoundsOptions: { padding: 48 },
          // The tile source supplies the OpenFreeMap / OpenMapTiles / OpenStreetMap attribution.
          attributionControl: { compact: false },
          dragRotate: false,
          pitchWithRotate: false,
        })
        created = instance
        instance.touchZoomRotate.disableRotation()
        instance.addControl(new maplibre.NavigationControl({ showCompass: false }), 'top-right')
        instance.addControl(new maplibre.ScaleControl({ unit: 'metric' }), 'bottom-left')
        const deck = new Overlay({ interleaved: false, layers: [] })
        instance.addControl(deck)
        map.current = instance
        overlay.current = deck
        instance.on('load', () => !cancelled && setReady(true))
      } catch (error) {
        if (!cancelled) setFailure(error instanceof Error ? error.message : 'Map could not start.')
      }
    })()
    return () => {
      cancelled = true
      created?.remove()
      map.current = null
      overlay.current = null
    }
    // The map is created once per scenario; theme changes swap the style below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scenario.scenario_id])

  useEffect(() => {
    if (ready) map.current?.setStyle(mapStyle(theme))
  }, [theme, ready])

  const layers = useMemo((): Layer[] => {
    if (!atlas) return []
    const assigned = new Set(plan?.assignments.map((a) => a.resource_id))
    const selectedRoutes = new Set(routes?.filter((r) => r.incident_id === selectedId).map((r) => r.resource_id))
    const alertPolygons = (alerts ?? []).flatMap((alert) =>
      alert.areas.flatMap((area) => area.polygons.map((ring) => ({ alert, ring: ring.map(([lat, lon]) => [lon, lat]) }))),
    )
    const alertCircles = (alerts ?? []).flatMap((alert) =>
      alert.areas.flatMap((area) => area.circles.map(([lat, lon, km]) => ({ alert, lat, lon, km }))),
    )
    const severityColour = (incident: Incident): [number, number, number] =>
      incident.severity === 'critical' ? rgb(colours.critical) : incident.severity === 'high' ? rgb(colours.high) : rgb(colours.muted)
    const selected = scenario.incidents.find((i) => i.id === selectedId)

    return [
      new PolygonLayer({
        id: 'alert-areas',
        data: alertPolygons,
        getPolygon: (d) => d.ring,
        getFillColor: [...rgb(colours.high), 28],
        getLineColor: [...rgb(colours.high), 200],
        lineWidthMinPixels: 1.5,
        stroked: true,
      }),
      new ScatterplotLayer({
        id: 'alert-circles',
        data: alertCircles,
        getPosition: (d) => [d.lon, d.lat],
        getRadius: (d) => d.km * 1000,
        getFillColor: [...rgb(colours.high), 28],
        getLineColor: [...rgb(colours.high), 200],
        stroked: true,
        lineWidthMinPixels: 1.5,
      }),
      new PathLayer({
        id: 'routes',
        data: routes ?? [],
        getPath: (d) => d.coordinates,
        // Road routes are normal (grey); a straight-line fallback is abnormal (amber).
        getColor: (d) => (d.geometry === 'straight_line' ? rgb(colours.high) : rgb(selectedRoutes.has(d.resource_id) && d.incident_id === selectedId ? colours.text : colours.muted)),
        getWidth: (d) => (d.incident_id === selectedId ? 4 : 2),
        widthUnits: 'pixels',
        updateTriggers: { getColor: [selectedId, theme], getWidth: [selectedId] },
      }),
      new IconLayer<Resource>({
        id: 'units',
        data: scenario.resources,
        iconAtlas: atlas as unknown as string,
        iconMapping: ICON_MAPPING,
        getIcon: (d): IconName => (d.available ? 'unit' : 'unit-unavailable'),
        getPosition: (d) => [d.location.lon, d.location.lat],
        getSize: 12,
        getColor: (d) => (assigned.has(d.id) ? rgb(colours.text) : rgb(colours.muted)),
        pickable: true,
        updateTriggers: { getColor: [plan?.decision_id, theme] },
      }),
      new ScatterplotLayer<Incident>({
        id: 'selected-ring',
        data: selected ? [selected] : [],
        getPosition: (d) => [d.location.lon, d.location.lat],
        getRadius: 16,
        radiusUnits: 'pixels',
        filled: false,
        stroked: true,
        getLineColor: rgb(colours.focus),
        lineWidthMinPixels: 3,
      }),
      new IconLayer<Incident>({
        id: 'incidents',
        data: scenario.incidents,
        iconAtlas: atlas as unknown as string,
        iconMapping: ICON_MAPPING,
        getIcon: (d): IconName => d.severity,
        getPosition: (d) => [d.location.lon, d.location.lat],
        getSize: (d) => (d.id === selectedId ? 26 : 20),
        getColor: severityColour,
        pickable: true,
        updateTriggers: { getSize: [selectedId], getColor: [theme] },
      }),
      new TextLayer<Incident>({
        id: 'selected-label',
        data: selected ? [selected] : [],
        getPosition: (d) => [d.location.lon, d.location.lat],
        getText: (d) => labels?.incidents[d.id] ?? d.id,
        getSize: 13,
        getPixelOffset: [0, -22],
        getColor: rgb(colours.text),
        background: true,
        getBackgroundColor: rgb(colours.surface),
        backgroundPadding: [4, 2],
        fontFamily: '"IBM Plex Sans", sans-serif',
      }),
    ]
  }, [alerts, atlas, colours, labels, plan, routes, scenario, selectedId, theme])

  useEffect(() => {
    overlay.current?.setProps({
      layers,
      onClick: (info: PickingInfo) => {
        if (info.layer?.id === 'incidents' && info.object) onSelect((info.object as Incident).id)
      },
      getTooltip: ({ object, layer }: PickingInfo) => {
        if (!object || !layer) return null
        const picked: Picked | null =
          layer.id === 'incidents' ? { kind: 'incident', incident: object as Incident } : layer.id === 'units' ? { kind: 'unit', unit: object as Resource } : null
        if (!picked) return null
        const text =
          picked.kind === 'incident'
            ? `${labels?.incidents[picked.incident.id] ?? 'Unnamed'} · ${picked.incident.id} · ${SEVERITY_TEXT[picked.incident.severity]}`
            : `${labels?.units[picked.unit.id] ?? 'Unit'} · ${picked.unit.id}${picked.unit.available ? '' : ' · unavailable'}`
        return { text, style: { background: colours.raised, color: colours.text, font: '12px "IBM Plex Sans", sans-serif', padding: '4px 6px', border: `1px solid ${colours.divider}` } }
      },
    })
  }, [layers, labels, colours, ready, onSelect])

  return (
    <section aria-labelledby="map-title" className="relative h-full border border-divider bg-surface">
      <h2 id="map-title" className="sr-only">
        Map of incidents, units, routes and alert areas. The incident list has the same information for keyboard use.
      </h2>
      {failure ? (
        <p className="p-3 text-muted">Map unavailable: {failure}</p>
      ) : (
        <div ref={container} className="aegis-map h-full w-full" />
      )}
      <MapLegend />
    </section>
  )
}

function MapLegend() {
  return (
    <div className="pointer-events-none absolute left-2 top-2 flex gap-3 border border-divider bg-surface/90 px-2 py-1 text-xs text-muted">
      <span><span className="text-critical">◆</span> critical</span>
      <span><span className="text-high">▲</span> high</span>
      <span>● medium / ○ low</span>
      <span>■ unit / □ unavailable</span>
      <span><span className="text-high">▭</span> alert area</span>
    </div>
  )
}
