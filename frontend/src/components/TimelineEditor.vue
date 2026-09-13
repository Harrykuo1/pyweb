<script setup>
import { computed, ref, watch } from 'vue'
import {
  ElButton,
  ElDatePicker,
  ElIcon,
  ElInput,
  ElRadioButton,
  ElRadioGroup,
} from 'element-plus'
import { Delete, InfoFilled, Plus } from '@element-plus/icons-vue'

// Structured timeline editor: a vertical list of rows where each row
// is { date: "YYYY-MM-DD", event } or { dayOffset: number, event }.
//
// Two ways to place an entry because people write these up months
// later: some remember the calendar date, some only remember "the
// test was a week after I applied". A relative entry stays relative —
// no date is derived for it, since that would put a guess on record.
//
// Which one is a property of the whole timeline, not of each row:
// somebody who has forgotten the dates has forgotten all of them. So
// the choice is made once, at the top, and every row carries the same
// kind. Offering both on every row meant a decision repeated per row,
// two boxes where only one could ever be used, and — worst — filling
// one silently wiped the other.
//
// The editor preserves entry order so the admin's caret never jumps
// mid-typing — the actual chronological sort happens in the parent
// dialog at submit time. The full ISO date is stored (not just M/D)
// so recruitment processes that span the year boundary record
// honestly without needing surrounding job context.
const props = defineProps({
  modelValue: {
    type: Array,
    default: () => [],
  },
  // The job's calendar context used to seed the picker's default
  // open position for the first row (e.g. editing a year-old job
  // shouldn't make every picker open at "today" — the admin would
  // have to click `<` 12+ times for each row). Optional: if absent,
  // the picker falls back to its own default (today).
  defaultDate: {
    type: Date,
    default: null,
  },
})

const emit = defineEmits(['update:modelValue'])

// Local row state carries a synthetic _id per row so v-for's :key
// stays stable across add/remove (Vue would otherwise reuse DOM by
// position and steal focus from a freshly-edited input). _id never
// leaves this component — emitToParent strips it before bubbling up.
let _idCounter = 0
function _newId() {
  _idCounter += 1
  return `row-${Date.now()}-${_idCounter}`
}

const rows = ref([])
// 'date' | 'offset'. Derived from the loaded rows rather than defaulting,
// so reopening a timeline lands on the way it was written.
const mode = ref('date')

function _modeFor(list) {
  const positioned = (list ?? []).filter(
    (e) => e.date != null || e.day_offset != null,
  )
  if (positioned.length === 0) return 'date'
  // Any relative row at all means the timeline was written relatively:
  // dated rows convert into offsets without inventing anything, while
  // the reverse cannot be done at all.
  return positioned.some((e) => e.day_offset != null) ? 'offset' : 'date'
}

function _hydrate(list) {
  return (list ?? []).map((entry) => ({
    _id: _newId(),
    date: entry.date ?? null,
    dayOffset: entry.day_offset ?? null,
    event: entry.event ?? '',
  }))
}

watch(
  () => props.modelValue,
  (next) => {
    // Skip re-hydration if the incoming list matches our current
    // emit shape — otherwise editing focus jumps as Vue rebuilds
    // rows on every keystroke. Hydrate only when the parent
    // genuinely replaces the list (resetForm on dialog open).
    if (_matchesCurrent(next)) return
    mode.value = _modeFor(next)
    rows.value = _hydrate(next)
    if (mode.value === 'offset') _seedOffsetsFromDates()
  },
  { immediate: true },
)

// Compares against what we would emit, not against the raw row. The row
// also holds the inactive column's draft, which never leaves here —
// comparing that would make every keystroke look like a foreign change
// and re-hydrate, discarding the draft this whole design exists to keep.
function _matchesCurrent(next) {
  if (!Array.isArray(next)) return false
  if (next.length !== rows.value.length) return false
  return next.every((entry, i) => {
    const r = rows.value[i]
    if (!r) return false
    return (
      (mode.value === 'date' ? r.date : null) === (entry.date ?? null) &&
      (mode.value === 'offset' ? r.dayOffset : null) ===
        (entry.day_offset ?? null) &&
      r.event === (entry.event ?? '')
    )
  })
}

