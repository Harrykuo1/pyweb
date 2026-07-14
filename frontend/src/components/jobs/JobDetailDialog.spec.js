import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import JobDetailDialog from './JobDetailDialog.vue'
import { useAuthStore } from '../../stores/auth'
import { jobsApi } from '../../api/jobs'

vi.mock('md-editor-v3', () => ({
  MdPreview: {
    name: 'MdPreview',
    props: ['modelValue'],
    template: '<div class="md-preview-stub">{{ modelValue }}</div>',
  },
}))
vi.mock('md-editor-v3/lib/preview.css', () => ({}))

const sample = {
  id: 1,
  job_year: 2025,
  job_month: 4,
  company: 'Acme',
  kind: 'internship',
  display_name: 'Alice',
  status: 'accepted',
  experience_md: '## interview content',
  timeline_md: '| date | event |\n|---|---|\n| 5/1 | apply |',
  created_at: '2025-05-01T00:00:00+00:00',
  like_count: 3,
  liked_by_me: false,
}

beforeEach(() => {
  setActivePinia(createPinia())
  // The embedded comment thread fetches on open; stub it so these tests
  // don't hit the real client.
  vi.spyOn(jobsApi, 'listComments').mockResolvedValue([])
})

afterEach(() => {
  vi.restoreAllMocks()
  document.body.innerHTML = ''
})

async function mountDialog(props = {}, role = 'admin') {
  const auth = useAuthStore()
  auth.user = { id: 1, username: 'a', role }
  const wrapper = mount(JobDetailDialog, {
    props: { modelValue: true, job: sample, ...props },
  })
  await flushPromises()
  return wrapper
}

describe('JobDetailDialog — likes', () => {
  it('renders the like button with the job count', async () => {
    const wrapper = await mountDialog()
    expect(wrapper.find('[data-test="like-count"]').text()).toBe('3')
  })

  it('likes the job and emits like-changed', async () => {
    const likeSpy = vi
      .spyOn(jobsApi, 'like')
      .mockResolvedValue({ like_count: 4, liked: true })
    const wrapper = await mountDialog()
    await wrapper.find('[data-test="like-toggle"]').trigger('click')
    await flushPromises()

    expect(likeSpy).toHaveBeenCalledWith(1)
    expect(wrapper.find('[data-test="like-count"]').text()).toBe('4')
    expect(wrapper.emitted('like-changed').at(-1)[0]).toMatchObject({
      id: 1,
      liked: true,
      likeCount: 4,
    })
  })

  it('reflects an in-place like change on the job (liked from its card)', async () => {
    const { reactive } = await import('vue')
    const job = reactive({ ...sample, like_count: 3, liked_by_me: false })
    const wrapper = await mountDialog({ job })
    expect(wrapper.find('[data-test="like-count"]').text()).toBe('3')

    job.like_count = 4
    job.liked_by_me = true
    await flushPromises()

    expect(wrapper.find('[data-test="like-count"]').text()).toBe('4')
    expect(wrapper.find('[data-test="like-toggle"]').classes()).toContain(
      'is-liked',
    )
  })

  it('opens the likers dialog and lists who liked', async () => {
    vi.spyOn(jobsApi, 'listLikers').mockResolvedValue([
      {
        user_id: 2,
        display_name: '阿明',
        member_id: null,
        has_photo: false,
        photo_updated_at: null,
      },
    ])
    const wrapper = await mountDialog()
    await wrapper.find('[data-test="like-count"]').trigger('click')
    await flushPromises()

    expect(jobsApi.listLikers).toHaveBeenCalledWith(1)
    expect(wrapper.find('[data-test="liker-item"]').text()).toContain('阿明')
  })
})

