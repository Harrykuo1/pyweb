<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElButton, ElIcon, ElMessage, ElSwitch, ElTag } from 'element-plus'
import {
  ArrowDown,
  Close,
  MoreFilled,
  Setting,
  SwitchButton,
  View,
} from '@element-plus/icons-vue'

import { useAuthStore } from '../stores/auth'
import { useOutsideClick } from '../composables/useOutsideClick'

const auth = useAuthStore()
const router = useRouter()

// Discord accounts have no username, so fall back to the Discord display
// name / handle. Keeps the chip from crashing on a null username.
const displayName = computed(() => {
  const u = auth.user
  if (!u) return ''
  return u.discord_global_name || u.discord_username || u.username || '成員'
})

const avatarInitial = computed(() => {
  const name = displayName.value
  return name ? name.charAt(0).toUpperCase() : '?'
})

const roleLabel = computed(() => {
  const role = auth.user?.role
  if (role === 'admin') return '管理員'
  if (role === 'member') return '成員'
  return '檢視者'
})

// el-switch's v-model needs a writable ref-like — bridge the store action
// through a computed setter.
const previewAsMember = computed({
  get: () => auth.previewAsMember,
  set: (v) => auth.setPreviewAsMember(v),
})

const mobileMenuOpen = ref(false)
const userMenuOpen = ref(false)
const chipRef = ref(null)
const menuRef = ref(null)

function toggleUserMenu() {
  userMenuOpen.value = !userMenuOpen.value
}

function closeUserMenu() {
  userMenuOpen.value = false
}

function gotoSettings() {
  closeUserMenu()
  router.push('/settings')
}

async function handleLogout() {
  closeUserMenu()
  mobileMenuOpen.value = false
  try {
    await auth.logout()
    ElMessage.success('已登出')
    router.push('/login')
  } catch (err) {
    ElMessage.error('登出失敗，請稍後再試')
  }
}

// Close the dropdown on an outside click (anywhere not inside the chip or
// the menu) or Escape — document-level listeners, lifecycle-managed.
useOutsideClick({
  isOpen: userMenuOpen,
  refs: [chipRef, menuRef],
  onClose: closeUserMenu,
})
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
        <router-link to="/jobs" class="nav-link">求職</router-link>
        <router-link to="/events" class="nav-link">活動</router-link>
        <router-link
          v-if="auth.isAdmin"
          to="/review"
          class="nav-link"
          data-test="nav-review"
          >審核</router-link
        >
      </nav>

      <el-button
        text
        class="mobile-menu-toggle"
        :aria-expanded="mobileMenuOpen"
        :aria-label="mobileMenuOpen ? '收起選單' : '展開選單'"
        data-test="mobile-menu-toggle"
        @click="mobileMenuOpen = !mobileMenuOpen"
      >
        <el-icon :size="20">
          <Close v-if="mobileMenuOpen" />
          <MoreFilled v-else />
        </el-icon>
      </el-button>

      <div class="navbar-right" :class="{ 'is-mobile-open': mobileMenuOpen }">
        <!-- Preview indicator: only present while an admin is actively
             previewing. Sits to the left of the chip so the "you're not
             really a viewer" cue is impossible to miss. -->
        <span
          v-if="auth.isPreviewingAsMember"
          class="preview-badge"
          data-test="preview-badge"
        >
          <el-icon class="preview-badge__icon"><View /></el-icon>
          預覽中
        </span>

        <!-- User chip — single-pill trigger that opens the dropdown menu.
             All admin actions (preview toggle, settings, logout) live in
             the panel; the chip itself stays compact. -->
        <div v-if="auth.user" class="user-menu-wrapper">
          <button
            ref="chipRef"
            type="button"
            class="user-chip"
            :class="{
              'is-open': userMenuOpen,
              'is-previewing': auth.isPreviewingAsMember,
            }"
            :aria-expanded="userMenuOpen"
            aria-haspopup="menu"
            data-test="user-menu-trigger"
            @click="toggleUserMenu"
          >
            <span class="user-chip__avatar" aria-hidden="true">
              {{ avatarInitial }}
            </span>
            <span class="user-chip__name">{{ displayName }}</span>
            <span
              class="user-chip__role"
              :data-role="auth.isActuallyAdmin ? 'admin' : 'viewer'"
            >
              {{ roleLabel }}
            </span>
            <el-icon class="user-chip__caret">
              <ArrowDown />
            </el-icon>
          </button>

          <Transition name="user-menu">
            <div
              v-show="userMenuOpen"
              ref="menuRef"
              class="user-menu"
              role="menu"
              data-test="user-menu"
            >
              <header class="user-menu__header">
                <span class="user-menu__avatar" aria-hidden="true">
                  {{ avatarInitial }}
                </span>
                <div class="user-menu__profile">
                  <div class="user-menu__name">{{ displayName }}</div>
                  <div class="user-menu__role-row">
                    <el-tag
                      :type="auth.isActuallyAdmin ? 'danger' : 'info'"
                      size="small"
                      effect="light"
                      round
                    >
                      {{ roleLabel }}
                    </el-tag>
                  </div>
                </div>
              </header>

              <div class="user-menu__divider" />

              <label
                v-if="auth.isActuallyAdmin"
                class="user-menu__row user-menu__toggle"
                data-test="preview-toggle"
              >
                <el-icon class="user-menu__icon"><View /></el-icon>
                <span class="user-menu__label">預覽為成員</span>
                <el-switch v-model="previewAsMember" size="small" />
              </label>

              <button
                v-if="auth.isAdmin"
                type="button"
                class="user-menu__row user-menu__action"
                role="menuitem"
                data-test="nav-settings"
                @click="gotoSettings"
              >
                <el-icon class="user-menu__icon"><Setting /></el-icon>
                <span class="user-menu__label">設定</span>
              </button>

              <div v-if="auth.isActuallyAdmin" class="user-menu__divider" />

              <button
                type="button"
                class="user-menu__row user-menu__action is-danger"
                role="menuitem"
                data-test="logout"
                @click="handleLogout"
              >
                <el-icon class="user-menu__icon"><SwitchButton /></el-icon>
                <span class="user-menu__label">登出</span>
              </button>
            </div>
          </Transition>
        </div>
      </div>
    </div>
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
  background: linear-gradient(
    135deg,
    var(--brand-primary),
    var(--brand-accent)
  );
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
  transition:
    color var(--dur) var(--ease),
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
  gap: 10px;
}

