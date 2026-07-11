<script setup>
import { nextTick, ref, watch } from 'vue'
import {
  ElButton,
  ElDialog,
  ElForm,
  ElFormItem,
  ElIcon,
  ElInput,
} from 'element-plus'
import { WarningFilled } from '@element-plus/icons-vue'

const props = defineProps({
  modelValue: { type: Boolean, required: true },
  title: { type: String, default: '刪除確認' },
  itemName: { type: String, default: '' },
  warning: { type: String, default: '此操作無法復原。' },
  loading: { type: Boolean, default: false },
  errorMessage: { type: String, default: '' },
  // Admins re-authenticate with their password before a destructive delete.
  // Post authors deleting their own content don't — the dialog then acts as
  // a plain confirmation and emits `confirm` with no password.
  requirePassword: { type: Boolean, default: true },
})

const emit = defineEmits(['update:modelValue', 'confirm'])

const password = ref('')
const inputRef = ref(null)

watch(
  () => props.modelValue,
  async (open) => {
    if (open) {
      password.value = ''
      await nextTick()
      inputRef.value?.focus()
    }
  },
)

function close() {
  emit('update:modelValue', false)
}

function submit() {
  if (props.loading) return
  if (props.requirePassword) {
    if (!password.value) return
    emit('confirm', password.value)
  } else {
    emit('confirm', undefined)
  }
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    :title="title"
    width="420"
    :close-on-click-modal="false"
    align-center
    data-test="delete-with-password-dialog"
    @update:model-value="(v) => emit('update:modelValue', v)"
  >
    <div class="warn-block">
      <el-icon class="warn-icon" :size="22">
        <WarningFilled />
      </el-icon>
      <div class="warn-text">
        <p v-if="itemName" class="warn-headline">
          將永久刪除<span class="target-name">「{{ itemName }}」</span>
        </p>
        <p class="warn-detail">{{ warning }}</p>
      </div>
    </div>

    <el-form label-position="top" @submit.prevent="submit">
      <el-form-item v-if="requirePassword" label="管理員密碼">
        <el-input
          ref="inputRef"
          v-model="password"
          type="password"
          placeholder="請輸入您的密碼以確認"
          autocomplete="current-password"
          show-password
          :disabled="loading"
          data-test="delete-password-input"
          @keyup.enter="submit"
        />
      </el-form-item>
      <p v-if="errorMessage" class="error" data-test="delete-error">
        {{ errorMessage }}
      </p>
    </el-form>

    <template #footer>
      <el-button :disabled="loading" @click="close">取消</el-button>
      <el-button
        type="danger"
        :loading="loading"
        :disabled="requirePassword && !password"
        data-test="delete-confirm"
        @click="submit"
      >
        刪除
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.warn-block {
  display: flex;
  gap: 12px;
  background: rgba(245, 158, 11, 0.08);
  border: 1px solid rgba(245, 158, 11, 0.2);
  border-radius: var(--radius-md);
  padding: 12px 14px;
  margin-bottom: var(--sp-md);
}

.warn-icon {
  color: #d97706;
  margin-top: 2px;
  flex-shrink: 0;
}

.warn-text {
  flex: 1;
  font-size: 13px;
  line-height: 1.6;
}

.warn-headline {
  margin: 0 0 4px;
  color: var(--ink-900);
  font-weight: 500;
}

.target-name {
  color: var(--brand-primary);
  font-weight: 600;
}

.warn-detail {
  margin: 0;
  color: var(--ink-700);
}

.error {
  margin: -4px 0 0;
  color: #ef4444;
  font-size: 13px;
}
</style>
