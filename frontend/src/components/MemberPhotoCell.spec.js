import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { membersApi } from '../api/members'
import { useAuthStore } from '../stores/auth'
import MemberPhotoCell from './MemberPhotoCell.vue'

vi.mock('element-plus', async (importOriginal) => {
  const actual = await importOriginal()
  // The component now invokes ElMessage as a function for the persistent
  // "上傳中…" toast; mirror Element Plus's real shape (callable, plus
  // .success / .error / .info / .warning helpers).
  const message = vi.fn(() => ({ close: vi.fn() }))
  message.success = vi.fn()
  message.error = vi.fn()
  message.info = vi.fn()
  message.warning = vi.fn()
  return {
    ...actual,
    ElMessage: message,
  }
})

// PhotoCropDialog pulls in cropperjs (web-component custom elements that
// happy-dom does not fully model). Stub it so the cell tests stay focused.
vi.mock('./PhotoCropDialog.vue', () => ({
  default: {
    name: 'PhotoCropDialog',
    props: ['modelValue', 'sourceFile'],
    emits: ['update:modelValue', 'cropped'],
    template: '<div data-test="crop-stub" />',
  },
}))

beforeEach(() => {
  setActivePinia(createPinia())
})

afterEach(() => {
  vi.restoreAllMocks()
  document.body.innerHTML = ''
})

const memberWithPhoto = {
  id: 1,
  real_name: 'Alice',
  has_photo: true,
}
const memberWithoutPhoto = {
  id: 2,
  real_name: 'Bob',
  has_photo: false,
}

function makeFile(opts = {}) {
  const f = new File(['x'], opts.name ?? 'a.png', { type: opts.type ?? 'image/png' })
  Object.defineProperty(f, 'size', { value: opts.size ?? 1024 })
  return f
}

