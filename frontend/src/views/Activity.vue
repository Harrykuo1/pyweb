<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElIcon, ElOption, ElSelect } from 'element-plus'
import {
  ChatDotRound,
  Microphone,
  User,
  Calendar,
  Refresh,
  ArrowRight,
  Search,
  DataAnalysis,
  Filter,
} from '@element-plus/icons-vue'
import { activityApi } from '../api/activity'
import ActivityTrend from '../components/activity/ActivityTrend.vue'
import ContributionCalendar from '../components/activity/ContributionCalendar.vue'
import {
  defaultFilters,
  filterError,
  hourLabel,
  intensity,
  localToday,
  number,
  parseFilters,
  shiftDate,
} from '../components/activity/activityUtils'

const route = useRoute()
const router = useRouter()
const filters = reactive(parseFilters(route.query))
const data = ref(null)
const options = ref({ configured: true, users: [], channels: [] })
const loading = ref(true)
const error = ref('')
const optionsError = ref(false)
const metric = ref('messages')
const rankSearch = ref('')
const rankPage = ref(1)
const advanced = ref(false)
const weekdays = ['一', '二', '三', '四', '五', '六', '日']
const zones = [
  'Asia/Taipei',
  'UTC',
  'Asia/Tokyo',
  'America/New_York',
  'Europe/London',
]
let controller
let optionsController
let requestNumber = 0
let disposed = false
const unit = computed(() =>
  metric.value === 'messages' ? '則訊息' : '分鐘語音',
)
const summary = computed(() => data.value?.summary || {})
const daily = computed(() => data.value?.daily || [])
const dirty = computed(
  () =>
    data.value &&
    JSON.stringify(filters) !== JSON.stringify(data.value.filters),
)
const dateRange = computed(() =>
  data.value
    ? `${data.value.filters.start_date.replaceAll('-', '.')} — ${data.value.filters.end_date.replaceAll('-', '.')}`
    : '選擇日期，探索社群的日常',
)
const lastReceived = computed(() =>
  options.value.last_received_at
    ? new Intl.DateTimeFormat('zh-TW', {
        timeZone: data.value?.filters.timezone || 'Asia/Taipei',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
      }).format(new Date(options.value.last_received_at))
    : null,
)
const hourMax = computed(() =>
  Math.max(1, ...(data.value?.hourly || []).map((h) => h[metric.value])),
)
const rhythmMax = computed(() =>
  Math.max(1, ...(data.value?.rhythm || []).map((h) => h[metric.value])),
)
const peakHour = computed(
  () =>
    [...(data.value?.hourly || [])].sort(
      (a, b) => b[metric.value] - a[metric.value],
    )[0],
)
const peakDay = computed(
  () => [...daily.value].sort((a, b) => b[metric.value] - a[metric.value])[0],
)
const members = computed(() =>
  [...(data.value?.members || [])]
    .filter((m) =>
      `${m.name} ${m.user_id}`
        .toLowerCase()
        .includes(rankSearch.value.toLowerCase()),
    )
    .sort(
      (a, b) =>
        b[metric.value] - a[metric.value] || a.user_id.localeCompare(b.user_id),
    ),
)
const pages = computed(() => Math.max(1, Math.ceil(members.value.length / 10)))
const ranked = computed(() =>
  members.value.slice((rankPage.value - 1) * 10, rankPage.value * 10),
)
const rankMax = computed(() =>
  Math.max(1, members.value[0]?.[metric.value] || 0),
)
const channels = computed(() =>
  [...(data.value?.channels || [])]
    .filter((c) => c[metric.value] > 0)
    .sort((a, b) => b[metric.value] - a[metric.value])
    .slice(0, 6),
)
const channelMax = computed(() =>
  Math.max(1, channels.value[0]?.[metric.value] || 0),
)
const hasActivity = computed(
  () => summary.value.messages > 0 || summary.value.voice_minutes > 0,
)
const metricCards = computed(() => [
  {
    label: '文字訊息',
    value: number(summary.value.messages),
    unit: '則',
    icon: ChatDotRound,
    tone: 'indigo',
    detail: `${number(daily.value.length ? summary.value.messages / daily.value.length : 0)} 則／日`,
  },
  {
    label: '語音參與',
    value: number((summary.value.voice_minutes || 0) / 60),
    unit: '小時',
    icon: Microphone,
    tone: 'teal',
    detail: `${number(summary.value.voice_minutes)} 個人分鐘 · 依掃描估計`,
  },
  {
    label: '活躍成員',
    value: number(summary.value.active_members),
    unit: '位',
    icon: User,
    tone: 'violet',
    detail: '有傳送訊息或參與語音的成員',
  },
  {
    label: '活躍天數',
    value: number(summary.value.active_days),
    unit: '天',
    icon: Calendar,
    tone: 'amber',
    detail: `選取範圍共 ${daily.value.length} 天`,
  },
])

