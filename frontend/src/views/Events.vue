<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElButton, ElIcon, ElInput, ElMessage, ElOption, ElSelect } from 'element-plus'
import {
  Calendar,
  Camera,
  CollectionTag,
  Delete,
  Location,
  Picture,
  Plus,
  Refresh,
  Search,
} from '@element-plus/icons-vue'

import DeleteWithPasswordDialog from '../components/DeleteWithPasswordDialog.vue'
import EventDetailDialog from '../components/events/EventDetailDialog.vue'
import EventFormDialog from '../components/events/EventFormDialog.vue'
import {
  TAG_FILTER_LIMIT,
  YEAR_OPTIONS,
  safeOrder,
  safeStringList,
  safeYear,
} from '../components/events/eventFilters'
import { storeToRefs } from 'pinia'

import { eventsApi } from '../api/events'
import { useAuthStore } from '../stores/auth'
import { useEventsStore } from '../stores/events'
import { useDeleteWithPassword } from '../composables/useDeleteWithPassword'
import { useEventPeek } from '../composables/useEventPeek'
import { useDialogRouteSync } from '../composables/useDialogRouteSync'
import { useUrlQuerySync } from '../composables/useUrlQuerySync'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const SEARCH_DEBOUNCE_MS = 300

// Filter state lives in the URL; `detail` is preserved across rewrites for
// the deep-link dialog. onChange refetches after each sync. Mirrors Jobs.
const { sortOrder, year, tag, q } = useUrlQuerySync({
  route,
  router,
  preserveKeys: ['detail'],
  onChange: () => loadItems(),
  fields: {
    sortOrder: {
      queryKey: 'order',
      parse: safeOrder,
      serialize: (v) => (v !== 'desc' ? v : undefined),
    },
    year: {
      parse: safeYear,
      serialize: (v) => (v ? String(v) : undefined),
    },
    tag: {
      parse: (v) => safeStringList(v, TAG_FILTER_LIMIT),
      serialize: (v) => (v.length > 0 ? [...v] : undefined),
    },
    q: {
      parse: (v) => (typeof v === 'string' ? v : ''),
      serialize: (v) => v || undefined,
      debounce: SEARCH_DEBOUNCE_MS,
    },
  },
})

const eventsStore = useEventsStore()
const { items, total, loading } = storeToRefs(eventsStore)

// Timeline card hover: rail fill (--tl-progress, 0..1, lights the warm
// spine down to the hovered card's node) + lazy photo-peek slideshow
// (peekLayers cross-dissolve), both driven by onCardEnter/onCardLeave.
const { timelineRef, tlProgress, peekLayers, onCardEnter, onCardLeave } =
  useEventPeek()

// ---- Warm Spectrum: deterministic per-event hue, clamped to the
// amber->rose arc. Pure FNV-1a over char codes — same seed always yields
// the same hue, so the rail's colour order is stable across re-sorts. ----
function _fnv1a(str) {
  let h = 0x811c9dc5
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i)
    h = (h + ((h << 1) + (h << 4) + (h << 7) + (h << 8) + (h << 24))) >>> 0
  }
  return h >>> 0
}

// Warm arc only: 350deg(rose) -> 360 -> 0 -> 38deg(amber), 48deg span, so a
// hash can never land on green/blue. Returns null when there's no seed at
// all -> the CSS var stays unset and every rule falls back to amber (28).
function eventHue(ev) {
  const seed = ((ev.tags && ev.tags[0]) || ev.title || '').trim()
  if (!seed) return null
  return (350 + (_fnv1a(seed) % 48)) % 360
}

function entryStyle(ev, ei) {
  const hue = eventHue(ev)
  return hue === null ? { '--i': ei } : { '--i': ei, '--ev-hue': hue }
}


const formOpen = ref(false)
const editingEvent = ref(null)

// ?detail=<id> deep-link <-> detail dialog (open/fetch/close + drop the
// URL key on close), shared with Jobs via useDialogRouteSync.
const {
  open: detailOpen,
  item: detailEvent,
  show: openDetail,
} = useDialogRouteSync({
  route,
  router,
  queryKey: 'detail',
  fetchItem: (id) => eventsApi.get(id),
})

// Group the (already sorted) events by calendar year so the timeline can
// drop a sticky year divider at each boundary. Order of years follows
// item order.
const groupedByYear = computed(() => {
  const groups = []
  let current = null
  for (const ev of items.value) {
    const y = ev.event_date ? ev.event_date.slice(0, 4) : '—'
    if (!current || current.year !== y) {
      current = { year: y, events: [] }
      groups.push(current)
    }
    current.events.push(ev)
  }
  return groups
})

function coverUrl(ev) {
  if (!ev.cover_photo_id) return null
  return eventsApi.photoUrl(ev.id, ev.cover_photo_id)
}

// Date parts for the right meta-rail date-stamp.
function dayNum(iso) {
  return iso ? String(Number(iso.slice(8, 10))) : ''
}
function monthShort(iso) {
  return iso ? `${Number(iso.slice(5, 7))}月` : ''
}
function weekday(iso) {
  if (!iso) return ''
  return new Date(`${iso}T00:00:00`).toLocaleDateString('zh-TW', { weekday: 'short' })
}

// Print a month tab on the rail only when an event opens a new month
// within its year group (the first event of a group always prints its
// month). Empty string = no tab for this row.
function monthTab(events, ei) {
  const m = events[ei]?.event_date?.slice(5, 7)
  if (!m) return ''
  if (ei > 0 && events[ei - 1]?.event_date?.slice(5, 7) === m) return ''
  return `${Number(m)}月`
}

