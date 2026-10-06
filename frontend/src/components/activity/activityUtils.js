export function localToday(timezone = 'Asia/Taipei', now = new Date()) {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: timezone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(now)
  const part = (type) => parts.find((p) => p.type === type).value
  return `${part('year')}-${part('month')}-${part('day')}`
}

export function shiftDate(date, days) {
  const value = new Date(`${date}T12:00:00Z`)
  value.setUTCDate(value.getUTCDate() + days)
  return value.toISOString().slice(0, 10)
}

export function defaultFilters() {
  const end = localToday()
  return {
    start_date: shiftDate(end, -364),
    end_date: end,
    timezone: 'Asia/Taipei',
    hour_start: 0,
    hour_end: 24,
    weekdays: [],
    user_ids: [],
    channel_ids: [],
  }
}

export function parseFilters(query) {
  const defaults = defaultFilters()
  const list = (key) =>
    query[key] == null ? [] : [query[key]].flat().map(String)
  const scalar = (key) => [query[key]].flat()[0]
  return {
    ...defaults,
    start_date: scalar('start_date') || defaults.start_date,
    end_date: scalar('end_date') || defaults.end_date,
    timezone: scalar('timezone') || defaults.timezone,
    hour_start: query.hour_start == null ? 0 : Number(scalar('hour_start')),
    hour_end: query.hour_end == null ? 24 : Number(scalar('hour_end')),
    weekdays: list('weekdays').map(Number),
    user_ids: list('user_ids'),
    channel_ids: list('channel_ids'),
  }
}

export function filterError(filters) {
  const days =
    (Date.parse(filters.end_date) - Date.parse(filters.start_date)) / 86400000
  if (
    !/^\d{4}-\d{2}-\d{2}$/.test(filters.start_date) ||
    !/^\d{4}-\d{2}-\d{2}$/.test(filters.end_date) ||
    !Number.isFinite(days) ||
    new Date(filters.start_date).toISOString().slice(0, 10) !==
      filters.start_date ||
    new Date(filters.end_date).toISOString().slice(0, 10) !==
      filters.end_date ||
    days < 0 ||
    days > 365
  )
    return '請選擇 1 至 366 天的日期範圍。'
  try {
    new Intl.DateTimeFormat('en', { timeZone: filters.timezone }).format()
  } catch {
    return '請選擇有效的時區。'
  }
  if (
    !Number.isInteger(filters.hour_start) ||
    !Number.isInteger(filters.hour_end) ||
    filters.hour_start < 0 ||
    filters.hour_start > 23 ||
    filters.hour_end < 1 ||
    filters.hour_end > 24 ||
    filters.hour_start === filters.hour_end
  )
    return '請選擇有效的每日時段，起訖時間不能相同。'
  if (filters.weekdays.some((d) => !Number.isInteger(d) || d < 0 || d > 6))
    return '請選擇有效的星期。'
  if (
    [filters.user_ids, filters.channel_ids].some(
      (ids) => ids.length > 50 || ids.some((id) => !/^\d{1,20}$/.test(id)),
    )
  )
    return '成員或頻道條件格式不正確。'
  return ''
}

export function calendarCells(daily) {
  if (!daily.length) return []
  const offset = (new Date(`${daily[0].date}T12:00:00Z`).getUTCDay() + 6) % 7
  const cells = [...Array(offset).fill(null), ...daily]
  while (cells.length % 7) cells.push(null)
  return cells
}

export function longestStreak(daily, metric) {
  let longest = 0
  let current = 0
  for (const day of daily) {
    current = day[metric] > 0 ? current + 1 : 0
    longest = Math.max(longest, current)
  }
  return longest
}

export function intensity(value, maximum) {
  if (!value || !maximum) return 0
  return Math.min(4, Math.max(1, Math.ceil((value / maximum) * 4)))
}

export const number = (value) =>
  new Intl.NumberFormat('zh-TW', { maximumFractionDigits: 1 }).format(
    value || 0,
  )
export const hourLabel = (hour) => `${String(hour).padStart(2, '0')}:00`
