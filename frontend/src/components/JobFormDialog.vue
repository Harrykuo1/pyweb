<script setup>
import { computed, markRaw, reactive, ref, watch } from 'vue'
import {
  ElAutocomplete,
  ElButton,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElInputNumber,
  ElMessage,
  ElTabPane,
  ElTabs,
} from 'element-plus'
import { Loading } from '@element-plus/icons-vue'
import { MdEditor } from 'md-editor-v3'
import 'md-editor-v3/lib/style.css'

import { jobsApi } from '../api/jobs'

const props = defineProps({
  modelValue: { type: Boolean, required: true },
  job: { type: Object, default: null },
})

const emit = defineEmits(['update:modelValue', 'saved'])

const isEdit = computed(() => props.job !== null)
const title = computed(() => (isEdit.value ? '編輯求職紀錄' : '新增求職紀錄'))

const KIND_OPTIONS = [
  { label: '實習', value: 'internship' },
  { label: '正職', value: 'fulltime' },
]

const CURRENT_YEAR = new Date().getFullYear()
const MIN_JOB_YEAR = 2000
const MAX_JOB_YEAR = CURRENT_YEAR + 1

const formRef = ref(null)
const submitting = ref(false)
const activeTab = ref('experience')

const form = reactive({
  kind: 'internship',
  job_year: CURRENT_YEAR,
  company: '',
  real_name: '',
  experience_md: '',
  timeline_md: '',
})

const rules = {
  kind: [{ required: true, message: '請選擇類型', trigger: 'change' }],
  job_year: [{ required: true, message: '請輸入求職年份', trigger: 'blur' }],
  company: [{ required: true, message: '請輸入公司名稱', trigger: 'blur' }],
  experience_md: [
    { required: true, message: '請填寫心得內容', trigger: 'blur' },
  ],
}

function resetForm(job) {
  Object.assign(form, {
    kind: job?.kind ?? 'internship',
    job_year: job?.job_year ?? CURRENT_YEAR,
    company: job?.company ?? '',
    real_name: job?.real_name ?? '',
    experience_md: job?.experience_md ?? '',
    timeline_md: job?.timeline_md ?? '',
  })
  activeTab.value = 'experience'
  formRef.value?.clearValidate()
}

watch(
  () => [props.modelValue, props.job],
  ([open]) => {
    if (open) resetForm(props.job)
  },
  { immediate: true },
)

function close() {
  emit('update:modelValue', false)
}

async function fetchCompanySuggestions(queryString, cb) {
  try {
    const list = await jobsApi.listCompanies(queryString || undefined)
    cb(list.map((c) => ({ value: c })))
  } catch {
    cb([])
  }
}

function buildPayload() {
  const trimmedRealName = form.real_name.trim()
  const trimmedTimeline = form.timeline_md.trim()
  return {
    kind: form.kind,
    job_year: form.job_year,
    company: form.company.trim(),
    experience_md: form.experience_md.trim(),
    real_name: trimmedRealName === '' ? null : trimmedRealName,
    timeline_md: trimmedTimeline === '' ? null : trimmedTimeline,
  }
}

