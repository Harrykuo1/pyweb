import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { membersApi } from '../api/members'
import { useAuthStore } from '../stores/auth'
import DeleteWithPasswordDialog from '../components/DeleteWithPasswordDialog.vue'
import Members from './Members.vue'

vi.mock('element-plus', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    // ElMessage is invoked as a function for the persistent
    // upload/loading toast, plus the regular .success/.error helpers.
    ElMessage: Object.assign(
      vi.fn(() => ({ close: vi.fn() })),
      { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
    ),
  }
})

const replaceMock = vi.fn()
const routeQuery = { value: {} }

vi.mock('vue-router', () => ({
  useRoute: () => ({
    get query() {
      return routeQuery.value
    },
  }),
  useRouter: () => ({ replace: replaceMock }),
}))

const sampleMembers = [
  {
    id: 1,
    graduation_year: 2022,
    real_name: 'Alice',
    institution: 'SWE',
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
    institution: 'PM',
    resume_md: null,
    joined_at: '2023-06-01T00:00:00+00:00',
    has_photo: false,
    has_resume_md: false,
    has_resume_pdf: false,
  },
]

// Richer fixture for the boolean-search tests: positions and years are
// crafted so each operator (AND, OR, NOT, "phrase") has a row that
// matches and one that doesn't.
const booleanSearchMembers = [
  {
    id: 11,
    graduation_year: 2020,
    real_name: 'Alice',
    institution: 'Senior React Developer',
    resume_md: null,
    joined_at: '2020-01-01T00:00:00+00:00',
    has_photo: false,
    has_resume_md: false,
    has_resume_pdf: false,
  },
  {
    id: 12,
    graduation_year: 2021,
    real_name: 'Bob',
    institution: 'Junior React Developer',
    resume_md: null,
    joined_at: '2021-01-01T00:00:00+00:00',
    has_photo: false,
    has_resume_md: false,
    has_resume_pdf: false,
  },
  {
    id: 13,
    graduation_year: 2022,
    real_name: 'Charlie',
    institution: 'Vue Team Lead',
    resume_md: null,
    joined_at: '2022-01-01T00:00:00+00:00',
    has_photo: false,
    has_resume_md: false,
    has_resume_pdf: false,
  },
  {
    id: 14,
    graduation_year: 2023,
    real_name: 'Dave',
    institution: 'Backend Engineer',
    resume_md: null,
    joined_at: '2023-01-01T00:00:00+00:00',
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
  routeQuery.value = {}
  replaceMock.mockClear()
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

async function mountInListMode(members = sampleMembers, role = 'admin') {
  localStorage.setItem('pyweb.members.viewMode', 'list')
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

  it('defaults to grid view with the view-grid toggle active', async () => {
    vi.spyOn(membersApi, 'list').mockResolvedValue(sampleMembers)
    const wrapper = mount(Members)
    await flushPromises()

    expect(wrapper.find('[data-test="view-grid"]').classes()).toContain('is-active')
    expect(wrapper.find('[data-test="view-list"]').classes()).not.toContain('is-active')
    expect(wrapper.findAll('[data-test="member-card"]').length).toBe(2)
  })

  it('list view renders el-table with the five sortable columns', async () => {
    const wrapper = await mountInListMode()

    const cols = wrapper.findAllComponents({ name: 'ElTableColumn' })
    const sortable = Object.fromEntries(
      cols
        .filter((c) => c.props('sortable'))
        .map((c) => [c.props('prop'), c.props('sortOrders')]),
    )
    expect(Object.keys(sortable).sort()).toEqual(
      ['graduation_year', 'institution', 'joined_at', 'position', 'real_name'].sort(),
    )
    for (const orders of Object.values(sortable)) {
      expect(orders).toEqual(['ascending', 'descending'])
    }
  })

  it('list view el-table default-sort is joined_at ascending', async () => {
    const wrapper = await mountInListMode()

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

  it('search input filters the table by name / position / year', async () => {
    const wrapper = await mountInListMode()

    // ElInput exposes the v-model via its component; setValue on it
    // dispatches the right update:modelValue event without relying on
    // happy-dom's combinator selector for the inner <input>.
    const search = wrapper.findComponent('.search-input')
    await search.setValue('alice')
    await flushPromises()

    const table = wrapper.findComponent({ name: 'ElTable' })
    expect(table.props('data')).toHaveLength(1)
    expect(table.props('data')[0].real_name).toBe('Alice')
    expect(wrapper.find('[data-test="search-count"]').text()).toBe('1 / 2')
  })

  it('search shows the no-results table-empty when nothing matches', async () => {
    const wrapper = await mountInListMode()

    const search = wrapper.findComponent('.search-input')
    await search.setValue('nonexistent-zzz')
    await flushPromises()

    const table = wrapper.findComponent({ name: 'ElTable' })
    expect(table.props('data')).toHaveLength(0)
    // EP renders the #empty slot inside the table once data is empty.
    expect(wrapper.text()).toContain('找不到符合')
  })

  // ---------- Boolean search syntax ----------
  // Asserts that the searchQuery parser is actually wired into Members.
  // Per-operator parsing is exhaustively tested in utils/searchQuery.spec.js;
  // here we confirm Members consumes the parser end-to-end.

  async function tableNamesAfterSearch(query) {
    const wrapper = await mountInListMode(booleanSearchMembers)
    const search = wrapper.findComponent('.search-input')
    await search.setValue(query)
    await flushPromises()
    const table = wrapper.findComponent({ name: 'ElTable' })
    return table.props('data').map((m) => m.real_name).sort()
  }

  it('search: implicit AND requires every term', async () => {
    expect(await tableNamesAfterSearch('senior react')).toEqual(['Alice'])
  })

  it('search: uppercase OR splits into groups', async () => {
    expect(await tableNamesAfterSearch('vue OR backend')).toEqual([
      'Charlie',
      'Dave',
    ])
  })

  it('search: dash prefix excludes matching rows', async () => {
    // Both Alice (Senior React) and Bob (Junior React) contain "react",
    // but `-junior` excludes Bob.
    expect(await tableNamesAfterSearch('react -junior')).toEqual(['Alice'])
  })

  it('search: quoted phrase requires contiguous match', async () => {
    expect(await tableNamesAfterSearch('"team lead"')).toEqual(['Charlie'])
  })

  it('search: combined boolean query end-to-end', async () => {
    // (senior AND react) OR (vue AND NOT junior AND "team lead")
    // -> Alice from group 1, Charlie from group 2.
    expect(
      await tableNamesAfterSearch('senior react OR vue -junior "team lead"'),
    ).toEqual(['Alice', 'Charlie'])
  })

  it('grid mode exposes sort pills for the four sort keys with joined_at active asc', async () => {
    vi.spyOn(membersApi, 'list').mockResolvedValue(sampleMembers)
    const wrapper = mount(Members)
    await flushPromises()

    for (const key of ['joined_at', 'graduation_year', 'real_name', 'institution']) {
      expect(wrapper.find(`[data-test="sort-${key}"]`).exists()).toBe(true)
    }

    const activePill = wrapper.find('[data-test="sort-joined_at"]')
    expect(activePill.classes()).toContain('is-active')
    expect(activePill.text()).toContain('↑')
  })

  it('grid mode: clicking the active sort pill toggles asc <-> desc', async () => {
    vi.spyOn(membersApi, 'list').mockResolvedValue(sampleMembers)
    const wrapper = mount(Members)
    await flushPromises()

    const pill = wrapper.find('[data-test="sort-joined_at"]')
    expect(pill.text()).toContain('↑')

    await pill.trigger('click')
    expect(pill.text()).toContain('↓')

    await pill.trigger('click')
    expect(pill.text()).toContain('↑')
  })

  it('grid mode: clicking a different sort pill switches the active key (asc default)', async () => {
    vi.spyOn(membersApi, 'list').mockResolvedValue(sampleMembers)
    const wrapper = mount(Members)
    await flushPromises()

    await wrapper.find('[data-test="sort-graduation_year"]').trigger('click')

    const newActive = wrapper.find('[data-test="sort-graduation_year"]')
    expect(newActive.classes()).toContain('is-active')
    expect(newActive.text()).toContain('↑')
    expect(
      wrapper.find('[data-test="sort-joined_at"]').classes(),
    ).not.toContain('is-active')
  })

  it('grid mode renders one card per member with data-test="member-card"', async () => {
    vi.spyOn(membersApi, 'list').mockResolvedValue(sampleMembers)
    const wrapper = mount(Members)
    await flushPromises()
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
        institution: 'X',
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
    const wrapper = await mountAsAdmin([])
    expect(wrapper.find('[data-test="empty-state"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('尚無成員資料')
  })

  // matchMedia stub: returns matches=true for the phone media query and
  // false otherwise. addEventListener/removeEventListener are no-ops because
  // the test never resizes; we just want the mount-time .matches read to
  // report phone width.
  function stubMatchMediaPhone() {
    const original = window.matchMedia
    window.matchMedia = (q) => ({
      matches: q === '(max-width: 640px)',
      media: q,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false,
      onchange: null,
    })
    return () => {
      window.matchMedia = original
    }
  }

  it('phone breakpoint forces grid view even when localStorage says list', async () => {
    const restore = stubMatchMediaPhone()
    try {
      localStorage.setItem('pyweb.members.viewMode', 'list')
      const auth = useAuthStore()
      auth.user = { id: 1, username: 'a', role: 'admin' }
      vi.spyOn(membersApi, 'list').mockResolvedValue(sampleMembers)

      const wrapper = mount(Members, { attachTo: document.body })
      pendingTeardowns.push(wrapper)
      await flushPromises()

      // Cards rendered, table not.
      expect(wrapper.findAll('[data-test="member-card"]').length).toBe(2)
      expect(wrapper.findComponent({ name: 'ElTable' }).exists()).toBe(false)
      // Stored desktop preference is preserved — only the rendered view
      // is overridden.
      expect(localStorage.getItem('pyweb.members.viewMode')).toBe('list')
    } finally {
      restore()
    }
  })

  it('clicking view-list toggle switches to el-table and persists to localStorage', async () => {
    vi.spyOn(membersApi, 'list').mockResolvedValue(sampleMembers)
    const wrapper = mount(Members)
    await flushPromises()

    expect(wrapper.findAll('[data-test="member-card"]').length).toBe(2)
    expect(wrapper.findComponent({ name: 'ElTable' }).exists()).toBe(false)

    await wrapper.find('[data-test="view-list"]').trigger('click')

    expect(wrapper.findAll('[data-test="member-card"]').length).toBe(0)
    expect(wrapper.findComponent({ name: 'ElTable' }).exists()).toBe(true)
    expect(localStorage.getItem('pyweb.members.viewMode')).toBe('list')
  })

  // The new delete flow: clicking delete-button opens
  // DeleteWithPasswordDialog with the target member's name; the dialog's
  // confirm event carries the typed password. We assert against parent
  // state (the same refs the dialog binds to) because VTU's snapshot of
  // the boolean modelValue prop reads stale once the parent updates the
  // ref. The dialog's own UI behavior is covered in
  // DeleteWithPasswordDialog.spec.js.
  function findDeleteDialog(wrapper) {
    return wrapper.findComponent(DeleteWithPasswordDialog)
  }

  it('clicking delete-button opens the password dialog targeting that row', async () => {
    const wrapper = await mountAsAdmin()
    expect(wrapper.vm.deleteDialogOpen).toBe(false)

    await wrapper.findAll('[data-test="delete-button"]')[0].trigger('click')
    await flushPromises()

    expect(wrapper.vm.deleteDialogOpen).toBe(true)
    expect(wrapper.vm.deleteTarget?.real_name).toBe('Alice')
    expect(findDeleteDialog(wrapper).exists()).toBe(true)
  })

  it('handleDeleteConfirm sends the typed password to the API and re-fetches', async () => {
    const wrapper = await mountAsAdmin()
    const remove = vi.spyOn(membersApi, 'remove').mockResolvedValue()
    const list = vi.spyOn(membersApi, 'list').mockResolvedValue(
      sampleMembers.filter((m) => m.id !== 1),
    )

    // Open via the row's delete-button so deleteTarget is bound to Alice.
    await wrapper.findAll('[data-test="delete-button"]')[0].trigger('click')
    await flushPromises()

    // The dialog's confirm event reaches the parent through the template
    // listener; under VTU we exercise the same parent function directly,
    // since the dialog's own emit is covered in its component spec.
    await wrapper.vm.handleDeleteConfirm('admin-pw')
    await flushPromises()

    expect(remove).toHaveBeenCalledWith(1, 'admin-pw')
    expect(list).toHaveBeenCalled()
    expect(wrapper.vm.deleteDialogOpen).toBe(false)
    expect(wrapper.vm.deleteTarget).toBeNull()
  })

  it('wrong password keeps the dialog open and sets deleteError to 密碼錯誤', async () => {
    const wrapper = await mountAsAdmin()
    vi.spyOn(membersApi, 'remove').mockRejectedValue(
      Object.assign(new Error('422'), { response: { status: 422 } }),
    )

    await wrapper.findAll('[data-test="delete-button"]')[0].trigger('click')
    await flushPromises()

    await wrapper.vm.handleDeleteConfirm('wrong-pw')
    await flushPromises()

    expect(wrapper.vm.deleteDialogOpen).toBe(true)
    expect(wrapper.vm.deleteError).toBe('密碼錯誤')
  })

  // ---------- Photo upload + delete flow (hoisted to page level) ----------

  it('onPhotoUploadRequest opens the crop dialog targeting the member', async () => {
    const wrapper = await mountAsAdmin()
    expect(wrapper.vm.photoCropOpen).toBe(false)

    const file = new File(['x'], 'a.png', { type: 'image/png' })
    wrapper.vm.onPhotoUploadRequest(sampleMembers[0], file)
    await flushPromises()

    expect(wrapper.vm.photoCropOpen).toBe(true)
    expect(wrapper.vm.photoCropTarget?.real_name).toBe('Alice')
    expect(wrapper.vm.photoCropFile?.name).toBe(file.name)
  })

  it('onPhotoCropped uploads the cropped file and reloads the list', async () => {
    const wrapper = await mountAsAdmin()
    const upload = vi.spyOn(membersApi, 'uploadPhoto').mockResolvedValue()
    const list = vi.spyOn(membersApi, 'list').mockResolvedValue(sampleMembers)

    const original = new File(['x'], 'a.png', { type: 'image/png' })
    wrapper.vm.onPhotoUploadRequest(sampleMembers[0], original)
    await flushPromises()

    const cropped = new File(['y'], 'cropped.png', { type: 'image/png' })
    await wrapper.vm.onPhotoCropped(cropped)
    await flushPromises()

    expect(upload).toHaveBeenCalledWith(1, cropped)
    // Reloading the list pulls in the fresh photo_updated_at, which the
    // photo cell uses as its cache-busting URL stamp — no parent-held
    // cache-buster state needed.
    expect(list).toHaveBeenCalled()
    expect(wrapper.vm.photoCropTarget).toBeNull()
    expect(wrapper.vm.photoCropFile).toBeNull()
    expect(wrapper.vm.uploadingPhotoMemberId).toBeNull()
  })

  it('onPhotoDeleteRequest opens the photo-delete dialog targeting the member', async () => {
    const wrapper = await mountAsAdmin()
    expect(wrapper.vm.photoDeleteDialogOpen).toBe(false)

    wrapper.vm.onPhotoDeleteRequest(sampleMembers[0])
    await flushPromises()

    expect(wrapper.vm.photoDeleteDialogOpen).toBe(true)
    expect(wrapper.vm.photoDeleteTarget?.real_name).toBe('Alice')
    expect(wrapper.vm.photoDeleteError).toBe('')
  })

  it('onPhotoDeleteConfirm calls deletePhoto with password and refreshes', async () => {
    const wrapper = await mountAsAdmin()
    const del = vi.spyOn(membersApi, 'deletePhoto').mockResolvedValue()
    const list = vi.spyOn(membersApi, 'list').mockResolvedValue(sampleMembers)

    wrapper.vm.onPhotoDeleteRequest(sampleMembers[0])
    await flushPromises()
    await wrapper.vm.onPhotoDeleteConfirm('admin-pw')
    await flushPromises()

    expect(del).toHaveBeenCalledWith(1, 'admin-pw')
    expect(list).toHaveBeenCalled()
    expect(wrapper.vm.photoDeleteDialogOpen).toBe(false)
    expect(wrapper.vm.photoDeleteTarget).toBeNull()
  })

  it('photo delete on 422 keeps the dialog open and surfaces 密碼錯誤', async () => {
    const wrapper = await mountAsAdmin()
    vi.spyOn(membersApi, 'deletePhoto').mockRejectedValue(
      Object.assign(new Error('422'), { response: { status: 422 } }),
    )

    wrapper.vm.onPhotoDeleteRequest(sampleMembers[0])
    await flushPromises()
    await wrapper.vm.onPhotoDeleteConfirm('wrong-pw')
    await flushPromises()

    expect(wrapper.vm.photoDeleteDialogOpen).toBe(true)
    expect(wrapper.vm.photoDeleteError).toBe('密碼錯誤')
  })

  it('a MemberPhotoCell\'s request-upload event drives the parent\'s crop state', async () => {
    const wrapper = await mountAsAdmin()
    const cell = wrapper.findComponent({ name: 'MemberPhotoCell' })
    expect(cell.exists()).toBe(true)

    const file = new File(['x'], 'b.png', { type: 'image/png' })
    cell.vm.$emit('request-upload', sampleMembers[0], file)
    await flushPromises()

    expect(wrapper.vm.photoCropOpen).toBe(true)
    expect(wrapper.vm.photoCropTarget?.id).toBe(1)
    expect(wrapper.vm.photoCropFile?.name).toBe(file.name)
  })
})

describe('Members.vue — ?focus=<id> deep-link', () => {
  it('adds the is-flash class to the matching member-card on mount', async () => {
    routeQuery.value = { focus: '1' }
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'a', role: 'admin' }
    vi.spyOn(membersApi, 'list').mockResolvedValue(sampleMembers)
    const wrapper = mount(Members, { attachTo: document.body })
    pendingTeardowns.push(wrapper)
    await flushPromises()
    // Watcher on members.length re-attempts focus once the cards are
    // rendered; nudge the queue once more for that pass.
    await flushPromises()

    const focused = wrapper.find('.member-anchor-1')
    expect(focused.exists()).toBe(true)
    expect(focused.classes()).toContain('is-flash')

    const other = wrapper.find('.member-anchor-2')
    expect(other.classes()).not.toContain('is-flash')
  })

  it('strips ?focus= from the URL after consuming it', async () => {
    routeQuery.value = { focus: '1' }
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'a', role: 'admin' }
    vi.spyOn(membersApi, 'list').mockResolvedValue(sampleMembers)
    const wrapper = mount(Members, { attachTo: document.body })
    pendingTeardowns.push(wrapper)
    await flushPromises()

    expect(replaceMock).toHaveBeenCalled()
    const lastCall = replaceMock.mock.calls.at(-1)[0]
    expect(lastCall.query).not.toHaveProperty('focus')
  })

  it('ignores a non-numeric focus value and adds no flash', async () => {
    routeQuery.value = { focus: 'abc' }
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'a', role: 'admin' }
    vi.spyOn(membersApi, 'list').mockResolvedValue(sampleMembers)
    const wrapper = mount(Members, { attachTo: document.body })
    pendingTeardowns.push(wrapper)
    await flushPromises()
    await flushPromises()

    const cards = wrapper.findAll('[data-test="member-card"]')
    for (const card of cards) {
      expect(card.classes()).not.toContain('is-flash')
    }
    expect(replaceMock).not.toHaveBeenCalled()
  })

  it('does not crash when ?focus points at a member not in the loaded list', async () => {
    routeQuery.value = { focus: '999' }
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'a', role: 'admin' }
    vi.spyOn(membersApi, 'list').mockResolvedValue(sampleMembers)
    const wrapper = mount(Members, { attachTo: document.body })
    pendingTeardowns.push(wrapper)
    await flushPromises()
    await flushPromises()

    // Page still renders the cards normally; nothing is flashed.
    const cards = wrapper.findAll('[data-test="member-card"]')
    expect(cards.length).toBe(sampleMembers.length)
    for (const card of cards) {
      expect(card.classes()).not.toContain('is-flash')
    }
  })
})
