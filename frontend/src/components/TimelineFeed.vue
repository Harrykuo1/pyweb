<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  ElCollapseTransition,
  ElEmpty,
  ElIcon,
  ElImage,
  ElSkeleton,
  ElSkeletonItem,
} from 'element-plus'
import {
  ArrowDown,
  Calendar,
  Loading,
  OfficeBuilding,
  Promotion,
  UserFilled,
} from '@element-plus/icons-vue'

import { timelineApi } from '../api/timeline'
import { jobsApi } from '../api/jobs'
import { membersApi } from '../api/members'
import { relativeTime } from '../utils/relativeTime'

const props = defineProps({
  // Page size for the cursor-paginated fetch. Each request asks the
  // server for this many rows starting from the current cursor; once
  // the user scrolls near the bottom, an IntersectionObserver fires
  // and we fetch the next batch with `before = lastItem.timestamp`.
  pageSize: { type: Number, default: 20 },
})

const router = useRouter()
const items = ref([])
const loading = ref(false)        // initial fetch only
const loadingMore = ref(false)    // every fetch after the first
const hasMore = ref(false)
const errored = ref(false)

// Always-expanded by default on every page load. We deliberately don't
// persist a collapsed state — the feed is the social-discovery hook, so
// each fresh visit should surface the latest updates, even if collapsed
// it last time. The toggle still works within a session for screen-
// real-estate reasons.
const collapsed = ref(false)

// Refs the IntersectionObserver needs: the scrollable container is the
// observer root, the sentinel is the element we watch for intersection.
const listRef = ref(null)
const sentinelRef = ref(null)
let observer = null

const KIND_LABEL = {
  internship: '實習',
  fulltime: '正職',
}

async function loadInitial() {
  loading.value = true
  errored.value = false
  try {
    const data = await timelineApi.list({ limit: props.pageSize })
    items.value = data.items ?? []
    hasMore.value = Boolean(data.has_more)
  } catch (err) {
    // Auth-redirect interceptor handles 401; any other failure should
    // degrade gracefully — the home page still has its hero + cards.
    errored.value = true
    items.value = []
    hasMore.value = false
  } finally {
    loading.value = false
  }
}

async function loadMore() {
  // Three guards: don't double-fire, don't fetch past the end, don't
  // run before the first batch (we have no cursor without items).
  if (loadingMore.value || !hasMore.value || items.value.length === 0) return

  // Disconnect during the in-flight fetch so a stale "still intersecting"
  // event can't queue up another call. We rebind right after items
  // change so the observer re-evaluates against the new layout — if the
  // sentinel is still in view (e.g. fetched fewer rows than the visible
  // window can show) it'll fire again and the cascade resolves itself.
  teardownObserver()
  loadingMore.value = true
  try {
    const cursor = items.value[items.value.length - 1].timestamp
    const data = await timelineApi.list({
      limit: props.pageSize,
      before: cursor,
    })
    items.value = [...items.value, ...(data.items ?? [])]
    hasMore.value = Boolean(data.has_more)
  } catch {
    // Silent failure on lazy-load: keep what we have, hide the sentinel
    // so the observer stops firing on every scroll. The user can refresh
    // the page to retry — the standalone error surface is reserved for
    // initial-load failures, where there's nothing to show at all.
    hasMore.value = false
  } finally {
    loadingMore.value = false
  }

  await nextTick()
  setupObserver()
}

function setupObserver() {
  if (typeof IntersectionObserver === 'undefined') return
  if (collapsed.value || !hasMore.value) return
  if (!listRef.value || !sentinelRef.value) return

  observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          loadMore()
        }
      }
    },
    {
      // The list itself is the scroll container, so intersection is
      // measured against its viewport, not the page's.
      root: listRef.value,
      // Pre-fetch when the sentinel is within 200 px of the bottom edge
      // — gives the network round-trip time to finish before the user
      // actually hits the floor.
      rootMargin: '200px 0px',
      threshold: 0.01,
    },
  )
  observer.observe(sentinelRef.value)
}

function teardownObserver() {
  if (observer) {
    observer.disconnect()
    observer = null
  }
}

onMounted(async () => {
  await loadInitial()
  await nextTick()
  setupObserver()
})

