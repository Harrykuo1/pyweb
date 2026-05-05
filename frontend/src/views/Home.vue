<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElIcon } from 'element-plus'
import {
  ArrowRight,
  Briefcase,
  Calendar,
  OfficeBuilding,
  UserFilled,
} from '@element-plus/icons-vue'

import ActivityFeed from '../components/ActivityFeed.vue'
import ActivityFeedPreview from '../components/ActivityFeedPreview.vue'
import { membersApi } from '../api/members'
import { statsApi } from '../api/stats'
import { useCounter } from '../utils/useCounter'

const router = useRouter()

// ---------- Stats + recent members for the avatar pile ----------
const stats = ref({ total_members: 0, total_jobs: 0 })
const statsLoaded = ref(false)
const PILE_LIMIT = 6
const PILE_MIN_TO_SHOW = 3
const recentMembers = ref([])

onMounted(async () => {
  const tasks = [
    statsApi
      .get()
      .then((d) => {
        stats.value = d
      })
      .catch(() => {
        /* keep zeros */
      }),
    membersApi
      .list({ order: 'desc' })
      .then((rows) => {
        recentMembers.value = (rows ?? []).slice(0, PILE_LIMIT)
      })
      .catch(() => {
        recentMembers.value = []
      }),
  ]
  try {
    await Promise.all(tasks)
  } finally {
    statsLoaded.value = true
  }
})

const membersCount = useCounter(() => stats.value.total_members)
const jobsCount = useCounter(() => stats.value.total_jobs)

const showPile = computed(
  () =>
    statsLoaded.value &&
    stats.value.total_members >= PILE_MIN_TO_SHOW &&
    recentMembers.value.length > 0,
)

const overflowCount = computed(() => {
  const total = stats.value.total_members
  const shown = recentMembers.value.length
  return Math.max(0, total - shown)
})

const heroSubtitle = computed(() => {
  if (!statsLoaded.value) return '正在點亮 pyweb 社群…'
  const total = stats.value.total_members
  if (total === 0) return '社群剛剛起步，等你來寫下第一筆故事。'
  if (total < PILE_MIN_TO_SHOW) {
    return `${total} 位學長姊已經在這裡，等你一起加入。`
  }
  return '在這裡找到自己的下一段故事。'
})

function memberPhotoSrc(m) {
  if (!m?.has_photo) return null
  return membersApi.photoUrl(m.id, m.photo_updated_at ?? '')
}

function memberInitial(m) {
  const name = m?.real_name ?? ''
  return name.charAt(0) || '?'
}

function goMembers() {
  router.push('/members')
}

function focusMember(id) {
  // Each pile avatar deep-links to that specific member via the
  // shared focusRoute helper, so the Members page scrolls + flashes
  // the matching card on arrival.
  router.push(membersApi.focusRoute(id))
}
</script>

