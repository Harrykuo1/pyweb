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

// Wrappers created with attachTo: document.body need explicit unmount —
// otherwise Element Plus's popconfirm reference handlers leak between
// tests and the next click silently no-ops. Track each one and unmount
// during afterEach.
let pendingTeardowns = []

beforeEach(() => {
  setActivePinia(createPinia())
  try {
    localStorage.removeItem('pyweb.members.viewMode')
  } catch {
    /* ignore */
  }
})

afterEach(() => {
  vi.restoreAllMocks()
  for (const w of pendingTeardowns) w.unmount()
  pendingTeardowns = []
  document.body.innerHTML = ''
})

async function mountAsAdmin(members = sampleMembers) {
  const auth = useAuthStore()
  auth.user = { id: 1, username: 'a', role: 'admin' }
  vi.spyOn(membersApi, 'list').mockResolvedValue(members)
  const wrapper = mount(Members, { attachTo: document.body })
  pendingTeardowns.push(wrapper)
  await flushPromises()
  return wrapper
}

async function mountInGridMode(members = sampleMembers, role = 'admin') {
  localStorage.setItem('pyweb.members.viewMode', 'grid')
  const auth = useAuthStore()
  auth.user = { id: 1, username: 'u', role }
  vi.spyOn(membersApi, 'list').mockResolvedValue(members)
  const wrapper = mount(Members, { attachTo: document.body })
  pendingTeardowns.push(wrapper)
  await flushPromises()
  return wrapper
}

