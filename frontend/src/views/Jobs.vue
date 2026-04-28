<script setup>
import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElButton, ElIcon, ElMessage } from 'element-plus'
import {
  Briefcase,
  Calendar,
  OfficeBuilding,
  Refresh,
  School,
  User,
} from '@element-plus/icons-vue'

import { jobsApi } from '../api/jobs'

const route = useRoute()
const router = useRouter()

const SORT_OPTIONS = [
  { key: 'created_at', label: '發布日期' },
  { key: 'job_year', label: '求職年份' },
  { key: 'company', label: '公司' },
  { key: 'real_name', label: '名字' },
  { key: 'kind', label: '類型' },
]
const ALLOWED_SORTS = SORT_OPTIONS.map((o) => o.key)
const ALLOWED_ORDERS = ['asc', 'desc']

const KIND_META = {
  internship: { label: '實習' },
  fulltime: { label: '正職' },
}

function _safeSort(v) {
  return ALLOWED_SORTS.includes(v) ? v : 'created_at'
}
function _safeOrder(v) {
  return ALLOWED_ORDERS.includes(v) ? v : 'desc'
}

const sortKey = ref(_safeSort(route.query.sort))
const sortOrder = ref(_safeOrder(route.query.order))

const items = ref([])
const total = ref(0)
const loading = ref(false)

async function loadItems() {
  loading.value = true
  try {
    const data = await jobsApi.list({
      sort: sortKey.value,
      order: sortOrder.value,
    })
    items.value = data.items
    total.value = data.total
  } catch (err) {
    ElMessage.error('載入求職紀錄失敗')
  } finally {
    loading.value = false
  }
}

function toggleSort(key) {
  if (sortKey.value === key) {
    sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortKey.value = key
    sortOrder.value = 'asc'
  }
}

// Mirror sort/order into the URL so refreshing or copy-pasting the URL
// preserves the user's view. Defaults are stripped to keep the URL
// uncluttered when nothing has been overridden.
watch([sortKey, sortOrder], () => {
  const query = { ...route.query }
  if (sortKey.value === 'created_at') delete query.sort
  else query.sort = sortKey.value
  if (sortOrder.value === 'desc') delete query.order
  else query.order = sortOrder.value
  router.replace({ query })
  loadItems()
})

function realNameOrAnonymous(item) {
  return item.real_name || '匿名'
}

function formatDate(iso) {
  if (!iso) return '-'
  return new Date(iso).toLocaleDateString('zh-TW', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  })
}

onMounted(loadItems)
</script>

<template>
  <div class="jobs-page" data-test="jobs-page">
    <header class="page-header">
      <div class="header-text">
        <div class="title-row">
          <span class="title-icon" aria-hidden="true">
            <el-icon :size="20"><Briefcase /></el-icon>
          </span>
          <h1 class="title">求職紀錄</h1>
          <span class="count-chip" aria-label="紀錄數">
            {{ total }} 筆
          </span>
        </div>
        <p class="subtitle">同學的實習與正職分享，點同一排序鈕可切換升降序。</p>
      </div>

      <div class="actions">
        <el-button :icon="Refresh" data-test="refresh-button" @click="loadItems">
          重新整理
        </el-button>
      </div>
    </header>

    <div class="sort-row">
      <span class="sort-label">排序</span>
      <button
        v-for="opt in SORT_OPTIONS"
        :key="opt.key"
        type="button"
        :class="['sort-pill', { 'is-active': sortKey === opt.key }]"
        :data-test="`sort-${opt.key}`"
        @click="toggleSort(opt.key)"
      >
        {{ opt.label }}
        <span v-if="sortKey === opt.key" class="sort-arrow" aria-hidden="true">
          {{ sortOrder === 'asc' ? '↑' : '↓' }}
        </span>
      </button>
    </div>

    <div v-if="loading" class="card-grid" data-test="grid-skeleton">
      <div
        v-for="i in 6"
        :key="`skel-${i}`"
        class="record-card record-card--skeleton"
      >
        <div class="skel-stripe shimmer"></div>
        <div class="skel-tag shimmer"></div>
        <div class="skel-line skel-line--title shimmer"></div>
        <div class="skel-line skel-line--sub shimmer"></div>
        <div class="skel-divider"></div>
        <div class="skel-line skel-line--meta shimmer"></div>
      </div>
    </div>

    <div v-else-if="items.length > 0" class="card-grid">
      <article
        v-for="i in items"
        :key="i.id"
        :class="['record-card', `record-card--${i.kind}`]"
        data-test="record-card"
      >
        <span class="card-stripe" aria-hidden="true"></span>
        <span class="card-glow" aria-hidden="true"></span>

        <span class="kind-badge" :data-test="`kind-${i.kind}`">
          <span class="kind-dot" aria-hidden="true"></span>
          {{ KIND_META[i.kind]?.label ?? i.kind }}
        </span>

        <h3 class="card-company">
          <el-icon class="company-icon" :size="14"><OfficeBuilding /></el-icon>
          <span class="company-text">{{ i.company }}</span>
        </h3>

        <p
          :class="['card-name', { 'is-anonymous': !i.real_name }]"
          :data-test="i.real_name ? 'real-name' : 'anonymous'"
        >
          <el-icon :size="12"><User /></el-icon>
          {{ realNameOrAnonymous(i) }}
        </p>

        <div class="card-meta">
          <span class="meta-year">
            <el-icon :size="12"><School /></el-icon>
            {{ i.job_year }} 求職
          </span>
          <span class="meta-date">
            <el-icon :size="12"><Calendar /></el-icon>
            {{ formatDate(i.created_at) }}
          </span>
        </div>
      </article>
    </div>

    <div v-else class="empty-state" data-test="empty-state">
      <div class="empty-icon" aria-hidden="true">
        <el-icon :size="32"><Briefcase /></el-icon>
      </div>
      <p class="empty-text">尚無求職紀錄</p>
    </div>
  </div>
