<script setup>
import { computed, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElButton, ElForm, ElFormItem, ElIcon, ElInput } from 'element-plus'
import { Lock } from '@element-plus/icons-vue'

import { DISCORD_LOGIN_URL } from '../api/auth'
import { settingImageUrl } from '../api/settings'
import { useAuthStore } from '../stores/auth'
import loginBg from '../assets/login-bg.jpg'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const formRef = ref(null)
const form = reactive({ password: '' })
const submitting = ref(false)
const errorMessage = ref('')

// Show the admin-uploaded logo if it exists; on 404 the <img> onerror fires
// and we fall back to the Lock icon. The query string is just a per-load
// cache-buster so admins testing rapid edits see fresh bytes.
const logoUrl = ref(settingImageUrl('login_logo', Date.now()))
const logoFailed = ref(false)
function onLogoError() {
  logoFailed.value = true
}

const rules = {
  password: [{ required: true, message: '請輸入密碼', trigger: 'blur' }],
}

// The Discord OAuth callback bounces failures back here as ?error=<reason>.
const OAUTH_ERRORS = {
  not_member: '你不是社群 Discord 群組的成員，無法登入。',
  guild_check_failed: 'Discord 群組驗證暫時失敗（可能是太頻繁），請稍後再試。',
  not_linked: '找不到對應的成員帳號，請聯絡管理員為你連結。',
  state_mismatch: '登入逾時或連結失效，請再登入一次。',
  invalid_invite: '註冊連結無效或已過期。',
  guild_not_configured: '系統尚未設定 Discord 群組，請聯絡管理員。',
  account_suspended: '此帳號已停權，請聯絡管理員',
  discord_denied: '你取消了 Discord 授權。',
}
const oauthError = computed(() => {
  const e = typeof route.query.error === 'string' ? route.query.error : ''
  if (!e) return ''
  return OAUTH_ERRORS[e] || 'Discord 登入失敗，請稍後再試。'
})

function loginWithDiscord() {
  window.location.href = DISCORD_LOGIN_URL
}

async function handleSubmit() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  errorMessage.value = ''
  try {
    await auth.login(form.password)
    const redirect =
      typeof route.query.redirect === 'string' ? route.query.redirect : '/'
    router.push(redirect)
  } catch (err) {
    if (err?.response?.status === 401) {
      errorMessage.value = '密碼錯誤'
    } else {
      errorMessage.value = '登入失敗，請稍後再試'
    }
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="login-page" :style="{ backgroundImage: `url(${loginBg})` }">
    <div class="login-overlay" />

    <div class="login-shell">
      <aside class="brand-panel">
        <div class="brand-decor" aria-hidden="true">
          <span class="b-decor b-a"></span>
          <span class="b-decor b-b"></span>
          <span class="b-decor b-c"></span>
        </div>

        <div class="brand-content">
          <div class="logo-circle" data-test="logo-circle">
            <img
              v-if="!logoFailed"
              :src="logoUrl"
              alt="site logo"
              class="logo-image"
              data-test="logo-image"
              @error="onLogoError"
            />
            <el-icon v-else :size="26" data-test="logo-fallback"
              ><Lock
            /></el-icon>
          </div>
          <h1 class="brand-name">pyweb 社群</h1>
          <p class="brand-tagline">
            大家在哪工作、履歷怎麼寫、面試考什麼 ——<br />
            都記在這。
          </p>
        </div>

        <p class="brand-foot">© pyweb · 內部成員專用</p>
      </aside>

      <main class="form-panel">
        <div class="form-inner">
          <h2 class="form-title">歡迎回來</h2>
          <p class="form-sub">用 Discord 登入，或輸入密碼。</p>

          <p v-if="oauthError" class="error-message" data-test="oauth-error">
            {{ oauthError }}
          </p>

          <el-button
            size="large"
            class="discord-button"
            data-test="discord-login"
            @click="loginWithDiscord"
          >
            使用 Discord 登入
          </el-button>

          <div class="login-divider"><span>或用密碼</span></div>

          <el-form
            ref="formRef"
            :model="form"
            :rules="rules"
            label-position="top"
            @submit.prevent="handleSubmit"
          >
            <el-form-item label="密碼" prop="password">
              <el-input
                v-model="form.password"
                type="password"
                size="large"
                placeholder="請輸入密碼"
                autocomplete="current-password"
                show-password
                :prefix-icon="Lock"
              />
            </el-form-item>

            <p v-if="errorMessage" class="error-message" data-test="error">
              {{ errorMessage }}
            </p>

            <el-button
              type="primary"
              size="large"
              class="submit-button"
              native-type="submit"
              :loading="submitting"
              @click="handleSubmit"
            >
              登入
            </el-button>
          </el-form>
        </div>
      </main>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  /* Pin to viewport so the page never scrolls. dvh tracks Safari's
     URL bar collapse (regular vh would oversize on first paint).
     border-box so the 24px padding sits inside the 100dvh, otherwise
     it'd add a scrollbar's worth of extra height on macOS Safari. */
  height: 100dvh;
  box-sizing: border-box;
  overflow: hidden;
  padding: 24px;
  background-size: cover;
  background-position: center;
  background-repeat: no-repeat;
}

