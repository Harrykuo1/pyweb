import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { ElMessage, ElMessageBox } from 'element-plus'

import { usePendingLinks } from './usePendingLinks'
import { authApi } from '../api/auth'
import { membersApi } from '../api/members'

vi.mock('element-plus', () => ({
  ElMessage: Object.assign(
    vi.fn(() => ({ close: vi.fn() })),
    {
      success: vi.fn(),
      error: vi.fn(),
      info: vi.fn(),
      warning: vi.fn(),
    },
  ),
  ElMessageBox: { confirm: vi.fn() },
}))

const LINKS = [
  {
    id: 1,
    discord_id: '111',
    discord_username: 'ada',
    discord_global_name: 'Ada Lovelace',
    first_seen_at: '2026-07-01T10:00:00Z',
  },
  {
    id: 2,
    discord_id: '222',
    discord_username: null,
    discord_global_name: null,
    first_seen_at: '2026-07-02T10:00:00Z',
  },
]

const MEMBERS = [
  { id: 10, real_name: '王小明', graduation_year: 2020, institution: 'NTU' },
  { id: 11, real_name: '陳大文', graduation_year: 2021, institution: 'NCU' },
]

// Host component so the composable's onMounted(load) runs.
function mountPendingLinks() {
  let api
  const Host = {
    setup() {
      api = usePendingLinks()
      return () => null
    },
  }
  const wrapper = mount(Host)
  return { wrapper, get: () => api }
}

beforeEach(() => {
  vi.clearAllMocks()
  setActivePinia(createPinia())
  vi.spyOn(authApi, 'listPendingLinks').mockResolvedValue(LINKS)
  vi.spyOn(membersApi, 'list').mockResolvedValue(MEMBERS)
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('usePendingLinks', () => {
  it('loads pending links and members on mount', async () => {
    const { get } = mountPendingLinks()
    await flushPromises()
    const a = get()
    expect(authApi.listPendingLinks).toHaveBeenCalled()
    expect(membersApi.list).toHaveBeenCalled()
    expect(a.links.value).toHaveLength(2)
    expect(a.members.value).toHaveLength(2)
    expect(a.loading.value).toBe(false)
  })

  it('resolve warns and does not call the API when no member is picked', async () => {
    const { get } = mountPendingLinks()
    await flushPromises()
    const a = get()
    const spy = vi.spyOn(authApi, 'resolvePendingLink')

    await a.resolve(a.links.value[0])

    expect(ElMessage.warning).toHaveBeenCalledWith('請先選擇要連結的成員')
    expect(spy).not.toHaveBeenCalled()
    expect(a.links.value).toHaveLength(2)
  })

  it('resolve links the picked member, removes the row, and toasts success', async () => {
    const { get } = mountPendingLinks()
    await flushPromises()
    const a = get()
    const spy = vi.spyOn(authApi, 'resolvePendingLink').mockResolvedValue({})
    a.picked['111'] = 10

    await a.resolve(a.links.value[0])

    expect(spy).toHaveBeenCalledWith('111', 10)
    expect(a.links.value.find((l) => l.discord_id === '111')).toBeUndefined()
    expect(a.links.value).toHaveLength(1)
    expect(ElMessage.success).toHaveBeenCalledWith('已完成連結')
    expect(a.resolvingId.value).toBe(null)
  })

  it('resolve surfaces the backend detail on 409 and keeps the row', async () => {
    const { get } = mountPendingLinks()
    await flushPromises()
    const a = get()
    vi.spyOn(authApi, 'resolvePendingLink').mockRejectedValue({
      response: { status: 409, data: { detail: 'Member already linked' } },
    })
    a.picked['111'] = 10

    await a.resolve(a.links.value[0])

    expect(ElMessage.error).toHaveBeenCalledWith('Member already linked')
    expect(a.links.value.find((l) => l.discord_id === '111')).toBeTruthy()
    expect(a.links.value).toHaveLength(2)
    expect(a.resolvingId.value).toBe(null)
  })

  it('dismiss deletes the pending link after confirm and removes the row', async () => {
    const { get } = mountPendingLinks()
    await flushPromises()
    const a = get()
    ElMessageBox.confirm.mockResolvedValue('confirm')
    const spy = vi.spyOn(authApi, 'deletePendingLink').mockResolvedValue()

    await a.dismiss(a.links.value[0])

    expect(spy).toHaveBeenCalledWith('111')
    expect(a.links.value.find((l) => l.discord_id === '111')).toBeUndefined()
    expect(ElMessage.success).toHaveBeenCalledWith('已忽略')
  })

  it('dismiss does nothing when the confirm is cancelled', async () => {
    const { get } = mountPendingLinks()
    await flushPromises()
    const a = get()
    ElMessageBox.confirm.mockRejectedValue('cancel')
    const spy = vi.spyOn(authApi, 'deletePendingLink').mockResolvedValue()

    await a.dismiss(a.links.value[0])

    expect(spy).not.toHaveBeenCalled()
    expect(a.links.value).toHaveLength(2)
  })
})
