import { useMemo } from 'react'
import { GeoJSON } from 'react-leaflet'
import geojsonData from '../data/omsk_boundaries.json'
import { matchDistrict } from '../utils/matchDistrict'

export default function MunicipalityBoundariesLayer({
  dark = false,
  highlightMunicipality = null,
  interactive = true,
}) {
  const highlight = useMemo(
    () => (highlightMunicipality ? [{ name: highlightMunicipality }] : []),
    [highlightMunicipality],
  )

  const borderColor = dark ? '#94a3b8' : '#64748b'
  const baseFill = dark ? '#1e293b' : '#cbd5e1'

  const styleFeature = (feature) => {
    const osmName = feature.properties?.name || ''
    const isActive = Boolean(highlight.length && matchDistrict(osmName, highlight))
    return {
      fillColor: isActive ? '#dc2626' : baseFill,
      fillOpacity: isActive ? 0.18 : 0.1,
      color: isActive ? '#dc2626' : borderColor,
      weight: isActive ? 2.5 : 1.25,
      opacity: isActive ? 0.95 : 0.75,
    }
  }

  const onEachFeature = (feature, layer) => {
    const osmName = feature.properties?.name || ''
    if (!interactive) return

    const baseStyle = styleFeature(feature)
    layer.bindTooltip(osmName, {
      sticky: true,
      className: dark ? 'leaflet-tooltip--dark' : '',
    })

    layer.on({
      mouseover: (e) => {
        e.target.setStyle({
          fillOpacity: 0.22,
          weight: 2,
          color: dark ? '#f1f5f9' : '#334155',
        })
        e.target.bringToFront()
      },
      mouseout: (e) => e.target.setStyle(baseStyle),
    })
  }

  return (
    <GeoJSON
      key={`${dark ? 'd' : 'l'}-${highlightMunicipality || 'none'}`}
      data={geojsonData}
      style={styleFeature}
      onEachFeature={onEachFeature}
    />
  )
}
