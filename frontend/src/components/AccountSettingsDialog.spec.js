import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { authApi } from '../api/auth'
import { useAuthStore } from '../stores/auth'
import AccountSettingsDialog from './AccountSettingsDialog.vue'

vi.mock('element-plus', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    ElMessage: {
      success: vi.fn(),
      error: vi.fn(),
      warning: vi.fn(),
      info: vi.fn(),
    },
  }
})

import { ElMessage } from 'element-plus'

beforeEach(() => {
  setActivePinia(createPinia())
  vi.spyOn(authApi, 'listUsers').mockResolvedValue([
    { id: 1, username: 'admin', role: 'admin' },
    { id: 2, username: 'viewer', role: 'viewer' },
  ])
})

afterEach(() => {
  vi.restoreAllMocks()
  document.body.innerHTML = ''
})

async function mountDialog() {
  const auth = useAuthStore()
  auth.user = { id: 1, username: 'admin', role: 'admin' }

  const wrapper = mount(AccountSettingsDialog, {
    props: { modelValue: true },
    attachTo: document.body,
  })
  await flushPromises()
  return wrapper
}

function inputBySelector(selector) {
  // ElInput renders a real <input> inside the wrapper; locate via the parent
  // container with the data-test attribute.
  const host = document.querySelector(selector)
  if (!host) throw new Error(`No DOM node for ${selector}`)
  return host.querySelector('input')
}

function setInput(selector, value) {
  const el = inputBySelector(selector)
  el.value = value
  el.dispatchEvent(new Event('input', { bubbles: true }))
  el.dispatchEvent(new Event('change', { bubbles: true }))
}

describe('AccountSettingsDialog', () => {
  it('loads both accounts on open and prefills usernames', async () => {
    await mountDialog()

    expect(authApi.listUsers).toHaveBeenCalled()
    expect(inputBySelector('[data-test="username-input-admin"]').value).toBe(
      'admin',
    )
  })

  it('successful username update calls store and shows success', async () => {
    const auth = useAuthStore()
    const updateSpy = vi
      .spyOn(auth, 'updateUsername')
      .mockResolvedValue({ id: 2, username: 'watcher', role: 'viewer' })

    const wrapper = await mountDialog()
    // Switch to viewer tab so its inputs render.
    await wrapper.vm.$.exposed
    wrapper.vm.activeTab = 'viewer'
    await flushPromises()

    setInput('[data-test="username-input-viewer"]', 'watcher')
    document.querySelector('[data-test="username-submit-viewer"]').click()
    await flushPromises()

    expect(updateSpy).toHaveBeenCalledWith('viewer', 'watcher')
    expect(ElMessage.success).toHaveBeenCalled()
  })

  it('username collision (409) shows specific error message', async () => {
    const auth = useAuthStore()
    vi.spyOn(auth, 'updateUsername').mockRejectedValue(
      Object.assign(new Error('409'), { response: { status: 409 } }),
    )

    await mountDialog()
    setInput('[data-test="username-input-admin"]', 'someone-else')
    document.querySelector('[data-test="username-submit-admin"]').click()
    await flushPromises()

    expect(ElMessage.error).toHaveBeenCalledWith('該名稱已被另一個帳號使用')
  })

  it('blocks username submit when value is unchanged', async () => {
    const auth = useAuthStore()
    const updateSpy = vi.spyOn(auth, 'updateUsername')

    await mountDialog()
    document.querySelector('[data-test="username-submit-admin"]').click()
    await flushPromises()

    expect(updateSpy).not.toHaveBeenCalled()
    expect(ElMessage.info).toHaveBeenCalled()
  })

  it('password update with mismatched confirm shows error and does not call api', async () => {
    const auth = useAuthStore()
    const updateSpy = vi.spyOn(auth, 'updatePassword')

    await mountDialog()
    setInput('[data-test="password-current-admin"]', 'admin-pw')
    setInput('[data-test="password-new-admin"]', 'new-pw')
    setInput('[data-test="password-confirm-admin"]', 'WRONG')
    document.querySelector('[data-test="password-submit-admin"]').click()
    await flushPromises()

    expect(updateSpy).not.toHaveBeenCalled()
    expect(ElMessage.error).toHaveBeenCalledWith('兩次輸入的新密碼不一致')
  })

  it('password update success calls store and clears inputs', async () => {
    const auth = useAuthStore()
    const updateSpy = vi
      .spyOn(auth, 'updatePassword')
      .mockResolvedValue()

    await mountDialog()
    setInput('[data-test="password-current-admin"]', 'admin-pw')
    setInput('[data-test="password-new-admin"]', 'new-pw')
    setInput('[data-test="password-confirm-admin"]', 'new-pw')
    document.querySelector('[data-test="password-submit-admin"]').click()
    await flushPromises()

    expect(updateSpy).toHaveBeenCalledWith('admin', 'admin-pw', 'new-pw')
    expect(ElMessage.success).toHaveBeenCalled()
    expect(inputBySelector('[data-test="password-new-admin"]').value).toBe('')
  })

  it('password update with wrong current password (401) shows specific error', async () => {
    const auth = useAuthStore()
    vi.spyOn(auth, 'updatePassword').mockRejectedValue(
      Object.assign(new Error('401'), { response: { status: 401 } }),
    )

    await mountDialog()
    setInput('[data-test="password-current-admin"]', 'WRONG')
    setInput('[data-test="password-new-admin"]', 'x')
    setInput('[data-test="password-confirm-admin"]', 'x')
    document.querySelector('[data-test="password-submit-admin"]').click()
    await flushPromises()

    expect(ElMessage.error).toHaveBeenCalledWith('目前管理員密碼不正確')
  })

  it('password update with collision (409) shows specific error', async () => {
    const auth = useAuthStore()
    vi.spyOn(auth, 'updatePassword').mockRejectedValue(
      Object.assign(new Error('409'), { response: { status: 409 } }),
    )

    await mountDialog()
    setInput('[data-test="password-current-admin"]', 'admin-pw')
    setInput('[data-test="password-new-admin"]', 'viewer-pw')
    setInput('[data-test="password-confirm-admin"]', 'viewer-pw')
    document.querySelector('[data-test="password-submit-admin"]').click()
    await flushPromises()

    expect(ElMessage.error).toHaveBeenCalledWith(
      '新密碼與另一個帳號相同，請改用其他密碼',
    )
  })
})
