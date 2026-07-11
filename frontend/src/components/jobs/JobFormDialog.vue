<script setup>
import {
  computed,
  markRaw,
  nextTick,
  onBeforeUnmount,
  onMounted,
  reactive,
  ref,
  watch,
} from 'vue'
import {
  ElAutocomplete,
  ElButton,
  ElDatePicker,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElMessage,
  ElOption,
  ElSelect,
  ElSwitch,
  ElTabPane,
  ElTabs,
  ElTooltip,
} from 'element-plus'
import { FullScreen, Loading } from '@element-plus/icons-vue'
import { MdEditor } from 'md-editor-v3'
import { sanitizeHtml } from '../../utils/sanitizeHtml'
import 'md-editor-v3/lib/style.css'

import { jobsApi } from '../../api/jobs'
import { membersApi } from '../../api/members'
import { useAuthStore } from '../../stores/auth'
import JobAttachmentsManager from './JobAttachmentsManager.vue'
import TimelineEditor from '../TimelineEditor.vue'

const auth = useAuthStore()

const props = defineProps({
  modelValue: { type: Boolean, required: true },
  job: { type: Object, default: null },
})

const emit = defineEmits(['update:modelValue', 'saved'])

// Locally-cached job created during this dialog session. Set by the
// submit handler after a successful POST so the dialog can flip
// from "new" mode into "edit" mode without closing — the user can
// then upload attachments against the freshly-issued job id.
const createdJob = ref(null)
const currentJob = computed(() => createdJob.value ?? props.job)
const isEdit = computed(() => currentJob.value !== null)
const title = computed(() => (isEdit.value ? '編輯求職紀錄' : '新增求職紀錄'))

const KIND_OPTIONS = [
  { label: '實習', value: 'internship' },
  { label: '正職', value: 'fulltime' },
]

const CURRENT_YEAR = new Date().getFullYear()
const CURRENT_MONTH = new Date().getMonth() + 1
const MIN_JOB_YEAR = 2000
const MAX_JOB_YEAR = CURRENT_YEAR + 1

// el-date-picker month-mode hands us a Date; the API only takes
// (year, month) integers, so adapt at the form-state boundary.
function _ymToDate(year, month) {
  if (!year || !month) return null
  return new Date(year, month - 1, 1)
}

// el-date-picker disabledDate prop callback — block months outside the
// allowed range so users can only pick valid year-month combos.
function isJobYearMonthDisabled(date) {
  const y = date.getFullYear()
  if (y < MIN_JOB_YEAR) return true
  if (y > MAX_JOB_YEAR) return true
  // The latest allowed month is December of (current year + 1) — no
  // need for a finer cap because the year guard already covers the
  // upper bound.
  return false
}

const formRef = ref(null)
const experienceEditorRef = ref(null)
const submitting = ref(false)
const activeTab = ref('experience')

// Desktop toolbar — full set, single row (no '=' divider so the lib
// won't hide the right section on narrow viewports).
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
  'code',
  'link',
  'image',
  'table',
  '-',
  'revoke',
  'next',
  '-',
  'pageFullscreen',
  'fullscreen',
  'preview',
  'previewOnly',
]

// Phones: only the formatting users actually reach for. Rich-text bits
// (image, table, sub/sup, code-block, task) stay desktop-only — they're
// painful to use on a touch keyboard. pageFullscreen has to be in the
// toolbar so users can exit fullscreen mode by tapping the same icon,
// since the dedicated expand button is hidden while the editor covers
// the page.
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

// md-editor-v3's `on(...)` is additive, so wire each instance's
// fullscreen subscription only once across reopens.
const wiredEditors = new WeakSet()

// Reactive viewport gate so the toolbar config and the dedicated
// "expand" button can both adapt without a page reload.
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

// Phones get the editor in a 95 vw dialog; a half-half preview split
// would leave both panes too narrow to read. Cap auto-preview to
// tablets and up so phone users entering fullscreen still see a wide
// editor and can manually toggle preview from the toolbar or the
// dedicated expand button.
function shouldAutoSplitPreview() {
  return !isMobileWidth.value
}

