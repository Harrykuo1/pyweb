<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ElButton,
  ElIcon,
  ElInput,
  ElMessage,
  ElMessageBox,
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
  Menu,
  Plus,
  Refresh,
  School,
  Search,
  UserFilled,
} from '@element-plus/icons-vue'

import DeleteWithPasswordDialog from '../components/DeleteWithPasswordDialog.vue'
import MarqueeText from '../components/MarqueeText.vue'
import MemberFormDialog from '../components/members/MemberFormDialog.vue'
import MemberPhotoCell from '../components/members/MemberPhotoCell.vue'
import PhotoCropDialog from '../components/PhotoCropDialog.vue'
import ResumeViewerDialog from '../components/members/ResumeViewerDialog.vue'
import { storeToRefs } from 'pinia'

import { membersApi } from '../api/members'
import { authApi } from '../api/auth'
import { extractError } from '../utils/apiError'
import { useAuthStore } from '../stores/auth'
import { useMembersStore } from '../stores/members'
import { useDeepLinkFocus } from '../composables/useDeepLinkFocus'
import { useDeleteWithPassword } from '../composables/useDeleteWithPassword'
import { useMediaQuery } from '../composables/useMediaQuery'
import { useMemberFiltering } from '../composables/useMemberFiltering'
import { useMemberPhoto } from '../composables/useMemberPhoto'
import { useViewModePreference } from '../composables/useViewModePreference'

const auth = useAuthStore()

const route = useRoute()
const router = useRouter()

const membersStore = useMembersStore()
const { members, loading } = storeToRefs(membersStore)

const dialogOpen = ref(false)
const editingMember = ref(null)

const resumeOpen = ref(false)
const resumeMember = ref(null)

// View mode (cards vs spreadsheet), persisted across sessions.
const { viewMode, setViewMode } = useViewModePreference(
  'pyweb.members.viewMode',
)

// The view-mode toggle is hidden at the phone breakpoint (≤640px) because
// el-table at that width is unusable. Force grid mode there regardless of
// the user's stored desktop preference, so a viewer who last picked "list"
// on desktop still sees cards on their phone. Desktop choice is preserved.
const isPhone = useMediaQuery('(max-width: 640px)')

const effectiveViewMode = computed(() =>
  isPhone.value ? 'grid' : viewMode.value,
)

// ---------- Sort (drives the grid; el-table has its own header sort) ----------
const SORT_OPTIONS = [
  { key: 'joined_at', label: '入群時間' },
  { key: 'graduation_year', label: '畢業年份' },
  { key: 'real_name', label: '本名' },
  { key: 'institution', label: '學校／公司' },
]
// An admin previewing the member experience shouldn't see suspended
// members either — the backend already hides them from real non-admins,
// so this only covers the client-side preview toggle. Feed the filtered
// list into the search/sort helpers so both grid and table respect it.
const visibleMembers = computed(() => {
  if (!auth.isPreviewingAsMember) return members.value
  return members.value.filter((m) => m.account_status !== 'suspended')
})

// Client-side filtering + sorting (grid uses sortedMembers; the el-table
// list sorts itself off filteredMembers via the helpers below).
const {
  sortKey,
  sortOrder,
  toggleSort,
  searchQuery,
  filteredMembers,
  sortedMembers,
  memberCount,
  filteredCount,
} = useMemberFiltering(visibleMembers)

// Sort orders are restricted to two states so a click cycles asc → desc →
// asc instead of the el-table default asc → desc → none.
const SORT_ORDERS = ['ascending', 'descending']

// Element Plus's default string sort uses < which is byte-wise; localeCompare
// gives the right ordering for Chinese / mixed CJK strings.
const stringSort = (key) => (a, b) =>
  String(a[key] ?? '').localeCompare(String(b[key] ?? ''), 'zh-Hant')

async function loadMembers() {
  try {
    await membersStore.fetch()
  } catch (err) {
    ElMessage.error('載入成員清單失敗')
  }
}

// After a create/update/delete or photo change the cache would serve stale
// rows, so drop it before reloading authoritatively.
function reloadFresh() {
  membersStore.invalidate()
  return loadMembers()
}