describe('MemberPhotoCell', () => {
  it('renders an el-image with preview when the member has a photo', () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'v', role: 'viewer' }
    const wrapper = mount(MemberPhotoCell, { props: { member: memberWithPhoto } })

    const img = wrapper.findComponent({ name: 'ElImage' })
    expect(img.exists()).toBe(true)
    expect(wrapper.find('[data-test="photo-thumb"]').exists()).toBe(true)
    // The previewable source list mirrors the thumbnail src so el-image's
    // built-in viewer can pull up a full-size copy.
    const list = img.props('previewSrcList')
    expect(Array.isArray(list)).toBe(true)
    expect(list).toHaveLength(1)
    expect(list[0]).toMatch(/\/api\/members\/1\/photo\?v=/)
    // Must teleport so the preview overlay escapes the table cell stacking.
    expect(img.props('previewTeleported')).toBe(true)
  })

  it('renders the icon fallback (no preview) when no photo', () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'v', role: 'viewer' }
    const wrapper = mount(MemberPhotoCell, { props: { member: memberWithoutPhoto } })

    expect(wrapper.findComponent({ name: 'ElImage' }).exists()).toBe(false)
    expect(wrapper.findComponent({ name: 'ElAvatar' }).exists()).toBe(true)
  })

  it('viewer sees no admin actions', () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'v', role: 'viewer' }
    const wrapper = mount(MemberPhotoCell, { props: { member: memberWithPhoto } })

    expect(wrapper.find('[data-test="upload-photo"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="delete-photo"]').exists()).toBe(false)
  })

  it('admin sees upload control whether or not photo exists', () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'a', role: 'admin' }

    const w1 = mount(MemberPhotoCell, { props: { member: memberWithoutPhoto } })
    expect(w1.find('[data-test="upload-photo"]').exists()).toBe(true)
    expect(w1.find('[data-test="delete-photo"]').exists()).toBe(false)

    const w2 = mount(MemberPhotoCell, { props: { member: memberWithPhoto } })
    expect(w2.find('[data-test="upload-photo"]').exists()).toBe(true)
    expect(w2.find('[data-test="delete-photo"]').exists()).toBe(true)
  })

  it('selecting a valid file opens the crop dialog with that file', async () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'a', role: 'admin' }
    const upload = vi.spyOn(membersApi, 'uploadPhoto')

    const wrapper = mount(MemberPhotoCell, { props: { member: memberWithoutPhoto } })
    const file = makeFile()

    const onChange = wrapper.findComponent({ name: 'ElUpload' }).props('onChange')
    await onChange({ raw: file, name: file.name, size: file.size })
    await flushPromises()

    // Upload should NOT be called yet — we wait for the crop confirmation.
    expect(upload).not.toHaveBeenCalled()
    const dialog = wrapper.findComponent({ name: 'PhotoCropDialog' })
    expect(dialog.props('modelValue')).toBe(true)
    // Vue Test Utils may proxy the prop, so compare identity-ish fields
    // instead of strict object equality.
    const passed = dialog.props('sourceFile')
    expect(passed.name).toBe(file.name)
    expect(passed.type).toBe(file.type)
    expect(passed.size).toBe(file.size)
  })

  it('cropped event triggers uploadPhoto with the cropped file', async () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'a', role: 'admin' }
    const upload = vi.spyOn(membersApi, 'uploadPhoto').mockResolvedValue({})

    const wrapper = mount(MemberPhotoCell, { props: { member: memberWithoutPhoto } })
    const croppedFile = makeFile({ name: 'photo.jpg', type: 'image/jpeg' })

    await wrapper.vm.handleCropped(croppedFile)
    await flushPromises()

    expect(upload).toHaveBeenCalledWith(2, croppedFile)
    expect(wrapper.emitted('changed')).toBeTruthy()
  })

  it('upload rejected when file too large; crop dialog stays closed', async () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'a', role: 'admin' }
    const upload = vi.spyOn(membersApi, 'uploadPhoto')

    const wrapper = mount(MemberPhotoCell, { props: { member: memberWithoutPhoto } })
    const huge = makeFile({ size: 5 * 1024 * 1024 + 1 })

    const onChange = wrapper.findComponent({ name: 'ElUpload' }).props('onChange')
    await onChange({ raw: huge, name: huge.name, size: huge.size })
    await flushPromises()

    expect(upload).not.toHaveBeenCalled()
    expect(wrapper.findComponent({ name: 'PhotoCropDialog' }).props('modelValue')).toBe(false)
  })

  it('upload rejected for unsupported MIME; crop dialog stays closed', async () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'a', role: 'admin' }
    const upload = vi.spyOn(membersApi, 'uploadPhoto')

    const wrapper = mount(MemberPhotoCell, { props: { member: memberWithoutPhoto } })
    const gif = makeFile({ type: 'image/gif', name: 'a.gif' })

    const onChange = wrapper.findComponent({ name: 'ElUpload' }).props('onChange')
    await onChange({ raw: gif, name: gif.name, size: gif.size })
    await flushPromises()

    expect(upload).not.toHaveBeenCalled()
    expect(wrapper.findComponent({ name: 'PhotoCropDialog' }).props('modelValue')).toBe(false)
  })

  it('handleDelete calls deletePhoto with password and emits changed', async () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'a', role: 'admin' }
    const del = vi.spyOn(membersApi, 'deletePhoto').mockResolvedValue()

    const wrapper = mount(MemberPhotoCell, { props: { member: memberWithPhoto } })
    await wrapper.vm.handleDelete('admin-pw')
    await flushPromises()

    expect(del).toHaveBeenCalledWith(1, 'admin-pw')
    expect(wrapper.emitted('changed')).toBeTruthy()
  })

  it('clicking delete-photo opens DeleteWithPasswordDialog with the member name', async () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'a', role: 'admin' }

    const wrapper = mount(MemberPhotoCell, { props: { member: memberWithPhoto } })
    const dialog = wrapper.findComponent({ name: 'DeleteWithPasswordDialog' })
    expect(dialog.props('modelValue')).toBe(false)

    await wrapper.find('[data-test="delete-photo"]').trigger('click')
    await flushPromises()

    expect(dialog.props('modelValue')).toBe(true)
    expect(dialog.props('itemName')).toBe('Alice')
  })

  it('handleDelete on 401 surfaces 密碼錯誤 via the dialog and does not emit changed', async () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'a', role: 'admin' }
    vi.spyOn(membersApi, 'deletePhoto').mockRejectedValue(
      Object.assign(new Error('401'), { response: { status: 401 } }),
    )

    const wrapper = mount(MemberPhotoCell, { props: { member: memberWithPhoto } })
    // Open the dialog first so its props reflect the error after submit.
    wrapper.vm.askDelete()
    await flushPromises()
    await wrapper.vm.handleDelete('wrong-pw')
    await flushPromises()

    const dialog = wrapper.findComponent({ name: 'DeleteWithPasswordDialog' })
    expect(dialog.props('errorMessage')).toBe('密碼錯誤')
    expect(dialog.props('modelValue')).toBe(true)
    expect(wrapper.emitted('changed')).toBeFalsy()
  })
})
