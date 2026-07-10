import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { computed, nextTick, ref } from 'vue'
import { ElMessageBox } from 'element-plus'

import MemberRoster from './MemberRoster.vue'
import { useMemberRoster } from '../../composables/useMemberRoster'

vi.mock('element-plus', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    ElMessage: Object.assign(
      vi.fn(() => ({ close: vi.fn() })),
      { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
    ),
    ElMessageBox: { confirm: vi.fn() },
  }
})

// The composable is unit-tested on its own; here we stub it so the component
// spec drives deterministic rows and asserts the wiring (filters, per-status
// actions, confirm dialogs, dialog opens, emits).
vi.mock('../../composables/useMemberRoster', () => ({
  useMemberRoster: vi.fn(),
}))

const ROWS = [
  {
    id: 10,
    real_name: '王小明',
    institution: '台大',
    position: '工程師',
    graduation_year: 2020,
    account_status: 'claimed',
    account_id: 1,
    account_discord_username: 'ming',
    role: 'member',
    has_photo: false,
    is_active: true,
  },
  {
    id: 11,
    real_name: '林小美',
    institution: '交大',
    position: '',
    graduation_year: 2021,
    account_status: 'pending',
    account_id: 2,
    account_discord_username: 'mei',
    role: 'member',
    has_photo: false,
    is_active: true,
  },
  {
    id: 12,
    real_name: '陳大文',
    institution: '清大',
    position: 'PM',
    graduation_year: 2019,
    account_status: 'suspended',
    account_id: 3,
    account_discord_username: 'wen',
    role: 'member',
    has_photo: false,
    is_active: false,
  },
  {
    id: 13,
    real_name: '舊資料',
    institution: '成大',
    position: '',
    graduation_year: 2015,
    account_status: 'legacy',
    account_id: null,
    account_discord_username: null,
    role: null,
    has_photo: false,
    is_active: true,
  },
  {
    id: 14,
    real_name: '管理員本人',
    institution: '政大',
    position: '',
    graduation_year: 2018,
    account_status: 'claimed',
    account_id: 4,
    account_discord_username: 'boss',
    role: 'admin',
    has_photo: false,
    is_active: true,
  },
]

let roster

function makeRoster() {
  const rows = ref(ROWS)
  const statusFilter = ref('all')
  const filteredRows = computed(() =>
    statusFilter.value === 'all'
      ? rows.value
      : rows.value.filter((r) => r.account_status === statusFilter.value),
  )
  const counts = computed(() => {
    const c = { all: rows.value.length, claimed: 0, pending: 0, suspended: 0 }
    for (const r of rows.value) {
      if (r.account_status === 'claimed') c.claimed += 1
      else if (r.account_status === 'pending') c.pending += 1
      else if (r.account_status === 'suspended') c.suspended += 1
    }
    return c
  })
  return {
    loading: ref(false),
    rows,
    statusFilter,
    filteredRows,
    counts,
    savingId: ref(null),
    load: vi.fn(),
    reload: vi.fn(),
    // Resolves true on success by default; failure-path tests override it.
    changeRole: vi.fn().mockResolvedValue(true),
    setActive: vi.fn(),
    displayName: (m) => m.real_name,
  }
}

// The role select is remounted (via a bumped :key) whenever a change is
// cancelled or rejected, so it re-reads the row's real role. A fresh component
// instance after the interaction is the observable signal of that remount.
function roleSelectVm(wrapper, id) {
  return wrapper.findComponent(`[data-test="roster-role-${id}"]`).vm
}

// el-table defers its body rows to a post-mount tick, so wait for both the
// microtask queue and a render tick before querying cell content.
async function settle() {
  await nextTick()
  await flushPromises()
  await nextTick()
}

// Stub the heavy dialog children — we only assert their open (modelValue) state.
const stubs = {
  MemberFormDialog: {
    name: 'MemberFormDialog',
    props: ['modelValue', 'member'],
    emits: ['update:modelValue', 'saved'],
    template: '<div data-test="stub-member-form" />',
  },
  DeleteWithPasswordDialog: {
    name: 'DeleteWithPasswordDialog',
    props: [
      'modelValue',
      'itemName',
      'loading',
      'errorMessage',
      'title',
      'warning',
    ],
    emits: ['update:modelValue', 'confirm'],
    template: '<div data-test="stub-delete-dialog" />',
  },
}

