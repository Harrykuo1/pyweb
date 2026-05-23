import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { ElMessage } from 'element-plus'

import SystemLimitsSection from './SystemLimitsSection.vue'
import { settingsApi } from '../../api/settings'

const SAMPLE = {
  fields: [
    { key: 'max_attachments_per_job', value: 10, type: 'int', min: 1, max: 50 },
    { key: 'max_attachment_mb', value: 20, type: 'int', min: 1, max: 200 },
  ],
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('SystemLimitsSection.vue', () => {
  it('loads config on mount and renders one input per field', async () => {
    const getConfig = vi
      .spyOn(settingsApi, 'getConfig')
      .mockResolvedValue(SAMPLE)

    const wrapper = mount(SystemLimitsSection)
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

    const wrapper = mount(SystemLimitsSection)
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

    const wrapper = mount(SystemLimitsSection)
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

    const wrapper = mount(SystemLimitsSection)
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

    const wrapper = mount(SystemLimitsSection)
    await flushPromises()

    wrapper.vm.form.max_attachments_per_job = 42
    await flushPromises()
    await wrapper.find('[data-test="settings-reset"]').trigger('click')

    expect(wrapper.vm.form.max_attachments_per_job).toBe(10)
  })

  it('remounts el-input-number after save so spinner stays in sync', async () => {
    vi.spyOn(settingsApi, 'getConfig').mockResolvedValue(SAMPLE)
    vi.spyOn(settingsApi, 'updateConfig').mockResolvedValue(SAMPLE)

    const wrapper = mount(SystemLimitsSection)
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

    const wrapper = mount(SystemLimitsSection)
    await flushPromises()

    expect(wrapper.text()).toContain('載入設定失敗')
    expect(wrapper.find('[data-test="settings-form"]').exists()).toBe(false)
  })
})
