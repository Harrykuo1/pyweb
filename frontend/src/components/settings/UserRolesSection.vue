<script setup>
import { ElEmpty, ElOption, ElSelect, ElSkeleton, ElTag } from 'element-plus'

import { useUserRoles } from '../../composables/useUserRoles'

// Logic lives in the composable; this component is the presentation surface.
const { loading, users, savingId, displayName, changeRole } = useUserRoles()

// Every known role gets a tag — including viewer, which is display-only and
// never offered as a settable option below.
const ROLE_TAG = {
  admin: { type: 'danger', label: '管理員' },
  member: { type: '', label: '成員' },
  viewer: { type: 'info', label: '檢視者' },
}

function tagFor(role) {
  return ROLE_TAG[role] ?? { type: 'info', label: role }
}

defineExpose({ users })
</script>

<template>
  <div class="user-roles-section">
    <el-skeleton v-if="loading" :rows="4" animated />

    <el-empty v-else-if="!users.length" description="目前沒有使用者" />

    <ul v-else class="user-roles-section__list">
      <li
        v-for="u in users"
        :key="u.id"
        class="role-card"
        data-test="user-role-row"
      >
        <div class="role-card__identity">
          <span class="role-card__name">{{ displayName(u) }}</span>
          <span v-if="u.discord_username" class="role-card__handle">
            @{{ u.discord_username }}
          </span>
        </div>

        <el-tag
          :type="tagFor(u.role).type"
          class="role-card__tag"
          size="small"
          effect="light"
          round
        >
          {{ tagFor(u.role).label }}
        </el-tag>

        <!-- The legacy shared viewer account predates the role model and is
             managed under 帳號管理; it is display-only here. -->
        <span
          v-if="u.role === 'viewer'"
          class="role-card__legacy"
          :data-test="`role-legacy-${u.id}`"
        >
          唯讀帳號
        </span>
        <el-select
          v-else
          :model-value="u.role"
          class="role-card__select"
          placeholder="變更角色"
          :disabled="savingId === u.id"
          :data-test="`role-select-${u.id}`"
          @change="(value) => changeRole(u, value)"
        >
          <el-option label="管理員" value="admin" />
          <el-option label="成員" value="member" />
        </el-select>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.user-roles-section {
  display: flex;
  flex-direction: column;
}

.user-roles-section__list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* One card per account — identity on the left, current-role tag and the
   role selector pushed to the right. */
.role-card {
  display: flex;
  align-items: center;
  gap: 16px;
  background: var(--surface-0);
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: var(--radius-lg);
  padding: 16px 22px;
  box-shadow: var(--shadow-sm);
  transition:
    border-color var(--dur) var(--ease),
    box-shadow var(--dur) var(--ease);
}

.role-card:hover {
  border-color: rgba(99, 102, 241, 0.22);
  box-shadow: var(--shadow-md);
}

.role-card__identity {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  flex: 1;
}

.role-card__name {
  font-size: 15px;
  font-weight: 700;
  color: var(--ink-900);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.role-card__handle {
  font-size: 12px;
  color: var(--ink-500);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.role-card__tag {
  flex: 0 0 auto;
}

.role-card__select {
  flex: 0 0 auto;
  width: 140px;
}

.role-card__legacy {
  flex: 0 0 auto;
  width: 140px;
  text-align: center;
  font-size: 12px;
  color: var(--ink-400, #94a3b8);
}

@media (max-width: 640px) {
  .role-card {
    flex-wrap: wrap;
    gap: 10px;
    padding: 14px 16px;
  }

  .role-card__select {
    width: 100%;
  }
}
</style>
