import { computed, ref } from 'vue'

import { matchHaystack, parseQuery } from '../utils/searchQuery'

// Client-side filtering + sorting for the members list. Search is a
// boolean query (implicit AND, uppercase OR, -/NOT negation, "quoted
// phrases") across name / school / position / graduation year, matching
// the Jobs backend search syntax. Sorting cycles asc <-> desc per key.
// Takes the members ref and derives filteredMembers (for the el-table,
// which sorts itself) and sortedMembers (for the grid, sorted here).
export function useMemberFiltering(members) {
  const sortKey = ref('joined_at')
  const sortOrder = ref('asc')

  function toggleSort(key) {
    if (sortKey.value === key) {
      sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc'
    } else {
      sortKey.value = key
      sortOrder.value = 'asc'
    }
  }

  const searchQuery = ref('')

  const filteredMembers = computed(() => {
    const parsed = parseQuery(searchQuery.value)
    if (parsed.length === 0) return members.value
    return members.value.filter((m) => {
      const haystack = [
        m.real_name,
        m.institution,
        m.position,
        String(m.graduation_year ?? ''),
      ]
        .filter(Boolean)
        .join(' ')
      return matchHaystack(parsed, haystack)
    })
  })

  const sortedMembers = computed(() => {
    const arr = [...filteredMembers.value]
    const k = sortKey.value
    const dir = sortOrder.value === 'asc' ? 1 : -1
    arr.sort((a, b) => {
      const av = a[k]
      const bv = b[k]
      if (typeof av === 'number' && typeof bv === 'number') {
        return (av - bv) * dir
      }
      return String(av ?? '').localeCompare(String(bv ?? ''), 'zh-Hant') * dir
    })
    return arr
  })

  const memberCount = computed(() => members.value.length)
  const filteredCount = computed(() => filteredMembers.value.length)

  return {
    sortKey,
    sortOrder,
    toggleSort,
    searchQuery,
    filteredMembers,
    sortedMembers,
    memberCount,
    filteredCount,
  }
}
