// Coerce a route-query value into a positive integer id, or null. Arrays
// (from a duplicated ?key=A&key=B), NaN, and non-positive values all drop
// to null so a malformed URL no-ops instead of crashing a fetch. Shared by
// the deep-link composables (useDialogRouteSync, useDeepLinkFocus).
export function safeId(v) {
  if (Array.isArray(v)) v = v[0]
  if (v === undefined || v === null || v === '') return null
  const n = Number(v)
  return Number.isInteger(n) && n > 0 ? n : null
}
