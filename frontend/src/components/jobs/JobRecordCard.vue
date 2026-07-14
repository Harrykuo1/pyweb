<script setup>
import { ref, watch } from 'vue'
import { ElIcon } from 'element-plus'
import { Calendar, OfficeBuilding, School, User } from '@element-plus/icons-vue'

import LikeButton from '../LikeButton.vue'
import { jobsApi } from '../../api/jobs'
import { useLikeToggle } from '../../composables/useLikeToggle'

const props = defineProps({
  job: { type: Object, required: true },
})
const emit = defineEmits(['open', 'like-changed'])

// Like straight from the card. Local optimistic state (never mutate the prop);
// after it settles we emit like-changed so the parent patches the list row.
const {
  isLiked,
  likeCount,
  pending: likePending,
  toggle: toggleLike,
  sync: syncLike,
} = useLikeToggle({
  liked: props.job.liked_by_me,
  count: props.job.like_count,
  like: () => jobsApi.like(props.job.id),
  unlike: () => jobsApi.unlike(props.job.id),
})

// Keep in step if the parent updates the row (e.g. liked from the detail
// dialog) — the parent patches props.job, we re-sync local state.
watch(
  () => [props.job.liked_by_me, props.job.like_count],
  ([liked, count]) => syncLike(liked, count),
)

async function onLike() {
  await toggleLike()
  emit('like-changed', {
    id: props.job.id,
    liked: isLiked.value,
    likeCount: likeCount.value,
  })
}

const KIND_META = {
  internship: { label: '實習' },
  fulltime: { label: '正職' },
}

// Only non-accepted posts get a status pill — accepted is the normal public
// state. The backend only ever sends a viewer their own pending/rejected
// posts (or everything, to an admin), so showing it unconditionally is safe.
const STATUS_META = {
  pending: { label: '審核中', cls: 'is-pending' },
  rejected: { label: '已退回', cls: 'is-rejected' },
}

// Marquee-on-hover for the category chip when its text overflows. Each
// card owns its own state — a boolean plus a template ref to the chip —
// instead of the parent tracking a Set keyed by id and reaching in with
// querySelector. Single-direction loop via a dual-copy: a ghost follows
// the primary with a fixed gap; the content translates from 0 to
// -(textWidth + gap), at which point the ghost sits where the primary
// started, so the animation jumps back to 0 seamlessly.
const CHIP_PADDING_X = 20 // 10px each side, must mirror .category-chip padding
const CHIP_GAP = 24 // .category-chip-text--ghost padding-left

const chipRef = ref(null)
const marqueeing = ref(false)

function onHover() {
  const chip = chipRef.value
  if (!chip) return
  // chip.scrollWidth includes left+right padding; subtract to get the text
  // content width. Default-state text is inline so its own offsetWidth is
  // unreliable.
  const textWidth = chip.scrollWidth - CHIP_PADDING_X
  if (textWidth <= chip.clientWidth - CHIP_PADDING_X + 1) return // no overflow
  const distance = textWidth + CHIP_GAP
  const duration = Math.max(3, distance / 30) // ~30px/sec for slow read
  chip.style.setProperty('--marquee-distance', `-${distance}px`)
  chip.style.setProperty('--marquee-duration', `${duration}s`)
  marqueeing.value = true
}

function onLeave() {
  marqueeing.value = false
  const chip = chipRef.value
  if (!chip) return
  chip.style.removeProperty('--marquee-distance')
  chip.style.removeProperty('--marquee-duration')
}

// Anonymous posts show 匿名 to everyone here — the backend still sends
// admins the real name, but the list must never render it (it could leak
// while presenting/streaming); the real name is revealable in the detail.
function isMasked(item) {
  return item.is_anonymous || !item.display_name
}

function displayNameOrAnonymous(item) {
  return isMasked(item) ? '匿名' : item.display_name
}

function formatJobYearMonth(item) {
  if (!item?.job_year) return '-'
  const m = item.job_month
  return m
    ? `${item.job_year}/${String(m).padStart(2, '0')}`
    : `${item.job_year}`
}

function formatDate(iso) {
  if (!iso) return '-'
  return new Date(iso).toLocaleDateString('zh-TW', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  })
}
</script>

