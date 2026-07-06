<script setup>
import { ElButton, ElIcon, ElSkeleton } from 'element-plus'
import {
  Calendar,
  Check,
  Close,
  Briefcase,
  Location,
  School,
  User,
} from '@element-plus/icons-vue'

import { useReviewQueue } from '../composables/useReviewQueue'

const { loading, jobs, events, busyKey, pendingCount, accept, reject } =
  useReviewQueue()

const KIND_LABEL = { internship: '實習', fulltime: '正職' }

function jobYearMonth(j) {
  if (!j?.job_year) return ''
  return j.job_month
    ? `${j.job_year}/${String(j.job_month).padStart(2, '0')}`
    : `${j.job_year}`
}

function formatDate(iso) {
  if (!iso) return '-'
  return new Date(iso).toLocaleDateString('zh-TW', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  })
}

function excerpt(md, max = 90) {
  if (!md) return ''
  const plain = md.replace(/[#*`>_~\-![\]()]/g, '').replace(/\s+/g, ' ').trim()
  return plain.length > max ? `${plain.slice(0, max)}…` : plain
}
</script>

<template>
  <div class="review-page" data-test="review-page">
    <header class="page-header">
      <div class="title-row">
        <span class="title-icon" aria-hidden="true">
          <el-icon :size="20"><Check /></el-icon>
        </span>
        <h1 class="title">審核</h1>
        <span class="count-chip" data-test="pending-count">
          {{ pendingCount }} 筆待審
        </span>
      </div>
      <p class="subtitle">通過後內容才會公開；退回時填寫原因，發表者可修正後重送。</p>
    </header>

    <el-skeleton v-if="loading" :rows="5" animated />

    <div
      v-else-if="pendingCount === 0"
      class="empty-state"
      data-test="review-empty"
    >
      <div class="empty-icon" aria-hidden="true">
        <el-icon :size="30"><Check /></el-icon>
      </div>
      <p>目前沒有待審核的內容 🎉</p>
    </div>

    <template v-else>
      <!-- ---------- Pending jobs ---------- -->
      <section v-if="jobs.length" class="review-section">
        <h2 class="section-title">
          <el-icon :size="16"><Briefcase /></el-icon>
          待審求職 <span class="section-count">{{ jobs.length }}</span>
        </h2>
        <ul class="review-list">
          <li
            v-for="j in jobs"
            :key="j.id"
            class="review-card"
            data-test="pending-job-row"
          >
            <div class="review-card__body">
              <div class="review-card__head">
                <span class="kind-badge">{{
                  KIND_LABEL[j.kind] ?? j.kind
                }}</span>
                <span v-if="j.category" class="cat-chip">{{ j.category }}</span>
              </div>
              <h3 class="review-card__title">{{ j.company }}</h3>
              <div class="review-card__meta">
                <span :class="{ 'is-anon': !j.display_name }">
                  <el-icon :size="12"><User /></el-icon>
                  {{ j.display_name || '匿名' }}
                </span>
                <span>
                  <el-icon :size="12"><School /></el-icon>
                  {{ jobYearMonth(j) }} 求職
                </span>
              </div>
              <p v-if="excerpt(j.experience_md)" class="review-card__excerpt">
                {{ excerpt(j.experience_md) }}
              </p>
            </div>
            <div class="review-card__actions">
              <el-button
                type="success"
                :icon="Check"
                :loading="busyKey === `job-${j.id}`"
                :data-test="`accept-job-${j.id}`"
                @click="accept('job', j)"
              >
                通過
              </el-button>
              <el-button
                type="danger"
                plain
                :icon="Close"
                :disabled="busyKey === `job-${j.id}`"
                :data-test="`reject-job-${j.id}`"
                @click="reject('job', j)"
              >
                退回
              </el-button>
            </div>
          </li>
        </ul>
      </section>

      <!-- ---------- Pending events ---------- -->
      <section v-if="events.length" class="review-section">
        <h2 class="section-title">
          <el-icon :size="16"><Calendar /></el-icon>
          待審活動 <span class="section-count">{{ events.length }}</span>
        </h2>
        <ul class="review-list">
          <li
            v-for="e in events"
            :key="e.id"
            class="review-card"
            data-test="pending-event-row"
          >
            <div class="review-card__body">
              <div v-if="e.tags?.length" class="review-card__head">
                <span v-for="t in e.tags" :key="t" class="cat-chip"
                  >#{{ t }}</span
                >
              </div>
              <h3 class="review-card__title">{{ e.title }}</h3>
              <div class="review-card__meta">
                <span v-if="e.author_display_name">
                  <el-icon :size="12"><User /></el-icon>
                  {{ e.author_display_name }}
                </span>
                <span>
                  <el-icon :size="12"><Calendar /></el-icon>
                  {{ formatDate(e.event_date) }}
                </span>
                <span v-if="e.location">
                  <el-icon :size="12"><Location /></el-icon>
                  {{ e.location }}
                </span>
              </div>
              <p v-if="excerpt(e.description_md)" class="review-card__excerpt">
                {{ excerpt(e.description_md) }}
              </p>
            </div>
            <div class="review-card__actions">
              <el-button
                type="success"
                :icon="Check"
                :loading="busyKey === `event-${e.id}`"
                :data-test="`accept-event-${e.id}`"
                @click="accept('event', e)"
              >
                通過
              </el-button>
              <el-button
                type="danger"
                plain
                :icon="Close"
                :disabled="busyKey === `event-${e.id}`"
                :data-test="`reject-event-${e.id}`"
                @click="reject('event', e)"
              >
                退回
              </el-button>
            </div>
          </li>
        </ul>
      </section>
    </template>
  </div>
</template>

<style scoped>
.review-page {
  max-width: 900px;
  margin: 0 auto;
}

.page-header {
  margin-bottom: 24px;
}

.title-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.title-icon {
  width: 38px;
  height: 38px;
  border-radius: var(--radius-md);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  background: linear-gradient(135deg, var(--brand-primary), var(--brand-accent));
  box-shadow: 0 6px 16px rgba(99, 102, 241, 0.28);
}

.title {
  margin: 0;
  font-size: 26px;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.count-chip {
  font-size: 13px;
  font-weight: 600;
  color: var(--brand-primary-hover);
  background: rgba(99, 102, 241, 0.12);
  padding: 4px 12px;
  border-radius: 999px;
}

.subtitle {
  margin: 10px 0 0;
  font-size: 14px;
  color: var(--ink-500);
}

.review-section {
  margin-top: 24px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 12px;
  font-size: 16px;
  font-weight: 700;
  color: var(--ink-900);
}

.section-count {
  font-size: 12px;
  font-weight: 700;
  color: var(--ink-500);
  background: var(--surface-2);
  border-radius: 999px;
  padding: 1px 9px;
}

.review-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.review-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  flex-wrap: wrap;
  background: var(--surface-0);
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: var(--radius-lg);
  padding: 18px 22px;
  box-shadow: var(--shadow-sm);
}

.review-card__body {
  min-width: 0;
  flex: 1;
}

.review-card__head {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 6px;
}

.kind-badge {
  font-size: 11px;
  font-weight: 600;
  padding: 3px 9px;
  border-radius: 999px;
  background: rgba(99, 102, 241, 0.12);
  color: var(--brand-primary-hover);
}

.cat-chip {
  font-size: 11px;
  font-weight: 600;
  padding: 3px 9px;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.06);
  color: var(--ink-700);
}

.review-card__title {
  margin: 0 0 6px;
  font-size: 17px;
  font-weight: 700;
  color: var(--ink-900);
}

.review-card__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  font-size: 12px;
  color: var(--ink-500);
}

.review-card__meta span {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.review-card__meta .is-anon {
  font-style: italic;
  color: var(--ink-400, #94a3b8);
}

.review-card__excerpt {
  margin: 8px 0 0;
  font-size: 13px;
  color: var(--ink-700);
  line-height: 1.6;
}

.review-card__actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.review-card__actions :deep(.el-button + .el-button) {
  margin-left: 0;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 60px 20px;
  color: var(--ink-500);
}

.empty-icon {
  width: 60px;
  height: 60px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #22c55e;
  background: rgba(34, 197, 94, 0.12);
}

@media (max-width: 640px) {
  .review-card {
    align-items: stretch;
  }
  .review-card__actions {
    width: 100%;
  }
  .review-card__actions :deep(.el-button) {
    flex: 1;
  }
}
</style>
