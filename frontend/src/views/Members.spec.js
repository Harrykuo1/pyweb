import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { membersApi } from '../api/members'
import { useAuthStore } from '../stores/auth'
import Members from './Members.vue'

vi.mock('element-plus', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    ElMessage: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
  }
})

const sampleMembers = [
  {
    id: 1,
    graduation_year: 2022,
    real_name: 'Alice',
    current_position: 'SWE',
    resume_md: null,
    joined_at: '2022-01-01T00:00:00+00:00',
  },
  {
    id: 2,
    graduation_year: 2023,
    real_name: 'Bob',
    current_position: 'PM',
    resume_md: null,
    joined_at: '2023-06-01T00:00:00+00:00',
  },
]

beforeEach(() => {
  setActivePinia(createPinia())
})

afterEach(() => {
  vi.restoreAllMocks()
  document.body.innerHTML = ''
})

async function mountAsAdmin() {
  const auth = useAuthStore()
  auth.user = { id: 1, username: 'a', role: 'admin' }
  vi.spyOn(membersApi, 'list').mockResolvedValue(sampleMembers)
  const wrapper = mount(Members, { attachTo: document.body })
  await flushPromises()
  return wrapper
}

describe('Members.vue', () => {
  it('loads members on mount with default order=asc', async () => {
    const list = vi.spyOn(membersApi, 'list').mockResolvedValue(sampleMembers)
    mount(Members)
    await flushPromises()

    expect(list).toHaveBeenCalledWith({ order: 'asc' })
  })

  it('renders rows for each member', async () => {
    vi.spyOn(membersApi, 'list').mockResolvedValue(sampleMembers)
    const wrapper = mount(Members)
    await flushPromises()

    const text = wrapper.text()
    expect(text).toContain('Alice')
    expect(text).toContain('Bob')
    expect(text).toContain('SWE')
    expect(text).toContain('PM')
  })

  it('shows the add-member button for admin', async () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'a', role: 'admin' }
    vi.spyOn(membersApi, 'list').mockResolvedValue([])

    const wrapper = mount(Members)
    await flushPromises()

    expect(wrapper.find('[data-test="add-member-button"]').exists()).toBe(true)
  })

  it('hides the add-member button for viewer', async () => {
    const auth = useAuthStore()
    auth.user = { id: 2, username: 'v', role: 'viewer' }
    vi.spyOn(membersApi, 'list').mockResolvedValue([])

    const wrapper = mount(Members)
    await flushPromises()

    expect(wrapper.find('[data-test="add-member-button"]').exists()).toBe(false)
  })

  it('toggle button flips order and re-fetches', async () => {
    const list = vi.spyOn(membersApi, 'list').mockResolvedValue([])
    const wrapper = mount(Members)
    await flushPromises()
    list.mockClear()

    await wrapper.findAll('button')[0].trigger('click')
    await flushPromises()

    expect(list).toHaveBeenCalledWith({ order: 'desc' })
  })

  it('admin sees edit and delete buttons on each row', async () => {
    const wrapper = await mountAsAdmin()
    expect(wrapper.findAll('[data-test="edit-button"]').length).toBe(2)
    expect(wrapper.findAll('[data-test="delete-button"]').length).toBe(2)
  })

  it('viewer does not see edit/delete buttons', async () => {
    const auth = useAuthStore()
    auth.user = { id: 2, username: 'v', role: 'viewer' }
    vi.spyOn(membersApi, 'list').mockResolvedValue(sampleMembers)
    const wrapper = mount(Members)
    await flushPromises()

    expect(wrapper.find('[data-test="edit-button"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="delete-button"]').exists()).toBe(false)
  })

  it('confirming delete calls membersApi.remove and re-fetches', async () => {
    const wrapper = await mountAsAdmin()
    const remove = vi.spyOn(membersApi, 'remove').mockResolvedValue()
    const list = vi.spyOn(membersApi, 'list').mockResolvedValue(
      sampleMembers.filter((m) => m.id !== 1),
    )

    // Open the popconfirm on the first row.
    await wrapper.findAll('[data-test="delete-button"]')[0].trigger('click')
    await flushPromises()

    // Confirm button is the popper's primary button labelled "刪除".
    const confirmBtn = Array.from(
      wrapper.element.querySelectorAll('.el-popconfirm__action button'),
    ).find((b) => b.textContent.trim() === '刪除')
    expect(confirmBtn).toBeDefined()
    confirmBtn.click()
    await flushPromises()

    expect(remove).toHaveBeenCalledWith(1)
    expect(list).toHaveBeenCalled()
  })

  it('cancelling delete does not call remove', async () => {
    const wrapper = await mountAsAdmin()
    const remove = vi.spyOn(membersApi, 'remove').mockResolvedValue()

    await wrapper.findAll('[data-test="delete-button"]')[0].trigger('click')
    await flushPromises()

    const cancelBtn = Array.from(
      wrapper.element.querySelectorAll('.el-popconfirm__action button'),
    ).find((b) => b.textContent.trim() === '取消')
    cancelBtn?.click()
    await flushPromises()

    expect(remove).not.toHaveBeenCalled()
  })
})
