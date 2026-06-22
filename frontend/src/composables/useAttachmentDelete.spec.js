import { afterEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'

import { useAttachmentDelete } from './useAttachmentDelete'
import { jobAttachmentsApi } from '../api/jobAttachments'

vi.mock('element-plus', () => ({
  ElMessage: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }),
}))

function setup(attachments = [{ id: 1 }, { id: 2 }, { id: 3 }]) {
  const attachmentsRef = ref(attachments)
  const onDeleted = vi.fn()
  const del = useAttachmentDelete({
    jobId: ref(7),
    attachments: attachmentsRef,
    onDeleted,
  })
  return { del, attachmentsRef, onDeleted }
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('useAttachmentDelete', () => {
  it('openDeleteDialog stores the descriptor, opens, and clears prior error', () => {
    const { del } = setup()
    del.deleteError.value = 'stale'
    del.openDeleteDialog({ mode: 'single', ids: [1] })
    expect(del.pendingDelete.value).toEqual({ mode: 'single', ids: [1] })
    expect(del.deleteDialogOpen.value).toBe(true)
    expect(del.deleteError.value).toBe('')
  })

  it('single mode calls remove, drops the row, fires onDeleted and closes', async () => {
    const remove = vi.spyOn(jobAttachmentsApi, 'remove').mockResolvedValue()
    const { del, attachmentsRef, onDeleted } = setup()
    del.openDeleteDialog({ mode: 'single', ids: [2], successMsg: 'ok' })
    await del.onDeleteConfirm('pw')

    expect(remove).toHaveBeenCalledWith(7, 2, 'pw')
    expect(attachmentsRef.value.map((a) => a.id)).toEqual([1, 3])
    expect(onDeleted).toHaveBeenCalledWith({
      mode: 'single',
      ids: [2],
      successMsg: 'ok',
    })
    expect(del.deleteDialogOpen.value).toBe(false)
  })

  it('bulk mode calls bulkRemove for every id', async () => {
    const bulk = vi.spyOn(jobAttachmentsApi, 'bulkRemove').mockResolvedValue({})
    const { del, attachmentsRef } = setup()
    del.openDeleteDialog({ mode: 'bulk', ids: [1, 3], successMsg: 'ok' })
    await del.onDeleteConfirm('pw')
    expect(bulk).toHaveBeenCalledWith(7, [1, 3], 'pw')
    expect(attachmentsRef.value.map((a) => a.id)).toEqual([2])
  })

  it('surfaces 密碼錯誤 on 422 and keeps the dialog open without deleting', async () => {
    vi.spyOn(jobAttachmentsApi, 'remove').mockRejectedValue({
      response: { status: 422 },
    })
    const { del, attachmentsRef, onDeleted } = setup()
    del.openDeleteDialog({ mode: 'single', ids: [1] })
    await del.onDeleteConfirm('wrong')

    expect(del.deleteError.value).toBe('密碼錯誤')
    expect(del.deleteDialogOpen.value).toBe(true)
    expect(attachmentsRef.value).toHaveLength(3)
    expect(onDeleted).not.toHaveBeenCalled()
  })

  it('confirm with no pending descriptor is a no-op', async () => {
    const remove = vi.spyOn(jobAttachmentsApi, 'remove')
    const { del } = setup()
    await del.onDeleteConfirm('pw')
    expect(remove).not.toHaveBeenCalled()
  })
})