async function handleSubmit() {
  if (!formRef.value) return

  // Guard the required text fields manually. el-form-item's validate()
  // is unreliable for the autocomplete-bound company input and the
  // MdEditor-bound experience field, since neither triggers the
  // form-item event hooks the way a plain el-input does.
  if (!form.company.trim() || !form.experience_md.trim()) {
    if (!form.experience_md.trim()) activeTab.value = 'experience'
    formRef.value.validate().catch(() => {})
    return
  }

  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) {
    if (!form.experience_md.trim()) activeTab.value = 'experience'
    return
  }

  submitting.value = true
  const toast = ElMessage({
    message: isEdit.value ? '儲存中…' : '新增中…',
    icon: markRaw(Loading),
    duration: 0,
    customClass: 'message-uploading',
  })

  try {
    const payload = buildPayload()
    if (isEdit.value) {
      await jobsApi.update(props.job.id, payload)
    } else {
      await jobsApi.create(payload)
    }
    toast.close()
    ElMessage.success(isEdit.value ? '已更新求職紀錄' : '已新增求職紀錄')
    emit('saved')
    close()
  } catch (err) {
    toast.close()
    const status = err?.response?.status
    if (status === 422) ElMessage.error('輸入格式不正確')
    else if (status === 403) ElMessage.error('權限不足')
    else ElMessage.error('儲存失敗，請稍後再試')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    :title="title"
    width="720"
    top="6vh"
    :close-on-click-modal="false"
    :teleported="false"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      label-position="top"
      class="job-form"
    >
      <div class="row-2">
        <el-form-item label="類型" prop="kind" class="form-kind">
          <div class="kind-picker" role="radiogroup" aria-label="類型">
            <button
              v-for="opt in KIND_OPTIONS"
              :key="opt.value"
              type="button"
              role="radio"
              :aria-checked="form.kind === opt.value"
              :class="[
                'kind-option',
                `kind-option--${opt.value}`,
                { 'is-active': form.kind === opt.value },
              ]"
              :data-test="`kind-option-${opt.value}`"
              @click="form.kind = opt.value"
            >
              {{ opt.label }}
            </button>
          </div>
        </el-form-item>

        <el-form-item label="求職年份" prop="job_year" class="form-year">
          <el-input-number
            v-model="form.job_year"
            :min="MIN_JOB_YEAR"
            :max="MAX_JOB_YEAR"
            :step="1"
            :precision="0"
            controls-position="right"
            data-test="form-year"
          />
        </el-form-item>
      </div>

      <el-form-item label="公司" prop="company">
        <el-autocomplete
          v-model="form.company"
          :fetch-suggestions="fetchCompanySuggestions"
          :trigger-on-focus="true"
          placeholder="請輸入公司名稱"
          maxlength="128"
          show-word-limit
          data-test="form-company"
          class="form-company"
        />
      </el-form-item>

      <el-form-item label="本名（留空為匿名）" prop="real_name">
        <el-input
          v-model="form.real_name"
          placeholder="可留空"
          maxlength="64"
          show-word-limit
          data-test="form-real-name"
        />
      </el-form-item>

      <el-form-item prop="experience_md" :show-message="false">
        <el-tabs v-model="activeTab" class="md-tabs">
          <el-tab-pane label="心得" name="experience">
            <MdEditor
              v-model="form.experience_md"
              theme="light"
              language="zh-TW"
              :preview="false"
              :toolbars-exclude="['github', 'save', 'mermaid', 'katex']"
              data-test="form-experience-md"
            />
            <p
              v-if="!form.experience_md.trim()"
              class="md-required-hint"
            >
              心得為必填
            </p>
          </el-tab-pane>
          <el-tab-pane label="時程表（選填）" name="timeline">
            <MdEditor
              v-model="form.timeline_md"
              theme="light"
              language="zh-TW"
              :preview="false"
              :toolbars-exclude="['github', 'save', 'mermaid', 'katex']"
              data-test="form-timeline-md"
            />
          </el-tab-pane>
        </el-tabs>
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="close">取消</el-button>
      <el-button
        type="primary"
        :loading="submitting"
        data-test="save-button"
        @click="handleSubmit"
      >
        {{ isEdit ? '儲存' : '新增' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.job-form {
  /* Make sure the form's vertical rhythm is comfortable inside the
     dialog — defaults bunch the items too tight when md editors take
     up most of the height. */
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.row-2 {
  display: grid;
  grid-template-columns: 1fr 200px;
  gap: var(--sp-md);
}

.form-kind :deep(.el-form-item__content),
.form-year :deep(.el-form-item__content) {
  width: 100%;
}

.form-company {
  width: 100%;
}

/* ---------- Kind picker (radio styled as segmented chips) ---------- */
.kind-picker {
  display: inline-flex;
  background: var(--surface-2, #f1f5f9);
  border-radius: var(--radius-md);
  padding: 3px;
  gap: 2px;
}

.kind-option {
  border: 0;
  background: transparent;
  padding: 6px 18px;
  font-size: 13px;
  font-weight: 500;
  color: var(--ink-500);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background-color var(--dur) var(--ease),
    color var(--dur) var(--ease), box-shadow var(--dur) var(--ease);
}

.kind-option:hover {
  color: var(--ink-700);
}

.kind-option.is-active {
  background: #ffffff;
  color: var(--ink-900);
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.1);
}

.kind-option--internship.is-active {
  color: #4f46e5;
}

.kind-option--fulltime.is-active {
  color: #047857;
}

/* ---------- Markdown editor tabs ---------- */
.md-tabs :deep(.el-tabs__nav-wrap)::after {
  height: 1px;
  background: rgba(15, 23, 42, 0.06);
}

.md-tabs :deep(.el-tabs__item) {
  font-weight: 500;
}

.md-tabs :deep(.el-tabs__item.is-active) {
  color: #7c3aed;
}

.md-tabs :deep(.el-tabs__active-bar) {
  background: linear-gradient(135deg, #7c3aed, #d946ef);
}

/* Cap editor height so the dialog stays scroll-friendly even with long
   markdown — the editor itself scrolls internally past the cap. */
:deep(.md-editor) {
  height: 320px;
}

.md-required-hint {
  margin: 4px 0 0;
  color: #f56c6c;
  font-size: 12px;
}

@media (max-width: 640px) {
  .row-2 {
    grid-template-columns: 1fr;
  }

  :deep(.md-editor) {
    height: 260px;
  }
}
</style>
