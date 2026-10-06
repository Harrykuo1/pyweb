<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import {
  calendarCells,
  intensity,
  longestStreak,
  number,
} from './activityUtils'
const props = defineProps({
  daily: { type: Array, required: true },
  metric: { type: String, required: true },
  unit: { type: String, required: true },
})
const emit = defineEmits(['select'])
const cells = computed(() => calendarCells(props.daily))
const maximum = computed(() =>
  Math.max(0, ...props.daily.map((d) => d[props.metric])),
)
const activeDays = computed(
  () => props.daily.filter((d) => d[props.metric] > 0).length,
)
const months = computed(() => {
  const labels = []
  let previous = ''
  for (let i = 0; i < cells.value.length; i += 7) {
    const first = cells.value.slice(i, i + 7).find(Boolean)
    const month = first?.date.slice(0, 7)
    if (first && month !== previous) {
      labels.push({
        label: `${Number(first.date.slice(5, 7))}月`,
        week: i / 7 + 1,
      })
      previous = month
    }
  }
  return labels
})
const scroll = ref(null)
async function showRecent() {
  await nextTick()
  if (scroll.value) scroll.value.scrollLeft = scroll.value.scrollWidth
}
onMounted(showRecent)
watch(() => props.daily, showRecent)
</script>
<template>
  <div class="contribution" :class="{ 'is-voice': metric === 'voice_minutes' }">
    <div
      ref="scroll"
      class="calendar-scroll"
      tabindex="0"
      aria-label="每日熱圖，可左右捲動"
    >
      <div class="calendar-inner" :style="{ '--weeks': cells.length / 7 }">
        <div class="month-labels">
          <span
            v-for="(month, i) in months"
            :key="i"
            :style="{ gridColumn: month.week }"
            >{{ month.label }}</span
          >
        </div>
        <div class="calendar-body">
          <div class="day-labels">
            <span>一</span><span></span><span>三</span><span></span
            ><span>五</span><span></span><span>日</span>
          </div>
          <div class="calendar-grid" data-test="contribution-grid">
            <template v-for="(day, i) in cells" :key="day?.date || i">
              <button
                v-if="day"
                type="button"
                class="day-cell"
                :data-level="intensity(day[metric], maximum)"
                :title="`${day.date} · ${number(day[metric])} ${unit}`"
                :aria-label="`${day.date}：${number(day[metric])} ${unit}，查看當日`"
                @click="emit('select', day.date)"
              ></button>
              <span v-else class="day-cell blank" aria-hidden="true"></span>
            </template>
          </div>
        </div>
      </div>
    </div>
    <div class="calendar-footer">
      <span
        ><strong>{{ number(activeDays) }}</strong> 個活躍日
        <span class="separator">／</span> 最長連續
        <strong>{{ longestStreak(daily, metric) }}</strong> 天</span
      >
      <div class="legend">
        <span>少</span
        ><i
          v-for="level in [0, 1, 2, 3, 4]"
          :key="level"
          :data-level="level"
        ></i
        ><span>多</span>
      </div>
    </div>
  </div>
</template>
<style scoped>
.contribution {
  --level-1: #ddd6fe;
  --level-2: #a5a0f5;
  --level-3: #7c72e9;
  --level-4: #5145cd;
}
.is-voice {
  --level-1: #ccfbef;
  --level-2: #79d9c7;
  --level-3: #24b6a0;
  --level-4: #087f73;
}
.calendar-scroll {
  overflow-x: auto;
  padding: 5px 2px 12px;
}
.calendar-inner {
  min-width: calc(var(--weeks) * 18px + 28px);
}
.month-labels {
  margin-left: 28px;
  display: grid;
  grid-template-columns: repeat(var(--weeks), 18px);
  height: 26px;
  color: var(--ink-500);
  font-size: 10px;
  white-space: nowrap;
}
.calendar-body {
  display: flex;
  gap: 12px;
}
.day-labels {
  display: grid;
  grid-template-rows: repeat(7, 14px);
  gap: 4px;
  width: 16px;
  font-size: 10px;
  color: var(--ink-500);
  align-items: center;
}
.calendar-grid {
  display: grid;
  grid-auto-flow: column;
  grid-template-rows: repeat(7, 14px);
  grid-auto-columns: 14px;
  gap: 4px;
}
.day-cell,
.legend i {
  display: block;
  width: 14px;
  height: 14px;
  border: 1px solid rgba(15, 23, 42, 0.035);
  border-radius: 3px;
  background: #edf0f5;
  padding: 0;
}
.day-cell {
  cursor: pointer;
  transition: transform 0.15s;
}
.day-cell:hover {
  transform: scale(1.25);
  outline: 1px solid var(--brand-primary);
}
.day-cell.blank {
  visibility: hidden;
}
.calendar-footer {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  font-size: 12px;
  color: var(--ink-500);
  border-top: 1px solid #f0f2f7;
  padding-top: 16px;
}
.calendar-footer strong {
  color: var(--ink-700);
  font-variant-numeric: tabular-nums;
}
.separator {
  margin: 0 8px;
  color: var(--ink-300);
}
.legend {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 10px;
}
.legend span {
  margin: 0 4px;
}
.contribution [data-level='1'] {
  background: var(--level-1);
}
.contribution [data-level='2'] {
  background: var(--level-2);
}
.contribution [data-level='3'] {
  background: var(--level-3);
}
.contribution [data-level='4'] {
  background: var(--level-4);
}
@media (max-width: 640px) {
  .calendar-footer {
    flex-direction: column;
  }
  .legend {
    justify-content: flex-end;
  }
}
</style>
