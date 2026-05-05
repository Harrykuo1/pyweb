import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { membersApi } from '../api/members'
import MemberFormDialog from './MemberFormDialog.vue'

vi.mock('element-plus', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    // ElMessage is now invoked as a function for the persistent
    // "儲存中…" toast; mirror Element Plus's real shape (callable +
    // helpers).
    ElMessage: Object.assign(
      vi.fn(() => ({ close: vi.fn() })),
      { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
    ),
  }
})

beforeEach(() => {
  setActivePinia(createPinia())
})

afterEach(() => {
  vi.restoreAllMocks()
  document.body.innerHTML = ''
})

async function mountDialog(props = {}) {
  const wrapper = mount(MemberFormDialog, {
    props: { modelValue: true, member: null, ...props },
    attachTo: document.body,
  })
  // ElDialog content may render after a microtask.
  await flushPromises()
  return wrapper
}

function setVmValue(wrapper, key, value) {
  // The dialog stores form fields in a reactive `form` object that is part
  // of <script setup> closure. Vue Test Utils does not surface it directly,
  // so we set values by typing into the matching DOM input.
  const inputs = Array.from(wrapper.element.querySelectorAll('input,textarea'))
  const map = {}
  for (const el of inputs) {
    if (el.placeholder?.includes('留空則使用今天')) map.joined_at = el
    else if (el.placeholder?.includes('Phase 7')) map.resume_md = el
    else if (el.tagName === 'TEXTAREA') map.resume_md = el
  }
  // Remaining inputs (number, real_name, institution, position) are
  // matched by their visual order, which is stable.
  const ordered = inputs.filter((el) => !Object.values(map).includes(el))
  ;[map.graduation_year, map.real_name, map.institution, map.position] = ordered

  const target = map[key]
  if (!target) throw new Error(`No DOM target for ${key}`)
  target.value = value
  target.dispatchEvent(new Event('input', { bubbles: true }))
  target.dispatchEvent(new Event('change', { bubbles: true }))
}

