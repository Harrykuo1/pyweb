import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

import JobFilterBar from './JobFilterBar.vue'
import { jobsApi } from '../../api/jobs'

function mountBar(props = {}) {
  return mount(JobFilterBar, {
    props: { kind: '', year: null, company: [], category: [], q: '', ...props },
  })
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('JobFilterBar', () => {
  it('renders the kind chips and filter controls', () => {
    const wrapper = mountBar()
    expect(wrapper.find('[data-test="filter-kind-all"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="filter-kind-internship"]').exists()).toBe(
      true,
    )
    expect(wrapper.find('[data-test="filter-year"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="filter-company"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="filter-category"]').exists()).toBe(true)
    expect(wrapper.find('.filter-search input').attributes('placeholder')).toBe(
      '搜尋姓名、心得內文',
    )
  })

  it('marks the active kind chip from the model value', () => {
    const wrapper = mountBar({ kind: 'internship' })
    expect(
      wrapper.find('[data-test="filter-kind-internship"]').classes(),
    ).toContain('is-active')
  })

  it('emits update:kind when a chip is clicked', async () => {
    const wrapper = mountBar()
    await wrapper.find('[data-test="filter-kind-fulltime"]').trigger('click')
    expect(wrapper.emitted('update:kind')).toEqual([['fulltime']])
  })

  it('wires the company remote-method to jobsApi.listCompanies', async () => {
    const spy = vi.spyOn(jobsApi, 'listCompanies').mockResolvedValue(['Acme'])
    const select = mountBar()
      .find('[data-test="filter-company"]')
      .findComponent({ name: 'ElSelect' })
    await select.props('remoteMethod')('ac')
    await flushPromises()
    expect(spy).toHaveBeenCalledWith('ac')
  })

  it('wires the category remote-method to jobsApi.listCategories', async () => {
    const spy = vi
      .spyOn(jobsApi, 'listCategories')
      .mockResolvedValue(['Backend'])
    const select = mountBar()
      .find('[data-test="filter-category"]')
      .findComponent({ name: 'ElSelect' })
    await select.props('remoteMethod')('de')
    await flushPromises()
    expect(spy).toHaveBeenCalledWith('de')
  })

  it('pushes already-selected suggestions to the bottom of the options', async () => {
    vi.spyOn(jobsApi, 'listCompanies').mockResolvedValue(['Acme', 'Globex'])
    const select = mountBar({ company: ['Acme'] })
      .find('[data-test="filter-company"]')
      .findComponent({ name: 'ElSelect' })
    await select.props('remoteMethod')('a')
    await flushPromises()
    const labels = select
      .findAllComponents({ name: 'ElOption' })
      .map((o) => o.props('label'))
    // 'Acme' is already selected, so it sorts after the fresh 'Globex'.
    expect(labels).toEqual(['Globex', 'Acme'])
  })
})
