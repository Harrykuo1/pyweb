<script setup>
import { useRouter } from 'vue-router'
import { ElButton, ElMessage } from 'element-plus'

import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()

async function handleLogout() {
  try {
    await auth.logout()
    ElMessage.success('已登出')
    router.push('/login')
  } catch (err) {
    ElMessage.error('登出失敗，請稍後再試')
  }
}
</script>

<template>
  <div class="home-page">
    <header class="home-header">
      <h1>pyweb 社群</h1>
      <div class="user-info">
        <span v-if="auth.user">
          歡迎，{{ auth.user.username }}
          <span class="role-tag">{{ auth.isAdmin ? '管理員' : '檢視者' }}</span>
        </span>
        <el-button type="primary" plain @click="handleLogout">登出</el-button>
      </div>
    </header>

    <main class="home-main">
      <p>後續會在這裡放成員列表與實習紀錄入口。</p>
    </main>
  </div>
</template>

<style scoped>
.home-page {
  max-width: 960px;
  margin: 0 auto;
  padding: 24px;
}

.home-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #e4e7ed;
  padding-bottom: 16px;
  margin-bottom: 24px;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.role-tag {
  display: inline-block;
  margin-left: 8px;
  padding: 2px 8px;
  font-size: 12px;
  border-radius: 4px;
  background: #ecf5ff;
  color: #409eff;
}
</style>
