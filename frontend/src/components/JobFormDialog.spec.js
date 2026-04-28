import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { jobsApi } from '../api/jobs'
import JobFormDialog from './JobFormDialog.vue'

// MdEditor is heavy and brings in CSS / DOM measurement; stub it to a
// minimal v-model'd textarea so the form-level behavior is what we
// actually test here.
vi.mock('md-editor-v3', () => ({
  MdEditor: {
    name: 'MdEditor',
    props: ['modelValue', 'preview'],
    emits: ['update:modelValue'],
    // Methods so the dialog's preview-sync wiring (ed.on / ed.togglePreview)
    // can call into the stub without crashing the test.
    methods: {
      on() {},
      togglePreview() {},
      togglePageFullscreen() {},
      toggleFullscreen() {},
    },
    template:
      '<textarea class="md-editor-stub" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
}))
vi.mock('md-editor-v3/lib/style.css', () => ({}))

vi.mock('element-plus', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    ElMessage: Object.assign(
      vi.fn(() => ({ close: vi.fn() })),
      { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() },
    ),
  }
})

beforeEach(() => {
  setActivePinia(createPinia())
  vi.spyOn(jobsApi, 'listCompanies').mockResolvedValue([])
})

afterEach(() => {
  vi.restoreAllMocks()
  document.body.innerHTML = ''
})

async function mountDialog(props = {}) {
  const wrapper = mount(JobFormDialog, {
    props: { modelValue: true, job: null, ...props },
  })
  await flushPromises()
  return wrapper
}


function findInputByDataTest(wrapper, dataTest) {
  const el = wrapper.element.querySelector(`[data-test="${dataTest}"]`)
  if (!el) return null
  return el.tagName === 'INPUT' ? el : el.querySelector('input')
}

function findMdEditorByDataTest(wrapper, dataTest) {
  // The MdEditor stub renders a textarea as its root, so data-test
  // lands directly on the textarea in test contexts.
  const el = wrapper.element.querySelector(`[data-test="${dataTest}"]`)
  if (!el) return null
  return el.tagName === 'TEXTAREA' ? el : el.querySelector('textarea')
}

function setNativeValue(el, value) {
  el.value = value
  el.dispatchEvent(new Event('input', { bubbles: true }))
  el.dispatchEvent(new Event('change', { bubbles: true }))
}


describe('JobFormDialog — create mode', () => {
  it('shows 新增 title', async () => {
    const wrapper = await mountDialog()
    expect(wrapper.element.innerHTML).toContain('新增求職紀錄')
  })

  it('defaults kind to internship and current year', async () => {
    const wrapper = await mountDialog()
    const internshipChip = wrapper.find('[data-test="kind-option-internship"]')
    expect(internshipChip.classes()).toContain('is-active')
  })

  it('lets the user switch kind to fulltime', async () => {
    const wrapper = await mountDialog()
    await wrapper.find('[data-test="kind-option-fulltime"]').trigger('click')
    expect(
      wrapper.find('[data-test="kind-option-fulltime"]').classes(),
    ).toContain('is-active')
  })
})

describe('JobFormDialog — edit mode', () => {
  it('shows 編輯 title and prefilled values', async () => {
    const wrapper = await mountDialog({
      job: {
        id: 7,
        kind: 'fulltime',
        job_year: 2023,
        company: 'Acme',
        real_name: 'Alice',
        experience_md: '## interview',
        timeline_md: '| d | e |',
      },
    })
    expect(wrapper.element.innerHTML).toContain('編輯求職紀錄')
    expect(
      wrapper.find('[data-test="kind-option-fulltime"]').classes(),
    ).toContain('is-active')
    const expEditor = findMdEditorByDataTest(wrapper, 'form-experience-md')
    expect(expEditor?.value).toBe('## interview')
  })
})