// Strip markdown to a short plain-text excerpt for the timeline entry.
function excerpt(md, n = 120) {
  if (!md) return ''
  const text = md
    .replace(/`{1,3}[^`]*`{1,3}/g, ' ')
    .replace(/!\[[^\]]*\]\([^)]*\)/g, ' ')
    .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1')
    .replace(/[#>*_~\-]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
  return text.length > n ? `${text.slice(0, n)}…` : text
}

async function loadItems() {
  try {
    await eventsStore.fetch({
      order: sortOrder.value,
      year: year.value ?? undefined,
      tag: tag.value,
      q: q.value || undefined,
    })
  } catch {
    ElMessage.error('載入活動失敗')
  }
}

// After a create/update/delete the cache would otherwise serve a stale
// row, so drop it before reloading the current view authoritatively.
function reloadFresh() {
  eventsStore.invalidate()
  loadItems()
}

// ---- tag filter suggestions ----
const tagSuggestions = ref([])
async function fetchTagSuggestions(queryString) {
  try {
    tagSuggestions.value = await eventsApi.listTags(queryString || undefined)
  } catch {
    tagSuggestions.value = []
  }
}
const displayedTagSuggestions = computed(() => {
  const sel = new Set(tag.value)
  const fresh = []
  const stale = []
  for (const t of tagSuggestions.value) {
    if (sel.has(t)) stale.push(t)
    else fresh.push(t)
  }
  return [...fresh, ...stale]
})

// ---- create / edit / detail ----
function openCreate() {
  editingEvent.value = null
  formOpen.value = true
}
function openEdit(ev) {
  editingEvent.value = { ...ev }
  formOpen.value = true
}
function onDetailEdit(ev) {
  setTimeout(() => openEdit(ev), 0)
}

// ---- delete (password-confirmed, shared with Jobs) ----
const {
  dialogOpen: deleteOpen,
  target: deleteTarget,
  submitting: deleteSubmitting,
  error: deleteError,
  open: askDelete,
  confirm: onDeleteConfirm,
} = useDeleteWithPassword({
  remove: (ev, password) => eventsApi.remove(ev.id, password),
  messages: { 404: '活動已不存在' },
  onSuccess: (ev) => {
    ElMessage.success(`已刪除「${ev.title}」`)
    // Close the detail dialog too if it was open on this same event.
    if (detailOpen.value && detailEvent.value?.id === ev.id) {
      detailOpen.value = false
    }
    reloadFresh()
  },
})

function onSaved() {
  reloadFresh()
}

onMounted(loadItems)
</script>

<template>
  <div class="events-page" data-test="events-page">
    <!-- Hero banner -->
    <header class="page-hero">
      <div class="hero-glow" aria-hidden="true"></div>
      <div class="hero-content">
        <div class="hero-text">
          <span class="hero-eyebrow">
            <el-icon :size="13"><Camera /></el-icon>
            社群相簿
          </span>
          <h1 class="hero-title">活動紀錄</h1>
          <p class="hero-subtitle">
            聚餐、出遊、比賽與講座——用照片和文字，把每一段時光留下來。
          </p>
        </div>
        <div class="hero-side">
          <div class="hero-count">
            <span class="hero-count-num">{{ total }}</span>
            <span class="hero-count-label">場活動</span>
          </div>
          <div class="hero-actions">
            <el-button
              class="hero-btn hero-btn--ghost"
              :icon="Refresh"
              data-test="refresh-button"
              @click="loadItems"
            >
              重新整理
            </el-button>
            <el-button
              v-if="auth.isAdmin"
              class="hero-btn hero-btn--solid"
              :icon="Plus"
              data-test="add-event-button"
              @click="openCreate"
            >
              新增活動
            </el-button>
          </div>
        </div>
      </div>
    </header>

    <!-- Filter bar -->
    <div class="filter-bar">
      <div class="filter-row">
        <el-select
          v-model="year"
          placeholder="年份"
          clearable
          data-test="filter-year"
          class="filter-year"
        >
          <template #prefix><el-icon><Calendar /></el-icon></template>
          <el-option v-for="y in YEAR_OPTIONS" :key="y" :label="`${y} 年`" :value="y" />
        </el-select>

        <el-select
          v-model="tag"
          multiple
          filterable
          remote
          :remote-method="fetchTagSuggestions"
          :reserve-keyword="false"
          :multiple-limit="TAG_FILTER_LIMIT"
          placeholder="標籤（可多選）"
          clearable
          data-test="filter-tag"
          class="filter-tag"
        >
          <template #prefix><el-icon><CollectionTag /></el-icon></template>
          <el-option v-for="t in displayedTagSuggestions" :key="t" :label="t" :value="t" />
        </el-select>

        <button
          type="button"
          class="sort-toggle"
          data-test="sort-toggle"
          @click="sortOrder = sortOrder === 'desc' ? 'asc' : 'desc'"
        >
          {{ sortOrder === 'desc' ? '新 → 舊' : '舊 → 新' }}
          <span aria-hidden="true">{{ sortOrder === 'desc' ? '↓' : '↑' }}</span>
        </button>
      </div>

      <el-input
        v-model="q"
        placeholder="搜尋活動名稱、地點、記錄內容"
        :prefix-icon="Search"
        clearable
        data-test="filter-search"
        class="filter-search"
      />
    </div>

    <!-- Loading skeleton -->
    <div v-if="loading" class="timeline" data-test="timeline-skeleton">
      <div v-for="i in 3" :key="`skel-${i}`" class="tl-entry">
        <div class="tl-rail-col"><span class="tl-node"></span></div>
        <div class="tl-content-col">
          <div class="tl-card tl-card--skel">
            <div class="skel-thumb shimmer"></div>
            <div class="skel-body">
              <div class="skel-line skel-line--title shimmer"></div>
              <div class="skel-line skel-line--text shimmer"></div>
              <div class="skel-line skel-line--text shimmer"></div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Timeline -->
    <div
      v-else-if="items.length > 0"
      ref="timelineRef"
      class="timeline"
      data-test="timeline"
      :style="{ '--tl-progress': tlProgress }"
    >
      <template v-for="(group, gi) in groupedByYear" :key="group.year">
        <div class="year-marker" data-test="year-marker">
          <div class="tl-rail-col">
            <span class="year-dot" aria-hidden="true"></span>
          </div>
          <div class="tl-content-col">
            <div class="year-head">
              <span class="year-label" data-test="year-label">{{ group.year }}</span>
              <span class="year-rule" aria-hidden="true"></span>
              <span class="year-count">{{ group.events.length }} 場</span>
            </div>
          </div>
        </div>

        <article
          v-for="(ev, ei) in group.events"
          :key="ev.id"
          class="tl-entry"
          :class="{ 'tl-entry--lead': gi === 0 && ei === 0 && sortOrder === 'desc' }"
          data-test="timeline-entry"
          :style="entryStyle(ev, ei)"
        >
          <div class="tl-rail-col">
            <span
              v-if="monthTab(group.events, ei)"
              class="tl-month"
              aria-hidden="true"
            >{{ monthTab(group.events, ei) }}</span>
            <span
              class="tl-node"
              :class="{ 'tl-node--photo': coverUrl(ev) }"
              aria-hidden="true"
            >
              <img v-if="coverUrl(ev)" :src="coverUrl(ev)" alt="" loading="lazy" />
            </span>
          </div>

          <div class="tl-content-col">
            <div
              class="tl-card"
              :class="{ 'has-cover': coverUrl(ev) }"
              role="button"
              tabindex="0"
              data-test="entry-card"
              @click="openDetail(ev)"
              @keydown.enter="openDetail(ev)"
              @keydown.space.prevent="openDetail(ev)"
              @pointerenter="onCardEnter($event, ev)"
              @pointerleave="onCardLeave(ev)"
            >
              <!-- Zone 1: cover (or placeholder). Always shows the photo
                   count; a 2nd photo lazily cross-fades in on hover. -->
              <div v-if="coverUrl(ev)" class="tl-thumb">
                <img :src="coverUrl(ev)" :alt="`${ev.title} 封面`" loading="lazy" />
                <template v-if="peekLayers[ev.id]">
                  <img
                    v-if="peekLayers[ev.id].a"
                    class="tl-peek"
                    :class="{ 'is-active': peekLayers[ev.id].active === 'a' }"
                    :src="peekLayers[ev.id].a"
                    alt=""
                    aria-hidden="true"
                    loading="lazy"
                  />
                  <img
                    v-if="peekLayers[ev.id].b"
                    class="tl-peek"
                    :class="{ 'is-active': peekLayers[ev.id].active === 'b' }"
                    :src="peekLayers[ev.id].b"
                    alt=""
                    aria-hidden="true"
                    loading="lazy"
                  />
                </template>
                <span class="photo-badge">
                  <el-icon :size="12"><Picture /></el-icon>
                  {{ ev.photo_count }}
                </span>
              </div>
              <div v-else class="tl-thumb tl-thumb--empty" aria-hidden="true">
                <el-icon class="empty-ico" :size="28"><Picture /></el-icon>
                <span class="empty-label">尚無照片</span>
              </div>

              <!-- Zone 2: editorial body -->
              <div class="tl-body">
                <span
                  v-if="gi === 0 && ei === 0 && sortOrder === 'desc'"
                  class="tl-lead-kicker"
                >最新</span>
                <div v-if="ev.tags?.length" class="tl-meta-row">
                  <div class="tl-tags">
                    <span
                      v-for="(t, ti) in ev.tags"
                      :key="t"
                      class="tl-tag"
                      :class="{ 'tl-tag--sig': ti === 0 }"
                    >#{{ t }}</span>
                  </div>
                </div>
                <h3 class="tl-title">{{ ev.title }}</h3>
                <p v-if="excerpt(ev.description_md)" class="tl-excerpt">
                  {{ excerpt(ev.description_md) }}
                </p>
                <p v-else class="tl-excerpt tl-excerpt--empty">尚無活動記錄內文</p>

                <span class="tl-more" aria-hidden="true">
                  閱讀活動 <span class="tl-more-arrow">→</span>
                </span>
              </div>

              <!-- Zone 3: right meta-rail (the journal date-stamp) -->
              <div class="tl-meta-rail" aria-hidden="true">
                <span class="mr-month">{{ monthShort(ev.event_date) }}</span>
                <span class="mr-day">{{ dayNum(ev.event_date) }}</span>
                <span class="mr-weekday">{{ weekday(ev.event_date) }}</span>
                <span class="mr-divider"></span>
                <span v-if="ev.location" class="mr-loc">
                  <el-icon :size="12"><Location /></el-icon>
                  <span>{{ ev.location }}</span>
                </span>
                <span class="mr-photo">
                  <el-icon :size="12"><Picture /></el-icon>{{ ev.photo_count }}
                </span>
              </div>
            </div>
          </div>
        </article>
      </template>
    </div>

    <!-- Empty state -->
    <div v-else class="empty-state" data-test="empty-state">
      <div class="empty-icon" aria-hidden="true">
        <el-icon :size="32"><Camera /></el-icon>
      </div>
      <p class="empty-text">還沒有任何活動紀錄</p>
      <el-button
        v-if="auth.isAdmin && total === 0"
        type="primary"
        :icon="Plus"
        @click="openCreate"
      >
        記錄第一場活動
      </el-button>
    </div>

    <EventDetailDialog v-model="detailOpen" :event="detailEvent" @edit="onDetailEdit">
      <template #footer-extra>
        <el-button
          v-if="auth.isAdmin && detailEvent"
          type="danger"
          plain
          :icon="Delete"
          data-test="detail-delete-button"
          @click="askDelete(detailEvent)"
        >
          刪除整場活動
        </el-button>
      </template>
    </EventDetailDialog>

    <EventFormDialog v-model="formOpen" :event="editingEvent" @saved="onSaved" />

    <DeleteWithPasswordDialog
      v-model="deleteOpen"
      title="刪除活動"
      :item-name="deleteTarget?.title ?? ''"
      warning="將永久刪除這場活動，包含記錄與所有照片。此操作無法復原。"
      :loading="deleteSubmitting"
      :error-message="deleteError"
      @confirm="onDeleteConfirm"
    />
  </div>
</template>

<style scoped>
.events-page {
  display: flex;
  flex-direction: column;
  gap: var(--sp-lg);
}

/* Column-flex items default to min-width:auto, so a pathological
   unbroken string (e.g. a description with no spaces) would expand the
   timeline past the 1200px layout container and overflow the page.
   Pin every section to min-width:0 so they always respect the column. */
.events-page > * {
  min-width: 0;
}

/* ============================================================
   Hero banner
   ============================================================ */
.page-hero {
  position: relative;
  overflow: hidden;
  border-radius: var(--radius-xl);
  padding: 28px 32px;
  color: #fff;
  background: linear-gradient(120deg, #b45309 0%, #f59e0b 110%);
  box-shadow: 0 16px 36px -22px rgba(180, 83, 9, 0.4);
}

.hero-glow {
  position: absolute;
  inset: 0;
  pointer-events: none;
  background:
    radial-gradient(420px 300px at 92% -10%, rgba(244, 63, 94, 0.3), transparent 70%),
    radial-gradient(360px 280px at 8% 120%, rgba(251, 191, 36, 0.3), transparent 70%);
  mix-blend-mode: screen;
}

.hero-content {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
  flex-wrap: wrap;
}

.hero-eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.08em;
  padding: 4px 12px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.16);
  border: 1px solid rgba(255, 255, 255, 0.22);
  backdrop-filter: blur(6px);
}

.hero-title {
  margin: 12px 0 0;
  font-size: 30px;
  font-weight: 800;
  letter-spacing: -0.02em;
  line-height: 1.08;
  color: #fff;
}

.hero-subtitle {
  margin: 8px 0 0;
  font-size: 14px;
  max-width: 46ch;
  color: rgba(255, 255, 255, 0.85);
  line-height: 1.6;
}

.hero-side {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 14px;
}

.hero-count {
  display: flex;
  align-items: baseline;
  gap: 6px;
}

.hero-count-num {
  font-size: 34px;
  font-weight: 800;
  line-height: 1;
  letter-spacing: -0.03em;
  font-variant-numeric: tabular-nums;
  background: linear-gradient(180deg, #fff 0%, #fed7aa 90%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  color: transparent;
}

.hero-count-label {
  font-size: 14px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.85);
}

.hero-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

/* Hero buttons tuned for the warm banner: a translucent-white ghost for
   the secondary action and a solid white CTA (warm ink) for the primary,
   instead of the indigo brand primary that clashed with the amber. */
.hero-btn.el-button {
  border: none;
  font-weight: 600;
  transition: transform var(--dur) var(--ease),
    background-color var(--dur) var(--ease), box-shadow var(--dur) var(--ease),
    color var(--dur) var(--ease);
}

.hero-btn--ghost.el-button {
  color: #fff;
  background: rgba(255, 255, 255, 0.16);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.3);
}

.hero-btn--ghost.el-button:hover,
.hero-btn--ghost.el-button:focus-visible {
  color: #fff;
  background: rgba(255, 255, 255, 0.26);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.42);
}

.hero-btn--solid.el-button {
  color: var(--accent-warm-ink);
  background: #fff;
  box-shadow: 0 6px 16px -8px rgba(124, 45, 18, 0.5);
}

.hero-btn--solid.el-button:hover,
.hero-btn--solid.el-button:focus-visible {
  color: var(--accent-warm-ink);
  background: #fff;
  box-shadow: 0 10px 22px -8px rgba(124, 45, 18, 0.55);
}

/* ============================================================
   Filter bar
   ============================================================ */
.filter-bar {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px;
  background: #fff;
  border: 1px solid rgba(15, 23, 42, 0.06);
  border-radius: var(--radius-lg);
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
}

.filter-row {
  display: flex;
  align-items: center;
  gap: var(--sp-sm);
  flex-wrap: wrap;
}

.filter-year {
  width: 140px;
}

.filter-tag {
  flex: 1;
  min-width: 200px;
}

.sort-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 1px solid rgba(15, 23, 42, 0.1);
  background: #fff;
  color: var(--ink-700);
  padding: 0 14px;
  height: 32px;
  border-radius: var(--radius-md);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  white-space: nowrap;
  transition: border-color var(--dur) var(--ease), color var(--dur) var(--ease);
}

.sort-toggle:hover {
  border-color: rgba(245, 158, 11, 0.5);
  color: var(--accent-warm-ink);
}

.filter-search {
  width: 100%;
}

.filter-bar :deep(.el-input__wrapper),
.filter-bar :deep(.el-select__wrapper) {
  border-radius: var(--radius-md);
  box-shadow: 0 0 0 1px rgba(15, 23, 42, 0.06) inset;
}

.filter-bar :deep(.el-input__wrapper.is-focus),
.filter-bar :deep(.el-select__wrapper.is-focused) {
  box-shadow: 0 0 0 1.5px var(--accent-warm-from) inset;
}

/* ============================================================
   Timeline — continuous rail, sticky year dividers, hero cards
   ============================================================ */
.timeline {
  position: relative;
  /* Calm, narrow cover so the expressive rail is the protagonist. Single
     source of truth so card + skeleton can't drift apart. */
  --tl-thumb-w: 184px;
}

/* The spine is two layers: a faint static track (::before = the road
   ahead) and a warm gradient fill (::after) scaled by --tl-progress (the
   road travelled), so the rail breathes as you scroll. Both share the
   same geometry + soft-masked ends. Centre sits at x=26 (half of the 52px
   rail column). */
.timeline::before,
.timeline::after {
  content: '';
  position: absolute;
  left: 24.75px;
  top: 0;
  bottom: 0;
  width: 2.5px;
  border-radius: 3px;
  -webkit-mask-image: linear-gradient(
    180deg,
    transparent 0,
    #000 18px,
    #000 calc(100% - 22px),
    transparent 100%
  );
  mask-image: linear-gradient(
    180deg,
    transparent 0,
    #000 18px,
    #000 calc(100% - 22px),
    transparent 100%
  );
}

.timeline::before {
  background: rgba(15, 23, 42, 0.09);
}

.timeline::after {
  /* Amber-dominant so the progress fill reads as a calm "you are here"
     indicator, not a red alert line stopping at a card. */
  background: linear-gradient(
    180deg,
    var(--accent-warm-from) 0%,
    hsl(24 92% 56%) 100%
  );
  opacity: 0.85;
  transform: scaleY(var(--tl-progress, 0));
  transform-origin: top;
  transition: transform 0.32s var(--ease);
}

.year-marker,
.tl-entry {
  display: flex;
}

/* Stretch so the rail column matches the year-head height — lets the
   year ring centre vertically on the year number (and stay on the rail
   line) instead of floating near the top of a zero-height column. */
.year-marker {
  align-items: stretch;
}

/* Stretch the rail column to the card's full height so the node can sit
   at the card's vertical centre. Card-to-card rhythm is one --sp-md step. */
.tl-entry {
  align-items: stretch;
  margin-bottom: var(--sp-md);
}

.tl-rail-col {
  flex: 0 0 52px;
  min-width: 0;
  align-self: stretch;
  position: relative;
}

/* No-photo fallback node: a small filled gradient dot. */
.tl-node {
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  width: 13px;
  height: 13px;
  border-radius: 50%;
  /* Warm Spectrum spot #1 — node takes the event hue. */
  background: linear-gradient(
    135deg,
    hsl(var(--ev-hue, 28) 90% 55%),
    hsl(calc(var(--ev-hue, 28) - 6) 82% 56%)
  );
  border: 3px solid #fff;
  box-shadow: 0 0 0 1px rgba(245, 158, 11, 0.18), 0 1px 4px rgba(245, 158, 11, 0.3);
  transition: transform var(--dur) var(--ease), box-shadow var(--dur) var(--ease);
  z-index: 2;
  overflow: hidden;
}

/* Cover-thumbnail node — turns the rail into a scannable contact sheet.
   The warm well frames white-background crops; the white ring lifts it
   off the spine. */
.tl-node--photo {
  width: 38px;
  height: 38px;
  border: 2.5px solid #fff;
  background: linear-gradient(135deg, hsl(var(--ev-hue, 28) 85% 92%), var(--surface-2));
  box-shadow: 0 0 0 1px rgba(245, 158, 11, 0.18), 0 3px 10px -2px rgba(15, 23, 42, 0.25);
}

.tl-node--photo img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

/* Month tab on the rail — prints only when a new month opens, so time is
   readable at a glance. Sits just above the node; surface-1 chip masks
   the spine behind it. */
.tl-month {
  position: absolute;
  left: 50%;
  top: calc(50% - 38px);
  transform: translateX(-50%);
  z-index: 3;
  white-space: nowrap;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.02em;
  color: var(--accent-warm-ink);
  background: var(--surface-1);
  padding: 1px 6px;
  border-radius: 999px;
  box-shadow: 0 0 0 1px rgba(245, 158, 11, 0.22);
}

.tl-content-col {
  flex: 1;
  min-width: 0;
  padding-left: 14px;
  position: relative;
}

/* Quiet hairline connector from the node out to the card. Runs under the
   photo node (z-index:0) and reaches the card edge. */
.tl-entry .tl-content-col::before {
  content: '';
  position: absolute;
  top: 50%;
  left: -26px;
  width: 40px;
  height: 2px;
  transform: translateY(-50%);
  background: linear-gradient(
    90deg,
    hsl(var(--ev-hue, 28) 85% 52% / 0.42),
    hsl(var(--ev-hue, 28) 85% 52% / 0.04)
  );
  transition: background var(--dur) var(--ease);
  z-index: 0;
}

.tl-meta-row {
  display: flex;
  flex-wrap: nowrap;
  align-items: center;
  gap: var(--sp-sm);
  min-width: 0;
}

/* Demoted to a quiet caption — the title now leads the row, so the date
   reads as secondary metadata, not a competing accent pill. */
.tl-date-pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  font-weight: 600;
  color: var(--ink-500);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
  flex: 0 0 auto;
}

.tl-weekday {
  margin-left: 1px;
  opacity: 0.85;
}

/* ---------- Sticky year divider ---------- */
.year-marker {
  position: sticky;
  top: 72px;
  z-index: 5;
  pointer-events: none;
  /* Big air before each year so the sticky header lands as a real
     section break rather than just another card gap. The gap below the
     year (to its first card) is a margin so it stays OUTSIDE the
     stretched area — keeping the ring centred on the number. */
  margin-top: var(--sp-2xl);
  margin-bottom: var(--sp-md);
}

.year-marker:first-child {
  margin-top: 0;
}

/* Hollow gradient-ring milestone — distinct from the filled event dots,
   so years read as chapters and entries as items. The surface-1 ring
   makes the spine appear to pass behind it. */
.year-dot {
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  width: 18px;
  height: 18px;
  border-radius: 50%;
  border: 3px solid transparent;
  background-image: linear-gradient(#fff, #fff),
    linear-gradient(135deg, var(--accent-warm-from), var(--accent-warm-to));
  background-origin: border-box;
  background-clip: padding-box, border-box;
  box-shadow: 0 0 0 4px var(--surface-1), 0 2px 8px rgba(244, 63, 94, 0.28);
}

.year-head {
  display: flex;
  align-items: center;
  gap: var(--sp-md);
  /* No padding-bottom — the gap to the first card is the year-marker's
     margin-bottom, so the ring can centre on the number exactly. */
  padding: 0;
}

.year-label {
  font-size: 30px;
  font-weight: 800;
  letter-spacing: -0.02em;
  font-variant-numeric: tabular-nums;
  background: linear-gradient(135deg, var(--accent-warm-ink), var(--accent-warm-to));
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  color: transparent;
}

.year-rule {
  flex: 1;
  height: 1px;
  background: linear-gradient(90deg, rgba(245, 158, 11, 0.4), transparent);
}

/* Neutral count chip so it doesn't read as a third interchangeable warm
   pill alongside the date and tags. */
.year-count {
  font-size: 12px;
  font-weight: 600;
  color: var(--ink-500);
  padding: 3px 10px;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.05);
}

/* ---------- Entry card ---------- */
.tl-entry {
  animation: tl-rise 0.5s var(--ease) backwards;
  /* Cap the stagger so a long list doesn't drag on for seconds. */
  animation-delay: calc(min(var(--i, 0), 8) * 50ms);
}

@keyframes tl-rise {
  from {
    opacity: 0;
    transform: translateY(14px);
  }
}

/* Three-zone "journal ledger": cover | editorial body | right date-stamp
   rail. The right track is REAL content, so the once-empty right half
   becomes a deliberate column. */
.tl-card {
  position: relative;
  overflow: hidden;
  isolation: isolate;
  display: grid;
  grid-template-columns: var(--tl-thumb-w, 184px) minmax(220px, 1fr) clamp(132px, 15%, 168px);
  align-items: stretch;
  border-radius: var(--radius-lg);
  background: #fff;
  /* Top-lit material elevation — a hairline ring + soft layered shadows +
     an inner top highlight. Depth without any coloured glow. */
  box-shadow:
    0 0 0 1px rgba(15, 23, 42, 0.06),
    0 1px 1px rgba(15, 23, 42, 0.04),
    0 6px 14px -10px rgba(15, 23, 42, 0.16),
    0 18px 40px -28px rgba(15, 23, 42, 0.18),
    inset 0 1px 0 rgba(255, 255, 255, 0.85);
  cursor: pointer;
  transition: transform var(--dur) var(--ease), box-shadow var(--dur) var(--ease);
  min-height: 156px;
}

/* Warm Spectrum spot #3 — a 3px per-event hue spine on the left edge. */
.tl-card::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  z-index: 2;
  background: linear-gradient(
    180deg,
    hsl(var(--ev-hue, 28) 90% 56%),
    hsl(calc(var(--ev-hue, 28) + 8) 84% 60%)
  );
  opacity: 0.9;
  pointer-events: none;
  transition: opacity var(--dur) var(--ease), width var(--dur) var(--ease);
}

.tl-card:hover {
  transform: translateY(-3px);
  box-shadow:
    0 0 0 1px hsl(var(--ev-hue, 28) 55% 50% / 0.18),
    0 2px 4px rgba(15, 23, 42, 0.05),
    0 12px 24px -12px rgba(15, 23, 42, 0.18),
    0 34px 64px -30px rgba(15, 23, 42, 0.2),
    inset 0 1px 0 rgba(255, 255, 255, 0.95);
}

.tl-card:hover::before {
  opacity: 1;
  width: 4px;
}

.tl-card:active {
  transform: translateY(-1px) scale(0.997);
  transition-duration: 90ms;
}

.tl-card:focus-visible {
  outline: 2px solid hsl(var(--ev-hue, 28) 80% 52%);
  outline-offset: 3px;
}

/* Node feedback on hover/focus — a gentle pop (smaller for the larger
   photo discs so they don't lurch). */
.tl-entry:hover .tl-node,
.tl-entry:focus-within .tl-node {
  transform: translate(-50%, -50%) scale(1.25);
  box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.2), 0 2px 8px rgba(245, 158, 11, 0.4);
}

.tl-entry:hover .tl-node--photo,
.tl-entry:focus-within .tl-node--photo {
  transform: translate(-50%, -50%) scale(1.08);
  box-shadow: 0 0 0 1px rgba(245, 158, 11, 0.3), 0 5px 14px -2px rgba(15, 23, 42, 0.3);
}

/* ---------- Per-year lead: one clear step up ---------- */
.tl-entry--lead .tl-node--photo {
  width: 46px;
  height: 46px;
}

.tl-entry--lead .tl-node:not(.tl-node--photo) {
  width: 16px;
  height: 16px;
}

.tl-entry--lead .tl-title {
  font-size: 21px;
  line-height: 1.2;
  letter-spacing: -0.022em;
}

.tl-entry--lead .tl-title::after {
  width: 36px;
  height: 3px;
}

/* ---------- Cover thumbnail (left column) ----------
   The image is absolutely positioned so it never contributes its own
   intrinsic height to layout — otherwise a tall source image would
   inflate the card and leave the text column with dead space. The card
   height is therefore driven purely by the content (floored by the
   thumbnail's min-height), and the image just crops to fill. */
.tl-thumb {
  position: relative;
  flex: 0 0 var(--tl-thumb-w, 220px);
  /* Fill the full card height (the image is absolutely positioned so it
     never inflates the card), so there's never an empty strip under the
     cover when the text is taller. */
  align-self: stretch;
  min-height: 0;
  overflow: hidden;
  /* Warm-Spectrum hue well — frames letterboxed / white-background images
     and ties the cover to this event's colour. */
  background: linear-gradient(135deg, hsl(var(--ev-hue, 28) 85% 92%), var(--surface-2));
}

.tl-thumb img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  transition: transform 0.5s var(--ease);
}

/* Lazy 2nd photo — cross-dissolves in on hover (Warm Spectrum-free, just
   the imagery). Sits above the cover, below the badge. */
/* Two stacked slideshow layers that cross-dissolve. Both start hidden;
   only the active layer shows, and only while the card is hovered, so
   leaving the card fades the show back to the cover. A slow ken-burns
   zoom plays on the active slide. */
.tl-peek {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  opacity: 0;
  transform: scale(1.02);
  z-index: 1;
  pointer-events: none;
  transition: opacity 1.6s var(--ease), transform 1.6s var(--ease);
}

.tl-card:hover .tl-peek.is-active {
  opacity: 1;
  transform: scale(1.08);
  transition: opacity 1.6s var(--ease), transform 7s linear;
}

/* Feathered hue seam at the cover's bottom + an inset hairline on the
   right edge, so white-bg covers stay framed and joined to the card. */
.tl-thumb::after {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 2;
  background: linear-gradient(
    0deg,
    hsl(var(--ev-hue, 28) 62% 48% / 0.18) 0%,
    transparent 36%
  );
  box-shadow: inset -1px 0 0 rgba(15, 23, 42, 0.07);
  transition: background var(--dur) var(--ease);
}

.tl-card:hover .tl-thumb img {
  transform: scale(1.05);
}

.tl-card:hover .tl-thumb::after {
  background: linear-gradient(
    0deg,
    hsl(var(--ev-hue, 28) 62% 48% / 0.26) 0%,
    transparent 44%
  );
}

/* No-photo placeholder: a calm warm tile with a faded picture mark, so
   every card keeps a consistent left block and the empty state reads as
   designed rather than missing. */
.tl-thumb--empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  background: linear-gradient(140deg, hsl(var(--ev-hue, 28) 80% 93%), var(--surface-2));
  color: hsl(var(--ev-hue, 28) 55% 36%);
}

.empty-ico {
  opacity: 0.5;
}

.empty-label {
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.04em;
  opacity: 0.72;
}

.photo-badge {
  position: absolute;
  bottom: 8px;
  right: 8px;
  z-index: 3;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 9px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  color: #fff;
  background: rgba(8, 11, 22, 0.55);
  border: 1px solid rgba(255, 255, 255, 0.18);
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
}

/* ---------- Content ----------
   The title leads each row (flex order), so the meta row, location and
   excerpt read as quiet secondary metadata beneath it. Order is pure CSS
   — the template markup / data-test hooks are untouched. z-index:1 keeps
   the text above the card's warm wash. */
.tl-body {
  position: relative;
  z-index: 1;
  grid-column: 2;
  min-width: 0;
  /* Cap to a comfortable reading measure so lines don't run banner-wide;
     the slack is absorbed by the right meta-rail, not empty text. */
  max-width: 62ch;
  display: flex;
  flex-direction: column;
  justify-content: center;
  /* Vertical rhythm is driven by explicit per-element margins (a real
     eyebrow->title->standfirst cadence), not a uniform gap. */
  gap: 0;
  padding: var(--sp-md);
}

.tl-lead-kicker {
  order: 0;
  align-self: flex-start;
  display: inline-flex;
  align-items: center;
  margin-bottom: 8px;
  padding: 2px 9px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.14em;
  color: #fff;
  background: linear-gradient(135deg, var(--accent-warm-from), var(--accent-warm-to));
  box-shadow: 0 2px 6px -1px rgba(244, 63, 94, 0.4);
}

.tl-title {
  order: 1;
}
.tl-meta-row {
  order: 2;
  margin-top: 8px;
}
.tl-loc {
  order: 3;
}
.tl-excerpt {
  order: 4;
}
.tl-more {
  order: 5;
}

/* Tags ride one line and fade out under a mask so a many-tag event can
   never wrap and shove the title down. */
.tl-tags {
  display: flex;
  flex-wrap: nowrap;
  overflow: hidden;
  min-width: 0;
  gap: 6px;
  -webkit-mask-image: linear-gradient(90deg, #000 85%, transparent);
  mask-image: linear-gradient(90deg, #000 85%, transparent);
}

.tl-tag {
  flex: 0 0 auto;
  white-space: nowrap;
  font-size: 12px;
  font-weight: 600;
  padding: 2px 9px;
  border-radius: 999px;
}

/* Warm Spectrum spot #2 — only the FIRST tag wears the event hue (the
   "signature"); the rest stay quiet neutral ghosts so the row reads as
   one accent, not a rainbow of chips. */
.tl-tag--sig {
  color: hsl(var(--ev-hue, 28) 72% 32%);
  background: hsl(var(--ev-hue, 28) 85% 50% / 0.08);
  box-shadow: inset 0 0 0 1px hsl(var(--ev-hue, 28) 80% 50% / 0.42);
  font-weight: 650;
}

.tl-tag:not(.tl-tag--sig) {
  color: var(--ink-500);
  background: transparent;
  box-shadow: inset 0 0 0 1px rgba(15, 23, 42, 0.12);
}

/* ---------- Zone 3: right meta-rail (journal date-stamp) ---------- */
.tl-meta-rail {
  grid-column: 3;
  align-self: stretch;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  justify-content: center;
  gap: 6px;
  padding: var(--sp-md) var(--sp-md) var(--sp-md) var(--sp-lg);
  text-align: right;
  border-left: 1px solid rgba(15, 23, 42, 0.06);
  /* Warm Spectrum spot #4 — a faint hue floor rising from the bottom. */
  background: linear-gradient(180deg, transparent, hsl(var(--ev-hue, 28) 70% 50% / 0.05));
  transition: background var(--dur) var(--ease);
}

.mr-month {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: hsl(var(--ev-hue, 28) 64% 38%);
}

.mr-day {
  font-size: 30px;
  font-weight: 800;
  line-height: 1;
  letter-spacing: -0.03em;
  font-variant-numeric: tabular-nums;
  color: var(--ink-900);
  transition: transform var(--dur) var(--ease);
}

.mr-weekday {
  font-size: 11px;
  font-weight: 600;
  color: var(--ink-500);
}

.mr-divider {
  width: 22px;
  height: 1px;
  margin: 4px 0;
  background: rgba(15, 23, 42, 0.12);
}

.mr-loc {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  max-width: 100%;
  min-width: 0;
  font-size: 11px;
  font-weight: 500;
  color: var(--ink-500);
}

.mr-loc span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mr-photo {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  font-weight: 600;
  color: var(--ink-500);
  font-variant-numeric: tabular-nums;
}

.tl-card:hover .mr-day {
  transform: translateY(-1px);
}

.tl-card:hover .tl-meta-rail {
  background: linear-gradient(180deg, transparent, hsl(var(--ev-hue, 28) 70% 50% / 0.09));
}

.tl-entry:hover .tl-content-col::before,
.tl-entry:focus-within .tl-content-col::before {
  background: linear-gradient(
    90deg,
    hsl(var(--ev-hue, 28) 88% 55% / 0.7),
    hsl(var(--ev-hue, 28) 88% 55% / 0.05)
  );
}

/* Title as a crafted display setting, with the body's ONE signature: a
   short hue hairline on the same left edge as the card spine, fading to
   nothing — it tints, never colours. */
.tl-title {
  position: relative;
  margin: 0;
  padding-bottom: 9px;
  font-size: 19px;
  font-weight: 700;
  color: var(--ink-900);
  letter-spacing: -0.018em;
  line-height: 1.24;
  text-wrap: balance;
  overflow-wrap: anywhere;
  transition: color var(--dur) var(--ease);
}

.tl-title::after {
  content: '';
  position: absolute;
  left: 0;
  bottom: 0;
  width: 28px;
  height: 2px;
  border-radius: 2px;
  background: linear-gradient(
    90deg,
    hsl(var(--ev-hue, 28) 80% 52% / 0.85),
    hsl(var(--ev-hue, 28) 80% 52% / 0)
  );
  transition: width var(--dur) var(--ease);
}

.tl-card:hover .tl-title::after,
.tl-card:focus-within .tl-title::after {
  width: 40px;
}

.tl-card:hover .tl-title,
.tl-card:focus-visible .tl-title {
  color: hsl(var(--ev-hue, 28) 32% 22%);
}

.tl-loc {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  font-weight: 500;
  color: var(--ink-500);
}

/* Excerpt reads as a warm standfirst — near-neutral ink carrying a trace
   of the event hue, tied to the column rather than cool slate caption. */
.tl-excerpt {
  margin: 10px 0 0;
  font-size: 13.5px;
  color: hsl(var(--ev-hue, 28) 10% 36%);
  line-height: 1.62;
  letter-spacing: 0.002em;
  max-width: 54ch;
  overflow-wrap: anywhere;
  word-break: break-word;
  /* Reserve the full 3-line clamp height so EVERY card body is the same
     height and titles land at the same Y. */
  min-height: calc(1.62em * 3);
  display: -webkit-box;
  -webkit-line-clamp: 3;
  line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* No-record state: a characterful hue em-dash note, not a grey apology. */
.tl-excerpt--empty {
  color: hsl(var(--ev-hue, 28) 24% 54%);
  font-style: normal;
  font-size: 13px;
  letter-spacing: 0.01em;
  opacity: 0.92;
}

/* Calm hue read-more — decorative (the whole card is the button), it just
   invites the click and nudges its arrow on hover. */
.tl-more {
  align-self: flex-start;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  margin-top: var(--sp-sm);
  font-size: 12px;
  font-weight: 650;
  letter-spacing: 0.01em;
  color: hsl(var(--ev-hue, 28) 58% 40%);
  opacity: 0.72;
  transition: opacity var(--dur) var(--ease), gap var(--dur) var(--ease),
    color var(--dur) var(--ease);
}

.tl-more-arrow {
  transition: transform var(--dur) var(--ease);
}

.tl-card:hover .tl-more,
.tl-card:focus-visible .tl-more {
  opacity: 1;
  gap: 8px;
  color: hsl(var(--ev-hue, 28) 66% 36%);
}

.tl-card:hover .tl-more-arrow,
.tl-card:focus-visible .tl-more-arrow {
  transform: translateX(3px);
}

/* ---------- Skeleton ---------- */
.tl-card--skel {
  pointer-events: none;
  min-height: 156px;
}

.skel-thumb {
  flex: 0 0 var(--tl-thumb-w, 220px);
  align-self: stretch;
  min-height: 0;
  background: rgba(15, 23, 42, 0.06);
}

.skel-body {
  flex: 1;
  padding: 16px 18px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.skel-line {
  height: 12px;
  border-radius: 4px;
  background: rgba(15, 23, 42, 0.06);
}

.skel-line--title {
  width: 45%;
  height: 18px;
}

.skel-line--text {
  width: 85%;
}

.shimmer {
  position: relative;
  overflow: hidden;
}

.shimmer::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.55), transparent);
  transform: translateX(-100%);
  animation: shimmer-sweep 1.5s ease-in-out infinite;
}

@keyframes shimmer-sweep {
  to {
    transform: translateX(100%);
  }
}

/* ---------- Empty ---------- */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--sp-md);
  padding: 72px 24px;
  background: radial-gradient(closest-side, rgba(245, 158, 11, 0.06), transparent 70%)
      center / 70% 100% no-repeat,
    #fff;
  border: 1px dashed rgba(15, 23, 42, 0.12);
  border-radius: var(--radius-lg);
}

.empty-icon {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, rgba(245, 158, 11, 0.14), rgba(244, 63, 94, 0.14));
  color: var(--accent-warm-ink);
  box-shadow: 0 8px 24px -10px rgba(244, 63, 94, 0.4);
}

.empty-text {
  margin: 0;
  color: var(--ink-500);
  font-size: 14px;
}

/* Respect reduced-motion across the whole timeline, not just the entry
   reveal — kill hover zooms, node pops, connector transitions, shimmer. */
@media (prefers-reduced-motion: reduce) {
  .tl-entry {
    animation: none;
  }
  .tl-card,
  .tl-card .tl-thumb img,
  .tl-node,
  .timeline::after,
  .tl-meta-rail,
  .mr-day,
  .tl-card::before,
  .tl-thumb::after,
  .tl-peek,
  .tl-title,
  .tl-title::after,
  .tl-more,
  .tl-more-arrow,
  .tl-entry .tl-content-col::before {
    transition: none;
  }
  .tl-card:hover .tl-thumb img,
  .tl-card:hover .mr-day,
  .tl-card:hover .tl-more-arrow {
    transform: none;
  }
  /* Drop the cross-fade entirely — no peek under reduced motion. */
  .tl-peek {
    display: none;
  }
  .shimmer::after {
    animation: none;
  }
}

/* Coarse pointers can't hover — keep the read-more affordance shown. */
@media (hover: none) {
  .tl-more {
    opacity: 1;
  }
}

/* ============================================================
   Responsive
   ============================================================ */
@media (max-width: 640px) {
  .page-hero {
    padding: 22px;
    border-radius: var(--radius-lg);
  }
  .hero-title {
    font-size: 28px;
  }
  .hero-content {
    align-items: flex-start;
  }
  .hero-side {
    align-items: flex-start;
    width: 100%;
  }
  .hero-actions {
    width: 100%;
  }
  .filter-row {
    flex-direction: column;
    align-items: stretch;
  }
  .filter-year,
  .filter-tag,
  .sort-toggle {
    width: 100%;
  }

  /* Narrow the rail a touch on phones but keep room for the photo discs
     (lead = 46px). Node centre = half of rail(46) = 23, so the 2.5px
     spine sits at 21.75. */
  .timeline::before,
  .timeline::after {
    left: 21.75px;
  }
  .tl-rail-col {
    flex-basis: 46px;
  }
  .tl-content-col {
    padding-left: 12px;
  }
  .tl-entry .tl-content-col::before {
    left: -22px;
    width: 34px;
  }
  .year-marker {
    top: 64px;
    margin-top: var(--sp-xl);
  }
  .year-label {
    font-size: 24px;
  }

  /* Collapse the 3-zone grid to a single stacked column: cover on top
     (16:9), body, then the meta-rail reflows into a horizontal footer
     strip. The hue spine moves to a top bar. */
  .tl-card {
    grid-template-columns: 1fr;
    min-height: 0;
  }
  .tl-card::before {
    left: 0;
    right: 0;
    top: 0;
    bottom: auto;
    width: auto;
    height: 3px;
  }
  .tl-body {
    grid-column: 1;
    max-width: none;
  }
  .tl-thumb {
    align-self: stretch;
    width: 100%;
    aspect-ratio: 16 / 9;
    min-height: 0;
  }
  .tl-thumb::after {
    background: linear-gradient(
      0deg,
      hsl(var(--ev-hue, 28) 62% 48% / 0.18) 0%,
      transparent 36%
    );
    box-shadow: inset 0 -1px 0 rgba(15, 23, 42, 0.07);
  }
  .tl-meta-rail {
    grid-column: 1;
    flex-direction: row;
    align-items: center;
    justify-content: flex-start;
    flex-wrap: wrap;
    gap: 10px;
    text-align: left;
    border-left: none;
    border-top: 1px solid rgba(15, 23, 42, 0.06);
    padding: 10px var(--sp-md);
  }
  .mr-day {
    font-size: 18px;
  }
  .mr-divider {
    display: none;
  }
}
</style>