<template>
  <article
    :class="['record-card', `record-card--${job.kind}`]"
    data-test="record-card"
    role="button"
    tabindex="0"
    @click="$emit('open', job)"
    @keydown.enter="$emit('open', job)"
    @keydown.space.prevent="$emit('open', job)"
    @mouseenter="onHover"
    @mouseleave="onLeave"
  >
    <span class="card-stripe" aria-hidden="true"></span>
    <span class="card-glow" aria-hidden="true"></span>

    <div class="card-like" data-test="card-like" @click.stop @keydown.stop>
      <LikeButton
        :liked="isLiked"
        :count="likeCount"
        :pending="likePending"
        @toggle="onLike"
        @show-likers="emit('open', job)"
      />
    </div>

    <div class="card-tags">
      <span class="kind-badge" :data-test="`kind-${job.kind}`">
        <span class="kind-dot" aria-hidden="true"></span>
        {{ KIND_META[job.kind]?.label ?? job.kind }}
      </span>
      <span
        v-if="job.category"
        ref="chipRef"
        class="category-chip"
        data-test="card-category"
        :class="{ 'is-marqueeing': marqueeing }"
      >
        <span class="category-chip-text">{{ job.category }}</span>
        <span
          v-if="marqueeing"
          class="category-chip-text category-chip-text--ghost"
          aria-hidden="true"
          >{{ job.category }}</span
        >
      </span>
      <span
        v-if="STATUS_META[job.status]"
        class="status-pill"
        :class="STATUS_META[job.status].cls"
        :data-test="`status-${job.status}`"
      >
        {{ STATUS_META[job.status].label }}
      </span>
    </div>

    <h3 class="card-company">
      <el-icon class="company-icon" :size="14"><OfficeBuilding /></el-icon>
      <span class="company-text">{{ job.company }}</span>
    </h3>

    <p
      :class="['card-name', { 'is-anonymous': isMasked(job) }]"
      :data-test="isMasked(job) ? 'anonymous' : 'real-name'"
    >
      <el-icon :size="12"><User /></el-icon>
      {{ displayNameOrAnonymous(job) }}
    </p>

    <div class="card-meta">
      <span class="meta-year">
        <el-icon :size="12"><School /></el-icon>
        {{ formatJobYearMonth(job) }} 求職
      </span>
      <span class="meta-date">
        <el-icon :size="12"><Calendar /></el-icon>
        {{ formatDate(job.created_at) }} 發佈
      </span>
    </div>
  </article>
</template>

<style scoped>
.record-card {
  --card-accent-from: var(--brand-primary);
  --card-accent-to: var(--brand-accent);
  --card-accent-soft: rgba(99, 102, 241, 0.18);
  --card-accent-ink: var(--brand-primary-hover);

  position: relative;
  overflow: hidden;
  background: var(--surface-0);
  border: 1px solid rgba(15, 23, 42, 0.06);
  border-radius: var(--radius-lg);
  padding: 20px 20px 18px 26px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  isolation: isolate;
  cursor: pointer;
  transition:
    transform var(--dur) var(--ease),
    box-shadow var(--dur) var(--ease),
    border-color var(--dur) var(--ease);
}

.record-card--internship {
  --card-accent-from: var(--kind-internship-from);
  --card-accent-to: var(--kind-internship-to);
  --card-accent-soft: var(--kind-internship-soft);
  --card-accent-ink: var(--kind-internship-ink);
}

.record-card--fulltime {
  --card-accent-from: var(--kind-fulltime-from);
  --card-accent-to: var(--kind-fulltime-to);
  --card-accent-soft: var(--kind-fulltime-soft);
  --card-accent-ink: var(--kind-fulltime-ink);
}

.record-card::before {
  content: '';
  position: absolute;
  inset: -2px;
  border-radius: inherit;
  background: linear-gradient(
    135deg,
    var(--card-accent-from),
    var(--card-accent-to)
  );
  opacity: 0;
  z-index: -1;
  transition: opacity var(--dur) var(--ease);
  filter: blur(14px);
}

.record-card:hover {
  transform: translateY(-4px);
  border-color: var(--card-accent-soft);
  box-shadow: 0 18px 42px -16px rgba(15, 23, 42, 0.18);
}

.record-card:focus-visible {
  outline: 2px solid var(--card-accent-from);
  outline-offset: 3px;
}

.record-card:hover::before {
  opacity: 0.18;
}

