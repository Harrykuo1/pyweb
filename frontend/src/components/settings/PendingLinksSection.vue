<script setup>
import { ElButton, ElEmpty, ElOption, ElSelect, ElSkeleton } from 'element-plus'
import { Close } from '@element-plus/icons-vue'

import { usePendingLinks } from '../../composables/usePendingLinks'

// The pending-link data and resolve flow live in the composable; this is
// presentation only.
const {
  loading,
  links,
  selectableMembers,
  picked,
  resolvingId,
  displayName,
  memberLabel,
  resolve,
  dismiss,
} = usePendingLinks()
</script>

<template>
  <div class="pending-links-section">
    <el-skeleton v-if="loading" :rows="4" animated />

    <el-empty
      v-else-if="!links.length"
      description="目前沒有待處理的 Discord 連結"
      :image-size="80"
    />

    <ul v-else class="pending-links-section__list">
      <li
        v-for="link in links"
        :key="link.discord_id"
        class="pending-row"
        data-test="pending-row"
      >
        <div class="pending-row__identity">
          <span class="pending-row__name">{{ displayName(link) }}</span>
          <code class="pending-row__id">{{ link.discord_id }}</code>
          <span class="pending-row__seen">
            首次登入
            {{ new Date(link.first_seen_at).toLocaleString('zh-TW') }}
          </span>
        </div>

        <div class="pending-row__action">
          <el-select
            v-model="picked[link.discord_id]"
            :data-test="`pending-member-select-${link.discord_id}`"
            class="pending-row__select"
            filterable
            placeholder="選擇成員"
          >
            <el-option
              v-for="m in selectableMembers"
              :key="m.id"
              :value="m.id"
              :label="memberLabel(m)"
            />
          </el-select>

          <el-button
            type="primary"
            :data-test="`pending-resolve-${link.discord_id}`"
            :loading="resolvingId === link.discord_id"
            @click="resolve(link)"
          >
            連結
          </el-button>

          <el-button
            :icon="Close"
            circle
            plain
            :data-test="`pending-dismiss-${link.discord_id}`"
            :disabled="resolvingId === link.discord_id"
            title="忽略此請求"
            aria-label="忽略此請求"
            @click="dismiss(link)"
          />
        </div>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.pending-links-section {
  display: flex;
  flex-direction: column;
}

.pending-links-section__list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* ---------- One card per pending link ---------- */
.pending-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  background: var(--surface-0);
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: var(--radius-lg);
  padding: 18px 22px;
  box-shadow: var(--shadow-sm);
  transition:
    border-color var(--dur) var(--ease),
    box-shadow var(--dur) var(--ease);
}

.pending-row:hover {
  border-color: rgba(99, 102, 241, 0.22);
  box-shadow: var(--shadow-md);
}

.pending-row__identity {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.pending-row__name {
  font-size: 15px;
  font-weight: 700;
  color: var(--ink-900);
}

.pending-row__id {
  font-family: var(--font-mono, ui-monospace, monospace);
  font-size: 12px;
  color: var(--ink-500);
  background: var(--surface-2);
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: var(--radius-sm);
  padding: 2px 8px;
  align-self: flex-start;
}

.pending-row__seen {
  font-size: 12px;
  color: var(--ink-500);
}

.pending-row__action {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.pending-row__select {
  min-width: 220px;
}

/* Element Plus injects margin-left:12px on sibling buttons by default.
   The row uses flex `gap`, so neutralize the margin to avoid doubling. */
.pending-row__action :deep(.el-button + .el-button) {
  margin-left: 0;
}

@media (max-width: 640px) {
  .pending-row {
    align-items: stretch;
  }

  .pending-row__action {
    width: 100%;
  }

  .pending-row__select {
    flex: 1;
    min-width: 0;
  }
}
</style>
