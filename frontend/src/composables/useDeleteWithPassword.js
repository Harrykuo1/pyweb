import { ref } from 'vue'

const DEFAULT_MESSAGES = {
  422: '密碼錯誤',
  403: '權限不足',
  404: '項目已不存在',
  fallback: '刪除失敗，請稍後再試',
}

// Shared "delete with password confirmation" flow. Owns the dialog
// open/target/submitting/error state and maps the backend status code to
// a human message. The API call itself and any post-success side effects
// (success toast, list refetch, closing a parent detail dialog) stay with
// the caller via `remove` and `onSuccess`, so the same flow serves jobs,
// attachments, events and members without baking any one page's copy in.
export function useDeleteWithPassword({ remove, onSuccess, messages } = {}) {
  const msg = { ...DEFAULT_MESSAGES, ...(messages ?? {}) }

  const dialogOpen = ref(false)
  const target = ref(null)
  const submitting = ref(false)
  const error = ref('')

  function open(item) {
    target.value = item
    error.value = ''
    dialogOpen.value = true
  }

  async function confirm(password) {
    const item = target.value
    if (!item) return
    submitting.value = true
    error.value = ''
    try {
      await remove(item, password)
      dialogOpen.value = false
      target.value = null
      await onSuccess?.(item)
    } catch (err) {
      const status = err?.response?.status
      error.value = msg[status] ?? msg.fallback
    } finally {
      submitting.value = false
    }
  }

  return { dialogOpen, target, submitting, error, open, confirm }
}
