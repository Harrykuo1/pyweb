import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { membersApi } from '../api/members'
import { useAuthStore } from '../stores/auth'
import MemberPhotoCell from './MemberPhotoCell.vue'

vi.mock('element-plus', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    ElMessage: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
  }
})

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

describe('MemberPhotoCell', () => {
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

  it('uploadPhoto is called for an admin file selection', async () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'a', role: 'admin' }
    const upload = vi.spyOn(membersApi, 'uploadPhoto').mockResolvedValue({})

    const wrapper = mount(MemberPhotoCell, { props: { member: memberWithoutPhoto } })

    // Simulate the el-upload :on-change callback firing for a chosen file.
    const file = new File(['x'], 'a.png', { type: 'image/png' })
    Object.defineProperty(file, 'size', { value: 1024 })

    // Find the underlying el-upload component instance and call its on-change.
    const uploadEl = wrapper.findComponent({ name: 'ElUpload' })
    const onChange = uploadEl.props('onChange')
    await onChange({ file })
    await flushPromises()

    expect(upload).toHaveBeenCalledWith(2, file)
    expect(wrapper.emitted('changed')).toBeTruthy()
  })

  it('upload rejected when file too large', async () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'a', role: 'admin' }
    const upload = vi.spyOn(membersApi, 'uploadPhoto')

    const wrapper = mount(MemberPhotoCell, { props: { member: memberWithoutPhoto } })
    const huge = new File(['x'], 'big.png', { type: 'image/png' })
    Object.defineProperty(huge, 'size', { value: 5 * 1024 * 1024 + 1 })

    const onChange = wrapper.findComponent({ name: 'ElUpload' }).props('onChange')
    await onChange({ file: huge })
    await flushPromises()

    expect(upload).not.toHaveBeenCalled()
  })

  it('upload rejected for unsupported MIME type', async () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'a', role: 'admin' }
    const upload = vi.spyOn(membersApi, 'uploadPhoto')

    const wrapper = mount(MemberPhotoCell, { props: { member: memberWithoutPhoto } })
    const gif = new File(['x'], 'a.gif', { type: 'image/gif' })
    Object.defineProperty(gif, 'size', { value: 100 })

    const onChange = wrapper.findComponent({ name: 'ElUpload' }).props('onChange')
    await onChange({ file: gif })
    await flushPromises()

    expect(upload).not.toHaveBeenCalled()
  })

  it('handleDelete (popconfirm @confirm target) calls deletePhoto and emits changed', async () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'a', role: 'admin' }
    const del = vi.spyOn(membersApi, 'deletePhoto').mockResolvedValue()

    const wrapper = mount(MemberPhotoCell, { props: { member: memberWithPhoto } })
    // handleDelete is what the popconfirm's @confirm prop calls. Exercising
    // it directly avoids fighting el-popconfirm's lazy popper render in
    // happy-dom while still covering the same code path.
    await wrapper.vm.handleDelete()
    await flushPromises()

    expect(del).toHaveBeenCalledWith(1)
    expect(wrapper.emitted('changed')).toBeTruthy()
  })
})
