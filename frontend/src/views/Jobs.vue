<script setup>
import { computed, onMounted, ref } from 'vue'
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
  OfficeBuilding,
  Operation,
  Plus,
  Refresh,
  Search,
} from '@element-plus/icons-vue'
import { storeToRefs } from 'pinia'

import DeleteWithPasswordDialog from '../components/DeleteWithPasswordDialog.vue'
import JobCardSkeleton from '../components/jobs/JobCardSkeleton.vue'
import JobDetailDialog from '../components/jobs/JobDetailDialog.vue'
import JobFormDialog from '../components/jobs/JobFormDialog.vue'
import JobRecordCard from '../components/jobs/JobRecordCard.vue'

import { jobsApi } from '../api/jobs'
import { useAuthStore } from '../stores/auth'
import { useJobsStore } from '../stores/jobs'
import { useDeleteWithPassword } from '../composables/useDeleteWithPassword'
import { useDialogRouteSync } from '../composables/useDialogRouteSync'
import { useUrlQuerySync } from '../composables/useUrlQuerySync'

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
const CATEGORY_FILTER_LIMIT = 10

// route.query.{company,category} is `string | string[] | undefined` depending
// on how many params the URL carries. Normalize to a deduped array of trimmed
// strings so each select's v-model has a stable shape.
function _safeStringList(v, limit) {
  const raw = v === undefined || v === null ? [] : Array.isArray(v) ? v : [v]
  const out = []
  for (const item of raw) {
    if (typeof item !== 'string') continue
    const trimmed = item.trim()
    if (!trimmed) continue
    if (!out.includes(trimmed)) out.push(trimmed)
    if (out.length >= limit) break
  }
  return out
}

// Filter state lives in the URL: each field is parsed from the query on
// load and written back (sans defaults) on change, with `q` debounced.
// `detail` is preserved across rewrites — it belongs to the deep-link
// dialog below, not the filter set. onChange refetches after each sync.
const { sortKey, sortOrder, year, company, category, kind, q } =
  useUrlQuerySync({
    route,
    router,
    preserveKeys: ['detail'],
    onChange: () => loadItems(),
    fields: {
      sortKey: {
        queryKey: 'sort',
        parse: _safeSort,
        serialize: (v) => (v !== 'created_at' ? v : undefined),
      },
      sortOrder: {
        queryKey: 'order',
        parse: _safeOrder,
        serialize: (v) => (v !== 'desc' ? v : undefined),
      },
      year: {
        parse: _safeYear,
        serialize: (v) => (v ? String(v) : undefined),
      },
      company: {
        parse: (v) => _safeStringList(v, COMPANY_FILTER_LIMIT),
        serialize: (v) => (v.length > 0 ? [...v] : undefined),
      },
      category: {
        parse: (v) => _safeStringList(v, CATEGORY_FILTER_LIMIT),
        serialize: (v) => (v.length > 0 ? [...v] : undefined),
      },
      kind: {
        parse: _safeKind,
        serialize: (v) => v || undefined,
      },
      q: {
        parse: (v) => (typeof v === 'string' ? v : ''),
        serialize: (v) => v || undefined,
        debounce: SEARCH_DEBOUNCE_MS,
      },
    },
  })

const jobsStore = useJobsStore()
const { items, total, loading } = storeToRefs(jobsStore)

const formOpen = ref(false)
const editingJob = ref(null)

// ?detail=<id> deep-link ↔ detail dialog. A deep-link URL fetches the
// record and opens the dialog; closing it drops `detail` from the URL.
// The query-key shape is owned by jobsApi.detailRoute() — see api/jobs.js.
const {
  open: detailOpen,
  item: detailJob,
  show: openDetail,
} = useDialogRouteSync({
  route,
  router,
  queryKey: 'detail',
  fetchItem: (id) => jobsApi.get(id),
})

function openCreate() {
  editingJob.value = null
  formOpen.value = true
}

function openEdit(job) {
  editingJob.value = { ...job }
  formOpen.value = true
}

function onDetailEdit(job) {
  // Close detail dialog (handled by detail itself) and open the form
  // for the same record. The detail dialog closes synchronously via
  // its own close emit, so opening the form on the next tick keeps
  // the el-overlay z-index stack tidy.
  setTimeout(() => openEdit(job), 0)
}

const {
  dialogOpen: deleteDialogOpen,
  target: deleteTarget,
  submitting: deleteSubmitting,
  error: deleteError,
  open: askDelete,
  confirm: handleDeleteConfirm,
} = useDeleteWithPassword({
  remove: (job, password) => jobsApi.remove(job.id, password),
  messages: { 404: '紀錄已不存在' },
  onSuccess: (job) => {
    ElMessage.success(`已刪除「${job.company}」的紀錄`)
    // Close the detail dialog too if it was open on this same row.
    if (detailOpen.value && detailJob.value?.id === job.id) {
      detailOpen.value = false
    }
    reloadFresh()
  },
})

async function loadItems() {
  try {
    await jobsStore.fetch({
      sort: sortKey.value,
      order: sortOrder.value,
      year: year.value ?? undefined,
      company: company.value,
      category: category.value,
      kind: kind.value || undefined,
      q: q.value || undefined,
    })
  } catch (err) {
    ElMessage.error('載入求職紀錄失敗')
  }
}

