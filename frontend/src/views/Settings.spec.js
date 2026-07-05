import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

import Settings from './Settings.vue'

const routeMock = { hash: '' }
const replaceMock = vi.fn()

vi.mock('vue-router', async () => {
  const actual = await vi.importActual('vue-router')
  return {
    ...actual,
    useRoute: () => routeMock,
    useRouter: () => ({ replace: replaceMock }),
  }
})

// Section components hit Pinia / network on mount; this spec only cares
// about layout & sidebar behavior, so swap them for tiny stubs.
const stubs = {
  AccountSection: { template: '<div data-test="stub-account" />' },
  AppearanceSection: { template: '<div data-test="stub-appearance" />' },
  SystemLimitsSection: { template: '<div data-test="stub-system" />' },
  PhotoCropDialog: { template: '<div data-test="stub-crop" />' },
}

beforeEach(() => {
  routeMock.hash = ''
  replaceMock.mockClear()
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('Settings.vue', () => {
  it('renders one sidebar entry per section', () => {
    const wrapper = mount(Settings, { global: { stubs } })
    expect(wrapper.find('[data-test="settings-tab-account"]').exists()).toBe(
      true,
    )
    expect(wrapper.find('[data-test="settings-tab-appearance"]').exists()).toBe(
      true,
    )
    expect(wrapper.find('[data-test="settings-tab-system"]').exists()).toBe(
      true,
    )
  })

  it('defaults to the account section when hash is empty', async () => {
    const wrapper = mount(Settings, { global: { stubs } })
    await flushPromises()
    expect(wrapper.find('[data-test="settings-active-account"]').exists()).toBe(
      true,
    )
    // Mount normalizes the URL hash so deep-links round-trip.
    expect(replaceMock).toHaveBeenCalledWith({ hash: '#account' })
  })

  it('honors a matching section hash on mount', async () => {
    routeMock.hash = '#system'
    const wrapper = mount(Settings, { global: { stubs } })
    await flushPromises()
    expect(wrapper.find('[data-test="settings-active-system"]').exists()).toBe(
      true,
    )
    // Hash already matched the active section, no replace needed.
    expect(replaceMock).not.toHaveBeenCalled()
  })

  it('falls back to default for an unknown hash', async () => {
    routeMock.hash = '#totally-bogus'
    const wrapper = mount(Settings, { global: { stubs } })
    await flushPromises()
    expect(wrapper.find('[data-test="settings-active-account"]').exists()).toBe(
      true,
    )
    expect(replaceMock).toHaveBeenCalledWith({ hash: '#account' })
  })

  it('clicking a sidebar item switches the active section and updates the hash', async () => {
    const wrapper = mount(Settings, { global: { stubs } })
    await flushPromises()
    replaceMock.mockClear()

    await wrapper.find('[data-test="settings-tab-appearance"]').trigger('click')
    expect(
      wrapper.find('[data-test="settings-active-appearance"]').exists(),
    ).toBe(true)
    expect(replaceMock).toHaveBeenCalledWith({ hash: '#appearance' })
  })

  it('marks the active sidebar item with is-active', async () => {
    const wrapper = mount(Settings, { global: { stubs } })
    await flushPromises()

    const accountBtn = wrapper.find('[data-test="settings-tab-account"]')
    expect(accountBtn.classes()).toContain('is-active')

    await wrapper.find('[data-test="settings-tab-system"]').trigger('click')
    expect(
      wrapper.find('[data-test="settings-tab-system"]').classes(),
    ).toContain('is-active')
    expect(
      wrapper.find('[data-test="settings-tab-account"]').classes(),
    ).not.toContain('is-active')
  })
})