describe('JobDetailDialog — header', () => {
  it('shows the kind badge, company, real name and meta', async () => {
    const wrapper = await mountDialog()
    expect(
      wrapper.find('[data-test="detail-kind-internship"]').text(),
    ).toContain('實習')
    expect(wrapper.find('[data-test="detail-company"]').text()).toContain(
      'Acme',
    )
    expect(wrapper.find('[data-test="detail-real-name"]').text()).toContain(
      'Alice',
    )
    expect(wrapper.text()).toContain('2025/04 求職')
  })

  it('shows 匿名 styling when display_name is null', async () => {
    const wrapper = await mountDialog({
      job: { ...sample, display_name: null },
    })
    expect(wrapper.find('[data-test="detail-anonymous"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="detail-real-name"]').exists()).toBe(false)
  })

  it('masks an anonymous post by default and reveals the real name on click', async () => {
    const wrapper = await mountDialog({
      job: { ...sample, is_anonymous: true, display_name: 'Alice' },
    })
    // Masked by default even for admin: shows 匿名 and an "anonymous" badge,
    // not the real name.
    expect(wrapper.find('[data-test="detail-anonymous"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="detail-anon-badge"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="detail-real-name"]').exists()).toBe(false)

    // Admin has a reveal control; clicking it shows the real name.
    await wrapper.find('[data-test="anon-reveal"]').trigger('click')
    expect(wrapper.find('[data-test="detail-real-name"]').text()).toContain(
      'Alice',
    )
  })

  it('re-masks the name each time the dialog reopens', async () => {
    const wrapper = await mountDialog({
      job: { ...sample, is_anonymous: true, display_name: 'Alice' },
    })
    await wrapper.find('[data-test="anon-reveal"]').trigger('click')
    expect(wrapper.find('[data-test="detail-real-name"]').exists()).toBe(true)

    await wrapper.setProps({ modelValue: false })
    await wrapper.setProps({ modelValue: true })
    await flushPromises()
    // Reopening resets to masked so an anonymous name never lingers revealed.
    expect(wrapper.find('[data-test="detail-anonymous"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="detail-real-name"]').exists()).toBe(false)
  })

  it('hides the reveal control while an admin previews as a member', async () => {
    const wrapper = await mountDialog({
      job: { ...sample, is_anonymous: true, display_name: 'Alice' },
    })
    expect(wrapper.find('[data-test="anon-reveal"]').exists()).toBe(true)

    useAuthStore().previewAsMember = true
    await flushPromises()
    expect(wrapper.find('[data-test="anon-reveal"]').exists()).toBe(false)
  })

  it('does not offer a reveal control to non-admins on anonymous posts', async () => {
    const wrapper = await mountDialog(
      { job: { ...sample, is_anonymous: true, display_name: null } },
      'member',
    )
    expect(wrapper.find('[data-test="detail-anonymous"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="anon-reveal"]').exists()).toBe(false)
  })

  it('shows a status pill for non-accepted posts and the rejection reason', async () => {
    const accepted = await mountDialog()
    expect(accepted.find('[data-test="detail-status-pending"]').exists()).toBe(
      false,
    )

    const rejected = await mountDialog({
      job: { ...sample, status: 'rejected', review_reason: '內容不足' },
    })
    expect(
      rejected.find('[data-test="detail-status-rejected"]').text(),
    ).toContain('已退回')
    expect(
      rejected.find('[data-test="detail-reject-reason"]').text(),
    ).toContain('內容不足')
  })

  it('themes header by kind', async () => {
    const wrapper = await mountDialog({
      job: { ...sample, kind: 'fulltime' },
    })
    const header = wrapper.find('.detail-header')
    expect(header.classes()).toContain('detail-header--fulltime')
    expect(wrapper.find('[data-test="detail-kind-fulltime"]').text()).toContain(
      '正職',
    )
  })
})

