<script setup>
import { computed, reactive, watch } from 'vue'
import { ElButton, ElDialog, ElRadio, ElRadioGroup } from 'element-plus'

const props = defineProps({
  modelValue: { type: Boolean, required: true },
  // [{ filename: string }] — one row per conflicting upload candidate.
  conflicts: { type: Array, required: true },
})

const emit = defineEmits(['update:modelValue', 'resolved'])

const STRATEGIES = [
  { value: 'rename', label: '附加流水號' },
  { value: 'overwrite', label: '覆蓋' },
  { value: 'skip', label: '略過' },
]

// resolutions maps filename -> chosen strategy. Default to "rename" so
// "OK without touching anything" produces the least-destructive outcome.
const resolutions = reactive({})

watch(
  () => props.conflicts,
  (list) => {
    for (const key of Object.keys(resolutions)) delete resolutions[key]
    for (const c of list) {
      resolutions[c.filename] = 'rename'
    }
  },
  { immediate: true },
)

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

function applyToAll(strategy) {
  for (const c of props.conflicts) {
    resolutions[c.filename] = strategy
  }
}

function handleConfirm() {
  // Clone so the parent doesn't accidentally see future edits to the
  // reactive object after the dialog reopens.
  const snapshot = { ...resolutions }
  emit('resolved', snapshot)
  emit('update:modelValue', false)
}

function handleCancel() {
  emit('resolved', null)
  emit('update:modelValue', false)
}
</script>

<template>
  <el-dialog
    v-model="visible"
    title="檔案名稱衝突"
    width="560"
    :close-on-click-modal="false"
    :teleported="false"
    data-test="attachment-conflict-dialog"
  >
    <p class="conflict-intro">
      以下檔案名稱與既有附件重複，請決定每個檔案的處理方式：
    </p>

    <div class="apply-all">
      <span class="apply-all-label">全部套用：</span>
      <el-button
        size="small"
        @click="applyToAll('rename')"
        data-test="apply-all-rename"
      >
        附加流水號
      </el-button>
      <el-button
        size="small"
        @click="applyToAll('overwrite')"
        data-test="apply-all-overwrite"
      >
        覆蓋
      </el-button>
      <el-button
        size="small"
        @click="applyToAll('skip')"
        data-test="apply-all-skip"
      >
        略過
      </el-button>
    </div>

    <ul class="conflict-list">
      <li v-for="c in conflicts" :key="c.filename" class="conflict-row">
        <div class="filename" :title="c.filename">{{ c.filename }}</div>
        <el-radio-group
          v-model="resolutions[c.filename]"
          :data-test="`conflict-row-${c.filename}`"
        >
          <el-radio
            v-for="opt in STRATEGIES"
            :key="opt.value"
            :value="opt.value"
          >
            {{ opt.label }}
          </el-radio>
        </el-radio-group>
      </li>
    </ul>

    <template #footer>
      <el-button @click="handleCancel" data-test="conflict-cancel">
        取消上傳
      </el-button>
      <el-button
        type="primary"
        @click="handleConfirm"
        data-test="conflict-confirm"
      >
        確認
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.conflict-intro {
  margin: 0 0 12px;
  color: var(--ink-700, #334155);
  font-size: 14px;
}

.apply-all {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px dashed rgba(15, 23, 42, 0.08);
}

.apply-all-label {
  font-size: 13px;
  color: var(--ink-500, #64748b);
}

.conflict-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.conflict-row {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 10px 12px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 8px;
  background: var(--surface-1, #f8fafc);
}

.filename {
  font-size: 13px;
  color: var(--ink-900, #0f172a);
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
