import { describe, expect, it, vi } from 'vitest'

import {
  readFilesFromEntry,
  useAttachmentDragDrop,
} from './useAttachmentDragDrop'

// --- FileSystemEntry mocks -------------------------------------------------
function fileEntry(name) {
  return {
    isFile: true,
    isDirectory: false,
    name,
    file: (onSuccess) => onSuccess(new File([new Uint8Array([1])], name)),
  }
}

function dirEntry(name, children) {
  return {
    isFile: false,
    isDirectory: true,
    name,
    createReader: () => {
      let served = false
      return {
        // readEntries yields the children once, then an empty batch to
        // signal exhaustion (mirrors the real 100-per-call API).
        readEntries: (onSuccess) => {
          onSuccess(served ? [] : children)
          served = true
        },
      }
    },
  }
}

describe('readFilesFromEntry', () => {
  it('stamps a bare file with its name as webkitRelativePath', async () => {
    const files = await readFilesFromEntry(fileEntry('foo.pdf'))
    expect(files).toHaveLength(1)
    expect(files[0].webkitRelativePath).toBe('foo.pdf')
  })

  it('recurses into directories and prefixes the folder path', async () => {
    const tree = dirEntry('src', [
      fileEntry('a.pdf'),
      dirEntry('utils', [fileEntry('b.py')]),
    ])
    const files = await readFilesFromEntry(tree)
    expect(files.map((f) => f.webkitRelativePath).sort()).toEqual([
      'src/a.pdf',
      'src/utils/b.py',
    ])
  })

  it('returns nothing for an entry that is neither file nor directory', async () => {
    expect(await readFilesFromEntry({ name: 'x' })).toEqual([])
  })
})

describe('useAttachmentDragDrop', () => {
  it('highlights only on file drags', () => {
    const { isDragOver, onDragEnter } = useAttachmentDragDrop({
      onFiles: vi.fn(),
    })
    onDragEnter({ dataTransfer: { types: ['text/plain'] } })
    expect(isDragOver.value).toBe(false)
    onDragEnter({ dataTransfer: { types: ['Files'] } })
    expect(isDragOver.value).toBe(true)
  })

  it('clears the highlight only when truly leaving the card', () => {
    const { isDragOver, onDragEnter, onDragLeave } = useAttachmentDragDrop({
      onFiles: vi.fn(),
    })
    onDragEnter({ dataTransfer: { types: ['Files'] } })

    // relatedTarget still inside the card → stays highlighted.
    onDragLeave({ currentTarget: { contains: () => true }, relatedTarget: {} })
    expect(isDragOver.value).toBe(true)

    onDragLeave({ currentTarget: { contains: () => false }, relatedTarget: {} })
    expect(isDragOver.value).toBe(false)
  })

  it('expands dropped folders via webkitGetAsEntry and emits each file', async () => {
    const onFiles = vi.fn()
    const { onDrop, isDragOver } = useAttachmentDragDrop({ onFiles })
    isDragOver.value = true

    const tree = dirEntry('src', [fileEntry('a.pdf'), fileEntry('b.pdf')])
    await onDrop({
      dataTransfer: {
        items: [{ webkitGetAsEntry: () => tree }],
      },
    })

    expect(isDragOver.value).toBe(false)
    expect(onFiles).toHaveBeenCalledTimes(2)
    expect(
      onFiles.mock.calls.map((c) => c[0].webkitRelativePath).sort(),
    ).toEqual(['src/a.pdf', 'src/b.pdf'])
  })

  it('falls back to a flat dataTransfer.files list when the items API is absent', async () => {
    const onFiles = vi.fn()
    const { onDrop } = useAttachmentDragDrop({ onFiles })
    const f = new File([new Uint8Array([1])], 'plain.pdf')
    await onDrop({ dataTransfer: { files: [f] } })
    expect(onFiles).toHaveBeenCalledWith(f)
  })

  it('falls back to dataTransfer.files when webkitGetAsEntry returns null (Linux/Chromium)', async () => {
    // The item API is present and reports a file, but webkitGetAsEntry
    // yields null — the platform quirk that left drag-drop silently broken.
    const onFiles = vi.fn()
    const { onDrop } = useAttachmentDragDrop({ onFiles })
    const f = new File([new Uint8Array([1])], 'dropped.pdf')
    await onDrop({
      dataTransfer: {
        items: [{ webkitGetAsEntry: () => null }],
        files: [f],
      },
    })
    expect(onFiles).toHaveBeenCalledWith(f)
  })
})
