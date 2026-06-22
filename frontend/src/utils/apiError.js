// Pull a human-readable message out of an axios error's response body.
// The backend returns { detail: "..." } for most 4xx; fall back to the
// caller's generic message otherwise. Shared by the composables that show
// a toast on a failed mutation.
export function extractError(err, fallback) {
  const detail = err?.response?.data?.detail
  if (typeof detail === 'string') return detail
  return fallback
}