onBeforeUnmount(teardownObserver)

// React to state that changes whether the observer should be running:
// collapsing hides the sentinel, has_more flipping false retires it,
// loading→false brings the real list (and its refs) into the DOM.
watch([collapsed, hasMore, loading], async () => {
  teardownObserver()
  await nextTick()
  setupObserver()
})

function toggleCollapsed() {
  collapsed.value = !collapsed.value
}

function memberAvatarUrl(item) {
  if (!item.has_photo) return null
  return membersApi.photoUrl(item.member_id, item.photo_updated_at ?? '')
}

function handleClick(item) {
  // Route shapes are owned by the destination api modules so the URL
  // schema (query keys, path) lives next to the page that consumes it
  // — see jobsApi.detailRoute / membersApi.focusRoute.
  if (item.type === 'member_joined') {
    router.push(membersApi.focusRoute(item.member_id))
  } else if (item.type === 'job_created') {
    router.push(jobsApi.detailRoute(item.job_id))
  }
}

function handleKey(event, item) {
  // a11y: rows are role=button, so Enter / Space should activate.
  if (event.key === 'Enter' || event.key === ' ') {
    event.preventDefault()
    handleClick(item)
  }
}

const skeletonRows = computed(() => Array.from({ length: 4 }))
</script>

<template>
  <section class="timeline-feed" data-test="timeline-feed">
    <header class="feed-header">
      <div class="feed-title-wrap">
        <span class="feed-title-icon">
          <el-icon :size="18"><Promotion /></el-icon>
        </span>
        <div>
          <h2 class="feed-title">社群動態</h2>
          <p class="feed-subtitle">最近的成員加入與求職紀錄</p>
        </div>
      </div>
      <button
        type="button"
        class="feed-toggle"
        :aria-expanded="!collapsed"
        aria-controls="timeline-feed-body"
        :title="collapsed ? '展開動態' : '收合動態'"
        data-test="timeline-toggle"
        @click="toggleCollapsed"
      >
        <span class="feed-toggle-label">{{ collapsed ? '展開' : '收合' }}</span>
        <el-icon
          :class="['feed-toggle-icon', { 'is-collapsed': collapsed }]"
          :size="14"
        >
          <ArrowDown />
        </el-icon>
      </button>
    </header>

    <el-collapse-transition>
      <div v-show="!collapsed" id="timeline-feed-body" class="feed-body">
        <div v-if="loading" class="feed-list" data-test="timeline-loading">
          <div
            v-for="(_, idx) in skeletonRows"
            :key="idx"
            class="feed-row is-skeleton"
          >
            <el-skeleton animated>
              <template #template>
                <div class="row-skeleton">
                  <el-skeleton-item variant="circle" class="sk-avatar" />
                  <div class="row-skeleton-text">
                    <el-skeleton-item variant="text" class="sk-line sk-line-1" />
                    <el-skeleton-item variant="text" class="sk-line sk-line-2" />
                  </div>
                  <el-skeleton-item variant="text" class="sk-time" />
                </div>
              </template>
            </el-skeleton>
          </div>
        </div>

        <div
          v-else-if="errored"
          class="feed-empty"
          data-test="timeline-error"
        >
          <el-empty description="動態載入失敗，稍後再試" :image-size="80" />
        </div>

        <div
          v-else-if="items.length === 0"
          class="feed-empty"
          data-test="timeline-empty"
        >
          <el-empty
            description="目前還沒有動態，新增成員或求職紀錄後會顯示在這裡"
            :image-size="80"
          />
        </div>

        <ul
          v-else
          ref="listRef"
          class="feed-list"
          data-test="timeline-list"
        >
          <li
            v-for="item in items"
            :key="`${item.type}:${item.type === 'member_joined' ? item.member_id : item.job_id}`"
            :class="['feed-row', `feed-row--${item.type}`]"
            role="button"
            tabindex="0"
            :data-test="`timeline-row-${item.type}`"
            @click="handleClick(item)"
            @keydown="handleKey($event, item)"
          >
            <!-- ---------- avatar ---------- -->
            <template v-if="item.type === 'member_joined'">
              <el-image
                v-if="item.has_photo"
                :src="memberAvatarUrl(item)"
                fit="cover"
                class="row-avatar row-avatar--photo"
                :alt="`${item.real_name} 的照片`"
              />
              <span
                v-else
                class="row-avatar row-avatar--member"
                :title="item.real_name"
                aria-hidden="true"
              >
                <el-icon :size="18"><UserFilled /></el-icon>
              </span>
            </template>
            <span
              v-else
              :class="[
                'row-avatar',
                'row-avatar--job',
                `row-avatar--kind-${item.kind}`,
              ]"
              aria-hidden="true"
            >
              <el-icon :size="18"><OfficeBuilding /></el-icon>
            </span>

            <!-- ---------- main text ---------- -->
            <div class="row-main">
              <div class="row-line-1">
                <template v-if="item.type === 'member_joined'">
                  <strong class="row-name">{{ item.real_name }}</strong>
                  <span class="row-verb">加入了社群</span>
                </template>
                <template v-else>
                  <strong class="row-name" :class="{ 'is-anonymous': !item.real_name }">
                    {{ item.real_name || '匿名成員' }}
                  </strong>
                  <span class="row-verb">新增了一筆求職紀錄</span>
                  <span
                    :class="['row-kind', `row-kind--${item.kind}`]"
                  >{{ KIND_LABEL[item.kind] }}</span>
                </template>
              </div>
              <div class="row-line-2">
                <template v-if="item.type === 'member_joined'">
                  <span>{{ item.institution }}</span>
                  <template v-if="item.position">
                    <span class="dot" aria-hidden="true">·</span>
                    <span>{{ item.position }}</span>
                  </template>
                </template>
                <template v-else>
                  <span class="row-company">{{ item.company }}</span>
                  <template v-if="item.category">
                    <span class="dot" aria-hidden="true">·</span>
                    <span>{{ item.category }}</span>
                  </template>
                </template>
              </div>
            </div>

            <!-- ---------- relative time ---------- -->
            <time
              class="row-time"
              :datetime="item.timestamp"
              :title="new Date(item.timestamp).toLocaleString('zh-TW')"
            >
              <el-icon class="row-time-icon" :size="12"><Calendar /></el-icon>
              {{ relativeTime(item.timestamp) }}
            </time>
          </li>

          <!-- Lazy-load sentinel: an empty row at the end of the list
               that the IntersectionObserver watches. As soon as it
               enters view (or gets within 200 px of it), we fetch the
               next batch with `before = lastItem.timestamp`. We only
               render it when there's actually more to fetch — once
               `hasMore` flips false the sentinel disappears, the
               observer disconnects, and the cascade ends silently. -->
          <li
            v-if="hasMore"
            ref="sentinelRef"
            class="feed-sentinel"
            aria-hidden="true"
            data-test="timeline-sentinel"
          >
            <el-icon
              v-if="loadingMore"
              class="feed-sentinel-spinner"
              :size="14"
            >
              <Loading />
            </el-icon>
          </li>
        </ul>
      </div>
    </el-collapse-transition>
  </section>
