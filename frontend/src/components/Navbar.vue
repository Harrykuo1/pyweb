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
      <router-link to="/" class="brand">
        <span class="brand-mark" aria-hidden="true">py</span>
        <span class="brand-name">pyweb 社群</span>
      </router-link>

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
          <span class="user-avatar" aria-hidden="true">
            {{ auth.user.username.charAt(0).toUpperCase() }}
          </span>
          <span class="user-meta">
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
          <span
            v-if="auth.isActuallyAdmin"
            class="preview-badge"
            :class="{ 'is-invisible': !auth.isViewingAsViewer }"
            data-test="preview-badge"
          >
            預覽中
          </span>
        </span>

        <span class="actions-divider" aria-hidden="true"></span>

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
  background: rgba(255, 255, 255, 0.78);
  backdrop-filter: saturate(180%) blur(14px);
  -webkit-backdrop-filter: saturate(180%) blur(14px);
  border-bottom: 1px solid rgba(15, 23, 42, 0.06);
}

.navbar-inner {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 var(--sp-lg);
  min-height: 64px;
  display: flex;
  align-items: center;
  gap: var(--sp-xl);
  flex-wrap: wrap;
}

/* ---------- Brand ---------- */
.brand {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  font-size: 16px;
  font-weight: 700;
  text-decoration: none;
  letter-spacing: -0.01em;
}

.brand-mark {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  color: #ffffff;
  background: linear-gradient(135deg, var(--brand-primary), var(--brand-accent));
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
  letter-spacing: -0.02em;
}

.brand-name {
  background: linear-gradient(
    135deg,
    var(--brand-primary) 0%,
    var(--brand-accent) 100%
  );
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}

/* ---------- Nav links — capsule active state ---------- */
.nav-links {
  display: flex;
  gap: var(--sp-xs);
  flex: 1;
}

.nav-link {
  position: relative;
  color: var(--ink-700);
  text-decoration: none;
  font-size: 14px;
  font-weight: 500;
  padding: 6px 14px;
  border-radius: var(--radius-md);
  transition: color var(--dur) var(--ease),
    background-color var(--dur) var(--ease);
}

.nav-link:hover {
  color: var(--brand-primary);
  background: rgba(99, 102, 241, 0.06);
}

.nav-link.router-link-exact-active {
  color: var(--brand-primary);
  background: rgba(99, 102, 241, 0.1);
}

/* ---------- Right side ---------- */
.navbar-right {
  display: flex;
  align-items: center;
  gap: var(--sp-md);
}

.preview-toggle {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  user-select: none;
  padding: 4px 10px 4px 12px;
  border-radius: var(--radius-md);
  background: rgba(99, 102, 241, 0.06);
  transition: background-color var(--dur) var(--ease);
}
.preview-toggle:hover {
  background: rgba(99, 102, 241, 0.1);
}

.preview-label {
  font-size: 12px;
  color: var(--brand-primary);
  font-weight: 500;
}

/* User pill — avatar + meta wrapped together so the username/role read
   as one unit instead of two loose siblings. */
.user-block {
  display: inline-flex;
  align-items: center;
  gap: 10px;
}

.user-avatar {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 600;
  color: #ffffff;
  background: linear-gradient(135deg, var(--brand-primary), var(--brand-accent));
  box-shadow: 0 2px 6px rgba(99, 102, 241, 0.3);
}

.user-meta {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.username {
  font-size: 13px;
  color: var(--ink-900);
  font-weight: 500;
}

.preview-badge {
  font-size: 10px;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(245, 158, 11, 0.1);
  color: #b45309;
  border: 1px solid rgba(245, 158, 11, 0.22);
  font-weight: 600;
  letter-spacing: 0.04em;
}

/* Reserve the badge's footprint when not previewing, so toggling preview
   mode does not shift the switcher's position. */
.preview-badge.is-invisible {
  visibility: hidden;
}

.actions-divider {
  width: 1px;
  height: 20px;
  background: rgba(15, 23, 42, 0.1);
}

/* ---------- Mobile ---------- */
@media (max-width: 640px) {
  .navbar-inner {
    padding: 8px 12px;
    gap: 12px;
    min-height: 56px;
  }

  /* Push nav-links and the right-side block to a second row, sharing it. */
  .nav-links {
    order: 3;
    flex-basis: 100%;
    gap: 4px;
  }

  .navbar-right {
    margin-left: auto;
    gap: 8px;
  }

  /* Hide the verbose label of the preview switch; the toggle itself stays. */
  .preview-label {
    display: none;
  }

  .preview-toggle {
    padding: 4px 8px;
  }

  .actions-divider {
    display: none;
  }

  .brand-name {
    display: none;
  }

  .user-meta {
    gap: 4px;
  }

  .username {
    display: none;
  }
}
</style>
