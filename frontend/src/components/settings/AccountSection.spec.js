import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { authApi } from '../../api/auth'
import { useAuthStore } from '../../stores/auth'
import AccountSection from './AccountSection.vue'

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

async function mountSection() {
  const auth = useAuthStore()
  auth.user = { id: 1, username: 'admin', role: 'admin' }

  const wrapper = mount(AccountSection, { attachTo: document.body })
  await flushPromises()
  return wrapper
}

function inputBySelector(selector) {
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

describe('AccountSection.vue', () => {
  it('lists both roles and prefills the admin username on mount', async () => {
    await mountSection()

    expect(authApi.listUsers).toHaveBeenCalled()
    expect(document.querySelector('[data-test="account-row-1"]')).not.toBeNull()
    expect(document.querySelector('[data-test="account-row-2"]')).not.toBeNull()
    expect(inputBySelector('[data-test="username-input-admin"]').value).toBe('admin')
  })

  it('selects admin by default with is-active styling', async () => {
    await mountSection()
    const adminRow = document.querySelector('[data-test="account-row-1"]')
    expect(adminRow.classList.contains('is-active')).toBe(true)
  })

  it('clicking the viewer row swaps the detail form to viewer inputs', async () => {
    await mountSection()
    document.querySelector('[data-test="account-row-2"]').click()
    await flushPromises()

    expect(
      document.querySelector('[data-test="username-input-viewer"]'),
    ).not.toBeNull()
    expect(
      document.querySelector('[data-test="username-input-admin"]'),
    ).toBeNull()
    expect(
      document
        .querySelector('[data-test="account-row-2"]')
        .classList.contains('is-active'),
    ).toBe(true)
  })

  it('successful username update calls the store and shows success', async () => {
    const auth = useAuthStore()
    const updateSpy = vi
      .spyOn(auth, 'updateUsername')
      .mockResolvedValue({ id: 1, username: 'commander', role: 'admin' })

    await mountSection()
    setInput('[data-test="username-input-admin"]', 'commander')
    document.querySelector('[data-test="username-submit-admin"]').click()
    await flushPromises()

    expect(updateSpy).toHaveBeenCalledWith('admin', 'commander')
    expect(ElMessage.success).toHaveBeenCalled()
  })

  it('username collision (409) shows specific error', async () => {
    const auth = useAuthStore()
    vi.spyOn(auth, 'updateUsername').mockRejectedValue(
      Object.assign(new Error('409'), { response: { status: 409 } }),
    )

    await mountSection()
    setInput('[data-test="username-input-admin"]', 'taken')
    document.querySelector('[data-test="username-submit-admin"]').click()
    await flushPromises()

    expect(ElMessage.error).toHaveBeenCalledWith('該名稱已被另一個帳號使用')
  })

  it('blocks submit when username is unchanged', async () => {
    const auth = useAuthStore()
    const updateSpy = vi.spyOn(auth, 'updateUsername')

    await mountSection()
    document.querySelector('[data-test="username-submit-admin"]').click()
    await flushPromises()

    expect(updateSpy).not.toHaveBeenCalled()
    expect(ElMessage.info).toHaveBeenCalled()
  })

  it('mismatched password confirm shows error and skips api call', async () => {
    const auth = useAuthStore()
    const updateSpy = vi.spyOn(auth, 'updatePassword')

    await mountSection()
    setInput('[data-test="password-current-admin"]', 'admin-pw')
    setInput('[data-test="password-new-admin"]', 'new-pw')
    setInput('[data-test="password-confirm-admin"]', 'WRONG')
    document.querySelector('[data-test="password-submit-admin"]').click()
    await flushPromises()

    expect(updateSpy).not.toHaveBeenCalled()
    expect(ElMessage.error).toHaveBeenCalledWith('兩次輸入的新密碼不一致')
  })

  it('password update success clears the inputs', async () => {
    const auth = useAuthStore()
    vi.spyOn(auth, 'updatePassword').mockResolvedValue()

    await mountSection()
    setInput('[data-test="password-current-admin"]', 'admin-pw')
    setInput('[data-test="password-new-admin"]', 'new-pw')
    setInput('[data-test="password-confirm-admin"]', 'new-pw')
    document.querySelector('[data-test="password-submit-admin"]').click()
    await flushPromises()

    expect(ElMessage.success).toHaveBeenCalled()
    expect(inputBySelector('[data-test="password-new-admin"]').value).toBe('')
  })

  it('wrong current password (422) shows specific error', async () => {
    const auth = useAuthStore()
    vi.spyOn(auth, 'updatePassword').mockRejectedValue(
      Object.assign(new Error('422'), { response: { status: 422 } }),
    )

    await mountSection()
    setInput('[data-test="password-current-admin"]', 'WRONG')
    setInput('[data-test="password-new-admin"]', 'x')
    setInput('[data-test="password-confirm-admin"]', 'x')
    document.querySelector('[data-test="password-submit-admin"]').click()
    await flushPromises()

    expect(ElMessage.error).toHaveBeenCalledWith('目前管理員密碼不正確')
  })

  it('shows role group headers and a total count', async () => {
    await mountSection()
    // Both role groups render — each gets its uppercase 管理員 / 檢視者 label.
    expect(document.body.textContent).toContain('管理員')
    expect(document.body.textContent).toContain('檢視者')
    expect(
      document.querySelector('[data-test="account-total"]').textContent.trim(),
    ).toBe('2')
  })

  it('two accounts with the same role highlight independently', async () => {
    // Regression: keying rows by role made every same-role account share
    // the active state, so clicking one viewer lit up every viewer.
    vi.restoreAllMocks()
    vi.spyOn(authApi, 'listUsers').mockResolvedValue([
      { id: 1, username: 'admin', role: 'admin' },
      { id: 2, username: 'PY!', role: 'viewer' },
      { id: 3, username: 'viewer', role: 'viewer' },
    ])

    await mountSection()

    const py = document.querySelector('[data-test="account-row-2"]')
    const viewer = document.querySelector('[data-test="account-row-3"]')
    expect(py).not.toBeNull()
    expect(viewer).not.toBeNull()

    py.click()
    await flushPromises()
    expect(py.classList.contains('is-active')).toBe(true)
    expect(viewer.classList.contains('is-active')).toBe(false)

    viewer.click()
    await flushPromises()
    expect(py.classList.contains('is-active')).toBe(false)
    expect(viewer.classList.contains('is-active')).toBe(true)
  })

  it('filters the list by search query and surfaces empty state', async () => {
    const wrapper = await mountSection()

    wrapper.vm.search = 'viewer'
    await flushPromises()
    expect(document.querySelector('[data-test="account-row-2"]')).not.toBeNull()
    expect(document.querySelector('[data-test="account-row-1"]')).toBeNull()

    wrapper.vm.search = 'no-such-account'
    await flushPromises()
    expect(document.querySelector('[data-test="account-empty"]')).not.toBeNull()
  })

  it('password collision (409) shows specific error', async () => {
    const auth = useAuthStore()
    vi.spyOn(auth, 'updatePassword').mockRejectedValue(
      Object.assign(new Error('409'), { response: { status: 409 } }),
    )

    await mountSection()
    setInput('[data-test="password-current-admin"]', 'admin-pw')
    setInput('[data-test="password-new-admin"]', 'viewer-pw')
    setInput('[data-test="password-confirm-admin"]', 'viewer-pw')
    document.querySelector('[data-test="password-submit-admin"]').click()
    await flushPromises()

    expect(ElMessage.error).toHaveBeenCalledWith(
      '新密碼與另一個帳號相同，請改用其他密碼',
    )
  })

  it('password update sends role, current, then new password in order', async () => {
    const auth = useAuthStore()
    const updateSpy = vi.spyOn(auth, 'updatePassword').mockResolvedValue()

    await mountSection()
    setInput('[data-test="password-current-admin"]', 'admin-pw')
    setInput('[data-test="password-new-admin"]', 'fresh-pw')
    setInput('[data-test="password-confirm-admin"]', 'fresh-pw')
    document.querySelector('[data-test="password-submit-admin"]').click()
    await flushPromises()

    expect(updateSpy).toHaveBeenCalledWith('admin', 'admin-pw', 'fresh-pw')
  })

  it('blocks the password submit when a field is incomplete', async () => {
    const auth = useAuthStore()
    const updateSpy = vi.spyOn(auth, 'updatePassword')

    await mountSection()
    // current-password left blank; only the new field filled
    setInput('[data-test="password-new-admin"]', 'fresh-pw')
    document.querySelector('[data-test="password-submit-admin"]').click()
    await flushPromises()

    expect(updateSpy).not.toHaveBeenCalled()
    expect(ElMessage.warning).toHaveBeenCalled()
  })

  it('blocks the username submit when the field is blank', async () => {
    const auth = useAuthStore()
    const updateSpy = vi.spyOn(auth, 'updateUsername')

    await mountSection()
    setInput('[data-test="username-input-admin"]', '   ')  // whitespace only
    document.querySelector('[data-test="username-submit-admin"]').click()
    await flushPromises()

    expect(updateSpy).not.toHaveBeenCalled()
    expect(ElMessage.warning).toHaveBeenCalled()
  })
})