// After a create/update/delete the cache would otherwise serve a stale
// row, so drop it before reloading the current view authoritatively.
function reloadFresh() {
  jobsStore.invalidate()
  loadItems()
}

function toggleSort(key) {
  if (sortKey.value === key) {
    sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortKey.value = key
    sortOrder.value = 'asc'
  }
}

// el-select with `remote` calls this on every keystroke. The dropdown
// shows only what the API returned for the current keyword — chips
// already in `company` render straight from their string value, so we
// don't inject them into options (that would surface unrelated chips
// during a fresh keyword search).
const companySuggestions = ref([])
const categorySuggestions = ref([])

async function fetchCompanySuggestions(queryString) {
  try {
    companySuggestions.value = await jobsApi.listCompanies(queryString || undefined)
  } catch {
    companySuggestions.value = []
  }
}

async function fetchCategorySuggestions(queryString) {
  try {
    categorySuggestions.value = await jobsApi.listCategories(
      queryString || undefined,
    )
  } catch {
    categorySuggestions.value = []
  }
}

// Block auto-repeat Backspace when the inline editor is empty so a
// held key can't rapid-fire delete every selected chip. The first
// press still removes one chip; the user has to release and press
// again to delete the next one.
function onChipFilterKeydown(event) {
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
function _reorderSuggestions(selected, suggestions) {
  const sel = new Set(selected)
  const fresh = []
  const stale = []
  for (const item of suggestions) {
    if (sel.has(item)) stale.push(item)
    else fresh.push(item)
  }
  return [...fresh, ...stale]
}

const displayedCompanySuggestions = computed(() =>
  _reorderSuggestions(company.value, companySuggestions.value),
)
const displayedCategorySuggestions = computed(() =>
  _reorderSuggestions(category.value, categorySuggestions.value),
)

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
          @keydown.capture="onChipFilterKeydown"
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

        <el-select
          v-model="category"
          multiple
          filterable
          remote
          :remote-method="fetchCategorySuggestions"
          :reserve-keyword="false"
          :multiple-limit="10"
          placeholder="職類（可多選）"
          clearable
          data-test="filter-category"
          class="filter-category"
          @keydown.capture="onChipFilterKeydown"
        >
          <template #prefix>
            <el-icon><Operation /></el-icon>
          </template>
          <el-option
            v-for="c in displayedCategorySuggestions"
            :key="c"
            :label="c"
            :value="c"
          />
        </el-select>
      </div>

      <el-input
        v-model="q"
        placeholder="搜尋姓名、心得內文"
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
      <JobCardSkeleton v-for="i in 6" :key="`skel-${i}`" />
    </div>

    <div v-else-if="items.length > 0" class="card-grid">
      <JobRecordCard
        v-for="i in items"
        :key="i.id"
        :job="i"
        @open="openDetail"
      />
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
          刪除整筆紀錄
        </el-button>
      </template>
    </JobDetailDialog>

    <JobFormDialog
      v-model="formOpen"
      :job="editingJob"
      @saved="reloadFresh"
    />

    <DeleteWithPasswordDialog
      v-model="deleteDialogOpen"
      title="刪除求職紀錄"
      :item-name="deleteTarget?.company ?? ''"
      warning="將永久刪除這筆求職紀錄，包含心得、時程表與所有附件。此操作無法復原。"
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
  color: var(--kind-internship-ink);
}

.kind-chip--fulltime.is-active {
  color: var(--kind-fulltime-ink);
}

.filter-year {
  width: 130px;
}

/* Company is given roughly twice the horizontal real-estate of category
   on desktop because company names tend to be longer (and there are
   typically more of them in the dropdown). flex-wrap on the parent row
   handles the narrow-viewport stack automatically once the combined
   widths exceed the row. */
.filter-company {
  flex: 2;
  min-width: 200px;
}

.filter-category {
  flex: 1;
  min-width: 160px;
}

/* Suppress the nested border that would otherwise appear around the
   chips' inline editor — el-select renders an internal input wrapper
   when filterable+multiple, and our generic .filter-bar input shadow
   leaks into it. We want only the outer wrapper to show a border. */
.filter-company :deep(.el-select__input),
.filter-company :deep(.el-select__selection) input,
.filter-category :deep(.el-select__input),
.filter-category :deep(.el-select__selection) input {
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

  /* Stack the action buttons full-width on phones; otherwise they sit
     inline with the title and squeeze .header-text down to the point
     where "求職紀錄" wraps one character per line. */
  .actions {
    width: 100%;
    justify-content: flex-end;
  }

  /* Subtitle prose is redundant on phones — the sort pills below are
     themselves tappable controls, no instructional copy needed. */
  .subtitle {
    display: none;
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
  .filter-company,
  .filter-category {
    width: 100%;
  }

  /* Compact sort row: drop the "排序" label and tighten pills so the
     options sit on one or two cleaner lines. Mirrors Members. */
  .sort-label {
    display: none;
  }

  .sort-row {
    gap: 4px;
  }

  .sort-pill {
    padding: 4px 10px;
    font-size: 11px;
  }

  .card-grid {
    grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
    gap: var(--sp-sm);
  }
}
</style>
