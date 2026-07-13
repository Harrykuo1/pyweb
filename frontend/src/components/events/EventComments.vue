<script setup>
import { computed, ref, watch } from 'vue'
import { ElButton, ElInput, ElMessage, ElMessageBox } from 'element-plus'

import { eventsApi } from '../../api/events'
import { useAuthStore } from '../../stores/auth'
import { useDeleteWithPassword } from '../../composables/useDeleteWithPassword'
import DeleteWithPasswordDialog from '../DeleteWithPasswordDialog.vue'

const props = defineProps({
  eventId: { type: Number, default: null },
  // The parent detail dialog toggles this; we (re)load when it opens so a
  // closed dialog isn't holding a stale thread.
  active: { type: Boolean, default: false },
})

const auth = useAuthStore()

const comments = ref([])
const loading = ref(false)
const loadError = ref(false)

const draft = ref('')
const submitting = ref(false)

const editingId = ref(null)
const editDraft = ref('')
const savingEdit = ref(false)

// Viewers are read-only; real members and admins may comment. Based on the
// real role so an admin previewing as a member keeps the affordance.
const canPost = computed(() => ['admin', 'member'].includes(auth.actualRole))

async function load() {
  if (!props.eventId) return
  loading.value = true
  loadError.value = false
  try {
    comments.value = await eventsApi.listComments(props.eventId)
  } catch {
    loadError.value = true
    comments.value = []
  } finally {
    loading.value = false
  }
}

watch(
  () => [props.active, props.eventId],
  ([active]) => {
    if (active && props.eventId) {
      load()
    } else if (!active) {
      draft.value = ''
      editingId.value = null
    }
  },
  { immediate: true },
)

async function submit() {
  const body = draft.value.trim()
  if (!body || submitting.value) return
  submitting.value = true
  try {
    const created = await eventsApi.createComment(props.eventId, body)
    comments.value.push(created)
    draft.value = ''
  } catch (err) {
    ElMessage.error(
      err?.response?.status === 403 ? '你沒有留言權限' : '留言失敗，請稍後再試',
    )
  } finally {
    submitting.value = false
  }
}

function startEdit(c) {
  editingId.value = c.id
  editDraft.value = c.body
}
function cancelEdit() {
  editingId.value = null
  editDraft.value = ''
}
async function saveEdit(c) {
  const body = editDraft.value.trim()
  if (!body || savingEdit.value) return
  savingEdit.value = true
  try {
    const updated = await eventsApi.updateComment(props.eventId, c.id, body)
    const idx = comments.value.findIndex((x) => x.id === c.id)
    if (idx !== -1) comments.value[idx] = updated
    editingId.value = null
  } catch {
    ElMessage.error('編輯失敗，請稍後再試')
  } finally {
    savingEdit.value = false
  }
}

// ---- delete ----
// Author removes their own after a plain confirm (no password); an admin
// moderating someone else's re-authenticates through the password dialog.
const {
  dialogOpen: pwDialogOpen,
  target: pwTarget,
  submitting: pwSubmitting,
  error: pwError,
  open: askPasswordDelete,
  confirm: onPasswordConfirm,
} = useDeleteWithPassword({
  remove: (c, password) =>
    eventsApi.removeComment(props.eventId, c.id, password),
  messages: { 404: '留言已不存在' },
  onSuccess: (c) => {
    comments.value = comments.value.filter((x) => x.id !== c.id)
    ElMessage.success('已刪除留言')
  },
})

