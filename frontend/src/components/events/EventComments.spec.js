import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import EventComments from './EventComments.vue'
import DeleteWithPasswordDialog from '../DeleteWithPasswordDialog.vue'
import { eventsApi } from '../../api/events'
import { useAuthStore } from '../../stores/auth'

vi.mock('element-plus', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    ElMessage: Object.assign(
      vi.fn(() => ({ close: vi.fn() })),
      {
        success: vi.fn(),
        error: vi.fn(),
        info: vi.fn(),
        warning: vi.fn(),
      },
    ),
    ElMessageBox: { confirm: vi.fn(() => Promise.resolve()) },
  }
})

import { ElMessage, ElMessageBox } from 'element-plus'

function comment(overrides = {}) {
  return {
    id: 1,
    event_id: 1,
    body: '好活動',
    created_at: '2026-03-02T10:00:00Z',
    edited_at: null,
    author_display_name: '我本人',
    author_user_id: null,
    can_edit: false,
    can_delete: false,
    ...overrides,
  }
}

beforeEach(() => {
  setActivePinia(createPinia())
})

afterEach(() => {
  vi.restoreAllMocks()
  // restoreAllMocks doesn't clear the persistent vi.fn()s from vi.mock, so
  // clear their call history too or counts bleed across tests.
  vi.clearAllMocks()
  document.body.innerHTML = ''
})

async function mountComments({ role = 'member', comments = [] } = {}) {
  const auth = useAuthStore()
  auth.user = { id: 1, role }
  vi.spyOn(eventsApi, 'listComments').mockResolvedValue(comments)
  const wrapper = mount(EventComments, { props: { eventId: 1, active: true } })
  await flushPromises()
  return wrapper
}

describe('EventComments', () => {
  it('loads and renders comments when the dialog is active', async () => {
    const wrapper = await mountComments({
      comments: [
        comment({ id: 1, body: '第一則', author_display_name: '阿明' }),
        comment({ id: 2, body: '第二則', edited_at: '2026-03-02T11:00:00Z' }),
      ],
    })
    expect(eventsApi.listComments).toHaveBeenCalledWith(1)
    const items = wrapper.findAll('[data-test="comment-item"]')
    expect(items).toHaveLength(2)
    expect(items[0].find('[data-test="comment-author"]').text()).toBe('阿明')
    expect(items[0].find('[data-test="comment-body"]').text()).toBe('第一則')
    // The second one was edited → shows the marker.
    expect(items[1].find('[data-test="comment-edited"]').exists()).toBe(true)
    expect(items[0].find('[data-test="comment-edited"]').exists()).toBe(false)
  })

  it('shows the empty state when there are no comments', async () => {
    const wrapper = await mountComments({ comments: [] })
    expect(wrapper.find('[data-test="comments-empty"]').exists()).toBe(true)
  })

  it('hides the compose box for the read-only viewer role', async () => {
    const wrapper = await mountComments({ role: 'viewer' })
    expect(wrapper.find('[data-test="comment-compose"]').exists()).toBe(false)
  })

  it('submits a new comment and appends it to the list', async () => {
    const wrapper = await mountComments({ comments: [] })
    const created = comment({
      id: 9,
      body: '新留言',
      can_edit: true,
      can_delete: true,
    })
    const spy = vi.spyOn(eventsApi, 'createComment').mockResolvedValue(created)

    await wrapper.find('textarea').setValue('新留言')
    await wrapper.find('[data-test="comment-submit"]').trigger('click')
    await flushPromises()

    expect(spy).toHaveBeenCalledWith(1, '新留言')
    const items = wrapper.findAll('[data-test="comment-item"]')
    expect(items).toHaveLength(1)
    expect(items[0].find('[data-test="comment-body"]').text()).toBe('新留言')
    // Draft cleared after a successful post.
    expect(wrapper.find('textarea').element.value).toBe('')
  })

  it('lets the author edit their own comment', async () => {
    const wrapper = await mountComments({
      comments: [
        comment({ id: 3, body: '打錯字', can_edit: true, can_delete: true }),
      ],
    })
    const updated = comment({
      id: 3,
      body: '更正了',
      can_edit: true,
      can_delete: true,
      edited_at: '2026-03-02T12:00:00Z',
    })
    const spy = vi.spyOn(eventsApi, 'updateComment').mockResolvedValue(updated)

    await wrapper.find('[data-test="comment-edit"]').trigger('click')
    // While editing, the edit textarea is first in the DOM (before compose).
    await wrapper.findAll('textarea')[0].setValue('更正了')
    await wrapper.find('[data-test="comment-edit-save"]').trigger('click')
    await flushPromises()

    expect(spy).toHaveBeenCalledWith(1, 3, '更正了')
    expect(wrapper.find('[data-test="comment-body"]').text()).toBe('更正了')
    expect(wrapper.find('[data-test="comment-edited"]').exists()).toBe(true)
  })

  it('deletes the author’s own comment after a plain confirm (no password)', async () => {
    const wrapper = await mountComments({
      comments: [comment({ id: 4, can_edit: true, can_delete: true })],
    })
    const spy = vi.spyOn(eventsApi, 'removeComment').mockResolvedValue()

    await wrapper.find('[data-test="comment-delete"]').trigger('click')
    await flushPromises()

    expect(ElMessageBox.confirm).toHaveBeenCalled()
    expect(spy).toHaveBeenCalledWith(1, 4)
    expect(wrapper.findAll('[data-test="comment-item"]')).toHaveLength(0)
  })

  it('routes an admin deleting someone else’s comment through the password dialog', async () => {
    const wrapper = await mountComments({
      role: 'admin',
      // Not the author (can_edit false) but can_delete → admin moderation.
      comments: [comment({ id: 5, can_edit: false, can_delete: true })],
    })
    const spy = vi.spyOn(eventsApi, 'removeComment').mockResolvedValue()

    await wrapper.find('[data-test="comment-delete"]').trigger('click')
    await flushPromises()

    // The password dialog opens; the delete call waits for confirmation.
    expect(spy).not.toHaveBeenCalled()
    expect(ElMessageBox.confirm).not.toHaveBeenCalled()
    const dialog = wrapper.findComponent(DeleteWithPasswordDialog)
    expect(dialog.props('modelValue')).toBe(true)
  })
})
