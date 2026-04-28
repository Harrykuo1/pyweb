<script setup>
import { computed, markRaw, onMounted, ref } from 'vue'
import {
  ElButton,
  ElIcon,
  ElInput,
  ElMessage,
  ElTable,
  ElTableColumn,
  ElTooltip,
} from 'element-plus'
import {
  Calendar,
  Delete,
  Document,
  Edit,
  Grid,
  Loading,
  Menu,
  Plus,
  Refresh,
  School,
  Search,
  UserFilled,
} from '@element-plus/icons-vue'

import DeleteWithPasswordDialog from '../components/DeleteWithPasswordDialog.vue'
import MemberFormDialog from '../components/MemberFormDialog.vue'
import MemberPhotoCell from '../components/MemberPhotoCell.vue'
import PhotoCropDialog from '../components/PhotoCropDialog.vue'
import ResumeViewerDialog from '../components/ResumeViewerDialog.vue'
import { membersApi } from '../api/members'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()

const members = ref([])
const loading = ref(false)

const dialogOpen = ref(false)
const editingMember = ref(null)

const resumeOpen = ref(false)
const resumeMember = ref(null)

// ---------- View mode ----------
// Persisted to localStorage so a user's choice (cards vs. spreadsheet) sticks
// across sessions. Default is the card grid — community-style browsing.
const VIEW_KEY = 'pyweb.members.viewMode'
function readInitialViewMode() {
  try {
    return localStorage.getItem(VIEW_KEY) === 'list' ? 'list' : 'grid'
  } catch {
    return 'grid'
  }
}
const viewMode = ref(readInitialViewMode())
function setViewMode(m) {
  viewMode.value = m
  try {
    localStorage.setItem(VIEW_KEY, m)
  } catch {
    /* swallow — quota / private mode */
  }
}

// ---------- Sort (drives the grid; el-table has its own header sort) ----------
const SORT_OPTIONS = [
  { key: 'joined_at', label: '入群時間' },
  { key: 'graduation_year', label: '畢業年份' },
  { key: 'real_name', label: '本名' },
  { key: 'current_position', label: '職位' },
]
const sortKey = ref('joined_at')
const sortOrder = ref('asc')

function toggleSort(key) {
  if (sortKey.value === key) {
    sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortKey.value = key
    sortOrder.value = 'asc'
  }
}

// Sort orders are restricted to two states so a click cycles asc → desc →
// asc instead of the el-table default asc → desc → none.
const SORT_ORDERS = ['ascending', 'descending']

// Element Plus's default string sort uses < which is byte-wise; localeCompare
// gives the right ordering for Chinese / mixed CJK strings.
const stringSort = (key) => (a, b) =>
  String(a[key] ?? '').localeCompare(String(b[key] ?? ''), 'zh-Hant')

// ---------- Search ----------
// Client-side substring match across name / position / graduation year. Fast
// enough at community-scale (we don't expect 10k members) and avoids a
// round-trip to the backend.
const searchQuery = ref('')

const filteredMembers = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return members.value
  return members.value.filter((m) => {
    const haystack = [
      m.real_name,
      m.current_position,
      String(m.graduation_year ?? ''),
    ]
      .filter(Boolean)
      .join(' ')
      .toLowerCase()
    return haystack.includes(q)
  })
})

const sortedMembers = computed(() => {
  const arr = [...filteredMembers.value]
  const k = sortKey.value
  const dir = sortOrder.value === 'asc' ? 1 : -1
  arr.sort((a, b) => {
    const av = a[k]
    const bv = b[k]
    if (typeof av === 'number' && typeof bv === 'number') {
      return (av - bv) * dir
    }
    return String(av ?? '').localeCompare(String(bv ?? ''), 'zh-Hant') * dir
  })
  return arr
})

const memberCount = computed(() => members.value.length)
const filteredCount = computed(() => filteredMembers.value.length)

