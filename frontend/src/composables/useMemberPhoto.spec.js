import { afterEach, describe, expect, it, vi } from 'vitest'

import { useMemberPhoto } from './useMemberPhoto'
import { membersApi } from '../api/members'

const close = vi.fn()
vi.mock('element-plus', () => ({
  ElMessage: Object.assign(
    vi.fn(() => ({ close })),
    { success: vi.fn(), error: vi.fn() },
  ),
}))

const member = { id: 7, real_name: 'Alice' }
const file = new File([new Uint8Array([1])], 'p.jpg', { type: 'image/jpeg' })

afterEach(() => {
  vi.restoreAllMocks()
})

describe('useMemberPhoto', () => {
  it('onUploadRequest opens the crop dialog with the member + file', () => {
    const p = useMemberPhoto()
    p.onUploadRequest(member, file)
    expect(p.cropOpen.value).toBe(true)
    expect(p.cropTarget.value).toEqual(member)
    expect(p.cropFile.value.name).toBe('p.jpg')
  })

  it('onCropped uploads the cropped file, fires onChanged and clears state', async () => {
    const upload = vi.spyOn(membersApi, 'uploadPhoto').mockResolvedValue({})
    const onChanged = vi.fn()
    const p = useMemberPhoto({ onChanged })
    p.onUploadRequest(member, file)

    const cropped = new File([new Uint8Array([2])], 'c.jpg')
    await p.onCropped(cropped)

    expect(upload).toHaveBeenCalledWith(7, cropped)
    expect(onChanged).toHaveBeenCalled()
    expect(p.cropTarget.value).toBe(null)
    expect(p.uploadingMemberId.value).toBe(null)
  })

  it('onCropped surfaces a too-large error without firing onChanged', async () => {
    vi.spyOn(membersApi, 'uploadPhoto').mockRejectedValue({
      response: { status: 413 },
    })
    const onChanged = vi.fn()
    const p = useMemberPhoto({ onChanged })
    p.onUploadRequest(member, file)
    await p.onCropped(file)
    expect(onChanged).not.toHaveBeenCalled()
  })

  it('delete goes through the password dialog and calls deletePhoto', async () => {
    const del = vi.spyOn(membersApi, 'deletePhoto').mockResolvedValue()
    const onChanged = vi.fn()
    const p = useMemberPhoto({ onChanged })

    p.onDeleteRequest(member)
    expect(p.deleteDialogOpen.value).toBe(true)
    await p.onDeleteConfirm('admin-pw')

    expect(del).toHaveBeenCalledWith(7, 'admin-pw')
    expect(onChanged).toHaveBeenCalled()
    expect(p.deleteDialogOpen.value).toBe(false)
  })

  it('a 422 photo-delete keeps the dialog open with the password error', async () => {
    vi.spyOn(membersApi, 'deletePhoto').mockRejectedValue({
      response: { status: 422 },
    })
    const p = useMemberPhoto()
    p.onDeleteRequest(member)
    await p.onDeleteConfirm('wrong')
    expect(p.deleteError.value).toBe('密碼錯誤')
    expect(p.deleteDialogOpen.value).toBe(true)
  })
})
