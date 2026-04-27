import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { membersApi } from '../api/members'
import { useAuthStore } from '../stores/auth'
import ResumeViewerDialog from './ResumeViewerDialog.vue'

vi.mock('element-plus', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    // ElMessage is invoked as a function for the persistent "上傳中…"
    // toast; mirror Element Plus's real shape (callable + helpers).
    ElMessage: Object.assign(
      vi.fn(() => ({ close: vi.fn() })),
      { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
    ),
  }
})

// MdPreview is heavy; stub it to keep tests fast and assert input only.
vi.mock('md-editor-v3', () => ({
  MdPreview: {
    name: 'MdPreview',
    props: ['modelValue', 'theme'],
    template: '<div data-test="md-preview-stub">{{ modelValue }}</div>',
  },
}))

beforeEach(() => {
  setActivePinia(createPinia())
})

afterEach(() => {
  vi.restoreAllMocks()
  document.body.innerHTML = ''
})

const memberPdfOnly = {
  id: 1,
  real_name: 'Alice',
  resume_md: null,
  has_resume_md: false,
  has_resume_pdf: true,
}
const memberMdOnly = {
  id: 2,
  real_name: 'Bob',
  resume_md: '# Bob resume',
  has_resume_md: true,
  has_resume_pdf: false,
}
const memberBoth = {
  id: 3,
  real_name: 'Carol',
  resume_md: '# Carol resume',
  has_resume_md: true,
  has_resume_pdf: true,
}
const memberNeither = {
  id: 4,
  real_name: 'Dave',
  resume_md: null,
  has_resume_md: false,
  has_resume_pdf: false,
}

async function open(member) {
  const wrapper = mount(ResumeViewerDialog, {
    props: { modelValue: true, member },
  })
  await flushPromises()
  return wrapper
}

describe('ResumeViewerDialog', () => {
  it('shows PDF iframe and no segmented control when only PDF exists', async () => {
    const wrapper = await open(memberPdfOnly)
    expect(wrapper.find('[data-test="pdf-frame"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="format-segmented"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="md-preview-stub"]').exists()).toBe(false)
  })

  it('shows Markdown preview and no segmented control when only Markdown exists', async () => {
    const wrapper = await open(memberMdOnly)
    expect(wrapper.find('[data-test="md-preview-stub"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="format-segmented"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="md-preview-stub"]').text()).toContain('# Bob resume')
  })

  it('defaults to PDF when both formats are present and shows segmented control', async () => {
    const wrapper = await open(memberBoth)
    expect(wrapper.find('[data-test="format-segmented"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="pdf-frame"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="md-preview-stub"]').exists()).toBe(false)
  })

  it('renders empty state when member has neither resume', async () => {
    const wrapper = await open(memberNeither)
    expect(wrapper.text()).toContain('尚未上傳履歷')
    expect(wrapper.find('[data-test="pdf-frame"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="md-preview-stub"]').exists()).toBe(false)
  })

  it('admin sees upload button regardless of existing PDF', async () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'a', role: 'admin' }

    const w1 = await open(memberPdfOnly)
    expect(w1.find('[data-test="upload-pdf"]').exists()).toBe(true)
    expect(w1.find('[data-test="delete-pdf"]').exists()).toBe(true)

    const w2 = await open(memberMdOnly)
    expect(w2.find('[data-test="upload-pdf"]').exists()).toBe(true)
    expect(w2.find('[data-test="delete-pdf"]').exists()).toBe(false)
  })

  it('viewer sees no admin actions', async () => {
    const auth = useAuthStore()
    auth.user = { id: 2, username: 'v', role: 'viewer' }

    const wrapper = await open(memberPdfOnly)
    expect(wrapper.find('[data-test="upload-pdf"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="delete-pdf"]').exists()).toBe(false)
  })

  it('handleUploadPdf calls api on valid file and emits changed', async () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'a', role: 'admin' }
    const upload = vi.spyOn(membersApi, 'uploadResumePdf').mockResolvedValue({})

    const wrapper = await open(memberMdOnly)
    const file = new File(['%PDF'], 'r.pdf', { type: 'application/pdf' })
    Object.defineProperty(file, 'size', { value: 1024 })

    await wrapper.vm.handleUploadPdf({ raw: file, name: file.name, size: file.size })
    await flushPromises()

    expect(upload).toHaveBeenCalledWith(2, file)
    expect(wrapper.emitted('changed')).toBeTruthy()
  })

  it('handleUploadPdf rejects oversized file without calling api', async () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'a', role: 'admin' }
    const upload = vi.spyOn(membersApi, 'uploadResumePdf')

    const wrapper = await open(memberMdOnly)
    const big = new File(['x'], 'big.pdf', { type: 'application/pdf' })
    Object.defineProperty(big, 'size', { value: 10 * 1024 * 1024 + 1 })

    await wrapper.vm.handleUploadPdf({ raw: big, name: big.name, size: big.size })
    expect(upload).not.toHaveBeenCalled()
  })

  it('handleUploadPdf rejects non-PDF MIME without calling api', async () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'a', role: 'admin' }
    const upload = vi.spyOn(membersApi, 'uploadResumePdf')

    const wrapper = await open(memberMdOnly)
    const docx = new File(['x'], 'r.docx', { type: 'application/msword' })
    Object.defineProperty(docx, 'size', { value: 100 })

    await wrapper.vm.handleUploadPdf({ raw: docx, name: docx.name, size: docx.size })
    expect(upload).not.toHaveBeenCalled()
  })

  it('handleDeletePdf passes password to deleteResumePdf and emits changed', async () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'a', role: 'admin' }
    const del = vi.spyOn(membersApi, 'deleteResumePdf').mockResolvedValue()

    const wrapper = await open(memberPdfOnly)
    await wrapper.vm.handleDeletePdf('admin-pw')
    await flushPromises()

    expect(del).toHaveBeenCalledWith(1, 'admin-pw')
    expect(wrapper.emitted('changed')).toBeTruthy()
  })

  it('clicking delete-pdf opens the password dialog', async () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'a', role: 'admin' }

    const wrapper = await open(memberPdfOnly)
    expect(wrapper.vm.deletePdfDialogOpen).toBe(false)

    await wrapper.find('[data-test="delete-pdf"]').trigger('click')
    await flushPromises()

    expect(wrapper.vm.deletePdfDialogOpen).toBe(true)
  })

  it('handleDeletePdf on 401 surfaces 密碼錯誤 and does not emit changed', async () => {
    const auth = useAuthStore()
    auth.user = { id: 1, username: 'a', role: 'admin' }
    vi.spyOn(membersApi, 'deleteResumePdf').mockRejectedValue(
      Object.assign(new Error('401'), { response: { status: 401 } }),
    )

    const wrapper = await open(memberPdfOnly)
    wrapper.vm.askDeletePdf()
    await flushPromises()
    await wrapper.vm.handleDeletePdf('wrong-pw')
    await flushPromises()

    expect(wrapper.vm.deletePdfError).toBe('密碼錯誤')
    expect(wrapper.vm.deletePdfDialogOpen).toBe(true)
    expect(wrapper.emitted('changed')).toBeFalsy()
  })
})
