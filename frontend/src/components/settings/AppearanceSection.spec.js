import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

import { settingsApi } from '../../api/settings'
import AppearanceSection from './AppearanceSection.vue'

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
  // PhotoCropDialog has its own integration tests; we don't need to mount it
  // here, just keep its template inert so the parent can render in jsdom.
})

afterEach(() => {
  vi.restoreAllMocks()
  document.body.innerHTML = ''
})

async function mountSection() {
  const wrapper = mount(AppearanceSection, {
    attachTo: document.body,
    global: {
      stubs: {
        PhotoCropDialog: { template: '<div data-test="crop-stub" />' },
      },
    },
  })
  await flushPromises()
  return wrapper
}

function makeFile(name, type, size = 16) {
  const buf = new Uint8Array(size)
  return new File([buf], name, { type })
}

describe('AppearanceSection.vue', () => {
  it('shows placeholder slots when no logo is set', async () => {
    await mountSection()
    expect(
      document.querySelector('[data-test="logo-current-img"]'),
    ).toBeNull()
    expect(
      document.querySelector('[data-test="logo-delete"]'),
    ).toBeNull()
  })

  it('rejects an unsupported file type', async () => {
    await mountSection()
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

  it('rejects an oversized file', async () => {
    await mountSection()
    const input = document.querySelector('[data-test="logo-file-input"]')
    const file = makeFile('big.png', 'image/png', 2 * 1024 * 1024 + 1)
    Object.defineProperty(input, 'files', { value: [file], configurable: true })
    input.dispatchEvent(new Event('change', { bubbles: true }))
    await flushPromises()

    expect(ElMessage.error).toHaveBeenCalledWith('圖片不可超過 2 MB')
  })

  // SVG bypasses cropping, so picking an SVG file goes straight to "pending".
  function pickSvg() {
    const input = document.querySelector('[data-test="logo-file-input"]')
    const file = makeFile('logo.svg', 'image/svg+xml')
    Object.defineProperty(input, 'files', { value: [file], configurable: true })
    input.dispatchEvent(new Event('change', { bubbles: true }))
    return file
  }

  it('picking an SVG shows pending preview and enables upload', async () => {
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:fake')
    await mountSection()

    pickSvg()
    await flushPromises()

    const preview = document.querySelector('[data-test="logo-pending-img"]')
    expect(preview).not.toBeNull()
    expect(preview.getAttribute('src')).toBe('blob:fake')

    const uploadBtn = document.querySelector('[data-test="logo-upload"]')
    expect(uploadBtn.disabled).toBe(false)
  })

  it('uploads the pending file and surfaces success', async () => {
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:fake')
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {})
    const upload = vi
      .spyOn(settingsApi, 'uploadImage')
      .mockResolvedValue({ key: 'login_logo', size: 16, content_type: 'image/svg+xml' })

    await mountSection()
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

  it('upload error 415 shows unsupported format message', async () => {
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:fake')
    vi.spyOn(settingsApi, 'uploadImage').mockRejectedValue(
      Object.assign(new Error('415'), { response: { status: 415 } }),
    )

    await mountSection()
    pickSvg()
    await flushPromises()
    document.querySelector('[data-test="logo-upload"]').click()
    await flushPromises()

    expect(ElMessage.error).toHaveBeenCalledWith('不支援的檔案格式')
  })

  it('delete removes the current logo and hides the delete button', async () => {
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:fake')
    vi.spyOn(settingsApi, 'uploadImage').mockResolvedValue({
      key: 'login_logo',
      size: 16,
      content_type: 'image/svg+xml',
    })
    const del = vi.spyOn(settingsApi, 'deleteImage').mockResolvedValue()

    await mountSection()
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
  })

  it('picking a PNG opens the crop dialog without a pending preview yet', async () => {
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:fake')
    const wrapper = await mountSection()

    const input = document.querySelector('[data-test="logo-file-input"]')
    const file = makeFile('logo.png', 'image/png')
    Object.defineProperty(input, 'files', { value: [file], configurable: true })
    input.dispatchEvent(new Event('change', { bubbles: true }))
    await flushPromises()

    expect(wrapper.vm.cropOpen).toBe(true)
    expect(wrapper.vm.cropSourceFile?.name).toBe('logo.png')
    expect(wrapper.vm.cropOutputType).toBe('image/png')
    expect(
      document.querySelector('[data-test="logo-pending-img"]'),
    ).toBeNull()
  })

  it('picking a JPEG sets crop output type to image/jpeg', async () => {
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:fake')
    const wrapper = await mountSection()

    const input = document.querySelector('[data-test="logo-file-input"]')
    const file = makeFile('photo.jpg', 'image/jpeg')
    Object.defineProperty(input, 'files', { value: [file], configurable: true })
    input.dispatchEvent(new Event('change', { bubbles: true }))
    await flushPromises()

    expect(wrapper.vm.cropOutputType).toBe('image/jpeg')
  })

  it('confirming a crop swaps the cropped file in as the pending preview', async () => {
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:cropped')
    const wrapper = await mountSection()

    const cropped = makeFile('cropped.png', 'image/png', 32)
    wrapper.vm.onCropConfirmed(cropped)
    await flushPromises()

    const preview = document.querySelector('[data-test="logo-pending-img"]')
    expect(preview).not.toBeNull()
    expect(preview.getAttribute('src')).toBe('blob:cropped')
    expect(wrapper.vm.pendingLogoFile?.name).toBe('cropped.png')
  })

  it('upload without a pending file warns and skips the api call', async () => {
    const upload = vi.spyOn(settingsApi, 'uploadImage')
    const wrapper = await mountSection()

    const btn = document.querySelector('[data-test="logo-upload"]')
    expect(btn.disabled).toBe(true)
    wrapper.vm.uploadLogo()
    await flushPromises()

    expect(upload).not.toHaveBeenCalled()
    expect(ElMessage.warning).toHaveBeenCalledWith('請先選擇圖片')
  })
})
