<script setup>
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ElButton,
  ElCard,
  ElForm,
  ElFormItem,
  ElIcon,
  ElInput,
} from 'element-plus'
import { Lock } from '@element-plus/icons-vue'

import { useAuthStore } from '../stores/auth'
import loginBg from '../assets/login-bg.jpg'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const formRef = ref(null)
const form = reactive({ password: '' })
const submitting = ref(false)
const errorMessage = ref('')

const rules = {
  password: [{ required: true, message: '請輸入密碼', trigger: 'blur' }],
}

async function handleSubmit() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  errorMessage.value = ''
  try {
    await auth.login(form.password)
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
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
    <el-card class="login-card" shadow="always">
      <div class="login-header">
        <div class="logo-circle">
          <el-icon :size="28"><Lock /></el-icon>
        </div>
        <h2 class="title">pyweb 社群</h2>
        <p class="subtitle">請輸入密碼以繼續</p>
      </div>

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
    </el-card>
  </div>
</template>

<style scoped>
.login-page {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  padding: 24px;
  background-size: cover;
  background-position: center;
  background-repeat: no-repeat;
}

/* Soft white veil so the photo stays visible but the card stays readable. */
.login-overlay {
  position: absolute;
  inset: 0;
  background: linear-gradient(
    135deg,
    rgba(255, 255, 255, 0.55) 0%,
    rgba(255, 255, 255, 0.35) 50%,
    rgba(237, 233, 254, 0.5) 100%
  );
  backdrop-filter: blur(2px);
  pointer-events: none;
}

.login-card {
  position: relative;
  width: 100%;
  max-width: 400px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.97);
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.18);
}

.login-header {
  text-align: center;
  margin-bottom: 24px;
}

.logo-circle {
  width: 64px;
  height: 64px;
  margin: 0 auto 12px;
  border-radius: 50%;
  background: linear-gradient(135deg, #409eff, #67c23a);
  color: #ffffff;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 12px rgba(64, 158, 255, 0.3);
}

.title {
  margin: 0 0 4px;
  font-size: 22px;
  font-weight: 600;
  color: #303133;
}

.subtitle {
  margin: 0;
  color: #909399;
  font-size: 14px;
}

.error-message {
  color: #f56c6c;
  font-size: 13px;
  margin: -4px 0 16px;
}

.submit-button {
  width: 100%;
  margin-top: 8px;
}
</style>
