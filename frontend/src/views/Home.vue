<script setup>
import { useRouter } from 'vue-router'
import { ElButton, ElIcon } from 'element-plus'
import {
  ArrowRight,
  Calendar,
  OfficeBuilding,
  UserFilled,
} from '@element-plus/icons-vue'

import ActivityFeed from '../components/ActivityFeed.vue'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()

</script>

<template>
  <div class="home-page">
    <section class="hero">
      <div class="hero-decor" aria-hidden="true">
        <span class="decor decor-a"></span>
        <span class="decor decor-b"></span>
        <span class="decor decor-c"></span>
      </div>

      <div class="hero-inner">
        <h1 class="hero-title">
          歡迎回來，{{ auth.user?.username }}
          <span class="wave" aria-hidden="true">👋</span>
        </h1>
        <p class="hero-sub">
          這是 pyweb 社群的成員管理平台。
          <span v-if="auth.isAdmin">您可以新增、編輯、刪除成員與求職紀錄。</span>
          <span v-else>您目前以檢視者身份登入，可瀏覽全部資料。</span>
        </p>
        <div class="hero-actions">
          <el-button
            class="hero-cta"
            size="large"
            data-test="hero-cta"
            @click="router.push('/members')"
          >
            瀏覽成員
            <el-icon class="hero-cta-icon"><ArrowRight /></el-icon>
          </el-button>
        </div>
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

    <ActivityFeed :limit="10" />
  </div>
</template>

<style scoped>
.home-page {
  display: flex;
  flex-direction: column;
  gap: var(--sp-lg);
}

/* ---------- Hero ---------- */
.hero {
  position: relative;
  overflow: hidden;
  border-radius: var(--radius-xl);
  padding: 56px 56px 60px;
  background: linear-gradient(
    135deg,
    #312e81 0%,
    #4f46e5 35%,
    #6366f1 60%,
    #8b5cf6 100%
  );
  color: #fff;
  box-shadow: var(--shadow-lg);
}

.hero-inner {
  position: relative;
  z-index: 1;
  max-width: 640px;
}

.hero-title {
  margin: 0 0 var(--sp-md);
  font-size: 36px;
  font-weight: 700;
  color: #fff;
  letter-spacing: -0.01em;
  line-height: 1.2;
}

.wave {
  display: inline-block;
  animation: wave 2s ease-in-out 0.5s 2;
  transform-origin: 70% 70%;
}

@keyframes wave {
  0%,
  60%,
  100% {
    transform: rotate(0deg);
  }
  10%,
  30% {
    transform: rotate(14deg);
  }
  20% {
    transform: rotate(-8deg);
  }
  40% {
    transform: rotate(14deg);
  }
  50% {
    transform: rotate(-4deg);
  }
}

.hero-sub {
  margin: 0 0 var(--sp-lg);
  font-size: 15px;
  color: rgba(255, 255, 255, 0.86);
  line-height: 1.75;
  max-width: 540px;
}

.hero-actions {
  display: flex;
  gap: var(--sp-md);
}

/* The CTA button needs to override Element Plus default styling, so we
   reach into it via :deep — the .hero-cta class lands on the inner
   <button>, but EP's own selectors are higher specificity. */
:deep(.hero-cta) {
  background: #ffffff;
  color: var(--brand-primary);
  border: 0;
  font-weight: 600;
  padding: 0 22px;
  height: 44px;
  border-radius: var(--radius-md);
}
:deep(.hero-cta:hover) {
  background: #ffffff;
  color: var(--brand-primary-hover);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
}

.hero-cta-icon {
  margin-left: 6px;
  vertical-align: -2px;
  transition: transform var(--dur) var(--ease);
}

:deep(.hero-cta:hover) .hero-cta-icon {
  transform: translateX(3px);
}

/* Decorative floating circles — pure CSS, no SVG */
.hero-decor {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
}

.decor {
  position: absolute;
  border-radius: 50%;
  filter: blur(40px);
}

.decor-a {
  top: -80px;
  right: -60px;
  width: 320px;
  height: 320px;
  background: radial-gradient(closest-side, #c084fc, transparent);
  opacity: 0.55;
}
.decor-b {
  bottom: -100px;
  right: 140px;
  width: 240px;
  height: 240px;
  background: radial-gradient(closest-side, #a78bfa, transparent);
  opacity: 0.45;
}
.decor-c {
  top: 35%;
  right: 22%;
  width: 200px;
  height: 200px;
  background: radial-gradient(closest-side, #818cf8, transparent);
  opacity: 0.35;
}

/* ---------- Feature grid ---------- */
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

/* ---------- Mobile ---------- */
@media (max-width: 640px) {
  .hero {
    padding: 32px 24px 36px;
    border-radius: var(--radius-lg);
  }
  .hero-title {
    font-size: 26px;
  }
  .hero-sub {
    font-size: 14px;
  }
  .decor-a {
    width: 220px;
    height: 220px;
  }
  .decor-b,
  .decor-c {
    display: none;
  }
  .feature-grid {
    grid-template-columns: 1fr;
  }
}
</style>