<template>
  <div class="home-page">
    <section class="hero" data-test="hero">
      <div class="hero-mesh" aria-hidden="true">
        <span class="mesh-blob mesh-blob-a"></span>
        <span class="mesh-blob mesh-blob-b"></span>
        <span class="mesh-blob mesh-blob-c"></span>
        <span class="mesh-blob mesh-blob-d"></span>
        <span class="mesh-grain"></span>
      </div>

      <!-- ============================================================
           Hero L/R band:
             left  → spotlight (members count + pile + 2 mini stats)
             right → activity preview (4 latest events)
           Both columns stretch to equal height so the hero stays
           visually balanced regardless of how dense each side is.
           ============================================================ -->
      <div class="hero-cols">
        <div class="spotlight-card" data-test="spotlight-card">
          <div class="spotlight-primary">
            <!-- Text block routes to the full /members list. The pile
                 below is intentionally OUTSIDE this button so each
                 avatar can be its own button without nested-button
                 HTML problems — clicking a face deep-links to that
                 specific member. -->
            <button
              type="button"
              class="spotlight-cta"
              :aria-label="`已有 ${stats.total_members} 位社群成員，點擊瀏覽全部`"
              data-test="spotlight-cta"
              @click="goMembers"
            >
              <span class="spotlight-eyebrow">已有</span>
              <span class="spotlight-number" data-test="spotlight-number">
                <span class="spotlight-number-value">{{ membersCount }}</span>
                <span class="spotlight-number-unit">位</span>
              </span>
              <span class="spotlight-label">社群成員正在這裡</span>
              <span class="spotlight-sub" data-test="hero-sub">{{ heroSubtitle }}</span>
            </button>

            <div
              v-if="showPile"
              class="member-pile"
              :data-count="recentMembers.length"
              data-test="member-pile"
            >
              <button
                v-for="(m, i) in recentMembers"
                :key="m.id"
                type="button"
                class="pile-avatar"
                :style="{
                  zIndex: PILE_LIMIT - i,
                  '--pile-index': i,
                }"
                :title="m.real_name"
                :aria-label="`查看 ${m.real_name}`"
                :data-test="`pile-avatar-${m.id}`"
                @click="focusMember(m.id)"
              >
                <img
                  v-if="m.has_photo"
                  :src="memberPhotoSrc(m)"
                  :alt="`${m.real_name} 的頭像`"
                />
                <span v-else class="pile-letter" aria-hidden="true">
                  {{ memberInitial(m) }}
                </span>
              </button>
              <button
                v-if="overflowCount > 0"
                type="button"
                class="pile-overflow"
                aria-label="瀏覽全部成員"
                @click="goMembers"
              >
                +{{ overflowCount }}
              </button>
              <button
                type="button"
                class="pile-hint"
                @click="goMembers"
              >
                認識他們
                <el-icon :size="12"><ArrowRight /></el-icon>
              </button>
            </div>
          </div>

          <div class="spotlight-secondary" data-test="spotlight-secondary">
            <button
              type="button"
              class="mini-stat mini-stat--clickable"
              data-test="mini-stat-jobs"
              @click="router.push('/jobs')"
            >
              <span class="mini-stat-icon mini-stat-icon--jobs">
                <el-icon :size="16"><Briefcase /></el-icon>
              </span>
              <span class="mini-stat-body">
                <span class="mini-stat-value">{{ jobsCount }}</span>
                <span class="mini-stat-label">求職紀錄</span>
              </span>
            </button>

            <div
              class="mini-stat mini-stat--placeholder"
              data-test="mini-stat-activities"
              aria-disabled="true"
            >
              <span class="mini-stat-icon mini-stat-icon--activities">
                <el-icon :size="16"><Calendar /></el-icon>
              </span>
              <span class="mini-stat-body">
                <span class="mini-stat-pill">規劃中</span>
                <span class="mini-stat-label">活動紀錄</span>
              </span>
            </div>
          </div>
        </div>

        <ActivityFeedPreview :limit="5" />
      </div>
    </section>

    <section class="feature-grid">
      <article
        class="feature-card"
        data-test="card-members"
        @click="router.push('/members')"
      >
        <span class="feature-accent feature-accent-indigo"></span>
        <div class="feature-icon-wrap feature-icon-indigo">
          <el-icon :size="22"><UserFilled /></el-icon>
        </div>
        <h3 class="feature-title">成員介紹</h3>
        <p class="feature-desc">瀏覽所有社群成員的基本資訊、履歷與聯絡方式。</p>
        <span class="feature-cta">
          查看清單 <span aria-hidden="true">→</span>
        </span>
      </article>

      <article
        class="feature-card"
        data-test="card-jobs"
        @click="router.push('/jobs')"
      >
        <span class="feature-accent feature-accent-violet"></span>
        <div class="feature-icon-wrap feature-icon-violet">
          <el-icon :size="22"><OfficeBuilding /></el-icon>
        </div>
        <h3 class="feature-title">求職紀錄</h3>
        <p class="feature-desc">分享實習與正職的求職心得、面試經驗與時程表。</p>
        <span class="feature-cta">
          查看清單 <span aria-hidden="true">→</span>
        </span>
      </article>

      <article class="feature-card is-disabled">
        <span class="feature-accent feature-accent-mute"></span>
        <div class="feature-icon-wrap feature-icon-mute">
          <el-icon :size="22"><Calendar /></el-icon>
        </div>
        <h3 class="feature-title">活動紀錄</h3>
        <p class="feature-desc">未來規劃中，記錄社群聚會、講座與工作坊。</p>
        <span class="feature-status feature-status-mute">規劃中</span>
      </article>
    </section>

    <div id="activity-feed-section">
      <ActivityFeed :limit="10" />
    </div>
  </div>
