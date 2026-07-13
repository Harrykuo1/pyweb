<script setup>
import { computed, ref, watch } from 'vue'
import {
  ElButton,
  ElDialog,
  ElEmpty,
  ElIcon,
  ElTabPane,
  ElTabs,
} from 'element-plus'
import {
  Calendar,
  Edit,
  OfficeBuilding,
  School,
  User,
} from '@element-plus/icons-vue'
import { MdPreview } from 'md-editor-v3'
import { sanitizeHtml } from '../../utils/sanitizeHtml'
import 'md-editor-v3/lib/preview.css'

import JobAttachmentsViewer from './JobAttachmentsViewer.vue'
import TimelineDisplay from '../TimelineDisplay.vue'
import CommentThread from '../CommentThread.vue'
import LikeButton from '../LikeButton.vue'
import LikersDialog from '../LikersDialog.vue'
import { useAuthStore } from '../../stores/auth'
import { useLikeToggle } from '../../composables/useLikeToggle'
import { jobsApi } from '../../api/jobs'

const auth = useAuthStore()

const props = defineProps({
  modelValue: { type: Boolean, required: true },
  job: { type: Object, default: null },
})

const emit = defineEmits(['update:modelValue', 'edit', 'like-changed'])

// Comment API bound to jobs, handed to the generic CommentThread.
const commentApi = {
  list: (id) => jobsApi.listComments(id),
  create: (id, body) => jobsApi.createComment(id, body),
  update: (id, cid, body) => jobsApi.updateComment(id, cid, body),
  remove: (id, cid, password) => jobsApi.removeComment(id, cid, password),
}

// ---- likes ----
const {
  isLiked,
  likeCount,
  pending: likePending,
  toggle: toggleLike,
  sync: syncLike,
} = useLikeToggle({
  liked: props.job?.liked_by_me,
  count: props.job?.like_count,
  like: () => jobsApi.like(props.job.id),
  unlike: () => jobsApi.unlike(props.job.id),
})

const likersOpen = ref(false)
const likers = ref([])
const likersLoading = ref(false)

watch(
  () => props.job,
  (job) => {
    syncLike(job?.liked_by_me, job?.like_count)
    likersOpen.value = false
    likers.value = []
  },
)

async function onToggleLike() {
  if (!props.job) return
  await toggleLike()
  emit('like-changed', {
    id: props.job.id,
    liked: isLiked.value,
    likeCount: likeCount.value,
  })
}

async function openLikers() {
  if (!props.job) return
  likersOpen.value = true
  likersLoading.value = true
  try {
    likers.value = await jobsApi.listLikers(props.job.id)
  } catch {
    likers.value = []
  } finally {
    likersLoading.value = false
  }
}

const KIND_META = {
  internship: { label: '實習', cls: 'kind-internship' },
  fulltime: { label: '正職', cls: 'kind-fulltime' },
}

// Only non-accepted posts show a status pill (accepted = normal public
// state). The owner/admin are the only ones the backend ever sends a
// non-accepted post to.
const STATUS_META = {
  pending: { label: '審核中', cls: 'is-pending' },
  rejected: { label: '已退回', cls: 'is-rejected' },
}

const tab = ref('experience')

// Anonymous posts stay masked as 匿名 by default — even for an admin, whom
// the backend does send the real name — so it can't leak while presenting.
// The admin can reveal it per-open with an explicit click; it re-masks on
// close so a revealed name never lingers.
const revealName = ref(false)
// Revealing an anonymous author is a real-admin power; hide it while an admin
// is previewing as a member (auth.isAdmin is false then) so the preview can't
// unmask names a member could never see.
const canRevealAnon = computed(
  () => !!(props.job?.is_anonymous && props.job?.display_name && auth.isAdmin),
)
const showRealName = computed(
  () =>
    !!props.job?.display_name && (!props.job?.is_anonymous || revealName.value),
)
const shownName = computed(() =>
  showRealName.value ? props.job.display_name : '匿名',
)

// Bumped on every dialog open so the attachments viewer's :key
// changes, forcing a fresh GET. Without this the lazy-rendered tab
// pane caches its first list and the user has to F5 after uploading
// an attachment from the edit form to see it appear here.
const openCounter = ref(0)

// New jobs use timeline_events (structured rows). hasTimelineEvents is
// the preferred path; the legacy timeline_md branch only matters for
// rows that haven't been re-saved through the structured editor since
// the migration.
const hasTimelineEvents = computed(
  () =>
    Array.isArray(props.job?.timeline_events) &&
    props.job.timeline_events.length > 0,
)
const hasLegacyTimelineMd = computed(
  () => !!props.job?.timeline_md && props.job.timeline_md.trim().length > 0,
)
const hasTimeline = computed(
  () => hasTimelineEvents.value || hasLegacyTimelineMd.value,
)

// Mirror the timeline behavior: tab only shows when there's content
// to look at. attachment_count is populated by the jobs API; default
// to 0 if the field is absent (defensive in case an older cached job
// object slips through without it).
const hasAttachments = computed(() => (props.job?.attachment_count ?? 0) > 0)

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      tab.value = 'experience'
      openCounter.value += 1
      revealName.value = false
    }
  },
)

