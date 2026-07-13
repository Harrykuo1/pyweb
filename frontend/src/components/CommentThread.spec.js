import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import CommentThread from './CommentThread.vue'
import DeleteWithPasswordDialog from './DeleteWithPasswordDialog.vue'
import MemberAvatar from './members/MemberAvatar.vue'
import { useAuthStore } from '../stores/auth'

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

import { ElMessageBox } from 'element-plus'

function comment(overrides = {}) {
  return {
    id: 1,
    body: '好活動',
    created_at: '2026-03-02T10:00:00Z',
    edited_at: null,
    author_display_name: '我本人',
    author_user_id: null,
    author_member_id: null,
    author_has_photo: false,
    author_photo_updated_at: null,
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
  vi.clearAllMocks()
  document.body.innerHTML = ''
})

async function mountThread({ role = 'member', comments = [], api = {} } = {}) {
  const auth = useAuthStore()
  auth.user = { id: 1, role }
  const resolvedApi = {
    list: vi.fn().mockResolvedValue(comments),
    create: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
    ...api,
  }
  const wrapper = mount(CommentThread, {
    props: { postId: 1, api: resolvedApi, active: true },
  })
  await flushPromises()
  return { wrapper, api: resolvedApi }
}

describe('CommentThread', () => {
  it('loads the thread through the injected api', async () => {
    const { wrapper, api } = await mountThread({
      comments: [
        comment({ id: 1, body: '第一則', author_display_name: '阿明' }),
        comment({ id: 2, body: '第二則', edited_at: '2026-03-02T11:00:00Z' }),
      ],
    })
    expect(api.list).toHaveBeenCalledWith(1)
    const items = wrapper.findAll('[data-test="comment-item"]')
    expect(items).toHaveLength(2)
    expect(items[1].find('[data-test="comment-edited"]').exists()).toBe(true)
  })

  it('passes author member/photo info to MemberAvatar', async () => {
    const { wrapper } = await mountThread({
      comments: [
        comment({
          id: 1,
          author_display_name: '王子銜',
          author_member_id: 7,
          author_has_photo: true,
          author_photo_updated_at: '2026-01-01',
        }),
      ],
    })
    const avatar = wrapper.findComponent(MemberAvatar)
    expect(avatar.props('memberId')).toBe(7)
    expect(avatar.props('hasPhoto')).toBe(true)
  })

  it('hides the compose box for the read-only viewer role', async () => {
    const { wrapper } = await mountThread({ role: 'viewer' })
    expect(wrapper.find('[data-test="comment-compose"]').exists()).toBe(false)
  })

  it('submits a new comment via api.create and appends it', async () => {
    const created = comment({
      id: 9,
      body: '新留言',
      can_edit: true,
      can_delete: true,
    })
    const { wrapper, api } = await mountThread({
      comments: [],
      api: { create: vi.fn().mockResolvedValue(created) },
    })
    await wrapper.find('textarea').setValue('新留言')
    await wrapper.find('[data-test="comment-submit"]').trigger('click')
    await flushPromises()

    expect(api.create).toHaveBeenCalledWith(1, '新留言')
    expect(wrapper.findAll('[data-test="comment-item"]')).toHaveLength(1)
    expect(wrapper.find('textarea').element.value).toBe('')
  })

  it('edits an own comment via api.update', async () => {
    const updated = comment({
      id: 3,
      body: '更正了',
      can_edit: true,
      can_delete: true,
      edited_at: '2026-03-02T12:00:00Z',
    })
    const { wrapper, api } = await mountThread({
      comments: [
        comment({ id: 3, body: '打錯字', can_edit: true, can_delete: true }),
      ],
      api: { update: vi.fn().mockResolvedValue(updated) },
    })
    await wrapper.find('[data-test="comment-edit"]').trigger('click')
    await wrapper.findAll('textarea')[0].setValue('更正了')
    await wrapper.find('[data-test="comment-edit-save"]').trigger('click')
    await flushPromises()

    expect(api.update).toHaveBeenCalledWith(1, 3, '更正了')
    expect(wrapper.find('[data-test="comment-body"]').text()).toBe('更正了')
  })

  it('deletes an own comment after a plain confirm (no password)', async () => {
    const { wrapper, api } = await mountThread({
      comments: [comment({ id: 4, can_edit: true, can_delete: true })],
      api: { remove: vi.fn().mockResolvedValue() },
    })
    await wrapper.find('[data-test="comment-delete"]').trigger('click')
    await flushPromises()

    expect(ElMessageBox.confirm).toHaveBeenCalled()
    expect(api.remove).toHaveBeenCalledWith(1, 4)
    expect(wrapper.findAll('[data-test="comment-item"]')).toHaveLength(0)
  })

  it('routes an admin deleting someone else’s comment through the password dialog', async () => {
    const { wrapper, api } = await mountThread({
      role: 'admin',
      comments: [comment({ id: 5, can_edit: false, can_delete: true })],
    })
    await wrapper.find('[data-test="comment-delete"]').trigger('click')
    await flushPromises()

    expect(api.remove).not.toHaveBeenCalled()
    expect(ElMessageBox.confirm).not.toHaveBeenCalled()
    expect(
      wrapper.findComponent(DeleteWithPasswordDialog).props('modelValue'),
    ).toBe(true)
  })
})
