import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

import Settings from './Settings.vue'
import { authApi } from '../api/auth'

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

// Section components hit Pinia / network on mount; this spec only cares about
// the navigation shell (groups + sub-tabs + hash sync), so swap them all for
// tiny stubs. Stubbing by name also covers the dynamic <component :is>.
const stubs = {
  MemberRoster: {
    name: 'MemberRoster',
    emits: ['generate-invite'],
    template:
      '<div data-test="stub-roles"><button data-test="stub-roster-invite" @click="$emit(\'generate-invite\')" /></div>',
  },
  InvitesSection: { template: '<div data-test="stub-invites" />' },
  PendingLinksSection: { template: '<div data-test="stub-pending" />' },
  GuildConfigSection: { template: '<div data-test="stub-discord" />' },
  AppearanceSection: { template: '<div data-test="stub-appearance" />' },
  SystemLimitsSection: { template: '<div data-test="stub-system" />' },
  AccountSection: { template: '<div data-test="stub-account" />' },
}

beforeEach(() => {
  routeMock.hash = ''
  replaceMock.mockClear()
  // Badge fetch on entering the members group — resolve to an empty list so
  // nothing hits the network.
  vi.spyOn(authApi, 'listPendingLinks').mockResolvedValue([])
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('Settings.vue navigation shell', () => {
  it('renders exactly the three top-level groups in the sidebar', () => {
    const wrapper = mount(Settings, { global: { stubs } })
    // Exactly three group tabs — a stray fourth group would fail here.
    expect(wrapper.findAll('.settings-sidebar__item')).toHaveLength(3)
    expect(wrapper.findAll('[data-test="settings-tab-members"]')).toHaveLength(
      1,
    )
    expect(wrapper.findAll('[data-test="settings-tab-site"]')).toHaveLength(1)
    expect(wrapper.findAll('[data-test="settings-tab-account"]')).toHaveLength(
      1,
    )
  })

  it('defaults to the members group / roles sub and normalizes an empty hash', async () => {
    const wrapper = mount(Settings, { global: { stubs } })
    await flushPromises()
    expect(
      wrapper.find('[data-test="settings-active-sub-roles"]').exists(),
    ).toBe(true)
    expect(replaceMock).toHaveBeenCalledWith({ hash: '#roles' })
  })

  it('falls back to #roles for an unknown hash', async () => {
    routeMock.hash = '#garbage'
    const wrapper = mount(Settings, { global: { stubs } })
    await flushPromises()
    expect(
      wrapper.find('[data-test="settings-active-sub-roles"]').exists(),
    ).toBe(true)
    expect(replaceMock).toHaveBeenCalledWith({ hash: '#roles' })
  })

  it('deep-links #system to the site group without rewriting the hash', async () => {
    routeMock.hash = '#system'
    const wrapper = mount(Settings, { global: { stubs } })
    await flushPromises()
    expect(
      wrapper.find('[data-test="settings-active-sub-system"]').exists(),
    ).toBe(true)
    expect(wrapper.find('[data-test="settings-active-site"]').exists()).toBe(
      true,
    )
    // Hash already resolved to a valid leaf — leave it untouched.
    expect(replaceMock).not.toHaveBeenCalled()
  })

  it('resolves every legacy hash to the right group and sub', async () => {
    const cases = [
      { hash: '#roles', group: 'members', sub: 'roles' },
      { hash: '#invites', group: 'members', sub: 'invites' },
      { hash: '#pending-links', group: 'members', sub: 'pending-links' },
      { hash: '#discord', group: 'site', sub: 'discord' },
      { hash: '#appearance', group: 'site', sub: 'appearance' },
      { hash: '#system', group: 'site', sub: 'system' },
      { hash: '#account', group: 'account', sub: 'account' },
    ]
    for (const { hash, group, sub } of cases) {
      routeMock.hash = hash
      replaceMock.mockClear()
      const wrapper = mount(Settings, { global: { stubs } })
      await flushPromises()
      expect(
        wrapper.find(`[data-test="settings-active-sub-${sub}"]`).exists(),
      ).toBe(true)
      expect(
        wrapper.find(`[data-test="settings-active-${group}"]`).exists(),
      ).toBe(true)
      // A valid deep-link must round-trip unchanged.
      expect(replaceMock).not.toHaveBeenCalled()
      wrapper.unmount()
    }
  })

  it('clicking the site group jumps to its first sub (#discord)', async () => {
    const wrapper = mount(Settings, { global: { stubs } })
    await flushPromises()
    replaceMock.mockClear()

    await wrapper.find('[data-test="settings-tab-site"]').trigger('click')
    expect(
      wrapper.find('[data-test="settings-active-sub-discord"]').exists(),
    ).toBe(true)
    expect(replaceMock).toHaveBeenCalledWith({ hash: '#discord' })
  })

  it('clicking a sub-tab switches the sub and syncs the hash within a group', async () => {
    routeMock.hash = '#roles'
    const wrapper = mount(Settings, { global: { stubs } })
    await flushPromises()
    replaceMock.mockClear()

    await wrapper.find('[data-test="settings-subtab-invites"]').trigger('click')
    expect(
      wrapper.find('[data-test="settings-active-sub-invites"]').exists(),
    ).toBe(true)
    expect(replaceMock).toHaveBeenCalledWith({ hash: '#invites' })
  })

  it('renders the component actually mapped to each leaf', async () => {
    routeMock.hash = '#discord'
    const discordWrapper = mount(Settings, { global: { stubs } })
    await flushPromises()
    expect(discordWrapper.find('[data-test="stub-discord"]').exists()).toBe(
      true,
    )
    expect(discordWrapper.find('[data-test="stub-roles"]').exists()).toBe(false)

    routeMock.hash = '#roles'
    const rolesWrapper = mount(Settings, { global: { stubs } })
    await flushPromises()
    expect(rolesWrapper.find('[data-test="stub-roles"]').exists()).toBe(true)
    expect(rolesWrapper.find('[data-test="stub-discord"]').exists()).toBe(false)
  })

  it('shows the待連結 badge with the unread count and hides it when empty', async () => {
    // Non-empty: badge shows the count.
    authApi.listPendingLinks.mockResolvedValue([{}, {}, {}])
    routeMock.hash = '#roles'
    const withBadge = mount(Settings, { global: { stubs } })
    await flushPromises()
    const badge = withBadge.find(
      '[data-test="settings-subtab-badge-pending-links"]',
    )
    expect(badge.exists()).toBe(true)
    expect(badge.text()).toBe('3')

    // Empty (beforeEach default resolves []): no badge.
    authApi.listPendingLinks.mockResolvedValue([])
    const noBadge = mount(Settings, { global: { stubs } })
    await flushPromises()
    expect(
      noBadge
        .find('[data-test="settings-subtab-badge-pending-links"]')
        .exists(),
    ).toBe(false)
  })

  it('roster generate-invite switches the members group to the invites sub', async () => {
    routeMock.hash = '#roles'
    const wrapper = mount(Settings, { global: { stubs } })
    await flushPromises()
    replaceMock.mockClear()

    await wrapper.find('[data-test="stub-roster-invite"]').trigger('click')

    expect(
      wrapper.find('[data-test="settings-active-sub-invites"]').exists(),
    ).toBe(true)
    expect(replaceMock).toHaveBeenCalledWith({ hash: '#invites' })
  })

  it('marks the sidebar group of the active leaf as active', async () => {
    routeMock.hash = '#invites'
    const wrapper = mount(Settings, { global: { stubs } })
    await flushPromises()

    expect(
      wrapper.find('[data-test="settings-tab-members"]').classes(),
    ).toContain('is-active')
    expect(
      wrapper.find('[data-test="settings-tab-site"]').classes(),
    ).not.toContain('is-active')
  })

  it('shows a sub-tab bar for multi-sub groups but not for the account group', async () => {
    routeMock.hash = '#roles'
    const membersWrapper = mount(Settings, { global: { stubs } })
    await flushPromises()
    expect(
      membersWrapper.find('[data-test="settings-subtab-roles"]').exists(),
    ).toBe(true)

    routeMock.hash = '#account'
    const accountWrapper = mount(Settings, { global: { stubs } })
    await flushPromises()
    expect(
      accountWrapper.find('[data-test="settings-subtab-account"]').exists(),
    ).toBe(false)
  })
})
