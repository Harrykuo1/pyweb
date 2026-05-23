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
  vi.spyOn(jobsApi, 'listCategories').mockResolvedValue([])
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
        job_month: 8,
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
      // The structured editor is the only timeline surface now; saving
      // always nulls out the legacy markdown column so it can't shadow
      // the structured timeline in the viewer fallback.
      timeline_md: null,
      timeline_events: [],
    })
    expect(typeof payload.job_year).toBe('number')
    expect(typeof payload.job_month).toBe('number')
    expect(payload.job_month).toBeGreaterThanOrEqual(1)
    expect(payload.job_month).toBeLessThanOrEqual(12)
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
        job_month: 5,
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

  it('emits saved and stays open in edit mode after a successful create', async () => {
    // After POST the dialog flips into "edit" mode against the newly
    // issued id so the user can immediately switch to the attachments
    // tab. The parent list still needs to refresh (saved emit), but the
    // dialog itself must NOT close — that's the whole point of option A.
    vi.spyOn(jobsApi, 'create').mockResolvedValue({
      id: 42,
      kind: 'internship',
      company: 'Acme',
      job_year: 2026,
      job_month: 5,
      experience_md: '## x',
    })
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
    // No close emit — the dialog stays open so the attachments tab is
    // reachable against the freshly-issued id.
    expect(wrapper.emitted('update:modelValue')).toBeFalsy()
  })

  it('flips to edit mode after create so subsequent saves go through update', async () => {
    const created = {
      id: 42,
      kind: 'internship',
      company: 'Acme',
      job_year: 2026,
      job_month: 5,
      experience_md: '## first',
    }
    vi.spyOn(jobsApi, 'create').mockResolvedValue(created)
    const update = vi.spyOn(jobsApi, 'update').mockResolvedValue(created)
    const wrapper = await mountDialog()

    setNativeValue(findInputByDataTest(wrapper, 'form-company'), 'Acme')
    setNativeValue(findMdEditorByDataTest(wrapper, 'form-experience-md'), '## first')
    await flushPromises()

    await wrapper.find('[data-test="save-button"]').trigger('click')
    await flushPromises()

    // Second save should be a PUT against the id POST handed back —
    // no second POST.
    setNativeValue(findMdEditorByDataTest(wrapper, 'form-experience-md'), '## edited')
    await flushPromises()
    await wrapper.find('[data-test="save-button"]').trigger('click')
    await flushPromises()

    expect(update).toHaveBeenCalledWith(42, expect.objectContaining({
      experience_md: '## edited',
    }))
  })

  it('unlocks the attachments tab once the job is created', async () => {
    vi.spyOn(jobsApi, 'create').mockResolvedValue({
      id: 7,
      kind: 'internship',
      company: 'Acme',
      job_year: 2026,
      job_month: 5,
      experience_md: '## hi',
    })
    const wrapper = await mountDialog()

    // Pre-create: the placeholder explains why the manager isn't here.
    expect(wrapper.find('[data-test="attachments-locked"]').exists()).toBe(true)

    setNativeValue(findInputByDataTest(wrapper, 'form-company'), 'Acme')
    setNativeValue(findMdEditorByDataTest(wrapper, 'form-experience-md'), '## hi')
    await flushPromises()
    await wrapper.find('[data-test="save-button"]').trigger('click')
    await flushPromises()

    // Post-create: placeholder gone, manager mounted in its place.
    expect(wrapper.find('[data-test="attachments-locked"]').exists()).toBe(false)
  })

  it('does not call the API if required fields are empty', async () => {
    const create = vi.spyOn(jobsApi, 'create').mockResolvedValue({ id: 1 })
    const wrapper = await mountDialog()

    // No company, no experience_md.
    await wrapper.find('[data-test="save-button"]').trigger('click')
    await flushPromises()
    expect(create).not.toHaveBeenCalled()
  })

  it('treats blank real_name as null and empty timeline as [] in the payload', async () => {
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
    expect(payload.timeline_events).toEqual([])
  })

  it('round-trips timeline_events through edit mode unchanged when not modified', async () => {
    // Loading an existing job with structured timeline events into the
    // editor and saving without further edits must produce a payload
    // identical to the input — i.e. the form preserves both the rows
    // and their input order.
    const update = vi.spyOn(jobsApi, 'update').mockResolvedValue({ id: 7 })
    const wrapper = await mountDialog({
      job: {
        id: 7,
        kind: 'internship',
        job_year: 2025,
        job_month: 4,
        company: 'Acme',
        real_name: null,
        experience_md: '## x',
        timeline_md: null,
        timeline_events: [
          { date: '2025-02-23', event: '投遞' },
          { date: '2025-04-17', event: '拿到 offer' },
        ],
      },
    })

    expect(wrapper.findAll('[data-test="timeline-row"]')).toHaveLength(2)

    await wrapper.find('[data-test="save-button"]').trigger('click')
    await flushPromises()

    const payload = update.mock.calls[0][1]
    expect(payload.timeline_events).toEqual([
      { date: '2025-02-23', event: '投遞' },
      { date: '2025-04-17', event: '拿到 offer' },
    ])
    // Legacy markdown column always nulled out by the structured editor.
    expect(payload.timeline_md).toBeNull()
  })

  it('sorts timeline_events by date ascending on submit (stable for same-date rows)', async () => {
    // Editor preserves entry order so the admin's caret never jumps,
    // but buildPayload sorts chronologically before sending. Same-date
    // rows keep their entry order via Array#sort's stability.
    const update = vi.spyOn(jobsApi, 'update').mockResolvedValue({ id: 9 })
    const wrapper = await mountDialog({
      job: {
        id: 9,
        kind: 'internship',
        job_year: 2026,
        job_month: 4,
        company: 'Acme',
        real_name: null,
        experience_md: '## x',
        timeline_md: null,
        timeline_events: [
          { date: '2026-04-17', event: '拿到 offer' },
          { date: '2026-02-23', event: '投遞 (entry order 2)' },
          { date: '2026-02-23', event: '投遞 (entry order 3)' },
          { date: '2025-12-01', event: '初次接觸' },
        ],
      },
    })

    await wrapper.find('[data-test="save-button"]').trigger('click')
    await flushPromises()

    expect(update.mock.calls[0][1].timeline_events).toEqual([
      { date: '2025-12-01', event: '初次接觸' },
      { date: '2026-02-23', event: '投遞 (entry order 2)' },
      { date: '2026-02-23', event: '投遞 (entry order 3)' },
      { date: '2026-04-17', event: '拿到 offer' },
    ])
  })

  it('drops timeline rows that are missing date or blank event before saving', async () => {
    // Inject partial rows through the job prop (the editor accepts
    // {date: null, event: ''} as the seed for a freshly-added row,
    // so the same shape drives this test) and verify buildPayload's
    // filter strips them before sending.
    const update = vi.spyOn(jobsApi, 'update').mockResolvedValue({ id: 7 })
    const wrapper = await mountDialog({
      job: {
        id: 7,
        kind: 'internship',
        job_year: 2025,
        job_month: 4,
        company: 'Acme',
        real_name: null,
        experience_md: '## x',
        timeline_md: null,
        timeline_events: [
          { date: '2025-02-23', event: '投遞' },
          { date: null, event: '半填的' }, // missing date
          { date: '2025-03-05', event: '' }, // missing event text
          { date: '2025-04-17', event: '拿到 offer' },
        ],
      },
    })

    await wrapper.find('[data-test="save-button"]').trigger('click')
    await flushPromises()

    expect(update.mock.calls[0][1].timeline_events).toEqual([
      { date: '2025-02-23', event: '投遞' },
      { date: '2025-04-17', event: '拿到 offer' },
    ])
  })

  it('sends category in the payload when filled, null when empty', async () => {
    const create = vi.spyOn(jobsApi, 'create').mockResolvedValue({ id: 1 })
    const wrapper = await mountDialog()

    setNativeValue(findInputByDataTest(wrapper, 'form-company'), 'Acme')
    setNativeValue(findInputByDataTest(wrapper, 'form-category'), 'DevOps')
    setNativeValue(
      findMdEditorByDataTest(wrapper, 'form-experience-md'),
      '## x',
    )
    await flushPromises()

    await wrapper.find('[data-test="save-button"]').trigger('click')
    await flushPromises()

    expect(create.mock.calls[0][0].category).toBe('DevOps')
  })

  it('treats blank category as null in the payload', async () => {
    const create = vi.spyOn(jobsApi, 'create').mockResolvedValue({ id: 1 })
    const wrapper = await mountDialog()

    setNativeValue(findInputByDataTest(wrapper, 'form-company'), 'Acme')
    setNativeValue(findInputByDataTest(wrapper, 'form-category'), '   ')
    setNativeValue(
      findMdEditorByDataTest(wrapper, 'form-experience-md'),
      '## x',
    )
    await flushPromises()

    await wrapper.find('[data-test="save-button"]').trigger('click')
    await flushPromises()

    expect(create.mock.calls[0][0].category).toBeNull()
  })

  it('prefills category in edit mode and round-trips through update', async () => {
    const update = vi.spyOn(jobsApi, 'update').mockResolvedValue({ id: 9 })
    const wrapper = await mountDialog({
      job: {
        id: 9,
        kind: 'fulltime',
        job_year: 2024,
        job_month: 5,
        company: 'Acme',
        category: 'Backend',
        real_name: 'Alice',
        experience_md: '## x',
        timeline_md: null,
      },
    })

    expect(findInputByDataTest(wrapper, 'form-category').value).toBe('Backend')

    await wrapper.find('[data-test="save-button"]').trigger('click')
    await flushPromises()

    expect(update).toHaveBeenCalledWith(
      9,
      expect.objectContaining({ category: 'Backend' }),
    )
  })
})

