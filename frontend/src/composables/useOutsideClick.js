import { onBeforeUnmount, onMounted } from 'vue'

// Dismiss an open popover / dropdown when the user clicks outside all of
// `refs` or presses Escape. Listeners are registered at document level (so
// they run before inner handlers) and gated by `isOpen` so they no-op
// while closed. Cleaned up on unmount.
export function useOutsideClick({ isOpen, refs, onClose }) {
  function onDocClick(event) {
    if (!isOpen.value) return
    for (const r of refs) {
      if (r.value?.contains(event.target)) return
    }
    onClose()
  }

  function onKeydown(event) {
    if (event.key === 'Escape' && isOpen.value) onClose()
  }

  onMounted(() => {
    document.addEventListener('click', onDocClick)
    document.addEventListener('keydown', onKeydown)
  })

  onBeforeUnmount(() => {
    document.removeEventListener('click', onDocClick)
    document.removeEventListener('keydown', onKeydown)
  })
}
