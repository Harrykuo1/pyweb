<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import {
  ElAlert,
  ElButton,
  ElCard,
  ElForm,
  ElFormItem,
  ElInputNumber,
  ElMessage,
  ElSkeleton,
} from 'element-plus'

import { settingsApi } from '../api/settings'

// Field metadata that's not in the API response (labels, help text) lives
// here so the backend stays free of locale strings. Unknown keys fall back
// to the raw key — that way a setting added on the backend before the
// frontend ships still renders, just without polish.
const FIELD_COPY = {
  max_attachments_per_job: {
    label: '單筆求職紀錄附件數上限',
    description: '每筆求職紀錄最多可掛上的附件總數。',
  },
  max_attachment_mb: {
    label: '單檔大小上限 (MB)',
    description: '每個附件檔案的最大上傳大小，單位為 MB。',
  },
}

const fields = ref([])
const form = reactive({})
const loading = ref(true)
const saving = ref(false)
const loadError = ref('')

// Bumped on every successful refresh from the server so the
// el-input-number :key changes, forcing Vue to tear down and rebuild
// each input. Without this, the component's internal display state can
// stay out of sync with v-model after a server-side clamp (e.g. user
// typed 999, blur clamped to 50, server confirmed 50): the prop didn't
// change so el-input-number's watch skipped, leaving its currentValue
// stale and the spinner unresponsive until the next external nudge.
const formVersion = ref(0)

function applyFromResponse(payload) {
  fields.value = payload.fields ?? []
  for (const f of fields.value) {
    form[f.key] = f.value
  }
  formVersion.value += 1
}

async function load() {
  loading.value = true
  loadError.value = ''
  try {
    applyFromResponse(await settingsApi.getConfig())
  } catch (err) {
    loadError.value = '載入設定失敗，請稍後再試。'
  } finally {
    loading.value = false
  }
}

async function handleSave() {
  saving.value = true
  try {
    // Only send keys that the form actually has a value for — protects
    // against accidentally clobbering future fields the frontend doesn't
    // know about yet.
    const values = {}
    for (const f of fields.value) {
      values[f.key] = form[f.key]
    }
    applyFromResponse(await settingsApi.updateConfig(values))
    ElMessage.success('設定已儲存')
  } catch (err) {
    const status = err?.response?.status
    if (status === 422 || status === 400) {
      ElMessage.error(err.response.data?.detail ?? '輸入值不符合限制')
    } else if (status === 403) {
      ElMessage.error('需要管理員權限')
    } else {
      ElMessage.error('儲存失敗，請稍後再試')
    }
  } finally {
    saving.value = false
  }
}

const dirty = computed(() =>
  fields.value.some((f) => form[f.key] !== f.value),
)

function handleReset() {
  for (const f of fields.value) {
    form[f.key] = f.value
  }
}

function copyFor(key) {
  return FIELD_COPY[key] ?? { label: key, description: '' }
}

onMounted(load)
</script>

<template>
  <section class="admin-settings">
    <header class="page-header">
      <h1>系統設定</h1>
      <p class="subtitle">調整全域行為，例如附件數量與大小限制。</p>
    </header>

    <el-card shadow="never" class="settings-card">
      <el-skeleton v-if="loading" :rows="3" animated />

      <el-alert
        v-else-if="loadError"
        :title="loadError"
        type="error"
        :closable="false"
        show-icon
      />

      <el-form
        v-else
        label-position="top"
        :model="form"
        data-test="settings-form"
        @submit.prevent="handleSave"
      >
        <el-form-item
          v-for="f in fields"
          :key="f.key"
          :label="copyFor(f.key).label"
        >
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
          <p v-if="copyFor(f.key).description" class="field-help">
            {{ copyFor(f.key).description }}
            <span v-if="f.min != null || f.max != null" class="field-bounds">
              （允許範圍 {{ f.min ?? '-' }} ~ {{ f.max ?? '-' }}）
            </span>
          </p>
        </el-form-item>

        <div class="actions">
          <el-button
            :disabled="!dirty || saving"
            @click="handleReset"
            data-test="settings-reset"
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
        </div>
      </el-form>
    </el-card>
  </section>
</template>

<style scoped>
.admin-settings {
  max-width: 720px;
  margin: 0 auto;
}

.page-header {
  margin-bottom: 24px;
}

.page-header h1 {
  margin: 0 0 4px;
  font-size: 22px;
  font-weight: 600;
}

.subtitle {
  margin: 0;
  color: var(--ink-500, #64748b);
  font-size: 14px;
}

.settings-card {
  border-radius: 12px;
}

.field-help {
  margin: 6px 0 0;
  color: var(--ink-500, #64748b);
  font-size: 12px;
  line-height: 1.5;
}

.field-bounds {
  margin-left: 4px;
  color: var(--ink-400, #94a3b8);
}

.actions {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