async function loadOptions() {
  optionsController?.abort()
  const current = new AbortController()
  optionsController = current
  try {
    const result = await activityApi.options(current.signal)
    if (!disposed && !current.signal.aborted) {
      options.value = result
      optionsError.value = false
    }
  } catch (err) {
    if (!disposed && !current.signal.aborted && err.code !== 'ERR_CANCELED')
      optionsError.value = true
  }
}
async function load(query) {
  const next = parseFilters(query)
  Object.assign(filters, next)
  controller?.abort()
  const ticket = ++requestNumber
  error.value = filterError(next)
  if (error.value) {
    loading.value = false
    data.value = null
    return
  }
  const current = new AbortController()
  controller = current
  loading.value = true
  error.value = ''
  try {
    const result = await activityApi.analytics(next, current.signal)
    if (!disposed && ticket === requestNumber) {
      data.value = result
      rankPage.value = 1
    }
  } catch (err) {
    if (!disposed && ticket === requestNumber && err.code !== 'ERR_CANCELED') {
      error.value =
        typeof err.response?.data?.detail === 'string'
          ? err.response.data.detail
          : '暫時無法取得活躍度資料，請稍後重試。'
      data.value = null
    }
  } finally {
    if (!disposed && ticket === requestNumber) loading.value = false
  }
}
async function apply() {
  error.value = filterError(filters)
  if (error.value) return
  const query = Object.fromEntries(
    Object.entries(filters)
      .filter(([, value]) => !Array.isArray(value) || value.length)
      .map(([key, value]) => [
        key,
        Array.isArray(value) ? value.map(String) : String(value),
      ]),
  )
  if (JSON.stringify(parseFilters(route.query)) === JSON.stringify(filters))
    await load(query)
  else await router.replace({ path: '/activity', query })
}
function preset(days, evening = false) {
  const end = localToday(filters.timezone)
  Object.assign(filters, {
    start_date: shiftDate(end, -(days - 1)),
    end_date: end,
    hour_start: evening ? 18 : 0,
    hour_end: 24,
  })
  apply()
}
function reset() {
  Object.assign(filters, defaultFilters())
  rankSearch.value = ''
  apply()
}
function selectDay(date) {
  if (loading.value) return
  Object.assign(filters, { start_date: date, end_date: date })
  apply()
}
function selectChannel(id) {
  filters.channel_ids = [id]
  advanced.value = true
  apply()
}
function selectMember(id) {
  filters.user_ids = [id]
  advanced.value = true
  apply()
}
function selectHour(hour, weekday = null) {
  filters.hour_start = hour
  filters.hour_end = hour + 1
  if (weekday !== null) filters.weekdays = [weekday]
  advanced.value = true
  apply()
}
function toggleWeekday(day) {
  filters.weekdays = filters.weekdays.includes(day)
    ? filters.weekdays.filter((d) => d !== day)
    : [...filters.weekdays, day].sort()
}
function refresh() {
  loadOptions()
  load(route.query)
}
watch(() => route.query, load, { immediate: true })
watch([metric, rankSearch], () => {
  rankPage.value = 1
})
onMounted(loadOptions)
onBeforeUnmount(() => {
  disposed = true
  controller?.abort()
  optionsController?.abort()
})
</script>

