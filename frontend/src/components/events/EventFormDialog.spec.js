import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import EventFormDialog from './EventFormDialog.vue'
import { eventsApi } from '../../api/events'

vi.mock('md-editor-v3', () => ({
  MdEditor: {
    name: 'MdEditor',
    props: ['modelValue'],
    emits: ['update:modelValue'],
    methods: { on() {}, togglePreview() {}, togglePageFullscreen() {} },
    template:
      '<textarea class="md-editor-stub" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
}))
vi.mock('md-editor-v3/lib/style.css', () => ({}))
// EventPhotosManager fetches on mount; stub it out so the form spec stays
// focused on the form's own behaviour.
vi.mock('./EventPhotosManager.vue', () => ({
  default: {
    name: 'EventPhotosManager',
    props: ['eventId'],
    template: '<div class="photos-manager-stub" :data-event-id="eventId" />',
  },
}))

// ElInput forwards attrs (data-test) onto its inner <input>, so the
// data-test attribute can land directly on the input element.
function findInputByDataTest(wrapper, dataTest) {
  const el = wrapper.element.querySelector(`[data-test="${dataTest}"]`)
  if (!el) return null
  return el.tagName === 'INPUT' ? el : el.querySelector('input')
}
function setNativeValue(el, value) {
  el.value = value
  el.dispatchEvent(new Event('input', { bubbles: true }))
  el.dispatchEvent(new Event('change', { bubbles: true }))
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.spyOn(eventsApi, 'listTags').mockResolvedValue([])
})

afterEach(() => {
  vi.restoreAllMocks()
  document.body.innerHTML = ''
})

function mountForm(props = {}) {
  return mount(EventFormDialog, {
    props: { modelValue: true, event: null, ...props },
  })
}

describe('EventFormDialog — create', () => {
  it('posts a new event and switches to the photos tab', async () => {
    const create = vi.spyOn(eventsApi, 'create').mockResolvedValue({
      id: 9,
      title: '春酒',
      event_date: '2026-03-01',
      tags: [],
    })
    const wrapper = mountForm()
    await flushPromises()

    setNativeValue(findInputByDataTest(wrapper, 'form-title'), '春酒聚餐')
    // event_date is required and set via the date picker; assign directly
    // through the component's reactive form to avoid driving the picker UI.
    wrapper.vm.form.event_date = '2026-03-15'
    await wrapper.find('[data-test="save-event-button"]').trigger('click')
    await flushPromises()

    expect(create).toHaveBeenCalledTimes(1)
    const payload = create.mock.calls[0][0]
    expect(payload.title).toBe('春酒聚餐')
    expect(payload.event_date).toBe('2026-03-15')
    expect(wrapper.emitted('saved')).toBeTruthy()
  })

  it('blocks submit when title is empty', async () => {
    const create = vi.spyOn(eventsApi, 'create').mockResolvedValue({})
    const wrapper = mountForm()
    await flushPromises()

    wrapper.vm.form.event_date = '2026-03-15'
    await wrapper.find('[data-test="save-event-button"]').trigger('click')
    await flushPromises()
    expect(create).not.toHaveBeenCalled()
  })

  it('normalizes tags: trims, dedupes case-insensitively', async () => {
    const create = vi.spyOn(eventsApi, 'create').mockResolvedValue({ id: 1 })
    const wrapper = mountForm()
    await flushPromises()

    setNativeValue(findInputByDataTest(wrapper, 'form-title'), 'x')
    wrapper.vm.form.event_date = '2026-03-15'
    wrapper.vm.form.tags = [' 春酒 ', '春酒', '聚餐']
    await wrapper.find('[data-test="save-event-button"]').trigger('click')
    await flushPromises()

    expect(create.mock.calls[0][0].tags).toEqual(['春酒', '聚餐'])
  })
})

describe('EventFormDialog — edit', () => {
  it('updates an existing event without switching to photos', async () => {
    const update = vi.spyOn(eventsApi, 'update').mockResolvedValue({})
    const wrapper = mountForm({
      event: {
        id: 5,
        title: '原標題',
        event_date: '2026-01-01',
        location: '台北',
        tags: ['t'],
        description_md: '',
      },
    })
    await flushPromises()

    setNativeValue(findInputByDataTest(wrapper, 'form-title'), '新標題')
    await wrapper.find('[data-test="save-event-button"]').trigger('click')
    await flushPromises()

    expect(update).toHaveBeenCalledWith(
      5,
      expect.objectContaining({ title: '新標題' }),
    )
    expect(wrapper.emitted('update:modelValue')?.at(-1)).toEqual([false])
  })

  it('enables the photos tab in edit mode', async () => {
    const wrapper = mountForm({
      event: { id: 5, title: 'x', event_date: '2026-01-01', tags: [] },
    })
    await flushPromises()
    expect(wrapper.find('.photos-manager-stub').exists()).toBe(true)
    expect(wrapper.find('[data-test="photos-locked"]').exists()).toBe(false)
  })

  it('locks the photos tab when creating', async () => {
    const wrapper = mountForm()
    await flushPromises()
    expect(wrapper.find('[data-test="photos-locked"]').exists()).toBe(true)
  })
})
