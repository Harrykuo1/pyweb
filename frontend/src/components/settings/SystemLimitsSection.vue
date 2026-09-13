<script setup>
import { ElAlert, ElButton, ElInputNumber, ElSkeleton } from 'element-plus'

import { useSystemLimitsForm } from '../../composables/useSystemLimitsForm'

// Which slice of the runtime config this instance edits. The settings page
// mounts one per domain, and the backend tags each field with its group, so
// a new setting lands in the right tab without touching this file.
const props = defineProps({
  group: {
    type: String,
    required: true,
    validator: (v) => ['job', 'event'].includes(v),
  },
})

// The config-form logic lives in the composable; this is presentation.
const {
  fields,
  form,
  loading,
  saving,
  loadError,
  formVersion,
  dirty,
  handleSave,
  handleReset,
  copyFor,
} = useSystemLimitsForm(props.group)

defineExpose({ form, formVersion })
</script>

<template>
  <div class="system-limits-section">
    <el-skeleton v-if="loading" :rows="4" animated />

    <el-alert
      v-else-if="loadError"
      :title="loadError"
      type="error"
      :closable="false"
      show-icon
    />

    <form
      v-else
      class="system-limits-section__form"
      data-test="settings-form"
      @submit.prevent="handleSave"
    >
      <article v-for="f in fields" :key="f.key" class="limits-card">
        <header class="limits-card__header">
          <h4>{{ copyFor(f.key).label }}</h4>
          <p v-if="copyFor(f.key).description">
            {{ copyFor(f.key).description }}
          </p>
        </header>

        <div class="limits-card__field">
          <div class="limits-card__input-group">
            <el-input-number
              v-if="f.type === 'int'"
              :key="`${f.key}-${formVersion}`"
              v-model="form[f.key]"
              :min="f.min ?? undefined"
              :max="f.max ?? undefined"
              :step="1"
              :precision="0"
              :data-test="`setting-${f.key}`"
            />
            <span v-if="copyFor(f.key).unit" class="limits-card__unit">
              {{ copyFor(f.key).unit }}
            </span>
          </div>
          <span
            v-if="f.min != null || f.max != null"
            class="limits-card__bounds"
          >
            允許範圍 {{ f.min ?? '-' }} ~ {{ f.max ?? '-' }}
          </span>
        </div>
      </article>

      <footer class="system-limits-section__actions">
        <span v-if="dirty" class="system-limits-section__dirty">
          有未儲存的變更
        </span>
        <el-button
          :disabled="!dirty || saving"
          data-test="settings-reset"
          @click="handleReset"
        >
          還原
        </el-button>
        <el-button
          type="primary"
          :loading="saving"
          :disabled="!dirty"
          data-test="settings-save"
          @click="handleSave"
        >
          儲存
        </el-button>
      </footer>
    </form>
  </div>
</template>

<style scoped>
.system-limits-section {
  display: flex;
  flex-direction: column;
}

.system-limits-section__form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

/* ---------- Card per setting ---------- */
.limits-card {
  background: var(--surface-0);
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: var(--radius-lg);
  padding: 20px 22px;
  box-shadow: var(--shadow-sm);
  transition:
    border-color var(--dur) var(--ease),
    box-shadow var(--dur) var(--ease);
}

.limits-card:hover {
  border-color: rgba(99, 102, 241, 0.22);
  box-shadow: var(--shadow-md);
}

.limits-card__header {
  margin: 0 0 16px;
}

.limits-card__header h4 {
  margin: 0 0 4px;
  font-size: 15px;
  font-weight: 700;
  color: var(--ink-900);
}

.limits-card__header p {
  margin: 0;
  font-size: 12px;
  color: var(--ink-500);
  line-height: 1.5;
}

.limits-card__field {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

/* Input + unit are visually one unit — same row, tight gap, shared
   baseline. Default-size el-input-number lines up with 14px medium
   unit text so the contrast user flagged is gone. */
.limits-card__input-group {
  display: inline-flex;
  align-items: center;
  gap: 10px;
}

.limits-card__unit {
  font-size: 14px;
  color: var(--ink-900);
  font-weight: 600;
  letter-spacing: 0.01em;
}

.limits-card__bounds {
  margin-left: auto;
  font-size: 12px;
  font-weight: 500;
  color: var(--ink-700);
  background: var(--surface-2);
  border: 1px solid rgba(15, 23, 42, 0.08);
  padding: 5px 12px;
  border-radius: var(--radius-sm);
  white-space: nowrap;
}

/* ---------- Action footer ---------- */
.system-limits-section__actions {
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
.system-limits-section__actions :deep(.el-button + .el-button) {
  margin-left: 0;
}

.system-limits-section__dirty {
  margin-right: auto;
  font-size: 12px;
  color: var(--accent-warm-ink);
  background: var(--accent-warm-soft);
  padding: 4px 10px;
  border-radius: 999px;
  font-weight: 500;
}

@media (max-width: 640px) {
  .limits-card__bounds {
    margin-left: 0;
    margin-top: 4px;
  }
}
</style>