// A row holds both drafts; the mode decides which one is real. Masking
// here rather than clearing as you switch is what makes switching safe:
// go and look at the other column, come back, nothing is gone. The saved
// entry still carries exactly one position, which is all the API allows.
function emitToParent() {
  emit(
    'update:modelValue',
    rows.value.map(({ date, dayOffset, event }) => ({
      date: mode.value === 'date' ? date : null,
      day_offset: mode.value === 'offset' ? dayOffset : null,
      event,
    })),
  )
}

function addRow() {
  rows.value.push({ _id: _newId(), date: null, dayOffset: null, event: '' })
  emitToParent()
}

function removeRow(index) {
  rows.value.splice(index, 1)
  emitToParent()
}

function patchRow(index, patch) {
  rows.value[index] = { ...rows.value[index], ...patch }
  emitToParent()
}

function setDate(index, value) {
  patchRow(index, { date: value || null })
}

function setDayOffset(index, value) {
  patchRow(index, { dayOffset: _parseOffset(value) })
}

// Arriving in relative mode with dates already entered, fill the blank
// offsets from them: an entry's distance from the earliest date is
// exactly the D+N the viewer has always shown beside it, so this
// invents nothing. Offsets already typed are left alone — they are the
// more recent statement of intent for this column.
function _seedOffsetsFromDates() {
  const earliest = rows.value
    .map((r) => r.date)
    .filter(Boolean)
    .sort()[0]
  if (!earliest) return
  const base = _parseISODate(earliest)
  rows.value = rows.value.map((r) => {
    if (r.dayOffset !== null || !r.date) return r
    const days = Math.round((_parseISODate(r.date) - base) / 86400000)
    return { ...r, dayOffset: days }
  })
}

// No confirmation, because nothing is destroyed: the other column's
// values stay in the row and come back when you switch back. Only what
// is saved follows the mode.
function setMode(next) {
  if (next === mode.value) return
  mode.value = next
  if (next === 'offset') _seedOffsetsFromDates()
  emitToParent()
}

// Accepts what people actually type into a "D+" box: 7, +7, -3, and
// the whole label (D+7 / d-3) pasted in from somewhere else.
function _parseOffset(raw) {
  if (raw === null || raw === undefined) return null
  const text = String(raw).trim()
  if (text === '') return null
  const match = /^[Dd]?\s*([+-]?\d{1,3})$/.exec(text)
  if (!match) return null
  return Number(match[1])
}

// When the admin clicks an empty row's date picker, anchor the
// calendar at the most contextually useful month: the previous
// row's date if any, otherwise the parent-supplied default
// (job_year / job_month for create + edit), otherwise null (lib
// falls back to today).
function defaultPickerDateFor(index) {
  for (let i = index - 1; i >= 0; i--) {
    const prev = rows.value[i].date
    if (prev) return _parseISODate(prev)
  }
  return props.defaultDate
}

function _parseISODate(iso) {
  const [y, m, d] = iso.split('-').map(Number)
  if (!y || !m || !d) return null
  return new Date(y, m - 1, d)
}

const accentForRow = computed(() => (index) => {
  // Gradient accent down the spine of the editor: violet for the
  // first row, emerald for the last, indigo for the middle ones —
  // matches the read-only TimelineDisplay so admins recognise the
  // shape they're editing.
  const total = rows.value.length
  if (index === 0) return 'first'
  if (index === total - 1) return 'last'
  return 'middle'
})
</script>

