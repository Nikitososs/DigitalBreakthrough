import { useEffect } from 'react'
import { MapContainer, TileLayer, GeoJSON, CircleMarker, Tooltip, useMap } from 'react-leaflet'
import MarkerClusterGroup from 'react-leaflet-cluster'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import 'react-leaflet-cluster/lib/assets/MarkerCluster.css'
import 'react-leaflet-cluster/lib/assets/MarkerCluster.Default.css'
import geojsonData from '../data/omsk_boundaries.json'
import { matchDistrict, findCityMarkerDistrict } from '../utils/matchDistrict'
import { mapTileLayer } from '../utils/mapTiles'
import { scoreColor as scoreToColor } from '../utils/scoreColor'
import { SEVERITY_COLORS } from '../utils/incidentModel'

const BOUNDS = L.latLngBounds([[52.5, 68.0], [59.5, 78.0]])
const MIN_ZOOM = 6.5

function MapConstraints() {
  const map = useMap()
  useEffect(() => {
    map.setMinZoom(MIN_ZOOM)
    map.setMaxBounds(BOUNDS)
    map.options.bounceAtZoomLimits = false
    const clampZoom = () => {
      if (map.getZoom() < MIN_ZOOM) map.setZoom(MIN_ZOOM, { animate: false })
    }
    map.on('zoom', clampZoom)
    map.on('zoomend', clampZoom)
    return () => { map.off('zoom', clampZoom); map.off('zoomend', clampZoom) }
  }, [map])
  return null
}

// Сопоставление OSM ↔ муниципалитет из API (см. utils/matchDistrict.js)

export default function OmskMap({ districts, livePins = [], onDistrictClick, showTiles = true, dark = false }) {
  const cityMarker = findCityMarkerDistrict(districts)
  const mapKey = districts.map((d) => `${d.id}:${d.score ?? 'x'}`).join('|')
  const tiles = mapTileLayer(dark)
  const borderColor = dark ? '#cbd5e1' : '#475569'
  const baseFillOpacity = showTiles ? 0.42 : 0.5
  const hoverFillOpacity = showTiles ? 0.58 : 0.7

  const styleFeature = (feature) => {
    const district = matchDistrict(feature.properties?.name, districts)
    return {
      fillColor: scoreToColor(district?.score),
      fillOpacity: baseFillOpacity,
      color: borderColor,
      weight: showTiles ? 1.5 : 1,
      opacity: showTiles ? 0.9 : 1,
    }
  }

  const onEachFeature = (feature, layer) => {
    const osmName = feature.properties?.name || ''
    const district = matchDistrict(osmName, districts)
    const label = district
      ? (district.mapLabel
        || (district.trend_pct != null
          ? `${district.name} · тренд ${district.trend_pct > 0 ? '+' : ''}${district.trend_pct}%`
            + (district.forecast_next_week != null ? ` · ~${Math.round(district.forecast_next_week)}/нед` : '')
            + (district.risk_level ? ` · ${district.risk_level}` : '')
          : `${district.name} · скор ${district.score}`))
      : `${osmName} · нет данных`

    layer.bindTooltip(label, { sticky: true })

    const baseStyle = styleFeature(feature)

    layer.on({
      mouseover: (e) => e.target.setStyle({
        fillOpacity: hoverFillOpacity,
        weight: 2.5,
        color: dark ? '#f8fafc' : '#1e293b',
      }),
      mouseout: (e) => e.target.setStyle(baseStyle),
      click: () => district && onDistrictClick(district),
    })
  }

  return (
    <MapContainer
      center={[55.8, 73.2]}
      zoom={6}
      zoomAnimation={true}
      maxBounds={BOUNDS}
      maxBoundsViscosity={3.0}
      bounceAtZoomLimits={false}
      inertia={false}
      className={dark ? 'leaflet-map--dark' : 'leaflet-map--light'}
      style={{ height: '100%', width: '100%' }}
      zoomControl
    >
      <MapConstraints />
      {showTiles && (
        <TileLayer url={tiles.url} attribution={tiles.attribution} />
      )}

      <GeoJSON
        key={mapKey || 'empty'}
        data={geojsonData}
        style={styleFeature}
        onEachFeature={onEachFeature}
      />

      {cityMarker && (
        <CircleMarker
          center={[cityMarker.lat, cityMarker.lng]}
          radius={14}
          pathOptions={{
            color: '#7f1d1d',
            weight: 2,
            fillColor: scoreToColor(cityMarker.district.score),
            fillOpacity: 0.85,
          }}
          eventHandlers={{
            click: () => onDistrictClick?.(cityMarker.district),
          }}
        >
          <Tooltip sticky>
            {cityMarker.district.mapLabel
              || (cityMarker.district.trend_pct != null
                ? `${cityMarker.district.name} · тренд ${cityMarker.district.trend_pct > 0 ? '+' : ''}${cityMarker.district.trend_pct}%`
                  + (cityMarker.district.forecast_next_week != null ? ` · ~${Math.round(cityMarker.district.forecast_next_week)}/нед` : '')
                : `${cityMarker.district.name} · скор ${cityMarker.district.score}`)}
          </Tooltip>
        </CircleMarker>
      )}

      {livePins.length > 0 && (
        <MarkerClusterGroup
          chunkedLoading
          chunkInterval={120}
          chunkDelay={30}
          spiderfyOnMaxZoom
          showCoverageOnHover={false}
          zoomToBoundsOnClick
          disableClusteringAtZoom={12}
          maxClusterRadius={55}
        >
          {livePins.map((pin) => {
            const color = SEVERITY_COLORS[pin.severity] || '#16a34a'
            const label = pin.label || pin.topic || 'Live'
            const preview = String(pin.text || '').slice(0, 120)
            return (
              <CircleMarker
                key={pin.id}
                center={[Number(pin.lat), Number(pin.lng)]}
                radius={9}
                pathOptions={{
                  color: '#fff',
                  weight: 2,
                  fillColor: color,
                  fillOpacity: 0.92,
                }}
              >
                <Tooltip sticky>
                  <span className="font-semibold">{label}</span>
                  {pin.municipality && <span> · {pin.municipality}</span>}
                  {preview && (
                    <>
                      <br />
                      <span>{preview}</span>
                    </>
                  )}
                </Tooltip>
              </CircleMarker>
            )
          })}
        </MarkerClusterGroup>
      )}
    </MapContainer>
  )
}
