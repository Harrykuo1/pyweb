<script setup>
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  reactive,
  ref,
  watch,
} from 'vue'
import {
  ElButton,
  ElDatePicker,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElMessage,
  ElOption,
  ElSelect,
  ElTabPane,
  ElTabs,
  ElTooltip,
} from 'element-plus'
import { FullScreen } from '@element-plus/icons-vue'
import { MdEditor } from 'md-editor-v3'
import { sanitizeHtml } from '../../utils/sanitizeHtml'
import 'md-editor-v3/lib/style.css'

import { eventsApi } from '../../api/events'
import EventPhotosManager from './EventPhotosManager.vue'

const props = defineProps({
  modelValue: { type: Boolean, required: true },
  event: { type: Object, default: null },
})

const emit = defineEmits(['update:modelValue', 'saved'])

// Locally-cached event created during this dialog session, so after a
// successful POST the dialog flips from "new" into "edit" mode without
// closing — the admin can then upload photos against the new id.
const createdEvent = ref(null)
const currentEvent = computed(() => createdEvent.value ?? props.event)
const isEdit = computed(() => currentEvent.value !== null)
const title = computed(() => (isEdit.value ? '編輯活動' : '新增活動'))

const formRef = ref(null)
const descEditorRef = ref(null)
const submitting = ref(false)
const activeTab = ref('detail')

const TAG_LIMIT = 12

const DESKTOP_TOOLBARS = [
  'bold',
  'underline',
  'italic',
  'strikeThrough',
  '-',
  'title',
  'quote',
  '-',
  'unorderedList',
  'orderedList',
  'task',
  '-',
  'codeRow',
  'link',
  'image',
  'table',
  '-',
  'revoke',
  'next',
  '-',
  'pageFullscreen',
  'preview',
  'previewOnly',
]
const MOBILE_TOOLBARS = [
  'bold',
  'title',
  '-',
  'unorderedList',
  'orderedList',
  '-',
  'link',
  'pageFullscreen',
]
const MOBILE_BREAKPOINT = 768

const viewportWidth = ref(
  typeof window !== 'undefined' ? window.innerWidth : 1024,
)
const isMobileWidth = computed(() => viewportWidth.value < MOBILE_BREAKPOINT)
function _onViewportResize() {
  viewportWidth.value = window.innerWidth
}
onMounted(() => {
  if (typeof window !== 'undefined') {
    window.addEventListener('resize', _onViewportResize)
  }
})
onBeforeUnmount(() => {
  if (typeof window !== 'undefined') {
    window.removeEventListener('resize', _onViewportResize)
  }
})
const editorToolbars = computed(() =>
  isMobileWidth.value ? MOBILE_TOOLBARS : DESKTOP_TOOLBARS,
)

const wiredEditors = new WeakSet()
const isDescFullscreen = ref(false)
function wirePreviewSync() {
  const ed = descEditorRef.value
  if (!ed || wiredEditors.has(ed)) return
  ed.on('fullscreen', (on) => {
    if (!isMobileWidth.value) ed.togglePreview(on)
  })
  ed.on('pageFullscreen', (on) => {
    if (!isMobileWidth.value) ed.togglePreview(on)
    isDescFullscreen.value = on
  })
  wiredEditors.add(ed)
}
function expandEditor() {
  descEditorRef.value?.togglePageFullscreen?.()
}

const form = reactive({
  title: '',
  event_date: null,
  location: '',
  tags: [],
  description_md: '',
})

const rules = {
  title: [{ required: true, message: '請輸入活動名稱', trigger: 'blur' }],
  event_date: [
    { required: true, message: '請選擇活動日期', trigger: 'change' },
  ],
}

const tagSuggestions = ref([])
async function fetchTagSuggestions(queryString) {
  try {
    tagSuggestions.value = await eventsApi.listTags(queryString || undefined)
  } catch {
    tagSuggestions.value = []
  }
}