describe('Members.vue', () => {
  it('loads members on mount without a server-side order arg', async () => {
    const list = vi.spyOn(membersApi, 'list').mockResolvedValue(sampleMembers)
    mount(Members)
    await flushPromises()

    // Sorting is now client-side via column headers, so the API wrapper is
    // called with no override.
    expect(list).toHaveBeenCalledWith()
  })

  it('defaults to list view with the view-list toggle active', async () => {
    vi.spyOn(membersApi, 'list').mockResolvedValue(sampleMembers)
    const wrapper = mount(Members)
    await flushPromises()

    expect(wrapper.find('[data-test="view-list"]').classes()).toContain('is-active')
    expect(wrapper.find('[data-test="view-grid"]').classes()).not.toContain('is-active')
    expect(wrapper.findComponent({ name: 'ElTable' }).exists()).toBe(true)
  })

  it('default list view renders el-table with the four sortable columns', async () => {
    vi.spyOn(membersApi, 'list').mockResolvedValue(sampleMembers)
    const wrapper = mount(Members)
    await flushPromises()

    const cols = wrapper.findAllComponents({ name: 'ElTableColumn' })
    const sortable = Object.fromEntries(
      cols
        .filter((c) => c.props('sortable'))
        .map((c) => [c.props('prop'), c.props('sortOrders')]),
    )
    expect(Object.keys(sortable).sort()).toEqual(
      ['current_position', 'graduation_year', 'joined_at', 'real_name'].sort(),
    )
    for (const orders of Object.values(sortable)) {
      expect(orders).toEqual(['ascending', 'descending'])
    }
  })

  it('default list view el-table default-sort is joined_at ascending', async () => {
    vi.spyOn(membersApi, 'list').mockResolvedValue(sampleMembers)
    const wrapper = mount(Members)
    await flushPromises()

    const table = wrapper.findComponent({ name: 'ElTable' })
    expect(table.props('defaultSort')).toEqual({
      prop: 'joined_at',
      order: 'ascending',
    })
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

  it('grid mode exposes sort pills for the four sort keys with joined_at active asc', async () => {
    const wrapper = await mountInGridMode()

    for (const key of ['joined_at', 'graduation_year', 'real_name', 'current_position']) {
      expect(wrapper.find(`[data-test="sort-${key}"]`).exists()).toBe(true)
    }

    const activePill = wrapper.find('[data-test="sort-joined_at"]')
    expect(activePill.classes()).toContain('is-active')
    expect(activePill.text()).toContain('↑')
  })

  it('grid mode: clicking the active sort pill toggles asc <-> desc', async () => {
    const wrapper = await mountInGridMode()

    const pill = wrapper.find('[data-test="sort-joined_at"]')
    expect(pill.text()).toContain('↑')

    await pill.trigger('click')
    expect(pill.text()).toContain('↓')

    await pill.trigger('click')
    expect(pill.text()).toContain('↑')
  })

  it('grid mode: clicking a different sort pill switches the active key (asc default)', async () => {
    const wrapper = await mountInGridMode()

    await wrapper.find('[data-test="sort-graduation_year"]').trigger('click')

    const newActive = wrapper.find('[data-test="sort-graduation_year"]')
    expect(newActive.classes()).toContain('is-active')
    expect(newActive.text()).toContain('↑')
    expect(
      wrapper.find('[data-test="sort-joined_at"]').classes(),
    ).not.toContain('is-active')
  })

  it('grid mode renders one card per member with data-test="member-card"', async () => {
    const wrapper = await mountInGridMode()
    expect(wrapper.findAll('[data-test="member-card"]').length).toBe(2)
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

  it('refresh button re-fetches the list', async () => {
    const list = vi.spyOn(membersApi, 'list').mockResolvedValue([])
    const wrapper = mount(Members)
    await flushPromises()
    list.mockClear()

    await wrapper.find('[data-test="refresh-button"]').trigger('click')
    await flushPromises()

    expect(list).toHaveBeenCalled()
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
    // The disabled placeholder button still renders inside the row.
    expect(wrapper.text()).toContain('履歷')
  })

  it('grid mode shows the empty-state when the member list is empty (admin)', async () => {
    const wrapper = await mountInGridMode([])
    expect(wrapper.find('[data-test="empty-state"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('尚無成員資料')
  })

  it('clicking view-grid toggle switches to card grid and persists to localStorage', async () => {
    vi.spyOn(membersApi, 'list').mockResolvedValue(sampleMembers)
    const wrapper = mount(Members)
    await flushPromises()

    expect(wrapper.findComponent({ name: 'ElTable' }).exists()).toBe(true)
    expect(wrapper.findAll('[data-test="member-card"]').length).toBe(0)

    await wrapper.find('[data-test="view-grid"]').trigger('click')

    expect(wrapper.findComponent({ name: 'ElTable' }).exists()).toBe(false)
    expect(wrapper.findAll('[data-test="member-card"]').length).toBe(2)
    expect(localStorage.getItem('pyweb.members.viewMode')).toBe('grid')
  })

  // ElPopconfirm's confirm/cancel buttons live inside a teleported popper
  // and become flaky to drive through happy-dom once a previous test has
  // mounted+unmounted in the same describe. Emit the events directly on
  // the popconfirm component instead — that's the only seam our handler
  // cares about. We pick the popconfirm by its 「確定要刪除」 title so we
  // don't accidentally fire on the photo-deletion popconfirm.
  function findDeleteMemberPopconfirm(wrapper, realName) {
    return wrapper
      .findAllComponents({ name: 'ElPopconfirm' })
      .find((c) => c.props('title') === `確定要刪除「${realName}」嗎？`)
  }

  it('confirming delete calls membersApi.remove and re-fetches', async () => {
    const wrapper = await mountAsAdmin()
    const remove = vi.spyOn(membersApi, 'remove').mockResolvedValue()
    const list = vi.spyOn(membersApi, 'list').mockResolvedValue(
      sampleMembers.filter((m) => m.id !== 1),
    )

    const popconfirm = findDeleteMemberPopconfirm(wrapper, 'Alice')
    expect(popconfirm).toBeDefined()
    popconfirm.vm.$emit('confirm')
    await flushPromises()

    expect(remove).toHaveBeenCalledWith(1)
    expect(list).toHaveBeenCalled()
  })

  it('cancelling delete does not call remove', async () => {
    const wrapper = await mountAsAdmin()
    const remove = vi.spyOn(membersApi, 'remove').mockResolvedValue()

    const popconfirm = findDeleteMemberPopconfirm(wrapper, 'Alice')
    expect(popconfirm).toBeDefined()
    popconfirm.vm.$emit('cancel')
    await flushPromises()

    expect(remove).not.toHaveBeenCalled()
  })
})