function expandEditor(which) {
  // Only the experience editor remains as a markdown surface; timeline
  // is now a structured-row editor that doesn't need fullscreening.
  if (which !== 'experience') return
  experienceEditorRef.value?.togglePageFullscreen?.()
}

// Tracks per-editor pageFullscreen state so we can hide the dedicated
// "expand" button while the editor is already covering the dialog —
// the custom button would be unreachable behind the overlay anyway.
const isExperienceFullscreen = ref(false)

function _fullscreenStateRef(ed) {
  if (ed === experienceEditorRef.value) return isExperienceFullscreen
  return null
}

function wirePreviewSync(ed) {
  if (!ed || wiredEditors.has(ed)) return
  // Editor-only by default; on tablet+ widths, expand the split preview
  // pane the moment the user fullscreens (browser fullscreen or
  // in-page fullscreen). Collapsing restores editor-only.
  ed.on('fullscreen', (on) => {
    if (shouldAutoSplitPreview()) ed.togglePreview(on)
  })
  ed.on('pageFullscreen', (on) => {
    if (shouldAutoSplitPreview()) ed.togglePreview(on)
    const stateRef = _fullscreenStateRef(ed)
    if (stateRef) stateRef.value = on
  })
  wiredEditors.add(ed)
}

async function wireAllPreviewSync() {
  await nextTick()
  wirePreviewSync(experienceEditorRef.value)
}

const form = reactive({
  kind: 'internship',
  job_year: CURRENT_YEAR,
  job_month: CURRENT_MONTH,
  company: '',
  category: '',
  is_anonymous: false,
  // Admin-only attribution in ONE field: a number is a picked roster member
  // (subject_member_id); a string is a free-text name for a non-member
  // (real_name); null is unattributed. Members can't attribute to others, so
  // the backend ignores this for them. buildPayload splits it back out.
  subject: null,
  experience_md: '',
  timeline_events: [],
})

// Member options for the admin's "post on behalf of" selector. Loaded once
// per dialog open, and only for admins (members can't attribute to others).
const members = ref([])
async function loadMembers() {
  if (!auth.isActuallyAdmin || members.value.length) return
  try {
    members.value = await membersApi.list()
  } catch {
    members.value = []
  }
}
function memberLabel(m) {
  // Disambiguate same-name members by their Discord handle (the permanent
  // identity in this system) rather than graduation year; fall back to just
  // the name for members without a linked handle.
  return m.account_discord_username
    ? `${m.real_name}（@${m.account_discord_username}）`
    : m.real_name
}

// Options for the single "歸屬對象" select: roster members, plus — in edit
// mode — the post's existing free-text name (a string not in the roster) so
// the select can display it.
const subjectOptions = computed(() => {
  const opts = members.value.map((m) => ({
    value: m.id,
    label: memberLabel(m),
  }))
  if (
    typeof form.subject === 'string' &&
    form.subject.trim() &&
    !opts.some((o) => o.value === form.subject)
  ) {
    opts.unshift({ value: form.subject, label: form.subject })
  }
  return opts
})

// Two-way bridge between the el-date-picker (Date) and the form's
// integer (year, month) pair. Using a writable computed keeps the form
// payload simple while letting users pick year-month with the native
// month picker UI.
const jobYearMonth = computed({
  get() {
    return _ymToDate(form.job_year, form.job_month)
  },
  set(value) {
    if (!value) {
      form.job_year = null
      form.job_month = null
      return
    }
    form.job_year = value.getFullYear()
    form.job_month = value.getMonth() + 1
  },
})

// Anchor for the timeline date pickers when a row has no date yet
// and there's no previous row to fall back on. Using the job's own
// year+month means editing a year-old job no longer makes admin
// click `<` 12+ times on every row to reach the right month.
const timelineDefaultDate = computed(() =>
  _ymToDate(form.job_year ?? CURRENT_YEAR, form.job_month ?? CURRENT_MONTH),
)

