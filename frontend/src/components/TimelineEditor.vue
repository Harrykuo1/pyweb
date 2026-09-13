<script setup>
import { computed, ref, watch } from 'vue'
import {
  ElButton,
  ElDatePicker,
  ElIcon,
  ElInput,
  ElMessageBox,
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
    if (mode.value === 'offset') _convertDatesToOffsets()
  },
  { immediate: true },
)

function _matchesCurrent(next) {
  if (!Array.isArray(next)) return false
  if (next.length !== rows.value.length) return false
  return next.every((entry, i) => {
    const r = rows.value[i]
    return (
      r &&
      r.date === (entry.date ?? null) &&
      r.dayOffset === (entry.day_offset ?? null) &&
      r.event === (entry.event ?? '')
    )
  })
}

function emitToParent() {
  emit(
    'update:modelValue',
    rows.value.map(({ date, dayOffset, event }) => ({
      date,
      day_offset: dayOffset,
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

// A row only ever shows the input for the active mode, so each setter
// clears the other side rather than leaving a row claiming both — which
// the API refuses anyway.
function setDate(index, value) {
  patchRow(index, { date: value || null, dayOffset: null })
}

function setDayOffset(index, value) {
  patchRow(index, { dayOffset: _parseOffset(value), date: null })
}

// Dates carry their offsets already — the viewer has always shown D+N
// next to them — so this direction loses the calendar but invents
// nothing. Measured from the earliest date, which is the D+0 a reader
// sees.
function _convertDatesToOffsets() {
  const earliest = rows.value
    .map((r) => r.date)
    .filter(Boolean)
    .sort()[0]
  const base = earliest ? _parseISODate(earliest) : null
  rows.value = rows.value.map((r) => {
    if (r.dayOffset !== null || !r.date || !base) {
      return { ...r, date: null }
    }
    const days = Math.round((_parseISODate(r.date) - base) / 86400000)
    return { ...r, date: null, dayOffset: days }
  })
}

const hasRelativeContent = computed(() =>
  rows.value.some((r) => r.dayOffset !== null),
)

async function setMode(next) {
  if (next === mode.value) return
  // Going back to dates cannot convert: a calendar date would have to be
  // invented for every row. Say so before throwing the numbers away.
  if (next === 'date' && hasRelativeContent.value) {
    try {
      await ElMessageBox.confirm(
        '改用日期後，已填的 D+ 天數會被清空，需要重新填寫日期。',
        '改用日期？',
        { confirmButtonText: '清空並改用日期', cancelButtonText: '取消' },
      )
    } catch {
      return
    }
    rows.value = rows.value.map((r) => ({ ...r, dayOffset: null }))
  } else if (next === 'offset') {
    _convertDatesToOffsets()
  }
  mode.value = next
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
    </div>

    <p class="timeline-helper">
      <el-icon :size="13"><InfoFilled /></el-icon>
      <span v-if="mode === 'date'">
        點選或直接輸入日期，例：2025/03/15。儲存時自動依日期排序。
      </span>
      <span v-else>
        只記得隔幾天就用這個：投履歷那天填 0，一週後的線上測驗填 7。
        投履歷前發生的事填負數，例如 -3。
      </span>
    </p>

    <ol v-if="rows.length > 0" class="timeline-rows">
      <li
        v-for="(entry, index) in rows"
        :key="entry._id"
        class="timeline-row"
        :class="`is-${accentForRow(index)}`"
        data-test="timeline-row"
      >
        <span class="row-accent" aria-hidden="true" />
        <span class="row-index">{{ index + 1 }}</span>
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
            <template #prepend>D+</template>
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
}

.timeline-helper {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 0;
  padding: 8px 12px;
  font-size: 12px;
  color: #4f46e5;
  background: rgba(99, 102, 241, 0.07);
  border-radius: 8px;
}

.timeline-rows {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* ------- Row card ------- */
.timeline-row {
  position: relative;
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  padding: 10px 14px 10px 18px;
  border-radius: 12px;
  background: linear-gradient(
    135deg,
    rgba(255, 255, 255, 0.92),
    rgba(248, 250, 252, 0.78)
  );
  border: 1px solid rgba(99, 102, 241, 0.14);
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
  transition:
    transform 200ms cubic-bezier(0.16, 1, 0.3, 1),
    box-shadow 200ms cubic-bezier(0.16, 1, 0.3, 1),
    border-color 200ms ease;
  overflow: hidden;
}

.timeline-row:hover {
  transform: translateY(-1px);
  box-shadow:
    0 1px 2px rgba(15, 23, 42, 0.04),
    0 6px 18px rgba(99, 102, 241, 0.12);
  border-color: rgba(99, 102, 241, 0.28);
}

/* Left accent strip — colour story matches the read-only display. */
.row-accent {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  background: linear-gradient(180deg, #6366f1, #818cf8);
}

.is-first .row-accent {
  background: linear-gradient(180deg, #a855f7, #7c3aed);
}

.is-last .row-accent {
  background: linear-gradient(180deg, #10b981, #059669);
}

/* ------- Row index chip ------- */
.row-index {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  width: 26px;
  height: 26px;
  border-radius: 50%;
  font-size: 12px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  background: rgba(99, 102, 241, 0.12);
  color: #4338ca;
}

.is-first .row-index {
  background: rgba(168, 85, 247, 0.16);
  color: #7e22ce;
}

.is-last .row-index {
  background: rgba(16, 185, 129, 0.16);
  color: #047857;
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
  flex: 0 0 120px;
}

.row-offset :deep(.el-input-group__prepend) {
  padding: 0 10px;
  font-weight: 600;
  color: #4f46e5;
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
