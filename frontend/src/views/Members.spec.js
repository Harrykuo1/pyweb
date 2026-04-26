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
})

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

    // The first action button is "切換排序".
    await wrapper.findAll('button')[0].trigger('click')
    await flushPromises()

    expect(list).toHaveBeenCalledWith({ order: 'desc' })
  })
})
