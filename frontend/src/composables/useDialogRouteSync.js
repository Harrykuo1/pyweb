import { ref, watch } from 'vue'

import { safeId } from '../utils/safeId'

// Two-way binding between a `?<queryKey>=<id>` deep-link and a detail
// dialog's open/target state: a deep-link URL fetches the record and opens
// the dialog, and closing the dialog drops the key from the URL while
// preserving every other query param. `fetchItem(id)` does the lookup;
// failures (e.g. a 404 for a deleted record) are swallowed so the
// still-usable list isn't interrupted by a toast.
export function useDialogRouteSync({
  route,
  router,
  queryKey = 'detail',
  fetchItem,
  validateId = safeId,
}) {
  const open = ref(false)
  const item = ref(null)

  function show(loaded) {
    item.value = loaded
    open.value = true
  }

  async function openById(id) {
    try {
      show(await fetchItem(id))
    } catch {
      // Deleted/invalid record — fail silently.
    }
  }

  watch(
    () => route.query[queryKey],
    (val) => {
      const id = validateId(val)
      if (id === null) return
      // Skip if the dialog is already showing this exact record — avoids a
      // redundant fetch when the watcher fires because a URL rewrite
      // re-emitted the same value.
      if (open.value && item.value?.id === id) return
      openById(id)
    },
    { immediate: true },
  )

  watch(open, (val) => {
    if (val) return
    if (route.query[queryKey] === undefined) return
    const next = { ...route.query }
    delete next[queryKey]
    router.replace({ query: next })
  })

  return { open, item, show }
}
