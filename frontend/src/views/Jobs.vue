<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ElButton,
  ElIcon,
  ElInput,
  ElMessage,
  ElOption,
  ElSelect,
} from 'element-plus'
import {
  Briefcase,
  Calendar,
  Delete,
  Edit,
  OfficeBuilding,
  Plus,
  Refresh,
  School,
  Search,
  User,
} from '@element-plus/icons-vue'

import DeleteWithPasswordDialog from '../components/DeleteWithPasswordDialog.vue'
import JobDetailDialog from '../components/JobDetailDialog.vue'
import JobFormDialog from '../components/JobFormDialog.vue'
import { jobsApi } from '../api/jobs'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()

const route = useRoute()
const router = useRouter()

const SORT_OPTIONS = [
  { key: 'created_at', label: '發布日期' },
  { key: 'job_year', label: '求職年月' },
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

const KIND_FILTER_OPTIONS = [
  { label: '全部', value: '' },
  { label: '實習', value: 'internship' },
  { label: '正職', value: 'fulltime' },
]
const ALLOWED_KIND_FILTERS = KIND_FILTER_OPTIONS.map((o) => o.value)

const CURRENT_YEAR = new Date().getFullYear()
const MIN_JOB_YEAR = 2000
const YEAR_OPTIONS = (() => {
  const out = []
  for (let y = CURRENT_YEAR; y >= MIN_JOB_YEAR; y--) out.push(y)
  return out
})()

const SEARCH_DEBOUNCE_MS = 300

function _safeSort(v) {
  return ALLOWED_SORTS.includes(v) ? v : 'created_at'
}
function _safeOrder(v) {
  return ALLOWED_ORDERS.includes(v) ? v : 'desc'
}
function _safeKind(v) {
  return ALLOWED_KIND_FILTERS.includes(v) ? v : ''
}
function _safeYear(v) {
  if (v === undefined || v === null || v === '') return null
  const n = Number(v)
  if (!Number.isFinite(n)) return null
  if (n < MIN_JOB_YEAR || n > CURRENT_YEAR) return null
  return n
}

const COMPANY_FILTER_LIMIT = 10

// route.query.company is `string | string[] | undefined` depending on
// how many `company=` params the URL carries. Normalize to a deduped
// array of trimmed strings so the select's v-model has a stable shape.
function _safeCompanyList(v) {
  const raw = v === undefined || v === null
    ? []
    : Array.isArray(v) ? v : [v]
  const out = []
  for (const item of raw) {
    if (typeof item !== 'string') continue
    const trimmed = item.trim()
    if (!trimmed) continue
    if (!out.includes(trimmed)) out.push(trimmed)
    if (out.length >= COMPANY_FILTER_LIMIT) break
  }
  return out
}

const sortKey = ref(_safeSort(route.query.sort))
const sortOrder = ref(_safeOrder(route.query.order))
const year = ref(_safeYear(route.query.year))
const company = ref(_safeCompanyList(route.query.company))
const kind = ref(_safeKind(route.query.kind))
const q = ref(typeof route.query.q === 'string' ? route.query.q : '')

const items = ref([])
const total = ref(0)
const loading = ref(false)

const formOpen = ref(false)
const editingJob = ref(null)

const detailOpen = ref(false)
const detailJob = ref(null)

function openCreate() {
  editingJob.value = null
  formOpen.value = true
}

function openEdit(job) {
  editingJob.value = { ...job }
  formOpen.value = true
}

function openDetail(job) {
  detailJob.value = job
  detailOpen.value = true
}

function onDetailEdit(job) {
  // Close detail dialog (handled by detail itself) and open the form
  // for the same record. The detail dialog closes synchronously via
  // its own close emit, so opening the form on the next tick keeps
  // the el-overlay z-index stack tidy.
  setTimeout(() => openEdit(job), 0)
}

const deleteDialogOpen = ref(false)
const deleteTarget = ref(null)
const deleteSubmitting = ref(false)
const deleteError = ref('')

function askDelete(job) {
  deleteTarget.value = job
  deleteError.value = ''
  deleteDialogOpen.value = true
}

async function handleDeleteConfirm(password) {
  const target = deleteTarget.value
  if (!target) return
  deleteSubmitting.value = true
  deleteError.value = ''
  try {
    await jobsApi.remove(target.id, password)
    ElMessage.success(`已刪除「${target.company}」的紀錄`)
    deleteDialogOpen.value = false
    deleteTarget.value = null
    // Close the detail dialog too if it was open on this same row.
    if (detailOpen.value && detailJob.value?.id === target.id) {
      detailOpen.value = false
    }
    loadItems()
  } catch (err) {
    const status = err?.response?.status
    if (status === 401) deleteError.value = '密碼錯誤'
    else if (status === 403) deleteError.value = '權限不足'
    else if (status === 404) deleteError.value = '紀錄已不存在'
    else deleteError.value = '刪除失敗，請稍後再試'
  } finally {
    deleteSubmitting.value = false
  }
}

async function loadItems() {
  loading.value = true
  try {
    const data = await jobsApi.list({
      sort: sortKey.value,
      order: sortOrder.value,
      year: year.value ?? undefined,
      company: company.value,
      kind: kind.value || undefined,
      q: q.value || undefined,
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

function syncUrl() {
  const query = {}
  if (sortKey.value !== 'created_at') query.sort = sortKey.value
  if (sortOrder.value !== 'desc') query.order = sortOrder.value
  if (year.value) query.year = String(year.value)
  if (company.value.length > 0) query.company = [...company.value]
  if (kind.value) query.kind = kind.value
  if (q.value) query.q = q.value
  router.replace({ query })
}

// Sort/year/company/kind changes are immediate. Search input is debounced
// so a user typing doesn't fire a request per keystroke.
watch(
  [sortKey, sortOrder, year, company, kind],
  () => {
    syncUrl()
    loadItems()
  },
  { deep: true },
)

let qTimer = null
watch(q, () => {
  if (qTimer !== null) clearTimeout(qTimer)
  qTimer = setTimeout(() => {
    qTimer = null
    syncUrl()
    loadItems()
  }, SEARCH_DEBOUNCE_MS)
})

onUnmounted(() => {
  if (qTimer !== null) clearTimeout(qTimer)
})

// el-select with `remote` calls this on every keystroke. The dropdown
// shows only what the API returned for the current keyword — chips
// already in `company` render straight from their string value, so we
// don't inject them into options (that would surface unrelated chips
// during a fresh keyword search).
const companySuggestions = ref([])

async function fetchCompanySuggestions(queryString) {
  try {
    companySuggestions.value = await jobsApi.listCompanies(queryString || undefined)
  } catch {
    companySuggestions.value = []
  }
}

// Block auto-repeat Backspace when the inline editor is empty so a
// held key can't rapid-fire delete every selected chip. The first
// press still removes one chip; the user has to release and press
// again to delete the next one.
function onCompanyFilterKeydown(event) {
  if (
    event.key === 'Backspace' &&
    event.repeat &&
    event.target instanceof HTMLInputElement &&
    event.target.value === ''
  ) {
    event.preventDefault()
    event.stopPropagation()
  }
}

// Push already-selected matches to the bottom so the user always sees
// new options first; each group keeps the API's alphabetical order.
const displayedCompanySuggestions = computed(() => {
  const selected = new Set(company.value)
  const fresh = []
  const stale = []
  for (const c of companySuggestions.value) {
    if (selected.has(c)) stale.push(c)
    else fresh.push(c)
  }
  return [...fresh, ...stale]
})

function realNameOrAnonymous(item) {
  return item.real_name || '匿名'
}

function formatJobYearMonth(item) {
  if (!item?.job_year) return '-'
  const m = item.job_month
  return m ? `${item.job_year}/${String(m).padStart(2, '0')}` : `${item.job_year}`
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
        <el-button
          v-if="auth.isAdmin"
          type="primary"
          :icon="Plus"
          data-test="add-job-button"
          @click="openCreate"
        >
          新增紀錄
        </el-button>
      </div>
    </header>

    <div class="filter-bar">
      <div class="filter-row filter-row--meta">
        <div class="kind-chips" role="tablist" aria-label="類型篩選">
          <button
            v-for="opt in KIND_FILTER_OPTIONS"
            :key="opt.value || 'all'"
            type="button"
            role="tab"
            :aria-selected="kind === opt.value"
            :class="[
              'kind-chip',
              `kind-chip--${opt.value || 'all'}`,
              { 'is-active': kind === opt.value },
            ]"
            :data-test="`filter-kind-${opt.value || 'all'}`"
            @click="kind = opt.value"
          >
            {{ opt.label }}
          </button>
        </div>

        <el-select
          v-model="year"
          placeholder="年份"
          clearable
          data-test="filter-year"
          class="filter-year"
        >
          <template #prefix>
            <el-icon><Calendar /></el-icon>
          </template>
          <el-option
            v-for="y in YEAR_OPTIONS"
            :key="y"
            :label="`${y} 年`"
            :value="y"
          />
        </el-select>

        <el-select
          v-model="company"
          multiple
          filterable
          remote
          :remote-method="fetchCompanySuggestions"
          :reserve-keyword="false"
          :multiple-limit="10"
          placeholder="公司（可多選）"
          clearable
          data-test="filter-company"
          class="filter-company"
          @keydown.capture="onCompanyFilterKeydown"
        >
          <template #prefix>
            <el-icon><OfficeBuilding /></el-icon>
          </template>
          <el-option
            v-for="c in displayedCompanySuggestions"
            :key="c"
            :label="c"
            :value="c"
          />
        </el-select>
      </div>

      <el-input
        v-model="q"
        placeholder="搜尋姓名、心得"
        :prefix-icon="Search"
        clearable
        data-test="filter-search"
        class="filter-search"
      />
    </div>

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
        role="button"
        tabindex="0"
        @click="openDetail(i)"
        @keydown.enter="openDetail(i)"
        @keydown.space.prevent="openDetail(i)"
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
            {{ formatJobYearMonth(i) }} 求職
          </span>
          <span class="meta-date">
            <el-icon :size="12"><Calendar /></el-icon>
            {{ formatDate(i.created_at) }} 發佈
          </span>
        </div>

        <div v-if="auth.isAdmin" class="card-admin-actions" @click.stop>
          <button
            type="button"
            class="card-admin-btn"
            data-test="edit-job-button"
            aria-label="編輯"
            title="編輯"
            @click="openEdit(i)"
          >
            <el-icon :size="14"><Edit /></el-icon>
          </button>
          <button
            type="button"
            class="card-admin-btn card-admin-btn--danger"
            data-test="delete-job-button"
            aria-label="刪除"
            title="刪除"
            @click="askDelete(i)"
          >
            <el-icon :size="14"><Delete /></el-icon>
          </button>
        </div>
      </article>
    </div>

    <div v-else class="empty-state" data-test="empty-state">
      <div class="empty-icon" aria-hidden="true">
        <el-icon :size="32"><Briefcase /></el-icon>
      </div>
      <p class="empty-text">尚無符合條件的紀錄</p>
      <el-button
        v-if="auth.isAdmin && total === 0"
        type="primary"
        :icon="Plus"
        @click="openCreate"
      >
        新增第一筆紀錄
      </el-button>
    </div>

    <JobDetailDialog
      v-model="detailOpen"
      :job="detailJob"
      @edit="onDetailEdit"
    >
      <template #footer-extra>
        <el-button
          v-if="auth.isAdmin && detailJob"
          type="danger"
          plain
          :icon="Delete"
          data-test="detail-delete-button"
          @click="askDelete(detailJob)"
        >
          刪除
        </el-button>
      </template>
    </JobDetailDialog>

    <JobFormDialog
      v-model="formOpen"
      :job="editingJob"
      @saved="loadItems"
    />

    <DeleteWithPasswordDialog
      v-model="deleteDialogOpen"
      title="刪除求職紀錄"
      :item-name="deleteTarget?.company ?? ''"
      warning="將永久刪除這筆求職紀錄，包含心得與時程表。此操作無法復原。"
      :loading="deleteSubmitting"
      :error-message="deleteError"
      @confirm="handleDeleteConfirm"
    />
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
   Filter bar
   ============================================================ */
.filter-bar {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px;
  background: #ffffff;
  border: 1px solid rgba(15, 23, 42, 0.06);
  border-radius: var(--radius-lg);
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
}

/* Row 1 — narrow widgets (kind chips, year, company autocomplete) so
   the row stays compact and the search input can take a full-width
   line of its own below. */
.filter-row {
  display: flex;
  align-items: center;
  gap: var(--sp-sm);
  flex-wrap: wrap;
}

/* ----- Kind segmented chips ----- */
.kind-chips {
  display: inline-flex;
  background: var(--surface-2, #f1f5f9);
  border-radius: 999px;
  padding: 3px;
  gap: 2px;
}

.kind-chip {
  border: 0;
  background: transparent;
  padding: 5px 14px;
  font-size: 12px;
  font-weight: 500;
  color: var(--ink-500);
  border-radius: 999px;
  cursor: pointer;
  transition: background-color var(--dur) var(--ease),
    color var(--dur) var(--ease), box-shadow var(--dur) var(--ease);
}

.kind-chip:hover {
  color: var(--ink-700);
}

.kind-chip.is-active {
  background: #ffffff;
  color: var(--ink-900);
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.08);
}

.kind-chip--internship.is-active {
  color: #4f46e5;
}

.kind-chip--fulltime.is-active {
  color: #047857;
}

.filter-year {
  width: 130px;
}

.filter-company {
  flex: 1;
  min-width: 200px;
}

/* Suppress the nested border that would otherwise appear around the
   chips' inline editor — el-select renders an internal input wrapper
   when filterable+multiple, and our generic .filter-bar input shadow
   leaks into it. We want only the outer wrapper to show a border. */
.filter-company :deep(.el-select__input),
.filter-company :deep(.el-select__selection) input {
  box-shadow: none !important;
  border: none !important;
  outline: none !important;
}

/* Row 2 — search takes the full width of the filter bar so users can
   read most of what they're typing without truncation. */
.filter-search {
  width: 100%;
}

/* Element Plus inputs all share these radii / shadows so the filter
   bar reads as one cohesive surface instead of a row of mismatched
   widgets. */
.filter-bar :deep(.el-input__wrapper),
.filter-bar :deep(.el-select__wrapper) {
  border-radius: var(--radius-md);
  box-shadow: 0 0 0 1px rgba(15, 23, 42, 0.06) inset;
  transition: box-shadow var(--dur) var(--ease);
}

.filter-bar :deep(.el-input__wrapper):hover,
.filter-bar :deep(.el-select__wrapper):hover {
  box-shadow: 0 0 0 1px rgba(124, 58, 237, 0.32) inset;
}

.filter-bar :deep(.el-input__wrapper.is-focus),
.filter-bar :deep(.el-select__wrapper.is-focused) {
  box-shadow: 0 0 0 1.5px #7c3aed inset;
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
  padding: 20px 20px 18px 26px;
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

.record-card {
  cursor: pointer;
}

.record-card:hover {
  transform: translateY(-4px);
  border-color: var(--card-accent-soft);
  box-shadow: 0 18px 42px -16px rgba(15, 23, 42, 0.18);
}

.record-card:focus-visible {
  outline: 2px solid var(--card-accent-from);
  outline-offset: 3px;
}

.record-card:hover::before {
  opacity: 0.18;
}

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

.meta-date {
  margin-left: auto;
}

/* ----- Admin actions on card (hover-revealed) ----- */
.card-admin-actions {
  position: absolute;
  top: 12px;
  right: 12px;
  display: inline-flex;
  gap: 4px;
  opacity: 0;
  transform: translateY(-4px);
  transition: opacity var(--dur) var(--ease),
    transform var(--dur) var(--ease);
}

.record-card:hover .card-admin-actions,
.record-card:focus-within .card-admin-actions {
  opacity: 1;
  transform: translateY(0);
}

.card-admin-btn {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(6px);
  color: var(--ink-700);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: background-color var(--dur) var(--ease),
    color var(--dur) var(--ease), border-color var(--dur) var(--ease);
}

.card-admin-btn:hover {
  background: #ffffff;
  color: var(--card-accent-ink);
  border-color: var(--card-accent-soft);
}

.card-admin-btn--danger:hover {
  color: #b91c1c;
  border-color: rgba(220, 38, 38, 0.3);
}

/* ============================================================
   Skeleton
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

  .filter-bar {
    padding: 8px;
  }

  .filter-row {
    /* Each control on phones gets its own line so the labels and clear
       buttons aren't cramped against each other. */
    flex-direction: column;
    align-items: stretch;
  }

  .filter-year,
  .filter-company {
    width: 100%;
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