// Date-picker hands us a Date; the API takes an ISO YYYY-MM-DD string.
// Bridge through a writable computed so the form holds the API shape.
function _toISODate(d) {
  if (!d) return null
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}
const eventDateModel = computed({
  get() {
    return form.event_date ? new Date(`${form.event_date}T00:00:00`) : null
  },
  set(value) {
    form.event_date = _toISODate(value)
  },
})

function resetForm(ev) {
  Object.assign(form, {
    title: ev?.title ?? '',
    event_date: ev?.event_date ?? null,
    location: ev?.location ?? '',
    tags: Array.isArray(ev?.tags) ? [...ev.tags] : [],
    description_md: ev?.description_md ?? '',
  })
  activeTab.value = 'detail'
  isDescFullscreen.value = false
  tagSuggestions.value = []
  formRef.value?.clearValidate()
}

const openCounter = ref(0)
watch(
  () => [props.modelValue, props.event],
  ([open]) => {
    if (open) {
      createdEvent.value = null
      resetForm(props.event)
      nextTick(wirePreviewSync)
      openCounter.value += 1
    }
  },
  { immediate: true },
)

function close() {
  emit('update:modelValue', false)
}

function buildPayload() {
  const trimmedLocation = form.location.trim()
  // Normalize tags client-side too (the backend re-cleans), capped at the
  // same limit. Trim, drop blanks, dedupe case-insensitively.
  const seen = new Set()
  const tags = []
  for (const raw of form.tags) {
    const t = String(raw).trim()
    if (!t) continue
    const key = t.toLowerCase()
    if (seen.has(key)) continue
    seen.add(key)
    tags.push(t)
    if (tags.length >= TAG_LIMIT) break
  }
  return {
    title: form.title.trim(),
    event_date: form.event_date,
    location: trimmedLocation === '' ? null : trimmedLocation,
    tags,
    description_md: form.description_md.trim() || null,
  }
}

