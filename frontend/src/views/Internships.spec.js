import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import Internships from './Internships.vue'

describe('Internships.vue', () => {
  it('renders the page title', () => {
    const wrapper = mount(Internships)
    expect(wrapper.find('[data-test="internships-page"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('求職紀錄')
  })
})
