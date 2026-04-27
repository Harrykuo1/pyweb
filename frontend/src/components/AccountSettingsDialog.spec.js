import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { authApi } from '../api/auth'
import { settingsApi } from '../api/settings'
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

  // ---------- site / login_logo tab ----------

  async function openSiteTab(wrapper) {
    wrapper.vm.activeTab = 'site'
    await flushPromises()
  }

  function makeFile(name, type, size = 16) {
    const buf = new Uint8Array(size)
    return new File([buf], name, { type })
  }

  it('site tab shows placeholder when no logo is set', async () => {
    const wrapper = await mountDialog()
    await openSiteTab(wrapper)
    // logoExists starts false; probeLogo's onerror fires async — by default
    // happy-dom can't load the URL, so the placeholder stays visible.
    expect(
      document.querySelector('[data-test="logo-current-img"]'),
    ).toBeNull()
    expect(
      document.querySelector('[data-test="logo-delete"]'),
    ).toBeNull()
  })

  it('selecting an unsupported file type shows error and clears preview', async () => {
    const wrapper = await mountDialog()
    await openSiteTab(wrapper)

    const input = document.querySelector('[data-test="logo-file-input"]')
    const file = makeFile('evil.exe', 'application/octet-stream')
    Object.defineProperty(input, 'files', { value: [file], configurable: true })
    input.dispatchEvent(new Event('change', { bubbles: true }))
    await flushPromises()

    expect(ElMessage.error).toHaveBeenCalledWith('僅支援 PNG / JPEG / WebP / SVG')
    expect(
      document.querySelector('[data-test="logo-pending-img"]'),
    ).toBeNull()
  })

  it('selecting an oversized file shows error', async () => {
    const wrapper = await mountDialog()
    await openSiteTab(wrapper)

    const input = document.querySelector('[data-test="logo-file-input"]')
    const file = makeFile('big.png', 'image/png', 2 * 1024 * 1024 + 1)
    Object.defineProperty(input, 'files', { value: [file], configurable: true })
    input.dispatchEvent(new Event('change', { bubbles: true }))
    await flushPromises()

    expect(ElMessage.error).toHaveBeenCalledWith('圖片不可超過 2 MB')
  })

  // SVG bypasses cropping, so picking an SVG file goes straight to "pending"
  // — used as a shortcut by the next handful of tests that want to skip the
  // crop step. The crop flow itself is exercised in dedicated tests below.
  function pickSvg(name = 'logo.svg', size = 16) {
    const input = document.querySelector('[data-test="logo-file-input"]')
    const file = makeFile(name, 'image/svg+xml', size)
    Object.defineProperty(input, 'files', { value: [file], configurable: true })
    input.dispatchEvent(new Event('change', { bubbles: true }))
    return file
  }

  it('selecting a valid SVG shows pending preview and enables upload', async () => {
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:fake')
    const wrapper = await mountDialog()
    await openSiteTab(wrapper)

    pickSvg()
    await flushPromises()

    const preview = document.querySelector('[data-test="logo-pending-img"]')
    expect(preview).not.toBeNull()
    expect(preview.getAttribute('src')).toBe('blob:fake')

    const uploadBtn = document.querySelector('[data-test="logo-upload"]')
    expect(uploadBtn.disabled).toBe(false)
  })

  it('upload calls settingsApi.uploadImage and marks logoExists', async () => {
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:fake')
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {})
    const upload = vi
      .spyOn(settingsApi, 'uploadImage')
      .mockResolvedValue({
        key: 'login_logo',
        size: 16,
        content_type: 'image/svg+xml',
      })

    const wrapper = await mountDialog()
    await openSiteTab(wrapper)

    const file = pickSvg()
    await flushPromises()

    document.querySelector('[data-test="logo-upload"]').click()
    await flushPromises()

    expect(upload).toHaveBeenCalledWith('login_logo', file)
    expect(ElMessage.success).toHaveBeenCalledWith('登入頁 Logo 已更新')
    expect(
      document.querySelector('[data-test="logo-pending-img"]'),
    ).toBeNull()
    expect(
      document.querySelector('[data-test="logo-delete"]'),
    ).not.toBeNull()
  })

  it('upload error 415 shows specific message', async () => {
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:fake')
    vi.spyOn(settingsApi, 'uploadImage').mockRejectedValue(
      Object.assign(new Error('415'), { response: { status: 415 } }),
    )

    const wrapper = await mountDialog()
    await openSiteTab(wrapper)

    pickSvg()
    await flushPromises()

    document.querySelector('[data-test="logo-upload"]').click()
    await flushPromises()

    expect(ElMessage.error).toHaveBeenCalledWith('不支援的檔案格式')
  })

  it('delete calls settingsApi.deleteImage and hides current logo', async () => {
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:fake')
    vi.spyOn(settingsApi, 'uploadImage').mockResolvedValue({
      key: 'login_logo',
      size: 16,
      content_type: 'image/svg+xml',
    })
    const del = vi.spyOn(settingsApi, 'deleteImage').mockResolvedValue()

    const wrapper = await mountDialog()
    await openSiteTab(wrapper)

    pickSvg()
    await flushPromises()
    document.querySelector('[data-test="logo-upload"]').click()
    await flushPromises()

    document.querySelector('[data-test="logo-delete"]').click()
    await flushPromises()

    expect(del).toHaveBeenCalledWith('login_logo')
    expect(ElMessage.success).toHaveBeenCalledWith('已恢復為預設圖示')
    expect(
      document.querySelector('[data-test="logo-current-img"]'),
    ).toBeNull()
    expect(
      document.querySelector('[data-test="logo-delete"]'),
    ).toBeNull()
  })

  it('picking a PNG opens the crop dialog and does NOT show a pending preview yet', async () => {
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:fake')
    const wrapper = await mountDialog()
    await openSiteTab(wrapper)

    const input = document.querySelector('[data-test="logo-file-input"]')
    const file = makeFile('logo.png', 'image/png')
    Object.defineProperty(input, 'files', { value: [file], configurable: true })
    input.dispatchEvent(new Event('change', { bubbles: true }))
    await flushPromises()

    expect(wrapper.vm.cropOpen).toBe(true)
    expect(wrapper.vm.cropSourceFile?.name).toBe('logo.png')
    // PNG output type preserves transparency.
    expect(wrapper.vm.cropOutputType).toBe('image/png')
    // No pending preview rendered until the user confirms the crop.
    expect(
      document.querySelector('[data-test="logo-pending-img"]'),
    ).toBeNull()
  })

  it('picking a JPEG sets crop output type to image/jpeg', async () => {
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:fake')
    const wrapper = await mountDialog()
    await openSiteTab(wrapper)

    const input = document.querySelector('[data-test="logo-file-input"]')
    const file = makeFile('photo.jpg', 'image/jpeg')
    Object.defineProperty(input, 'files', { value: [file], configurable: true })
    input.dispatchEvent(new Event('change', { bubbles: true }))
    await flushPromises()

    expect(wrapper.vm.cropOutputType).toBe('image/jpeg')
  })

  it('confirming the crop swaps in the cropped file as the pending preview', async () => {
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:cropped')
    const wrapper = await mountDialog()
    await openSiteTab(wrapper)

    // Simulate the upstream flow without going through the real cropper.
    const cropped = makeFile('cropped.png', 'image/png', 32)
    wrapper.vm.onCropConfirmed(cropped)
    await flushPromises()

    const preview = document.querySelector('[data-test="logo-pending-img"]')
    expect(preview).not.toBeNull()
    expect(preview.getAttribute('src')).toBe('blob:cropped')
    expect(wrapper.vm.pendingLogoFile?.name).toBe('cropped.png')
  })

  it('upload without selecting a file warns and does not call api', async () => {
    const upload = vi.spyOn(settingsApi, 'uploadImage')
    const wrapper = await mountDialog()
    await openSiteTab(wrapper)

    const btn = document.querySelector('[data-test="logo-upload"]')
    expect(btn.disabled).toBe(true)
    // Force the action even though disabled, to exercise the guard:
    wrapper.vm.uploadLogo()
    await flushPromises()

    expect(upload).not.toHaveBeenCalled()
    expect(ElMessage.warning).toHaveBeenCalledWith('請先選擇圖片')
  })
})
