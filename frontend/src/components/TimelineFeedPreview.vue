<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElIcon, ElImage } from 'element-plus'
import { ArrowRight, Briefcase, Promotion } from '@element-plus/icons-vue'

import { timelineApi } from '../api/timeline'
import { jobsApi } from '../api/jobs'
import { membersApi } from '../api/members'
import { relativeTime } from '../utils/relativeTime'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()

// A compact preview of the timeline feed designed to live inside the
// hero. Visually distinct (dark glass card on the hero gradient) and
// stripped of features that belong to the standalone full feed below
// (collapse toggle, skeleton variant, large rows). The full feed
// remains the source of truth — this is just the "highlights" tease.

const props = defineProps({
  limit: { type: Number, default: 4 },
  // DOM id to scroll to when the user clicks 查看全部. Defaults to the
  // standalone TimelineFeed below the hero.
  fullFeedAnchor: { type: String, default: 'timeline-feed-section' },
})

const router = useRouter()
const items = ref([])
const loading = ref(true)

async function load() {
  loading.value = true
  try {
    const data = await timelineApi.list({
      limit: props.limit,
      preview: auth.isPreviewingAsMember,
    })
    items.value = data.items ?? []
  } catch {
    // Hero degrades gracefully — empty state copy covers both empty DB
    // and silent failure. The standalone feed below has its own error
    // surface, so we don't need to repeat it here.
    items.value = []
  } finally {
    loading.value = false
  }
}

onMounted(load)
// Reload when the admin toggles preview-as-member.
watch(() => auth.isPreviewingAsMember, load)

function handleRowClick(item) {
  if (item.type === 'member_joined') {
    router.push(membersApi.focusRoute(item.member_id))
  } else if (item.type === 'job_created') {
    router.push(jobsApi.detailRoute(item.job_id))
  }
}

function handleKey(event, item) {
  if (event.key === 'Enter' || event.key === ' ') {
    event.preventDefault()
    handleRowClick(item)
  }
}