async function handleSubmit() {
  if (!formRef.value) return
  if (!form.title.trim() || !form.event_date) {
    activeTab.value = 'detail'
    formRef.value.validate().catch(() => {})
    return
  }
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) {
    activeTab.value = 'detail'
    return
  }

  submitting.value = true
  try {
    const payload = buildPayload()
    if (isEdit.value) {
      await eventsApi.update(currentEvent.value.id, payload)
      ElMessage.success('已更新活動')
      emit('saved')
      close()
    } else {
      const created = await eventsApi.create(payload)
      createdEvent.value = created
      activeTab.value = 'photos'
      emit('saved')
      // Members' events enter the review queue; admins' are live at once.
      ElMessage.success(
        created.status === 'accepted'
          ? '已新增，現在可上傳照片'
          : '已送出審核，通過後才會公開；你可以先上傳照片',
      )
    }
  } catch (err) {
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
    width="820"
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
      class="event-form"
    >
      <el-tabs v-model="activeTab" class="event-tabs">
        <el-tab-pane label="基本資料" name="detail">
          <div class="form-row-inline">
            <el-form-item label="活動名稱" prop="title" class="grow">
              <el-input
                v-model="form.title"
                placeholder="例如：春酒聚餐、溪頭兩日遊"
                maxlength="128"
                show-word-limit
                data-test="form-title"
              />
            </el-form-item>

            <el-form-item label="活動日期" prop="event_date">
              <el-date-picker
                v-model="eventDateModel"
                type="date"
                format="YYYY / MM / DD"
                placeholder="選擇日期"
                data-test="form-event-date"
                class="form-date"
              />
            </el-form-item>
          </div>

          <div class="form-row-inline">
            <el-form-item label="地點（選填）" class="grow">
              <el-input
                v-model="form.location"
                placeholder="例如：台北、陽明山、線上"
                maxlength="128"
                data-test="form-location"
              />
            </el-form-item>

            <el-form-item label="標籤（選填，可自由輸入）" class="grow">
              <el-select
                v-model="form.tags"
                multiple
                filterable
                allow-create
                remote
                default-first-option
                :reserve-keyword="false"
                :multiple-limit="TAG_LIMIT"
                :remote-method="fetchTagSuggestions"
                placeholder="輸入後按 Enter 建立，如：春酒、桌遊"
                data-test="form-tags"
                class="form-tags"
              >
                <el-option
                  v-for="t in tagSuggestions"
                  :key="t"
                  :label="t"
                  :value="t"
                />
              </el-select>
            </el-form-item>
          </div>

          <el-form-item label="活動記錄（選填）">
            <button
              v-if="isMobileWidth && !isDescFullscreen"
              type="button"
              class="md-expand-btn"
              data-test="expand-desc-button"
              @click="expandEditor"
            >
              <el-icon :size="14"><FullScreen /></el-icon>
              展開編輯
            </button>
            <MdEditor
              ref="descEditorRef"
              v-model="form.description_md"
              theme="light"
              language="zh-TW"
              :preview="false"
              :toolbars="editorToolbars"
              :sanitize="sanitizeHtml"
              data-test="form-description-md"
            />
          </el-form-item>
        </el-tab-pane>

        <el-tab-pane name="photos" :disabled="!isEdit" data-test="tab-photos">
          <template #label>
            <el-tooltip
              v-if="!isEdit"
              content="先按「新增」建立活動後可上傳照片"
              placement="top"
              :show-after="200"
            >
              <span>照片</span>
            </el-tooltip>
            <span v-else>照片</span>
          </template>

          <EventPhotosManager
            v-if="isEdit"
            :key="`${currentEvent.id}-${openCounter}`"
            :event-id="currentEvent.id"
          />
          <div v-else class="photos-locked" data-test="photos-locked">
            <p class="photos-locked-title">先儲存基本資料</p>
            <p class="photos-locked-sub">
              按下方「新增」建立活動後即可上傳照片。
            </p>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-form>

    <template #footer>
      <el-button @click="close">{{ createdEvent ? '關閉' : '取消' }}</el-button>
      <el-button
        type="primary"
        :loading="submitting"
        data-test="save-event-button"
        @click="handleSubmit"
      >
        {{ isEdit ? '儲存' : '新增' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.event-form {
  display: flex;
  flex-direction: column;
  min-width: 0;
  overflow-x: hidden;
}

.event-tabs,
.event-tabs :deep(.el-tabs__content),
.event-tabs :deep(.el-tab-pane) {
  width: 100%;
}

.event-tabs :deep(.el-tabs__nav-wrap)::after {
  height: 1px;
  background: rgba(15, 23, 42, 0.06);
}

.event-tabs :deep(.el-tabs__item.is-active) {
  color: var(--accent-warm-ink);
}

.event-tabs :deep(.el-tabs__active-bar) {
  background: linear-gradient(
    135deg,
    var(--accent-warm-from),
    var(--accent-warm-to)
  );
}

.form-row-inline {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  column-gap: 24px;
  row-gap: 4px;
}

.form-row-inline .grow {
  flex: 1;
  min-width: 220px;
}

.form-date {
  width: 200px;
}

.form-tags {
  width: 100%;
}

:deep(.md-editor) {
  width: 100% !important;
  min-width: 0;
  max-width: 100%;
  height: 320px;
}

:deep(.md-editor-toolbar-wrapper) {
  overflow-x: auto;
}

:deep(.cm-editor .cm-content),
:deep(.cm-editor .cm-line) {
  white-space: pre-wrap !important;
  word-break: break-word;
}

:deep(.cm-editor .cm-scroller) {
  overflow-x: hidden;
}

.md-expand-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
  padding: 8px 14px;
  border: 1px solid rgba(245, 158, 11, 0.4);
  border-radius: 999px;
  background: rgba(245, 158, 11, 0.1);
  color: var(--accent-warm-ink);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
}

.photos-locked {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 36px 16px;
  text-align: center;
  color: var(--ink-500);
}

.photos-locked-title {
  margin: 0;
  font-size: 14px;
  font-weight: 500;
  color: var(--ink-700);
}

.photos-locked-sub {
  margin: 0;
  font-size: 12px;
}

@media (max-width: 640px) {
  .form-row-inline {
    flex-direction: column;
    align-items: stretch;
  }
  .form-date {
    width: 100%;
  }
  :deep(.md-editor) {
    height: 260px;
  }
}
</style>