/* ---------- Preview indicator badge ---------- */
.preview-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 10px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
  border-radius: 999px;
  color: var(--accent-warm-ink);
  background: linear-gradient(
    135deg,
    rgba(245, 158, 11, 0.16),
    rgba(244, 63, 94, 0.1)
  );
  border: 1px solid rgba(245, 158, 11, 0.32);
}

.preview-badge__icon {
  font-size: 12px;
}

/* ---------- User chip (dropdown trigger) ---------- */
.user-menu-wrapper {
  position: relative;
}

.user-chip {
  appearance: none;
  font: inherit;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 5px 12px 5px 6px;
  background: var(--surface-0);
  border: 1px solid rgba(15, 23, 42, 0.1);
  border-radius: var(--radius-md);
  color: var(--ink-900);
  transition:
    background-color var(--dur) var(--ease),
    border-color var(--dur) var(--ease),
    box-shadow var(--dur) var(--ease);
}

.user-chip:hover {
  border-color: rgba(99, 102, 241, 0.3);
  background: rgba(99, 102, 241, 0.05);
}

.user-chip.is-open {
  border-color: rgba(99, 102, 241, 0.45);
  background: rgba(99, 102, 241, 0.08);
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
}

.user-chip.is-previewing {
  border-color: rgba(245, 158, 11, 0.4);
  background: rgba(245, 158, 11, 0.06);
}

.user-chip.is-previewing.is-open {
  box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.12);
}

.user-chip__avatar {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  color: #ffffff;
  background: linear-gradient(
    135deg,
    var(--brand-primary),
    var(--brand-accent)
  );
  box-shadow: 0 2px 6px rgba(99, 102, 241, 0.3);
  flex: 0 0 auto;
}

.user-chip__name {
  font-size: 13px;
  font-weight: 600;
  color: var(--ink-900);
  letter-spacing: -0.01em;
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Inline role pill inside the chip. Width here is what closes the gap
   between chip and dropdown — without it the chip is ~110px while the
   dropdown is ~220px and the open menu visibly overhangs to the left. */
.user-chip__role {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.04em;
  padding: 2px 8px;
  border-radius: 999px;
  line-height: 1.4;
  white-space: nowrap;
}

.user-chip__role[data-role='admin'] {
  background: rgba(239, 68, 68, 0.1);
  color: #b91c1c;
  border: 1px solid rgba(239, 68, 68, 0.2);
}

.user-chip__role[data-role='viewer'] {
  background: rgba(99, 102, 241, 0.1);
  color: var(--brand-primary);
  border: 1px solid rgba(99, 102, 241, 0.22);
}

.user-chip__caret {
  font-size: 14px;
  color: var(--ink-500);
  transition: transform var(--dur) var(--ease);
}

.user-chip.is-open .user-chip__caret {
  transform: rotate(180deg);
  color: var(--brand-primary);
}

/* ---------- Dropdown panel ---------- */
.user-menu {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  width: 220px;
  background: var(--surface-0);
  border: 1px solid rgba(15, 23, 42, 0.1);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  padding: 6px;
  z-index: 200;
  /* The project has no global box-sizing reset, so without this the
     row's width:100% + padding pushes children (notably the toggle
     switch) past the menu's right border. */
  box-sizing: border-box;
}

.user-menu__header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: linear-gradient(
    135deg,
    rgba(99, 102, 241, 0.1),
    rgba(139, 92, 246, 0.05)
  );
  border-radius: var(--radius-md);
}