function scrollToFullFeed() {
  const el = document.getElementById(props.fullFeedAnchor)
  if (el && typeof el.scrollIntoView === 'function') {
    el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
}

function memberPhotoSrc(item) {
  if (!item?.has_photo) return null
  return membersApi.photoUrl(item.member_id, item.photo_updated_at ?? '')
}

function memberInitial(item) {
  const name = item?.real_name ?? ''
  return name.charAt(0) || '?'
}

const skeletonRows = computed(() => Array.from({ length: props.limit }))
</script>

<template>
  <section class="hero-feed" data-test="hero-feed">
    <header class="hero-feed-head">
      <div class="hero-feed-title-wrap">
        <span class="hero-feed-icon">
          <el-icon :size="14"><Promotion /></el-icon>
        </span>
        <h2 class="hero-feed-title">最近動態</h2>
      </div>
      <button
        type="button"
        class="hero-feed-link"
        data-test="hero-feed-link"
        @click="scrollToFullFeed"
      >
        查看全部
        <el-icon :size="11"><ArrowRight /></el-icon>
      </button>
    </header>

    <ul v-if="loading" class="hero-feed-list" data-test="hero-feed-loading">
      <li
        v-for="(_, idx) in skeletonRows"
        :key="idx"
        class="hero-feed-row hero-feed-row--skeleton"
      >
        <span class="hero-feed-avatar hero-feed-avatar--ghost"></span>
        <span class="hero-feed-text">
          <span class="sk-line sk-line-1"></span>
          <span class="sk-line sk-line-2"></span>
        </span>
      </li>
    </ul>

    <div
      v-else-if="items.length === 0"
      class="hero-feed-empty"
      data-test="hero-feed-empty"
    >
      尚無動態
    </div>

    <ul v-else class="hero-feed-list" data-test="hero-feed-list">
      <li
        v-for="item in items"
        :key="`${item.type}:${item.type === 'member_joined' ? item.member_id : item.job_id}`"
        :class="['hero-feed-row', `hero-feed-row--${item.type}`]"
        role="button"
        tabindex="0"
        :data-test="`hero-feed-row-${item.type}`"
        @click="handleRowClick(item)"
        @keydown="handleKey($event, item)"
      >
        <!-- Avatar branches:
             1. member with photo  → real headshot via <el-image>
             2. member without photo → gradient circle + first letter
             3. job_created → gradient square tinted by kind, so the
                preview's icon colour echoes the kind chip on /jobs
                even though the chip itself isn't shown here. -->
        <el-image
          v-if="item.type === 'member_joined' && item.has_photo"
          :src="memberPhotoSrc(item)"
          fit="cover"
          class="hero-feed-avatar hero-feed-avatar--photo"
          :alt="`${item.real_name} 的頭像`"
        />
        <span
          v-else-if="item.type === 'member_joined'"
          class="hero-feed-avatar hero-feed-avatar--member_joined"
          aria-hidden="true"
        >
          <span class="hero-feed-avatar-letter">
            {{ memberInitial(item) }}
          </span>
        </span>
        <span
          v-else
          :class="[
            'hero-feed-avatar',
            'hero-feed-avatar--job_created',
            `hero-feed-avatar--kind-${item.kind}`,
          ]"
          aria-hidden="true"
        >
          <el-icon :size="11"><Briefcase /></el-icon>
        </span>
        <span class="hero-feed-text">
          <span class="hero-feed-line">
            <strong class="hero-feed-name">
              {{
                item.type === 'member_joined'
                  ? item.real_name
                  : item.real_name || '匿名成員'
              }}
            </strong>
            <template v-if="item.type === 'member_joined'">
              <span class="hero-feed-verb">加入了社群</span>
            </template>
            <template v-else>
              <!-- A styled circle, not a · glyph: font-rendered middle
                   dots sit on the Latin baseline and read as "low"
                   between CJK characters. A pure box-shape with
                   vertical-align lets us centre exactly. -->
              <span class="hero-feed-dot" aria-hidden="true"></span>
              <span class="hero-feed-verb">
                新增了
                <span class="hero-feed-company">{{ item.company }}</span>
                的紀錄
              </span>
            </template>
          </span>
        </span>
        <time
          class="hero-feed-time"
          :datetime="item.timestamp"
          :title="new Date(item.timestamp).toLocaleString('zh-TW')"
        >
          {{ relativeTime(item.timestamp) }}
        </time>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.hero-feed {
  display: flex;
  flex-direction: column;
  gap: 12px;
  /* box-sizing:border-box keeps the padding inside the grid cell
     instead of bleeding past it — there's no global reset in
     this project, so it has to be explicit. */
  box-sizing: border-box;
  width: 100%;
  min-width: 0;
  padding: 18px 20px 16px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.14);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  box-shadow:
    0 12px 32px rgba(15, 23, 42, 0.22),
    0 0 0 1px rgba(255, 255, 255, 0.04) inset;
  color: #ffffff;
  height: 100%;
  min-height: 0;
}

/* ---------- Header ---------- */
.hero-feed-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.hero-feed-title-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
}

.hero-feed-icon {
  width: 24px;
  height: 24px;
  border-radius: 7px;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: #ffffff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 3px 8px rgba(99, 102, 241, 0.3);
}

.hero-feed-title {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
  color: #ffffff;
  letter-spacing: 0.02em;
}

.hero-feed-link {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 4px 8px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: rgba(255, 255, 255, 0.78);
  font-size: 11.5px;
  font-weight: 500;
  letter-spacing: 0.02em;
  cursor: pointer;
  outline: none;
  transition:
    background var(--dur) var(--ease),
    color var(--dur) var(--ease),
    transform var(--dur) var(--ease);
}

.hero-feed-link:hover,
.hero-feed-link:focus-visible {
  background: rgba(255, 255, 255, 0.1);
  color: #ffffff;
  transform: translateX(1px);
}

/* ---------- List ---------- */
.hero-feed-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
}

.hero-feed-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 6px;
  border-radius: 10px;
  cursor: pointer;
  outline: none;
  min-width: 0;
  transition:
    background var(--dur) var(--ease),
    transform var(--dur) var(--ease);
  animation: row-fade 0.32s var(--ease) backwards;
}

