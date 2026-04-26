<script setup>
import { computed, reactive, ref, watch } from 'vue'
import {
  ElButton,
  ElDatePicker,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElInputNumber,
  ElMessage,
} from 'element-plus'

import { membersApi } from '../api/members'

const props = defineProps({
  modelValue: { type: Boolean, required: true },
  member: { type: Object, default: null },
})

const emit = defineEmits(['update:modelValue', 'saved'])

const isEdit = computed(() => props.member !== null)
const title = computed(() => (isEdit.value ? '編輯成員' : '新增成員'))

const formRef = ref(null)
const submitting = ref(false)
const form = reactive({
  graduation_year: new Date().getFullYear(),
  real_name: '',
  current_position: '',
  resume_md: '',
  joined_at: null,
})

const rules = {
  graduation_year: [{ required: true, message: '請輸入畢業年份', trigger: 'blur' }],
  real_name: [{ required: true, message: '請輸入本名', trigger: 'blur' }],
  current_position: [{ required: true, message: '請輸入目前就職／就讀', trigger: 'blur' }],
}

function resetForm(member) {
  Object.assign(form, {
    graduation_year: member?.graduation_year ?? new Date().getFullYear(),
    real_name: member?.real_name ?? '',
    current_position: member?.current_position ?? '',
    resume_md: member?.resume_md ?? '',
    joined_at: member?.joined_at ?? null,
  })
  formRef.value?.clearValidate()
}

watch(
  () => [props.modelValue, props.member],
  ([open]) => {
    if (open) resetForm(props.member)
  },
  { immediate: true },
)

function close() {
  emit('update:modelValue', false)
}

function buildPayload() {
  // Always send required fields. Send optional fields only when populated;
  // strip joined_at when null so the backend keeps existing value on edit
  // and falls back to now() on create.
  const payload = {
    graduation_year: form.graduation_year,
    real_name: form.real_name.trim(),
    current_position: form.current_position.trim(),
    resume_md: form.resume_md.trim() || null,
  }
  if (form.joined_at) {
    const d = form.joined_at instanceof Date ? form.joined_at : new Date(form.joined_at)
    payload.joined_at = d.toISOString()
  }
  return payload
}

async function handleSubmit() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    const payload = buildPayload()
    if (isEdit.value) {
      await membersApi.update(props.member.id, payload)
      ElMessage.success('已更新成員')
    } else {
      await membersApi.create(payload)
      ElMessage.success('已新增成員')
    }
    emit('saved')
    close()
  } catch (err) {
    if (err?.response?.status === 422) {
      ElMessage.error('輸入格式不正確')
    } else if (err?.response?.status === 403) {
      ElMessage.error('權限不足')
    } else {
      ElMessage.error('儲存失敗，請稍後再試')
    }
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    :title="title"
    width="540"
    :close-on-click-modal="false"
    :teleported="false"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      label-width="120px"
      label-position="right"
    >
      <el-form-item label="畢業年份" prop="graduation_year">
        <el-input-number v-model="form.graduation_year" :min="1900" :max="2100" />
      </el-form-item>
      <el-form-item label="本名" prop="real_name">
        <el-input v-model="form.real_name" maxlength="64" show-word-limit />
      </el-form-item>
      <el-form-item label="目前就職／就讀" prop="current_position">
        <el-input v-model="form.current_position" maxlength="255" show-word-limit />
      </el-form-item>
      <el-form-item label="入群時間">
        <el-date-picker
          v-model="form.joined_at"
          type="date"
          placeholder="留空則使用今天"
          value-format="YYYY-MM-DD"
        />
      </el-form-item>
      <el-form-item label="履歷 (Markdown)">
        <el-input
          v-model="form.resume_md"
          type="textarea"
          :rows="6"
          placeholder="可留空。Phase 7 將升級為 Markdown 編輯器"
        />
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
