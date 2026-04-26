<script setup>
import { useRouter } from 'vue-router'
import { ElButton, ElMessage, ElTag } from 'element-plus'

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
  <header class="navbar">
    <div class="navbar-inner">
      <router-link to="/" class="brand">pyweb 社群</router-link>

      <nav class="nav-links">
        <router-link to="/" class="nav-link">首頁</router-link>
      </nav>

      <div class="navbar-right">
        <span v-if="auth.user" class="user-block">
          <span class="username">{{ auth.user.username }}</span>
          <el-tag
            :type="auth.isAdmin ? 'danger' : 'info'"
            size="small"
            effect="light"
            round
          >
            {{ auth.isAdmin ? '管理員' : '檢視者' }}
          </el-tag>
        </span>
        <el-button text @click="handleLogout">登出</el-button>
      </div>
    </div>
  </header>
</template>

<style scoped>
.navbar {
  position: sticky;
  top: 0;
  z-index: 100;
  background: #ffffff;
  border-bottom: 1px solid #e4e7ed;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

.navbar-inner {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 24px;
  height: 56px;
  display: flex;
  align-items: center;
  gap: 32px;
}

.brand {
  font-size: 18px;
  font-weight: 600;
  color: #409eff;
  text-decoration: none;
  letter-spacing: 0.5px;
}

.nav-links {
  display: flex;
  gap: 24px;
  flex: 1;
}

.nav-link {
  color: #303133;
  text-decoration: none;
  font-size: 14px;
  padding: 4px 0;
  border-bottom: 2px solid transparent;
  transition: color 0.2s, border-color 0.2s;
}

.nav-link:hover {
  color: #409eff;
}

.nav-link.router-link-exact-active {
  color: #409eff;
  border-bottom-color: #409eff;
}

.navbar-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.user-block {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.username {
  font-size: 14px;
  color: #606266;
}
</style>
