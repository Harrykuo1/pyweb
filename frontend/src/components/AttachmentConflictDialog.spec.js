import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

import AttachmentConflictDialog from './AttachmentConflictDialog.vue'

beforeEach(() => {})

afterEach(() => {
  vi.restoreAllMocks()
  document.body.innerHTML = ''
})

async function mountOpen(overrides = {}) {
  const wrapper = mount(AttachmentConflictDialog, {
    props: {
      modelValue: true,
      conflicts: [{ filename: 'a.pdf' }, { filename: 'b.pdf' }],
      ...overrides,
    },
    attachTo: document.body,
  })
  // el-dialog renders slot content after a microtask.
  await flushPromises()
  return wrapper
}

describe('AttachmentConflictDialog.vue', () => {
  it('seeds every conflict with "rename" as the default strategy', async () => {
    const wrapper = await mountOpen()
    expect(wrapper.vm.resolutions['a.pdf']).toBe('rename')
    expect(wrapper.vm.resolutions['b.pdf']).toBe('rename')
  })

  it('apply-to-all sets every row to the chosen strategy', async () => {
    const wrapper = await mountOpen()
    const btn = document.querySelector('[data-test="apply-all-overwrite"]')
    expect(btn).toBeTruthy()
    btn.click()
    await flushPromises()

    expect(wrapper.vm.resolutions['a.pdf']).toBe('overwrite')
    expect(wrapper.vm.resolutions['b.pdf']).toBe('overwrite')
  })

  it('confirm emits resolved with the current resolutions and closes', async () => {
    const wrapper = await mountOpen()
    document.querySelector('[data-test="apply-all-skip"]').click()
    await flushPromises()

    document.querySelector('[data-test="conflict-confirm"]').click()
    await flushPromises()

    const resolved = wrapper.emitted('resolved')
    expect(resolved).toHaveLength(1)
    expect(resolved[0][0]).toEqual({ 'a.pdf': 'skip', 'b.pdf': 'skip' })
    expect(wrapper.emitted('update:modelValue').at(-1)).toEqual([false])
  })

  it('cancel emits resolved=null and closes', async () => {
    const wrapper = await mountOpen()

    document.querySelector('[data-test="conflict-cancel"]').click()
    await flushPromises()

    expect(wrapper.emitted('resolved').at(-1)).toEqual([null])
    expect(wrapper.emitted('update:modelValue').at(-1)).toEqual([false])
  })

  it('rebuilds defaults when conflicts prop changes', async () => {
    const wrapper = await mountOpen({ conflicts: [{ filename: 'old.pdf' }] })
    expect(wrapper.vm.resolutions['old.pdf']).toBe('rename')

    await wrapper.setProps({
      conflicts: [{ filename: 'new.pdf' }, { filename: 'other.pdf' }],
    })
    await flushPromises()

    expect(wrapper.vm.resolutions['old.pdf']).toBeUndefined()
    expect(wrapper.vm.resolutions['new.pdf']).toBe('rename')
    expect(wrapper.vm.resolutions['other.pdf']).toBe('rename')
  })
})