.card-stripe {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 4px;
  background: linear-gradient(
    180deg,
    var(--card-accent-from),
    var(--card-accent-to)
  );
  border-radius: 0 4px 4px 0;
  transition: width var(--dur) var(--ease);
}

.record-card:hover .card-stripe {
  width: 6px;
}

.card-glow {
  position: absolute;
  right: -20px;
  bottom: -30px;
  width: 140px;
  height: 140px;
  border-radius: 50%;
  background: radial-gradient(
    closest-side,
    var(--card-accent-soft),
    transparent 70%
  );
  pointer-events: none;
  opacity: 0.7;
  transition: opacity var(--dur) var(--ease);
}

.record-card:hover .card-glow {
  opacity: 1;
}

.card-tags {
  display: flex;
  flex-wrap: nowrap;
  align-items: center;
  gap: 6px;
  margin-bottom: 2px;
  /* Reserve room at the right so a long category/status never runs under
     the top-right like button. */
  padding-right: 46px;
  /* Allow the chip child to shrink below its intrinsic content width
     so it stays inline with .kind-badge instead of wrapping. */
  min-width: 0;
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
  background: var(--card-accent-soft);
  color: var(--card-accent-ink);
  /* Pin the kind label at full size — only the category chip should
     compress when the row runs out of room. */
  flex-shrink: 0;
}

/* Neutral, slightly recessive so the kind-badge keeps visual primacy.
   The chip sits right next to it like a secondary tag. */
.category-chip {
  /* inline-block (not inline-flex) so the chip is a text container —
     text-overflow: ellipsis applies to inline children's text content. */
  display: inline-block;
  vertical-align: middle;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.06);
  color: var(--ink-700);
  /* Required for shrink-below-content inside .card-tags' flex row. */
  min-width: 0;
  max-width: 100%;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  position: relative;
}

/* Default state: inline so the chip's text-overflow ellipsis sees the
   text as part of its own inline content and can clip with "…". */
.category-chip-text {
  display: inline;
  white-space: nowrap;
}

/* While marqueeing both copies become inline-block so they're
   transformable; ghost provides the loop seam via padding-left. */
.category-chip.is-marqueeing {
  text-overflow: clip;
}

.category-chip.is-marqueeing .category-chip-text {
  display: inline-block;
  animation: chip-marquee var(--marquee-duration, 6s) linear infinite;
}

.category-chip-text--ghost {
  /* Gap between the primary copy and its ghost; the marquee distance
     accounts for this so the ghost lands exactly where the primary
     started, hiding the iteration boundary. */
  padding-left: 24px;
}

@keyframes chip-marquee {
  0% {
    transform: translateX(0);
  }
  100% {
    transform: translateX(var(--marquee-distance, 0));
  }
}

.status-pill {
  flex-shrink: 0;
  margin-left: auto;
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

.kind-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: linear-gradient(
    135deg,
    var(--card-accent-from),
    var(--card-accent-to)
  );
  box-shadow: 0 0 0 2px rgba(255, 255, 255, 0.85);
}

.card-company {
  margin: 0;
  font-size: 19px;
  font-weight: 700;
  color: var(--ink-900);
  letter-spacing: -0.01em;
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.company-icon {
  flex-shrink: 0;
  color: var(--card-accent-ink);
  opacity: 0.55;
}

.company-text {
  background: linear-gradient(
    135deg,
    var(--ink-900) 0%,
    var(--card-accent-ink) 140%
  );
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.card-name {
  margin: 0;
  font-size: 13px;
  color: var(--ink-700);
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.card-name.is-anonymous {
  color: var(--ink-400, #94a3b8);
  font-style: italic;
}

.card-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  margin-top: auto;
  padding-top: var(--sp-sm);
  border-top: 1px dashed rgba(15, 23, 42, 0.08);
}

.card-like {
  position: absolute;
  top: 12px;
  right: 12px;
  z-index: 2;
}

.meta-year,
.meta-date {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--ink-500);
}

.meta-year {
  color: var(--card-accent-ink);
  font-weight: 600;
}

.meta-date {
  margin-left: auto;
}

@media (max-width: 640px) {
  .record-card {
    padding: 16px 16px 14px 20px;
  }

  .card-company {
    font-size: 17px;
  }
}
</style>
