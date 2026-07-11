<script setup>
import {
  ElButton,
  ElEmpty,
  ElMessageBox,
  ElSkeleton,
  ElTable,
  ElTableColumn,
} from 'element-plus'
import { Link, Plus } from '@element-plus/icons-vue'
import { onBeforeUnmount, onMounted, ref } from 'vue'

import DeleteWithPasswordDialog from '../DeleteWithPasswordDialog.vue'
import MemberFormDialog from '../members/MemberFormDialog.vue'
import MemberPhotoCell from '../members/MemberPhotoCell.vue'
import RosterRowActions from './RosterRowActions.vue'

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

// The 7-column table only stays readable when the content area is wide
// enough for every column to fit; below that it re-renders as a card list.
// The threshold sits above the widths where the table would otherwise need
// a horizontal scroll (which is where el-table's fixed columns misbehave),
// so cards cover phones, tablets and small laptops.
const isNarrow = ref(false)
let _mql = null
function _syncNarrow(e) {
  isNarrow.value = e.matches
}
onMounted(() => {
  _mql = window.matchMedia('(max-width: 1199px)')
  isNarrow.value = _mql.matches
  _mql.addEventListener('change', _syncNarrow)
})
onBeforeUnmount(() => _mql?.removeEventListener('change', _syncNarrow))

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

// ---- change role from the role-tag dropdown: confirm-on-promote ----
// The tag always renders from row.role, which changeRole only patches on
// success — so a cancelled confirm or a rejected change needs no reset.
async function onRoleCommand(member, role) {
  if (role === member.role) return
  if (role === 'admin') {
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
      return
    }
  }
  changeRole(member, role)
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
  // Delete is offered only for pending / legacy rows, so the "active account"
  // 409 can never fire here — the only reachable 409 is a member still
  // referenced by job records.
  messages: { 409: '此成員已有關聯的求職記錄，無法刪除' },
  onSuccess: () => reload(),
})
</script>

<template>
  <div class="member-roster">
    <div class="member-roster__toolbar">
      <div class="member-roster__filters" role="group" aria-label="狀態篩選">
        <button
          v-for="f in FILTERS"
          :key="f.key"
          type="button"
          :class="['roster-filter', { 'is-active': statusFilter === f.key }]"
          :aria-pressed="statusFilter === f.key"
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

    <template v-else>
      <!-- Wide screens only (see isNarrow): rendered only when the content
           area fits all columns, so every column expands to fill and nothing
           needs a horizontal scroll. -->
      <el-table
        v-if="!isNarrow"
        :data="filteredRows"
        class="member-roster__table"
      >
        <el-table-column label="照片" width="72">
          <template #default="{ row }">
            <MemberPhotoCell :member="row" />
          </template>
        </el-table-column>

        <el-table-column label="本名" min-width="100">
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

        <el-table-column label="畢業年" width="88" align="center">
          <template #default="{ row }">{{ row.graduation_year }}</template>
        </el-table-column>

        <el-table-column label="學校職位" min-width="150">
          <template #default="{ row }">
            <div class="roster-inst">
              <span class="roster-inst__school">{{ row.institution }}</span>
              <span v-if="row.position" class="roster-muted">
                {{ row.position }}
              </span>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="狀態" width="96" align="center">
          <template #default="{ row }">
            <span
              :class="['roster-status', badgeFor(row.account_status).class]"
              :data-test="`roster-status-${row.id}`"
            >
              {{ badgeFor(row.account_status).label }}
            </span>
          </template>
        </el-table-column>

        <el-table-column label="角色 / 操作" min-width="220">
          <template #default="{ row }">
            <RosterRowActions
              :row="row"
              :saving-id="savingId"
              @role-command="(role) => onRoleCommand(row, role)"
              @suspend="onSuspend(row)"
              @reactivate="setActive(row, true)"
              @edit="openEdit(row)"
              @delete="askDelete(row)"
            />
          </template>
        </el-table-column>
      </el-table>

      <!-- Narrow screens: one card per member — no horizontal scroll. -->
      <ul v-else class="roster-cards" data-test="roster-cards">
        <li v-for="row in filteredRows" :key="row.id" class="roster-card">
          <div class="roster-card__head">
            <MemberPhotoCell :member="row" />
            <div class="roster-card__ident">
              <span class="roster-name">{{ row.real_name }}</span>
              <span
                v-if="row.account_discord_username"
                class="roster-handle"
              >
                @{{ row.account_discord_username }}
              </span>
            </div>
            <span
              :class="['roster-status', badgeFor(row.account_status).class]"
              :data-test="`roster-status-${row.id}`"
            >
              {{ badgeFor(row.account_status).label }}
            </span>
          </div>

          <dl class="roster-card__meta">
            <div>
              <dt>畢業年</dt>
              <dd>{{ row.graduation_year }}</dd>
            </div>
            <div>
              <dt>學校職位</dt>
              <dd>
                {{ row.institution
                }}<span v-if="row.position" class="roster-muted">
                  · {{ row.position }}</span
                >
              </dd>
            </div>
          </dl>

          <RosterRowActions
            :row="row"
            :saving-id="savingId"
            @role-command="(role) => onRoleCommand(row, role)"
            @suspend="onSuspend(row)"
            @reactivate="setActive(row, true)"
            @edit="openEdit(row)"
            @delete="askDelete(row)"
          />
        </li>
      </ul>
    </template>

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

/* ---------- Narrow-screen card layout ---------- */
.roster-cards {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.roster-card {
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: var(--radius-lg);
  background: var(--surface-0);
  box-shadow: var(--shadow-sm);
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.roster-card__head {
  display: flex;
  align-items: center;
  gap: 12px;
}

.roster-card__ident {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  flex: 1;
}

.roster-card__meta {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px 12px;
  margin: 0;
}

.roster-card__meta > div {
  min-width: 0;
}

.roster-card__meta dt {
  font-size: 11px;
  color: var(--ink-400);
  margin-bottom: 2px;
}

.roster-card__meta dd {
  margin: 0;
  font-size: 13px;
  color: var(--ink-700);
  word-break: break-word;
}

@media (max-width: 640px) {
  .member-roster__toolbar {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
