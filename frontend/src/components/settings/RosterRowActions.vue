<script setup>
import { computed } from 'vue'
import {
  ElButton,
  ElDropdown,
  ElDropdownItem,
  ElDropdownMenu,
  ElIcon,
  ElTag,
} from 'element-plus'
import { ArrowDown } from '@element-plus/icons-vue'

// The interactive cluster of a roster row — the role tag/switcher plus the
// lifecycle buttons. Extracted so it can be reused verbatim by both the
// desktop table column and the narrow-screen card layout. Purely
// presentational: it decides which controls a row's account_status/role
// warrant and emits semantic events; the parent owns confirms and API calls.
const props = defineProps({
  row: { type: Object, required: true },
  savingId: { type: [Number, null], default: null },
})
const emit = defineEmits([
  'role-command',
  'suspend',
  'reactivate',
  'edit',
  'delete',
])

const ROLE_TAG = {
  admin: { type: 'danger', label: '管理員' },
  member: { type: '', label: '成員' },
  viewer: { type: 'info', label: '檢視者' },
}
function tagFor(role) {
  return ROLE_TAG[role] ?? { type: 'info', label: role }
}

const saving = computed(
  () => props.savingId != null && props.savingId === props.row.account_id,
)
</script>

<template>
  <div class="roster-actions">
    <!-- claimed or pending: the tag itself is the role switcher, so an admin
         can (pre-)assign a role even before the member has logged in -->
    <el-dropdown
      v-if="
        (row.account_status === 'claimed' ||
          row.account_status === 'pending') &&
        row.role
      "
      trigger="click"
      :disabled="saving"
      :data-test="`roster-role-trigger-${row.id}`"
      @command="(role) => emit('role-command', role)"
    >
      <span class="roster-role-trigger" role="button" tabindex="0">
        <el-tag :type="tagFor(row.role).type" size="small" effect="light" round>
          {{ tagFor(row.role).label }}
        </el-tag>
        <el-icon class="roster-role-trigger__caret"><ArrowDown /></el-icon>
      </span>
      <template #dropdown>
        <el-dropdown-menu>
          <el-dropdown-item
            command="admin"
            :disabled="row.role === 'admin'"
            :data-test="`roster-role-admin-${row.id}`"
          >
            管理員
          </el-dropdown-item>
          <el-dropdown-item
            command="member"
            :disabled="row.role === 'member'"
            :data-test="`roster-role-member-${row.id}`"
          >
            成員
          </el-dropdown-item>
        </el-dropdown-menu>
      </template>
    </el-dropdown>
    <el-tag
      v-else-if="row.role"
      :type="tagFor(row.role).type"
      size="small"
      effect="light"
      round
    >
      {{ tagFor(row.role).label }}
    </el-tag>
    <span v-else class="roster-muted">—</span>

    <!-- edit is available on every row and always sits first -->
    <el-button
      size="small"
      plain
      :data-test="`roster-edit-${row.id}`"
      @click="emit('edit')"
    >
      編輯
    </el-button>

    <!-- lifecycle action, always last so 停權 / 復權 / 刪除 line up -->
    <!-- claimed: suspend (non-admin only) -->
    <template v-if="row.account_status === 'claimed'">
      <el-button
        v-if="row.role !== 'admin'"
        size="small"
        type="warning"
        plain
        :loading="saving"
        :data-test="`roster-suspend-${row.id}`"
        @click="emit('suspend')"
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
        :loading="saving"
        :data-test="`roster-reactivate-${row.id}`"
        @click="emit('reactivate')"
      >
        復權
      </el-button>
    </template>

    <!-- pending / legacy: no linked active account, so delete is safe -->
    <el-button
      v-else-if="
        row.account_status === 'pending' || row.account_status === 'legacy'
      "
      size="small"
      type="danger"
      plain
      :data-test="`roster-delete-${row.id}`"
      @click="emit('delete')"
    >
      刪除
    </el-button>
  </div>
</template>

<style scoped>
.roster-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.roster-role-trigger {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  cursor: pointer;
  outline: none;
}

.roster-role-trigger__caret {
  font-size: 12px;
  color: var(--ink-400);
}

.roster-muted {
  color: var(--ink-400);
}
</style>