</template>

<style scoped>
.timeline-feed {
  background: var(--surface-0);
  border: 1px solid rgba(15, 23, 42, 0.06);
  border-radius: var(--radius-lg);
  padding: 22px 24px 16px;
  box-shadow: 0 2px 6px rgba(15, 23, 42, 0.04);
}

/* ---------- header ---------- */
.feed-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.feed-title-wrap {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.feed-title-icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: #ffffff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.25);
  flex: 0 0 auto;
}

.feed-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--ink-900);
  letter-spacing: -0.01em;
}

.feed-subtitle {
  margin: 2px 0 0;
  font-size: 12px;
  color: var(--ink-500);
}

.feed-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 999px;
  border: 1px solid rgba(99, 102, 241, 0.16);
  background: rgba(99, 102, 241, 0.06);
  color: var(--brand-primary);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  outline: none;
  transition: background var(--dur) var(--ease),
    border-color var(--dur) var(--ease),
    color var(--dur) var(--ease);
}

.feed-toggle:hover {
  background: rgba(99, 102, 241, 0.12);
  border-color: rgba(99, 102, 241, 0.32);
  color: var(--brand-primary-hover);
}

.feed-toggle:focus-visible {
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.2);
}

.feed-toggle-icon {
  transition: transform var(--dur) var(--ease);
}