/* Dark indigo veil over the bg photo so the white form-panel pops. */
.login-overlay {
  position: absolute;
  inset: 0;
  background: linear-gradient(
    135deg,
    rgba(15, 23, 42, 0.45) 0%,
    rgba(30, 27, 75, 0.55) 100%
  );
  backdrop-filter: blur(8px);
  pointer-events: none;
}

.login-shell {
  position: relative;
  /* flex (not grid) so .form-panel is a flex item, not a grid item.
     The Safari layout-recalc bug requires the panel to be both a grid
     item AND a flex container (with vertical padding) for its intrinsic
     height to be miscalculated on every focus/blur/hover event. Flex
     parent + flex container child doesn't trigger the bug. */
  display: flex;
  width: 100%;
  max-width: 960px;
  min-height: 540px;
  border-radius: var(--radius-xl);
  overflow: hidden;
  background: #ffffff;
  box-shadow:
    0 30px 80px rgba(15, 23, 42, 0.28),
    0 12px 32px rgba(15, 23, 42, 0.18);
}

/* ---------- Brand panel (left) ---------- */
.brand-panel {
  position: relative;
  overflow: hidden;
  /* flex 5 / 6 mirrors the original 5fr / 6fr grid columns. */
  flex: 5;
  padding: 48px 40px;
  background: linear-gradient(155deg, #312e81 0%, #4f46e5 40%, #7c3aed 100%);
  color: #ffffff;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.brand-decor {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
}

.b-decor {
  position: absolute;
  border-radius: 50%;
  filter: blur(50px);
}
.b-a {
  top: -80px;
  right: -60px;
  width: 280px;
  height: 280px;
  background: radial-gradient(closest-side, #c084fc, transparent);
  opacity: 0.55;
}
.b-b {
  bottom: -80px;
  left: -60px;
  width: 240px;
  height: 240px;
  background: radial-gradient(closest-side, #a78bfa, transparent);
  opacity: 0.4;
}
.b-c {
  top: 45%;
  left: 30%;
  width: 200px;
  height: 200px;
  background: radial-gradient(closest-side, #818cf8, transparent);
  opacity: 0.3;
}

.brand-content {
  position: relative;
  z-index: 1;
}

.logo-circle {
  width: 56px;
  height: 56px;
  margin: 0 0 28px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.16);
  border: 1px solid rgba(255, 255, 255, 0.26);
  backdrop-filter: blur(8px);
  color: #ffffff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.logo-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.brand-name {
  margin: 0 0 12px;
  font-size: 32px;
  font-weight: 700;
  color: #ffffff;
  letter-spacing: -0.01em;
  line-height: 1.15;
}

.brand-tagline {
  margin: 0;
  font-size: 14px;
  line-height: 1.75;
  color: rgba(255, 255, 255, 0.86);
  max-width: 320px;
}

.brand-foot {
  position: relative;
  z-index: 1;
  margin: 0;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.6);
  letter-spacing: 0.03em;
}

/* ---------- Form panel (right) ---------- */
.form-panel {
  flex: 6;
  background: #ffffff;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48px 56px;
}

.form-inner {
  width: 100%;
  max-width: 360px;
}

.form-title {
  margin: 0 0 6px;
  font-size: 26px;
  font-weight: 700;
  color: var(--ink-900);
  letter-spacing: -0.01em;
}

.form-sub {
  margin: 0 0 28px;
  font-size: 14px;
  color: var(--ink-500);
}

.error-message {
  color: #ef4444;
  font-size: 13px;
  margin: -4px 0 16px;
}

/* Discord brand button — the primary login path going forward. */
:deep(.discord-button) {
  width: 100%;
  height: 44px;
  font-weight: 600;
  border-radius: var(--radius-md);
  background: #5865f2;
  color: #ffffff;
  border: 0;
}
:deep(.discord-button:hover) {
  background: #4752c4;
  color: #ffffff;
}

.login-divider {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 18px 0;
  color: var(--ink-400, #94a3b8);
  font-size: 12px;
}
.login-divider::before,
.login-divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: rgba(15, 23, 42, 0.1);
}

/* Override Element's primary-button gradient + height inside the form. */
:deep(.submit-button) {
  width: 100%;
  margin-top: 8px;
  height: 44px;
  font-weight: 600;
  border-radius: var(--radius-md);
  background: linear-gradient(
    135deg,
    var(--brand-primary),
    var(--brand-accent)
  );
  border: 0;
  box-shadow: 0 6px 18px rgba(99, 102, 241, 0.28);
}
:deep(.submit-button:hover) {
  background: linear-gradient(135deg, var(--brand-primary-hover), #7c3aed);
  box-shadow: 0 10px 24px rgba(99, 102, 241, 0.36);
}
:deep(.submit-button.is-loading) {
  opacity: 0.85;
}

@media (max-width: 760px) {
  .login-shell {
    flex-direction: column;
    min-height: 0;
    max-width: 460px;
  }
  .brand-panel {
    padding: 32px 28px 28px;
    min-height: 0;
  }
  .brand-name {
    font-size: 24px;
  }
  .brand-tagline {
    font-size: 13px;
  }
  .logo-circle {
    width: 48px;
    height: 48px;
    margin-bottom: 16px;
    border-radius: 12px;
  }
  .form-panel {
    padding: 32px 28px 36px;
  }
}
</style>
