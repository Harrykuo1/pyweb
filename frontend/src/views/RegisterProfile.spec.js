import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { membersApi } from '../api/members'
import { useAuthStore } from '../stores/auth'
import RegisterProfile from './RegisterProfile.vue'

const pushMock = vi.fn()

vi.mock('vue-router', async () => {
  const actual = await vi.importActual('vue-router')
  return { ...actual, useRouter: () => ({ push: pushMock }) }
})

vi.mock('element-plus', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, ElMessage: { success: vi.fn(), error: vi.fn() } }
})

beforeEach(() => {
  setActivePinia(createPinia())
  pushMock.mockClear()
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('RegisterProfile.vue', () => {
  it('submits the profile, refreshes auth, and redirects home', async () => {
    const createSpy = vi
      .spyOn(membersApi, 'createMyProfile')
      .mockResolvedValue({})
    const auth = useAuthStore()
    const fetchSpy = vi.spyOn(auth, 'fetchMe').mockResolvedValue()

    const wrapper = mount(RegisterProfile)
    wrapper.vm.form.graduation_year = 2025
    wrapper.vm.form.real_name = '新人'
    wrapper.vm.form.institution = 'NYCU'
    await wrapper.vm.handleSubmit()

    expect(createSpy).toHaveBeenCalledWith(
      expect.objectContaining({ real_name: '新人', institution: 'NYCU' }),
    )
    expect(fetchSpy).toHaveBeenCalled()
    expect(pushMock).toHaveBeenCalledWith('/')
  })

  it('starts with a blank graduation year so the member must enter it', () => {
    const wrapper = mount(RegisterProfile)
    expect(wrapper.vm.form.graduation_year).toBe(null)
  })

  it('logout escape hatch clears the session and returns to /login', async () => {
    const auth = useAuthStore()
    const logoutSpy = vi.spyOn(auth, 'logout').mockResolvedValue()

    const wrapper = mount(RegisterProfile)
    await wrapper.find('[data-test="logout"]').trigger('click')

    expect(logoutSpy).toHaveBeenCalled()
    expect(pushMock).toHaveBeenCalledWith('/login')
  })
})
