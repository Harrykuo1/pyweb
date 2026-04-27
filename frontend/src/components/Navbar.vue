<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElButton, ElMessage, ElSwitch, ElTag, ElTooltip } from 'element-plus'

import AccountSettingsDialog from './AccountSettingsDialog.vue'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()

// el-switch's v-model needs a writable ref-like — bridge the store action
// through a computed setter.
const previewAsViewer = computed({
  get: () => auth.viewAsViewer,
  set: (v) => auth.setViewAsViewer(v),
})

const accountDialogVisible = ref(false)

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
        <router-link to="/members" class="nav-link">成員</router-link>
      </nav>

      <div class="navbar-right">
        <el-tooltip
          v-if="auth.isActuallyAdmin"
          content="切換後 UI 會以檢視者身分顯示，後端權限不變"
          placement="bottom"
        >
          <label class="preview-toggle" data-test="preview-toggle">
            <span class="preview-label">預覽為檢視者</span>
            <el-switch v-model="previewAsViewer" size="small" />
          </label>
        </el-tooltip>

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
          <span
            v-if="auth.isActuallyAdmin"
            class="preview-badge"
            :class="{ 'is-invisible': !auth.isViewingAsViewer }"
            data-test="preview-badge"
          >
            預覽中
          </span>
        </span>
        <el-button
          v-if="auth.isActuallyAdmin"
          text
          data-test="account-settings"
          @click="accountDialogVisible = true"
        >
          帳號設定
        </el-button>
        <el-button text @click="handleLogout">登出</el-button>
      </div>
    </div>

    <AccountSettingsDialog
      v-if="auth.isActuallyAdmin"
      v-model="accountDialogVisible"
    />
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

.preview-toggle {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  user-select: none;
}

.preview-label {
  font-size: 13px;
  color: #606266;
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

.preview-badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  background: #fdf6ec;
  color: #e6a23c;
  border: 1px solid #f5dab1;
}

/* Reserve the badge's footprint when not previewing, so toggling preview
   mode does not shift the switcher's position. */
.preview-badge.is-invisible {
  visibility: hidden;
}
</style>