</template>

<style scoped>
.home-page {
  display: flex;
  flex-direction: column;
  gap: var(--sp-lg);
}

/* ============================================================
   HERO — single L/R band:
     left  → spotlight card (members count + pile + mini stats)
     right → activity preview (4 latest events)
   ============================================================ */
.hero {
  position: relative;
  overflow: hidden;
  border-radius: var(--radius-xl);
  padding: 28px;
  color: #ffffff;
  background: linear-gradient(135deg, #1e1b4b 0%, #312e81 60%, #4338ca 100%);
  box-shadow: 0 24px 48px -16px rgba(49, 46, 129, 0.6),
    0 0 0 1px rgba(255, 255, 255, 0.04) inset;
}

/* ---------- Mesh gradient background ---------- */
.hero-mesh {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
}

.mesh-blob {
  position: absolute;
  border-radius: 50%;
  filter: blur(60px);
  opacity: 0.7;
}

.mesh-blob-a {
  top: -120px;
  right: -80px;
  width: 480px;
  height: 480px;
  background: radial-gradient(closest-side, #c084fc 0%, transparent 70%);
}

.mesh-blob-b {
  bottom: -120px;
  right: 18%;
  width: 380px;
  height: 380px;
  background: radial-gradient(closest-side, #a78bfa 0%, transparent 70%);
  opacity: 0.55;
}

.mesh-blob-c {
  top: 30%;
  left: -100px;
  width: 360px;
  height: 360px;
  background: radial-gradient(closest-side, #6366f1 0%, transparent 70%);
  opacity: 0.55;
}

.mesh-blob-d {
  top: -60px;
  left: 30%;
  width: 280px;
  height: 280px;
  background: radial-gradient(closest-side, #ec4899 0%, transparent 70%);
  opacity: 0.35;
}

.mesh-grain {
  position: absolute;
  inset: 0;
  background-image: radial-gradient(
      circle at 1px 1px,
      rgba(255, 255, 255, 0.04) 1px,
      transparent 0
    );
  background-size: 3px 3px;
  mix-blend-mode: overlay;
  opacity: 0.5;
}

/* ============================================================
   L/R band: spotlight | preview
   ============================================================ */
.hero-cols {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 18px;
  align-items: stretch;
}

/* ---------- Spotlight card ---------- */
.spotlight-card {
  position: relative;
  isolation: isolate;
  display: flex;
  flex-direction: column;
  width: 100%;
  min-width: 0;
  height: 100%;
  /* height:100% pairs with the grid's align-items:stretch so this
     card matches the preview's vertical extent — without it the
     cards end at different Y values and the hero looks ragged.
     box-sizing:border-box prevents the padding from pushing the
     card past its grid cell — there's no global reset in this
     project so it has to be explicit. */
  box-sizing: border-box;
  padding: 20px 22px 16px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.14);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  box-shadow: 0 12px 32px rgba(15, 23, 42, 0.22),
    0 0 0 1px rgba(255, 255, 255, 0.04) inset;
  color: #ffffff;
}

/* Soft glow behind the number — pulses once on mount, then settles. */
.spotlight-card::before {
  content: '';
  position: absolute;
  top: 30%;
  left: 16%;
  width: 220px;
  height: 220px;
  border-radius: 50%;
  background: radial-gradient(closest-side, #d946ef 0%, transparent 70%);
  filter: blur(40px);
  opacity: 0.45;
  z-index: -1;
  pointer-events: none;
  animation: spotlight-pulse 2.4s ease-out 0.2s 1 backwards;
}

@keyframes spotlight-pulse {
  0% { transform: scale(0.7); opacity: 0; }
  60% { transform: scale(1.1); opacity: 0.6; }
  100% { transform: scale(1); opacity: 0.45; }
}

/* ---------- Spotlight primary (wrapper, not interactive) ---------- */
.spotlight-primary {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 12px;
  padding: 0 0 14px;
}

/* The text block is the "go to /members list" affordance — pile
   avatars below are their own buttons that deep-link to specific
   members, so clicking them must NOT bubble up here. The pile
   sits outside this button for that reason. */
.spotlight-cta {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  padding: 0;
  background: transparent;
  border: 0;
  text-align: left;
  font: inherit;
  color: inherit;
  cursor: pointer;
  outline: none;
  border-radius: 8px;
  transition: transform var(--dur) var(--ease);
}

.spotlight-cta:hover,
.spotlight-cta:focus-visible {
  transform: translateY(-2px);
}

.spotlight-cta:focus-visible {
  box-shadow: 0 0 0 3px rgba(192, 132, 252, 0.4);
}

.spotlight-eyebrow {
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 0.08em;
  color: rgba(255, 255, 255, 0.7);
  text-transform: uppercase;
}

.spotlight-number {
  display: inline-flex;
  align-items: baseline;
  gap: 5px;
  margin: 1px 0 2px;
  line-height: 1;
}

.spotlight-number-value {
  font-size: 64px;
  font-weight: 800;
  letter-spacing: -0.04em;
  font-variant-numeric: tabular-nums;
  background: linear-gradient(180deg, #ffffff 0%, #e9d5ff 75%, #c084fc 100%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  color: transparent;
  text-shadow: 0 4px 24px rgba(192, 132, 252, 0.35);
}

.spotlight-number-unit {
  font-size: 18px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.85);
  letter-spacing: -0.01em;
}

.spotlight-label {
  font-size: 14px;
  font-weight: 600;
  color: #ffffff;
  letter-spacing: -0.01em;
}

.spotlight-sub {
  font-size: 12.5px;
  color: rgba(255, 255, 255, 0.7);
  letter-spacing: 0.01em;
  line-height: 1.55;
  margin-top: 2px;
}

/* ---------- Member pile (each avatar is its own button) ---------- */
.member-pile {
  display: inline-flex;
  align-items: center;
  padding-left: 4px;
}

.pile-avatar {
  position: relative;
  width: 30px;
  height: 30px;
  padding: 0;
  border-radius: 50%;
  border: 2px solid #312e81;
  margin-left: -10px;
  background: linear-gradient(135deg, #c084fc, #818cf8);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  box-shadow: 0 2px 6px rgba(15, 23, 42, 0.35);
  cursor: pointer;
  outline: none;
  font: inherit;
  color: inherit;
  transition: transform var(--dur) var(--ease),
    box-shadow var(--dur) var(--ease);
  animation: pile-in 0.45s var(--ease) backwards;
  animation-delay: calc(var(--pile-index, 0) * 60ms + 200ms);
}

.pile-avatar:first-child {
  margin-left: 0;
}

.pile-avatar:hover,
.pile-avatar:focus-visible {
  transform: translateY(-2px) scale(1.08);
  z-index: 100 !important;
  box-shadow: 0 6px 16px rgba(192, 132, 252, 0.55);
}

.pile-avatar:focus-visible {
  border-color: #f0abfc;
}

.pile-avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.pile-letter {
  font-size: 12px;
  font-weight: 700;
  color: #ffffff;
  text-transform: uppercase;
}

@keyframes pile-in {
  from { opacity: 0; transform: translateX(-6px) scale(0.7); }
  to { opacity: 1; transform: translateX(0) scale(1); }
}

/* Fan the pile out a touch when the user hovers any avatar so the
   neighbouring faces stay readable. The hovered avatar overrides
   this with its own scale rule above. */
.member-pile:hover .pile-avatar {
  transform: translateX(calc(var(--pile-index, 0) * 4px));
}

.pile-overflow {
  margin-left: -6px;
  padding: 0 9px;
  height: 30px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.16);
  border: 1px solid rgba(255, 255, 255, 0.22);
  color: #ffffff;
  font-size: 11.5px;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  letter-spacing: 0.02em;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  cursor: pointer;
  outline: none;
  font-family: inherit;
  transition: background var(--dur) var(--ease),
    border-color var(--dur) var(--ease);
}

.pile-overflow:hover,
.pile-overflow:focus-visible {
  background: rgba(255, 255, 255, 0.24);
  border-color: rgba(255, 255, 255, 0.36);
}

.pile-hint {
  margin-left: 12px;
  padding: 0;
  background: transparent;
  border: 0;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.7);
  letter-spacing: 0.02em;
  cursor: pointer;
  outline: none;
  font-family: inherit;
  transition: color var(--dur) var(--ease),
    transform var(--dur) var(--ease);
}

.pile-hint:hover,
.pile-hint:focus-visible {
  color: #ffffff;
  transform: translateX(2px);
}

/* ---------- Spotlight secondary (jobs + activities) ----------
   margin-top:auto pushes this row to the bottom of the spotlight
   card so the divider hugs the bottom edge regardless of how tall
   the card stretched to match the preview. */
.spotlight-secondary {
  margin-top: auto;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  padding-top: 12px;
  border-top: 1px solid rgba(255, 255, 255, 0.14);
}

.mini-stat {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 8px 10px;
  border-radius: 11px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.08);
  text-align: left;
  font: inherit;
  color: inherit;
  transition: background var(--dur) var(--ease),
    border-color var(--dur) var(--ease),
    transform var(--dur) var(--ease);
}

.mini-stat--clickable {
  cursor: pointer;
  outline: none;
}

.mini-stat--clickable:hover,
.mini-stat--clickable:focus-visible {
  background: rgba(255, 255, 255, 0.14);
  border-color: rgba(255, 255, 255, 0.24);
  transform: translateY(-1px);
}

.mini-stat--placeholder {
  cursor: default;
  opacity: 0.7;
}

.mini-stat-icon {
  flex: 0 0 auto;
  width: 28px;
  height: 28px;
  border-radius: 9px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #ffffff;
  box-shadow: 0 4px 10px rgba(0, 0, 0, 0.18);
}

.mini-stat-icon--jobs {
  background: linear-gradient(135deg, #8b5cf6, #d946ef);
}

.mini-stat-icon--activities {
  background: linear-gradient(135deg, #475569, #64748b);
  box-shadow: none;
}

.mini-stat-body {
  display: flex;
  flex-direction: column;
  min-width: 0;
  line-height: 1.15;
}

.mini-stat-value {
  font-size: 19px;
  font-weight: 700;
  color: #ffffff;
  letter-spacing: -0.01em;
  font-variant-numeric: tabular-nums;
  line-height: 1.1;
}

.mini-stat-pill {
  align-self: flex-start;
  font-size: 10.5px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.16);
  color: rgba(255, 255, 255, 0.92);
  letter-spacing: 0.04em;
}

.mini-stat-label {
  margin-top: 1px;
  font-size: 11.5px;
  color: rgba(255, 255, 255, 0.7);
  letter-spacing: 0.02em;
}

/* ============================================================
   Feature grid (unchanged below the hero).
   ============================================================ */
.feature-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: var(--sp-md);
}

.feature-card {
  position: relative;
  overflow: hidden;
  background: var(--surface-0);
  border: 1px solid rgba(15, 23, 42, 0.06);
  border-radius: var(--radius-lg);
  padding: 24px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: var(--sp-sm);
  transition: transform var(--dur) var(--ease),
    box-shadow var(--dur) var(--ease), border-color var(--dur) var(--ease);
}

.feature-card:hover:not(.is-disabled) {
  transform: translateY(-4px);
  box-shadow: var(--shadow-lg);
  border-color: rgba(99, 102, 241, 0.2);
}

.feature-card:hover:not(.is-disabled) .feature-accent {
  height: 100%;
}

.feature-accent {
  position: absolute;
  left: 0;
  top: 0;
  width: 4px;
  height: 56px;
  border-radius: 0 4px 4px 0;
  transition: height var(--dur) var(--ease);
}
.feature-accent-indigo {
  background: linear-gradient(180deg, #6366f1, #8b5cf6);
}
.feature-accent-violet {
  background: linear-gradient(180deg, #8b5cf6, #d946ef);
}
.feature-accent-mute {
  background: var(--ink-300);
}

.feature-icon-wrap {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #ffffff;
  margin-bottom: var(--sp-xs);
}
.feature-icon-indigo {
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  box-shadow: 0 6px 16px rgba(99, 102, 241, 0.3);
}
.feature-icon-violet {
  background: linear-gradient(135deg, #8b5cf6, #d946ef);
  box-shadow: 0 6px 16px rgba(139, 92, 246, 0.3);
}
.feature-icon-mute {
  background: var(--surface-2);
  color: var(--ink-500);
}

.feature-title {
  margin: 4px 0 0;
  font-size: 17px;
  font-weight: 600;
  color: var(--ink-900);
}

.feature-desc {
  margin: 0;
  font-size: 13px;
  color: var(--ink-500);
  line-height: 1.7;
  flex: 1;
}

.feature-cta {
  margin-top: var(--sp-sm);
  font-size: 13px;
  font-weight: 500;
  color: var(--brand-primary);
}
.feature-card:hover .feature-cta {
  color: var(--brand-primary-hover);
}

.feature-status {
  margin-top: var(--sp-sm);
  align-self: flex-start;
  font-size: 11px;
  font-weight: 500;
  padding: 3px 10px;
  border-radius: 999px;
  letter-spacing: 0.02em;
}
.feature-status-soon {
  background: rgba(139, 92, 246, 0.12);
  color: #7c3aed;
}
.feature-status-mute {
  background: var(--surface-2);
  color: var(--ink-500);
}

.feature-card.is-disabled {
  cursor: default;
  opacity: 0.65;
}
.feature-card.is-disabled:hover {
  transform: none;
  box-shadow: none;
  border-color: rgba(15, 23, 42, 0.06);
}

/* ============================================================
   Mobile
   ============================================================ */
@media (max-width: 1024px) {
  .hero-cols {
    grid-template-columns: 1fr;
    gap: 14px;
  }
}

@media (max-width: 640px) {
  .hero {
    padding: 18px;
    border-radius: var(--radius-lg);
  }
  .spotlight-card {
    padding: 18px 18px 14px;
  }
  .spotlight-number-value {
    font-size: 56px;
  }
  .spotlight-number-unit {
    font-size: 16px;
  }
  .pile-avatar {
    width: 28px;
    height: 28px;
  }
  .pile-overflow {
    height: 28px;
    font-size: 11px;
  }
  .mesh-blob-b,
  .mesh-blob-d {
    display: none;
  }
  .mesh-blob-a {
    width: 280px;
    height: 280px;
  }
  .mesh-blob-c {
    width: 240px;
    height: 240px;
  }
  .feature-grid {
    grid-template-columns: 1fr;
  }
}
</style>
