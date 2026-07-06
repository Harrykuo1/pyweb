import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { ElMessage } from 'element-plus'

import { useRegistrationInvites } from './useRegistrationInvites'
import { authApi } from '../api/auth'

vi.mock('element-plus', () => ({
  ElMessage: Object.assign(
    vi.fn(() => ({ close: vi.fn() })),
    {
      success: vi.fn(),
      error: vi.fn(),
      warning: vi.fn(),
      info: vi.fn(),
    },
  ),
}))

// Fixed ISO strings so status() is deterministic without mocking Date.now —
// the past date is unambiguously < now, the far-future date unambiguously > .
const ACTIVE = {
  id: 1,
  token: 'tok-active',
  created_at: '2026-07-06T00:00:00.000Z',
  expires_at: '2999-01-01T00:00:00.000Z',
  used_at: null,
  used_by_user_id: null,
}
const USED = {
  id: 2,
  token: 'tok-used',
  created_at: '2026-07-05T00:00:00.000Z',
  expires_at: '2999-01-01T00:00:00.000Z',
  used_at: '2026-07-05T01:00:00.000Z',
  used_by_user_id: 7,
}
const EXPIRED = {
  id: 3,
  token: 'tok-expired',
  created_at: '2020-01-01T00:00:00.000Z',
  expires_at: '2020-01-03T00:00:00.000Z',
  used_at: null,
  used_by_user_id: null,
}

// Host component so the composable's onMounted(load) runs.
function mountInvites() {
  let api
  const Host = {
    setup() {
      api = useRegistrationInvites()
      return () => null
    },
  }
  const wrapper = mount(Host)
  return { wrapper, get: () => api }
}

beforeEach(() => {
  vi.clearAllMocks()
  setActivePinia(createPinia())
  vi.spyOn(authApi, 'listRegistrationInvites').mockResolvedValue([ACTIVE, USED])
  // happy-dom exposes navigator.clipboard as a getter-only property, so a
  // plain assignment throws — define it as a configurable value instead.
  Object.defineProperty(globalThis.navigator, 'clipboard', {
    value: { writeText: vi.fn().mockResolvedValue() },
    configurable: true,
    writable: true,
  })
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('useRegistrationInvites', () => {
  it('loads invites on mount', async () => {
    const { get } = mountInvites()
    await flushPromises()
    const a = get()
    expect(a.invites.value).toHaveLength(2)
    expect(a.invites.value[0].token).toBe('tok-active')
    expect(a.loading.value).toBe(false)
  })

  it('surfaces a toast and keeps the list empty when load fails', async () => {
    authApi.listRegistrationInvites.mockRejectedValueOnce(new Error('boom'))
    const { get } = mountInvites()
    await flushPromises()
    expect(get().invites.value).toEqual([])
    expect(ElMessage.error).toHaveBeenCalledWith('載入邀請連結失敗')
  })

  it('create() prepends the new invite and toasts success', async () => {
    const created = { ...ACTIVE, id: 99, token: 'tok-new' }
    vi.spyOn(authApi, 'createRegistrationInvite').mockResolvedValue(created)
    const { get } = mountInvites()
    await flushPromises()
    const a = get()

    await a.create()

    expect(a.invites.value).toHaveLength(3)
    expect(a.invites.value[0].token).toBe('tok-new')
    expect(a.creating.value).toBe(false)
    expect(ElMessage.success).toHaveBeenCalledWith('已產生邀請連結')
  })

  it('create() toasts an error and keeps the list on failure', async () => {
    vi.spyOn(authApi, 'createRegistrationInvite').mockRejectedValue(
      new Error('nope'),
    )
    const { get } = mountInvites()
    await flushPromises()
    const a = get()

    await a.create()

    expect(a.invites.value).toHaveLength(2)
    expect(ElMessage.error).toHaveBeenCalledWith('產生失敗，請稍後再試')
  })

  it('status()/statusLabel() classify used, expired and active', async () => {
    const { get } = mountInvites()
    await flushPromises()
    const a = get()

    expect(a.status(USED)).toBe('used')
    expect(a.statusLabel(USED)).toBe('已使用')
    expect(a.status(EXPIRED)).toBe('expired')
    expect(a.statusLabel(EXPIRED)).toBe('已過期')
    expect(a.status(ACTIVE)).toBe('active')
    expect(a.statusLabel(ACTIVE)).toBe('可使用')
  })

  it('inviteUrl() targets the Discord register endpoint with the token', async () => {
    const { get } = mountInvites()
    await flushPromises()
    const a = get()

    expect(a.inviteUrl(ACTIVE)).toBe(
      `${window.location.origin}/api/auth/discord/register?token=tok-active`,
    )
  })

  it('copy() writes the invite URL to the clipboard and toasts success', async () => {
    const { get } = mountInvites()
    await flushPromises()
    const a = get()

    await a.copy(ACTIVE)

    expect(globalThis.navigator.clipboard.writeText).toHaveBeenCalledWith(
      a.inviteUrl(ACTIVE),
    )
    expect(ElMessage.success).toHaveBeenCalledWith('已複製連結')
  })

  it('copy() toasts an error when the clipboard write rejects', async () => {
    globalThis.navigator.clipboard.writeText.mockRejectedValueOnce(
      new Error('denied'),
    )
    const { get } = mountInvites()
    await flushPromises()
    const a = get()

    await a.copy(ACTIVE)

    expect(ElMessage.error).toHaveBeenCalledWith('複製失敗')
  })
})
