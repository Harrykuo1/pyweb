<script setup>
import {
  ElButton,
  ElEmpty,
  ElMessageBox,
  ElOption,
  ElSelect,
  ElSkeleton,
  ElTable,
  ElTableColumn,
  ElTag,
} from 'element-plus'
import { Link, Plus } from '@element-plus/icons-vue'
import { ref } from 'vue'

import DeleteWithPasswordDialog from '../DeleteWithPasswordDialog.vue'
import MemberFormDialog from '../members/MemberFormDialog.vue'
import MemberPhotoCell from '../members/MemberPhotoCell.vue'

import { membersApi } from '../../api/members'
import { useDeleteWithPassword } from '../../composables/useDeleteWithPassword'
import { useMemberRoster } from '../../composables/useMemberRoster'

const emit = defineEmits(['generate-invite'])

// Data + mutations live in the composable; this component is the presentation
// surface plus the confirm-dialog / form-dialog wiring.
const {
  loading,
  filteredRows,
  statusFilter,
  counts,
  savingId,
  reload,
  changeRole,
  setActive,
  displayName,
} = useMemberRoster()

const FILTERS = [
  { key: 'all', label: '全部' },
  { key: 'claimed', label: '已加入' },
  { key: 'pending', label: '尚未加入' },
  { key: 'suspended', label: '已停權' },
]

// Every known role gets a tag; viewer is display-only and never settable.
const ROLE_TAG = {
  admin: { type: 'danger', label: '管理員' },
  member: { type: '', label: '成員' },
  viewer: { type: 'info', label: '檢視者' },
}
function tagFor(role) {
  return ROLE_TAG[role] ?? { type: 'info', label: role }
}

// Account-state badge per row. claimed/legacy read as 已加入 / 舊資料;
// pending and suspended get their own explicit label.
const STATUS_BADGE = {
  claimed: { label: '已加入', class: 'is-claimed' },
  pending: { label: '尚未加入', class: 'is-pending' },
  suspended: { label: '已停權', class: 'is-suspended' },
  legacy: { label: '舊資料', class: 'is-legacy' },
}
function badgeFor(status) {
  return STATUS_BADGE[status] ?? { label: status, class: '' }
}

// ---- member form (新增 / 編輯) ----
const formOpen = ref(false)
const editingMember = ref(null)

function openAdd() {
  editingMember.value = null
  formOpen.value = true
}
function openEdit(member) {
  editingMember.value = { ...member }
  formOpen.value = true
}

// ---- change role: confirm-on-promote + remount-on-cancel ----
// selectResetKey is bumped on a cancelled promote to force the select to
// remount and snap its displayed value back to the row's unchanged role
// (it binds :model-value one-way, so a remount re-reads row.role).
const selectResetKey = ref(0)

async function onRoleChange(member, value) {
  if (value === member.role) return
  if (value === 'admin') {
    try {
      await ElMessageBox.confirm(
        `確定要將「${displayName(member)}」設為管理員嗎？管理員擁有完整權限。`,
        '設為管理員',
        {
          type: 'warning',
          confirmButtonText: '設為管理員',
          cancelButtonText: '取消',
        },
      )
    } catch {
      selectResetKey.value += 1
      return
    }
  }
  changeRole(member, value)
}

