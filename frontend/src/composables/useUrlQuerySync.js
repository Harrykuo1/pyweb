import { onUnmounted, reactive, toRefs, watch } from 'vue'

// Two-way bridge between a set of filter fields and the URL query string.
// The composable owns the *mechanism* — reading initial values out of the
// URL, writing changes back (stripping defaults), preserving foreign keys
// it doesn't own, and debouncing the fields that ask for it — while the
// caller supplies the *domain* via a per-field schema:
//
//   fields: {
//     <stateName>: {
//       queryKey?: string,        // URL param name; defaults to stateName
//       parse: (rawQueryValue) => value,
//       serialize: (value) => queryValue | undefined,   // undefined ⇒ omit
//       debounce?: number,        // ms; field gets its own debounced watch
//     },
//   }
//
// `preserveKeys` are query params owned by something else (e.g. a detail
// deep-link) that must survive every filter rewrite. `onChange` fires
// after each sync so the caller can refetch.
export function useUrlQuerySync({
  route,
  router,
  fields,
  preserveKeys = [],
  onChange,
}) {
  const entries = Object.entries(fields)
  const queryKeyOf = (name) => fields[name].queryKey ?? name

  const state = reactive({})
  for (const [name, cfg] of entries) {
    state[name] = cfg.parse(route.query[queryKeyOf(name)])
  }

  function syncUrl() {
    const query = {}
    for (const [name, cfg] of entries) {
      const serialized = cfg.serialize(state[name])
      if (serialized !== undefined) query[queryKeyOf(name)] = serialized
    }
    for (const key of preserveKeys) {
      if (route.query[key] !== undefined) query[key] = route.query[key]
    }
    router.replace({ query })
  }

  function fire() {
    syncUrl()
    onChange?.()
  }

  // Fields without a debounce share one immediate watch; debounced fields
  // each get their own timer so a burst on one doesn't reset the others.
  const immediate = entries.filter(([, cfg]) => !cfg.debounce).map(([n]) => n)
  const debounced = entries.filter(([, cfg]) => cfg.debounce)

  if (immediate.length > 0) {
    watch(
      immediate.map((n) => () => state[n]),
      fire,
      { deep: true },
    )
  }

  const timers = {}
  for (const [name, cfg] of debounced) {
    watch(
      () => state[name],
      () => {
        if (timers[name]) clearTimeout(timers[name])
        timers[name] = setTimeout(() => {
          timers[name] = null
          fire()
        }, cfg.debounce)
      },
    )
  }

  onUnmounted(() => {
    for (const t of Object.values(timers)) if (t) clearTimeout(t)
  })

  return toRefs(state)
}