.feed-toggle-icon.is-collapsed {
  /* expanded → arrow points down (default), collapsed → arrow points
     to the right so the affordance reads "click to expand". */
  transform: rotate(-90deg);
}

/* ---------- body wrapper (top-margin lives here so the collapse
   animation eats the spacing too — feels natural at both ends). ---- */
.feed-body {
  margin-top: 14px;
}

/* ---------- list ---------- */
.feed-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  /* Cap the expanded feed at ~6 rows so the home page doesn't grow
     with every new entry — anything beyond uses the inner scroll.
     The cut-off lands mid-row to signal "more below" without needing
     a separate fade overlay. */
  max-height: 420px;
  overflow-y: auto;
  /* Setting overflow-y to a non-visible value forces overflow-x to
     compute as `auto` per the CSS spec — without this explicit hidden,
     a long company name + scrollbar-gutter shaving 6 px off the row
     width is enough to spawn a horizontal scrollbar. min-width: 0 +
     ellipsis already keep content visually contained, so clipping the
     last sub-pixel is safe. */
  overflow-x: hidden;
  /* Reserve gutter so the row width doesn't twitch when the scrollbar
     comes and goes (overlay-scrollbar systems). */
  scrollbar-gutter: stable;
  /* Slim, low-contrast scrollbar to match the dialog body style in
     style.css so the feed doesn't sprout a chunky default bar. */
  scrollbar-width: thin;
  scrollbar-color: rgba(15, 23, 42, 0.15) transparent;
}

.feed-list::-webkit-scrollbar {
  width: 6px;
}

.feed-list::-webkit-scrollbar-thumb {
  background: rgba(15, 23, 42, 0.15);
  border-radius: 999px;
}

.feed-list::-webkit-scrollbar-track {
  background: transparent;
}

/* ---------- lazy-load sentinel ---------- */
.feed-sentinel {
  /* Quiet end-of-list footer that doubles as the IntersectionObserver
     target. Just tall enough that it can intersect comfortably with
     the 200 px rootMargin even when the list is nearly empty. */
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 32px;
  padding: 8px 0;
  pointer-events: none;
}

.feed-sentinel-spinner {
  color: var(--ink-300);
  animation: feed-sentinel-spin 0.9s linear infinite;
}

@keyframes feed-sentinel-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.feed-row {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 12px 8px;
  border-radius: var(--radius-md);
  cursor: pointer;
  outline: none;
  position: relative;
  transition: background var(--dur) var(--ease),
    transform var(--dur) var(--ease);
  /* gentle entrance — only meaningful on the first paint, but cheap. */
  animation: row-fade 0.32s var(--ease) backwards;
}

.feed-row + .feed-row {
  border-top: 1px solid rgba(15, 23, 42, 0.05);
}

.feed-row:hover,
.feed-row:focus-visible {
  background: rgba(99, 102, 241, 0.06);
  transform: translateX(2px);
}

.feed-row:focus-visible {
  box-shadow: inset 0 0 0 2px rgba(99, 102, 241, 0.4);
}

.feed-row.is-skeleton {
  cursor: default;
  animation: none;
}

.feed-row.is-skeleton:hover {
  background: transparent;
  transform: none;
}