// ---- suspend: confirm before it fires (logs the account out immediately) ----
async function onSuspend(member) {
  try {
    await ElMessageBox.confirm(
      `確定要停權「${displayName(member)}」嗎？停權後對方將立即被登出且無法再登入，直到你復權。`,
      '停權帳號',
      { type: 'warning', confirmButtonText: '停權', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  setActive(member, false)
}

// ---- delete pending / legacy member (admin password) ----
const {
  dialogOpen: deleteDialogOpen,
  target: deleteTarget,
  submitting: deleteSubmitting,
  error: deleteError,
  open: askDelete,
  confirm: handleDeleteConfirm,
} = useDeleteWithPassword({
  remove: (member, password) => membersApi.remove(member.id, password),
  messages: { 409: '此成員已啟用帳號，請先停權後再刪除' },
  onSuccess: () => reload(),
})
</script>

<template>
  <div class="member-roster">
    <div class="member-roster__toolbar">
      <div class="member-roster__filters" role="tablist" aria-label="狀態篩選">
        <button
          v-for="f in FILTERS"
          :key="f.key"
          type="button"
          :class="['roster-filter', { 'is-active': statusFilter === f.key }]"
          :data-test="`roster-filter-${f.key}`"
          @click="statusFilter = f.key"
        >
          {{ f.label }}
          <span class="roster-filter__count">{{ counts[f.key] }}</span>
        </button>
      </div>

      <div class="member-roster__actions">
        <el-button
          type="primary"
          :icon="Plus"
          data-test="roster-add-member"
          @click="openAdd"
        >
          新增成員
        </el-button>
        <el-button
          :icon="Link"
          data-test="roster-generate-invite"
          @click="emit('generate-invite')"
        >
          產生邀請連結
        </el-button>
      </div>
    </div>

    <el-skeleton v-if="loading" :rows="5" animated />

    <el-empty v-else-if="!filteredRows.length" description="沒有符合的成員" />

    <el-table v-else :data="filteredRows" class="member-roster__table">
      <el-table-column label="照片" width="80">
        <template #default="{ row }">
          <MemberPhotoCell :member="row" />
        </template>
      </el-table-column>

      <el-table-column label="本名" min-width="110">
        <template #default="{ row }">
          <span class="roster-name">{{ row.real_name }}</span>
        </template>
      </el-table-column>

      <el-table-column label="Discord" min-width="130">
        <template #default="{ row }">
          <span v-if="row.account_discord_username" class="roster-handle">
            @{{ row.account_discord_username }}
          </span>
          <span v-else class="roster-muted">—</span>
        </template>
      </el-table-column>

      <el-table-column label="畢業年" width="90" align="center">
        <template #default="{ row }">{{ row.graduation_year }}</template>
      </el-table-column>

      <el-table-column label="學校職位" min-width="160">
        <template #default="{ row }">
          <div class="roster-inst">
            <span class="roster-inst__school">{{ row.institution }}</span>
            <span v-if="row.position" class="roster-muted">
              {{ row.position }}
            </span>
          </div>
        </template>
      </el-table-column>

      <el-table-column label="角色" width="100" align="center">
        <template #default="{ row }">
          <el-tag
            v-if="row.role"
            :type="tagFor(row.role).type"
            size="small"
            effect="light"
            round
          >
            {{ tagFor(row.role).label }}
          </el-tag>
          <span v-else class="roster-muted">—</span>
        </template>
      </el-table-column>

      <el-table-column label="狀態" width="100" align="center">
        <template #default="{ row }">
          <span
            :class="['roster-status', badgeFor(row.account_status).class]"
            :data-test="`roster-status-${row.id}`"
          >
            {{ badgeFor(row.account_status).label }}
          </span>
        </template>
      </el-table-column>

      <el-table-column label="操作" min-width="230">
        <template #default="{ row }">
          <div class="roster-row-actions">
            <!-- claimed: role select + suspend (non-admin only) -->
            <template v-if="row.account_status === 'claimed'">
              <el-select
                :key="selectResetKey"
                :model-value="row.role"
                size="small"
                class="roster-role-select"
                :disabled="savingId === row.account_id"
                :data-test="`roster-role-${row.id}`"
                @change="(value) => onRoleChange(row, value)"
              >
                <el-option label="管理員" value="admin" />
                <el-option label="成員" value="member" />
              </el-select>
              <el-button
                v-if="row.role !== 'admin'"
                size="small"
                type="warning"
                plain
                :loading="savingId === row.account_id"
                :data-test="`roster-suspend-${row.id}`"
                @click="onSuspend(row)"
              >
                停權
              </el-button>
            </template>

            <!-- suspended: reactivate -->
            <template v-else-if="row.account_status === 'suspended'">
              <el-button
                size="small"
                type="success"
                plain
                :loading="savingId === row.account_id"
                :data-test="`roster-reactivate-${row.id}`"
                @click="setActive(row, true)"
              >
                復權
              </el-button>
            </template>

            <!-- edit is available on every row -->
            <el-button
              size="small"
              plain
              :data-test="`roster-edit-${row.id}`"
              @click="openEdit(row)"
            >
              編輯
            </el-button>

            <!-- pending / legacy: no linked active account, so delete is safe -->
            <el-button
              v-if="
                row.account_status === 'pending' ||
                row.account_status === 'legacy'
              "
              size="small"
              type="danger"
              plain
              :data-test="`roster-delete-${row.id}`"
              @click="askDelete(row)"
            >
              刪除
            </el-button>
          </div>
        </template>
      </el-table-column>
    </el-table>

    <MemberFormDialog
      v-model="formOpen"
      :member="editingMember"
      @saved="reload"
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
  </div>
</template>

<style scoped>
.member-roster {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* ---------- Toolbar: status filters (left) + actions (right) ---------- */
.member-roster__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.member-roster__filters {
  display: inline-flex;
  gap: 6px;
  flex-wrap: wrap;
}

.roster-filter {
  border: 1px solid rgba(15, 23, 42, 0.08);
  background: var(--surface-0);
  color: var(--ink-700);
  padding: 6px 14px;
  font-size: 13px;
  font-weight: 500;
  border-radius: 999px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  transition:
    background-color var(--dur) var(--ease),
    color var(--dur) var(--ease),
    border-color var(--dur) var(--ease);
}

.roster-filter:hover {
  border-color: rgba(99, 102, 241, 0.3);
  color: var(--brand-primary);
}

.roster-filter.is-active {
  background: var(--brand-primary);
  color: #ffffff;
  border-color: var(--brand-primary);
}

.roster-filter__count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 20px;
  height: 18px;
  padding: 0 6px;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.06);
  color: inherit;
  font-size: 11px;
  font-weight: 700;
}

.roster-filter.is-active .roster-filter__count {
  background: rgba(255, 255, 255, 0.24);
}

.member-roster__actions {
  display: inline-flex;
  gap: 8px;
}

.member-roster__actions :deep(.el-button + .el-button) {
  margin-left: 0;
}

/* ---------- Table cells ---------- */
.member-roster__table {
  background: var(--surface-0);
  border-radius: var(--radius-lg);
  overflow: hidden;
  border: 1px solid rgba(15, 23, 42, 0.06);
  box-shadow: var(--shadow-sm);

  --el-table-header-bg-color: var(--surface-1);
  --el-table-header-text-color: var(--ink-700);
  --el-table-row-hover-bg-color: rgba(99, 102, 241, 0.05);
  --el-table-border-color: rgba(15, 23, 42, 0.06);
  --el-table-text-color: var(--ink-900);
  --el-table-tr-bg-color: var(--surface-0);
}

.roster-name {
  font-weight: 600;
  color: var(--ink-900);
}

.roster-handle {
  font-size: 12px;
  color: var(--ink-500);
}

.roster-inst {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.roster-inst__school {
  font-size: 13px;
  color: var(--ink-700);
}

.roster-muted {
  color: var(--ink-400, #94a3b8);
  font-size: 12px;
}

/* ---------- Status badge ---------- */
.roster-status {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.02em;
  white-space: nowrap;
}

.roster-status.is-claimed {
  background: rgba(34, 197, 94, 0.12);
  color: #15803d;
}

.roster-status.is-pending {
  background: rgba(234, 179, 8, 0.14);
  color: #a16207;
}

.roster-status.is-suspended {
  background: rgba(239, 68, 68, 0.12);
  color: #b91c1c;
}

.roster-status.is-legacy {
  background: rgba(15, 23, 42, 0.06);
  color: var(--ink-500);
}

/* ---------- Row actions ---------- */
.roster-row-actions {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.roster-row-actions :deep(.el-button + .el-button) {
  margin-left: 0;
}

.roster-role-select {
  width: 110px;
}

@media (max-width: 640px) {
  .member-roster__toolbar {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