function openCreate() {
  editingMember.value = null
  dialogOpen.value = true
}

function openEdit(member) {
  editingMember.value = { ...member }
  dialogOpen.value = true
}

// A card is self-editable by an admin (any card) or by the member who owns
// it (their own card only). Deleting the whole member stays admin-only.
function canEdit(member) {
  if (auth.isAdmin) return true
  return auth.myMemberId != null && member?.id === auth.myMemberId
}

// Short label for the member's account state. claimed / legacy carry no
// badge (they're the ordinary states); only pending and suspended do.
function statusBadge(member) {
  if (member.account_status === 'pending') return '尚未加入'
  if (member.account_status === 'suspended') return '已停權'
  return null
}

// Admin suspend / reactivate of the member's linked account. Reuses the
// accounts API (not membersApi) since it acts on the account, not the
// member profile.
async function setMemberActive(member, isActive) {
  try {
    await authApi.setUserActive(member.account_id, isActive)
    ElMessage.success(isActive ? '已復權' : '已停權')
    reloadFresh()
  } catch (err) {
    ElMessage.error(
      extractError(err, isActive ? '復權失敗，請稍後再試' : '停權失敗，請稍後再試'),
    )
  }
}

// Photo removal: admins re-authenticate via the password dialog; an owning
// member just confirms (no password) and deletes directly.
async function requestPhotoDelete(member) {
  if (auth.isActuallyAdmin) {
    onPhotoDeleteRequest(member)
    return
  }
  try {
    await ElMessageBox.confirm('將移除你的大頭照，確定嗎？', '移除照片', {
      type: 'warning',
      confirmButtonText: '移除',
      cancelButtonText: '取消',
    })
  } catch {
    return // user cancelled
  }
  try {
    await membersApi.deletePhoto(member.id)
    ElMessage.success('已移除照片')
    reloadFresh()
  } catch {
    ElMessage.error('移除失敗，請稍後再試')
  }
}

// Photo crop+upload and password-confirmed remove. Single dialogs are
// hoisted here (not per-card) so a 50-card grid doesn't carry 50 hidden
// el-dialogs. The names below map to the existing template bindings.
const {
  cropOpen: photoCropOpen,
  cropFile: photoCropFile,
  // eslint-disable-next-line no-unused-vars -- read by component tests via wrapper.vm
  cropTarget: photoCropTarget,
  uploadingMemberId: uploadingPhotoMemberId,
  onUploadRequest: onPhotoUploadRequest,
  onCropped: onPhotoCropped,
  deleteDialogOpen: photoDeleteDialogOpen,
  deleteTarget: photoDeleteTarget,
  deleteSubmitting: photoDeleteSubmitting,
  deleteError: photoDeleteError,
  onDeleteRequest: onPhotoDeleteRequest,
  onDeleteConfirm: onPhotoDeleteConfirm,
} = useMemberPhoto({ onChanged: () => reloadFresh() })

// ---------- Delete *member* with admin-password confirmation ----------
// Member delete (password-confirmed, shared with Jobs/Events). The
// original had no specific 404 copy, so keep 404 on the generic fallback.
const {
  dialogOpen: deleteDialogOpen,
  target: deleteTarget,
  submitting: deleteSubmitting,
  error: deleteError,
  open: askDeleteMember,
  confirm: handleDeleteConfirm,
} = useDeleteWithPassword({
  remove: (member, password) => membersApi.remove(member.id, password),
  messages: {
    404: '刪除失敗，請稍後再試',
    409: '此成員已啟用帳號，請至 設定 → 成員角色 停權',
  },
  onSuccess: (member) => {
    ElMessage.success(`已刪除「${member.real_name}」`)
    reloadFresh()
  },
})

function viewResume(member) {
  resumeMember.value = member
  resumeOpen.value = true
}