describe('MemberFormDialog', () => {
  it('shows 新增成員 title in create mode', async () => {
    const wrapper = await mountDialog()
    expect(wrapper.element.innerHTML).toContain('新增成員')
  })

  it('shows 編輯成員 title and prefilled values in edit mode', async () => {
    const wrapper = await mountDialog({
      member: {
        id: 1,
        graduation_year: 2022,
        real_name: 'Alice',
        institution: 'SWE',
        resume_md: '# x',
        joined_at: '2022-05-01',
      },
    })
    expect(wrapper.element.innerHTML).toContain('編輯成員')

    const values = Array.from(
      wrapper.element.querySelectorAll('input,textarea'),
    ).map((el) => el.value)
    expect(values).toContain('Alice')
    expect(values).toContain('SWE')
    expect(values).toContain('# x')
  })

  it('create flow calls membersApi.create with the form payload', async () => {
    const create = vi.spyOn(membersApi, 'create').mockResolvedValue({ id: 1 })
    const wrapper = await mountDialog()

    setVmValue(wrapper, 'real_name', 'Carol')
    setVmValue(wrapper, 'institution', 'PhD student')
    setVmValue(wrapper, 'resume_md', '# resume')

    await wrapper.find('[data-test="save-button"]').trigger('click')
    await flushPromises()

    expect(create).toHaveBeenCalledTimes(1)
    const payload = create.mock.calls[0][0]
    expect(payload.real_name).toBe('Carol')
    expect(payload.institution).toBe('PhD student')
    expect(payload.position).toBeNull()
    expect(payload.resume_md).toBe('# resume')
    expect(typeof payload.graduation_year).toBe('number')
  })

  it('prefills institution + position in edit mode', async () => {
    const update = vi.spyOn(membersApi, 'update').mockResolvedValue({ id: 9 })
    const wrapper = await mountDialog({
      member: {
        id: 9,
        graduation_year: 2024,
        real_name: 'Eve',
        institution: 'NYCU',
        position: '資工系',
        resume_md: null,
        joined_at: null,
        has_photo: false,
        has_resume_md: false,
        has_resume_pdf: false,
      },
    })

    // Save without changes; payload should round-trip institution + position.
    await wrapper.find('[data-test="save-button"]').trigger('click')
    await flushPromises()

    expect(update).toHaveBeenCalledWith(
      9,
      expect.objectContaining({ institution: 'NYCU', position: '資工系' }),
    )
  })

  it('sends position in payload when filled, null when blank', async () => {
    const create = vi.spyOn(membersApi, 'create').mockResolvedValue({ id: 1 })
    const wrapper = await mountDialog()

    setVmValue(wrapper, 'real_name', 'Frank')
    setVmValue(wrapper, 'institution', 'Acme')
    setVmValue(wrapper, 'position', 'Backend Engineer')

    await wrapper.find('[data-test="save-button"]').trigger('click')
    await flushPromises()

    expect(create.mock.calls[0][0].position).toBe('Backend Engineer')
  })

  it('edit flow calls membersApi.update with the member id', async () => {
    const update = vi.spyOn(membersApi, 'update').mockResolvedValue({ id: 7 })
    const wrapper = await mountDialog({
      member: {
        id: 7,
        graduation_year: 2020,
        real_name: 'Old',
        institution: 'Old',
        resume_md: null,
        joined_at: null,
      },
    })

    await wrapper.find('[data-test="save-button"]').trigger('click')
    await flushPromises()

    expect(update).toHaveBeenCalledTimes(1)
    expect(update.mock.calls[0][0]).toBe(7)
  })

  it('emits saved and closes the dialog after a successful save', async () => {
    vi.spyOn(membersApi, 'create').mockResolvedValue({ id: 1 })
    const wrapper = await mountDialog()

    setVmValue(wrapper, 'real_name', 'Alice')
    setVmValue(wrapper, 'institution', 'SWE')

    await wrapper.find('[data-test="save-button"]').trigger('click')
    await flushPromises()

    expect(wrapper.emitted('saved')).toBeTruthy()
    expect(wrapper.emitted('update:modelValue')).toContainEqual([false])
  })

  it('does not emit saved when the API rejects', async () => {
    vi.spyOn(membersApi, 'create').mockRejectedValue(
      Object.assign(new Error('500'), { response: { status: 500 } }),
    )
    const wrapper = await mountDialog()

    setVmValue(wrapper, 'real_name', 'Alice')
    setVmValue(wrapper, 'institution', 'SWE')

    await wrapper.find('[data-test="save-button"]').trigger('click')
    await flushPromises()

    expect(wrapper.emitted('saved')).toBeFalsy()
  })

  // ---------- PDF upload integration ----------

  function pdfFile(size = 1024, type = 'application/pdf', name = 'r.pdf') {
    const f = new File(['%PDF'], name, { type })
    Object.defineProperty(f, 'size', { value: size })
    return f
  }

  it('create with selected PDF uploads after create succeeds', async () => {
    const create = vi.spyOn(membersApi, 'create').mockResolvedValue({ id: 11 })
    const upload = vi.spyOn(membersApi, 'uploadResumePdf').mockResolvedValue({})

    const wrapper = await mountDialog()
    setVmValue(wrapper, 'real_name', 'Alice')
    setVmValue(wrapper, 'institution', 'SWE')
    const file = pdfFile()
    await wrapper.vm.handlePdfChange({ raw: file, name: file.name, size: file.size })

    await wrapper.find('[data-test="save-button"]').trigger('click')
    await flushPromises()

    expect(create).toHaveBeenCalledTimes(1)
    expect(upload).toHaveBeenCalledWith(11, file)
    expect(wrapper.emitted('saved')).toBeTruthy()
  })

  it('edit with selected PDF uploads after update succeeds', async () => {
    const update = vi.spyOn(membersApi, 'update').mockResolvedValue({ id: 7 })
    const upload = vi.spyOn(membersApi, 'uploadResumePdf').mockResolvedValue({})

    const wrapper = await mountDialog({
      member: {
        id: 7,
        graduation_year: 2020,
        real_name: 'Old',
        institution: 'Old',
        resume_md: null,
        joined_at: null,
        has_resume_pdf: false,
      },
    })
    const file = pdfFile()
    await wrapper.vm.handlePdfChange({ raw: file, name: file.name, size: file.size })

    await wrapper.find('[data-test="save-button"]').trigger('click')
    await flushPromises()

    expect(update).toHaveBeenCalled()
    expect(upload).toHaveBeenCalledWith(7, file)
  })

  it('handleDeletePdf calls deleteResumePdf with the typed password and emits saved', async () => {
    vi.spyOn(membersApi, 'update').mockResolvedValue({ id: 7 })
    const del = vi.spyOn(membersApi, 'deleteResumePdf').mockResolvedValue()

    const wrapper = await mountDialog({
      member: {
        id: 7,
        graduation_year: 2020,
        real_name: 'Old',
        institution: 'Old',
        resume_md: null,
        joined_at: null,
        has_resume_pdf: true,
      },
    })

    // The 「移除」 button is rendered for an edit-mode member with an
    // existing PDF and no pending replacement.
    expect(wrapper.find('[data-test="mark-remove-pdf"]').exists()).toBe(true)

    await wrapper.vm.handleDeletePdf('admin-pw')
    await flushPromises()

    expect(del).toHaveBeenCalledWith(7, 'admin-pw')
    expect(wrapper.emitted('saved')).toBeTruthy()
    expect(wrapper.vm.pdfDeletedThisSession).toBe(true)
  })

  it('handleDeletePdf on 422 keeps dialog open and surfaces 密碼錯誤', async () => {
    vi.spyOn(membersApi, 'deleteResumePdf').mockRejectedValue(
      Object.assign(new Error('422'), { response: { status: 422 } }),
    )

    const wrapper = await mountDialog({
      member: {
        id: 7,
        graduation_year: 2020,
        real_name: 'Old',
        institution: 'Old',
        resume_md: null,
        joined_at: null,
        has_resume_pdf: true,
      },
    })
    wrapper.vm.askDeletePdf()
    await flushPromises()
    await wrapper.vm.handleDeletePdf('wrong-pw')
    await flushPromises()

    expect(wrapper.vm.pdfDeleteError).toBe('密碼錯誤')
    expect(wrapper.vm.pdfDeleteDialogOpen).toBe(true)
    expect(wrapper.vm.pdfDeletedThisSession).toBe(false)
  })

  it('handlePdfChange rejects oversized files without setting state', async () => {
    const upload = vi.spyOn(membersApi, 'uploadResumePdf')
    vi.spyOn(membersApi, 'create').mockResolvedValue({ id: 1 })

    const wrapper = await mountDialog()
    setVmValue(wrapper, 'real_name', 'Alice')
    setVmValue(wrapper, 'institution', 'SWE')
    const big = pdfFile(11 * 1024 * 1024)
    await wrapper.vm.handlePdfChange({ raw: big, name: big.name, size: big.size })

    await wrapper.find('[data-test="save-button"]').trigger('click')
    await flushPromises()

    expect(upload).not.toHaveBeenCalled()
  })

  it('handlePdfChange rejects non-PDF MIME', async () => {
    const upload = vi.spyOn(membersApi, 'uploadResumePdf')
    vi.spyOn(membersApi, 'create').mockResolvedValue({ id: 1 })

    const wrapper = await mountDialog()
    setVmValue(wrapper, 'real_name', 'Alice')
    setVmValue(wrapper, 'institution', 'SWE')
    const docx = pdfFile(1024, 'application/msword', 'r.docx')
    await wrapper.vm.handlePdfChange({ raw: docx, name: docx.name, size: docx.size })

    await wrapper.find('[data-test="save-button"]').trigger('click')
    await flushPromises()

    expect(upload).not.toHaveBeenCalled()
  })

  it('still emits saved and closes when basic save passes but PDF upload fails', async () => {
    vi.spyOn(membersApi, 'create').mockResolvedValue({ id: 1 })
    vi.spyOn(membersApi, 'uploadResumePdf').mockRejectedValue(
      Object.assign(new Error('413'), { response: { status: 413 } }),
    )

    const wrapper = await mountDialog()
    setVmValue(wrapper, 'real_name', 'Alice')
    setVmValue(wrapper, 'institution', 'SWE')
    const f = pdfFile()
    await wrapper.vm.handlePdfChange({ raw: f, name: f.name, size: f.size })

    await wrapper.find('[data-test="save-button"]').trigger('click')
    await flushPromises()

    expect(wrapper.emitted('saved')).toBeTruthy()
    expect(wrapper.emitted('update:modelValue')).toContainEqual([false])
  })

  it('opening dialog clears any leftover pending PDF state', async () => {
    const wrapper = await mountDialog()
    const f = pdfFile()
    await wrapper.vm.handlePdfChange({ raw: f, name: f.name, size: f.size })
    expect(wrapper.text()).toContain('已選擇')

    // Re-open with a new member; the form should reset.
    await wrapper.setProps({
      modelValue: false,
    })
    await wrapper.setProps({
      modelValue: true,
      member: {
        id: 9,
        graduation_year: 2024,
        real_name: 'X',
        institution: 'Y',
        resume_md: null,
        joined_at: null,
        has_resume_pdf: false,
      },
    })
    await flushPromises()

    expect(wrapper.text()).not.toContain('已選擇')
  })
})