const rules = {
  kind: [{ required: true, message: '請選擇類型', trigger: 'change' }],
  job_year: [{ required: true, message: '請選擇求職年月', trigger: 'blur' }],
  company: [{ required: true, message: '請輸入公司名稱', trigger: 'blur' }],
  experience_md: [
    { required: true, message: '請填寫心得內容', trigger: 'blur' },
  ],
}

function resetForm(job) {
  Object.assign(form, {
    kind: job?.kind ?? 'internship',
    job_year: job?.job_year ?? CURRENT_YEAR,
    job_month: job?.job_month ?? CURRENT_MONTH,
    company: job?.company ?? '',
    category: job?.category ?? '',
    is_anonymous: job?.is_anonymous ?? false,
    // A member subject → its id (number); otherwise recover the free-text
    // name from display_name (the response drops real_name itself); null when
    // there's neither.
    subject:
      job?.subject_member_id != null
        ? job.subject_member_id
        : (job?.display_name ?? null),
    experience_md: job?.experience_md ?? '',
    // Structured editor bound to a copy so the user's edits don't
    // mutate the parent's job object until they actually save.
    // Legacy jobs (which only have timeline_md) start with an empty
    // list — admin re-enters the timeline through the structured
    // editor on next save, replacing the old markdown.
    timeline_events: Array.isArray(job?.timeline_events)
      ? job.timeline_events.map((e) => ({ ...e }))
      : [],
  })
  activeTab.value = 'experience'
  isExperienceFullscreen.value = false
  formRef.value?.clearValidate()
}

// Bumped on every dialog open so the attachments manager's :key
// changes, forcing a fresh GET — otherwise the manager keeps showing
// whatever it loaded the first time this dialog ever rendered, even
// after attachments are added or deleted elsewhere in the session.
const openCounter = ref(0)

