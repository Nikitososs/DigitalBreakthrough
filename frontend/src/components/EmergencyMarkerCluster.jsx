import { Marker, Popup } from 'react-leaflet'
import MarkerClusterGroup from 'react-leaflet-cluster'
import L from 'leaflet'
import 'react-leaflet-cluster/lib/assets/MarkerCluster.css'
import 'react-leaflet-cluster/lib/assets/MarkerCluster.Default.css'

const CLUSTER_DISABLE_ZOOM = 15
const MAX_RENDERED_MARKERS = 4000

function clusterIcon(cluster) {
  const count = cluster.getChildCount()
  const size = count > 99 ? 48 : count > 9 ? 42 : 36
  const fontSize = count > 99 ? 13 : count > 9 ? 14 : 15
  return L.divIcon({
    html: `<div class="emergency-cluster" style="width:${size}px;height:${size}px;font-size:${fontSize}px"><span>${count}</span></div>`,
    className: 'emergency-cluster-icon',
    iconSize: L.point(size, size),
    iconAnchor: L.point(size / 2, size / 2),
  })
}

export default function EmergencyMarkerCluster({
  markers,
  activeId,
  createIcon,
  renderPopup,
  onSelect,
}) {
  const visible = markers.length > MAX_RENDERED_MARKERS
    ? markers
      .slice()
      .sort((a, b) => {
        if (a.id === activeId) return -1
        if (b.id === activeId) return 1
        return (b.severity ?? 0) - (a.severity ?? 0)
      })
      .slice(0, MAX_RENDERED_MARKERS)
    : markers

  return (
    <MarkerClusterGroup
      chunkedLoading
      chunkInterval={80}
      chunkDelay={20}
      spiderfyOnMaxZoom
      showCoverageOnHover={false}
      zoomToBoundsOnClick
      disableClusteringAtZoom={CLUSTER_DISABLE_ZOOM}
      maxClusterRadius={70}
      iconCreateFunction={clusterIcon}
    >
      {visible.map((pin) => {
        const isActive = pin.id === activeId
        return (
          <Marker
            key={pin.id}
            position={pin.coords}
            icon={createIcon(pin.color, {
              active: isActive,
              geocoded: pin.geocoded,
              severity: pin.severity,
            })}
            zIndexOffset={isActive ? 1000 : pin.severity * 10}
            eventHandlers={{
              click: () => onSelect(pin.source),
            }}
          >
            <Popup
              className="emergency-popup"
              minWidth={300}
              maxWidth={340}
              autoPan
              autoPanPadding={[40, 40]}
            >
              {renderPopup(pin)}
            </Popup>
          </Marker>
        )
      })}
    </MarkerClusterGroup>
  )
}