async function loadMembers() {
  loading.value = true
  try {
    members.value = await membersApi.list()
  } catch (err) {
    ElMessage.error('載入成員清單失敗')
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingMember.value = null
  dialogOpen.value = true
}

function openEdit(member) {
  editingMember.value = { ...member }
  dialogOpen.value = true
}

// ---------- Photo upload + delete (single dialogs hoisted up here so
// the cards/rows don't each carry their own hidden el-dialogs in the
// DOM — that was the dominant cost of rendering a 50-card grid). ----
const photoCropOpen = ref(false)
const photoCropFile = ref(null)
const photoCropTarget = ref(null)
const uploadingPhotoMemberId = ref(null)
// Per-member cache-buster — bumped after a successful upload so the
// browser refetches that photo without us having to refetch the
// whole list.
const photoCacheBusters = ref({})

function photoCacheBusterFor(memberId) {
  return photoCacheBusters.value[memberId] ?? 0
}

const photoDeleteDialogOpen = ref(false)
const photoDeleteTarget = ref(null)
const photoDeleteSubmitting = ref(false)
const photoDeleteError = ref('')

function onPhotoUploadRequest(member, file) {
  photoCropTarget.value = member
  photoCropFile.value = file
  photoCropOpen.value = true
}

async function onPhotoCropped(croppedFile) {
  const target = photoCropTarget.value
  if (!target) return
  uploadingPhotoMemberId.value = target.id
  const toast = ElMessage({
    message: '上傳照片中…',
    icon: markRaw(Loading),
    duration: 0,
    customClass: 'message-uploading',
  })
  try {
    await membersApi.uploadPhoto(target.id, croppedFile)
    photoCacheBusters.value = {
      ...photoCacheBusters.value,
      [target.id]: Date.now(),
    }
    toast.close()
    ElMessage.success('已上傳照片')
    loadMembers()
  } catch (err) {
    toast.close()
    if (err?.response?.status === 413) ElMessage.error('檔案過大')
    else if (err?.response?.status === 415) ElMessage.error('格式不支援')
    else ElMessage.error('上傳失敗')
  } finally {
    photoCropFile.value = null
    photoCropTarget.value = null
    uploadingPhotoMemberId.value = null
  }
}

function onPhotoDeleteRequest(member) {
  photoDeleteTarget.value = member
  photoDeleteError.value = ''
  photoDeleteDialogOpen.value = true
}

async function onPhotoDeleteConfirm(password) {
  const target = photoDeleteTarget.value
  if (!target) return
  photoDeleteSubmitting.value = true
  photoDeleteError.value = ''
  try {
    await membersApi.deletePhoto(target.id, password)
    // Bump the cache-buster too so any inline preview re-resolves.
    photoCacheBusters.value = {
      ...photoCacheBusters.value,
      [target.id]: Date.now(),
    }
    ElMessage.success('已移除照片')
    photoDeleteDialogOpen.value = false
    photoDeleteTarget.value = null
    loadMembers()
  } catch (err) {
    const status = err?.response?.status
    if (status === 401) photoDeleteError.value = '密碼錯誤'
    else if (status === 403) photoDeleteError.value = '權限不足'
    else photoDeleteError.value = '移除失敗，請稍後再試'
  } finally {
    photoDeleteSubmitting.value = false
  }
}

// ---------- Delete *member* with admin-password confirmation ----------
const deleteDialogOpen = ref(false)
const deleteTarget = ref(null)
const deleteSubmitting = ref(false)
const deleteError = ref('')

function askDeleteMember(member) {
  deleteTarget.value = member
  deleteError.value = ''
  deleteDialogOpen.value = true
}

async function handleDeleteConfirm(password) {
  const target = deleteTarget.value
  if (!target) return
  deleteSubmitting.value = true
  deleteError.value = ''
  try {
    await membersApi.remove(target.id, password)
    ElMessage.success(`已刪除「${target.real_name}」`)
    deleteDialogOpen.value = false
    deleteTarget.value = null
    loadMembers()
  } catch (err) {
    const status = err?.response?.status
    if (status === 401) deleteError.value = '密碼錯誤'
    else if (status === 403) deleteError.value = '權限不足'
    else deleteError.value = '刪除失敗，請稍後再試'
  } finally {
    deleteSubmitting.value = false
  }
}

function viewResume(member) {
  resumeMember.value = member
  resumeOpen.value = true
}

async function reloadAndRebindResume() {
  await loadMembers()
  // Re-point the resume dialog at the freshly fetched row so flag changes
  // (e.g. resume_pdf was deleted) are reflected without a full close/reopen.
  if (resumeMember.value) {
    const fresh = members.value.find((m) => m.id === resumeMember.value.id)
    resumeMember.value = fresh ?? null
    if (!fresh) resumeOpen.value = false
  }
}

function hasAnyResume(member) {
  return member.has_resume_md || member.has_resume_pdf
}

function formatDate(iso) {
  if (!iso) return '-'
  return new Date(iso).toLocaleDateString('zh-TW', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  })
}

