import { onBeforeUnmount, ref, unref, watch } from 'vue'

// Animates a displayed integer from its current value toward a target,
// driven by `source` (a ref or a plain number — re-runs whenever the
// source mutates). Ease-out cubic over `duration` ms.
//
// `animate: false` short-circuits the animation entirely (used by tests
// and as the fallback for users who set prefers-reduced-motion). The
// caller still gets a reactive `display` that mirrors the source —
// just without the rAF dance.

const DEFAULT_DURATION_MS = 900

function prefersReducedMotion() {
  if (typeof window === 'undefined' || !window.matchMedia) return false
  try {
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches
  } catch {
    return false
  }
}

export function useCounter(source, options = {}) {
  const duration = options.duration ?? DEFAULT_DURATION_MS
  const display = ref(0)
  let frame = null

  function clear() {
    if (frame !== null && typeof cancelAnimationFrame === 'function') {
      cancelAnimationFrame(frame)
      frame = null
    }
  }

  // Re-checked on every watcher fire so test environments can flip
  // prefers-reduced-motion via matchMedia stubs without timing out
  // setup ordering.
  function animationDisabled() {
    if (options.animate === false) return true
    if (prefersReducedMotion()) return true
    return typeof requestAnimationFrame !== 'function'
  }

  // Source can be a ref, a plain number, or a getter function (the
  // common case when binding to nested reactive state, e.g.
  // `() => store.value.total_members`). unref() handles refs but
  // returns getter functions as-is, so we resolve callables manually.
  function readSource() {
    return typeof source === 'function' ? source() : unref(source)
  }

  watch(
    () => {
      const v = Number(readSource())
      return Number.isFinite(v) ? v : 0
    },
    (target) => {
      clear()
      if (animationDisabled()) {
        display.value = target
        return
      }
      const start =
        typeof performance !== 'undefined' ? performance.now() : Date.now()
      const initial = display.value
      const delta = target - initial
      if (delta === 0) return
      const tick = (now) => {
        const t = typeof now === 'number' ? now : Date.now()
        const progress = Math.min(1, (t - start) / duration)
        const eased = 1 - Math.pow(1 - progress, 3)
        display.value = Math.round(initial + delta * eased)
        if (progress < 1) frame = requestAnimationFrame(tick)
        else frame = null
      }
      frame = requestAnimationFrame(tick)
    },
    { immediate: true },
  )

  onBeforeUnmount(clear)

  return display
}
