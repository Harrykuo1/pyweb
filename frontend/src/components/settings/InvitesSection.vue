<script setup>
import { ElButton, ElSkeleton, ElTag } from 'element-plus'

import { useRegistrationInvites } from '../../composables/useRegistrationInvites'

// All data + logic lives in the composable; this component is the
// presentation surface.
const {
  loading,
  invites,
  creating,
  create,
  inviteUrl,
  status,
  statusLabel,
  copy,
} = useRegistrationInvites()

// Element Plus tag variant per invite status — presentation only, so it
// stays out of the composable.
const STATUS_TAG = { active: 'success', used: 'info', expired: 'warning' }

function formatExpiry(inv) {
  return new Date(inv.expires_at).toLocaleString('zh-TW')
}

defineExpose({ invites })
</script>

<template>
  <div class="invites-section">
    <header class="invites-section__header">
      <div class="invites-section__intro">
        <h4>註冊邀請連結</h4>
        <p>產生一次性連結，分享給新成員以 Discord 完成註冊。</p>
      </div>
      <el-button
        type="primary"
        :loading="creating"
        data-test="invite-create"
        @click="create"
      >
        產生新的邀請連結
      </el-button>
    </header>

    <el-skeleton v-if="loading" :rows="4" animated />

    <div
      v-else-if="!invites.length"
      class="invites-section__empty"
      data-test="invite-empty"
    >
      尚無邀請連結
    </div>

    <ul v-else class="invites-list">
      <li
        v-for="inv in invites"
        :key="inv.id"
        class="invite-row"
        data-test="invite-row"
      >
        <div class="invite-row__main">
          <code
            class="invite-row__link"
            :data-test="`invite-link-${inv.id}`"
            :title="inviteUrl(inv)"
          >
            {{ inviteUrl(inv) }}
          </code>
          <div class="invite-row__meta">
            <el-tag
              :type="STATUS_TAG[status(inv)]"
              size="small"
              effect="light"
              round
            >
              {{ statusLabel(inv) }}
            </el-tag>
            <span class="invite-row__expiry">
              到期 {{ formatExpiry(inv) }}
            </span>
          </div>
        </div>
        <el-button
          class="invite-row__copy"
          :disabled="status(inv) !== 'active'"
          :data-test="`invite-copy-${inv.id}`"
          @click="copy(inv)"
        >
          複製
        </el-button>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.invites-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* ---------- Header ---------- */
.invites-section__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.invites-section__intro h4 {
  margin: 0 0 4px;
  font-size: 15px;
  font-weight: 700;
  color: var(--ink-900);
}

.invites-section__intro p {
  margin: 0;
  font-size: 12px;
  color: var(--ink-500);
  line-height: 1.5;
}

/* ---------- Empty ---------- */
.invites-section__empty {
  padding: 28px 12px;
  text-align: center;
  font-size: 13px;
  color: var(--ink-500);
  background: var(--surface-0);
  border: 1px dashed rgba(15, 23, 42, 0.12);
  border-radius: var(--radius-md);
}

/* ---------- List ---------- */
.invites-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.invite-row {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 18px;
  background: var(--surface-0);
  border: 1px solid rgba(15, 23, 42, 0.06);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  transition:
    border-color var(--dur) var(--ease),
    box-shadow var(--dur) var(--ease);
}

.invite-row:hover {
  border-color: rgba(99, 102, 241, 0.22);
  box-shadow: var(--shadow-md);
}

.invite-row__main {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
  flex: 1;
}

.invite-row__link {
  font-family:
    ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, monospace;
  font-size: 12px;
  color: var(--ink-700);
  background: var(--surface-2);
  border: 1px solid rgba(15, 23, 42, 0.06);
  border-radius: var(--radius-sm);
  padding: 6px 10px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.invite-row__meta {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.invite-row__expiry {
  font-size: 12px;
  color: var(--ink-500);
}

.invite-row__copy {
  flex: 0 0 auto;
}

@media (max-width: 640px) {
  .invite-row {
    align-items: stretch;
    flex-direction: column;
  }

  .invite-row__copy {
    align-self: flex-end;
  }
}
</style>