<template>
  <div class="timeline-editor" data-test="timeline-editor">
    <div class="timeline-mode">
      <el-radio-group
        :model-value="mode"
        size="small"
        data-test="timeline-mode"
        @change="setMode"
      >
        <el-radio-button value="date" data-test="timeline-mode-date">
          用日期
        </el-radio-button>
        <el-radio-button value="offset" data-test="timeline-mode-offset">
          用 D+ 天數
        </el-radio-button>
      </el-radio-group>

      <p class="timeline-helper">
        <el-icon :size="13"><InfoFilled /></el-icon>
        <span v-if="mode === 'date'">儲存時自動依日期排序</span>
        <span v-else>投履歷那天填 0，一週後填 7，之前的事填 -3</span>
      </p>
    </div>

    <ol v-if="rows.length > 0" class="timeline-rows">
      <li
        v-for="(entry, index) in rows"
        :key="entry._id"
        class="timeline-row"
        :class="`is-${accentForRow(index)}`"
        data-test="timeline-row"
      >
        <span class="row-accent" aria-hidden="true" />
        <div
          v-if="mode === 'date'"
          class="row-date"
          data-test="timeline-row-date"
        >
          <el-date-picker
            :model-value="entry.date"
            type="date"
            value-format="YYYY-MM-DD"
            format="YYYY/MM/DD"
            placeholder="YYYY/MM/DD"
            :default-value="defaultPickerDateFor(index)"
            class="row-date-picker"
            @update:model-value="(d) => setDate(index, d)"
          />
        </div>
        <div v-else class="row-offset" data-test="timeline-row-offset">
          <el-input
            :model-value="
              entry.dayOffset === null ? '' : String(entry.dayOffset)
            "
            :placeholder="index === 0 ? '0' : '7'"
            maxlength="5"
            aria-label="相對天數"
            @update:model-value="(v) => setDayOffset(index, v)"
          >
            <template #prefix>
              <span class="offset-prefix">D+</span>
            </template>
          </el-input>
        </div>
        <div class="row-event" data-test="timeline-row-event">
          <el-input
            :model-value="entry.event"
            maxlength="200"
            placeholder="事件描述（例：投遞履歷 / 面試邀請 / 拿到 offer）"
            @update:model-value="(v) => patchRow(index, { event: v })"
          />
        </div>
        <el-button
          type="danger"
          text
          :icon="Delete"
          size="small"
          class="row-remove"
          data-test="timeline-row-remove"
          aria-label="刪除這筆"
          @click="removeRow(index)"
        />
      </li>
    </ol>
    <p v-else class="timeline-empty">尚無時程紀錄，點下方「加一筆」開始。</p>

    <el-button
      type="primary"
      plain
      :icon="Plus"
      data-test="timeline-add"
      class="timeline-add-button"
      @click="addRow"
    >
      加一筆
    </el-button>
  </div>
</template>

<style scoped>
.timeline-editor {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
}

.timeline-mode {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

/* Sits beside the switch rather than in its own tinted banner: the hint
   is one short line, and a full-width band of colour above the rows was
   competing with the fields for attention. */
.timeline-helper {
  display: flex;
  align-items: center;
  gap: 5px;
  margin: 0;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.timeline-rows {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
}

/* ------- Row card ------- */
.timeline-row {
  position: relative;
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  padding: 6px 4px 6px 14px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.timeline-row:last-child {
  border-bottom: none;
}

/* Hover only lifts the row's own ground — no transform, so a list of
   rows never nudges its neighbours while the pointer travels down it. */
.timeline-row:hover {
  background: var(--el-fill-color-lighter);
}

/* A 2px tick rather than a full-height strip: it marks where the row
   starts and echoes the read-only display's colour story without
   bracketing the whole row like a card. */
.row-accent {
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 2px;
  height: 18px;
  border-radius: 1px;
  background: #818cf8;
}

.is-first .row-accent {
  background: #a855f7;
}

.is-last .row-accent {
  background: #10b981;
}

/* ------- Date picker slot ------- */
.row-date {
  flex: 0 0 168px;
}

.row-date :deep(.el-date-editor) {
  width: 100%;
}

/* ------- Relative-day slot: narrow, it only ever holds a small number ------- */
.row-offset {
  flex: 0 0 116px;
}

/* Inside the field, not a grey attached block: el-input's prepend paints
   a filled panel that reads as disabled next to a white input. */
.offset-prefix {
  font-weight: 600;
  color: #6366f1;
}

.row-offset :deep(.el-input__inner) {
  font-variant-numeric: tabular-nums;
}

/* ------- Event input slot ------- */
.row-event {
  flex: 1 1 auto;
  min-width: 0;
}

/* ------- Delete button (low-emphasis until hovered) ------- */
.row-remove {
  flex: 0 0 auto;
  opacity: 0.45;
  transition: opacity 160ms ease;
}

.timeline-row:hover .row-remove {
  opacity: 1;
}

.row-remove:focus-visible {
  opacity: 1;
}

/* ------- Empty + add button ------- */
.timeline-empty {
  margin: 0;
  padding: 18px;
  text-align: center;
  color: var(--el-text-color-secondary);
  background: var(--el-fill-color-lighter);
  border: 1px dashed var(--el-border-color);
  border-radius: 8px;
}

.timeline-add-button {
  align-self: stretch;
  border-style: dashed;
}

@media (max-width: 600px) {
  .timeline-row {
    flex-wrap: wrap;
    gap: 8px;
    padding: 10px 12px 10px 16px;
  }
  .row-event {
    flex: 1 1 100%;
    order: 99;
  }
}
</style>
