// Wraps Intl.RelativeTimeFormat so callers don't have to pick a unit.
// Accepts a Date, ISO string, or epoch ms — anything `new Date()` understands.
// Returns Traditional Chinese phrases like "剛剛", "5 分鐘前", "3 天前".

const formatter = new Intl.RelativeTimeFormat('zh-TW', { numeric: 'auto' })

const MIN = 60
const HOUR = 60 * MIN
const DAY = 24 * HOUR
const MONTH = 30 * DAY
const YEAR = 365 * DAY

export function relativeTime(date, now = new Date()) {
  const target = date instanceof Date ? date : new Date(date)
  if (Number.isNaN(target.getTime())) return ''

  const seconds = Math.round((target.getTime() - now.getTime()) / 1000)
  const abs = Math.abs(seconds)

  if (abs < 5) return '剛剛'
  if (abs < MIN) return formatter.format(seconds, 'second')
  if (abs < HOUR) return formatter.format(Math.round(seconds / MIN), 'minute')
  if (abs < DAY) return formatter.format(Math.round(seconds / HOUR), 'hour')
  if (abs < MONTH) return formatter.format(Math.round(seconds / DAY), 'day')
  if (abs < YEAR) return formatter.format(Math.round(seconds / MONTH), 'month')
  return formatter.format(Math.round(seconds / YEAR), 'year')
}