onMounted(loadMembers)
</script>

<template>
  <div class="members-page">
    <header class="page-header">
      <div class="header-text">
        <div class="title-row">
          <span class="title-icon" aria-hidden="true">
            <el-icon :size="20"><UserFilled /></el-icon>
          </span>
          <h1 class="title">成員</h1>
          <span class="count-chip" aria-label="成員人數">
            {{ memberCount }} 位
          </span>
        </div>
        <p class="subtitle">
          {{ viewMode === 'grid' ? '點上方排序按鈕切換排序方向' : '點欄位標題可切換排序方向' }}
        </p>
      </div>

      <div class="actions">
        <div class="search-wrap">
          <el-input
            v-model="searchQuery"
            placeholder="搜尋姓名、職位或畢業年份..."
            clearable
            :prefix-icon="Search"
            class="search-input"
            data-test="search-input"
          />
          <span
            v-if="searchQuery && filteredCount !== memberCount"
            class="search-count"
            data-test="search-count"
          >
            {{ filteredCount }} / {{ memberCount }}
          </span>
        </div>

        <div class="view-toggle" role="tablist" aria-label="檢視模式">
          <button
            type="button"
            role="tab"
            :aria-selected="viewMode === 'grid'"
            :class="['view-btn', { 'is-active': viewMode === 'grid' }]"
            data-test="view-grid"
            title="卡片檢視"
            @click="setViewMode('grid')"
          >
            <el-icon :size="16"><Grid /></el-icon>
          </button>
          <button
            type="button"
            role="tab"
            :aria-selected="viewMode === 'list'"
            :class="['view-btn', { 'is-active': viewMode === 'list' }]"
            data-test="view-list"
            title="列表檢視"
            @click="setViewMode('list')"
          >
            <el-icon :size="16"><Menu /></el-icon>
          </button>
        </div>

        <el-button
          :icon="Refresh"
          data-test="refresh-button"
          @click="loadMembers"
        >
          重新整理
        </el-button>
        <el-button
          v-if="auth.isAdmin"
          type="primary"
          :icon="Plus"
          data-test="add-member-button"
          @click="openCreate"
        >
          新增成員
        </el-button>
      </div>
    </header>

    <!-- Sort pills (grid mode only — table has its own column-click sort). -->
    <div v-if="viewMode === 'grid'" class="sort-row">
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

    <!-- ---------- GRID VIEW ---------- -->
    <div v-if="viewMode === 'grid'" class="grid-stage">
      <!-- Skeleton placeholders cover the initial fetch so users see card
           shapes immediately instead of an EP spinner overlay. -->
      <div v-if="loading" class="member-grid" data-test="grid-skeleton">
        <div
          v-for="i in 8"
          :key="`skel-${i}`"
          class="member-card-skeleton"
        >
          <div class="skel-photo shimmer"></div>
          <div class="skel-body">
            <div class="skel-line skel-line--name shimmer"></div>
            <div class="skel-line skel-line--position shimmer"></div>
            <div class="skel-divider"></div>
            <div class="skel-line skel-line--meta shimmer"></div>
            <div class="skel-actions">
              <div class="skel-btn shimmer"></div>
              <div class="skel-btn shimmer"></div>
            </div>
          </div>
        </div>
      </div>

      <div v-else-if="sortedMembers.length > 0" class="member-grid">
        <article
          v-for="m in sortedMembers"
          :key="m.id"
          class="member-card"
          data-test="member-card"
        >
          <MemberPhotoCell
            :member="m"
            variant="card"
            :cache-buster="photoCacheBusterFor(m.id)"
            :uploading="uploadingPhotoMemberId === m.id"
            @request-upload="onPhotoUploadRequest"
            @request-delete="onPhotoDeleteRequest"
          />

          <div class="card-body">
            <h3 class="card-name">{{ m.real_name }}</h3>
            <p class="card-position">{{ m.current_position }}</p>

            <div class="card-meta">
              <span class="card-year">
                <el-icon :size="13"><School /></el-icon>
                {{ m.graduation_year }} 年
              </span>
              <span class="card-join">
                <el-icon :size="13"><Calendar /></el-icon>
                {{ formatDate(m.joined_at) }}
              </span>
            </div>

            <div class="card-actions">
              <el-tooltip
                v-if="!hasAnyResume(m)"
                content="此成員尚未提供履歷"
                placement="top"
              >
                <el-button size="small" :icon="Document" disabled>履歷</el-button>
              </el-tooltip>
              <el-button
                v-else
                size="small"
                type="primary"
                plain
                :icon="Document"
                data-test="view-resume-button"
                @click="viewResume(m)"
              >
                履歷
              </el-button>

              <span v-if="auth.isAdmin" class="card-admin-actions">
                <el-button
                  size="small"
                  plain
                  data-test="edit-button"
                  @click="openEdit(m)"
                >
                  編輯
                </el-button>
                <el-button
                  size="small"
                  type="danger"
                  plain
                  data-test="delete-button"
                  @click="askDeleteMember(m)"
                >
                  刪除
                </el-button>
              </span>
            </div>
          </div>
        </article>
      </div>

      <div v-else class="empty-state" data-test="empty-state">
        <div class="empty-icon" aria-hidden="true">
          <el-icon :size="32"><UserFilled /></el-icon>
        </div>
        <p v-if="searchQuery && memberCount > 0" class="empty-text">
          找不到符合「{{ searchQuery }}」的成員
        </p>
        <p v-else class="empty-text">尚無成員資料</p>
        <el-button
          v-if="auth.isAdmin && memberCount === 0"
          type="primary"
          :icon="Plus"
          @click="openCreate"
        >
          新增第一位成員
        </el-button>
      </div>
    </div>

    <!-- ---------- LIST (TABLE) VIEW ---------- -->
    <!-- Skeleton table mimics the real layout so the page doesn't shift
         when data arrives — much calmer than the v-loading spinner overlay. -->
    <div
      v-if="viewMode === 'list' && loading"
      class="table-skeleton"
      data-test="table-skeleton"
    >
      <div class="ts-header">
        <div class="ts-h-cell" style="width: 140px"></div>
        <div class="ts-h-cell" style="width: 120px"></div>
        <div class="ts-h-cell" style="width: 180px"></div>
        <div class="ts-h-cell" style="flex: 1"></div>
        <div class="ts-h-cell" style="width: 160px"></div>
        <div class="ts-h-cell" style="width: 120px"></div>
      </div>
      <div v-for="r in 6" :key="`ts-row-${r}`" class="ts-row">
        <div class="ts-photo-cell">
          <div class="ts-photo shimmer"></div>
        </div>
        <div class="ts-cell" style="width: 120px">
          <div class="ts-line shimmer" style="width: 60px"></div>
        </div>
        <div class="ts-cell" style="width: 180px">
          <div class="ts-line shimmer" style="width: 70%"></div>
        </div>
        <div class="ts-cell" style="flex: 1">
          <div class="ts-line shimmer" style="width: 80%"></div>
        </div>
        <div class="ts-cell" style="width: 160px">
          <div class="ts-line shimmer" style="width: 50%"></div>
        </div>
        <div class="ts-cell" style="width: 120px">
          <div class="ts-line shimmer" style="width: 40%"></div>
        </div>
      </div>
    </div>

    <el-table
      v-else-if="viewMode === 'list'"
      :data="filteredMembers"
      class="members-table"
      :default-sort="{ prop: 'joined_at', order: 'ascending' }"
    >
      <template #empty>
        <div class="table-empty" data-test="table-empty">
          <p v-if="searchQuery && memberCount > 0" class="table-empty-text">
            找不到符合「{{ searchQuery }}」的成員
          </p>
          <p v-else class="table-empty-text">尚無成員資料</p>
        </div>
      </template>
      <el-table-column label="照片" width="140">
        <template #default="{ row }">
          <MemberPhotoCell
            :member="row"
            :cache-buster="photoCacheBusterFor(row.id)"
            :uploading="uploadingPhotoMemberId === row.id"
            @request-upload="onPhotoUploadRequest"
            @request-delete="onPhotoDeleteRequest"
          />
        </template>
      </el-table-column>
      <el-table-column
        prop="graduation_year"
        label="畢業年份"
        width="120"
        sortable
        :sort-orders="SORT_ORDERS"
      >
        <template #default="{ row }">
          <span class="year-chip">{{ row.graduation_year }} 年</span>
        </template>
      </el-table-column>
      <el-table-column
        prop="real_name"
        label="本名"
        width="180"
        sortable
        :sort-method="stringSort('real_name')"
        :sort-orders="SORT_ORDERS"
      />
      <el-table-column
        prop="current_position"
        label="目前就職／就讀"
        sortable
        :sort-method="stringSort('current_position')"
        :sort-orders="SORT_ORDERS"
        min-width="200"
      />
      <el-table-column
        prop="joined_at"
        label="入群時間"
        width="160"
        sortable
        :sort-orders="SORT_ORDERS"
      >
        <template #default="{ row }">{{ formatDate(row.joined_at) }}</template>
      </el-table-column>
      <el-table-column label="履歷" width="120" align="center">
        <template #default="{ row }">
          <el-tooltip
            v-if="!hasAnyResume(row)"
            content="此成員尚未提供履歷"
            placement="top"
          >
            <el-button size="small" :icon="Document" disabled>履歷</el-button>
          </el-tooltip>
          <el-button
            v-else
            size="small"
            type="primary"
            plain
            :icon="Document"
            data-test="view-resume-button"
            @click="viewResume(row)"
          >
            履歷
          </el-button>
        </template>
      </el-table-column>
      <el-table-column v-if="auth.isAdmin" label="操作" width="120" align="center">
        <template #default="{ row }">
          <el-tooltip content="編輯" placement="top">
            <el-button
              size="small"
              plain
              circle
              :icon="Edit"
              data-test="edit-button"
              aria-label="編輯"
              @click="openEdit(row)"
            />
          </el-tooltip>
          <el-button
            size="small"
            type="danger"
            plain
            circle
            :icon="Delete"
            data-test="delete-button"
            aria-label="刪除"
            title="刪除"
            @click="askDeleteMember(row)"
          />
        </template>
      </el-table-column>
    </el-table>

    <MemberFormDialog
      v-model="dialogOpen"
      :member="editingMember"
      @saved="loadMembers"
    />

    <ResumeViewerDialog
      v-model="resumeOpen"
      :member="resumeMember"
      @changed="reloadAndRebindResume"
    />

    <DeleteWithPasswordDialog
      v-model="deleteDialogOpen"
      title="刪除成員"
      :item-name="deleteTarget?.real_name ?? ''"
      warning="將永久刪除這位成員與其所有照片、履歷資料。此操作無法復原。"
      :loading="deleteSubmitting"
      :error-message="deleteError"
      @confirm="handleDeleteConfirm"
    />

    <!-- Single page-level crop dialog and photo-deletion dialog —
         every MemberPhotoCell shares them via parent state, instead
         of mounting its own. -->
    <PhotoCropDialog
      v-model="photoCropOpen"
      :source-file="photoCropFile"
      @cropped="onPhotoCropped"
    />

    <DeleteWithPasswordDialog
      v-model="photoDeleteDialogOpen"
      title="移除照片"
      :item-name="photoDeleteTarget?.real_name ?? ''"
      warning="將永久移除這位成員的照片。此操作無法復原。"
      :loading="photoDeleteSubmitting"
      :error-message="photoDeleteError"
      @confirm="onPhotoDeleteConfirm"
    />
  </div>
