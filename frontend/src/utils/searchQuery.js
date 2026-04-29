/**
 * Boolean search query parser (Google-style precedence).
 *
 * Mirror of backend/app/core/search_query.py — the parse semantics and
 * test case tables must stay in lockstep. Output is an array of AND-groups
 * (each group is an array of { text, negate } terms), combined with OR.
 *
 * Supported syntax:
 *   - Implicit AND between terms: `react vue` requires both
 *   - Uppercase OR (low precedence): `a b OR c d` = (a AND b) OR (c AND d)
 *   - Negation via `-prefix` or uppercase NOT keyword
 *   - Quoted phrases preserve internal whitespace: `"team lead"`
 *
 * `parseQuery()` is pure. `matchHaystack()` evaluates the IR against a
 * single concatenated haystack string (case-insensitive substring) —
 * that's how the Members surface filters client-side, which differs from
 * the backend's per-column ILIKE in that phrases can match across
 * concatenated field boundaries. We accept the leak: Members is small,
 * the haystack-join behavior predates this parser, and matching it keeps
 * the search UX consistent for users.
 */

export function parseQuery(q) {
  if (!q || !q.trim()) return []

  const tokens = tokenize(q)
  const groups = [[]]
  let pendingNot = false

  for (const { text, isPhrase, negPrefix } of tokens) {
    if (!isPhrase && !negPrefix && text === 'OR') {
      if (groups[groups.length - 1].length > 0) groups.push([])
      pendingNot = false
      continue
    }
    if (!isPhrase && !negPrefix && text === 'NOT') {
      pendingNot = true
      continue
    }
    const negate = negPrefix || pendingNot
    pendingNot = false
    groups[groups.length - 1].push({ text, negate })
  }

  return groups.filter((g) => g.length > 0)
}

function tokenize(q) {
  const tokens = []
  const n = q.length
  let i = 0
  while (i < n) {
    const c = q[i]
    if (/\s/.test(c)) {
      i++
      continue
    }
    let negate = false
    if (c === '-') {
      // Dash only attaches as a negation prefix when the next char is
      // part of a token (no whitespace). Lone `-` and `- foo` drop the dash.
      if (i + 1 < n && !/\s/.test(q[i + 1])) {
        negate = true
        i++
      } else {
        i++
        continue
      }
    }
    const head = q[i]
    if (head === '"') {
      let j = i + 1
      while (j < n && q[j] !== '"') j++
      const text = q.slice(i + 1, j)
      if (text) tokens.push({ text, isPhrase: true, negPrefix: negate })
      i = j < n ? j + 1 : n
    } else {
      let j = i
      while (j < n && !/\s/.test(q[j]) && q[j] !== '"') j++
      const text = q.slice(i, j)
      if (text) tokens.push({ text, isPhrase: false, negPrefix: negate })
      i = j
    }
  }
  return tokens
}

export function matchHaystack(parsed, haystack) {
  if (!parsed || parsed.length === 0) return true
  const hay = String(haystack ?? '').toLowerCase()
  return parsed.some((group) =>
    group.every((term) => {
      const hit = hay.includes(term.text.toLowerCase())
      return term.negate ? !hit : hit
    }),
  )
}