.hero-feed-row + .hero-feed-row {
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.hero-feed-row:hover,
.hero-feed-row:focus-visible {
  background: rgba(255, 255, 255, 0.08);
  transform: translateX(1px);
}

.hero-feed-row--skeleton {
  cursor: default;
  animation: none;
}

.hero-feed-row--skeleton:hover {
  background: transparent;
  transform: none;
}

@keyframes row-fade {
  from {
    opacity: 0;
    transform: translateY(3px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.hero-feed-row:nth-child(1) {
  animation-delay: 0ms;
}
.hero-feed-row:nth-child(2) {
  animation-delay: 50ms;
}
.hero-feed-row:nth-child(3) {
  animation-delay: 100ms;
}
.hero-feed-row:nth-child(4) {
  animation-delay: 150ms;
}
.hero-feed-row:nth-child(n + 5) {
  animation-delay: 200ms;
}

/* ---------- Avatar / type indicator ---------- */
.hero-feed-avatar {
  flex: 0 0 auto;
  width: 26px;
  height: 26px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #ffffff;
  border: 1px solid rgba(255, 255, 255, 0.12);
  box-shadow: 0 2px 6px rgba(15, 23, 42, 0.3);
}

.hero-feed-avatar--member_joined {
  background: linear-gradient(
    135deg,
    var(--brand-primary),
    var(--brand-accent)
  );
}

.hero-feed-avatar-letter {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0;
  text-transform: uppercase;
  color: #ffffff;
}

.hero-feed-avatar--photo {
  background: linear-gradient(135deg, #eef2ff, #f3e8ff);
  border-radius: 50%;
}

.hero-feed-avatar--photo :deep(img) {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

/* job_created is shape-coded (rounded square, vs member's circle) so
   the type stays disambiguated; kind only paints in the colour. */
.hero-feed-avatar--job_created {
  border-radius: 8px;
  background: linear-gradient(
    135deg,
    var(--accent-career-from),
    var(--accent-career-to)
  );
}

.hero-feed-avatar--kind-internship {
  background: linear-gradient(
    135deg,
    var(--kind-internship-from),
    var(--kind-internship-to)
  );
}

.hero-feed-avatar--kind-fulltime {
  background: linear-gradient(
    135deg,
    var(--kind-fulltime-from),
    var(--kind-fulltime-to)
  );
}

.hero-feed-avatar--ghost {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.06);
  box-shadow: none;
}

/* ---------- Text body ---------- */
.hero-feed-text {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.hero-feed-line {
  display: block;
  font-size: 12.5px;
  line-height: 1.45;
  color: rgba(255, 255, 255, 0.92);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.hero-feed-name {
  font-weight: 600;
  color: #ffffff;
}

.hero-feed-verb {
  color: rgba(255, 255, 255, 0.7);
  font-weight: 400;
  margin-left: 4px;
}

/* When the dot precedes the verb (job_created rows), it already
   carries the side-spacing — zero out the verb's leading margin
   so the gaps on either side of the dot stay symmetric. */
.hero-feed-dot + .hero-feed-verb {
  margin-left: 0;
}

.hero-feed-dot {
  display: inline-block;
  width: 3px;
  height: 3px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.5);
  /* Symmetric horizontal padding around the dot — both sides equal. */
  margin: 0 8px;
  /* vertical-align: middle aligns the dot's centre with the line's
     x-height midpoint. CJK glyphs sit slightly above that, so we
     lift by 1px more for optical centring between 王 / 新. */
  vertical-align: middle;
  transform: translateY(-1px);
}

.hero-feed-company {
  color: rgba(255, 255, 255, 0.92);
  font-weight: 500;
}

.hero-feed-time {
  flex: 0 0 auto;
  font-size: 11px;
  color: rgba(255, 255, 255, 0.55);
  letter-spacing: 0.02em;
  white-space: nowrap;
}

/* ---------- Skeleton ---------- */
.sk-line {
  display: block;
  height: 9px;
  border-radius: 5px;
  background: rgba(255, 255, 255, 0.1);
  margin-top: 4px;
  animation: sk-shimmer 1.4s ease-in-out infinite;
}

.sk-line-1 {
  width: 70%;
}

.sk-line-2 {
  width: 40%;
}

@keyframes sk-shimmer {
  0%,
  100% {
    opacity: 0.6;
  }
  50% {
    opacity: 1;
  }
}

/* ---------- Empty state ---------- */
.hero-feed-empty {
  padding: 18px 4px;
  font-size: 12.5px;
  color: rgba(255, 255, 255, 0.6);
  text-align: center;
}

/* ---------- Mobile tweaks ---------- */
@media (max-width: 640px) {
  .hero-feed {
    padding: 14px 14px 12px;
  }
  .hero-feed-line {
    font-size: 12px;
  }
  .hero-feed-time {
    font-size: 10.5px;
  }
}
</style>
