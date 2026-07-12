<script setup>
import { ElButton, ElInput, ElSkeleton } from 'element-plus'

import { useGuildConfig } from '../../composables/useGuildConfig'

// The config-form logic lives in the composable; this is presentation.
const { loading, saving, guildId, dirty, valid, save, reset } = useGuildConfig()
</script>

<template>
  <div class="guild-config-section">
    <el-skeleton v-if="loading" :rows="4" animated />

    <form
      v-else
      class="guild-config-section__form"
      data-test="guild-form"
      @submit.prevent="save"
    >
      <article class="guild-card">
        <header class="guild-card__header">
          <h4>Discord 群組 ID</h4>
          <p>
            驗證登入者是否屬於此 Discord 群組（伺服器）。填入群組的數字
            ID（17–20 位）。
          </p>
        </header>

        <div class="guild-card__field">
          <el-input
            v-model="guildId"
            data-test="guild-input"
            placeholder="例如：123456789012345678"
          />
          <span
            v-if="guildId && !valid"
            class="guild-card__hint"
            data-test="guild-hint"
          >
            必須是 17–20 位數字
          </span>
        </div>
      </article>

      <footer class="guild-config-section__actions">
        <el-button
          :disabled="!dirty || saving"
          data-test="guild-reset"
          @click="reset"
        >
          還原
        </el-button>
        <el-button
          type="primary"
          :loading="saving"
          :disabled="!dirty || !valid"
          data-test="guild-save"
          @click="save"
        >
          儲存
        </el-button>
      </footer>
    </form>
  </div>
</template>

<style scoped>
.guild-config-section {
  display: flex;
  flex-direction: column;
}

.guild-config-section__form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

/* ---------- Config card ---------- */
.guild-card {
  background: var(--surface-0);
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: var(--radius-lg);
  padding: 20px 22px;
  box-shadow: var(--shadow-sm);
  transition:
    border-color var(--dur) var(--ease),
    box-shadow var(--dur) var(--ease);
}

.guild-card:hover {
  border-color: rgba(99, 102, 241, 0.22);
  box-shadow: var(--shadow-md);
}

.guild-card__header {
  margin: 0 0 16px;
}

.guild-card__header h4 {
  margin: 0 0 4px;
  font-size: 15px;
  font-weight: 700;
  color: var(--ink-900);
}

.guild-card__header p {
  margin: 0;
  font-size: 12px;
  color: var(--ink-500);
  line-height: 1.5;
}

.guild-card__field {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.guild-card__hint {
  font-size: 12px;
  font-weight: 500;
  color: var(--el-color-danger);
}

/* ---------- Action footer ---------- */
.guild-config-section__actions {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
  padding: 14px 4px 4px;
  border-top: 1px dashed rgba(15, 23, 42, 0.08);
}

/* Element Plus injects margin-left:12px on sibling buttons by default.
   When the row uses flex `gap`, both apply and spacing doubles —
   neutralize the margin so gap alone owns the rhythm. */
.guild-config-section__actions :deep(.el-button + .el-button) {
  margin-left: 0;
}
</style>