async function requestDelete(c) {
  if (!c.can_edit) {
    // Not the author → an admin moderating → needs the admin password.
    askPasswordDelete(c)
    return
  }
  try {
    await ElMessageBox.confirm('確定刪除這則留言？', '刪除留言', {
      type: 'warning',
      confirmButtonText: '刪除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await eventsApi.removeComment(props.eventId, c.id)
    comments.value = comments.value.filter((x) => x.id !== c.id)
    ElMessage.success('已刪除留言')
  } catch {
    ElMessage.error('刪除失敗，請稍後再試')
  }
}

function formatTime(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleString('zh-TW', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function initial(name) {
  return (name || '?').trim().charAt(0) || '?'
}
</script>

<template>
  <section class="comments" data-test="event-comments">
    <h3 class="comments-title">
      留言
      <span v-if="comments.length" class="comments-count"
        >（{{ comments.length }}）</span
      >
    </h3>

    <p v-if="loading" class="comments-hint" data-test="comments-loading">
      載入留言中…
    </p>
    <p
      v-else-if="loadError"
      class="comments-hint is-error"
      data-test="comments-error"
    >
      留言載入失敗，請稍後再試。
    </p>
    <p
      v-else-if="comments.length === 0"
      class="comments-hint"
      data-test="comments-empty"
    >
      還沒有留言，來當第一個留言的人吧。
    </p>

    <ul v-else class="comment-list">
      <li
        v-for="c in comments"
        :key="c.id"
        class="comment-item"
        data-test="comment-item"
      >
        <div class="avatar" aria-hidden="true">
          {{ initial(c.author_display_name) }}
        </div>
        <div class="comment-main">
          <div class="comment-head">
            <span class="comment-author" data-test="comment-author">
              {{ c.author_display_name || '未知成員' }}
            </span>
            <span class="comment-time">{{ formatTime(c.created_at) }}</span>
            <span
              v-if="c.edited_at"
              class="comment-edited"
              data-test="comment-edited"
              >（已編輯）</span
            >
          </div>

          <div v-if="editingId === c.id" class="comment-edit">
            <el-input
              v-model="editDraft"
              type="textarea"
              :autosize="{ minRows: 2, maxRows: 8 }"
              maxlength="2000"
              show-word-limit
              data-test="comment-edit-input"
            />
            <div class="comment-edit-actions">
              <el-button
                size="small"
                type="primary"
                :loading="savingEdit"
                data-test="comment-edit-save"
                @click="saveEdit(c)"
              >
                儲存
              </el-button>
              <el-button
                size="small"
                data-test="comment-edit-cancel"
                @click="cancelEdit"
              >
                取消
              </el-button>
            </div>
          </div>
          <p v-else class="comment-body" data-test="comment-body">
            {{ c.body }}
          </p>

          <div
            v-if="(c.can_edit || c.can_delete) && editingId !== c.id"
            class="comment-actions"
          >
            <button
              v-if="c.can_edit"
              type="button"
              class="link-btn"
              data-test="comment-edit"
              @click="startEdit(c)"
            >
              編輯
            </button>
            <button
              v-if="c.can_delete"
              type="button"
              class="link-btn is-danger"
              data-test="comment-delete"
              @click="requestDelete(c)"
            >
              刪除
            </button>
          </div>
        </div>
      </li>
    </ul>

    <div v-if="canPost" class="comment-compose" data-test="comment-compose">
      <el-input
        v-model="draft"
        type="textarea"
        :autosize="{ minRows: 2, maxRows: 6 }"
        maxlength="2000"
        show-word-limit
        placeholder="留個言吧…"
        data-test="comment-input"
      />
      <div class="compose-actions">
        <el-button
          type="primary"
          :loading="submitting"
          :disabled="!draft.trim()"
          data-test="comment-submit"
          @click="submit"
        >
          送出留言
        </el-button>
      </div>
    </div>

    <DeleteWithPasswordDialog
      v-model="pwDialogOpen"
      title="刪除留言"
      :item-name="pwTarget?.body?.slice(0, 24) ?? ''"
      warning="將永久刪除這則留言，此操作無法復原。"
      :loading="pwSubmitting"
      :error-message="pwError"
      @confirm="onPasswordConfirm"
    />
  </section>
</template>

<style scoped>
.comments {
  border-top: 1px solid rgba(15, 23, 42, 0.08);
  padding-top: 18px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.comments-title {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  color: var(--ink-900);
}

.comments-count {
  color: var(--ink-500);
  font-weight: 500;
}

.comments-hint {
  margin: 0;
  font-size: 13px;
  color: var(--ink-500);
}

.comments-hint.is-error {
  color: #ef4444;
}

.comment-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.comment-item {
  display: flex;
  gap: 10px;
}

.avatar {
  flex: 0 0 auto;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 700;
  color: #fff;
  background: linear-gradient(
    135deg,
    var(--brand-primary, #6366f1),
    var(--brand-accent, #7c3aed)
  );
  text-transform: uppercase;
}

.comment-main {
  flex: 1;
  min-width: 0;
}

.comment-head {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 8px;
}

.comment-author {
  font-size: 13.5px;
  font-weight: 600;
  color: var(--ink-900);
}

.comment-time {
  font-size: 12px;
  color: var(--ink-400, #94a3b8);
  font-variant-numeric: tabular-nums;
}

.comment-edited {
  font-size: 12px;
  color: var(--ink-400, #94a3b8);
}

.comment-body {
  margin: 4px 0 0;
  font-size: 14px;
  line-height: 1.6;
  color: var(--ink-800, #1f2937);
  /* Plain text: preserve the author's line breaks, wrap long words, and
     never let a URL blow out the dialog width. */
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.comment-edit {
  margin-top: 6px;
}

.comment-edit-actions {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}

.comment-actions {
  display: flex;
  gap: 14px;
  margin-top: 6px;
}

.link-btn {
  border: 0;
  background: none;
  padding: 0;
  font-size: 12.5px;
  color: var(--ink-500);
  cursor: pointer;
}

.link-btn:hover {
  color: var(--brand-primary, #6366f1);
}

.link-btn.is-danger:hover {
  color: #ef4444;
}

.comment-compose {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.compose-actions {
  display: flex;
  justify-content: flex-end;
}
</style>