</template>

<style scoped>
.members-page {
  display: flex;
  flex-direction: column;
  gap: var(--sp-lg);
}

/* ---------- Page header ---------- */
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
  background: linear-gradient(135deg, var(--brand-primary), var(--brand-accent));
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.28);
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
  background: rgba(99, 102, 241, 0.1);
  color: var(--brand-primary);
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
  flex-wrap: wrap;
}

/* Element Plus injects margin-left:12px between adjacent el-buttons,
   which made the gap between 重新整理 and 新增成員 wider than the rest
   of the row. Reset it so the flex gap is the only spacing source. */
.actions :deep(.el-button + .el-button) {
  margin-left: 0;
}

/* ---------- View toggle (segmented) ---------- */
.view-toggle {
  display: inline-flex;
  background: var(--surface-2);
  border-radius: var(--radius-md);
  padding: 3px;
  gap: 2px;
}

.view-btn {
  border: 0;
  background: transparent;
  padding: 6px 12px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  color: var(--ink-500);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: background-color var(--dur) var(--ease),
    color var(--dur) var(--ease);
}

.view-btn:hover {
  color: var(--ink-700);
}

.view-btn.is-active {
  background: #ffffff;
  color: var(--brand-primary);
  box-shadow: var(--shadow-sm);
}

