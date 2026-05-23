// Folder-tree helpers shared by JobAttachmentsViewer (read-only
// browsing) and JobAttachmentsManager (browse + upload-to-current-
// path). Both consumers project the flat list of attachments (each
// with a "src/components/Foo.vue" style filename) into a per-folder
// listing keyed by the user's current path.
//
// The tree is *emergent*: there are no real folder entities. A
// folder shows up if any attachment's filename starts with that
// segment, and disappears as soon as the last descendant is gone.
// This keeps the data model trivial (single filename column on
// job_attachments) while still giving users a familiar
// browse-by-folder UI.

/**
 * Returns the folder+file listing visible at `currentPath`.
 *
 * @param {Array<{id: number, filename: string, ...}>} attachments
 * @param {string} currentPath  ""   for root,
 *                              "src/components" for a sub-folder.
 * @returns {{
 *   folders: Array<{name: string, count: number}>,
 *   files: Array<{attachment: object, displayName: string}>,
 * }}
 *
 * `folders[].count` is the total descendant file count (not just
 * direct children), so users can tell a sparse from a dense folder
 * at a glance. Both sides are locale-sorted with numeric awareness
 * so "Section 2" comes before "Section 10".
 */
export function buildListing(attachments, currentPath) {
  const folders = new Map()
  const files = []
  const prefix = currentPath === '' ? '' : `${currentPath}/`

  for (const a of attachments) {
    if (prefix && !a.filename.startsWith(prefix)) continue
    const remaining = a.filename.slice(prefix.length)
    const slash = remaining.indexOf('/')
    if (slash === -1) {
      files.push({ attachment: a, displayName: remaining })
    } else {
      const folderName = remaining.slice(0, slash)
      const existing =
        folders.get(folderName) || { name: folderName, count: 0 }
      existing.count += 1
      folders.set(folderName, existing)
    }
  }

  const compare = (a, b) =>
    a.localeCompare(b, undefined, { numeric: true })

  return {
    folders: [...folders.values()].sort((a, b) => compare(a.name, b.name)),
    files: files.sort((a, b) => compare(a.displayName, b.displayName)),
  }
}

/**
 * Splits `currentPath` into clickable breadcrumb segments, prefixed
 * by a synthetic root entry so the user always sees where they
 * started.
 */
export function breadcrumbSegments(currentPath, rootLabel = '附件') {
  const segs = [{ name: rootLabel, path: '' }]
  if (!currentPath) return segs
  const parts = currentPath.split('/')
  let acc = ''
  for (const part of parts) {
    acc = acc ? `${acc}/${part}` : part
    segs.push({ name: part, path: acc })
  }
  return segs
}

/** Concatenate a parent path with a child segment using "/". */
export function joinPath(parent, child) {
  if (!parent) return child
  if (!child) return parent
  return `${parent}/${child}`
}

/**
 * Return every attachment whose filename sits under `folderPath`,
 * at any depth. Used by the manager's "delete folder" + "bulk delete
 * with folder rows selected" paths to expand a folder selection into
 * the concrete row IDs the backend's bulk-delete endpoint expects.
 *
 * `folderPath` is the absolute path (e.g. "src/components"), without
 * a trailing slash. The prefix match is anchored at a "/" boundary so
 * "src" doesn't accidentally swallow "src-archived/".
 */
export function attachmentsUnder(attachments, folderPath) {
  if (!folderPath) return [...attachments]
  const prefix = `${folderPath}/`
  return attachments.filter((a) => a.filename.startsWith(prefix))
}
