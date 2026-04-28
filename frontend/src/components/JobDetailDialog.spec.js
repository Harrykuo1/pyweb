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
    expect(wrapper.text()).toContain('2025 求職')
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

  it('renders the timeline tab when timeline_md is present', async () => {
    const wrapper = await mountDialog()
    expect(wrapper.text()).toContain('時程表')
  })

  it('hides the timeline tab when timeline_md is empty / null', async () => {
    const wrapper = await mountDialog({
      job: { ...sample, timeline_md: '' },
    })
    expect(wrapper.text()).not.toContain('時程表')

    const wrapper2 = await mountDialog({
      job: { ...sample, timeline_md: null },
    })
    expect(wrapper2.text()).not.toContain('時程表')
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
