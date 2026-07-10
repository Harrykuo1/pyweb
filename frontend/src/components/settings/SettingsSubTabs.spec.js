import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import SettingsSubTabs from './SettingsSubTabs.vue'

const ITEMS = [
  { key: 'roles', label: '成員名冊' },
  { key: 'invites', label: '邀請連結' },
  { key: 'pending-links', label: '待連結', badge: 3 },
]

function mountBar(overrides = {}) {
  return mount(SettingsSubTabs, {
    props: { items: ITEMS, modelValue: 'roles', ...overrides },
  })
}

describe('SettingsSubTabs.vue', () => {
  it('renders one button per item', () => {
    const wrapper = mountBar()
    expect(wrapper.findAll('.settings-subtabs__item')).toHaveLength(3)
    expect(
      wrapper.find('[data-test="settings-subtab-roles"]').exists(),
    ).toBe(true)
    expect(
      wrapper.find('[data-test="settings-subtab-invites"]').exists(),
    ).toBe(true)
    expect(
      wrapper.find('[data-test="settings-subtab-pending-links"]').exists(),
    ).toBe(true)
  })

  it('marks the active item via class and aria-pressed', () => {
    const wrapper = mountBar({ modelValue: 'invites' })
    const activeBtn = wrapper.find('[data-test="settings-subtab-invites"]')
    expect(activeBtn.classes()).toContain('is-active')
    expect(activeBtn.attributes('aria-pressed')).toBe('true')

    const idleBtn = wrapper.find('[data-test="settings-subtab-roles"]')
    expect(idleBtn.classes()).not.toContain('is-active')
    expect(idleBtn.attributes('aria-pressed')).toBe('false')
  })

  it('uses semantic buttons, not the ARIA tab role (keyboard-safe)', () => {
    const wrapper = mountBar()
    expect(wrapper.find('[role="tablist"]').exists()).toBe(false)
    const btn = wrapper.find('[data-test="settings-subtab-roles"]')
    expect(btn.attributes('role')).toBeUndefined()
    expect(btn.attributes('aria-selected')).toBeUndefined()
  })

  it('emits update:modelValue when a sub-tab is clicked', async () => {
    const wrapper = mountBar()
    await wrapper
      .find('[data-test="settings-subtab-invites"]')
      .trigger('click')
    expect(wrapper.emitted('update:modelValue')).toEqual([['invites']])
  })

  it('does not re-emit when the already-active sub-tab is clicked', async () => {
    const wrapper = mountBar({ modelValue: 'roles' })
    await wrapper.find('[data-test="settings-subtab-roles"]').trigger('click')
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
  })

  it('renders a badge only when badge > 0', () => {
    const wrapper = mountBar()
    const badge = wrapper.find(
      '[data-test="settings-subtab-badge-pending-links"]',
    )
    expect(badge.exists()).toBe(true)
    expect(badge.text()).toBe('3')
    // No badge for items without one.
    expect(
      wrapper.find('[data-test="settings-subtab-badge-roles"]').exists(),
    ).toBe(false)
  })

  it('hides the badge when the count is zero', () => {
    const wrapper = mountBar({
      items: [{ key: 'pending-links', label: '待連結', badge: 0 }],
    })
    expect(
      wrapper.find('[data-test="settings-subtab-badge-pending-links"]').exists(),
    ).toBe(false)
  })
})
