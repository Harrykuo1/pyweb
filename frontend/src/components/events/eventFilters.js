// Single source of truth for the Events list query contract: the option
// lists the filter UI renders and the validators that coerce raw URL query
// values into safe, in-range state. Shared by Events.vue (which builds the
// useUrlQuerySync schema) and the filter controls. Mirrors jobFilters.js.

export const CURRENT_YEAR = new Date().getFullYear()
export const MIN_YEAR = 2000
export const YEAR_OPTIONS = (() => {
  const out = []
  for (let y = CURRENT_YEAR; y >= MIN_YEAR; y--) out.push(y)
  return out
})()

export const TAG_FILTER_LIMIT = 20

export function safeOrder(v) {
  return v === 'asc' ? 'asc' : 'desc'
}

export function safeYear(v) {
  if (v === undefined || v === null || v === '') return null
  const n = Number(v)
  if (!Number.isFinite(n) || n < MIN_YEAR || n > CURRENT_YEAR) return null
  return n
}

export function safeStringList(v, limit) {
  const raw = v === undefined || v === null ? [] : Array.isArray(v) ? v : [v]
  const out = []
  for (const item of raw) {
    if (typeof item !== 'string') continue
    const trimmed = item.trim()
    if (!trimmed || out.includes(trimmed)) continue
    out.push(trimmed)
    if (out.length >= limit) break
  }
  return out
}
