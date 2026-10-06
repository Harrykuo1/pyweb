<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { ElSelect, ElOption } from 'element-plus'
import { activityApi } from '../../api/activity'
const number = (value) =>
  new Intl.NumberFormat('zh-TW', { maximumFractionDigits: 2 }).format(
    value || 0,
  )
const props = defineProps({
  filters: { type: Object, required: true },
  users: { type: Array, default: () => [] },
  members: { type: Array, default: () => [] },
  metric: { type: String, default: 'messages' },
})
const selected = ref([])
const days = ref(7)
const smooth = ref(true)
const result = ref(null)
const loading = ref(false)
const error = ref('')
const hover = ref(null)
const colors = [
  '#8061cf',
  '#20a79a',
  '#e09347',
  '#d46698',
  '#598bc7',
  '#899e43',
]
let controller
let ticket = 0
let initialized = false
watch(
  () => [props.members, props.filters.user_ids],
  () => {
    if (initialized) return
    const candidates = props.filters.user_ids?.length
      ? props.filters.user_ids
      : props.members.slice(0, 3).map((m) => m.user_id)
    if (candidates.length) {
      selected.value = candidates.slice(0, 6)
      initialized = true
    }
  },
  { immediate: true },
)
const query = computed(() => ({
  end_date: props.filters.end_date,
  window_days: days.value,
  timezone: props.filters.timezone,
  hour_start: props.filters.hour_start,
  hour_end: props.filters.hour_end,
  weekdays: props.filters.weekdays,
  channel_ids: props.filters.channel_ids,
  user_ids: selected.value,
}))
async function load() {
  controller?.abort()
  const current = ++ticket
  error.value = ''
  hover.value = null
  if (!selected.value.length) {
    result.value = null
    loading.value = false
    return
  }
  controller = new AbortController()
  loading.value = true
  try {
    const response = await activityApi.memberTrends(
      query.value,
      controller.signal,
    )
    if (current === ticket) result.value = response
  } catch (err) {
    if (
      current === ticket &&
      err.name !== 'CanceledError' &&
      err.name !== 'AbortError'
    ) {
      result.value = null
      error.value = '個人趨勢載入失敗，請再試一次。'
    }
  } finally {
    if (current === ticket) loading.value = false
  }
}
watch(query, load, { deep: true, immediate: true })
onBeforeUnmount(() => {
  ++ticket
  controller?.abort()
})
const series = computed(() => result.value?.series || [])
const dates = computed(() => series.value[0]?.daily.map((p) => p.date) || [])
const valueKey = computed(() => `${props.metric}${smooth.value ? '_avg7' : ''}`)
const ceiling = computed(() =>
  Math.max(
    1,
    ...series.value.flatMap((s) => s.daily.map((p) => p[valueKey.value])),
  ),
)
const unit = computed(() =>
  props.metric === 'messages' ? '則／日' : '分鐘／日',
)
const x = (i) => 48 + (i * 900) / Math.max(1, dates.value.length - 1)
const y = (v) => 222 - (v / ceiling.value) * 180
const points = (s) =>
  s.daily.map((p, i) => `${x(i)},${y(p[valueKey.value])}`).join(' ')
