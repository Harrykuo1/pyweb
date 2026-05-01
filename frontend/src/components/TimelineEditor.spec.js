import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import TimelineEditor from './TimelineEditor.vue'

function mountEditor(modelValue = []) {
  // v-model needs a manual update handler in test mounts because the
  // component is the source of truth for its own list operations.
  let value = modelValue.slice()
  const wrapper = mount(TimelineEditor, {
    props: {
      modelValue: value,
      'onUpdate:modelValue': (next) => {
        value = next
        wrapper.setProps({ modelValue: next })
      },
    },
  })
  return { wrapper, getValue: () => value }
}

describe('TimelineEditor', () => {
  it('shows the empty hint when the list is empty', () => {
    const { wrapper } = mountEditor([])
    expect(wrapper.text()).toContain('尚無時程紀錄')
    expect(wrapper.findAll('[data-test="timeline-row"]')).toHaveLength(0)
  })

  it('renders one row per entry in modelValue', () => {
    const { wrapper } = mountEditor([
      { date: '2025-02-23', event: '投遞履歷' },
      { date: '2025-04-17', event: '拿到 offer' },
    ])
    expect(wrapper.findAll('[data-test="timeline-row"]')).toHaveLength(2)
    // el-input renders the value into the underlying <input> attribute,
    // not into text content; assert via the input element's value.
    const eventInputs = wrapper.findAll('[data-test="timeline-row-event"] input')
    expect(eventInputs[0].element.value).toBe('投遞履歷')
    expect(eventInputs[1].element.value).toBe('拿到 offer')
  })

  it('appends a blank row when "加一筆" is clicked', async () => {
    const { wrapper, getValue } = mountEditor([])
    await wrapper.find('[data-test="timeline-add"]').trigger('click')

    expect(getValue()).toHaveLength(1)
    expect(getValue()[0]).toEqual({ date: null, event: '' })
    expect(wrapper.findAll('[data-test="timeline-row"]')).toHaveLength(1)
  })

  it('removes a row when its delete button is clicked, leaving the others in place', async () => {
    const { wrapper, getValue } = mountEditor([
      { date: '2025-02-23', event: 'a' },
      { date: '2025-03-01', event: 'b' },
      { date: '2025-04-05', event: 'c' },
    ])
    const deleteButtons = wrapper.findAll('[data-test="timeline-row-remove"]')
    await deleteButtons[1].trigger('click')

    expect(getValue()).toEqual([
      { date: '2025-02-23', event: 'a' },
      { date: '2025-04-05', event: 'c' },
    ])
  })

  it('renders a drag handle on every row', () => {
    const { wrapper } = mountEditor([
      { date: '2025-02-23', event: 'a' },
      { date: '2025-03-01', event: 'b' },
    ])
    const handles = wrapper.findAll('[data-test="timeline-row-handle"]')
    expect(handles).toHaveLength(2)
  })

  it('does not leak the internal _id key into emitted modelValue', async () => {
    // The drag library needs a stable key per row, so the editor
    // attaches a synthetic _id internally. That field must never
    // surface in the model the parent (and ultimately the backend)
    // sees — otherwise the backend's strict TimelineEvent schema
    // would reject the extra property.
    const { wrapper, getValue } = mountEditor([])
    await wrapper.find('[data-test="timeline-add"]').trigger('click')
    await wrapper.find('[data-test="timeline-add"]').trigger('click')

    const emitted = getValue()
    expect(emitted).toHaveLength(2)
    for (const entry of emitted) {
      expect(Object.keys(entry).sort()).toEqual(['date', 'event'])
    }
  })

  it('preserves input order regardless of date ordering (no auto-sort)', async () => {
    // Admin enters events out of date order on purpose — the editor
    // must not silently re-sort them. Cross-year (Dec → Jan) is now
    // a fully-supported case since each row carries its own ISO
    // year, so the editor must not shuffle these rows around.
    const { wrapper, getValue } = mountEditor([
      { date: '2025-12-15', event: 'first (Dec 2025)' },
      { date: '2026-01-08', event: 'second (Jan 2026)' },
      { date: '2025-11-30', event: 'third (back to Nov 2025)' },
    ])

    expect(wrapper.findAll('[data-test="timeline-row"]')).toHaveLength(3)
    const eventInputs = wrapper.findAll('[data-test="timeline-row-event"] input')
    expect(eventInputs[0].element.value).toBe('first (Dec 2025)')
    expect(eventInputs[1].element.value).toBe('second (Jan 2026)')
    expect(eventInputs[2].element.value).toBe('third (back to Nov 2025)')
    expect(getValue().map((e) => e.event)).toEqual([
      'first (Dec 2025)',
      'second (Jan 2026)',
      'third (back to Nov 2025)',
    ])
  })
})
