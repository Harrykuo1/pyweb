import { describe, expect, it } from 'vitest'
import { ref } from 'vue'

import { useMemberFiltering } from './useMemberFiltering'

const sample = [
  { real_name: 'Alice', institution: 'NTU', position: 'SWE', graduation_year: 2022, joined_at: '2022-01-01' },
  { real_name: 'Bob', institution: 'NCKU', position: 'PM', graduation_year: 2020, joined_at: '2020-05-01' },
  { real_name: 'Carol', institution: 'NTU', position: 'Designer', graduation_year: 2024, joined_at: '2024-03-01' },
]

describe('useMemberFiltering', () => {
  it('returns all members when the search is empty', () => {
    const f = useMemberFiltering(ref(sample))
    expect(f.filteredMembers.value).toHaveLength(3)
    expect(f.memberCount.value).toBe(3)
    expect(f.filteredCount.value).toBe(3)
  })

  it('filters by the boolean search across name/school/position/year', () => {
    const f = useMemberFiltering(ref(sample))
    f.searchQuery.value = 'NTU'
    expect(f.filteredMembers.value.map((m) => m.real_name)).toEqual([
      'Alice',
      'Carol',
    ])
    f.searchQuery.value = '2020'
    expect(f.filteredMembers.value.map((m) => m.real_name)).toEqual(['Bob'])
  })

  it('supports negation', () => {
    const f = useMemberFiltering(ref(sample))
    f.searchQuery.value = 'NTU -Designer'
    expect(f.filteredMembers.value.map((m) => m.real_name)).toEqual(['Alice'])
  })

  it('sorts the grid list by the active key and direction', () => {
    const f = useMemberFiltering(ref(sample))
    f.sortKey.value = 'graduation_year'
    f.sortOrder.value = 'asc'
    expect(f.sortedMembers.value.map((m) => m.graduation_year)).toEqual([
      2020, 2022, 2024,
    ])
    f.sortOrder.value = 'desc'
    expect(f.sortedMembers.value.map((m) => m.graduation_year)).toEqual([
      2024, 2022, 2020,
    ])
  })

  it('toggleSort flips direction on the same key, resets to asc on a new key', () => {
    const f = useMemberFiltering(ref(sample))
    expect(f.sortKey.value).toBe('joined_at')
    f.toggleSort('joined_at')
    expect(f.sortOrder.value).toBe('desc')
    f.toggleSort('real_name')
    expect(f.sortKey.value).toBe('real_name')
    expect(f.sortOrder.value).toBe('asc')
  })

  it('filteredCount tracks the search while memberCount stays the total', () => {
    const f = useMemberFiltering(ref(sample))
    f.searchQuery.value = 'NTU'
    expect(f.filteredCount.value).toBe(2)
    expect(f.memberCount.value).toBe(3)
  })
})
