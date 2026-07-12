import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import JobRecordCard from './JobRecordCard.vue'

const baseJob = {
  id: 1,
  job_year: 2024,
  job_month: 5,
  company: 'Acme',
  kind: 'internship',
  display_name: 'Alice',
  status: 'accepted',
  category: 'Backend',
  created_at: '2024-05-01T00:00:00+00:00',
}

function mountCard(job = baseJob) {
  return mount(JobRecordCard, { props: { job } })
}

describe('JobRecordCard', () => {
  it('renders company, kind label, real name, year/month and category', () => {
    const wrapper = mountCard()
    expect(wrapper.text()).toContain('Acme')
    expect(wrapper.find('[data-test="kind-internship"]').text()).toContain(
      '實習',
    )
    expect(wrapper.find('[data-test="real-name"]').text()).toContain('Alice')
    expect(wrapper.text()).toContain('2024/05 求職')
    expect(wrapper.find('[data-test="card-category"]').text()).toBe('Backend')
  })

  it('falls back to 匿名 and the anonymous data-test when display_name is null', () => {
    const wrapper = mountCard({ ...baseJob, display_name: null })
    expect(wrapper.find('[data-test="anonymous"]').text()).toContain('匿名')
    expect(wrapper.find('[data-test="real-name"]').exists()).toBe(false)
  })

  it('masks an anonymous post as 匿名 even when a real name is present (admin view)', () => {
    // The backend still sends admins the real name, but the list must not
    // show it — it could leak on screen while presenting.
    const wrapper = mountCard({
      ...baseJob,
      is_anonymous: true,
      display_name: 'Alice',
    })
    expect(wrapper.find('[data-test="anonymous"]').text()).toContain('匿名')
    expect(wrapper.text()).not.toContain('Alice')
    expect(wrapper.find('[data-test="real-name"]').exists()).toBe(false)
  })

  it('shows a status pill only for non-accepted posts', () => {
    expect(mountCard().find('[data-test="status-pending"]').exists()).toBe(
      false,
    )
    expect(
      mountCard({ ...baseJob, status: 'pending' })
        .find('[data-test="status-pending"]')
        .text(),
    ).toContain('審核中')
    expect(
      mountCard({ ...baseJob, status: 'rejected' })
        .find('[data-test="status-rejected"]')
        .text(),
    ).toContain('已退回')
  })

  it('shows only the year when job_month is missing', () => {
    const wrapper = mountCard({ ...baseJob, job_month: null })
    expect(wrapper.text()).toContain('2024 求職')
    expect(wrapper.text()).not.toContain('2024/05 求職')
  })

  it('omits the category chip when the job has no category', () => {
    const wrapper = mountCard({ ...baseJob, category: null })
    expect(wrapper.find('[data-test="card-category"]').exists()).toBe(false)
  })

  it('emits open with the job on click and on Enter', async () => {
    const wrapper = mountCard()
    await wrapper.find('[data-test="record-card"]').trigger('click')
    await wrapper.find('[data-test="record-card"]').trigger('keydown.enter')
    expect(wrapper.emitted('open')).toHaveLength(2)
    expect(wrapper.emitted('open')[0]).toEqual([baseJob])
  })

  it('applies the kind modifier class', () => {
    expect(mountCard().find('.record-card').classes()).toContain(
      'record-card--internship',
    )
    expect(
      mountCard({ ...baseJob, kind: 'fulltime' })
        .find('.record-card')
        .classes(),
    ).toContain('record-card--fulltime')
  })
})
