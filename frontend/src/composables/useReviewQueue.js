import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { jobsApi } from '../api/jobs'
import { eventsApi } from '../api/events'
import { extractError } from '../utils/apiError'

// Admin review inbox: the pending jobs and events awaiting approval, with
// accept / reject-with-reason actions. Logic lives here so Review.vue is
// presentation only. kind is 'job' | 'event'; the two are handled uniformly.
export function useReviewQueue() {
  const loading = ref(false)
  const jobs = ref([])
  const events = ref([])
  // `${kind}-${id}` of the row currently being acted on, for per-row spinners.
  const busyKey = ref(null)

  const pendingCount = computed(() => jobs.value.length + events.value.length)

  const _apiFor = (kind) => (kind === 'job' ? jobsApi : eventsApi)
  const _listFor = (kind) => (kind === 'job' ? jobs : events)

  async function load() {
    loading.value = true
    try {
      const [jobsResp, eventsResp] = await Promise.all([
        jobsApi.list({ status: 'pending', order: 'asc' }),
        eventsApi.list({ status: 'pending', order: 'asc' }),
      ])
      jobs.value = jobsResp.items ?? []
      events.value = eventsResp.items ?? []
    } catch {
      ElMessage.error('載入待審清單失敗')
    } finally {
      loading.value = false
    }
  }

  function _drop(kind, id) {
    const listRef = _listFor(kind)
    listRef.value = listRef.value.filter((x) => x.id !== id)
  }

  async function accept(kind, item) {
    busyKey.value = `${kind}-${item.id}`
    try {
      await _apiFor(kind).accept(item.id)
      _drop(kind, item.id)
      ElMessage.success('已通過')
    } catch (err) {
      ElMessage.error(extractError(err, '操作失敗，請稍後再試'))
    } finally {
      busyKey.value = null
    }
  }

  async function reject(kind, item) {
    let reason
    try {
      const res = await ElMessageBox.prompt(
        '請輸入退回原因（會顯示給發表者，讓對方修正後重新送審）。',
        '退回',
        {
          confirmButtonText: '退回',
          cancelButtonText: '取消',
          inputType: 'textarea',
          inputValidator: (v) => (v && v.trim() ? true : '請輸入退回原因'),
        },
      )
      reason = res.value.trim()
    } catch {
      return // cancelled
    }
    busyKey.value = `${kind}-${item.id}`
    try {
      await _apiFor(kind).reject(item.id, reason)
      _drop(kind, item.id)
      ElMessage.success('已退回')
    } catch (err) {
      ElMessage.error(extractError(err, '操作失敗，請稍後再試'))
    } finally {
      busyKey.value = null
    }
  }

  onMounted(load)

  return {
    loading,
    jobs,
    events,
    busyKey,
    pendingCount,
    load,
    accept,
    reject,
  }
}
