import { ref } from 'vue'

// A view-mode toggle (e.g. grid vs list) persisted to localStorage so the
// choice sticks across sessions. Reads/writes are wrapped so quota or
// private-mode failures fall back to the default instead of throwing.
export function useViewModePreference(
  key,
  allowed = ['grid', 'list'],
  fallback = 'grid',
) {
  function read() {
    try {
      const stored = localStorage.getItem(key)
      return allowed.includes(stored) ? stored : fallback
    } catch {
      return fallback
    }
  }

  const viewMode = ref(read())

  function setViewMode(mode) {
    viewMode.value = mode
    try {
      localStorage.setItem(key, mode)
    } catch {
      /* swallow — quota / private mode */
    }
  }

  return { viewMode, setViewMode }
}