@keyframes row-fade {
  from {
    opacity: 0;
    transform: translateY(4px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* Stagger so rows feel hand-dealt rather than slamming in together. */
.feed-row:nth-child(1) {
  animation-delay: 0ms;
}
.feed-row:nth-child(2) {
  animation-delay: 40ms;
}
.feed-row:nth-child(3) {
  animation-delay: 80ms;
}
.feed-row:nth-child(4) {
  animation-delay: 120ms;
}
.feed-row:nth-child(5) {
  animation-delay: 160ms;
}
.feed-row:nth-child(n + 6) {
  animation-delay: 200ms;
}

/* ---------- avatar ---------- */
.row-avatar {
  flex: 0 0 auto;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #ffffff;
  overflow: hidden;
  border: 1px solid rgba(15, 23, 42, 0.06);
}

.row-avatar--member {
  background: linear-gradient(
    135deg,
    var(--brand-primary),
    var(--brand-accent)
  );
  box-shadow: 0 3px 8px rgba(99, 102, 241, 0.25);
}

/* Job avatars are shape-coded via the rounded-square radius (vs the
   member avatar's circle) so type stays disambiguated; the gradient
   below is then tinted by kind to mirror the chip colour beside it.
   Internship → indigo, Fulltime → career teal — matches the Jobs
   page card accents and TimelineFeedPreview's avatar tints. */
.row-avatar--job {
  border-radius: 12px;
}

.row-avatar--kind-internship {
  background: linear-gradient(
    135deg,
    var(--kind-internship-from),
    var(--kind-internship-to)
  );
  box-shadow: 0 3px 8px rgba(99, 102, 241, 0.25);
}

.row-avatar--kind-fulltime {
  background: linear-gradient(
    135deg,
    var(--kind-fulltime-from),
    var(--kind-fulltime-to)
  );
  box-shadow: 0 3px 8px rgba(16, 185, 129, 0.25);
}

.row-avatar--photo {
  background: linear-gradient(135deg, #eef2ff, #f3e8ff);
}

.row-avatar--photo :deep(img) {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

/* ---------- main text ---------- */
.row-main {
  flex: 1 1 auto;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.row-line-1 {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  color: var(--ink-900);
  line-height: 1.5;
}

.row-name {
  font-weight: 600;
  color: var(--ink-900);
  white-space: nowrap;
}

.row-name.is-anonymous {
  color: var(--ink-500);
  font-weight: 500;
  font-style: italic;
}

.row-verb {
  color: var(--ink-500);
  font-weight: 400;
}

.row-kind {
  font-size: 11px;
  font-weight: 500;
  padding: 2px 8px;
  border-radius: 999px;
  letter-spacing: 0.02em;
  white-space: nowrap;
}

.row-kind--internship {
  background: var(--kind-internship-soft);
  color: var(--kind-internship-ink);
}

.row-kind--fulltime {
  background: var(--kind-fulltime-soft);
  color: var(--kind-fulltime-ink);
}

.row-line-2 {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--ink-500);
  line-height: 1.5;
  /* Truncate gracefully on phone widths if a line is too long. */
  overflow: hidden;
  text-overflow: ellipsis;
}

.row-company {
  font-weight: 500;
  color: var(--ink-700, #334155);
}

.dot {
  color: var(--ink-300);
}

/* ---------- right column: relative time ---------- */
.row-time {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--ink-500);
  white-space: nowrap;
}

.row-time-icon {
  color: var(--ink-300);
}

/* ---------- empty / error ---------- */
.feed-empty {
  padding: 8px 0 16px;
}

/* ---------- skeleton ---------- */
.row-skeleton {
  display: flex;
  align-items: center;
  gap: 14px;
  width: 100%;
}

.sk-avatar {
  width: 40px !important;
  height: 40px !important;
}

.row-skeleton-text {
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.sk-line {
  height: 12px;
  border-radius: 6px;
}

.sk-line-1 {
  width: 60%;
}

.sk-line-2 {
  width: 40%;
}

.sk-time {
  width: 56px;
  height: 12px;
  border-radius: 6px;
}

/* ---------- mobile ---------- */
@media (max-width: 640px) {
  .timeline-feed {
    padding: 18px 16px 12px;
  }

  .feed-toggle-label {
    /* Reclaim space — the chevron alone communicates the action. */
    display: none;
  }

  .feed-toggle {
    padding: 6px 8px;
  }

  .feed-row {
    gap: 10px;
    padding: 10px 4px;
  }

  .row-line-2 {
    font-size: 11.5px;
  }

  /* On very narrow screens the time can crowd the title row — drop it
     under the main text so the row never gets cramped. */
  .row-time {
    align-self: flex-start;
    margin-left: 50px; /* avatar width + gap */
    margin-top: 2px;
  }

  .feed-row {
    flex-wrap: wrap;
  }

  .row-main {
    flex-basis: calc(100% - 50px);
  }

  .feed-list {
    /* On phones each row wraps the time below the text, so 420 px
       only fits ~5 rows. Switch to vh so the cap scales with the
       viewport instead of dominating very short screens. */
    max-height: 60vh;
  }
}
</style>
