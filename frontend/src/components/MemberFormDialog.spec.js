import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { membersApi } from '../api/members'
import MemberFormDialog from './MemberFormDialog.vue'

vi.mock('element-plus', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    ElMessage: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
  }
})

beforeEach(() => {
  setActivePinia(createPinia())
})

afterEach(() => {
  vi.restoreAllMocks()
  document.body.innerHTML = ''
})

async function mountDialog(props = {}) {
  const wrapper = mount(MemberFormDialog, {
    props: { modelValue: true, member: null, ...props },
    attachTo: document.body,
  })
  // ElDialog content may render after a microtask.
  await flushPromises()
  return wrapper
}

function setVmValue(wrapper, key, value) {
  // The dialog stores form fields in a reactive `form` object that is part
  // of <script setup> closure. Vue Test Utils does not surface it directly,
  // so we set values by typing into the matching DOM input.
  const inputs = Array.from(wrapper.element.querySelectorAll('input,textarea'))
  const map = {}
  for (const el of inputs) {
    if (el.placeholder?.includes('留空則使用今天')) map.joined_at = el
    else if (el.placeholder?.includes('Phase 7')) map.resume_md = el
    else if (el.tagName === 'TEXTAREA') map.resume_md = el
  }
  // Remaining inputs (number, real_name, current_position) are matched by
  // their visual order, which is stable.
  const ordered = inputs.filter((el) => !Object.values(map).includes(el))
  ;[map.graduation_year, map.real_name, map.current_position] = ordered

  const target = map[key]
  if (!target) throw new Error(`No DOM target for ${key}`)
  target.value = value
  target.dispatchEvent(new Event('input', { bubbles: true }))
  target.dispatchEvent(new Event('change', { bubbles: true }))
}

describe('MemberFormDialog', () => {
  it('shows 新增成員 title in create mode', async () => {
    const wrapper = await mountDialog()
    expect(wrapper.element.innerHTML).toContain('新增成員')
  })

  it('shows 編輯成員 title and prefilled values in edit mode', async () => {
    const wrapper = await mountDialog({
      member: {
        id: 1,
        graduation_year: 2022,
        real_name: 'Alice',
        current_position: 'SWE',
        resume_md: '# x',
        joined_at: '2022-05-01',
      },
    })
    expect(wrapper.element.innerHTML).toContain('編輯成員')

    const values = Array.from(
      wrapper.element.querySelectorAll('input,textarea'),
    ).map((el) => el.value)
    expect(values).toContain('Alice')
    expect(values).toContain('SWE')
    expect(values).toContain('# x')
  })

  it('create flow calls membersApi.create with the form payload', async () => {
    const create = vi.spyOn(membersApi, 'create').mockResolvedValue({ id: 1 })
    const wrapper = await mountDialog()

    setVmValue(wrapper, 'real_name', 'Carol')
    setVmValue(wrapper, 'current_position', 'PhD student')
    setVmValue(wrapper, 'resume_md', '# resume')

    await wrapper.find('[data-test="save-button"]').trigger('click')
    await flushPromises()

    expect(create).toHaveBeenCalledTimes(1)
    const payload = create.mock.calls[0][0]
    expect(payload.real_name).toBe('Carol')
    expect(payload.current_position).toBe('PhD student')
    expect(payload.resume_md).toBe('# resume')
    expect(typeof payload.graduation_year).toBe('number')
  })

  it('edit flow calls membersApi.update with the member id', async () => {
    const update = vi.spyOn(membersApi, 'update').mockResolvedValue({ id: 7 })
    const wrapper = await mountDialog({
      member: {
        id: 7,
        graduation_year: 2020,
        real_name: 'Old',
        current_position: 'Old',
        resume_md: null,
        joined_at: null,
      },
    })

    await wrapper.find('[data-test="save-button"]').trigger('click')
    await flushPromises()

    expect(update).toHaveBeenCalledTimes(1)
    expect(update.mock.calls[0][0]).toBe(7)
  })

  it('emits saved and closes the dialog after a successful save', async () => {
    vi.spyOn(membersApi, 'create').mockResolvedValue({ id: 1 })
    const wrapper = await mountDialog()

    setVmValue(wrapper, 'real_name', 'Alice')
    setVmValue(wrapper, 'current_position', 'SWE')

    await wrapper.find('[data-test="save-button"]').trigger('click')
    await flushPromises()

    expect(wrapper.emitted('saved')).toBeTruthy()
    expect(wrapper.emitted('update:modelValue')).toContainEqual([false])
  })

  it('does not emit saved when the API rejects', async () => {
    vi.spyOn(membersApi, 'create').mockRejectedValue(
      Object.assign(new Error('500'), { response: { status: 500 } }),
    )
    const wrapper = await mountDialog()

    setVmValue(wrapper, 'real_name', 'Alice')
    setVmValue(wrapper, 'current_position', 'SWE')

    await wrapper.find('[data-test="save-button"]').trigger('click')
    await flushPromises()

    expect(wrapper.emitted('saved')).toBeFalsy()
  })
})
