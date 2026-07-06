<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElButton, ElIcon, ElMessage, ElMessageBox } from 'element-plus'
import { Briefcase, Delete, Plus, Refresh } from '@element-plus/icons-vue'
import { storeToRefs } from 'pinia'

import DeleteWithPasswordDialog from '../components/DeleteWithPasswordDialog.vue'
import JobCardSkeleton from '../components/jobs/JobCardSkeleton.vue'
import JobDetailDialog from '../components/jobs/JobDetailDialog.vue'
import JobFilterBar from '../components/jobs/JobFilterBar.vue'
import JobFormDialog from '../components/jobs/JobFormDialog.vue'
import JobRecordCard from '../components/jobs/JobRecordCard.vue'
import JobSortRow from '../components/jobs/JobSortRow.vue'
import {
  COMPANY_FILTER_LIMIT,
  CATEGORY_FILTER_LIMIT,
  SORT_OPTIONS,
  safeKind,
  safeOrder,
  safeSort,
  safeStringList,
  safeYear,
} from '../components/jobs/jobFilters'

import { jobsApi } from '../api/jobs'
import { useAuthStore } from '../stores/auth'
import { useJobsStore } from '../stores/jobs'
import { useDeleteWithPassword } from '../composables/useDeleteWithPassword'
import { useDialogRouteSync } from '../composables/useDialogRouteSync'
import { useUrlQuerySync } from '../composables/useUrlQuerySync'

const auth = useAuthStore()

const route = useRoute()
const router = useRouter()

const SEARCH_DEBOUNCE_MS = 300

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
        parse: safeSort,
        serialize: (v) => (v !== 'created_at' ? v : undefined),
      },
      sortOrder: {
        queryKey: 'order',
        parse: safeOrder,
        serialize: (v) => (v !== 'desc' ? v : undefined),
      },
      year: {
        parse: safeYear,
        serialize: (v) => (v ? String(v) : undefined),
      },
      company: {
        parse: (v) => safeStringList(v, COMPANY_FILTER_LIMIT),
        serialize: (v) => (v.length > 0 ? [...v] : undefined),
      },
      category: {
        parse: (v) => safeStringList(v, CATEGORY_FILTER_LIMIT),
        serialize: (v) => (v.length > 0 ? [...v] : undefined),
      },
      kind: {
        parse: safeKind,
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

// Admins and members can post (viewers can't). Based on the real role so an
// admin previewing as a member still sees the affordance a member would have.
const canPost = computed(() =>
  ['admin', 'member'].includes(auth.actualRole),
)

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

// Admins re-authenticate with a password (backend requires it); an owning
// member deletes their own post after a plain confirm, with no password body.
async function requestDeleteJob(job) {
  if (!job) return
  if (auth.isActuallyAdmin) {
    askDelete(job)
    return
  }
  try {
    await ElMessageBox.confirm(
      '將永久刪除這筆求職紀錄，包含心得、時程表與附件，此操作無法復原。',
      '刪除求職紀錄',
      { type: 'warning', confirmButtonText: '刪除', cancelButtonText: '取消' },
    )
  } catch {
    return // user cancelled
  }
  try {
    await jobsApi.remove(job.id)
    ElMessage.success(`已刪除「${job.company}」的紀錄`)
    if (detailOpen.value && detailJob.value?.id === job.id) {
      detailOpen.value = false
    }
    reloadFresh()
  } catch {
    ElMessage.error('刪除失敗，請稍後再試')
  }
}

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
          <span class="count-chip" aria-label="紀錄數"> {{ total }} 筆 </span>
        </div>
        <p class="subtitle">同學的實習與正職分享，點同一排序鈕可切換升降序。</p>
      </div>

      <div class="actions">
        <el-button
          :icon="Refresh"
          data-test="refresh-button"
          @click="loadItems"
        >
          重新整理
        </el-button>
        <el-button
          v-if="canPost"
          type="primary"
          :icon="Plus"
          data-test="add-job-button"
          @click="openCreate"
        >
          新增紀錄
        </el-button>
      </div>
    </header>

    <JobFilterBar
      v-model:kind="kind"
      v-model:year="year"
      v-model:company="company"
      v-model:category="category"
      v-model:q="q"
    />

    <JobSortRow
      :options="SORT_OPTIONS"
      :sort-key="sortKey"
      :sort-order="sortOrder"
      @toggle="toggleSort"
    />

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
        v-if="canPost && total === 0"
        type="primary"
        :icon="Plus"
        @click="openCreate"
      >
        新增第一筆紀錄
      </el-button>
    </div>

    <JobDetailDialog v-model="detailOpen" :job="detailJob" @edit="onDetailEdit">
      <template #footer-extra>
        <el-button
          v-if="detailJob?.can_edit"
          type="danger"
          plain
          :icon="Delete"
          data-test="detail-delete-button"
          @click="requestDeleteJob(detailJob)"
        >
          刪除整筆紀錄
        </el-button>
      </template>
    </JobDetailDialog>

    <JobFormDialog v-model="formOpen" :job="editingJob" @saved="reloadFresh" />

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
  color: var(--surface-0);
  background: linear-gradient(
    135deg,
    var(--brand-primary),
    var(--brand-accent)
  );
  box-shadow: 0 6px 18px rgba(99, 102, 241, 0.3);
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
  background: linear-gradient(
    135deg,
    rgba(99, 102, 241, 0.12),
    rgba(139, 92, 246, 0.12)
  );
  color: var(--brand-primary-hover);
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
    radial-gradient(closest-side, rgba(99, 102, 241, 0.05), transparent 70%)
      center / 70% 100% no-repeat,
    var(--surface-0);
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
    rgba(139, 92, 246, 0.12)
  );
  color: var(--brand-primary-hover);
  box-shadow: 0 8px 24px -10px rgba(99, 102, 241, 0.4);
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

  .card-grid {
    grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
    gap: var(--sp-sm);
  }
}
</style>