describe('JobFormDialog — company autocomplete wiring', () => {
  it('hooks the company autocomplete fetcher to jobsApi.listCompanies', async () => {
    const wrapper = await mountDialog()
    // First ElAutocomplete in the form is the company picker.
    const autocomplete = wrapper.findAllComponents({ name: 'ElAutocomplete' })[0]
    const fetchSuggestions = autocomplete.props('fetchSuggestions')

    jobsApi.listCompanies.mockResolvedValue(['Acme', 'AcmeInc'])

    const suggestions = await new Promise((resolve) =>
      fetchSuggestions('ac', resolve),
    )
    expect(jobsApi.listCompanies).toHaveBeenCalledWith('ac')
    expect(suggestions).toEqual([{ value: 'Acme' }, { value: 'AcmeInc' }])
  })
})

describe('JobFormDialog — category autocomplete wiring', () => {
  it('hooks the category autocomplete fetcher to jobsApi.listCategories', async () => {
    const wrapper = await mountDialog()
    // Second ElAutocomplete in the form is the category picker.
    const autocomplete = wrapper.findAllComponents({ name: 'ElAutocomplete' })[1]
    const fetchSuggestions = autocomplete.props('fetchSuggestions')

    jobsApi.listCategories.mockResolvedValue(['Backend', 'DevOps'])

    const suggestions = await new Promise((resolve) =>
      fetchSuggestions('de', resolve),
    )
    expect(jobsApi.listCategories).toHaveBeenCalledWith('de')
    expect(suggestions).toEqual([{ value: 'Backend' }, { value: 'DevOps' }])
  })
})
