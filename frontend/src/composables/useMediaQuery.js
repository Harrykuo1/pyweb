import { onBeforeUnmount, onMounted, ref } from 'vue'

// Reactive `matchMedia` — returns a ref that tracks whether `query`
// currently matches, wiring the change listener on mount and cleaning it
// up on unmount. SSR/JSDOM-safe (no-op when matchMedia is unavailable).
export function useMediaQuery(query) {
  const matches = ref(false)
  let mql = null

  function onChange(e) {
    matches.value = e.matches
  }

  onMounted(() => {
    if (typeof window !== 'undefined' && window.matchMedia) {
      mql = window.matchMedia(query)
      matches.value = mql.matches
      mql.addEventListener?.('change', onChange)
    }
  })

  onBeforeUnmount(() => {
    mql?.removeEventListener?.('change', onChange)
    mql = null
  })

  return matches
}