</template>

<style scoped>
.jobs-page {
  display: flex;
  flex-direction: column;
  gap: var(--sp-lg);
}

/* ============================================================
   Page header
   ============================================================ */
.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--sp-md);
  flex-wrap: wrap;
}

.header-text {
  flex: 1;
  min-width: 0;
}

.title-row {
  display: inline-flex;
  align-items: center;
  gap: 10px;
}

.title-icon {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-md);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #ffffff;
  background: linear-gradient(135deg, #6366f1, #8b5cf6 50%, #d946ef);
  box-shadow: 0 6px 18px rgba(139, 92, 246, 0.32);
}

.title {
  margin: 0;
  font-size: 26px;
  font-weight: 700;
  letter-spacing: -0.01em;
  color: var(--ink-900);
}

.count-chip {
  display: inline-flex;
  align-items: center;
  padding: 3px 10px;
  border-radius: 999px;
  background: linear-gradient(135deg, rgba(139, 92, 246, 0.14), rgba(217, 70, 239, 0.14));
  color: #7c3aed;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.02em;
}

.subtitle {
  margin: 6px 0 0;
  color: var(--ink-500);
  font-size: 13px;
}

.actions {
  display: flex;
  gap: var(--sp-sm);
  align-items: center;
}

/* ============================================================
   Sort pills
   ============================================================ */
.sort-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
}

.sort-label {
  font-size: 12px;
  color: var(--ink-500);
  margin-right: 4px;
  letter-spacing: 0.04em;
}

.sort-pill {
  border: 1px solid rgba(15, 23, 42, 0.08);
  background: #ffffff;
  color: var(--ink-700);
  padding: 5px 12px;
  font-size: 12px;
  font-weight: 500;
  border-radius: 999px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  transition: background-color var(--dur) var(--ease),
    color var(--dur) var(--ease), border-color var(--dur) var(--ease),
    box-shadow var(--dur) var(--ease);
}

.sort-pill:hover {
  border-color: rgba(124, 58, 237, 0.32);
  color: #7c3aed;
}

.sort-pill.is-active {
  background: linear-gradient(135deg, #7c3aed, #d946ef);
  color: #ffffff;
  border-color: transparent;
  box-shadow: 0 6px 16px -4px rgba(124, 58, 237, 0.45);
}

.sort-arrow {
  font-size: 11px;
}

/* ============================================================
   Card grid
   ============================================================ */
.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: var(--sp-md);
}

/* ----- Card shell ----- */
.record-card {
  --card-accent-from: #6366f1;
  --card-accent-to: #8b5cf6;
  --card-accent-soft: rgba(99, 102, 241, 0.18);
  --card-accent-ink: #4f46e5;

  position: relative;
  overflow: hidden;
  background: #ffffff;
  border: 1px solid rgba(15, 23, 42, 0.06);
  border-radius: var(--radius-lg);
  padding: 20px 20px 18px 26px; /* extra left padding makes room for the stripe */
  display: flex;
  flex-direction: column;
  gap: 8px;
  isolation: isolate;
  transition: transform var(--dur) var(--ease),
    box-shadow var(--dur) var(--ease), border-color var(--dur) var(--ease);
}

.record-card--internship {
  --card-accent-from: #6366f1;
  --card-accent-to: #8b5cf6;
  --card-accent-soft: rgba(99, 102, 241, 0.18);
  --card-accent-ink: #4f46e5;
}

.record-card--fulltime {
  --card-accent-from: #10b981;
  --card-accent-to: #06b6d4;
  --card-accent-soft: rgba(16, 185, 129, 0.18);
  --card-accent-ink: #047857;
}

/* Soft halo behind the card on hover, themed by kind. -10px insets so
   the glow leaks slightly past the card border for a lifted feel. */
.record-card::before {
  content: '';
  position: absolute;
  inset: -2px;
  border-radius: inherit;
  background: linear-gradient(
    135deg,
    var(--card-accent-from),
    var(--card-accent-to)
  );
  opacity: 0;
  z-index: -1;
  transition: opacity var(--dur) var(--ease);
  filter: blur(14px);
}

