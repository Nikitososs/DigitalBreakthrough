import geojsonData from '../data/omsk_boundaries.json'
import { CITY_MARKERS, matchDistrict } from './matchDistrict'

const DEFAULT_CENTER = [54.9893, 73.3682]
const boundsCache = new Map()

function ringCentroid(ring) {
  if (!ring?.length) return null
  let latSum = 0
  let lngSum = 0
  for (const [lng, lat] of ring) {
    latSum += lat
    lngSum += lng
  }
  return [latSum / ring.length, lngSum / ring.length]
}

function geometryCentroid(geometry) {
  if (!geometry) return null
  if (geometry.type === 'Polygon') {
    return ringCentroid(geometry.coordinates?.[0])
  }
  if (geometry.type === 'MultiPolygon') {
    const first = geometry.coordinates?.[0]?.[0]
    return ringCentroid(first)
  }
  return null
}

function geometryBounds(geometry) {
  if (!geometry) return null
  const rings = []
  if (geometry.type === 'Polygon') {
    rings.push(...(geometry.coordinates || []))
  } else if (geometry.type === 'MultiPolygon') {
    for (const polygon of geometry.coordinates || []) {
      rings.push(...polygon)
    }
  }
  let south = Infinity
  let north = -Infinity
  let west = Infinity
  let east = -Infinity
  for (const ring of rings) {
    for (const [lng, lat] of ring) {
      south = Math.min(south, lat)
      north = Math.max(north, lat)
      west = Math.min(west, lng)
      east = Math.max(east, lng)
    }
  }
  if (!Number.isFinite(south)) return null
  return { south, north, west, east }
}

export function getMunicipalityBounds(municipalityName) {
  const name = String(municipalityName || '').trim()
  if (!name) return null

  if (boundsCache.has(name)) return boundsCache.get(name)

  for (const city of CITY_MARKERS) {
    if (city.match(name) && city.bounds) {
      boundsCache.set(name, city.bounds)
      return city.bounds
    }
  }

  const stub = [{ name }]
  for (const feature of geojsonData.features || []) {
    if (matchDistrict(feature.properties?.name, stub)) {
      const bounds = geometryBounds(feature.geometry)
      if (bounds) {
        boundsCache.set(name, bounds)
        return bounds
      }
    }
  }

  return null
}

export function getMunicipalityCoords(municipalityName) {
  const name = String(municipalityName || '').trim()
  if (!name) return DEFAULT_CENTER

  const city = CITY_MARKERS.find((m) => m.match(name))
  if (city) return [city.lat, city.lng]

  const stub = [{ name }]
  for (const feature of geojsonData.features || []) {
    if (matchDistrict(feature.properties?.name, stub)) {
      const c = geometryCentroid(feature.geometry)
      if (c) return c
    }
  }

  return DEFAULT_CENTER
}
