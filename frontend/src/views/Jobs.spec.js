import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import Jobs from './Jobs.vue'

describe('Jobs.vue', () => {
  it('renders the page title', () => {
    const wrapper = mount(Jobs)
    expect(wrapper.find('[data-test="jobs-page"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('求職紀錄')
  })
})
