import { onBeforeUnmount, ref, watch } from 'vue'
import Sortable from 'sortablejs'

import { eventsApi } from '../api/events'

/**
 * Drag-to-reorder for the event media grid.
 *
 * Sortable rather than the HTML5 drag-and-drop API: DnD does not fire on
 * touch at all, and members edit events from phones. Writing the touch
 * fallback by hand is most of what this library already is.
 *
 * The list is applied locally first and reverted if the save fails —
 * a grid that snaps back mid-drag is worse than one that corrects after.
 */
export function useMediaReorder({ getEventId, getItems, onReordered }) {
  const container = ref(null)
  const saving = ref(false)
  let sortable = null

  async function persist(from, to) {
    const items = [...getItems()]
    const [moved] = items.splice(from, 1)
    items.splice(to, 0, moved)

    const previous = getItems()
    onReordered(items)
    saving.value = true
    try {
      await eventsApi.reorderMedia(
        getEventId(),
        items.map((m) => ({ type: m.type, id: m.row?.id ?? m.id })),
      )
    } catch {
      onReordered(previous)
      throw new Error('reorder-failed')
    } finally {
      saving.value = false
    }
  }

  function destroy() {
    sortable?.destroy()
    sortable = null
  }

  function attach(el) {
    destroy()
    if (!el) return
    sortable = Sortable.create(el, {
      animation: 150,
      // Long-press to start on touch, so scrolling the grid still scrolls.
      delay: 150,
      delayOnTouchOnly: true,
      // The caption box and the delete button live inside each cell and must
      // stay usable; dragging starts from the thumbnail only.
      handle: '[data-drag-handle]',
      ghostClass: 'media-drag-ghost',
      onEnd: (evt) => {
        if (evt.oldIndex === evt.newIndex) return
        // Sortable has already moved the DOM node; Vue re-renders from the
        // list, so let it put the node back and drive from data instead.
        sortable.sort(sortable.toArray())
        persist(evt.oldIndex, evt.newIndex).catch(() => {})
      },
    })
  }

  watch(container, attach)
  onBeforeUnmount(destroy)

  return { container, saving }
}
