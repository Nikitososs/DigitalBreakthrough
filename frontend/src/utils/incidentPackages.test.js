import { describe, expect, it } from 'vitest'
import { buildAgencyPackages, isOpenProblem, topicsSimilar } from './incidentPackages'

const mk = (overrides) => ({
  id: '1',
  severity: 2,
  group: 'ЖКХ',
  topic: 'Отопление',
  category: 'Отопление',
  district: 'г. Омск',
  text: 'test',
  agency: { name: 'МинЖКХ', email: 'a@test.ru' },
  outcome: null,
  manually_resolved: false,
  ...overrides,
})

describe('incidentPackages', () => {
  it('excludes resolved and noise', () => {
    expect(isOpenProblem(mk({ severity: 0 }))).toBe(false)
    expect(isOpenProblem(mk({ outcome: 'решено' }))).toBe(false)
    expect(isOpenProblem(mk({ manually_resolved: true }))).toBe(false)
    expect(isOpenProblem(mk())).toBe(true)
  })

  it('merges similar topics', () => {
    expect(topicsSimilar('Отопление', 'отопление в домах')).toBe(true)
  })

  it('groups by agency and theme group', () => {
    const items = [
      mk({ id: '1', severity: 4 }),
      mk({ id: '2', severity: 1, topic: 'Вода' }),
      mk({ id: '3', group: 'Дороги', topic: 'Ямы', agency: { name: 'Минтранс', email: '' } }),
    ]
    const pkgs = buildAgencyPackages(items)
    expect(pkgs).toHaveLength(2)
    expect(pkgs[0].agencyName).toBe('МинЖКХ')
    expect(pkgs[0].total).toBe(2)
  })
})