function close() {
  emit('update:modelValue', false)
}

function onEditClick() {
  emit('edit', props.job)
  close()
}

function formatDate(iso) {
  if (!iso) return '-'
  return new Date(iso).toLocaleDateString('zh-TW', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  })
}

function formatJobYearMonth(j) {
  if (!j?.job_year) return '-'
  const m = j.job_month
  return m ? `${j.job_year}/${String(m).padStart(2, '0')}` : `${j.job_year}`
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    width="760"
    top="6vh"
    :teleported="false"
    :show-close="true"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <template #header>
      <div
        v-if="job"
        class="detail-header"
        :class="`detail-header--${job.kind}`"
      >
        <div class="header-row-1">
          <span class="kind-badge" :data-test="`detail-kind-${job.kind}`">
            <span class="kind-dot" aria-hidden="true"></span>
            {{ KIND_META[job.kind]?.label ?? job.kind }}
          </span>
          <span
            v-if="job.category"
            class="category-chip"
            data-test="detail-category"
          >
            {{ job.category }}
          </span>
          <span
            v-if="STATUS_META[job.status]"
            class="status-pill"
            :class="STATUS_META[job.status].cls"
            :data-test="`detail-status-${job.status}`"
          >
            {{ STATUS_META[job.status].label }}
          </span>
        </div>
        <h2 class="detail-company" data-test="detail-company">
          <el-icon class="company-icon" :size="18"><OfficeBuilding /></el-icon>
          {{ job.company }}
        </h2>
        <div class="detail-meta">
          <span
            class="meta-name"
            :class="{ 'is-anonymous': !showRealName }"
            :data-test="showRealName ? 'detail-real-name' : 'detail-anonymous'"
          >
            <el-icon :size="13"><User /></el-icon>
            {{ shownName }}
          </span>
          <span
            v-if="job.is_anonymous"
            class="anon-badge"
            data-test="detail-anon-badge"
          >
            🔒 對外匿名
          </span>
          <button
            v-if="canRevealAnon"
            type="button"
            class="anon-reveal"
            data-test="anon-reveal"
            @click="revealName = !revealName"
          >
            {{ revealName ? '隱藏本名' : '顯示本名' }}
          </button>
          <span class="meta-year">
            <el-icon :size="13"><School /></el-icon>
            {{ formatJobYearMonth(job) }} 求職
          </span>
          <span class="meta-date">
            <el-icon :size="13"><Calendar /></el-icon>
            {{ formatDate(job.created_at) }}
          </span>
        </div>
      </div>
    </template>

    <div v-if="!job" class="detail-empty">
      <el-empty description="無資料" />
    </div>

    <template v-else>
      <p
        v-if="job.status === 'rejected' && job.review_reason"
        class="reject-banner"
        data-test="detail-reject-reason"
      >
        退回原因：{{ job.review_reason }}
      </p>

      <el-tabs v-model="tab" class="detail-tabs">
        <el-tab-pane label="心得" name="experience">
          <div class="md-frame" data-test="detail-experience">
            <MdPreview
              :model-value="job.experience_md ?? ''"
              theme="light"
              preview-theme="default"
              language="zh-TW"
              :sanitize="sanitizeHtml"
            />
          </div>
        </el-tab-pane>
        <el-tab-pane v-if="hasTimeline" label="時程表" name="timeline">
          <div class="md-frame" data-test="detail-timeline">
            <TimelineDisplay
              v-if="hasTimelineEvents"
              :events="job.timeline_events"
            />
            <div v-else data-test="detail-timeline-legacy">
              <p class="legacy-timeline-badge">
                ⚠ 舊版時程表（編輯這筆紀錄即可升級為結構化時程）
              </p>
              <MdPreview
                :model-value="job.timeline_md ?? ''"
                theme="light"
                preview-theme="default"
                language="zh-TW"
                :sanitize="sanitizeHtml"
              />
            </div>
          </div>
        </el-tab-pane>
        <el-tab-pane
          v-if="hasAttachments"
          label="附件"
          name="attachments"
          lazy
          data-test="detail-tab-attachments"
        >
          <div class="md-frame" data-test="detail-attachments">
            <!-- :key forces a fresh component (and a fresh GET) every
               time the dialog opens, so attachments uploaded in the
               edit form between opens appear without a manual F5. -->
            <JobAttachmentsViewer
              :key="`${job.id}-${openCounter}`"
              :job-id="job.id"
            />
          </div>
        </el-tab-pane>
      </el-tabs>

      <CommentThread :post-id="job.id" :api="commentApi" :active="modelValue" />
    </template>

    <template #footer>
      <div class="footer-row">
        <LikeButton
          :liked="isLiked"
          :count="likeCount"
          :pending="likePending"
          @toggle="onToggleLike"
          @show-likers="openLikers"
        />
        <slot name="footer-extra" />
        <div class="footer-spacer" />
        <el-button
          v-if="job?.can_edit"
          :icon="Edit"
          plain
          data-test="detail-edit-button"
          @click="onEditClick"
        >
          編輯
        </el-button>
        <el-button @click="close">關閉</el-button>
      </div>
    </template>
  </el-dialog>

  <LikersDialog
    v-model="likersOpen"
    :likers="likers"
    :loading="likersLoading"
  />
</template>

<style scoped>
/* ---------- Header ---------- */
.detail-header {
  --header-from: #6366f1;
  --header-to: #8b5cf6;
  --header-soft: rgba(99, 102, 241, 0.16);
  --header-ink: #4f46e5;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 4px 4px 8px;
  border-bottom: none;
}

.detail-header--internship {
  --header-from: var(--kind-internship-from);
  --header-to: var(--kind-internship-to);
  --header-soft: var(--kind-internship-soft);
  --header-ink: var(--kind-internship-ink);
}

.detail-header--fulltime {
  --header-from: var(--kind-fulltime-from);
  --header-to: var(--kind-fulltime-to);
  --header-soft: var(--kind-fulltime-soft);
  --header-ink: var(--kind-fulltime-ink);
}

.header-row-1 {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.kind-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  padding: 4px 10px 4px 8px;
  border-radius: 999px;
  background: var(--header-soft);
  color: var(--header-ink);
}

.category-chip {
  display: inline-flex;
  align-items: center;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.06);
  color: var(--ink-700);
}