<template>
  <div
    class="activity-page"
    :class="{ 'metric-voice': metric === 'voice_minutes' }"
    :aria-busy="loading"
  >
    <header class="activity-hero">
      <div class="hero-orbit orbit-one" aria-hidden="true"></div>
      <div class="hero-orbit orbit-two" aria-hidden="true"></div>
      <div class="hero-copy">
        <div class="eyebrow">
          <span class="live-dot"></span> COMMUNITY PULSE
        </div>
        <h1>活躍度<span>每一份參與，都在這裡。</span></h1>
        <p>從一句對話到一段陪伴，看見社群的日常與連結。</p>
      </div>
      <div class="hero-meta">
        <span class="hero-meta-label">資料收錄至</span
        ><strong>{{ lastReceived || '尚無收錄紀錄' }}</strong
        ><button
          type="button"
          class="hero-refresh"
          :disabled="loading"
          @click="refresh"
        >
          <el-icon :class="{ spinning: loading }"><Refresh /></el-icon>更新資料
        </button>
      </div>
    </header>

    <section class="filter-panel" aria-label="活躍度查詢條件">
      <div class="filter-top">
        <div class="filter-title">
          <el-icon><Filter /></el-icon><strong>探索範圍</strong
          ><span>最多 366 天</span>
        </div>
        <div class="presets">
          <button
            v-for="days in [7, 30, 90, 365]"
            :key="days"
            type="button"
            :disabled="loading"
            :class="{
              selected:
                filters.start_date === shiftDate(filters.end_date, -(days - 1)),
            }"
            @click="preset(days)"
          >
            {{ days === 365 ? '近一年' : `近 ${days} 天` }}</button
          ><button type="button" :disabled="loading" @click="preset(5, true)">
            近五天・晚間
          </button>
        </div>
      </div>
      <form @submit.prevent="apply">
        <div class="filter-main">
          <label class="field date-field"
            ><span>開始日期</span
            ><input
              v-model="filters.start_date"
              type="date"
              required
              aria-label="開始日期" /></label
          ><span class="date-separator" aria-hidden="true">—</span
          ><label class="field date-field"
            ><span>結束日期</span
            ><input
              v-model="filters.end_date"
              type="date"
              required
              aria-label="結束日期" /></label
          ><label class="field timezone-field"
            ><span>統計時區</span
            ><select v-model="filters.timezone" aria-label="統計時區">
              <option v-for="zone in zones" :key="zone" :value="zone">
                {{ zone === 'Asia/Taipei' ? '台北 · UTC+8' : zone }}
              </option>
            </select></label
          >
          <div class="filter-actions">
            <button
              type="button"
              class="quiet-button"
              @click="advanced = !advanced"
              :aria-expanded="advanced"
            >
              {{ advanced ? '收起條件' : '進階條件' }}</button
            ><button
              type="button"
              class="quiet-button"
              :disabled="loading"
              @click="reset"
            >
              重設</button
            ><button type="submit" class="primary-button" :disabled="loading">
              <el-icon><Search /></el-icon>{{ loading ? '查詢中' : '套用查詢' }}
            </button>
          </div>
        </div>
        <div
          v-if="advanced"
          class="advanced-filters"
          data-test="advanced-filters"
        >
          <div class="field">
            <span>成員 <small>可搜尋姓名或 Discord ID</small></span
            ><el-select
              v-model="filters.user_ids"
              multiple
              filterable
              collapse-tags
              collapse-tags-tooltip
              placeholder="全部成員"
              aria-label="篩選成員"
              ><el-option
                v-for="person in options.users"
                :key="person.user_id"
                :label="`${person.name} · ${person.user_id}`"
                :value="person.user_id"
            /></el-select>
          </div>
          <div class="field">
            <span>頻道 <small>以 Discord 頻道 ID 辨識</small></span
            ><el-select
              v-model="filters.channel_ids"
              multiple
              filterable
              collapse-tags
              collapse-tags-tooltip
              placeholder="全部頻道"
              aria-label="篩選頻道"
              ><el-option
                v-for="id in options.channels"
                :key="id"
                :label="`# ${id}`"
                :value="id"
            /></el-select>
          </div>
          <div class="field">
            <span>每日時段 <small>起始含、結束不含</small></span>
            <div class="hour-inputs">
              <select
                v-model.number="filters.hour_start"
                aria-label="每日開始時間"
              >
                <option v-for="hour in 24" :key="hour" :value="hour - 1">
                  {{ hourLabel(hour - 1) }}
                </option></select
              ><span>至</span
              ><select
                v-model.number="filters.hour_end"
                aria-label="每日結束時間"
              >
                <option v-for="hour in 24" :key="hour" :value="hour">
                  {{ hourLabel(hour) }}
                </option>
              </select>
            </div>
          </div>
          <div class="field">
            <span>星期 <small>未選擇代表每天</small></span>
            <div class="weekday-buttons">
              <button
                v-for="(day, i) in weekdays"
                :key="day"
                type="button"
                :class="{ selected: filters.weekdays.includes(i) }"
                :aria-pressed="filters.weekdays.includes(i)"
                :aria-label="`星期${day}`"
                @click="toggleWeekday(i)"
              >
                {{ day }}
              </button>
            </div>
          </div>
          <p v-if="filters.hour_start > filters.hour_end" class="filter-note">
            跨午夜時段會計入每個所選日期的凌晨與深夜，例如 22:00–02:00 代表當日
            00–02 與 22–24 點。
          </p>
        </div>
        <div
          v-if="
            filters.user_ids.length ||
            filters.channel_ids.length ||
            filters.hour_start !== 0 ||
            filters.hour_end !== 24 ||
            filters.weekdays.length ||
            dirty
          "
          class="filter-tags"
        >
          <span v-if="filters.user_ids.length"
            >{{ filters.user_ids.length }} 位成員</span
          ><span v-if="filters.channel_ids.length"
            >{{ filters.channel_ids.length }} 個頻道</span
          ><span v-if="filters.hour_start !== 0 || filters.hour_end !== 24"
            >每日 {{ hourLabel(filters.hour_start) }}–{{
              hourLabel(filters.hour_end)
            }}</span
          ><span v-if="filters.weekdays.length"
            >週{{ filters.weekdays.map((d) => weekdays[d]).join('、') }}</span
          ><em v-if="dirty">條件已變更，請套用查詢</em>
        </div>
      </form>
      <p v-if="optionsError" class="options-error">
        成員與頻道選項載入失敗。<button type="button" @click="loadOptions">
          重新載入
        </button>
      </p>
    </section>

    <div v-if="error" class="state-panel error-panel" role="alert">
      <strong>這次查詢沒有完成</strong>
      <p>{{ error }}</p>
      <button type="button" class="primary-button" @click="apply">
        重新查詢
      </button>
    </div>
    <div
      v-else-if="loading && !data"
      class="loading-grid"
      role="status"
      aria-label="載入活躍度資料"
    >
      <div v-for="i in 4" :key="i" class="skeleton-card"></div>
      <div class="skeleton-chart"></div>
      <span>正在整理社群的每一份參與…</span>
    </div>
    <template v-else-if="data">
      <div class="results-header">
        <span
          >{{ dateRange }} <small>· {{ data.filters.timezone }}</small></span
        >
        <div class="metric-switch" role="group" aria-label="圖表統計指標">
          <button
            type="button"
            :class="{ active: metric === 'messages' }"
            :aria-pressed="metric === 'messages'"
            @click="metric = 'messages'"
          >
            <el-icon><ChatDotRound /></el-icon>文字訊息</button
          ><button
            type="button"
            :class="{ active: metric === 'voice_minutes' }"
            :aria-pressed="metric === 'voice_minutes'"
            @click="metric = 'voice_minutes'"
          >
            <el-icon><Microphone /></el-icon>語音參與
          </button>
        </div>
      </div>
      <div class="metrics-grid" :class="{ refreshing: loading }">
        <article
          v-for="card in metricCards"
          :key="card.label"
          class="metric-card"
          :class="card.tone"
        >
          <div class="metric-card-top">
            <span>{{ card.label }}</span
            ><span class="metric-icon"
              ><el-icon><component :is="card.icon" /></el-icon
            ></span>
          </div>
          <div class="metric-number">
            {{ card.value }}<small>{{ card.unit }}</small>
          </div>
          <p>{{ card.detail }}</p>
        </article>
      </div>
      <div v-if="!hasActivity" class="empty-notice" data-test="empty-activity">
        <el-icon><DataAnalysis /></el-icon>
        <div>
          <strong>{{
            options.configured
              ? '這個範圍還沒有活動紀錄'
              : '尚未設定 Discord 群組'
          }}</strong>
          <p>
            {{
              options.configured
                ? '試著放寬日期、成員或時段條件；零筆紀錄也會如實呈現在圖表中。'
                : '請管理員至設定頁指定群組，並讓 Bot 開始回傳資料。'
            }}
          </p>
        </div>
      </div>

      <section class="panel contribution-panel">
        <div class="panel-heading">
          <div>
            <span class="section-kicker">THE EVERYDAY</span>
            <h2>每日貢獻熱圖</h2>
            <p>
              每一格是一天，深淺代表{{
                metric === 'messages' ? '訊息數量' : '語音參與分鐘'
              }}。點選探索當日。
            </p>
          </div>
          <span class="metric-badge">{{ unit }}</span>
        </div>
        <ContributionCalendar
          :daily="daily"
          :metric="metric"
          :unit="unit"
          @select="selectDay"
        />
      </section>

      <section class="panel trend-panel">
        <div class="panel-heading">
          <div>
            <span class="section-kicker">IN MOTION</span>
            <h2>參與趨勢</h2>
          </div>
          <div class="peak-label" v-if="peakDay?.[metric] > 0">
            最高的一天
            <strong>{{ peakDay.date.slice(5).replace('-', '/') }}</strong
            ><span>{{ number(peakDay[metric]) }} {{ unit }}</span>
          </div>
        </div>
        <ActivityTrend
          :daily="daily"
          :metric="metric"
          :unit="unit"
          @select="selectDay"
        />
      </section>

      <div class="analysis-grid">
        <section class="panel hourly-panel">
          <div class="panel-heading">
            <div>
              <span class="section-kicker">DAILY RHYTHM</span>
              <h2>什麼時候最熱鬧？</h2>
              <p>依所選時區，累計每個小時的參與量。</p>
            </div>
          </div>
          <div class="hour-bars">
            <button
              v-for="hour in data.hourly"
              :key="hour.hour"
              type="button"
              class="hour-bar"
              :title="`${hourLabel(hour.hour)} · ${number(hour[metric])} ${unit}`"
              :aria-label="`${hourLabel(hour.hour)}：${number(hour[metric])} ${unit}，篩選此時段`"
              @click="selectHour(hour.hour)"
            >
              <span class="bar-track"
                ><i
                  :style="{
                    height: `${hour[metric] ? Math.max(3, (hour[metric] / hourMax) * 100) : 0}%`,
                  }"
                ></i></span
              ><span class="hour-label">{{
                hour.hour % 3 === 0 ? String(hour.hour).padStart(2, '0') : ''
              }}</span>
            </button>
          </div>
          <div class="panel-footnote">
            高峰時段
            <strong>{{
              peakHour?.[metric] > 0
                ? `${hourLabel(peakHour.hour)}–${hourLabel(peakHour.hour + 1)}`
                : '尚無紀錄'
            }}</strong
            ><span>點選長條可套用時段</span>
          </div>
        </section>
        <section class="panel rhythm-panel">
          <div class="panel-heading">
            <div>
              <span class="section-kicker">WEEKLY PATTERN</span>
              <h2>一週的節奏</h2>
              <p>星期 × 小時，找到大家相聚的時間。</p>
            </div>
          </div>
          <div class="rhythm-scroll">
            <div class="rhythm-labels">
              <span></span
              ><span v-for="hour in 24" :key="hour">{{
                (hour - 1) % 6 === 0 ? hour - 1 : ''
              }}</span>
            </div>
            <div
              v-for="(day, weekday) in weekdays"
              :key="day"
              class="rhythm-row"
            >
              <span class="rhythm-day">{{ day }}</span
              ><button
                v-for="hour in 24"
                :key="hour"
                type="button"
                :data-level="
                  intensity(
                    data.rhythm[weekday * 24 + hour - 1]?.[metric],
                    rhythmMax,
                  )
                "
                :title="`週${day} ${hourLabel(hour - 1)} · ${number(data.rhythm[weekday * 24 + hour - 1]?.[metric])} ${unit}`"
                :aria-label="`篩選星期${day} ${hourLabel(hour - 1)}`"
                @click="selectHour(hour - 1, weekday)"
              ></button>
            </div>
          </div>
          <div class="panel-footnote">
            <span>點選方格可同時套用星期與時段</span>
            <div class="small-legend">
              少
              <i
                v-for="level in [0, 1, 2, 3, 4]"
                :key="level"
                :data-level="level"
              ></i>
              多
            </div>
          </div>
        </section>
      </div>

      <div class="bottom-grid">
        <section class="panel leaderboard">
          <div class="panel-heading">
            <div>
              <span class="section-kicker">PEOPLE BEHIND THE NUMBERS</span>
              <h2>
                成員活躍排行
                <span class="count-badge">{{ data.members.length }}</span>
              </h2>
            </div>
            <label class="rank-search"
              ><el-icon><Search /></el-icon
              ><input
                v-model="rankSearch"
                placeholder="搜尋成員"
                aria-label="搜尋排行榜成員"
            /></label>
          </div>
          <div class="table-scroll">
            <table>
              <thead>
                <tr>
                  <th class="rank-col">排名</th>
                  <th>成員</th>
                  <th
                    :aria-sort="metric === 'messages' ? 'descending' : 'none'"
                  >
                    <button type="button" @click="metric = 'messages'">
                      訊息 {{ metric === 'messages' ? '↓' : '' }}
                    </button>
                  </th>
                  <th
                    :aria-sort="
                      metric === 'voice_minutes' ? 'descending' : 'none'
                    "
                  >
                    <button type="button" @click="metric = 'voice_minutes'">
                      語音分鐘 {{ metric === 'voice_minutes' ? '↓' : '' }}
                    </button>
                  </th>
                  <th>活躍日</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(person, i) in ranked" :key="person.user_id">
                  <td
                    class="rank-number"
                    :class="{ 'top-three': rankPage === 1 && i < 3 }"
                  >
                    {{ String((rankPage - 1) * 10 + i + 1).padStart(2, '0') }}
                  </td>
                  <td>
                    <button
                      type="button"
                      class="person-button"
                      :title="`篩選 ${person.name} · ${person.user_id}`"
                      @click="selectMember(person.user_id)"
                    >
                      <span
                        class="person-avatar"
                        :style="{ '--avatar-hue': 235 + (i % 4) * 15 }"
                        >{{
                          person.name.startsWith('Discord ·')
                            ? '#'
                            : person.name.slice(0, 1)
                        }}</span
                      ><span class="person-details"
                        ><strong>{{ person.name }}</strong
                        ><span class="person-progress"
                          ><i
                            :style="{
                              width: `${(person[metric] / rankMax) * 100}%`,
                            }"
                          ></i></span
                      ></span>
                    </button>
                  </td>
                  <td :class="{ 'selected-number': metric === 'messages' }">
                    {{ number(person.messages) }}
                  </td>
                  <td
                    :class="{ 'selected-number': metric === 'voice_minutes' }"
                  >
                    {{ number(person.voice_minutes) }}
                  </td>
                  <td>{{ person.active_days }}</td>
                </tr>
                <tr v-if="!ranked.length">
                  <td colspan="5" class="empty-ranking">
                    {{
                      rankSearch ? '找不到符合的成員' : '這個範圍尚無成員紀錄'
                    }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="ranking-footer">
            <span
              >依{{ metric === 'messages' ? '訊息數' : '語音分鐘' }}排序 ·
              點選成員深入查看</span
            >
            <div>
              <button
                type="button"
                :disabled="rankPage <= 1"
                aria-label="排行榜上一頁"
                @click="rankPage--"
              >
                ←</button
              ><span>{{ rankPage }} / {{ pages }}</span
              ><button
                type="button"
                :disabled="rankPage >= pages"
                aria-label="排行榜下一頁"
                @click="rankPage++"
              >
                →
              </button>
            </div>
          </div>
        </section>
        <aside class="sidebar-panels">
          <section class="panel channel-panel">
            <div class="panel-heading">
              <div>
                <span class="section-kicker">WHERE WE CONNECT</span>
                <h2>熱門頻道</h2>
              </div>
              <span class="metric-badge">TOP 6</span>
            </div>
            <button
              v-for="(channel, i) in channels"
              :key="channel.channel_id"
              class="channel-row"
              type="button"
              :title="`篩選頻道 ${channel.channel_id}`"
              @click="selectChannel(channel.channel_id)"
            >
              <span class="channel-line"
                ><span
                  ><em>{{ i + 1 }}</em> # {{ channel.channel_id }}</span
                ><strong>{{ number(channel[metric]) }}</strong></span
              ><span class="channel-track"
                ><i
                  :style="{ width: `${(channel[metric] / channelMax) * 100}%` }"
                ></i
              ></span>
            </button>
            <p v-if="!channels.length" class="muted">尚無{{ unit }}紀錄</p>
            <p class="channel-note">頻道以 Discord ID 顯示，點選可篩選。</p>
          </section>
          <section class="conversation-card">
            <span class="section-kicker">MORE THAN A NUMBER</span>
            <h2>對話裡的小細節</h2>
            <div>
              <span>回覆訊息</span
              ><strong>{{ number(summary.replies) }} <small>則</small></strong>
            </div>
            <div>
              <span>附件分享</span
              ><strong
                >{{ number(summary.attachments) }} <small>個</small></strong
              >
            </div>
            <div>
              <span>平均訊息長度</span
              ><strong
                >{{
                  number(
                    summary.messages
                      ? summary.text_characters / summary.messages
                      : 0,
                  )
                }}
                <small>字元</small></strong
              >
            </div>
          </section>
        </aside>
      </div>
      <footer class="activity-footer">
        <el-icon><DataAnalysis /></el-icon>
        <p>
          訊息依實際傳送時間統計；每筆語音掃描計為 1
          個人分鐘，代表在頻道內的估計參與時間，並非實際發言時長。未綁定網站帳號的成員以
          Discord ID 顯示。
        </p>
        <button type="button" @click="router.push('/members')">
          認識社群成員<el-icon><ArrowRight /></el-icon>
        </button>
      </footer>
    </template>
  </div>
</template>

<style scoped>
.activity-page {
  display: flex;
  flex-direction: column;
  gap: 22px;
  --chart-color: #7064df;
  --chart-soft: #e6e2fb;
  --level-1: #e5dffc;
  --level-2: #b6a9f0;
  --level-3: #8a76df;
  --level-4: #5947b9;
}
.activity-page.metric-voice {
  --chart-color: #0d9488;
  --chart-soft: #d5f3ed;
  --level-1: #d5f3ed;
  --level-2: #83d9c7;
  --level-3: #36b7a0;
  --level-4: #0f8275;
}
.activity-page button,
.activity-page input,
.activity-page select {
  font: inherit;
}
.activity-page button {
  cursor: pointer;
}
.activity-page button:disabled {
  cursor: default;
  opacity: 0.5;
}
.activity-hero {
  position: relative;
  isolation: isolate;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 28px;
  padding: 34px 38px;
  background: linear-gradient(118deg, #211e4f, #363070 68%, #4e4590);
  border-radius: 20px;
  color: #fff;
}
.hero-orbit {
  position: absolute;
  z-index: -1;
  width: 450px;
  height: 450px;
  border: 1px solid #ffffff12;
  border-radius: 50%;
  right: 70px;
  top: -280px;
  box-shadow:
    0 0 0 35px #ffffff04,
    0 0 0 70px #ffffff03,
    0 0 0 105px #ffffff02;
}
.orbit-two {
  width: 250px;
  height: 250px;
  right: -130px;
  top: 35px;
  border-color: #a5b4fc28;
}
.eyebrow {
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 2px;
  color: #c8c6ed;
  display: flex;
  align-items: center;
  gap: 8px;
}
.live-dot {
  width: 6px;
  height: 6px;
  background: #78debd;
  border-radius: 50%;
  box-shadow: 0 0 0 4px #78debd12;
}
.activity-hero h1 {
  font-size: 30px;
  letter-spacing: -0.7px;
  line-height: 1.5;
  color: #fff;
  margin: 12px 0 7px;
}
.activity-hero h1 span {
  font-size: 15px;
  font-weight: 400;
  color: #dedaf2;
  letter-spacing: 0.2px;
  margin-left: 18px;
}
.hero-copy p {
  margin: 0;
  font-size: 12px;
  color: #c1beda;
}
.hero-meta {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 7px;
  white-space: nowrap;
}
.hero-meta-label {
  font-size: 10px;
  color: #c1beda;
}
.hero-meta strong {
  font-size: 16px;
  font-weight: 500;
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.5px;
}
.hero-refresh {
  display: flex;
  gap: 6px;
  align-items: center;
  border: 1px solid #ffffff22;
  background: #ffffff09;
  color: #eeeaff;
  padding: 6px 11px;
  border-radius: 7px;
  font-size: 11px !important;
  margin-top: 3px;
}
.hero-refresh:hover {
  background: #ffffff18;
}
.filter-panel,
.panel,
.metric-card {
  background: white;
  border: 1px solid #e5e9f0;
  border-radius: 15px;
  box-shadow: 0 2px 6px #0f172a02;
}
.filter-panel {
  padding: 20px 24px;
}
.filter-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}
.filter-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  white-space: nowrap;
}
.filter-title > .el-icon {
  color: #7c75b0;
}
.filter-title > span {
  font-size: 10px;
  color: #98a0b0;
  margin-left: 4px;
}
.presets {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}
.presets button,
.weekday-buttons button {
  border: 1px solid transparent;
  background: transparent;
  color: var(--ink-500);
  font-size: 11px;
  padding: 5px 10px;
  border-radius: 6px;
}
.presets button:hover,
.presets button.selected,
.weekday-buttons button.selected {
  color: #5a4bbd;
  background: #f0edfc;
  border-color: #e6e0fa;
}
.filter-main {
  display: flex;
  align-items: end;
  gap: 12px;
  flex-wrap: wrap;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 7px;
  min-width: 0;
}
.field > span {
  font-size: 11px;
  font-weight: 500;
  color: var(--ink-700);
}
.field small {
  font-size: 10px;
  font-weight: 400;
  color: var(--ink-500);
  margin-left: 5px;
}
.field input,
.field select {
  height: 36px;
  box-sizing: border-box;
  border: 1px solid #dfe4ed;
  background: #fff;
  border-radius: 7px;
  padding: 0 10px;
  color: var(--ink-700);
  font-size: 12px;
  color-scheme: light;
  min-width: 0;
  width: 100%;
}
.date-field {
  flex: 1;
  max-width: 190px;
  min-width: 135px;
}
.date-separator {
  align-self: end;
  line-height: 36px;
  color: #bcc4d2;
}
.timezone-field {
  min-width: 158px;
  max-width: 190px;
  flex: 1;
}
.filter-actions {
  display: flex;
  gap: 9px;
  margin-left: auto;
  align-items: center;
}
.quiet-button {
  border: 0;
  background: transparent;
  color: var(--ink-500);
  font-size: 12px !important;
  padding: 8px 6px;
}
.quiet-button:hover {
  color: var(--brand-primary);
}
.primary-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  background: #6354ce;
  border: 1px solid #6354ce;
  color: white;
  padding: 8px 15px;
  min-height: 36px;
  border-radius: 7px;
  font-size: 12px !important;
  font-weight: 500;
  box-shadow: 0 3px 8px #6354ce18;
}
.primary-button:hover {
  background: #5544bd;
}
.advanced-filters {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px 24px;
  padding-top: 20px;
  margin-top: 18px;
  border-top: 1px solid #eef0f5;
}
.hour-inputs {
  display: flex;
  align-items: center;
  gap: 12px;
}
.hour-inputs > span {
  color: var(--ink-500);
  font-size: 11px;
}
.weekday-buttons {
  display: flex;
  gap: 5px;
}
.weekday-buttons button {
  height: 36px;
  flex: 1;
  border-color: #e5e9f0;
}
.filter-note {
  grid-column: 1/-1;
  margin: 0;
  font-size: 11px;
  color: var(--ink-500);
}
.filter-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  padding-top: 14px;
  font-size: 10px;
  align-items: center;
}
.filter-tags > span {
  background: #f3f2fa;
  color: #665b9d;
  padding: 3px 8px;
  border-radius: 5px;
}
.filter-tags em {
  font-style: normal;
  color: #ae761c;
  margin-left: auto;
}
.options-error {
  color: #b45309;
  font-size: 12px;
}
.options-error button {
  border: 0;
  background: none;
  color: var(--brand-primary);
}
.results-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  color: var(--ink-700);
  font-size: 12px;
  margin-top: 4px;
}
.results-header small {
  color: var(--ink-500);
  font-size: 10px;
}
.metric-switch {
  display: flex;
  background: #eaeaf1;
  border-radius: 8px;
  padding: 3px;
  gap: 3px;
}
.metric-switch button {
  display: flex;
  gap: 6px;
  align-items: center;
  font-size: 11px;
  padding: 7px 12px;
  border: 0;
  border-radius: 6px;
  color: var(--ink-500);
  background: none;
}
.metric-switch button.active {
  background: white;
  color: var(--chart-color);
  box-shadow: 0 1px 4px #0f172a10;
  font-weight: 600;
}
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}
.refreshing {
  opacity: 0.55;
  transition: opacity 0.2s;
}
.metric-card {
  padding: 20px 23px;
}
.metric-card-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  color: var(--ink-500);
}
.metric-icon {
  display: grid;
  place-items: center;
  height: 30px;
  width: 30px;
  border-radius: 9px;
  background: #efedfc;
  color: #7663cf;
}
.teal .metric-icon {
  background: #e5f7f2;
  color: #259c88;
}
.violet .metric-icon {
  background: #f4ecfc;
  color: #a172c6;
}
.amber .metric-icon {
  background: #fff4df;
  color: #bf9650;
}
.metric-number {
  font-size: 32px;
  line-height: 1.6;
  font-weight: 600;
  letter-spacing: -1px;
  color: #263047;
  font-variant-numeric: tabular-nums;
  margin-top: 4px;
}
.metric-number small {
  font-size: 11px;
  font-weight: 400;
  letter-spacing: 0;
  margin-left: 7px;
  color: var(--ink-500);
}
.metric-card p {
  font-size: 10px;
  color: #8b95a7;
  margin: 5px 0 0;
}
.panel {
  padding: 24px;
}
.panel-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 15px;
  margin-bottom: 23px;
}
.section-kicker {
  font-size: 9px;
  color: #939ab0;
  font-weight: 600;
  letter-spacing: 1.6px;
}
.panel h2,
.conversation-card h2 {
  font-size: 16px;
  font-weight: 600;
  margin: 5px 0 0;
  color: #2a3247;
  letter-spacing: 0.2px;
}
.panel-heading p {
  font-size: 11px;
  color: var(--ink-500);
  margin: 7px 0 0;
}
.metric-badge {
  font-size: 10px;
  color: var(--chart-color);
  background: var(--chart-soft);
  padding: 4px 9px;
  border-radius: 5px;
  white-space: nowrap;
}
.peak-label {
  font-size: 10px;
  color: var(--ink-500);
  display: flex;
  align-items: center;
  gap: 8px;
}
.peak-label strong {
  font-size: 13px;
  color: var(--ink-700);
}
.peak-label span {
  padding-left: 8px;
  border-left: 1px solid #e5e9f0;
  color: var(--chart-color);
}
.analysis-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  min-width: 0;
}
.analysis-grid > .panel {
  min-width: 0;
}
.hour-bars {
  height: 164px;
  display: grid;
  grid-template-columns: repeat(24, minmax(0, 1fr));
  gap: 5px;
  margin-top: 8px;
}
.hour-bar {
  border: 0;
  background: none;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
  color: var(--ink-500);
  min-width: 0;
}
.bar-track {
  height: 130px;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  background: #f7f8fc;
  border-radius: 4px;
  width: 100%;
  overflow: hidden;
}
.bar-track i {
  width: 100%;
  border-radius: 4px 4px 0 0;
  background: var(--chart-color);
  opacity: 0.72;
  min-height: 0;
  transition: height 0.3s;
}
.hour-bar:hover i {
  opacity: 1;
}
.hour-label {
  font-size: 9px;
  height: 14px;
}
.panel-footnote {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 10px;
  color: var(--ink-500);
  padding-top: 14px;
  margin-top: 10px;
  border-top: 1px solid #eef1f6;
  flex-wrap: wrap;
}
.panel-footnote strong {
  color: var(--chart-color);
  font-weight: 500;
}
.panel-footnote > span:last-child {
  margin-left: auto;
}
.rhythm-scroll {
  overflow-x: auto;
  padding: 0 0 3px;
}
.rhythm-labels,
.rhythm-row {
  display: grid;
  grid-template-columns: 18px repeat(24, minmax(9px, 1fr));
  gap: 3px;
  min-width: 360px;
  margin-bottom: 3px;
}
.rhythm-labels {
  height: 20px;
  align-items: start;
  font-size: 9px;
  color: var(--ink-500);
}
.rhythm-row {
  height: 17px;
}
.rhythm-day {
  font-size: 9px;
  color: var(--ink-500);
  align-self: center;
}
.rhythm-row button,
.small-legend i {
  border: 1px solid #0f172a03;
  border-radius: 3px;
  background: #edf0f5;
  padding: 0;
}
.rhythm-row button:hover {
  outline: 1px solid var(--chart-color);
  transform: scale(1.15);
}
[data-level='1'] {
  background: var(--level-1) !important;
}
[data-level='2'] {
  background: var(--level-2) !important;
}
[data-level='3'] {
  background: var(--level-3) !important;
}
[data-level='4'] {
  background: var(--level-4) !important;
}
.small-legend {
  display: flex;
  align-items: center;
  gap: 3px;
  font-size: 9px;
  margin-left: auto;
}
.small-legend i {
  display: block;
  width: 10px;
  height: 10px;
}
.bottom-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.85fr) minmax(0, 1fr);
  gap: 20px;
  align-items: start;
}
.leaderboard {
  padding-bottom: 14px;
  min-width: 0;
}
.count-badge {
  font-size: 10px;
  font-weight: 500;
  vertical-align: middle;
  background: #f1effa;
  border-radius: 5px;
  color: #897bb4;
  padding: 3px 7px;
  margin-left: 4px;
}
.rank-search {
  display: flex;
  align-items: center;
  gap: 7px;
  max-width: 155px;
  border: 1px solid #e5e9f0;
  border-radius: 7px;
  padding: 7px 9px;
  color: #9ba4b3;
}
.rank-search input {
  width: 100%;
  border: 0;
  outline: none;
  font-size: 11px;
}
.table-scroll {
  overflow-x: auto;
}
.leaderboard table {
  width: 100%;
  border-collapse: collapse;
  white-space: nowrap;
  font-size: 12px;
}
.leaderboard th {
  font-size: 10px;
  font-weight: 400;
  text-align: right;
  color: #9aa3b3;
  padding: 10px 8px;
  border-bottom: 1px solid #e9edf3;
}
.leaderboard th:nth-child(2) {
  text-align: left;
}
.leaderboard th button {
  border: 0;
  background: none;
  color: inherit;
  font-size: 10px;
  padding: 0;
}
.leaderboard th[aria-sort='descending'] button {
  color: var(--chart-color);
}
.leaderboard td {
  padding: 13px 8px;
  text-align: right;
  border-bottom: 1px solid #f2f4f8;
  color: var(--ink-500);
  font-variant-numeric: tabular-nums;
}
.leaderboard .rank-col,
.leaderboard .rank-number {
  text-align: left;
  width: 30px;
}
.leaderboard .rank-number {
  font-size: 11px;
  color: #a7aec0;
}
.leaderboard .top-three {
  color: var(--chart-color);
  font-weight: 600;
}
.leaderboard .selected-number {
  color: var(--ink-900);
  font-weight: 600;
}
.person-button {
  display: flex;
  align-items: center;
  gap: 10px;
  max-width: 260px;
  width: 100%;
  border: 0;
  background: none;
  padding: 0;
  text-align: left;
}
.person-avatar {
  flex-shrink: 0;
  width: 29px;
  height: 29px;
  border-radius: 10px;
  display: grid;
  place-items: center;
  background: hsl(var(--avatar-hue) 60% 96%);
  color: hsl(var(--avatar-hue) 35% 52%);
  font-size: 12px;
  font-weight: 600;
}
.person-details {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
  width: 100%;
}
.person-details strong {
  font-size: 11px;
  color: var(--ink-700);
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 185px;
}
.person-progress {
  display: block;
  height: 3px;
  border-radius: 4px;
  max-width: 120px;
  background: #f4f3fa;
}
.person-progress i {
  display: block;
  height: 100%;
  background: var(--chart-color);
  opacity: 0.4;
  border-radius: 4px;
}
.person-button:hover strong {
  color: var(--brand-primary);
}
.ranking-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 10px;
  color: #98a1b2;
  margin-top: 14px;
  gap: 8px;
}
.ranking-footer > div {
  display: flex;
  align-items: center;
  gap: 10px;
  white-space: nowrap;
}
.ranking-footer button {
  border: 1px solid #e9edf3;
  background: white;
  color: var(--ink-500);
  border-radius: 5px;
  padding: 2px 6px;
}
.leaderboard .empty-ranking {
  text-align: center;
  padding: 35px 0;
}
.sidebar-panels {
  display: flex;
  flex-direction: column;
  gap: 20px;
  min-width: 0;
}
.channel-panel .panel-heading {
  margin-bottom: 17px;
}
.channel-row {
  display: block;
  width: 100%;
  margin: 0 0 17px;
  padding: 0;
  border: 0;
  background: none;
  text-align: left;
}
.channel-line {
  display: flex;
  gap: 8px;
  justify-content: space-between;
  font-size: 10px;
  color: var(--ink-500);
}
.channel-line > span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.channel-line em {
  font-style: normal;
  color: #b3bac8;
  font-size: 9px;
  margin-right: 4px;
}
.channel-line strong {
  color: var(--ink-700);
  font-size: 11px;
  font-weight: 500;
  white-space: nowrap;
}
.channel-track {
  display: block;
  height: 5px;
  border-radius: 4px;
  background: #f3f4f9;
  margin-top: 8px;
}
.channel-track i {
  display: block;
  height: 100%;
  background: var(--chart-color);
  opacity: 0.55;
  border-radius: 4px;
}
.channel-row:hover .channel-track i {
  opacity: 1;
}
.channel-note {
  font-size: 10px;
  color: #9aa3b3;
  margin: 16px 0 0;
}
.conversation-card {
  border: 1px solid #e3e0f1;
  border-radius: 15px;
  padding: 24px;
  background: linear-gradient(130deg, #f1effa, #f8f7fc);
}
.conversation-card h2 {
  margin-bottom: 20px;
}
.conversation-card > div {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 14px;
  font-size: 11px;
  color: #7e7894;
}
.conversation-card strong {
  color: #615578;
  font-size: 16px;
  font-weight: 500;
  font-variant-numeric: tabular-nums;
}
.conversation-card small {
  font-size: 10px;
  font-weight: 400;
}
.activity-footer {
  display: flex;
  align-items: start;
  gap: 10px;
  color: #98a1b2;
  font-size: 10px;
  margin: 2px 4px 16px;
}
.activity-footer > .el-icon {
  margin-top: 4px;
  flex-shrink: 0;
}
.activity-footer p {
  margin: 0;
  line-height: 1.8;
  max-width: 760px;
}
.activity-footer button {
  display: flex;
  align-items: center;
  gap: 4px;
  white-space: nowrap;
  margin-left: auto;
  border: 0;
  background: none;
  color: #867aa8;
  font-size: 10px !important;
  padding: 0;
}
.empty-notice {
  display: flex;
  gap: 12px;
  align-items: center;
  background: #f0eef9;
  border: 1px solid #e4dff4;
  border-radius: 10px;
  padding: 16px 20px;
  color: #7966a3;
}
.empty-notice strong {
  font-size: 12px;
  font-weight: 500;
}
.empty-notice p {
  font-size: 11px;
  margin: 4px 0 0;
}
.muted {
  color: var(--ink-500);
  font-size: 12px;
}
.state-panel {
  padding: 36px;
  border-radius: 15px;
  background: #fff;
  border: 1px solid #e5e9f0;
  text-align: center;
  color: var(--ink-500);
}
.state-panel strong {
  font-size: 16px;
  color: var(--ink-900);
}
.state-panel p {
  font-size: 13px;
}
.error-panel {
  border-color: #fecaca;
}
.loading-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}
.skeleton-card,
.skeleton-chart {
  background: linear-gradient(100deg, #e8ebf2 20%, #f6f7fa 45%, #e8ebf2 70%);
  background-size: 200% 100%;
  animation: shimmer 1.6s infinite;
  border-radius: 15px;
  height: 145px;
}
.skeleton-chart {
  grid-column: 1/-1;
  height: 220px;
}
.loading-grid > span {
  grid-column: 1/-1;
  text-align: center;
  font-size: 12px;
  color: var(--ink-500);
}
.spinning {
  animation: spin 1s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
@keyframes shimmer {
  to {
    background-position: -200% 0;
  }
}
@media (prefers-reduced-motion: reduce) {
  .spinning,
  .skeleton-card,
  .skeleton-chart {
    animation: none;
  }
  .bar-track i {
    transition: none;
  }
}
@media (max-width: 1024px) {
  .metrics-grid {
    gap: 12px;
  }
  .metric-card {
    padding: 18px;
  }
  .metric-number {
    font-size: 27px;
  }
  .analysis-grid {
    grid-template-columns: 1fr;
  }
  .bottom-grid {
    grid-template-columns: minmax(0, 1.65fr) minmax(0, 1fr);
  }
  .activity-hero h1 span {
    display: block;
    margin: 4px 0 0;
    font-size: 14px;
  }
  .filter-actions {
    margin-left: 0;
  }
  .filter-main {
    gap: 10px;
  }
  .filter-top {
    align-items: start;
  }
  .person-details strong {
    max-width: 145px;
  }
  .rank-search {
    max-width: 120px;
  }
}
@media (max-width: 720px) {
  .activity-page {
    gap: 16px;
  }
  .activity-hero {
    padding: 25px 22px;
    align-items: start;
  }
  .activity-hero h1 {
    font-size: 27px;
  }
  .activity-hero h1 span {
    font-size: 12px;
  }
  .hero-copy p {
    font-size: 10px;
    max-width: 210px;
    line-height: 1.8;
  }
  .hero-meta strong {
    font-size: 13px;
  }
  .hero-meta-label {
    font-size: 9px;
  }
  .hero-refresh {
    font-size: 10px !important;
    padding: 5px 8px;
  }
  .metrics-grid {
    grid-template-columns: 1fr 1fr;
  }
  .metric-number {
    font-size: 29px;
  }
  .metric-card {
    padding: 17px;
  }
  .metric-card p {
    font-size: 9px;
  }
  .filter-panel {
    padding: 18px;
  }
  .filter-top {
    flex-direction: column;
    gap: 12px;
  }
  .presets {
    gap: 2px;
  }
  .presets button {
    padding: 5px 8px;
    font-size: 10px;
  }
  .filter-main {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 14px;
  }
  .date-field,
  .timezone-field {
    max-width: none;
    min-width: 0;
  }
  .date-separator {
    display: none;
  }
  .filter-actions {
    grid-column: 1/-1;
    justify-content: flex-end;
  }
  .timezone-field {
    grid-column: 1/-1;
  }
  .advanced-filters {
    grid-template-columns: 1fr;
  }
  .results-header {
    flex-wrap: wrap;
    font-size: 11px;
  }
  .results-header small {
    font-size: 9px;
  }
  .metric-switch {
    margin-left: auto;
  }
  .panel {
    padding: 20px 18px;
  }
  .panel h2 {
    font-size: 15px;
  }
  .panel-heading p {
    font-size: 10px;
  }
  .peak-label {
    flex-wrap: wrap;
    justify-content: flex-end;
    gap: 4px;
    max-width: 135px;
  }
  .peak-label span {
    border: 0;
    padding: 0;
  }
  .bottom-grid {
    grid-template-columns: 1fr;
  }
  .sidebar-panels {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
  }
  .conversation-card {
    padding: 20px 16px;
  }
  .conversation-card h2 {
    font-size: 14px;
  }
  .channel-line {
    font-size: 9px;
  }
  .activity-footer {
    flex-wrap: wrap;
  }
  .activity-footer p {
    flex: 1;
    min-width: 240px;
  }
  .activity-footer button {
    margin-left: 24px;
  }
  .rank-search {
    max-width: 120px;
  }
  .person-details strong {
    max-width: 180px;
  }
  .loading-grid {
    grid-template-columns: 1fr 1fr;
  }
}
@media (max-width: 400px) {
  .hero-meta {
    max-width: 105px;
  }
  .hero-copy {
    max-width: 205px;
  }
  .activity-hero h1 span {
    font-size: 11px;
  }
  .sidebar-panels {
    grid-template-columns: 1fr;
  }
  .person-details strong {
    max-width: 125px;
  }
  .metric-card {
    padding: 15px;
  }
  .metric-number {
    font-size: 25px;
  }
  .filter-panel {
    padding: 15px;
  }
  .ranking-footer {
    flex-wrap: wrap;
  }
}
</style>
