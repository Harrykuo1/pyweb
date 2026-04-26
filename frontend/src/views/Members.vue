<script setup>
import { onMounted, ref } from 'vue'
import {
  ElButton,
  ElIcon,
  ElMessage,
  ElTable,
  ElTableColumn,
} from 'element-plus'
import { Plus, Refresh, Sort } from '@element-plus/icons-vue'

import MemberFormDialog from '../components/MemberFormDialog.vue'
import { membersApi } from '../api/members'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()

const members = ref([])
const loading = ref(false)
const order = ref('asc')

const dialogOpen = ref(false)
const editingMember = ref(null)

async function loadMembers() {
  loading.value = true
  try {
    members.value = await membersApi.list({ order: order.value })
  } catch (err) {
    ElMessage.error('載入成員清單失敗')
  } finally {
    loading.value = false
  }
}

function toggleOrder() {
  order.value = order.value === 'asc' ? 'desc' : 'asc'
  loadMembers()
}

function openCreate() {
  editingMember.value = null
  dialogOpen.value = true
}

function openEdit(member) {
  editingMember.value = { ...member }
  dialogOpen.value = true
}

function formatDate(iso) {
  if (!iso) return '-'
  return new Date(iso).toLocaleDateString('zh-TW', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  })
}

onMounted(loadMembers)
</script>

<template>
  <div class="members-page">
    <header class="page-header">
      <div>
        <h1 class="title">成員介紹</h1>
        <p class="subtitle">依入群時間排列（{{ order === 'asc' ? '舊 → 新' : '新 → 舊' }}）</p>
      </div>
      <div class="actions">
        <el-button :icon="Sort" @click="toggleOrder">切換排序</el-button>
        <el-button :icon="Refresh" @click="loadMembers">重新整理</el-button>
        <el-button
          v-if="auth.isAdmin"
          type="primary"
          :icon="Plus"
          data-test="add-member-button"
          @click="openCreate"
        >
          新增成員
        </el-button>
      </div>
    </header>

    <el-table
      v-loading="loading"
      :data="members"
      stripe
      class="members-table"
      empty-text="尚無成員資料"
    >
      <el-table-column prop="graduation_year" label="畢業年份" width="100" />
      <el-table-column prop="real_name" label="本名" width="160" />
      <el-table-column prop="current_position" label="目前就職／就讀" />
      <el-table-column label="入群時間" width="140">
        <template #default="{ row }">{{ formatDate(row.joined_at) }}</template>
      </el-table-column>
      <el-table-column v-if="auth.isAdmin" label="操作" width="180" align="center">
        <template #default="{ row }">
          <el-button
            size="small"
            plain
            data-test="edit-button"
            @click="openEdit(row)"
          >
            編輯
          </el-button>
          <el-button size="small" type="danger" plain disabled>刪除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <MemberFormDialog
      v-model="dialogOpen"
      :member="editingMember"
      @saved="loadMembers"
    />
  </div>
</template>

<style scoped>
.members-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.title {
  margin: 0;
  font-size: 22px;
}

.subtitle {
  margin: 4px 0 0;
  color: #909399;
  font-size: 13px;
}

.actions {
  display: flex;
  gap: 8px;
}

.members-table {
  background: #ffffff;
  border-radius: 8px;
}
</style>
