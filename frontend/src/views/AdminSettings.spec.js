import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { ElMessage } from 'element-plus'

import AdminSettings from './AdminSettings.vue'
import { settingsApi } from '../api/settings'

const SAMPLE = {
  fields: [
    {
      key: 'max_attachments_per_job',
      value: 10,
      type: 'int',
      min: 1,
      max: 50,
    },
    { key: 'max_attachment_mb', value: 20, type: 'int', min: 1, max: 200 },
  ],
}

beforeEach(() => {
  setActivePinia(createPinia())
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('AdminSettings.vue', () => {
  it('loads config on mount and renders one input per field', async () => {
    const getConfig = vi.spyOn(settingsApi, 'getConfig').mockResolvedValue(SAMPLE)

    const wrapper = mount(AdminSettings)
    await flushPromises()

    expect(getConfig).toHaveBeenCalledTimes(1)
    expect(wrapper.find('[data-test="setting-max_attachments_per_job"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="setting-max_attachment_mb"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('單筆求職紀錄附件數上限')
    expect(wrapper.text()).toContain('單檔大小上限 (MB)')
  })

  it('save button is disabled until form changes', async () => {
    vi.spyOn(settingsApi, 'getConfig').mockResolvedValue(SAMPLE)

    const wrapper = mount(AdminSettings)
    await flushPromises()

    const saveBtn = wrapper.find('[data-test="settings-save"]')
    expect(saveBtn.attributes('disabled')).toBeDefined()
  })

  it('PUTs the values on save and refreshes from response', async () => {
    vi.spyOn(settingsApi, 'getConfig').mockResolvedValue(SAMPLE)
    const updated = {
      fields: [
        { ...SAMPLE.fields[0], value: 25 },
        { ...SAMPLE.fields[1], value: 50 },
      ],
    }
    const update = vi.spyOn(settingsApi, 'updateConfig').mockResolvedValue(updated)
    const success = vi.spyOn(ElMessage, 'success').mockImplementation(() => {})

    const wrapper = mount(AdminSettings)
    await flushPromises()

    // Mutate the form via the exposed reactive state on the component
    // instance. Driving el-input-number's spinner buttons would be brittle.
    const vm = wrapper.vm
    vm.form.max_attachments_per_job = 25
    vm.form.max_attachment_mb = 50
    await flushPromises()

    await wrapper.find('[data-test="settings-save"]').trigger('click')
    await flushPromises()

    expect(update).toHaveBeenCalledWith({
      max_attachments_per_job: 25,
      max_attachment_mb: 50,
    })
    expect(success).toHaveBeenCalled()
    // After refresh, the form mirrors the server-confirmed values.
    expect(vm.form.max_attachments_per_job).toBe(25)
  })

  it('shows error toast with API detail when PUT fails with 422', async () => {
    vi.spyOn(settingsApi, 'getConfig').mockResolvedValue(SAMPLE)
    vi.spyOn(settingsApi, 'updateConfig').mockRejectedValue(
      Object.assign(new Error('422'), {
        response: { status: 422, data: { detail: 'value out of range' } },
      }),
    )
    const error = vi.spyOn(ElMessage, 'error').mockImplementation(() => {})

    const wrapper = mount(AdminSettings)
    await flushPromises()

    wrapper.vm.form.max_attachments_per_job = 5
    await flushPromises()

    await wrapper.find('[data-test="settings-save"]').trigger('click')
    await flushPromises()

    expect(error).toHaveBeenCalledWith('value out of range')
    // Form retains the user's edit so they can correct it without re-typing.
    expect(wrapper.vm.form.max_attachments_per_job).toBe(5)
  })

  it('reset reverts unsaved edits', async () => {
    vi.spyOn(settingsApi, 'getConfig').mockResolvedValue(SAMPLE)

    const wrapper = mount(AdminSettings)
    await flushPromises()

    wrapper.vm.form.max_attachments_per_job = 42
    await flushPromises()
    await wrapper.find('[data-test="settings-reset"]').trigger('click')

    expect(wrapper.vm.form.max_attachments_per_job).toBe(10)
  })

  it('the el-input-number is remounted after save so internal state stays fresh', async () => {
    // Regression guard for the reported "stuck at max after save" bug:
    // formVersion bumps on every applyFromResponse, forcing :key to
    // change so Vue tears down and rebuilds the input. Without this,
    // el-input-number's currentValue could lag behind its modelValue
    // prop when a user-typed out-of-range value was silently clamped.
    vi.spyOn(settingsApi, 'getConfig').mockResolvedValue(SAMPLE)
    vi.spyOn(settingsApi, 'updateConfig').mockResolvedValue(SAMPLE)

    const wrapper = mount(AdminSettings)
    await flushPromises()
    const versionBefore = wrapper.vm.formVersion

    // Move a value so save has something to send, then save.
    wrapper.vm.form.max_attachments_per_job = 15
    await flushPromises()
    await wrapper.find('[data-test="settings-save"]').trigger('click')
    await flushPromises()

    expect(wrapper.vm.formVersion).toBe(versionBefore + 1)
  })

  it('can decrease via the spinner after saving at max', async () => {
    // Reproduce the reported bug: user saves the value at max=50,
    // then the input field gets stuck and cannot be decremented.
    vi.spyOn(settingsApi, 'getConfig').mockResolvedValue({
      fields: [
        { ...SAMPLE.fields[0], value: 50 },
        SAMPLE.fields[1],
      ],
    })
    vi.spyOn(settingsApi, 'updateConfig').mockImplementation(async ({ values }) => {
      return {
        fields: [
          { ...SAMPLE.fields[0], value: values.max_attachments_per_job ?? 50 },
          { ...SAMPLE.fields[1], value: values.max_attachment_mb ?? 20 },
        ],
      }
    })

    const wrapper = mount(AdminSettings)
    await flushPromises()
    // Start state mirrors "just saved at max=50".
    expect(wrapper.vm.form.max_attachments_per_job).toBe(50)

    // Click the spinner decrease button on the max-attachments input.
    const inputNumber = wrapper
      .findAllComponents({ name: 'ElInputNumber' })
      .find((c) => c.attributes('data-test') === 'setting-max_attachments_per_job')
    expect(inputNumber).toBeTruthy()

    const decreaseBtn = inputNumber.find('.el-input-number__decrease')
    expect(decreaseBtn.exists()).toBe(true)
    expect(decreaseBtn.classes()).not.toContain('is-disabled')

    await decreaseBtn.trigger('mousedown')
    await flushPromises()

    expect(wrapper.vm.form.max_attachments_per_job).toBe(49)
    // dirty flips to true, save button re-enables.
    const saveBtn = wrapper.find('[data-test="settings-save"]')
    expect(saveBtn.attributes('disabled')).toBeUndefined()
  })

  it('shows the error banner when GET fails', async () => {
    vi.spyOn(settingsApi, 'getConfig').mockRejectedValue(new Error('boom'))

    const wrapper = mount(AdminSettings)
    await flushPromises()

    expect(wrapper.text()).toContain('載入設定失敗')
    expect(wrapper.find('[data-test="settings-form"]').exists()).toBe(false)
  })
})
