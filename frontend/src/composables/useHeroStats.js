import { computed, onMounted, ref } from 'vue'

import { membersApi } from '../api/members'
import { statsApi } from '../api/stats'
import { useCounter } from '../utils/useCounter'

const PILE_LIMIT = 6
const PILE_MIN_TO_SHOW = 3

// Home hero data: community counts (animated via useCounter) and the
// recent-member avatar pile, plus the derived pile visibility / overflow /
// subtitle copy. Fetched once on mount; failures keep the zeros so the
// hero still renders. Lifted out of Home.vue so the view is presentation.
export function useHeroStats() {
  const stats = ref({ total_members: 0, total_jobs: 0, total_events: 0 })
  const statsLoaded = ref(false)
  const recentMembers = ref([])

  onMounted(async () => {
    const tasks = [
      statsApi
        .get()
        .then((d) => {
          stats.value = d
        })
        .catch(() => {
          /* keep zeros */
        }),
      membersApi
        .list({ order: 'desc' })
        .then((rows) => {
          recentMembers.value = (rows ?? []).slice(0, PILE_LIMIT)
        })
        .catch(() => {
          recentMembers.value = []
        }),
    ]
    try {
      await Promise.all(tasks)
    } finally {
      statsLoaded.value = true
    }
  })

  const membersCount = useCounter(() => stats.value.total_members)
  const jobsCount = useCounter(() => stats.value.total_jobs)
  const eventsCount = useCounter(() => stats.value.total_events)

  const showPile = computed(
    () =>
      statsLoaded.value &&
      stats.value.total_members >= PILE_MIN_TO_SHOW &&
      recentMembers.value.length > 0,
  )

  const overflowCount = computed(() => {
    const total = stats.value.total_members
    const shown = recentMembers.value.length
    return Math.max(0, total - shown)
  })

  const heroSubtitle = computed(() => {
    if (!statsLoaded.value) return '正在點亮 pyweb 社群…'
    const total = stats.value.total_members
    if (total === 0) return '社群剛剛起步，等你來寫下第一筆故事。'
    if (total < PILE_MIN_TO_SHOW) {
      return `${total} 位學長姊已經在這裡，等你一起加入。`
    }
    return '在這裡找到自己的下一段故事。'
  })

  function memberPhotoSrc(m) {
    if (!m?.has_photo) return null
    return membersApi.photoUrl(m.id, m.photo_updated_at ?? '')
  }

  function memberInitial(m) {
    const name = m?.real_name ?? ''
    return name.charAt(0) || '?'
  }

  return {
    stats,
    statsLoaded,
    recentMembers,
    membersCount,
    jobsCount,
    eventsCount,
    showPile,
    overflowCount,
    heroSubtitle,
    memberPhotoSrc,
    memberInitial,
  }
}
