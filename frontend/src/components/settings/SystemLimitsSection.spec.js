import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { ElMessage } from 'element-plus'

import SystemLimitsSection from './SystemLimitsSection.vue'
import { settingsApi } from '../../api/settings'

// The API returns every group's fields in one payload; the component keeps
// only its own, so the sample carries an event field to prove it is dropped.
const SAMPLE = {
  fields: [
    {
      key: 'max_attachments_per_job',
      value: 10,
      type: 'int',
      group: 'job',
      min: 1,
      max: 50,
    },
    {
      key: 'max_attachment_mb',
      value: 20,
      type: 'int',
      group: 'job',
      min: 1,
      max: 200,
    },
    {
      key: 'max_photo_mb',
      value: 15,
      type: 'int',
      group: 'event',
      min: 1,
      max: 40,
    },
  ],
}

const JOB = { props: { group: 'job' } }

afterEach(() => {
  vi.restoreAllMocks()
})

describe('SystemLimitsSection.vue', () => {
  it('loads config on mount and renders one input per field', async () => {
    const getConfig = vi
      .spyOn(settingsApi, 'getConfig')
      .mockResolvedValue(SAMPLE)

    const wrapper = mount(SystemLimitsSection, JOB)
    await flushPromises()

    expect(getConfig).toHaveBeenCalledTimes(1)
    expect(
      wrapper.find('[data-test="setting-max_attachments_per_job"]').exists(),
    ).toBe(true)
    expect(
      wrapper.find('[data-test="setting-max_attachment_mb"]').exists(),
    ).toBe(true)
    expect(wrapper.text()).toContain('單筆求職紀錄附件數上限')
    expect(wrapper.text()).toContain('單檔大小上限')
    expect(wrapper.text()).toContain('MB')
  })

  it('save button is disabled until the form changes', async () => {
    vi.spyOn(settingsApi, 'getConfig').mockResolvedValue(SAMPLE)

    const wrapper = mount(SystemLimitsSection, JOB)
    await flushPromises()

    expect(
      wrapper.find('[data-test="settings-save"]').attributes('disabled'),
    ).toBeDefined()
  })

  it('PUTs values on save and refreshes from response', async () => {
    vi.spyOn(settingsApi, 'getConfig').mockResolvedValue(SAMPLE)
    const updated = {
      fields: [
        { ...SAMPLE.fields[0], value: 25 },
        { ...SAMPLE.fields[1], value: 50 },
      ],
    }
    const update = vi
      .spyOn(settingsApi, 'updateConfig')
      .mockResolvedValue(updated)
    const success = vi.spyOn(ElMessage, 'success').mockImplementation(() => {})

    const wrapper = mount(SystemLimitsSection, JOB)
    await flushPromises()

    wrapper.vm.form.max_attachments_per_job = 25
    wrapper.vm.form.max_attachment_mb = 50
    await flushPromises()

    await wrapper.find('[data-test="settings-save"]').trigger('click')
    await flushPromises()

    expect(update).toHaveBeenCalledWith({
      max_attachments_per_job: 25,
      max_attachment_mb: 50,
    })
    expect(success).toHaveBeenCalled()
    expect(wrapper.vm.form.max_attachments_per_job).toBe(25)
  })

  it('422 surfaces the API detail and keeps the user edit', async () => {
    vi.spyOn(settingsApi, 'getConfig').mockResolvedValue(SAMPLE)
    vi.spyOn(settingsApi, 'updateConfig').mockRejectedValue(
      Object.assign(new Error('422'), {
        response: { status: 422, data: { detail: 'value out of range' } },
      }),
    )
    const error = vi.spyOn(ElMessage, 'error').mockImplementation(() => {})

    const wrapper = mount(SystemLimitsSection, JOB)
    await flushPromises()

    wrapper.vm.form.max_attachments_per_job = 5
    await flushPromises()
    await wrapper.find('[data-test="settings-save"]').trigger('click')
    await flushPromises()

    expect(error).toHaveBeenCalledWith('value out of range')
    expect(wrapper.vm.form.max_attachments_per_job).toBe(5)
  })

  it('reset reverts unsaved edits', async () => {
    vi.spyOn(settingsApi, 'getConfig').mockResolvedValue(SAMPLE)

    const wrapper = mount(SystemLimitsSection, JOB)
    await flushPromises()

    wrapper.vm.form.max_attachments_per_job = 42
    await flushPromises()
    await wrapper.find('[data-test="settings-reset"]').trigger('click')

    expect(wrapper.vm.form.max_attachments_per_job).toBe(10)
  })

  it('remounts el-input-number after save so spinner stays in sync', async () => {
    vi.spyOn(settingsApi, 'getConfig').mockResolvedValue(SAMPLE)
    vi.spyOn(settingsApi, 'updateConfig').mockResolvedValue(SAMPLE)

    const wrapper = mount(SystemLimitsSection, JOB)
    await flushPromises()
    const before = wrapper.vm.formVersion

    wrapper.vm.form.max_attachments_per_job = 15
    await flushPromises()
    await wrapper.find('[data-test="settings-save"]').trigger('click')
    await flushPromises()

    expect(wrapper.vm.formVersion).toBe(before + 1)
  })

  it('shows error banner when GET fails', async () => {
    vi.spyOn(settingsApi, 'getConfig').mockRejectedValue(new Error('boom'))

    const wrapper = mount(SystemLimitsSection, JOB)
    await flushPromises()

    expect(wrapper.text()).toContain('載入設定失敗')
    expect(wrapper.find('[data-test="settings-form"]').exists()).toBe(false)
  })
})

describe('SystemLimitsSection.vue — per-group split', () => {
  it('renders only its own group and ignores the rest of the payload', async () => {
    vi.spyOn(settingsApi, 'getConfig').mockResolvedValue(SAMPLE)

    const wrapper = mount(SystemLimitsSection, { props: { group: 'event' } })
    await flushPromises()

    expect(wrapper.find('[data-test="setting-max_photo_mb"]').exists()).toBe(
      true,
    )
    // A job field must not leak into the events tab — one payload feeds both.
    expect(
      wrapper.find('[data-test="setting-max_attachment_mb"]').exists(),
    ).toBe(false)
    expect(wrapper.text()).toContain('照片單檔大小上限')
  })

  it('saves only its own group, leaving the other tab untouched', async () => {
    vi.spyOn(settingsApi, 'getConfig').mockResolvedValue(SAMPLE)
    const updateConfig = vi
      .spyOn(settingsApi, 'updateConfig')
      .mockResolvedValue(SAMPLE)

    const wrapper = mount(SystemLimitsSection, { props: { group: 'event' } })
    await flushPromises()

    wrapper.vm.form.max_photo_mb = 20
    await flushPromises()
    await wrapper.find('[data-test="settings-save"]').trigger('click')
    await flushPromises()

    // PUT is a partial update, so sending a job key here would overwrite
    // whatever the other tab holds with this tab's stale copy.
    expect(updateConfig).toHaveBeenCalledWith({ max_photo_mb: 20 })
  })
})