async function reloadAndRebindResume() {
  await reloadFresh()
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

// ---------- ?focus=<id> deep-link ----------
// Members has no detail dialog, so the deep-link entry from elsewhere
// (currently the home-page timeline feed) lands here as ?focus=<id>.
// We strip the query immediately so a refresh doesn't re-flash, then
// scroll the matching anchor into view + briefly highlight it. The URL
// shape is owned by membersApi.focusRoute() — see api/members.js.

const { consume: consumeFocusFromQuery } = useDeepLinkFocus({
  route,
  router,
  queryKey: 'focus',
  anchorClass: (id) => `member-anchor-${id}`,
  // Re-try after the cards actually render. The grid is gated on
  // !loading, and the store updates members and loading in separate
  // flushes, so watch both: the retry must fire when loading settles
  // (cards mount), not just when the list length changes.
  watchSource: () => [loading.value, members.value.length],
})

onMounted(() => {
  loadMembers()
  // Process any ?focus=<id> the page was opened with. Has to run after
  // mount because router.replace would no-op during setup.
  consumeFocusFromQuery()
})
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
          {{
            effectiveViewMode === 'grid'
              ? '點上方排序按鈕切換排序方向'
              : '點欄位標題可切換排序方向'
          }}
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
    <div v-if="effectiveViewMode === 'grid'" class="sort-row">
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
    <div v-if="effectiveViewMode === 'grid'" class="grid-stage">
      <!-- Skeleton placeholders cover the initial fetch so users see card
           shapes immediately instead of an EP spinner overlay. -->
      <div v-if="loading" class="member-grid" data-test="grid-skeleton">
        <div v-for="i in 8" :key="`skel-${i}`" class="member-card-skeleton">
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
          :class="['member-card', `member-anchor-${m.id}`]"
          data-test="member-card"
        >
          <MemberPhotoCell
            :member="m"
            variant="card"
            :can-manage="canEdit(m)"
            :uploading="uploadingPhotoMemberId === m.id"
            @request-upload="onPhotoUploadRequest"
            @request-delete="requestPhotoDelete"
          />

          <div class="card-body">
            <h3 class="card-name">{{ m.real_name }}</h3>
            <p class="card-institution">
              <MarqueeText :text="m.institution" />
            </p>
            <p class="card-position" :class="{ 'is-empty': !m.position }">
              <MarqueeText :text="m.position || '—'" />
            </p>

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
                <el-button size="small" :icon="Document" disabled
                  >履歷</el-button
                >
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

              <span
                v-if="canEdit(m) || auth.isActuallyAdmin"
                class="card-admin-actions"
              >
                <span
                  v-if="auth.isActuallyAdmin && statusBadge(m)"
                  :class="['status-badge', `status-badge--${m.account_status}`]"
                  :data-test="`member-status-${m.id}`"
                >
                  {{ statusBadge(m) }}
                </span>
                <el-button
                  v-if="canEdit(m)"
                  size="small"
                  plain
                  data-test="edit-button"
                  @click="openEdit(m)"
                >
                  編輯
                </el-button>
                <template v-if="auth.isActuallyAdmin">
                  <el-button
                    v-if="m.account_status === 'claimed'"
                    size="small"
                    type="warning"
                    plain
                    :data-test="`member-suspend-${m.id}`"
                    @click="setMemberActive(m, false)"
                  >
                    停權
                  </el-button>
                  <el-button
                    v-if="m.is_active === false"
                    size="small"
                    type="success"
                    plain
                    :data-test="`member-reactivate-${m.id}`"
                    @click="setMemberActive(m, true)"
                  >
                    復權
                  </el-button>
                  <el-button
                    v-if="
                      m.account_status !== 'claimed' &&
                      m.account_status !== 'suspended'
                    "
                    size="small"
                    type="danger"
                    plain
                    data-test="delete-button"
                    @click="askDeleteMember(m)"
                  >
                    刪除
                  </el-button>
                </template>
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
      v-if="effectiveViewMode === 'list' && loading"
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
      v-else-if="effectiveViewMode === 'list'"
      :data="filteredMembers"
      class="members-table"
      :default-sort="{ prop: 'joined_at', order: 'ascending' }"
      :row-class-name="({ row }) => `member-anchor-${row.id}`"
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
            :can-manage="canEdit(row)"
            :uploading="uploadingPhotoMemberId === row.id"
            @request-upload="onPhotoUploadRequest"
            @request-delete="requestPhotoDelete"
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
        prop="institution"
        label="學校／公司"
        sortable
        :sort-method="stringSort('institution')"
        :sort-orders="SORT_ORDERS"
        min-width="180"
      />
      <el-table-column
        prop="position"
        label="系所／職位"
        sortable
        :sort-method="stringSort('position')"
        :sort-orders="SORT_ORDERS"
        min-width="160"
      >
        <template #default="{ row }">
          <span v-if="row.position">{{ row.position }}</span>
          <span v-else class="muted-cell">—</span>
        </template>
      </el-table-column>
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
      <el-table-column
        v-if="auth.isActuallyAdmin || auth.myMemberId != null"
        label="操作"
        width="160"
        align="center"
      >
        <template #default="{ row }">
          <span
            v-if="auth.isActuallyAdmin && statusBadge(row)"
            :class="['status-badge', `status-badge--${row.account_status}`]"
            :data-test="`member-status-${row.id}`"
          >
            {{ statusBadge(row) }}
          </span>
          <el-tooltip v-if="canEdit(row)" content="編輯" placement="top">
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
          <template v-if="auth.isActuallyAdmin">
            <el-button
              v-if="row.account_status === 'claimed'"
              size="small"
              type="warning"
              plain
              :data-test="`member-suspend-${row.id}`"
              @click="setMemberActive(row, false)"
            >
              停權
            </el-button>
            <el-button
              v-if="row.is_active === false"
              size="small"
              type="success"
              plain
              :data-test="`member-reactivate-${row.id}`"
              @click="setMemberActive(row, true)"
            >
              復權
            </el-button>
            <el-button
              v-if="
                row.account_status !== 'claimed' &&
                row.account_status !== 'suspended'
              "
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
        </template>
      </el-table-column>
    </el-table>

    <MemberFormDialog
      v-model="dialogOpen"
      :member="editingMember"
      @saved="reloadFresh"
    />

    <ResumeViewerDialog
      v-model="resumeOpen"
      :member="resumeMember"
      :can-manage="canEdit(resumeMember)"
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
  background: linear-gradient(
    135deg,
    var(--brand-primary),
    var(--brand-accent)
  );
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
  transition:
    background-color var(--dur) var(--ease),
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
  transition:
    background-color var(--dur) var(--ease),
    color var(--dur) var(--ease),
    border-color var(--dur) var(--ease);
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
  /* Flex column so .card-body can absorb the leftover height in
     mixed-line-count rows, keeping the meta + action rows aligned
     across cards no matter how long each member's position text is. */
  display: flex;
  flex-direction: column;
  transition:
    transform var(--dur) var(--ease),
    box-shadow var(--dur) var(--ease),
    border-color var(--dur) var(--ease);
}