describe('JobDetailDialog — markdown tabs', () => {
  it('renders the experience tab body via MdPreview', async () => {
    const wrapper = await mountDialog()
    const exp = wrapper.find('[data-test="detail-experience"]')
    expect(exp.exists()).toBe(true)
    expect(exp.text()).toContain('## interview content')
  })

  it('renders the timeline tab when timeline_md (legacy) is present', async () => {
    const wrapper = await mountDialog()
    expect(wrapper.text()).toContain('時程表')
  })

  it('hides the timeline tab when both timeline_md and timeline_events are empty', async () => {
    const wrapper = await mountDialog({
      job: { ...sample, timeline_md: '', timeline_events: null },
    })
    expect(wrapper.text()).not.toContain('時程表')

    const wrapper2 = await mountDialog({
      job: { ...sample, timeline_md: null, timeline_events: [] },
    })
    expect(wrapper2.text()).not.toContain('時程表')
  })

  it('renders TimelineDisplay when timeline_events is non-empty (preferred over legacy markdown)', async () => {
    // Even if both fields are populated, the structured events take
    // priority — that's the migration path: editing a legacy job
    // refills timeline_events, which immediately shadows the old
    // markdown column without us having to delete it server-side.
    const wrapper = await mountDialog({
      job: {
        ...sample,
        timeline_md: '舊資料',
        timeline_events: [
          { date: '2025-02-23', event: '投遞' },
          { date: '2025-04-17', event: '拿到 offer' },
        ],
      },
    })
    expect(wrapper.find('[data-test="timeline-display"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="detail-timeline-legacy"]').exists()).toBe(
      false,
    )
    expect(wrapper.text()).toContain('投遞')
    expect(wrapper.text()).toContain('拿到 offer')
  })

  it('falls back to legacy markdown with a deprecated badge when only timeline_md is set', async () => {
    const wrapper = await mountDialog({
      job: {
        ...sample,
        timeline_md: '舊版時程內文',
        timeline_events: null,
      },
    })
    expect(wrapper.find('[data-test="timeline-display"]').exists()).toBe(false)
    const legacy = wrapper.find('[data-test="detail-timeline-legacy"]')
    expect(legacy.exists()).toBe(true)
    expect(legacy.text()).toContain('舊版時程表')
    expect(wrapper.text()).toContain('舊版時程內文')
  })

  it('renders the attachments tab when attachment_count > 0', async () => {
    const wrapper = await mountDialog({
      job: { ...sample, attachment_count: 2 },
    })
    // Inspect the visible tab nav text — Element Plus's el-tab-pane
    // doesn't surface its data-test on the nav element, so checking
    // the rendered label is more reliable (matches the timeline tab
    // tests' pattern).
    expect(wrapper.text()).toContain('附件')
  })

  it('hides the attachments tab when attachment_count is 0 or missing', async () => {
    // Mirror the timeline behaviour — no content → no tab. Both the
    // explicit-zero case and the missing-field case should hide.
    const w1 = await mountDialog({
      job: { ...sample, attachment_count: 0 },
    })
    expect(w1.text()).not.toContain('附件')

    const { attachment_count, ...withoutCount } = sample
    const w2 = await mountDialog({ job: withoutCount })
    expect(w2.text()).not.toContain('附件')
  })
})

describe('JobDetailDialog — edit button', () => {
  it('emits edit and closes when can_edit and 編輯 is clicked', async () => {
    const job = { ...sample, can_edit: true }
    const wrapper = await mountDialog({ job })
    const btn = wrapper.find('[data-test="detail-edit-button"]')
    expect(btn.exists()).toBe(true)
    await btn.trigger('click')
    expect(wrapper.emitted('edit')?.[0]?.[0]).toEqual(job)
    expect(wrapper.emitted('update:modelValue')?.at(-1)).toEqual([false])
  })

  it('hides the edit button when can_edit is false', async () => {
    const wrapper = await mountDialog({ job: { ...sample, can_edit: false } })
    expect(wrapper.find('[data-test="detail-edit-button"]').exists()).toBe(
      false,
    )
  })
})
