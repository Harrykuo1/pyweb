import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { ElMessage } from 'element-plus'

import { useGuildConfig } from './useGuildConfig'
import { authApi } from '../api/auth'

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
}))

const GUILD_ID = '123456789012345678' // 18-digit snowflake

// Host component so the composable's onMounted(load) runs.
function mountGuild() {
  let api
  const Host = {
    setup() {
      api = useGuildConfig()
      return () => null
    },
  }
  const wrapper = mount(Host)
  return { wrapper, get: () => api }
}

beforeEach(() => {
  vi.clearAllMocks()
  setActivePinia(createPinia())
  vi.spyOn(authApi, 'getGuildConfig').mockResolvedValue({ guild_id: GUILD_ID })
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('useGuildConfig', () => {
  it('load() populates guildId and original from getGuildConfig', async () => {
    const { get } = mountGuild()
    await flushPromises()
    const g = get()
    expect(g.guildId.value).toBe(GUILD_ID)
    // original isn't exposed; dirty === false proves guildId === original.
    expect(g.dirty.value).toBe(false)
    expect(g.loading.value).toBe(false)
  })

  it('dirty flips when guildId changes', async () => {
    const { get } = mountGuild()
    await flushPromises()
    const g = get()
    expect(g.dirty.value).toBe(false)
    g.guildId.value = '999888777666555444'
    expect(g.dirty.value).toBe(true)
  })

  it('valid is false for empty / non-numeric / too-short, true for 19 digits', async () => {
    const { get } = mountGuild()
    await flushPromises()
    const g = get()
    g.guildId.value = ''
    expect(g.valid.value).toBe(false)
    g.guildId.value = 'abc'
    expect(g.valid.value).toBe(false)
    g.guildId.value = '12345'
    expect(g.valid.value).toBe(false)
    g.guildId.value = '1234567890123456789' // 19 digits
    expect(g.valid.value).toBe(true)
  })

  it('save() with an invalid value errors and does not call setGuildConfig', async () => {
    const { get } = mountGuild()
    await flushPromises()
    const g = get()
    const spy = vi.spyOn(authApi, 'setGuildConfig')
    g.guildId.value = 'not-a-snowflake'
    await g.save()
    expect(spy).not.toHaveBeenCalled()
    expect(ElMessage.error).toHaveBeenCalledWith('群組 ID 必須是 17–20 位數字')
  })

  it('save() success calls setGuildConfig, updates original, toasts success', async () => {
    const { get } = mountGuild()
    await flushPromises()
    const g = get()
    const next = '987654321098765432'
    const spy = vi
      .spyOn(authApi, 'setGuildConfig')
      .mockResolvedValue({ guild_id: next })
    g.guildId.value = next
    await g.save()
    expect(spy).toHaveBeenCalledWith(next)
    expect(g.guildId.value).toBe(next)
    // dirty === false after save proves original was advanced to next too.
    expect(g.dirty.value).toBe(false)
    expect(ElMessage.success).toHaveBeenCalledWith('已更新 Discord 群組')
  })

  it('save() surfaces the backend error detail on rejection', async () => {
    const { get } = mountGuild()
    await flushPromises()
    const g = get()
    vi.spyOn(authApi, 'setGuildConfig').mockRejectedValue({
      response: { data: { detail: '找不到該群組' } },
    })
    g.guildId.value = '987654321098765432'
    await g.save()
    expect(ElMessage.error).toHaveBeenCalledWith('找不到該群組')
  })

  it('reset() restores the original value', async () => {
    const { get } = mountGuild()
    await flushPromises()
    const g = get()
    g.guildId.value = '000111222333444555'
    expect(g.dirty.value).toBe(true)
    g.reset()
    expect(g.guildId.value).toBe(GUILD_ID)
    expect(g.dirty.value).toBe(false)
  })
})
