import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { useAuthStore } from '../stores/auth'
import MemberPhotoCell from './MemberPhotoCell.vue'

vi.mock('element-plus', async (importOriginal) => {
  const actual = await importOriginal()
  // ElMessage is invoked both as a function and via .error/.success
  // helpers (rejection toasts on invalid file size / MIME).
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
    const list = img.props('previewSrcList')
    expect(Array.isArray(list)).toBe(true)
    expect(list).toHaveLength(1)
    expect(list[0]).toMatch(/\/api\/members\/1\/photo/)
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

  it('selecting a valid file emits request-upload with the member and the raw File', async () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'a', role: 'admin' }

    const wrapper = mount(MemberPhotoCell, { props: { member: memberWithoutPhoto } })
    const file = makeFile()

    const onChange = wrapper.findComponent({ name: 'ElUpload' }).props('onChange')
    await onChange({ raw: file, name: file.name, size: file.size })

    const events = wrapper.emitted('request-upload')
    expect(events).toBeTruthy()
    expect(events).toHaveLength(1)
    expect(events[0][0]).toEqual(memberWithoutPhoto)
    expect(events[0][1].name).toBe(file.name)
    expect(events[0][1].type).toBe(file.type)
    expect(events[0][1].size).toBe(file.size)
  })

  it('rejects an oversized file without emitting request-upload', async () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'a', role: 'admin' }

    const wrapper = mount(MemberPhotoCell, { props: { member: memberWithoutPhoto } })
    const huge = makeFile({ size: 5 * 1024 * 1024 + 1 })

    const onChange = wrapper.findComponent({ name: 'ElUpload' }).props('onChange')
    await onChange({ raw: huge, name: huge.name, size: huge.size })

    expect(wrapper.emitted('request-upload')).toBeFalsy()
  })

  it('rejects an unsupported MIME without emitting request-upload', async () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'a', role: 'admin' }

    const wrapper = mount(MemberPhotoCell, { props: { member: memberWithoutPhoto } })
    const gif = makeFile({ type: 'image/gif', name: 'a.gif' })

    const onChange = wrapper.findComponent({ name: 'ElUpload' }).props('onChange')
    await onChange({ raw: gif, name: gif.name, size: gif.size })

    expect(wrapper.emitted('request-upload')).toBeFalsy()
  })

  it('clicking delete-photo emits request-delete with the member', async () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'a', role: 'admin' }

    const wrapper = mount(MemberPhotoCell, { props: { member: memberWithPhoto } })
    await wrapper.find('[data-test="delete-photo"]').trigger('click')

    const events = wrapper.emitted('request-delete')
    expect(events).toBeTruthy()
    expect(events).toHaveLength(1)
    expect(events[0][0]).toEqual(memberWithPhoto)
  })

  it('uploading prop renders the in-progress overlay and hides the actions', async () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'a', role: 'admin' }

    const wrapper = mount(MemberPhotoCell, {
      props: { member: memberWithPhoto, uploading: true },
    })

    expect(wrapper.find('[data-test="photo-uploading"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="upload-photo"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="delete-photo"]').exists()).toBe(false)

    await wrapper.setProps({ uploading: false })
    expect(wrapper.find('[data-test="photo-uploading"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="upload-photo"]').exists()).toBe(true)
  })

  it('appends member.photo_updated_at as cache-busting version stamp', () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'v', role: 'viewer' }
    const stamped = { ...memberWithPhoto, photo_updated_at: '2026-04-30T12:00:00Z' }
    const wrapper = mount(MemberPhotoCell, { props: { member: stamped } })

    const img = wrapper.findComponent({ name: 'ElImage' })
    expect(img.props('src')).toContain('?v=')
    expect(img.props('src')).toContain(encodeURIComponent('2026-04-30T12:00:00Z'))
  })

  it('omits version stamp when photo_updated_at is null', () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'v', role: 'viewer' }
    const stamped = { ...memberWithPhoto, photo_updated_at: null }
    const wrapper = mount(MemberPhotoCell, { props: { member: stamped } })

    const img = wrapper.findComponent({ name: 'ElImage' })
    expect(img.props('src')).toBe('/api/members/1/photo')
  })
})