watch(
  () => [props.modelValue, props.job],
  ([open]) => {
    if (open) {
      // Reset the create-then-edit handoff so reopening for a new
      // record doesn't inherit the previous session's createdJob.
      createdJob.value = null
      resetForm(props.job)
      loadMembers()
      wireAllPreviewSync()
      openCounter.value += 1
    }
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

async function fetchCategorySuggestions(queryString, cb) {
  try {
    const list = await jobsApi.listCategories(queryString || undefined)
    cb(list.map((c) => ({ value: c })))
  } catch {
    cb([])
  }
}

function buildPayload() {
  const trimmedCategory = form.category.trim()
  // Drop incomplete rows (missing date or blank event text) so the
  // backend's per-row validation never sees partial input. An entirely
  // empty list goes through as []; the backend distinguishes [] (admin
  // chose no timeline) from null (legacy markdown-only job) and we
  // always send the structured form here.
  //
  // Sort by date asc on submit — the editor preserves entry order so
  // the admin's caret never jumps mid-typing, but the persisted /
  // displayed order is always chronological. ISO YYYY-MM-DD strings
  // sort lexicographically = chronologically; V8's Array#sort is
  // stable so same-date rows keep their entry order.
  const cleanedEvents = form.timeline_events
    .map((e) => ({
      date: typeof e.date === 'string' ? e.date : null,
      event: typeof e.event === 'string' ? e.event.trim() : '',
    }))
    .filter((e) => e.date !== null && e.event.length > 0)
    .sort((a, b) => a.date.localeCompare(b.date))
  const payload = {
    kind: form.kind,
    job_year: form.job_year,
    job_month: form.job_month,
    company: form.company.trim(),
    category: trimmedCategory === '' ? null : trimmedCategory,
    experience_md: form.experience_md.trim(),
    is_anonymous: form.is_anonymous,
    timeline_events: cleanedEvents,
    // Always null out the legacy markdown column when saving via the
    // structured editor — otherwise an old job's markdown would shadow
    // the freshly-entered structured timeline in the viewer fallback.
    timeline_md: null,
  }
  // Attribution is admin-only; the backend ignores it for members (their
  // subject is always themselves). Split the single field back out: a number
  // is a roster member, a non-empty string is a free-text name.
  if (auth.isActuallyAdmin) {
    if (typeof form.subject === 'number') {
      payload.subject_member_id = form.subject
      payload.real_name = null
    } else if (typeof form.subject === 'string' && form.subject.trim()) {
      payload.subject_member_id = null
      payload.real_name = form.subject.trim()
    } else {
      payload.subject_member_id = null
      payload.real_name = null
    }
  }
  return payload
}

async function handleSubmit() {
  if (!formRef.value) return

  // Guard the required text / picker fields manually. el-form-item's
  // validate() is unreliable for the autocomplete-bound company input,
  // the MdEditor-bound experience field, and the date-picker-bound
  // year-month — none of them trigger the form-item event hooks the
  // way a plain el-input does.
  if (
    !form.company.trim() ||
    !form.experience_md.trim() ||
    !form.job_year ||
    !form.job_month
  ) {
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
      // currentJob covers both the "opened in edit mode" case (props.job
      // populated) and the "created earlier in this session" case
      // (createdJob populated by the POST branch below).
      await jobsApi.update(currentJob.value.id, payload)
      toast.close()
      ElMessage.success('已更新求職紀錄')
      emit('saved')
      close()
    } else {
      const created = await jobsApi.create(payload)
      toast.close()
      // Stay in the dialog so the user can drop files into the
      // attachments tab against the freshly-issued id. Tell the parent
      // list to refresh now (don't wait for close) so the new record
      // appears in the index immediately.
      createdJob.value = created
      activeTab.value = 'attachments'
      emit('saved')
      ElMessage.success('已新增，現在可上傳附件')
    }
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
    width="880"
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
      <div class="form-row-inline">
        <el-form-item label="類型" prop="kind">
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

        <el-form-item label="匿名發表" class="form-real-name-item">
          <div class="anon-row">
            <el-switch v-model="form.is_anonymous" data-test="form-anonymous" />
            <span class="anon-hint">開啟後，非管理員看不到發表者姓名</span>
          </div>
        </el-form-item>

        <el-form-item label="求職年月" prop="job_year">
          <el-date-picker
            v-model="jobYearMonth"
            type="month"
            format="YYYY / MM"
            placeholder="選擇年月"
            :disabled-date="isJobYearMonthDisabled"
            data-test="form-job-year-month"
            class="form-year-month"
          />
        </el-form-item>
      </div>

      <!-- Admin attribution on its own row: the allow-create select has a
           variable width, so keeping it out of the inline row above stops it
           from re-wrapping (and visually jumping) when it gains focus. -->
      <el-form-item
        v-if="auth.isActuallyAdmin"
        label="歸屬對象（選填）"
        class="form-subject-item"
      >
        <el-select
          v-model="form.subject"
          filterable
          clearable
          allow-create
          default-first-option
          placeholder="選名冊成員，或直接輸入姓名（可留空）"
          class="form-subject-select"
          data-test="form-subject-member"
        >
          <el-option
            v-for="o in subjectOptions"
            :key="o.value"
            :value="o.value"
            :label="o.label"
          />
        </el-select>
        <p class="subject-hint">
          選成員會連到其個人檔案；輸入非成員姓名則只顯示文字。
        </p>
      </el-form-item>

      <div class="form-row-inline form-company-row">
        <el-form-item label="公司" prop="company" class="form-company-item">
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

        <el-form-item
          label="職類（選填）"
          prop="category"
          class="form-category-item"
        >
          <el-autocomplete
            v-model="form.category"
            :fetch-suggestions="fetchCategorySuggestions"
            :trigger-on-focus="true"
            placeholder="例如：Backend、DevOps、R&D"
            maxlength="64"
            show-word-limit
            data-test="form-category"
            class="form-category"
          />
        </el-form-item>
      </div>

      <el-form-item prop="experience_md" :show-message="false">
        <el-tabs v-model="activeTab" class="md-tabs">
          <el-tab-pane label="心得" name="experience">
            <button
              v-if="isMobileWidth && !isExperienceFullscreen"
              type="button"
              class="md-expand-btn"
              data-test="expand-experience-button"
              @click="expandEditor('experience')"
            >
              <el-icon :size="14"><FullScreen /></el-icon>
              展開編輯
            </button>
            <MdEditor
              ref="experienceEditorRef"
              v-model="form.experience_md"
              theme="light"
              language="zh-TW"
              :preview="false"
              :toolbars="editorToolbars"
              :sanitize="sanitizeHtml"
              data-test="form-experience-md"
            />
            <p v-if="!form.experience_md.trim()" class="md-required-hint">
              心得為必填
            </p>
          </el-tab-pane>
          <el-tab-pane label="時程表（選填）" name="timeline">
            <TimelineEditor
              v-model="form.timeline_events"
              :default-date="timelineDefaultDate"
              data-test="form-timeline-editor"
            />
          </el-tab-pane>
          <el-tab-pane
            name="attachments"
            :disabled="!isEdit"
            data-test="tab-attachments"
          >
            <!-- Custom label so we can wrap a tooltip around the
                 disabled state. el-tab-pane's disabled flag stops
                 activation but doesn't tell the user *why*; the
                 tooltip mirrors the locked-placeholder copy in a
                 hover-discoverable spot. -->
            <template #label>
              <el-tooltip
                v-if="!isEdit"
                content="先按「新增」建立紀錄後可上傳附件"
                placement="top"
                :show-after="200"
                data-test="attachments-tab-tooltip"
              >
                <span>附件</span>
              </el-tooltip>
              <span v-else>附件</span>
            </template>
            <!-- :key forces a fresh manager (and a fresh GET) every
                 time the dialog opens, so the manager picks up server
                 state added between sessions — including the previous
                 job's attachments not bleeding through. -->
            <JobAttachmentsManager
              v-if="isEdit"
              :key="`${currentJob.id}-${openCounter}`"
              :job-id="currentJob.id"
            />
            <div
              v-else
              class="attachments-locked"
              data-test="attachments-locked"
            >
              <p class="attachments-locked-title">先儲存基本資料</p>
              <p class="attachments-locked-sub">
                按下方「新增」建立紀錄後即可上傳附件。
              </p>
            </div>
          </el-tab-pane>
        </el-tabs>
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="close">{{ createdJob ? '關閉' : '取消' }}</el-button>
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
     up most of the height. overflow-x clamps so the markdown editor's
     wide toolbar can never push the dialog wider than its declared
     width. */
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
  overflow-x: hidden;
}

.form-company,
.form-category {
  width: 100%;
}

.form-year-month {
  width: 220px;
}

/* Desktop: pack 類型 / 本名 / 求職年月 on one row. Real-name flexes to
   absorb leftover width so the row stays balanced. The wrapper gets
   its own margin-bottom because we zero out the inner form-items'
   margins to keep the three labels on the same baseline.

   row-gap is split out from column-gap so that when the row wraps to
   a vertical stack (narrow desktop or stacked next to another inline
   row), each item is exactly one between-row rhythm apart instead of
   inheriting the much larger horizontal gap. 22px = wrapper's
   margin-bottom (18) + parent form's gap (4), so inside-wrap rhythm
   matches between-wrapper rhythm. */
.form-row-inline {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  column-gap: 32px;
  row-gap: 22px;
  margin-bottom: 18px;
}

.form-row-inline :deep(.el-form-item) {
  margin-bottom: 0;
}

.form-real-name-item {
  flex: 1;
  min-width: 200px;
}

.anon-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.anon-hint {
  font-size: 12px;
  color: var(--ink-500);
}

.form-subject-item {
  max-width: 460px;
}

.form-subject-select {
  width: 100%;
}

.subject-hint {
  margin: 4px 0 0;
  font-size: 12px;
  line-height: 1.4;
  color: var(--ink-500);
}

/* Equal-width 1:1 split for the company / category pair on desktop.
   form-row-inline's flex-wrap takes care of stacking once a side
   shrinks below the min-width, and the 640px breakpoint forces the
   column layout for phones. */
.form-company-item,
.form-category-item {
  flex: 1;
  min-width: 200px;
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
  transition:
    background-color var(--dur) var(--ease),
    color var(--dur) var(--ease),
    box-shadow var(--dur) var(--ease);
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
  color: var(--kind-internship-ink);
}

.kind-option--fulltime.is-active {
  color: var(--kind-fulltime-ink);
}

/* ---------- Markdown editor tabs ---------- */

/* el-tabs / el-tab-pane / el-form-item__content all need to be flex
   children that stretch — otherwise the editor sits at its content's
   natural width and leaves dead space on the right of the dialog. */
.md-tabs,
.md-tabs :deep(.el-tabs__content),
.md-tabs :deep(.el-tab-pane) {
  width: 100%;
}

.md-tabs :deep(.el-tabs__nav-wrap)::after {
  height: 1px;
  background: rgba(15, 23, 42, 0.06);
}

.md-tabs :deep(.el-tabs__item) {
  font-weight: 500;
}

.md-tabs :deep(.el-tabs__item.is-active) {
  color: var(--brand-primary-hover);
}

.md-tabs :deep(.el-tabs__active-bar) {
  background: linear-gradient(
    135deg,
    var(--brand-primary),
    var(--brand-accent)
  );
}

/* Cap editor height so the dialog stays scroll-friendly even with long
   markdown — the editor itself scrolls internally past the cap. The
   width clamps stop the toolbar's natural width from expanding the
   dialog past its declared width, and !important is needed because
   md-editor's own stylesheet sets a default width that wins on
   specificity. */
:deep(.md-editor) {
  width: 100% !important;
  min-width: 0;
  max-width: 100%;
  height: 360px;
}

/* Toolbar can have ~20 icons; let it scroll horizontally inside the
   editor instead of pushing the editor (and the dialog) wider. */
:deep(.md-editor-toolbar-wrapper) {
  overflow-x: auto;
}

/* CodeMirror by default uses `white-space: pre`, which sends long
   typed lines past the editor's right edge instead of wrapping. Force
   wrapping so users can always see what they're typing without having
   to scroll the editor sideways. */
:deep(.cm-editor .cm-content),
:deep(.cm-editor .cm-line) {
  white-space: pre-wrap !important;
  word-break: break-word;
}

:deep(.cm-editor .cm-scroller) {
  overflow-x: hidden;
}

/* Mobile-only "expand to fullscreen" affordance. md-editor-v3's own
   toolbar is too cramped on phones to discover the fullscreen icon
   reliably, so we hoist a finger-friendly button just above the
   editor for the same action. */
.md-expand-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
  padding: 8px 14px;
  border: 1px solid rgba(99, 102, 241, 0.32);
  border-radius: 999px;
  background: rgba(99, 102, 241, 0.08);
  color: var(--brand-primary-hover);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: background-color var(--dur) var(--ease);
}

.md-expand-btn:active {
  background: rgba(99, 102, 241, 0.16);
}

.md-required-hint {
  margin: 4px 0 0;
  color: #f56c6c;
  font-size: 12px;
}

/* Placeholder inside the attachments tab while we're still in "new"
   mode — the manager can't mount until POST returns an id, so we
   explain why instead of leaving an empty pane. */
.attachments-locked {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 36px 16px;
  text-align: center;
  color: var(--ink-500, #64748b);
}

.attachments-locked-title {
  margin: 0;
  font-size: 14px;
  font-weight: 500;
  color: var(--ink-700, #334155);
}

.attachments-locked-sub {
  margin: 0;
  font-size: 12px;
}

@media (max-width: 640px) {
  .form-row-inline {
    flex-direction: column;
    align-items: stretch;
    /* Match the 22px between-wrapper rhythm so the column-mode stack
       doesn't read as tighter than the gaps between adjacent rows. */
    gap: 22px;
  }

  :deep(.md-editor) {
    height: 280px;
  }

  /* Beef up touch targets on phones so toolbar buttons are easier
     to hit between thumbs. */
  :deep(.md-editor-toolbar-item) {
    padding: 8px 10px !important;
  }
}
</style>
