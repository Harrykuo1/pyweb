<script setup>
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElButton, ElForm, ElFormItem, ElInput, ElCard } from 'element-plus'

import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const formRef = ref(null)
const form = reactive({ username: '', password: '' })
const submitting = ref(false)
const errorMessage = ref('')

const rules = {
  username: [{ required: true, message: '請輸入帳號', trigger: 'blur' }],
  password: [{ required: true, message: '請輸入密碼', trigger: 'blur' }],
}

async function handleSubmit() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  errorMessage.value = ''
  try {
    await auth.login(form.username, form.password)
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
    router.push(redirect)
  } catch (err) {
    if (err?.response?.status === 401) {
      errorMessage.value = '帳號或密碼錯誤'
    } else {
      errorMessage.value = '登入失敗，請稍後再試'
    }
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <el-card class="login-card">
      <h2>pyweb 登入</h2>
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="60px"
        @submit.prevent="handleSubmit"
      >
        <el-form-item label="帳號" prop="username">
          <el-input v-model="form.username" autocomplete="username" />
        </el-form-item>
        <el-form-item label="密碼" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            autocomplete="current-password"
            show-password
          />
        </el-form-item>
        <p v-if="errorMessage" class="error-message" data-test="error">
          {{ errorMessage }}
        </p>
        <el-form-item>
          <el-button
            type="primary"
            native-type="submit"
            :loading="submitting"
            @click="handleSubmit"
          >
            登入
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<style scoped>
.login-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: #f5f7fa;
}

.login-card {
  width: 360px;
}

.error-message {
  color: #f56c6c;
  font-size: 13px;
  margin: 0 0 12px;
}
</style>
