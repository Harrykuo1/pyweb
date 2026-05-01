<script setup>
import { computed, ref, watch } from 'vue'
import { ElButton, ElDatePicker, ElIcon, ElInput } from 'element-plus'
import { Delete, InfoFilled, Plus, Rank } from '@element-plus/icons-vue'
import draggable from 'vuedraggable'

// Structured timeline editor: a vertical list of rows where each row
// is { date: "YYYY-MM-DD" | null, event: string }.
//
// Storage / display order is the order the admin enters them. The
// admin can re-order rows by dragging the handle on the left of each
// row. The full ISO date is stored (not just M/D) so recruitment
// processes that span the year boundary record honestly without
// needing surrounding job context.
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

// Local row state carries a synthetic _id per row so vuedraggable
// has a stable list key during drag (the parent's clean payload
// has no IDs). _id never leaves this component — emitToParent
// strips it before bubbling up.
let _idCounter = 0
function _newId() {
  _idCounter += 1
  return `row-${Date.now()}-${_idCounter}`
}

const rows = ref([])

function _hydrate(list) {
  return (list ?? []).map((entry) => ({
    _id: _newId(),
    date: entry.date ?? null,
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
    rows.value = _hydrate(next)
  },
  { immediate: true },
)

function _matchesCurrent(next) {
  if (!Array.isArray(next)) return false
  if (next.length !== rows.value.length) return false
  return next.every((entry, i) => {
    const r = rows.value[i]
    return r && r.date === (entry.date ?? null) && r.event === (entry.event ?? '')
  })
}

function emitToParent() {
  emit(
    'update:modelValue',
    rows.value.map(({ date, event }) => ({ date, event })),
  )
}

function addRow() {
  rows.value.push({ _id: _newId(), date: null, event: '' })
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

function onDragEnd() {
  emitToParent()
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
    <p class="timeline-helper">
      <el-icon :size="13"><InfoFilled /></el-icon>
      點選或直接輸入日期，例：2025/03/15。可拖曳左側 ⠿ 圖示重新排序。
    </p>

    <draggable
      v-if="rows.length > 0"
      :list="rows"
      tag="ol"
      class="timeline-rows"
      handle=".timeline-row-handle"
      item-key="_id"
      :animation="180"
      ghost-class="timeline-row-ghost"
      drag-class="timeline-row-dragging"
      @end="onDragEnd"
    >
      <template #item="{ element: entry, index }">
        <li
          class="timeline-row"
          :class="`is-${accentForRow(index)}`"
          data-test="timeline-row"
        >
          <span class="row-accent" aria-hidden="true" />
          <button
            type="button"
            class="timeline-row-handle"
            data-test="timeline-row-handle"
            aria-label="拖曳排序"
            title="拖曳排序"
          >
            <el-icon :size="16"><Rank /></el-icon>
          </button>
          <span class="row-index">{{ index + 1 }}</span>
          <div class="row-date" data-test="timeline-row-date">
            <el-date-picker
              :model-value="entry.date"
              type="date"
              value-format="YYYY-MM-DD"
              format="YYYY/MM/DD"
              placeholder="YYYY/MM/DD"
              :default-value="defaultPickerDateFor(index)"
              class="row-date-picker"
              @update:model-value="(d) => patchRow(index, { date: d ?? null })"
            />
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
      </template>
    </draggable>
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

/* ------- Drag handle ------- */
.timeline-row-handle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  border-radius: 6px;
  color: #94a3b8;
  cursor: grab;
  transition: background-color 120ms ease, color 120ms ease;
}

.timeline-row-handle:hover {
  background: rgba(99, 102, 241, 0.14);
  color: #4f46e5;
}

.timeline-row-handle:active {
  cursor: grabbing;
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

/* ------- Drag states -------
   Using sortablejs's HTML5 drag mode (no forceFallback): the browser
   produces the drag image at the cursor while sortablejs reorders
   the DOM in place. The :list binding (instead of v-model) means
   sortablejs mutates the row array directly during drag, so Vue
   does not re-render mid-drag — that was the source of the earlier
   "row appears twice" residue. */
.timeline-row-ghost {
  opacity: 0.4;
  background: rgba(99, 102, 241, 0.12);
  border-style: dashed;
}

.timeline-row-dragging {
  background: rgba(255, 255, 255, 0.98);
  box-shadow: 0 16px 40px rgba(15, 23, 42, 0.24);
  border-color: rgba(99, 102, 241, 0.45);
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
