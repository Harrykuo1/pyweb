import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import JobSortRow from './JobSortRow.vue'

const options = [
  { key: 'created_at', label: '發布日期' },
  { key: 'company', label: '公司' },
]

function mountRow(props = {}) {
  return mount(JobSortRow, {
    props: { options, sortKey: 'created_at', sortOrder: 'desc', ...props },
  })
}

describe('JobSortRow', () => {
  it('renders one pill per option', () => {
    const wrapper = mountRow()
    expect(wrapper.findAll('.sort-pill')).toHaveLength(2)
    expect(wrapper.find('[data-test="sort-company"]').text()).toContain('公司')
  })

  it('marks the active sort key and shows the direction arrow', () => {
    const wrapper = mountRow({ sortKey: 'company', sortOrder: 'asc' })
    const active = wrapper.find('[data-test="sort-company"]')
    expect(active.classes()).toContain('is-active')
    expect(active.text()).toContain('↑')
    // The inactive pill shows no arrow.
    expect(wrapper.find('[data-test="sort-created_at"]').text()).not.toContain('↓')
  })

  it('shows a down arrow when the active order is desc', () => {
    const wrapper = mountRow({ sortKey: 'company', sortOrder: 'desc' })
    expect(wrapper.find('[data-test="sort-company"]').text()).toContain('↓')
  })

  it('emits toggle with the option key on click', async () => {
    const wrapper = mountRow()
    await wrapper.find('[data-test="sort-company"]').trigger('click')
    expect(wrapper.emitted('toggle')).toEqual([['company']])
  })
})
