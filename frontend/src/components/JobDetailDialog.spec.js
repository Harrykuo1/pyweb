import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import JobDetailDialog from './JobDetailDialog.vue'
import { useAuthStore } from '../stores/auth'

vi.mock('md-editor-v3', () => ({
  MdPreview: {
    name: 'MdPreview',
    props: ['modelValue'],
    template: '<div class="md-preview-stub">{{ modelValue }}</div>',
  },
}))
vi.mock('md-editor-v3/lib/preview.css', () => ({}))

const sample = {
  id: 1,
  job_year: 2025,
  job_month: 4,
  company: 'Acme',
  kind: 'internship',
  real_name: 'Alice',
  experience_md: '## interview content',
  timeline_md: '| date | event |\n|---|---|\n| 5/1 | apply |',
  created_at: '2025-05-01T00:00:00+00:00',
}

beforeEach(() => {
  setActivePinia(createPinia())
})

afterEach(() => {
  vi.restoreAllMocks()
  document.body.innerHTML = ''
})

async function mountDialog(props = {}, role = 'admin') {
  const auth = useAuthStore()
  auth.user = { id: 1, username: 'a', role }
  const wrapper = mount(JobDetailDialog, {
    props: { modelValue: true, job: sample, ...props },
  })
  await flushPromises()
  return wrapper
}

describe('JobDetailDialog — header', () => {
  it('shows the kind badge, company, real name and meta', async () => {
    const wrapper = await mountDialog()
    expect(wrapper.find('[data-test="detail-kind-internship"]').text())
      .toContain('實習')
    expect(wrapper.find('[data-test="detail-company"]').text())
      .toContain('Acme')
    expect(wrapper.find('[data-test="detail-real-name"]').text())
      .toContain('Alice')
    expect(wrapper.text()).toContain('2025/04 求職')
  })

  it('shows 匿名 styling when real_name is null', async () => {
    const wrapper = await mountDialog({
      job: { ...sample, real_name: null },
    })
    expect(wrapper.find('[data-test="detail-anonymous"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="detail-real-name"]').exists()).toBe(false)
  })

  it('themes header by kind', async () => {
    const wrapper = await mountDialog({
      job: { ...sample, kind: 'fulltime' },
    })
    const header = wrapper.find('.detail-header')
    expect(header.classes()).toContain('detail-header--fulltime')
    expect(wrapper.find('[data-test="detail-kind-fulltime"]').text())
      .toContain('正職')
  })
})

describe('JobDetailDialog — markdown tabs', () => {
  it('renders the experience tab body via MdPreview', async () => {
    const wrapper = await mountDialog()
    const exp = wrapper.find('[data-test="detail-experience"]')
    expect(exp.exists()).toBe(true)
    expect(exp.text()).toContain('## interview content')
  })

  it('renders the timeline tab when timeline_md (legacy) is present', async () => {
    const wrapper = await mountDialog()
    expect(wrapper.text()).toContain('時程表')
  })

  it('hides the timeline tab when both timeline_md and timeline_events are empty', async () => {
    const wrapper = await mountDialog({
      job: { ...sample, timeline_md: '', timeline_events: null },
    })
    expect(wrapper.text()).not.toContain('時程表')

    const wrapper2 = await mountDialog({
      job: { ...sample, timeline_md: null, timeline_events: [] },
    })
    expect(wrapper2.text()).not.toContain('時程表')
  })

  it('renders TimelineDisplay when timeline_events is non-empty (preferred over legacy markdown)', async () => {
    // Even if both fields are populated, the structured events take
    // priority — that's the migration path: editing a legacy job
    // refills timeline_events, which immediately shadows the old
    // markdown column without us having to delete it server-side.
    const wrapper = await mountDialog({
      job: {
        ...sample,
        timeline_md: '舊資料',
        timeline_events: [
          { date: '2025-02-23', event: '投遞' },
          { date: '2025-04-17', event: '拿到 offer' },
        ],
      },
    })
    expect(wrapper.find('[data-test="timeline-display"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="detail-timeline-legacy"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('投遞')
    expect(wrapper.text()).toContain('拿到 offer')
  })

  it('falls back to legacy markdown with a deprecated badge when only timeline_md is set', async () => {
    const wrapper = await mountDialog({
      job: {
        ...sample,
        timeline_md: '舊版時程內文',
        timeline_events: null,
      },
    })
    expect(wrapper.find('[data-test="timeline-display"]').exists()).toBe(false)
    const legacy = wrapper.find('[data-test="detail-timeline-legacy"]')
    expect(legacy.exists()).toBe(true)
    expect(legacy.text()).toContain('舊版時程表')
    expect(wrapper.text()).toContain('舊版時程內文')
  })

  it('renders the attachments tab when attachment_count > 0', async () => {
    const wrapper = await mountDialog({
      job: { ...sample, attachment_count: 2 },
    })
    // Inspect the visible tab nav text — Element Plus's el-tab-pane
    // doesn't surface its data-test on the nav element, so checking
    // the rendered label is more reliable (matches the timeline tab
    // tests' pattern).
    expect(wrapper.text()).toContain('附件')
  })

  it('hides the attachments tab when attachment_count is 0 or missing', async () => {
    // Mirror the timeline behaviour — no content → no tab. Both the
    // explicit-zero case and the missing-field case should hide.
    const w1 = await mountDialog({
      job: { ...sample, attachment_count: 0 },
    })
    expect(w1.text()).not.toContain('附件')

    const { attachment_count, ...withoutCount } = sample
    const w2 = await mountDialog({ job: withoutCount })
    expect(w2.text()).not.toContain('附件')
  })
})

describe('JobDetailDialog — admin edit button', () => {
  it('emits edit with the current job and closes when admin clicks 編輯', async () => {
    const wrapper = await mountDialog()
    const btn = wrapper.find('[data-test="detail-edit-button"]')
    expect(btn.exists()).toBe(true)
    await btn.trigger('click')
    expect(wrapper.emitted('edit')?.[0]?.[0]).toEqual(sample)
    expect(wrapper.emitted('update:modelValue')?.at(-1)).toEqual([false])
  })

  it('hides the edit button for viewers', async () => {
    const wrapper = await mountDialog({}, 'viewer')
    expect(wrapper.find('[data-test="detail-edit-button"]').exists())
      .toBe(false)
  })
})