/* ---------- Search (lives inside the header actions row) ---------- */
.search-wrap {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.search-input {
  width: 240px;
}

.search-input :deep(.el-input__wrapper) {
  background: #ffffff;
  border-radius: var(--radius-md);
  box-shadow: 0 0 0 1px rgba(15, 23, 42, 0.06) inset;
  transition: box-shadow var(--dur) var(--ease);
}

.search-input :deep(.el-input__wrapper):hover {
  box-shadow: 0 0 0 1px rgba(99, 102, 241, 0.3) inset;
}

.search-input :deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1.5px var(--brand-primary) inset;
}

.search-count {
  font-size: 12px;
  font-weight: 500;
  color: var(--brand-primary);
  background: rgba(99, 102, 241, 0.1);
  padding: 4px 10px;
  border-radius: 999px;
  letter-spacing: 0.02em;
}

/* ---------- Sort pills ---------- */
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
    color var(--dur) var(--ease), border-color var(--dur) var(--ease);
}

.sort-pill:hover {
  border-color: rgba(99, 102, 241, 0.3);
  color: var(--brand-primary);
}

.sort-pill.is-active {
  background: var(--brand-primary);
  color: #ffffff;
  border-color: var(--brand-primary);
}

.sort-arrow {
  font-size: 11px;
}