describe('JobFormDialog — submit', () => {
  it('POSTs the form to jobsApi.create on save in create mode', async () => {
    const create = vi
      .spyOn(jobsApi, 'create')
      .mockResolvedValue({ id: 1 })
    const wrapper = await mountDialog()

    setNativeValue(
      findInputByDataTest(wrapper, 'form-company'),
      'Acme',
    )
    setNativeValue(
      findMdEditorByDataTest(wrapper, 'form-experience-md'),
      '## interview',
    )
    await flushPromises()

    await wrapper.find('[data-test="save-button"]').trigger('click')
    await flushPromises()

    expect(create).toHaveBeenCalledTimes(1)
    const payload = create.mock.calls[0][0]
    expect(payload).toMatchObject({
      kind: 'internship',
      company: 'Acme',
      experience_md: '## interview',
      real_name: null,
      timeline_md: null,
    })
    expect(typeof payload.job_year).toBe('number')
  })

  it('PUTs to jobsApi.update on save in edit mode', async () => {
    const update = vi
      .spyOn(jobsApi, 'update')
      .mockResolvedValue({ id: 7 })
    const wrapper = await mountDialog({
      job: {
        id: 7,
        kind: 'internship',
        job_year: 2024,
        company: 'Acme',
        real_name: 'Alice',
        experience_md: '## interview',
        timeline_md: null,
      },
    })

    setNativeValue(
      findMdEditorByDataTest(wrapper, 'form-experience-md'),
      '## updated',
    )
    await flushPromises()

    await wrapper.find('[data-test="save-button"]').trigger('click')
    await flushPromises()

    expect(update).toHaveBeenCalledWith(7, expect.objectContaining({
      kind: 'internship',
      company: 'Acme',
      experience_md: '## updated',
      real_name: 'Alice',
    }))
  })

  it('emits saved and closes the dialog after a successful create', async () => {
    vi.spyOn(jobsApi, 'create').mockResolvedValue({ id: 1 })
    const wrapper = await mountDialog()

    setNativeValue(
      findInputByDataTest(wrapper, 'form-company'),
      'Acme',
    )
    setNativeValue(
      findMdEditorByDataTest(wrapper, 'form-experience-md'),
      '## x',
    )
    await flushPromises()

    await wrapper.find('[data-test="save-button"]').trigger('click')
    await flushPromises()

    expect(wrapper.emitted('saved')).toBeTruthy()
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([false])
  })

  it('does not call the API if required fields are empty', async () => {
    const create = vi.spyOn(jobsApi, 'create').mockResolvedValue({ id: 1 })
    const wrapper = await mountDialog()

    // No company, no experience_md.
    await wrapper.find('[data-test="save-button"]').trigger('click')
    await flushPromises()
    expect(create).not.toHaveBeenCalled()
  })

  it('treats blank real_name and timeline as null in the payload', async () => {
    const create = vi.spyOn(jobsApi, 'create').mockResolvedValue({ id: 1 })
    const wrapper = await mountDialog()

    setNativeValue(
      findInputByDataTest(wrapper, 'form-company'),
      'Acme',
    )
    setNativeValue(
      findMdEditorByDataTest(wrapper, 'form-experience-md'),
      '## x',
    )
    // real_name has a placeholder of "可留空"
    setNativeValue(findInputByDataTest(wrapper, 'form-real-name'), '   ')
    await flushPromises()

    await wrapper.find('[data-test="save-button"]').trigger('click')
    await flushPromises()

    const payload = create.mock.calls[0][0]
    expect(payload.real_name).toBeNull()
    expect(payload.timeline_md).toBeNull()
  })
})

describe('JobFormDialog — company autocomplete wiring', () => {
  it('hooks the autocomplete fetcher to jobsApi.listCompanies', async () => {
    const wrapper = await mountDialog()
    const autocomplete = wrapper.findComponent({ name: 'ElAutocomplete' })
    const fetchSuggestions = autocomplete.props('fetchSuggestions')

    jobsApi.listCompanies.mockResolvedValue(['Acme', 'AcmeInc'])

    const suggestions = await new Promise((resolve) =>
      fetchSuggestions('ac', resolve),
    )
    expect(jobsApi.listCompanies).toHaveBeenCalledWith('ac')
    expect(suggestions).toEqual([{ value: 'Acme' }, { value: 'AcmeInc' }])
  })
})
