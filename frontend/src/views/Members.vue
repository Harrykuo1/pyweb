<script setup>
import { onMounted, ref } from 'vue'
import {
  ElButton,
  ElIcon,
  ElMessage,
  ElPopconfirm,
  ElTable,
  ElTableColumn,
  ElTooltip,
} from 'element-plus'
import { Document, Plus, Refresh, Sort } from '@element-plus/icons-vue'

import MemberFormDialog from '../components/MemberFormDialog.vue'
import MemberPhotoCell from '../components/MemberPhotoCell.vue'
import ResumeViewerDialog from '../components/ResumeViewerDialog.vue'
import { membersApi } from '../api/members'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()

const members = ref([])
const loading = ref(false)
const order = ref('asc')

const dialogOpen = ref(false)
const editingMember = ref(null)

const resumeOpen = ref(false)
const resumeMember = ref(null)

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

async function deleteMember(member) {
  try {
    await membersApi.remove(member.id)
    ElMessage.success(`已刪除「${member.real_name}」`)
    loadMembers()
  } catch (err) {
    if (err?.response?.status === 403) {
      ElMessage.error('權限不足')
    } else {
      ElMessage.error('刪除失敗，請稍後再試')
    }
  }
}

function viewResume(member) {
  resumeMember.value = member
  resumeOpen.value = true
}

async function reloadAndRebindResume() {
  await loadMembers()
  // Re-point the resume dialog at the freshly fetched row so flag changes
  // (e.g. resume_pdf was deleted) are reflected without a full close/reopen.
  if (resumeMember.value) {
    const fresh = members.value.find((m) => m.id === resumeMember.value.id)
    resumeMember.value = fresh ?? null
    if (!fresh) resumeOpen.value = false
  }
}

function hasAnyResume(member) {
  return member.has_resume_md || member.has_resume_pdf
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
      class="members-table"
      empty-text="尚無成員資料"
    >
      <el-table-column label="照片" width="140">
        <template #default="{ row }">
          <MemberPhotoCell :member="row" @changed="loadMembers" />
        </template>
      </el-table-column>
      <el-table-column prop="graduation_year" label="畢業年份" width="100" />
      <el-table-column prop="real_name" label="本名" width="160" />
      <el-table-column prop="current_position" label="目前就職／就讀" />
      <el-table-column label="入群時間" width="140">
        <template #default="{ row }">{{ formatDate(row.joined_at) }}</template>
      </el-table-column>
      <el-table-column label="履歷" width="120" align="center">
        <template #default="{ row }">
          <el-tooltip
            v-if="!hasAnyResume(row)"
            content="此成員尚未提供履歷"
            placement="top"
          >
            <el-button size="small" :icon="Document" disabled>履歷</el-button>
          </el-tooltip>
          <el-button
            v-else
            size="small"
            type="primary"
            plain
            :icon="Document"
            data-test="view-resume-button"
            @click="viewResume(row)"
          >
            履歷
          </el-button>
        </template>
      </el-table-column>
      <el-table-column v-if="auth.isAdmin" label="操作" width="200" align="center">
        <template #default="{ row }">
          <el-button
            size="small"
            plain
            data-test="edit-button"
            @click="openEdit(row)"
          >
            編輯
          </el-button>
          <el-popconfirm
            :title="`確定要刪除「${row.real_name}」嗎？`"
            confirm-button-text="刪除"
            cancel-button-text="取消"
            confirm-button-type="danger"
            width="240"
            :teleported="false"
            @confirm="deleteMember(row)"
          >
            <template #reference>
              <el-button
                size="small"
                type="danger"
                plain
                data-test="delete-button"
              >
                刪除
              </el-button>
            </template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <MemberFormDialog
      v-model="dialogOpen"
      :member="editingMember"
      @saved="loadMembers"
    />

    <ResumeViewerDialog
      v-model="resumeOpen"
      :member="resumeMember"
      @changed="reloadAndRebindResume"
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
