<script setup>
import { useRouter } from 'vue-router'
import { ElCard, ElIcon } from 'element-plus'
import { Calendar, OfficeBuilding, UserFilled } from '@element-plus/icons-vue'

import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()

function notReady() {
  alert('此功能即將推出')
}
</script>

<template>
  <div class="home-page">
    <section class="welcome-card">
      <div class="welcome-text">
        <h1 class="welcome-title">歡迎，{{ auth.user?.username }} 👋</h1>
        <p class="welcome-sub">
          這是 pyweb 社群的成員管理平台。
          <span v-if="auth.isAdmin">您可以新增、編輯、刪除成員與實習紀錄。</span>
          <span v-else>您目前以檢視者身份登入。</span>
        </p>
      </div>
    </section>

    <section class="feature-grid">
      <el-card
        class="feature-card"
        shadow="hover"
        body-class="feature-card-body"
        data-test="card-members"
        @click="router.push('/members')"
      >
        <el-icon class="feature-icon" :size="32"><UserFilled /></el-icon>
        <h3 class="feature-title">成員介紹</h3>
        <p class="feature-desc">瀏覽所有社群成員的基本資訊與履歷。</p>
        <div class="feature-status">查看清單 →</div>
      </el-card>

      <el-card
        class="feature-card"
        shadow="hover"
        body-class="feature-card-body"
        data-test="card-internships"
        @click="notReady"
      >
        <el-icon class="feature-icon" :size="32"><OfficeBuilding /></el-icon>
        <h3 class="feature-title">實習工作紀錄</h3>
        <p class="feature-desc">分享求職心得、面試經驗與時程表。</p>
        <div class="feature-status">即將推出</div>
      </el-card>

      <el-card
        class="feature-card disabled-card"
        body-class="feature-card-body"
      >
        <el-icon class="feature-icon" :size="32"><Calendar /></el-icon>
        <h3 class="feature-title">活動紀錄</h3>
        <p class="feature-desc">未來規劃中的功能。</p>
        <div class="feature-status">規劃中</div>
      </el-card>
    </section>
  </div>
</template>

<style scoped>
.home-page {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.welcome-card {
  background: linear-gradient(135deg, #409eff 0%, #67c23a 100%);
  color: #ffffff;
  padding: 32px;
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(64, 158, 255, 0.2);
}

.welcome-title {
  margin: 0 0 8px;
  font-size: 26px;
  color: #ffffff;
}

.welcome-sub {
  margin: 0;
  font-size: 14px;
  opacity: 0.9;
}

.feature-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 16px;
}

.feature-card {
  border-radius: 12px;
  cursor: pointer;
  transition: transform 0.15s ease;
}

.feature-card:hover {
  transform: translateY(-2px);
}

.disabled-card {
  cursor: default;
  opacity: 0.6;
}

.disabled-card:hover {
  transform: none;
}

:deep(.feature-card-body) {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 24px;
}

.feature-icon {
  color: #409eff;
}

.feature-title {
  margin: 4px 0 0;
  font-size: 18px;
}

.feature-desc {
  margin: 0;
  font-size: 13px;
  color: #606266;
  line-height: 1.6;
}

.feature-status {
  margin-top: 8px;
  font-size: 12px;
  color: #909399;
}
</style>
