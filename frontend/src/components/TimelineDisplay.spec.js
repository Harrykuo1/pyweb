import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import TimelineDisplay from './TimelineDisplay.vue'

function mountDisplay(events) {
  return mount(TimelineDisplay, { props: { events } })
}

describe('TimelineDisplay', () => {
  it('shows the empty hint when events is empty', () => {
    const wrapper = mountDisplay([])
    expect(wrapper.text()).toContain('尚無時程紀錄')
    expect(wrapper.findAll('[data-test="timeline-display-item"]')).toHaveLength(
      0,
    )
  })

  it('renders one item per event in the given order', () => {
    const wrapper = mountDisplay([
      { date: '2025-02-23', event: '投遞履歷' },
      { date: '2025-03-06', event: '面試邀請' },
      { date: '2025-04-17', event: '拿到 offer' },
    ])
    const items = wrapper.findAll('[data-test="timeline-display-item"]')
    expect(items).toHaveLength(3)

    const events = wrapper.findAll('[data-test="timeline-display-event"]')
    expect(events[0].text()).toBe('投遞履歷')
    expect(events[1].text()).toBe('面試邀請')
    expect(events[2].text()).toBe('拿到 offer')
  })

  it('formats every date as YYYY/M/D without zero-padding', () => {
    const wrapper = mountDisplay([
      { date: '2025-02-03', event: 'a' },
      { date: '2025-12-25', event: 'b' },
    ])
    const dates = wrapper.findAll('[data-test="timeline-display-date"]')
    expect(dates[0].text()).toBe('2025/2/3')
    expect(dates[1].text()).toBe('2025/12/25')
  })

  it('keeps the YYYY/M/D format across year boundaries', () => {
    // Cross-year recruitment: first entry in Dec 2025, last in Feb
    // 2026. Year shows on every row so the reader never has to scan
    // back to disambiguate.
    const wrapper = mountDisplay([
      { date: '2025-12-15', event: '投遞履歷' },
      { date: '2026-01-08', event: '面試' },
      { date: '2026-02-03', event: '拿到 offer' },
    ])
    const dates = wrapper.findAll('[data-test="timeline-display-date"]')
    expect(dates[0].text()).toBe('2025/12/15')
    expect(dates[1].text()).toBe('2026/1/8')
    expect(dates[2].text()).toBe('2026/2/3')
  })

  it('computes D+0 for the first event and D+N for the rest', () => {
    const wrapper = mountDisplay([
      { date: '2025-02-23', event: 'a' },
      { date: '2025-03-06', event: 'b' },
      { date: '2025-04-17', event: 'c' },
    ])
    const offsets = wrapper.findAll('[data-test="timeline-display-offset"]')
    expect(offsets[0].text()).toBe('D+0')
    expect(offsets[1].text()).toBe('D+11')
    expect(offsets[2].text()).toBe('D+53')
  })

  it('uses the date-embedded year so leap years compute correctly', () => {
    // 2024 is a leap year (29 days in February). Feb 1 -> Mar 1 = 29 days.
    const leap = mountDisplay([
      { date: '2024-02-01', event: 'start' },
      { date: '2024-03-01', event: 'one month later' },
    ])
    expect(
      leap.findAll('[data-test="timeline-display-offset"]')[1].text(),
    ).toBe('D+29')

    // 2025 is not a leap year — same M/D inputs yield D+28.
    const nonLeap = mountDisplay([
      { date: '2025-02-01', event: 'start' },
      { date: '2025-03-01', event: 'one month later' },
    ])
    expect(
      nonLeap.findAll('[data-test="timeline-display-offset"]')[1].text(),
    ).toBe('D+28')
  })

  it('handles cross-year D+N correctly (Dec → Jan)', () => {
    // Dec 15, 2025 → Jan 8, 2026 = 24 days
    // Dec 15, 2025 → Feb 3, 2026 = 50 days
    const wrapper = mountDisplay([
      { date: '2025-12-15', event: 'a' },
      { date: '2026-01-08', event: 'b' },
      { date: '2026-02-03', event: 'c' },
    ])
    const offsets = wrapper.findAll('[data-test="timeline-display-offset"]')
    expect(offsets[0].text()).toBe('D+0')
    expect(offsets[1].text()).toBe('D+24')
    expect(offsets[2].text()).toBe('D+50')
  })

  it('measures D+N from the earliest date, not from whichever row is first', () => {
    // The anchor cannot be "row 0": a timeline may now open with a
    // relative entry, which has no date at all, and reading the offset
    // off that row left every D+N unanswerable. Saved timelines are
    // sorted, so for them the two rules agree; this pins the rule that
    // survives unsorted input.
    const wrapper = mountDisplay([
      { date: '2025-03-06', event: 'later' },
      { date: '2025-02-23', event: 'earlier' },
    ])
    const offsets = wrapper.findAll('[data-test="timeline-display-offset"]')
    expect(offsets[0].text()).toBe('D+11')
    expect(offsets[1].text()).toBe('D+0')
  })
})

describe('TimelineDisplay — relative entries', () => {
  it('shows a relative entry as its own D+N with no date', () => {
    // The offset is what the writer recorded. Deriving a date for it
    // would put a guess on the page beside things actually on record.
    const wrapper = mountDisplay([
      { date: '2025-03-01', event: '投遞履歷' },
      { day_offset: 7, event: '線上測驗' },
    ])
    const dates = wrapper.findAll('[data-test="timeline-display-date"]')
    const offsets = wrapper.findAll('[data-test="timeline-display-offset"]')

    expect(dates).toHaveLength(1)
    expect(dates[0].text()).toBe('2025/3/1')
    expect(offsets.map((o) => o.text())).toEqual(['D+0', 'D+7'])
  })

  it('renders a timeline that opens with a relative entry', () => {
    // This used to render nothing at all: the anchor was read off row 0,
    // which has no date here, and the whole list was discarded.
    const wrapper = mountDisplay([
      { day_offset: 0, event: '投遞履歷' },
      { day_offset: 7, event: '線上測驗' },
      { date: '2025-03-22', event: '拿到 offer' },
    ])
    expect(wrapper.findAll('[data-test="timeline-display-item"]')).toHaveLength(
      3,
    )
    expect(wrapper.text()).toContain('投遞履歷')
  })

  it('renders a timeline with no dates at all', () => {
    const wrapper = mountDisplay([
      { day_offset: -3, event: '看到職缺' },
      { day_offset: 0, event: '投遞履歷' },
    ])
    const offsets = wrapper.findAll('[data-test="timeline-display-offset"]')
    expect(offsets.map((o) => o.text())).toEqual(['D-3', 'D+0'])
    expect(wrapper.findAll('[data-test="timeline-display-date"]')).toHaveLength(
      0,
    )
  })

  it('keeps a relative entry at the offset it was given', () => {
    // Not recomputed against the dated rows: D+7 means seven days into
    // the process as the writer counted it, whatever the dates say.
    const wrapper = mountDisplay([
      { date: '2025-03-01', event: '投遞履歷' },
      { day_offset: 7, event: '線上測驗' },
      { date: '2025-03-22', event: '拿到 offer' },
    ])
    const offsets = wrapper.findAll('[data-test="timeline-display-offset"]')
    expect(offsets.map((o) => o.text())).toEqual(['D+0', 'D+7', 'D+21'])
  })
})
