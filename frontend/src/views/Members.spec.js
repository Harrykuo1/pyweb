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
    resume_md: '# resume',
    joined_at: '2022-01-01T00:00:00+00:00',
    has_photo: true,
    has_resume_md: true,
    has_resume_pdf: false,
  },
  {
    id: 2,
    graduation_year: 2023,
    real_name: 'Bob',
    current_position: 'PM',
    resume_md: null,
    joined_at: '2023-06-01T00:00:00+00:00',
    has_photo: false,
    has_resume_md: false,
    has_resume_pdf: false,
  },
]

beforeEach(() => {
  setActivePinia(createPinia())
})

afterEach(() => {
  vi.restoreAllMocks()
  document.body.innerHTML = ''
})

async function mountAsAdmin(members = sampleMembers) {
  const auth = useAuthStore()
  auth.user = { id: 1, username: 'a', role: 'admin' }
  vi.spyOn(membersApi, 'list').mockResolvedValue(members)
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

    // The first action button in the empty-list state is "切換排序".
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

  it('resume button is enabled for members with at least one resume format', async () => {
    const wrapper = await mountAsAdmin()
    const buttons = wrapper.findAll('[data-test="view-resume-button"]')
    // Only Alice has a resume_md, so only one resume button is enabled.
    expect(buttons.length).toBe(1)
  })

  it('resume button is rendered as disabled tooltip for members without any resume', async () => {
    const noResume = [
      {
        id: 1,
        graduation_year: 2024,
        real_name: 'Carol',
        current_position: 'X',
        resume_md: null,
        joined_at: '2024-01-01T00:00:00+00:00',
        has_photo: false,
        has_resume_md: false,
        has_resume_pdf: false,
      },
    ]
    const wrapper = await mountAsAdmin(noResume)
    expect(wrapper.findAll('[data-test="view-resume-button"]').length).toBe(0)
    // The disabled placeholder button still renders inside the table.
    expect(wrapper.text()).toContain('履歷')
  })

  it('confirming delete calls membersApi.remove and re-fetches', async () => {
    const wrapper = await mountAsAdmin()
    const remove = vi.spyOn(membersApi, 'remove').mockResolvedValue()
    const list = vi.spyOn(membersApi, 'list').mockResolvedValue(
      sampleMembers.filter((m) => m.id !== 1),
    )

    await wrapper.findAll('[data-test="delete-button"]')[0].trigger('click')
    await flushPromises()

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