const divider = computed(() =>
  x(Math.max(0, (result.value?.window_days || 7) - 0.5)),
)
const ticks = computed(() =>
  [
    ...new Set([0, Math.floor(dates.value.length / 2), dates.value.length - 1]),
  ].filter((i) => i >= 0),
)
function change(s) {
  const percent = s[`${props.metric}_change_percent`]
  if (percent === null)
    return s[`current_${props.metric}`] ? '前期無紀錄' : '尚無紀錄'
  if (percent === 0) return '持平'
  return `${percent > 0 ? '↑' : '↓'} ${Math.abs(percent)}%`
}
function direction(s) {
  const value = s[`${props.metric}_change_percent`]
  return value > 0 ? 'rising' : value < 0 ? 'falling' : ''
}
function inspect(event) {
  const rect = event.currentTarget.getBoundingClientRect()
  hover.value = Math.max(
    0,
    Math.min(
      dates.value.length - 1,
      Math.round(
        ((((event.clientX - rect.left) / rect.width) * 980 - 48) / 900) *
          (dates.value.length - 1),
      ),
    ),
  )
}
</script>
<template>
  <section class="member-trends" :aria-busy="loading">
    <div class="heading">
      <div>
        <span class="kicker">THE PEOPLE BEHIND THE PULSE</span>
        <h2>每個人的活躍節奏</h2>
        <p>把日常連成線，看見最近的變化。</p>
      </div>
      <div class="periods" aria-label="比較期間">
        <button
          v-for="n in [7, 14, 30]"
          :key="n"
          type="button"
          :aria-pressed="days === n"
          @click="days = n"
        >
          近 {{ n }} 天
        </button>
      </div>
    </div>
    <div class="controls">
      <el-select
        v-model="selected"
        multiple
        filterable
        :multiple-limit="6"
        collapse-tags
        :max-collapse-tags="3"
        collapse-tags-tooltip
        placeholder="選擇要比較的成員，最多 6 人"
        aria-label="比較成員"
      >
        <el-option
          v-for="user in users"
          :key="user.user_id"
          :value="user.user_id"
          :label="`${user.name} · ${user.user_id}`"
        />
      </el-select>
      <div class="modes">
        <button type="button" :aria-pressed="smooth" @click="smooth = true">
          7 日均線</button
        ><button type="button" :aria-pressed="!smooth" @click="smooth = false">
          每日紀錄
        </button>
      </div>
    </div>
    <p class="scope">
      以查詢結束日往前比較兩個完整期間，沿用頻道、時段與星期條件；此圖不受查詢開始日限制。{{
        result?.excluded_today ? '今天尚未結束，已排除。' : ''
      }}
    </p>
    <div v-if="loading" class="state" role="status">正在整理每個人的節奏…</div>
    <div v-else-if="error" class="state" role="alert">
      {{ error }} <button type="button" @click="load">重新載入</button>
    </div>
    <p v-else-if="!series.length" class="state">
      選擇成員，開始比較最近的活躍頻率。
    </p>
    <template v-else>
      <div class="period-labels">
        <span>前期 {{ result.previous_start }} — {{ result.previous_end }}</span
        ><strong
          >本期 {{ result.current_start }} — {{ result.current_end }}</strong
        >
      </div>
      <div class="chart-scroll">
        <svg
          viewBox="0 0 980 264"
          role="img"
          aria-label="各成員活躍頻率折線圖"
          @mousemove="inspect"
          @mouseleave="hover = null"
        >
          <rect
            :x="divider"
            y="28"
            :width="960 - divider"
            height="194"
            rx="8"
            fill="#f5f2fb"
          />
          <g v-for="fraction in [0, 0.5, 1]" :key="fraction">
            <line
              x1="48"
              x2="948"
              :y1="y(ceiling * fraction)"
              :y2="y(ceiling * fraction)"
              stroke="#eae7f0"
              stroke-dasharray="3 5"
            />
            <text x="40" :y="y(ceiling * fraction) + 4" text-anchor="end">
              {{ number(Math.round(ceiling * fraction * 10) / 10) }}
            </text>
          </g>
          <text x="48" y="16">
            {{ smooth ? '7 日平均' : '每日' }} · {{ unit }}
          </text>
          <line
            :x1="divider"
            :x2="divider"
            y1="28"
            y2="222"
            stroke="#bfb0df"
            stroke-dasharray="4 4"
          />
          <polyline
            v-for="(s, i) in series"
            :key="s.user_id"
            :points="points(s)"
            fill="none"
            :stroke="colors[i]"
            stroke-width="2.8"
            stroke-linejoin="round"
            stroke-linecap="round"
          />
          <text
            v-for="i in ticks"
            :key="i"
            :x="x(i)"
            y="247"
            :text-anchor="
              i === 0 ? 'start' : i === dates.length - 1 ? 'end' : 'middle'
            "
          >
            {{ dates[i] }}
          </text>
          <g
            v-for="(date, i) in dates"
            :key="date"
            tabindex="0"
            role="button"
            :aria-label="`查看 ${date}`"
            @focus="hover = i"
            @blur="hover = null"
            @click="hover = i"
          >
            <rect
              :x="x(i) - 7"
              y="28"
              width="14"
              height="194"
              fill="transparent"
            />
          </g>
          <g v-if="hover !== null" pointer-events="none">
            <line
              :x1="x(hover)"
              :x2="x(hover)"
              y1="28"
              y2="222"
              stroke="#90849f"
            />
            <circle
              v-for="(s, i) in series"
              :key="s.user_id"
              :cx="x(hover)"
              :cy="y(s.daily[hover][valueKey])"
              r="4"
              :fill="colors[i]"
              stroke="white"
              stroke-width="2"
            />
          </g>
        </svg>
      </div>
      <div class="readout" aria-live="polite">
        <template v-if="hover !== null"
          ><strong>{{ dates[hover] }}</strong
          ><span
            v-for="(s, i) in series"
            :key="s.user_id"
            :style="{ color: colors[i] }"
            >{{ s.name }} {{ number(s.daily[hover][valueKey]) }}
            {{ unit }}</span
          ></template
        ><span v-else>滑過折線、點選日期或用 Tab 查看每日數值</span>
      </div>
      <div class="member-cards">
        <article
          v-for="(s, i) in series"
          :key="s.user_id"
          :style="{ '--series-color': colors[i] }"
        >
          <div class="person">
            <i></i><strong :title="s.user_id">{{ s.name }}</strong
            ><span :class="direction(s)" class="change">{{ change(s) }}</span>
          </div>
          <div class="rate">
            {{ number(s[`current_${metric}_rate`]) }} <small>{{ unit }}</small>
          </div>
          <p>
            前期 {{ number(s[`previous_${metric}_rate`]) }} {{ unit }}
            <span
              >本期共 {{ number(s[`current_${metric}`]) }}
              {{ metric === 'messages' ? '則' : '分鐘' }}</span
            >
          </p>
        </article>
      </div>
      <p class="scope">
        升降以符合星期條件的每日平均比較（本期
        {{ result.eligible_current_days }} 天／前期
        {{ result.eligible_previous_days }} 天）。7 日均線包含畫面前 6
        天的資料。{{
          metric === 'voice_minutes'
            ? '語音為頻道內的估計參與時間，並非實際發言時長。'
            : '訊息筆數代表發送頻率，不含訊息內容。'
        }}
      </p>
    </template>
  </section>
