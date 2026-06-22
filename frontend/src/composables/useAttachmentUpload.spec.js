import { afterEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'
import { flushPromises } from '@vue/test-utils'

import { useAttachmentUpload } from './useAttachmentUpload'
import { jobAttachmentsApi } from '../api/jobAttachments'

vi.mock('element-plus', () => ({
  ElMessage: Object.assign(vi.fn(), {
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  }),
  ElMessageBox: { confirm: vi.fn(), prompt: vi.fn() },
}))

function setup({ attachments = [], currentPath = '', maxAttachments = null } = {}) {
  const attachmentsRef = ref(attachments)
  const upload = useAttachmentUpload({
    jobId: ref(7),
    attachments: attachmentsRef,
    currentPath: ref(currentPath),
    maxAttachments: ref(maxAttachments),
  })
  return { upload, attachmentsRef }
}

function fileWith(name, relpath) {
  const f = new File([new Uint8Array([1])], name, { type: 'application/pdf' })
  if (relpath) Object.defineProperty(f, 'webkitRelativePath', { value: relpath })
  return f
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('useAttachmentUpload', () => {
  it('drops OS junk files without queuing them', async () => {
    const spy = vi.spyOn(jobAttachmentsApi, 'upload').mockResolvedValue({ id: 1 })
    const { upload } = setup()
    upload.pushPending(fileWith('.DS_Store', 'src/.DS_Store'))
    await flushPromises()
    expect(spy).not.toHaveBeenCalled()
  })

  it('stamps the relpath with the current folder', async () => {
    const spy = vi
      .spyOn(jobAttachmentsApi, 'upload')
      .mockResolvedValue({ id: 9, filename: 'src/foo.pdf' })
    const { upload } = setup({ currentPath: 'src' })
    upload.pushPending(fileWith('foo.pdf'))
    await flushPromises()
    expect(spy).toHaveBeenCalledWith(
      7,
      expect.any(File),
      null,
      'src/foo.pdf',
      expect.any(Function),
    )
  })

  it('appends a newly uploaded file to attachments', async () => {
    vi.spyOn(jobAttachmentsApi, 'upload').mockResolvedValue({
      id: 9,
      filename: 'foo.pdf',
    })
    const { upload, attachmentsRef } = setup()
    upload.pushPending(fileWith('foo.pdf'))
    await flushPromises()
    expect(attachmentsRef.value.map((a) => a.id)).toContain(9)
  })

  it('opens the conflict dialog for a name collision and overwrites by id on resolve', async () => {
    const spy = vi
      .spyOn(jobAttachmentsApi, 'upload')
      .mockResolvedValue({ id: 1, filename: 'foo.pdf', size_bytes: 99 })
    const { upload, attachmentsRef } = setup({
      attachments: [{ id: 1, filename: 'foo.pdf', size_bytes: 1 }],
    })

    upload.pushPending(fileWith('foo.pdf'))
    await flushPromises()
    expect(upload.conflictDialogOpen.value).toBe(true)
    expect(spy).not.toHaveBeenCalled()

    upload.onConflictResolved({ 'foo.pdf': 'overwrite' })
    await flushPromises()

    expect(spy).toHaveBeenCalledWith(
      7,
      expect.any(File),
      'overwrite',
      'foo.pdf',
      expect.any(Function),
    )
    // Replaced in place, not appended.
    expect(attachmentsRef.value).toHaveLength(1)
    expect(attachmentsRef.value[0].size_bytes).toBe(99)
  })

  it('skips files the user chose to skip in the conflict dialog', async () => {
    const spy = vi.spyOn(jobAttachmentsApi, 'upload')
    const { upload } = setup({
      attachments: [{ id: 1, filename: 'foo.pdf' }],
    })
    upload.pushPending(fileWith('foo.pdf'))
    await flushPromises()
    upload.onConflictResolved({ 'foo.pdf': 'skip' })
    await flushPromises()
    expect(spy).not.toHaveBeenCalled()
  })
})
