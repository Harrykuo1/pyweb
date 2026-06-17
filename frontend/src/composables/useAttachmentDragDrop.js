import { ref } from 'vue'

// Recursively walk a dropped FileSystemEntry into a flat array of Files,
// stamping each with a synthetic webkitRelativePath so the folder
// structure survives — matching what <input webkitdirectory> produces, so
// the rest of the upload pipeline needs no special-casing for drops.
export async function readFilesFromEntry(entry, pathPrefix = '') {
  if (entry.isFile) {
    return new Promise((resolve, reject) => {
      entry.file((file) => {
        try {
          Object.defineProperty(file, 'webkitRelativePath', {
            value: pathPrefix + entry.name,
            configurable: true,
          })
        } catch {
          // Some browsers seal File; harmless — relpathOf falls back to
          // file.name and we lose folder structure for that one file,
          // which is the best we can do.
        }
        resolve([file])
      }, reject)
    })
  }
  if (entry.isDirectory) {
    const reader = entry.createReader()
    // readEntries returns at most 100 per call — loop until exhausted.
    const directChildren = []
    let batch
    do {
      batch = await new Promise((resolve, reject) => {
        reader.readEntries(resolve, reject)
      })
      directChildren.push(...batch)
    } while (batch.length > 0)
    const all = []
    for (const child of directChildren) {
      const collected = await readFilesFromEntry(
        child,
        pathPrefix + entry.name + '/',
      )
      all.push(...collected)
    }
    return all
  }
  return []
}

// Drag-and-drop affordance for the attachments card. Owns only the
// drag-over highlight and turns a drop — folders expanded recursively via
// the FileSystemEntry API, with a flat dataTransfer.files fallback — into
// individual Files handed back through onFiles. It does not know about the
// upload queue; the caller wires onFiles to its pushPending.
export function useAttachmentDragDrop({ onFiles }) {
  const isDragOver = ref(false)

  function onDragEnter(event) {
    // Only react to file drags — ignoring text/link drags keeps random
    // browser-internal drags from flickering the overlay.
    if (event.dataTransfer?.types?.includes('Files')) {
      isDragOver.value = true
    }
  }

  function onDragLeave(event) {
    // dragleave fires every time the pointer crosses a child boundary;
    // only clear the highlight when truly leaving the card.
    if (!event.currentTarget.contains(event.relatedTarget)) {
      isDragOver.value = false
    }
  }

  async function onDrop(event) {
    isDragOver.value = false
    const items = event.dataTransfer?.items
    // Capture the flat file list synchronously — dataTransfer is only
    // valid during the event dispatch, and the entry-walk path below
    // awaits, after which dataTransfer.files would read empty.
    const flatFiles = event.dataTransfer?.files
      ? [...event.dataTransfer.files]
      : []

    // Preferred path: walk DataTransferItems with webkitGetAsEntry so a
    // dropped folder expands recursively. Collect every entry first, all
    // synchronously, before any await.
    if (
      items &&
      items.length > 0 &&
      typeof items[0].webkitGetAsEntry === 'function'
    ) {
      const entries = []
      for (const item of items) {
        const entry = item.webkitGetAsEntry()
        if (entry) entries.push(entry)
      }
      // webkitGetAsEntry returns null for dragged files on some platforms
      // (notably Linux/Chromium) even when dataTransfer.files has them.
      // Only trust the entry walk when it actually yielded entries;
      // otherwise fall through to the flat list below.
      if (entries.length > 0) {
        for (const entry of entries) {
          for (const file of await readFilesFromEntry(entry, '')) onFiles(file)
        }
        return
      }
    }

    // Fallback: the items/entry API was unavailable or produced nothing —
    // upload the flat files (no folder structure, which is fine for a
    // plain file drop). Captured synchronously above.
    for (const file of flatFiles) onFiles(file)
  }

  return { isDragOver, onDragEnter, onDragLeave, onDrop }
}