/* ---------- Grid view ---------- */
.grid-stage {
  min-height: 200px;
}

.member-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: var(--sp-md);
}

.member-card {
  position: relative;
  background: #ffffff;
  border: 1px solid rgba(15, 23, 42, 0.06);
  border-radius: var(--radius-lg);
  overflow: hidden;
  transition: transform var(--dur) var(--ease),
    box-shadow var(--dur) var(--ease), border-color var(--dur) var(--ease);
}

.member-card:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-lg);
  border-color: rgba(99, 102, 241, 0.2);
}

.card-body {
  padding: var(--sp-md);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.card-name {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--ink-900);
  letter-spacing: -0.005em;
}

.card-position {
  margin: 0;
  font-size: 13px;
  color: var(--ink-500);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.card-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 4px;
  padding-top: var(--sp-sm);
  border-top: 1px solid rgba(15, 23, 42, 0.06);
}

.card-year,
.card-join {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--ink-500);
}

.card-year {
  color: var(--brand-primary);
  font-weight: 500;
}

.card-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--sp-sm);
  margin-top: 6px;
}

.card-admin-actions {
  margin-left: auto;
  display: inline-flex;
  gap: 4px;
}

/* ---------- Skeleton (initial-fetch placeholder) ---------- */
.member-card-skeleton {
  background: #ffffff;
  border: 1px solid rgba(15, 23, 42, 0.06);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.skel-photo {
  width: 100%;
  aspect-ratio: 1;
  background: linear-gradient(135deg, #eef2ff 0%, #e0e7ff 100%);
}

.skel-body {
  padding: var(--sp-md);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.skel-line {
  height: 12px;
  background: rgba(15, 23, 42, 0.06);
  border-radius: 4px;
}
.skel-line--name {
  width: 70%;
  height: 14px;
}
.skel-line--position {
  width: 55%;
}
.skel-line--meta {
  width: 80%;
  height: 10px;
  margin-top: 4px;
}

.skel-divider {
  height: 1px;
  background: rgba(15, 23, 42, 0.06);
  margin: 4px 0 2px;
}

.skel-actions {
  display: flex;
  gap: 6px;
  margin-top: 6px;
}

.skel-btn {
  height: 28px;
  width: 60px;
  background: rgba(15, 23, 42, 0.06);
  border-radius: var(--radius-sm);
}

/* Light-sweep shimmer — subtle but signals "loading" without being loud. */
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
    rgba(255, 255, 255, 0.5) 50%,
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

/* ---------- Empty state ---------- */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--sp-md);
  padding: 64px 24px;
  background: #ffffff;
  border: 1px dashed rgba(15, 23, 42, 0.12);
  border-radius: var(--radius-lg);
}

.empty-icon {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: rgba(99, 102, 241, 0.1);
  color: var(--brand-primary);
}

.empty-text {
  margin: 0;
  color: var(--ink-500);
  font-size: 14px;
}

/* ---------- Inline cell decorations (used by both table and grid) ---------- */
.year-chip {
  display: inline-flex;
  align-items: center;
  padding: 2px 10px;
  border-radius: 999px;
  background: rgba(99, 102, 241, 0.1);
  color: var(--brand-primary);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.02em;
}

/* ---------- Table skeleton (loading placeholder) ---------- */
.table-skeleton {
  background: #ffffff;
  border-radius: var(--radius-lg);
  border: 1px solid rgba(15, 23, 42, 0.06);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}

.ts-header {
  display: flex;
  height: 48px;
  background: var(--surface-1);
  border-bottom: 1px solid rgba(15, 23, 42, 0.08);
  align-items: center;
  padding: 0 12px;
  gap: 12px;
}

.ts-h-cell {
  height: 12px;
  background: rgba(15, 23, 42, 0.08);
  border-radius: 4px;
}

.ts-row {
  display: flex;
  align-items: center;
  padding: 14px 12px;
  gap: 12px;
  border-bottom: 1px solid rgba(15, 23, 42, 0.04);
}

.ts-row:last-child {
  border-bottom: 0;
}

.ts-photo-cell {
  width: 140px;
  display: flex;
  justify-content: center;
}

.ts-photo {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: linear-gradient(135deg, #eef2ff, #f3e8ff);
}

.ts-cell {
  display: flex;
  align-items: center;
}

.ts-line {
  height: 12px;
  background: rgba(15, 23, 42, 0.06);
  border-radius: 4px;
}

/* ---------- Table view ---------- */
.members-table {
  background: #ffffff;
  border-radius: var(--radius-lg);
  overflow: hidden;
  border: 1px solid rgba(15, 23, 42, 0.06);
  box-shadow: var(--shadow-sm);

  /* Drive Element Plus's table tokens to our palette so header / hover /
     borders read as part of the indigo system instead of EP defaults. */
  --el-table-header-bg-color: var(--surface-1);
  --el-table-header-text-color: var(--ink-700);
  --el-table-row-hover-bg-color: rgba(99, 102, 241, 0.05);
  --el-table-border-color: rgba(15, 23, 42, 0.06);
  --el-table-text-color: var(--ink-900);
  --el-table-tr-bg-color: #ffffff;
}

/* Indigo gradient strip on the left edge of a hovered row — matches the
   Home feature-card accent language. ::before lives on the first cell
   so it spans the entire row's vertical extent. */
.members-table :deep(.el-table__body tr.el-table__row .el-table__cell:first-child) {
  position: relative;
}

.members-table :deep(.el-table__body tr.el-table__row .el-table__cell:first-child)::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  background: linear-gradient(180deg, var(--brand-primary), var(--brand-accent));
  opacity: 0;
  transition: opacity var(--dur) var(--ease);
  pointer-events: none;
}

.members-table :deep(.el-table__body tr.el-table__row:hover .el-table__cell:first-child)::before {
  opacity: 1;
}

/* Header polish: stronger weight, tighter tracking, taller cells. */
.members-table :deep(.el-table__header th.el-table__cell) {
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: var(--ink-700);
  height: 48px;
  background: var(--surface-1);
  border-bottom: 1px solid rgba(15, 23, 42, 0.08);
}

/* Body cells get a hair more vertical breathing room than EP's default. */
.members-table :deep(.el-table__body td.el-table__cell) {
  padding: 14px 0;
  font-size: 13px;
}

/* Sort caret colors. Each .sort-caret is a 0×0 box rendered as a
   triangle via ONE colored border — the .ascending arrow is shaped by
   border-bottom, the .descending one by border-top. Only set the
   matching side here, otherwise both borders fill in and each caret
   renders as two stacked triangles (= 4 visible per column). */
.members-table :deep(.el-table__header th .caret-wrapper .ascending) {
  border-bottom-color: var(--ink-300);
}
.members-table :deep(.el-table__header th .caret-wrapper .descending) {
  border-top-color: var(--ink-300);
}
.members-table :deep(.el-table__header th.ascending .caret-wrapper .ascending) {
  border-bottom-color: var(--brand-primary);
}
.members-table :deep(.el-table__header th.descending .caret-wrapper .descending) {
  border-top-color: var(--brand-primary);
}

/* Empty inner placeholder gets the same treatment as the grid empty
   state so toggling views feels consistent. */
.members-table :deep(.el-table__empty-block) {
  min-height: 180px;
}

.table-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32px 16px;
}

.table-empty-text {
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

  /* Table columns sum to ~860 px which is wider than a phone viewport;
     let it scroll horizontally inside the card instead of overflowing the
     whole page. The table component already wraps its body in a scrollable
     element-plus inner, but we also need the wrapper itself not to clip. */
  .members-table {
    width: 100%;
    overflow-x: auto;
  }

  .members-table :deep(.el-table__body),
  .members-table :deep(.el-table__header) {
    min-width: 860px;
  }

  /* Stack the action buttons full-width on phones so each is easy to tap. */
  .actions {
    width: 100%;
    justify-content: flex-end;
  }

  .member-grid {
    grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
    gap: var(--sp-sm);
  }

  .card-body {
    padding: var(--sp-sm) var(--sp-md);
  }
}
</style>