</template>
<style scoped>
.member-trends {
  background: #fff;
  border: 1px solid #ebe7f1;
  border-radius: 20px;
  padding: 28px;
  margin-bottom: 24px;
  min-width: 0;
}
.heading,
.controls,
.period-labels,
.person {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}
.kicker {
  font-size: 10px;
  letter-spacing: 1.8px;
  color: #a395be;
  font-weight: 700;
}
h2 {
  margin: 8px 0;
  font-size: 21px;
  color: #38304c;
}
.heading p {
  color: #8f879d;
  font-size: 12px;
  margin: 0;
}
button {
  cursor: pointer;
  border: 0;
  background: transparent;
  color: #91899f;
  padding: 8px 12px;
  font: inherit;
  font-size: 12px;
  border-radius: 8px;
}
button[aria-pressed='true'] {
  color: #7753b9;
  background: white;
  box-shadow: 0 2px 6px #66518514;
  font-weight: 600;
}
.periods,
.modes {
  background: #f3f0f7;
  padding: 4px;
  border-radius: 11px;
  display: flex;
  flex-shrink: 0;
}
.controls {
  margin-top: 24px;
}
.controls :deep(.el-select) {
  max-width: 650px;
  flex: 1;
  min-width: 0;
}
.scope {
  font-size: 11px;
  color: #938a9e;
  line-height: 1.8;
  margin: 12px 0 0;
}
.period-labels {
  margin-top: 24px;
  font-size: 11px;
  color: #9b92a8;
}
.period-labels strong {
  color: #8765bb;
  font-weight: 500;
}
.chart-scroll {
  overflow-x: auto;
  margin-top: 16px;
}
svg {
  display: block;
  width: 100%;
  min-width: 540px;
}
svg text {
  fill: #a197ae;
  font-size: 11px;
}
.readout {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  min-height: 32px;
  color: #a197ad;
  font-size: 11px;
}
.member-cards {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-top: 16px;
}
article {
  background: #fcfbfe;
  border: 1px solid #eeeaf4;
  border-radius: 13px;
  padding: 16px;
  min-width: 0;
}
.person {
  gap: 7px;
  font-size: 12px;
}
.person i {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--series-color);
  flex-shrink: 0;
}
.person strong {
  color: #655975;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.change {
  color: #aaa1b6;
  font-size: 10px;
  white-space: nowrap;
}
.rising {
  color: #299d8e;
}
.falling {
  color: #b28276;
}
.rate {
  font-size: 26px;
  font-weight: 600;
  color: #51435f;
  margin-top: 14px;
  font-variant-numeric: tabular-nums;
}
.rate small {
  font-size: 10px;
  color: #a397af;
  font-weight: 400;
}
article p {
  font-size: 10px;
  color: #a397af;
  margin: 8px 0 0;
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 5px;
}
.state {
  text-align: center;
  padding: 50px 10px;
  color: #948a9f;
  font-size: 13px;
}
@media (max-width: 720px) {
  .member-trends {
    padding: 20px 16px;
  }
  .heading,
  .controls {
    align-items: stretch;
    flex-direction: column;
  }
  .periods,
  .modes {
    align-self: flex-start;
  }
  .controls :deep(.el-select) {
    flex: auto;
  }
  .member-cards {
    grid-template-columns: 1fr;
  }
  .period-labels {
    flex-direction: column;
    align-items: flex-start;
    gap: 6px;
  }
}
</style>