.member-card:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-lg);
  border-color: rgba(99, 102, 241, 0.2);
}

/* Deep-link arrival flash. Brief indigo halo + tinted background that
   fades back to default — long enough to draw the eye after a scroll,
   short enough to stay out of the user's way. Mirrored on table rows
   via :deep below so list-mode users get the same affordance. */
.member-card.is-flash {
  animation: member-flash 1.5s ease-out;
}

@keyframes member-flash {
  0% {
    box-shadow:
      0 0 0 4px rgba(99, 102, 241, 0.45),
      0 12px 28px rgba(99, 102, 241, 0.18);
    border-color: rgba(99, 102, 241, 0.4);
    background: rgba(99, 102, 241, 0.08);
  }
  100% {
    box-shadow: 0 0 0 0 rgba(99, 102, 241, 0);
    border-color: rgba(15, 23, 42, 0.06);
    background: #ffffff;
  }
}

/* Same flash but on the table row's cells, since el-table styles the
   <tr> via inner <td>s. The :deep is required because .is-flash lands
   on a row generated by el-table outside the scoped scope. */
:deep(tr.is-flash > td) {
  animation: member-row-flash 1.5s ease-out;
}

@keyframes member-row-flash {
  0% {
    background: rgba(99, 102, 241, 0.16);
  }
  100% {
    background: transparent;
  }
}

