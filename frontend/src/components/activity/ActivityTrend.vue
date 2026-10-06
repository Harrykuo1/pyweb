<script setup>
import { computed, ref } from 'vue'
import { number } from './activityUtils'
const props = defineProps({
  daily: { type: Array, required: true },
  metric: { type: String, required: true },
  unit: { type: String, required: true },
})
const emit = defineEmits(['select'])
const hovered = ref(null)
const maximum = computed(() =>
  Math.max(1, ...props.daily.map((d) => d[props.metric])),
)
const x = (i) => 54 + (i * 880) / Math.max(props.daily.length - 1, 1)
const y = (value) => 204 - (value / maximum.value) * 166
const points = computed(() =>
  props.daily.map((d, i) => `${x(i)},${y(d[props.metric])}`).join(' '),
)
const area = computed(() =>
  props.daily.length
    ? `M54,204 L${props.daily.map((d, i) => `${x(i)},${y(d[props.metric])}`).join(' L')} L${x(props.daily.length - 1)},204 Z`
    : '',
)
const labels = computed(() =>
  [
    ...new Set([
      0,
      Math.floor((props.daily.length - 1) / 4),
      Math.floor((props.daily.length - 1) / 2),
      Math.floor(((props.daily.length - 1) * 3) / 4),
      props.daily.length - 1,
    ]),
  ].filter((i) => i >= 0),
)
const active = computed(() => props.daily[hovered.value] || null)
</script>
<template>
  <div class="trend-chart" :class="{ 'is-voice': metric === 'voice_minutes' }">
    <div class="trend-caption" aria-live="polite">
      <template v-if="active"
        ><strong>{{ active.date }}</strong
        ><span>{{ number(active[metric]) }} {{ unit }}</span
        ><span class="chart-hint">點選查看當日</span></template
      >
      <template v-else
        ><span>移到曲線上查看每日數據</span
        ><span class="chart-hint">點選日期可深入查詢</span></template
      >
    </div>
    <svg
      viewBox="0 0 960 240"
      role="img"
      :aria-label="`每日${unit}趨勢`"
      @mouseleave="hovered = null"
    >
      <defs>
        <linearGradient id="activity-trend-fill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="currentColor" stop-opacity=".23" />
          <stop offset="100%" stop-color="currentColor" stop-opacity=".01" />
        </linearGradient>
      </defs>
      <g v-for="tick in [0, 1, 2, 3]" :key="tick">
        <line
          x1="54"
          x2="934"
          :y1="y((maximum * tick) / 3)"
          :y2="y((maximum * tick) / 3)"
          stroke="#e9edf4"
          stroke-dasharray="4 5"
        />
        <text x="43" :y="y((maximum * tick) / 3) + 4" text-anchor="end">
          {{ number(Math.round((maximum * tick) / 3)) }}
        </text>
      </g>
      <path :d="area" fill="url(#activity-trend-fill)" />
      <polyline
        :points="points"
        fill="none"
        stroke="currentColor"
        stroke-width="2.5"
        stroke-linecap="round"
        stroke-linejoin="round"
      />
      <circle
        v-if="daily.length === 1"
        :cx="x(0)"
        :cy="y(daily[0][metric])"
        r="4"
        fill="currentColor"
      />
      <g v-if="active">
        <line
          :x1="x(hovered)"
          :x2="x(hovered)"
          y1="30"
          y2="204"
          stroke="currentColor"
          stroke-opacity=".3"
        />
        <circle
          :cx="x(hovered)"
          :cy="y(active[metric])"
          r="4"
          fill="currentColor"
          stroke="white"
          stroke-width="2"
        />
      </g>
      <text v-for="i in labels" :key="i" :x="x(i)" y="230" text-anchor="middle">
        {{ daily[i].date.slice(5).replace('-', '/') }}
      </text>
      <rect
        v-for="(day, i) in daily"
        :key="day.date"
        :x="x(i) - 440 / Math.max(daily.length, 1)"
        y="24"
        :width="880 / Math.max(daily.length, 1)"
        height="184"
        fill="transparent"
        tabindex="0"
        role="button"
        :aria-label="`${day.date}：${number(day[metric])} ${unit}，查看當日`"
        @mouseenter="hovered = i"
        @focus="hovered = i"
        @click="emit('select', day.date)"
        @keydown.enter="emit('select', day.date)"
      >
        <title>{{ day.date }} · {{ number(day[metric]) }} {{ unit }}</title>
      </rect>
    </svg>
  </div>
</template>
<style scoped>
.trend-chart {
  color: var(--brand-primary);
}
.trend-chart.is-voice {
  color: #0d9488;
}
.trend-caption {
  min-height: 24px;
  display: flex;
  gap: 14px;
  font-size: 12px;
  color: var(--ink-500);
  align-items: center;
}
.trend-caption strong {
  color: var(--ink-900);
}
.chart-hint {
  margin-left: auto;
  font-size: 11px;
}
.trend-chart svg {
  width: 100%;
  display: block;
  overflow: visible;
}
.trend-chart text {
  fill: #8190a5;
  font-size: 11px;
  font-family: var(--font-sans);
}
.trend-chart rect {
  cursor: crosshair;
}
.trend-chart rect:focus {
  outline: 1px solid currentColor;
}
@media (max-width: 640px) {
  .chart-hint {
    display: none;
  }
  .trend-chart svg {
    min-height: 150px;
  }
}
</style>
