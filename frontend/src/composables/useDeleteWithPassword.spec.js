import { describe, expect, it, vi } from 'vitest'

import { useDeleteWithPassword } from './useDeleteWithPassword'

function reject(status) {
  return Promise.reject({ response: { status } })
}

describe('useDeleteWithPassword', () => {
  it('open() stores the target, opens the dialog and clears prior error', () => {
    const flow = useDeleteWithPassword({ remove: vi.fn() })
    flow.error.value = 'stale'

    flow.open({ id: 1 })

    expect(flow.target.value).toEqual({ id: 1 })
    expect(flow.dialogOpen.value).toBe(true)
    expect(flow.error.value).toBe('')
  })

  it('confirm() calls remove with the target + password, then closes and fires onSuccess', async () => {
    const remove = vi.fn().mockResolvedValue()
    const onSuccess = vi.fn()
    const flow = useDeleteWithPassword({ remove, onSuccess })

    flow.open({ id: 7 })
    await flow.confirm('pw')

    expect(remove).toHaveBeenCalledWith({ id: 7 }, 'pw')
    expect(onSuccess).toHaveBeenCalledWith({ id: 7 })
    expect(flow.dialogOpen.value).toBe(false)
    expect(flow.target.value).toBe(null)
    expect(flow.submitting.value).toBe(false)
  })

  it('confirm() with no target is a no-op', async () => {
    const remove = vi.fn()
    const flow = useDeleteWithPassword({ remove })

    await flow.confirm('pw')

    expect(remove).not.toHaveBeenCalled()
  })

  it('maps 422/403/404 to default messages and keeps the dialog open', async () => {
    for (const [status, expected] of [
      [422, '密碼錯誤'],
      [403, '權限不足'],
      [404, '項目已不存在'],
    ]) {
      const flow = useDeleteWithPassword({ remove: () => reject(status) })
      const onSuccess = vi.fn()
      flow.open({ id: 1 })
      await flow.confirm('pw')
      expect(flow.error.value).toBe(expected)
      expect(flow.dialogOpen.value).toBe(true)
      expect(flow.submitting.value).toBe(false)
    }
  })

  it('falls back to a generic message for unmapped statuses', async () => {
    const flow = useDeleteWithPassword({ remove: () => reject(500) })
    flow.open({ id: 1 })
    await flow.confirm('pw')
    expect(flow.error.value).toBe('刪除失敗，請稍後再試')
  })

  it('lets the caller override a status message', async () => {
    const flow = useDeleteWithPassword({
      remove: () => reject(404),
      messages: { 404: '紀錄已不存在' },
    })
    flow.open({ id: 1 })
    await flow.confirm('pw')
    expect(flow.error.value).toBe('紀錄已不存在')
  })

  it('does not call onSuccess when remove rejects', async () => {
    const onSuccess = vi.fn()
    const flow = useDeleteWithPassword({
      remove: () => reject(422),
      onSuccess,
    })
    flow.open({ id: 1 })
    await flow.confirm('pw')
    expect(onSuccess).not.toHaveBeenCalled()
  })
})
