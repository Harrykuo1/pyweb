import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { ElMessageBox } from 'element-plus'

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

afterEach(() => {
  vi.restoreAllMocks()
})

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
    const eventInputs = wrapper.findAll(
      '[data-test="timeline-row-event"] input',
    )
    expect(eventInputs[0].element.value).toBe('投遞履歷')
    expect(eventInputs[1].element.value).toBe('拿到 offer')
  })

  it('appends a blank row when "加一筆" is clicked', async () => {
    const { wrapper, getValue } = mountEditor([])
    await wrapper.find('[data-test="timeline-add"]').trigger('click')

    expect(getValue()).toHaveLength(1)
    expect(getValue()[0]).toEqual({ date: null, day_offset: null, event: '' })
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
      { date: '2025-02-23', day_offset: null, event: 'a' },
      { date: '2025-04-05', day_offset: null, event: 'c' },
    ])
  })

  it('does not leak the internal _id key into emitted modelValue', async () => {
    // Each row carries a synthetic _id internally so v-for's :key stays
    // stable across add / remove (otherwise Vue reuses DOM by position
    // and steals focus from a freshly-edited input). That field must
    // never surface in the model the parent (and ultimately the
    // backend) sees — the backend's strict TimelineEvent schema would
    // reject the extra property.
    const { wrapper, getValue } = mountEditor([])
    await wrapper.find('[data-test="timeline-add"]').trigger('click')
    await wrapper.find('[data-test="timeline-add"]').trigger('click')

    const emitted = getValue()
    expect(emitted).toHaveLength(2)
    for (const entry of emitted) {
      expect(Object.keys(entry).sort()).toEqual(['date', 'day_offset', 'event'])
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
    const eventInputs = wrapper.findAll(
      '[data-test="timeline-row-event"] input',
    )
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

describe('TimelineEditor — one mode for the whole timeline', () => {
  function offsetInput(wrapper, index = 0) {
    return wrapper
      .findAll('[data-test="timeline-row-offset"]')
      [index].find('input')
  }

  async function switchTo(wrapper, mode) {
    await wrapper
      .findComponent({ name: 'ElRadioGroup' })
      .vm.$emit('change', mode)
    await flushPromises()
  }

  it('opens in date mode for a timeline written with dates', () => {
    const { wrapper } = mountEditor([{ date: '2025-03-01', event: '投遞' }])
    expect(wrapper.findAll('[data-test="timeline-row-date"]')).toHaveLength(1)
    expect(wrapper.findAll('[data-test="timeline-row-offset"]')).toHaveLength(0)
  })

  it('opens in relative mode for a timeline written with offsets', () => {
    // Reopening must land on the way it was written, not on a default
    // that hides what is there.
    const { wrapper } = mountEditor([{ day_offset: 7, event: '線上測驗' }])
    expect(wrapper.findAll('[data-test="timeline-row-offset"]')).toHaveLength(1)
    expect(wrapper.findAll('[data-test="timeline-row-date"]')).toHaveLength(0)
    expect(offsetInput(wrapper).element.value).toBe('7')
  })

  it('shows one position input per row, never both', () => {
    // The pair was the whole problem: two boxes where only one could be
    // used, and filling one silently wiped the other.
    const { wrapper } = mountEditor([
      { date: '2025-03-01', event: 'a' },
      { date: '2025-03-08', event: 'b' },
    ])
    expect(wrapper.findAll('[data-test="timeline-row-date"]')).toHaveLength(2)
    expect(wrapper.findAll('[data-test="timeline-row-offset"]')).toHaveLength(0)
  })

  it('converts dates into offsets when switching to relative mode', async () => {
    // Lossless in this direction: D+N is what the viewer already showed
    // beside each date, so nothing is invented.
    const { wrapper, getValue } = mountEditor([
      { date: '2025-03-01', event: '投遞' },
      { date: '2025-03-08', event: '測驗' },
      { date: '2025-03-22', event: 'offer' },
    ])
    await switchTo(wrapper, 'offset')

    expect(getValue().map((e) => e.day_offset)).toEqual([0, 7, 21])
    expect(getValue().every((e) => e.date === null)).toBe(true)
  })

  it('measures the conversion from the earliest date, not from row 0', async () => {
    const { wrapper, getValue } = mountEditor([
      { date: '2025-03-08', event: 'later' },
      { date: '2025-03-01', event: 'earlier' },
    ])
    await switchTo(wrapper, 'offset')

    expect(getValue().map((e) => e.day_offset)).toEqual([7, 0])
  })

  it('asks before switching back to dates, because nothing can be converted', async () => {
    // A calendar date would have to be invented for every row, so the
    // offsets are simply lost — say so rather than wiping them quietly.
    const confirm = vi
      .spyOn(ElMessageBox, 'confirm')
      .mockResolvedValue('confirm')
    const { wrapper, getValue } = mountEditor([{ day_offset: 7, event: 'x' }])
    await switchTo(wrapper, 'date')

    expect(confirm).toHaveBeenCalled()
    expect(getValue()[0].day_offset).toBeNull()
  })

  it('keeps the offsets when that switch is cancelled', async () => {
    vi.spyOn(ElMessageBox, 'confirm').mockRejectedValue(new Error('cancel'))
    const { wrapper, getValue } = mountEditor([{ day_offset: 7, event: 'x' }])
    await switchTo(wrapper, 'date')

    expect(getValue()[0].day_offset).toBe(7)
    expect(wrapper.findAll('[data-test="timeline-row-offset"]')).toHaveLength(1)
  })

  it('does not ask when there is nothing to lose', async () => {
    const confirm = vi.spyOn(ElMessageBox, 'confirm')
    const { wrapper } = mountEditor([{ day_offset: null, event: '' }])
    await switchTo(wrapper, 'offset')
    await switchTo(wrapper, 'date')

    expect(confirm).not.toHaveBeenCalled()
  })

  it('accepts the forms people actually type', async () => {
    // A bare number is the common case; the rest gets pasted in from a
    // message thread.
    for (const [typed, expected] of [
      ['7', 7],
      ['+7', 7],
      ['-3', -3],
      ['D+7', 7],
      ['d-3', -3],
    ]) {
      const { wrapper, getValue } = mountEditor([{ day_offset: 0, event: 'x' }])
      await offsetInput(wrapper).setValue(typed)
      expect(getValue()[0].day_offset).toBe(expected)
    }
  })

  it('treats an emptied offset field as no offset rather than zero', async () => {
    // Clearing the box must not silently pin the entry to D+0.
    const { wrapper, getValue } = mountEditor([{ day_offset: 7, event: 'x' }])
    await offsetInput(wrapper).setValue('')

    expect(getValue()[0].day_offset).toBeNull()
  })

  it('prompts for 0 on the first row so the anchor is obvious', async () => {
    // Nothing else tells someone a relative timeline should start at D+0.
    const { wrapper } = mountEditor([
      { day_offset: 0, event: 'a' },
      { day_offset: 7, event: 'b' },
    ])
    await offsetInput(wrapper, 0).setValue('')
    await offsetInput(wrapper, 1).setValue('')

    expect(offsetInput(wrapper, 0).attributes('placeholder')).toBe('0')
    expect(offsetInput(wrapper, 1).attributes('placeholder')).toBe('7')
  })
})