.record-card:hover {
  transform: translateY(-4px);
  border-color: var(--card-accent-soft);
  box-shadow: 0 18px 42px -16px rgba(15, 23, 42, 0.18);
}

.record-card:hover::before {
  opacity: 0.18;
}

/* Side stripe — vertical kind-themed gradient on the card's left edge. */
.card-stripe {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 4px;
  background: linear-gradient(180deg, var(--card-accent-from), var(--card-accent-to));
  border-radius: 0 4px 4px 0;
  transition: width var(--dur) var(--ease);
}

.record-card:hover .card-stripe {
  width: 6px;
}

/* Subtle radial glow on the bottom-right of the card so the surface
   isn't a flat white plane. Adds depth without taking attention. */
.card-glow {
  position: absolute;
  right: -20px;
  bottom: -30px;
  width: 140px;
  height: 140px;
  border-radius: 50%;
  background: radial-gradient(closest-side, var(--card-accent-soft), transparent 70%);
  pointer-events: none;
  opacity: 0.7;
  transition: opacity var(--dur) var(--ease);
}

.record-card:hover .card-glow {
  opacity: 1;
}

/* ----- Kind badge ----- */
.kind-badge {
  align-self: flex-start;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  padding: 4px 10px 4px 8px;
  border-radius: 999px;
  background: var(--card-accent-soft);
  color: var(--card-accent-ink);
  margin-bottom: 2px;
}

.kind-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--card-accent-from), var(--card-accent-to));
  box-shadow: 0 0 0 2px rgba(255, 255, 255, 0.85);
}

/* ----- Company hero ----- */
.card-company {
  margin: 0;
  font-size: 19px;
  font-weight: 700;
  color: var(--ink-900);
  letter-spacing: -0.01em;
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.company-icon {
  flex-shrink: 0;
  color: var(--card-accent-ink);
  opacity: 0.55;
}

.company-text {
  background: linear-gradient(
    135deg,
    var(--ink-900) 0%,
    var(--card-accent-ink) 140%
  );
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ----- Real name / anonymous ----- */
.card-name {
  margin: 0;
  font-size: 13px;
  color: var(--ink-700);
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.card-name.is-anonymous {
  color: var(--ink-400, #94a3b8);
  font-style: italic;
}

/* ----- Meta row ----- */
.card-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: auto;
  padding-top: var(--sp-sm);
  border-top: 1px dashed rgba(15, 23, 42, 0.08);
}

.meta-year,
.meta-date {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--ink-500);
}

.meta-year {
  color: var(--card-accent-ink);
  font-weight: 600;
}

/* ============================================================
   Skeleton (initial-fetch placeholder)
   ============================================================ */
.record-card--skeleton {
  pointer-events: none;
}

.record-card--skeleton::before,
.record-card--skeleton .card-glow,
.record-card--skeleton .card-stripe {
  display: none;
}

.skel-stripe {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 4px;
  background: rgba(15, 23, 42, 0.08);
}

.skel-tag {
  width: 56px;
  height: 18px;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.08);
}

.skel-line {
  height: 12px;
  background: rgba(15, 23, 42, 0.06);
  border-radius: 4px;
}

.skel-line--title {
  width: 70%;
  height: 16px;
}

.skel-line--sub {
  width: 50%;
}

.skel-line--meta {
  width: 80%;
  height: 10px;
}

.skel-divider {
  height: 1px;
  background: rgba(15, 23, 42, 0.06);
  margin-top: 4px;
}

.shimmer {
  position: relative;
  overflow: hidden;
}

.shimmer::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(
    90deg,
    transparent 0%,
    rgba(255, 255, 255, 0.55) 50%,
    transparent 100%
  );
  transform: translateX(-100%);
  animation: shimmer-sweep 1.5s ease-in-out infinite;
}

@keyframes shimmer-sweep {
  0% {
    transform: translateX(-100%);
  }
  100% {
    transform: translateX(100%);
  }
}

/* ============================================================
   Empty state
   ============================================================ */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--sp-md);
  padding: 72px 24px;
  background:
    radial-gradient(closest-side, rgba(139, 92, 246, 0.05), transparent 70%) center / 70% 100% no-repeat,
    #ffffff;
  border: 1px dashed rgba(15, 23, 42, 0.12);
  border-radius: var(--radius-lg);
}

.empty-icon {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(
    135deg,
    rgba(99, 102, 241, 0.12),
    rgba(217, 70, 239, 0.12)
  );
  color: #7c3aed;
  box-shadow: 0 8px 24px -10px rgba(124, 58, 237, 0.4);
}

.empty-text {
  margin: 0;
  color: var(--ink-500);
  font-size: 14px;
}

@media (max-width: 640px) {
  .title {
    font-size: 20px;
  }

  .title-icon {
    width: 32px;
    height: 32px;
  }

  .card-grid {
    grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
    gap: var(--sp-sm);
  }

  .record-card {
    padding: 16px 16px 14px 20px;
  }

  .card-company {
    font-size: 17px;
  }
}
</style>
