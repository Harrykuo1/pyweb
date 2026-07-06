import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { ElMessage } from 'element-plus'

import { useUserRoles } from './useUserRoles'
import { authApi } from '../api/auth'

vi.mock('element-plus', () => ({
  ElMessage: Object.assign(vi.fn(), {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
  }),
}))

const USERS = [
  {
    id: 1,
    username: 'admin',
    role: 'admin',
    discord_username: 'adminhandle',
    discord_global_name: 'Admin Global',
    has_profile: true,
    member_id: 10,
  },
  {
    id: 2,
    username: 'viewer',
    role: 'viewer',
    discord_username: 'viewerhandle',
    discord_global_name: null,
    has_profile: false,
    member_id: null,
  },
]

// Host component so the composable's onMounted(load) runs.
function mountUserRoles() {
  let api
  const Host = {
    setup() {
      api = useUserRoles()
      return () => null
    },
  }
  const wrapper = mount(Host)
  return { wrapper, get: () => api }
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.spyOn(authApi, 'listUsers').mockResolvedValue(USERS)
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('useUserRoles', () => {
  it('loads users on mount', async () => {
    const { get } = mountUserRoles()
    await flushPromises()
    const a = get()
    expect(a.users.value).toHaveLength(2)
    expect(a.users.value[0].username).toBe('admin')
    expect(a.loading.value).toBe(false)
  })

  it('displayName falls back member name → global name → handle → username → #id', async () => {
    const { get } = mountUserRoles()
    await flushPromises()
    const { displayName } = get()
    expect(
      displayName({
        id: 9,
        member_name: '王小明',
        discord_global_name: 'Global',
        discord_username: 'handle',
        username: 'seed',
      }),
    ).toBe('王小明')
    expect(
      displayName({
        id: 9,
        member_name: null,
        discord_global_name: 'Global',
        discord_username: 'handle',
        username: 'seed',
      }),
    ).toBe('Global')
    expect(
      displayName({
        id: 9,
        discord_global_name: null,
        discord_username: 'handle',
        username: 'seed',
      }),
    ).toBe('handle')
    expect(
      displayName({
        id: 9,
        discord_global_name: null,
        discord_username: null,
        username: 'seed',
      }),
    ).toBe('seed')
    expect(
      displayName({
        id: 9,
        discord_global_name: null,
        discord_username: null,
        username: null,
      }),
    ).toBe('#9')
  })

  it('changeRole replaces the user and calls assignRole with (id, role)', async () => {
    const { get } = mountUserRoles()
    await flushPromises()
    const a = get()
    const updated = { ...USERS[1], role: 'member' }
    const spy = vi.spyOn(authApi, 'assignRole').mockResolvedValue(updated)

    await a.changeRole(a.users.value[1], 'member')

    expect(spy).toHaveBeenCalledWith(2, 'member')
    expect(a.users.value[1].role).toBe('member')
    expect(a.savingId.value).toBeNull()
  })

  it('changeRole surfaces the backend 409 detail and leaves the list unchanged', async () => {
    const { get } = mountUserRoles()
    await flushPromises()
    const a = get()
    const before = a.users.value.map((u) => u.role)
    vi.spyOn(authApi, 'assignRole').mockRejectedValue({
      response: {
        status: 409,
        data: { detail: 'Cannot demote the last admin' },
      },
    })

    await a.changeRole(a.users.value[0], 'member')

    expect(ElMessage.error).toHaveBeenCalledWith('Cannot demote the last admin')
    expect(a.users.value.map((u) => u.role)).toEqual(before)
    expect(a.savingId.value).toBeNull()
  })

  it('changeRole is a no-op when the role is unchanged', async () => {
    const { get } = mountUserRoles()
    await flushPromises()
    const a = get()
    const spy = vi.spyOn(authApi, 'assignRole')
    await a.changeRole(a.users.value[0], 'admin')
    expect(spy).not.toHaveBeenCalled()
  })
})