.status-pill {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.04em;
  padding: 3px 9px;
  border-radius: 999px;
  white-space: nowrap;
}

.status-pill.is-pending {
  background: var(--accent-warm-soft, #fef3c7);
  color: var(--accent-warm-ink, #b45309);
}

.status-pill.is-rejected {
  background: #fee2e2;
  color: #b91c1c;
}

.reject-banner {
  margin: 4px 0 0;
  padding: 10px 14px;
  background: #fef2f2;
  border-left: 3px solid #ef4444;
  border-radius: 4px;
  font-size: 13px;
  color: #b91c1c;
}

.kind-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--header-from), var(--header-to));
  box-shadow: 0 0 0 2px rgba(255, 255, 255, 0.85);
}

.detail-company {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.015em;
  color: var(--ink-900);
  display: flex;
  align-items: center;
  gap: 8px;
}

.company-icon {
  color: var(--header-ink);
  opacity: 0.65;
}

.detail-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  font-size: 13px;
  color: var(--ink-500);
}

.meta-name,
.meta-year,
.meta-date {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.meta-name.is-anonymous {
  font-style: italic;
  color: var(--ink-400, #94a3b8);
}

.anon-badge {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  padding: 1px 8px;
  border-radius: 999px;
  font-size: 12px;
  background: rgba(15, 23, 42, 0.06);
  color: var(--ink-500);
}

.anon-reveal {
  appearance: none;
  border: 0;
  background: transparent;
  padding: 0;
  cursor: pointer;
  font: inherit;
  font-size: 12px;
  color: var(--brand-primary);
  text-decoration: underline;
}

.anon-reveal:hover {
  opacity: 0.8;
}

.meta-year {
  color: var(--header-ink);
  font-weight: 600;
}

/* ---------- Tabs ---------- */
.detail-tabs :deep(.el-tabs__nav-wrap)::after {
  height: 1px;
  background: rgba(15, 23, 42, 0.06);
}

.detail-tabs :deep(.el-tabs__item) {
  font-weight: 500;
}

.detail-tabs :deep(.el-tabs__item.is-active) {
  color: var(--brand-primary-hover);
}

.detail-tabs :deep(.el-tabs__active-bar) {
  background: linear-gradient(
    135deg,
    var(--brand-primary),
    var(--brand-accent)
  );
}

.md-frame {
  /* The outer .el-dialog__body now caps height and scrolls internally
     (see style.css). A second scroll container here just produced a
     nested scrollbar inside the dialog. */
  padding: 12px 4px;
}

/* Tame md-editor-v3's preview surface so it sits cleanly inside the
   dialog without its own border/background fighting the theme. */
.md-frame :deep(.md-editor-preview) {
  background: transparent;
  padding: 0;
}

/* md-editor-v3's default heading rhythm (margin: 1.4em 0 .8em) leaves
   a visually disconnected gap between an h1 and the paragraph below.
   Tighten it so the section header feels attached to its content. */
.md-frame :deep(.md-editor-preview h1),
.md-frame :deep(.md-editor-preview h2),
.md-frame :deep(.md-editor-preview h3),
.md-frame :deep(.md-editor-preview h4),
.md-frame :deep(.md-editor-preview h5),
.md-frame :deep(.md-editor-preview h6) {
  margin: 0.7em 0 0.35em;
}

.md-frame :deep(.md-editor-preview > :first-child) {
  margin-top: 0;
}

/* ---------- Footer ---------- */
.footer-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.footer-spacer {
  flex: 1;
}

.detail-empty {
  padding: 32px 0;
}

.legacy-timeline-badge {
  margin: 0 0 12px;
  padding: 8px 12px;
  background: rgba(245, 158, 11, 0.1);
  border-left: 3px solid #f59e0b;
  border-radius: 4px;
  font-size: 12px;
  color: #92400e;
}

@media (max-width: 640px) {
  .detail-company {
    font-size: 18px;
  }
}
</style>
