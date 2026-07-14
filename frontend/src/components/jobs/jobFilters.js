// Single source of truth for the Jobs list query contract: the option
// lists the UI renders and the validators that coerce raw URL query values
// into safe, in-range state. Shared by Jobs.vue (which builds the
// useUrlQuerySync schema) and JobFilterBar/JobSortRow (which render the
// controls), so the accepted values and the offered options can never
// drift apart.

export const SORT_OPTIONS = [
  { key: 'created_at', label: '發布日期' },
  { key: 'job_year', label: '求職年月' },
  { key: 'company', label: '公司' },
  { key: 'real_name', label: '名字' },
  { key: 'kind', label: '類型' },
  { key: 'likes', label: '最多愛心' },
]
const ALLOWED_SORTS = SORT_OPTIONS.map((o) => o.key)
const ALLOWED_ORDERS = ['asc', 'desc']

export const KIND_FILTER_OPTIONS = [
  { label: '全部', value: '' },
  { label: '實習', value: 'internship' },
  { label: '正職', value: 'fulltime' },
]
const ALLOWED_KIND_FILTERS = KIND_FILTER_OPTIONS.map((o) => o.value)

export const CURRENT_YEAR = new Date().getFullYear()
export const MIN_JOB_YEAR = 2000
export const YEAR_OPTIONS = (() => {
  const out = []
  for (let y = CURRENT_YEAR; y >= MIN_JOB_YEAR; y--) out.push(y)
  return out
})()

export const COMPANY_FILTER_LIMIT = 10
export const CATEGORY_FILTER_LIMIT = 10

export function safeSort(v) {
  return ALLOWED_SORTS.includes(v) ? v : 'created_at'
}

export function safeOrder(v) {
  return ALLOWED_ORDERS.includes(v) ? v : 'desc'
}

export function safeKind(v) {
  return ALLOWED_KIND_FILTERS.includes(v) ? v : ''
}

export function safeYear(v) {
  if (v === undefined || v === null || v === '') return null
  const n = Number(v)
  if (!Number.isFinite(n)) return null
  if (n < MIN_JOB_YEAR || n > CURRENT_YEAR) return null
  return n
}

// route.query.{company,category} is `string | string[] | undefined` depending
// on how many params the URL carries. Normalize to a deduped array of trimmed
// strings so each select's v-model has a stable shape.
export function safeStringList(v, limit) {
  const raw = v === undefined || v === null ? [] : Array.isArray(v) ? v : [v]
  const out = []
  for (const item of raw) {
    if (typeof item !== 'string') continue
    const trimmed = item.trim()
    if (!trimmed) continue
    if (!out.includes(trimmed)) out.push(trimmed)
    if (out.length >= limit) break
  }
  return out
}
