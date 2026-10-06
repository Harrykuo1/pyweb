import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ChannelNames from './ChannelNames.vue'
import { useAuthStore } from '../../stores/auth'
import { activityApi } from '../../api/activity'
vi.mock('../../api/activity', () => ({
  activityApi: { updateChannel: vi.fn() },
}))
const select = {
  props: ['modelValue'],
  emits: ['update:modelValue', 'change'],
  template: '<div><slot/></div>',
}
function render() {
  return mount(ChannelNames, {
    props: { channels: ['201'], names: { 201: '舊名' } },
    global: { stubs: { ElSelect: select, ElOption: true } },
  })
}
beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
  activityApi.updateChannel.mockResolvedValue({})
})
describe('channel name editor', () => {
  it('hides editor for members and admin member preview', () => {
    const auth = useAuthStore()
    auth.user = { role: 'member' }
    expect(render().find('button').exists()).toBe(false)
    auth.user = { role: 'admin' }
    auth.previewAsMember = true
    expect(render().find('button').exists()).toBe(false)
  })
  it('edits a name and tells parent to refresh labels', async () => {
    useAuthStore().user = { role: 'admin' }
    const w = render()
    await w.find('button').trigger('click')
    const input = w.findComponent(select)
    input.vm.$emit('update:modelValue', '201')
    input.vm.$emit('change', '201')
    await flushPromises()
    expect(w.find('input').element.value).toBe('舊名')
    await w.find('input').setValue(' 新名稱 🎉 ')
    await w.find('form').trigger('submit')
    await flushPromises()
    expect(activityApi.updateChannel).toHaveBeenCalledWith('201', '新名稱 🎉')
    expect(w.emitted('saved')).toHaveLength(1)
    expect(w.find('form').exists()).toBe(false)
  })
  it('keeps input on error without claiming success', async () => {
    useAuthStore().user = { role: 'admin' }
    activityApi.updateChannel.mockRejectedValue(new Error('403'))
    const w = render()
    await w.find('button').trigger('click')
    w.findComponent(select).vm.$emit('update:modelValue', '201')
    await w.find('input').setValue('新名')
    await w.find('form').trigger('submit')
    await flushPromises()
    expect(w.find('[role="alert"]').exists()).toBe(true)
    expect(w.emitted('saved')).toBeUndefined()
    expect(w.find('input').element.value).toBe('新名')
  })
})
