<script setup>
import { onMounted, ref } from 'vue'
import {
  ElButton,
  ElMessage,
  ElPopconfirm,
  ElTable,
  ElTableColumn,
  ElTooltip,
} from 'element-plus'
import { Document, Plus, Refresh } from '@element-plus/icons-vue'

import MemberFormDialog from '../components/MemberFormDialog.vue'
import MemberPhotoCell from '../components/MemberPhotoCell.vue'
import ResumeViewerDialog from '../components/ResumeViewerDialog.vue'
import { membersApi } from '../api/members'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()

const members = ref([])
const loading = ref(false)

const dialogOpen = ref(false)
const editingMember = ref(null)

const resumeOpen = ref(false)
const resumeMember = ref(null)

// Sort orders are restricted to two states so a click cycles asc → desc →
// asc instead of the el-table default asc → desc → none.
const SORT_ORDERS = ['ascending', 'descending']

// Element Plus's default string sort uses < which is byte-wise; localeCompare
// gives the right ordering for Chinese / mixed CJK strings.
const stringSort = (key) => (a, b) =>
  String(a[key] ?? '').localeCompare(String(b[key] ?? ''), 'zh-Hant')

async function loadMembers() {
  loading.value = true
  try {
    members.value = await membersApi.list()
  } catch (err) {
    ElMessage.error('載入成員清單失敗')
  } finally {
    loading.value = false
  }
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
        <p class="subtitle">點欄位標題可切換排序方向</p>
      </div>
      <div class="actions">
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
      :default-sort="{ prop: 'joined_at', order: 'ascending' }"
    >
      <el-table-column label="照片" width="140">
        <template #default="{ row }">
          <MemberPhotoCell :member="row" @changed="loadMembers" />
        </template>
      </el-table-column>
      <el-table-column
        prop="graduation_year"
        label="畢業年份"
        width="120"
        sortable
        :sort-orders="SORT_ORDERS"
      />
      <el-table-column
        prop="real_name"
        label="本名"
        width="180"
        sortable
        :sort-method="stringSort('real_name')"
        :sort-orders="SORT_ORDERS"
      />
      <el-table-column
        prop="current_position"
        label="目前就職／就讀"
        sortable
        :sort-method="stringSort('current_position')"
        :sort-orders="SORT_ORDERS"
        min-width="200"
      />
      <el-table-column
        prop="joined_at"
        label="入群時間"
        width="160"
        sortable
        :sort-orders="SORT_ORDERS"
      >
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
  flex-wrap: wrap;
}

.members-table {
  background: #ffffff;
  border-radius: 8px;
}

@media (max-width: 640px) {
  .title {
    font-size: 18px;
  }

  /* Table columns sum to ~860 px which is wider than a phone viewport;
     let it scroll horizontally inside the card instead of overflowing the
     whole page. The table component already wraps its body in a scrollable
     element-plus inner, but we also need the wrapper itself not to clip. */
  .members-table {
    width: 100%;
    overflow-x: auto;
  }

  /* Force the underlying table to keep its design width so columns don't
     squeeze into unreadable widths. */
  .members-table :deep(.el-table__body),
  .members-table :deep(.el-table__header) {
    min-width: 860px;
  }

  /* Stack the action buttons full-width on phones so each is easy to tap. */
  .actions {
    width: 100%;
    justify-content: flex-end;
  }
}
</style>
