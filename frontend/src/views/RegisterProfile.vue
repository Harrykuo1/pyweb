<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  ElButton,
  ElForm,
  ElFormItem,
  ElInput,
  ElInputNumber,
  ElMessage,
} from 'element-plus'

import { membersApi } from '../api/members'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()

const formRef = ref(null)
const form = reactive({
  // Left blank on purpose: prefilling the current year reads as an answered
  // field and pollutes the data with a wrong-but-plausible default. The
  // required rule forces the member to enter their real graduation year.
  graduation_year: null,
  real_name: '',
  institution: '',
  position: '',
})
const submitting = ref(false)

const rules = {
  graduation_year: [
    { required: true, message: '請輸入畢業年', trigger: 'blur' },
  ],
  real_name: [{ required: true, message: '請輸入姓名', trigger: 'blur' }],
  institution: [
    { required: true, message: '請輸入目前工作 / 學校', trigger: 'blur' },
  ],
}

async function handleLogout() {
  try {
    await auth.logout()
  } catch (err) {
    // Session may already be gone server-side; drop it locally either way.
    auth.clearLocal()
  }
  router.push('/login')
}

async function handleSubmit() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    await membersApi.createMyProfile({
      graduation_year: form.graduation_year,
      real_name: form.real_name.trim(),
      institution: form.institution.trim(),
      position: form.position.trim() || null,
    })
    // Refresh so has_profile flips true and the router guard lets us in.
    await auth.fetchMe()
    ElMessage.success('資料已建立，歡迎加入！')
    router.push('/')
  } catch (err) {
    if (err?.response?.status === 409) {
      // Already has a profile (e.g. two tabs) — just proceed.
      await auth.fetchMe()
      router.push('/')
      return
    }
    ElMessage.error('建立失敗，請稍後再試')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="register-profile">
    <div class="rp-card">
      <h2 class="rp-title">完成你的成員資料</h2>
      <p class="rp-sub">填寫後即可瀏覽社群內容。</p>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        @submit.prevent="handleSubmit"
      >
        <el-form-item label="畢業年" prop="graduation_year">
          <el-input-number
            v-model="form.graduation_year"
            :min="1900"
            :max="2100"
            controls-position="right"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="姓名" prop="real_name">
          <el-input v-model="form.real_name" placeholder="你的姓名" />
        </el-form-item>
        <el-form-item label="目前工作 / 學校" prop="institution">
          <el-input
            v-model="form.institution"
            placeholder="例如：Google / 台大資工"
          />
        </el-form-item>
        <el-form-item label="職稱 / 系級（選填）" prop="position">
          <el-input
            v-model="form.position"
            placeholder="例如：Software Engineer"
          />
        </el-form-item>

        <el-button
          type="primary"
          size="large"
          native-type="submit"
          class="rp-submit"
          :loading="submitting"
          data-test="submit"
          @click="handleSubmit"
        >
          建立資料
        </el-button>
      </el-form>

      <button
        type="button"
        class="rp-logout"
        data-test="logout"
        @click="handleLogout"
      >
        先不要，改用其他帳號登入
      </button>
    </div>
  </div>
</template>

<style scoped>
.register-profile {
  min-height: 100dvh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: var(--surface-1, #f8fafc);
}

.rp-card {
  width: 100%;
  max-width: 460px;
  background: var(--surface-0, #ffffff);
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: var(--radius-lg);
  padding: 32px;
  box-shadow: var(--shadow-md);
}

.rp-title {
  margin: 0 0 6px;
  font-size: 22px;
  font-weight: 700;
  color: var(--ink-900);
}

.rp-sub {
  margin: 0 0 24px;
  font-size: 14px;
  color: var(--ink-500);
}

:deep(.rp-submit) {
  width: 100%;
  margin-top: 8px;
}

.rp-logout {
  display: block;
  width: 100%;
  margin-top: 16px;
  padding: 4px;
  background: none;
  border: 0;
  color: var(--ink-500, #64748b);
  font-size: 13px;
  cursor: pointer;
  text-align: center;
}
.rp-logout:hover {
  color: var(--brand-primary, #6366f1);
  text-decoration: underline;
}
</style>