async function mountRoster() {
  const wrapper = mount(MemberRoster, { global: { stubs } })
  await settle()
  return wrapper
}

beforeEach(() => {
  setActivePinia(createPinia())
  ElMessageBox.confirm.mockReset()
  ElMessageBox.confirm.mockResolvedValue('confirm')
  roster = makeRoster()
  useMemberRoster.mockReturnValue(roster)
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('MemberRoster.vue', () => {
  it('shows live status counts and filters the table by status', async () => {
    const wrapper = await mountRoster()

    expect(wrapper.find('[data-test="roster-filter-all"]').text()).toContain(
      '5',
    )
    expect(
      wrapper.find('[data-test="roster-filter-claimed"]').text(),
    ).toContain('2')
    expect(
      wrapper.find('[data-test="roster-filter-pending"]').text(),
    ).toContain('1')
    expect(
      wrapper.find('[data-test="roster-filter-suspended"]').text(),
    ).toContain('1')

    // All rows render initially.
    expect(wrapper.find('[data-test="roster-status-11"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="roster-status-10"]').exists()).toBe(true)

    await wrapper.find('[data-test="roster-filter-pending"]').trigger('click')
    await settle()

    expect(wrapper.find('[data-test="roster-status-11"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="roster-status-10"]').exists()).toBe(false)
  })

  it('renders status badges per row', async () => {
    const wrapper = await mountRoster()
    expect(wrapper.find('[data-test="roster-status-11"]').text()).toContain(
      '尚未加入',
    )
    expect(wrapper.find('[data-test="roster-status-12"]').text()).toContain(
      '已停權',
    )
  })

  it('renders status-driven actions per account_status', async () => {
    const wrapper = await mountRoster()

    // claimed member (10): role select + suspend + edit
    expect(wrapper.find('[data-test="roster-role-10"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="roster-suspend-10"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="roster-edit-10"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="roster-delete-10"]').exists()).toBe(false)

    // pending (11): edit + delete, no role select
    expect(wrapper.find('[data-test="roster-role-11"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="roster-edit-11"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="roster-delete-11"]').exists()).toBe(true)

    // suspended (12): reactivate + edit
    expect(wrapper.find('[data-test="roster-reactivate-12"]').exists()).toBe(
      true,
    )
    expect(wrapper.find('[data-test="roster-edit-12"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="roster-suspend-12"]').exists()).toBe(false)

    // legacy (13): edit + delete
    expect(wrapper.find('[data-test="roster-edit-13"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="roster-delete-13"]').exists()).toBe(true)
  })

  it('hides 停權 for a claimed member whose role is already admin', async () => {
    const wrapper = await mountRoster()
    expect(wrapper.find('[data-test="roster-role-14"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="roster-suspend-14"]').exists()).toBe(false)
  })

  it('clicking 停權 confirms then calls setActive(member, false)', async () => {
    const wrapper = await mountRoster()
    await wrapper.find('[data-test="roster-suspend-10"]').trigger('click')
    await flushPromises()

    expect(ElMessageBox.confirm).toHaveBeenCalledTimes(1)
    expect(roster.setActive).toHaveBeenCalledWith(
      expect.objectContaining({ id: 10 }),
      false,
    )
  })

  it('does not suspend when the confirm is cancelled', async () => {
    ElMessageBox.confirm.mockRejectedValue('cancel')
    const wrapper = await mountRoster()
    await wrapper.find('[data-test="roster-suspend-10"]').trigger('click')
    await flushPromises()

    expect(ElMessageBox.confirm).toHaveBeenCalledTimes(1)
    expect(roster.setActive).not.toHaveBeenCalled()
  })

  it('clicking 復權 calls setActive(member, true) without a confirm', async () => {
    const wrapper = await mountRoster()
    await wrapper.find('[data-test="roster-reactivate-12"]').trigger('click')
    await flushPromises()

    expect(ElMessageBox.confirm).not.toHaveBeenCalled()
    expect(roster.setActive).toHaveBeenCalledWith(
      expect.objectContaining({ id: 12 }),
      true,
    )
  })

  it('promoting to admin confirms then calls changeRole(member, admin)', async () => {
    const wrapper = await mountRoster()
    const select = wrapper.findComponent('[data-test="roster-role-10"]')
    await select.vm.$emit('change', 'admin')
    await flushPromises()

    expect(ElMessageBox.confirm).toHaveBeenCalledTimes(1)
    expect(roster.changeRole).toHaveBeenCalledWith(
      expect.objectContaining({ id: 10 }),
      'admin',
    )
  })

  it('does not promote when the confirm is cancelled, and resets the select', async () => {
    ElMessageBox.confirm.mockRejectedValue('cancel')
    const wrapper = await mountRoster()
    const before = roleSelectVm(wrapper, 10)
    const select = wrapper.findComponent('[data-test="roster-role-10"]')
    await select.vm.$emit('change', 'admin')
    await flushPromises()
    await nextTick()

    expect(ElMessageBox.confirm).toHaveBeenCalledTimes(1)
    expect(roster.changeRole).not.toHaveBeenCalled()
    // Select was remounted, snapping its display back to the row's real role.
    expect(roleSelectVm(wrapper, 10)).not.toBe(before)
  })

  it('demoting to member calls changeRole without a confirm', async () => {
    const wrapper = await mountRoster()
    const select = wrapper.findComponent('[data-test="roster-role-14"]')
    await select.vm.$emit('change', 'member')
    await flushPromises()

    expect(ElMessageBox.confirm).not.toHaveBeenCalled()
    expect(roster.changeRole).toHaveBeenCalledWith(
      expect.objectContaining({ id: 14 }),
      'member',
    )
  })

  it('resets the select when the backend rejects a role change', async () => {
    // A demote (admin -> member) that the backend rejects: no confirm, but the
    // select must snap back to the row's real role instead of showing 成員.
    roster.changeRole.mockResolvedValue(false)
    const wrapper = await mountRoster()
    const before = roleSelectVm(wrapper, 14)
    const select = wrapper.findComponent('[data-test="roster-role-14"]')
    await select.vm.$emit('change', 'member')
    await flushPromises()
    await nextTick()

    expect(roster.changeRole).toHaveBeenCalledWith(
      expect.objectContaining({ id: 14 }),
      'member',
    )
    // Row role is unchanged (the composable never patched it) and the select
    // was remounted to re-read it.
    expect(roleSelectVm(wrapper, 14)).not.toBe(before)
  })

  it('新增成員 opens the member form dialog with a null member', async () => {
    const wrapper = await mountRoster()
    const form = wrapper.findComponent({ name: 'MemberFormDialog' })
    expect(form.props('modelValue')).toBe(false)

    await wrapper.find('[data-test="roster-add-member"]').trigger('click')

    expect(form.props('modelValue')).toBe(true)
    expect(form.props('member')).toBeNull()
  })

  it('編輯 opens the member form dialog targeting the row', async () => {
    const wrapper = await mountRoster()
    await wrapper.find('[data-test="roster-edit-10"]').trigger('click')

    const form = wrapper.findComponent({ name: 'MemberFormDialog' })
    expect(form.props('modelValue')).toBe(true)
    expect(form.props('member')).toMatchObject({ id: 10 })
  })

  it('刪除 opens the password-confirmed delete dialog', async () => {
    const wrapper = await mountRoster()
    const del = wrapper.findComponent({ name: 'DeleteWithPasswordDialog' })
    expect(del.props('modelValue')).toBe(false)

    await wrapper.find('[data-test="roster-delete-11"]').trigger('click')

    expect(del.props('modelValue')).toBe(true)
    expect(del.props('itemName')).toBe('林小美')
  })

  it('emits generate-invite from the toolbar button', async () => {
    const wrapper = await mountRoster()
    await wrapper.find('[data-test="roster-generate-invite"]').trigger('click')
    expect(wrapper.emitted('generate-invite')).toBeTruthy()
  })
})
