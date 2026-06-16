import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import JobCardSkeleton from './JobCardSkeleton.vue'

describe('JobCardSkeleton', () => {
  it('renders shimmer placeholder lines', () => {
    const wrapper = mount(JobCardSkeleton)
    expect(wrapper.find('.skeleton-card').exists()).toBe(true)
    expect(wrapper.findAll('.shimmer').length).toBeGreaterThan(0)
  })
})