.card-body {
  padding: var(--sp-md);
  display: flex;
  flex-direction: column;
  gap: 6px;
  /* Fill the leftover card height so .card-meta's margin-top:auto has
     room to push the meta + action rows down to the bottom edge. */
  flex: 1;
}

.card-name {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--ink-900);
  letter-spacing: -0.005em;
}

.card-institution {
  margin: 0;
  font-size: 13px;
  font-weight: 500;
  color: var(--ink-700);
  line-height: 1.4;
  min-width: 0;
}

.card-position {
  margin: 0;
  font-size: 12px;
  color: var(--ink-500);
  line-height: 1.4;
  min-width: 0;
}

.card-position.is-empty {
  color: var(--ink-300);
}

.card-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  /* auto pushes the meta row (and the action row that follows) to the
     bottom of .card-body, so cards with 1-line vs 2-line positions
     line up their footer chrome on the same baseline. */
  margin-top: auto;
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

.card-join {
  margin-left: auto;
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
  align-items: center;
  gap: 4px;
}

/* Account-state badge: pending (尚未加入) reads as neutral/amber, suspended
   (已停權) as a muted danger tone. Shown next to the admin action buttons. */
.status-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.02em;
  white-space: nowrap;
}

.status-badge--pending {
  background: rgba(234, 179, 8, 0.14);
  color: #a16207;
}

.status-badge--suspended {
  background: rgba(239, 68, 68, 0.12);
  color: #b91c1c;
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
.members-table
  :deep(.el-table__body tr.el-table__row .el-table__cell:first-child) {
  position: relative;
}

.members-table
  :deep(.el-table__body tr.el-table__row .el-table__cell:first-child)::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  background: linear-gradient(
    180deg,
    var(--brand-primary),
    var(--brand-accent)
  );
  opacity: 0;
  transition: opacity var(--dur) var(--ease);
  pointer-events: none;
}

.members-table
  :deep(
    .el-table__body tr.el-table__row:hover .el-table__cell:first-child
  )::before {
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
.members-table
  :deep(.el-table__header th.descending .caret-wrapper .descending) {
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

/* Tablet portrait + phone: drop the actions row to a full-width second
   line so the header text isn't squeezed. */
@media (max-width: 1024px) {
  .actions {
    width: 100%;
    justify-content: flex-end;
  }
}

@media (max-width: 640px) {
  .title {
    font-size: 20px;
  }

  .title-icon {
    width: 32px;
    height: 32px;
  }

  /* Sort pills are themselves tappable controls — the prose hint above
     them is redundant on a small screen and just steals a row. */
  .subtitle {
    display: none;
  }

  /* Card / table toggle is desktop-only: the table view at phone width
     is unusable. Hide the toggle and force grid mode via
     effectiveViewMode in the template, so a viewer who last picked
     "list" on desktop still sees cards on their phone. */
  .view-toggle {
    display: none;
  }

  /* Search takes its own full-width row so the input isn't squeezed
     against the view toggle. Refresh / add buttons wrap to the next
     row naturally via .actions's flex-wrap. */
  .search-wrap {
    flex: 1 1 100%;
  }

  .search-input {
    width: 100%;
  }

  /* Compact sort row: drop the "排序" label and tighten pills so the
     four sort options fit on one or two cleaner lines. */
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

  .member-grid {
    grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
    gap: var(--sp-sm);
  }

  .card-body {
    padding: var(--sp-sm) var(--sp-md);
  }

  /* At ~155-180 px card width the year-icon row and date-icon row do
     not fit on one line; stacking them vertically (and dropping the
     margin-left:auto that would otherwise right-align the second row)
     keeps both flush-left and avoids the disconnected split. */
  .card-meta {
    flex-direction: column;
    align-items: flex-start;
    gap: 4px;
  }

  .card-join {
    margin-left: 0;
  }

  /* Same idea for the action buttons: when they wrap, don't shove the
     admin actions to the right edge of the next row — left-align so
     all three buttons read as one group. */
  .card-admin-actions {
    margin-left: 0;
  }
}
</style>