.user-menu__avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  font-weight: 700;
  color: #ffffff;
  background: linear-gradient(
    135deg,
    var(--brand-primary),
    var(--brand-accent)
  );
  box-shadow: 0 4px 10px rgba(99, 102, 241, 0.3);
  flex: 0 0 auto;
}

.user-menu__profile {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.user-menu__name {
  font-size: 14px;
  font-weight: 700;
  color: var(--ink-900);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-menu__role-row {
  display: inline-flex;
}

.user-menu__divider {
  height: 1px;
  background: rgba(15, 23, 42, 0.06);
  margin: 6px 4px;
}

.user-menu__row {
  appearance: none;
  font: inherit;
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 8px 10px;
  border-radius: var(--radius-sm);
  background: transparent;
  border: 0;
  color: var(--ink-900);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  text-align: left;
  /* Without this the row's content-box width:100% plus its padding
     overflows the menu's inner content area, pushing the trailing
     switch past the menu's right border. */
  box-sizing: border-box;
  transition:
    background-color var(--dur) var(--ease),
    color var(--dur) var(--ease);
}

.user-menu__row:hover {
  background: rgba(99, 102, 241, 0.06);
  color: var(--brand-primary);
}

.user-menu__row:hover .user-menu__icon {
  color: var(--brand-primary);
}

.user-menu__icon {
  font-size: 16px;
  color: var(--ink-500);
  transition: color var(--dur) var(--ease);
}

.user-menu__label {
  flex: 1;
}

.user-menu__row.is-danger:hover {
  background: rgba(239, 68, 68, 0.08);
  color: #dc2626;
}

.user-menu__row.is-danger:hover .user-menu__icon {
  color: #dc2626;
}

.user-menu__toggle {
  cursor: pointer;
  user-select: none;
}

/* ---------- Dropdown enter/leave transition ---------- */
.user-menu-enter-active,
.user-menu-leave-active {
  transition:
    opacity var(--dur) var(--ease),
    transform var(--dur) var(--ease);
}

.user-menu-enter-from,
.user-menu-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

/* Mobile-only hamburger; takes over row-1's right edge when shown. */
.mobile-menu-toggle {
  display: none;
}

/* ---------- Mobile / tablet portrait ---------- */
@media (max-width: 1024px) {
  .navbar-inner {
    padding: 8px 12px;
    /* row-gap: 0 keeps the collapsed drawer flush against row 1; when
       expanded, navbar-right adds its own padding-top for separation. */
    column-gap: 12px;
    row-gap: 0;
    min-height: 56px;
  }

  /* Row 1: brand + page nav (compact) + hamburger pinned right. */
  .nav-links {
    flex: 0 0 auto;
    gap: 4px;
  }

  .mobile-menu-toggle {
    display: inline-flex;
    margin-left: auto;
    padding: 6px;
  }

  /* Row 2: navbar-right collapses to a full-width drawer below row 1.
     Hidden by default; .is-mobile-open expands it. max-height/opacity
     (not display:none) keeps the transition smooth. */
  .navbar-right {
    order: 3;
    flex-basis: 100%;
    flex-wrap: wrap;
    justify-content: flex-start;
    gap: 8px;
    max-height: 0;
    opacity: 0;
    overflow: hidden;
    transition:
      max-height 0.25s ease,
      opacity 0.2s ease,
      padding-top 0.25s ease;
  }

  .navbar-right.is-mobile-open {
    max-height: 360px;
    opacity: 1;
    padding-top: 12px;
    margin-top: 8px;
    border-top: 1px solid rgba(15, 23, 42, 0.06);
    overflow: visible;
  }

  .brand-name {
    display: none;
  }

  /* Inside the drawer, a floating dropdown anchored to a tiny chip
     overflows the viewport left edge and gets clipped. Render the menu
     contents inline within the drawer instead — chip stays at the top
     of the drawer as an identity card, menu rows stack below it. */
  .user-menu-wrapper {
    flex-basis: 100%;
  }

  .user-chip {
    cursor: default;
    width: 100%;
    justify-content: flex-start;
  }

  .user-chip__caret {
    display: none;
  }

  .navbar-right .user-menu {
    /* `display: block !important` overrides the inline `display: none`
       v-show writes when userMenuOpen is false, so the menu shows
       regardless of dropdown state. */
    display: block !important;
    position: static;
    width: 100%;
    background: transparent;
    border: 0;
    border-radius: 0;
    box-shadow: none;
    padding: 0;
    margin-top: 4px;
  }

  /* The dropdown's gradient header card is redundant when the chip
     itself already shows avatar + name + role pill — hide it and the
     divider that followed it. */
  .navbar-right .user-menu .user-menu__header,
  .navbar-right .user-menu .user-menu__divider:first-of-type {
    display: none;
  }

  /* No enter/leave transform on mobile — the menu is always present. */
  .user-menu-enter-active,
  .user-menu-leave-active {
    transition: none;
  }
}
</style>
