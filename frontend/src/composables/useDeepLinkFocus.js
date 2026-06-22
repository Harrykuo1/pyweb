import { nextTick, ref, watch } from 'vue'

import { safeId } from '../utils/safeId'

// "Scroll to and flash" a row from a `?<queryKey>=<id>` deep-link. Calling
// consume() reads the id, strips the key from the URL (so a refresh or
// back/forward doesn't replay the highlight), then scrolls the matching
// anchor into view and briefly adds an `is-flash` class. The first attempt
// can run before the target is rendered, so it retries whenever
// `watchSource` changes (e.g. the list length after data loads).
export function useDeepLinkFocus({
  route,
  router,
  queryKey = 'focus',
  anchorClass,
  watchSource,
  flashMs = 1500,
  validateId = safeId,
}) {
  const pendingId = ref(null)

  async function attempt() {
    if (pendingId.value === null) return
    // Wait one tick so any just-rendered row is in the DOM.
    await nextTick()
    const id = pendingId.value
    if (id === null) return
    const el = document.querySelector(`.${anchorClass(id)}`)
    if (!el) return
    if (typeof el.scrollIntoView === 'function') {
      el.scrollIntoView({ block: 'center', behavior: 'smooth' })
    }
    el.classList.add('is-flash')
    setTimeout(() => el.classList.remove('is-flash'), flashMs)
    pendingId.value = null
  }

  function consume() {
    const id = validateId(route.query[queryKey])
    if (id === null) return
    const next = { ...route.query }
    delete next[queryKey]
    router.replace({ query: next })
    pendingId.value = id
    attempt()
  }

  watch(watchSource, attempt)
  watch(() => route.query[queryKey], consume)

  return { consume }
}
