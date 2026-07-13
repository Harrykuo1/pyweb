import { ref } from 'vue'

// Optimistic like/unlike state shared by any post type. `like`/`unlike` are
// async callbacks that hit the relevant API and resolve to the server's
// { like_count, liked } truth; the composable flips the UI immediately and
// reconciles (or reverts on error) when they settle.
export function useLikeToggle({ liked = false, count = 0, like, unlike }) {
  const isLiked = ref(!!liked)
  const likeCount = ref(count ?? 0)
  const pending = ref(false)

  async function toggle() {
    if (pending.value) return
    const wasLiked = isLiked.value
    const prevCount = likeCount.value

    // Optimistic flip.
    isLiked.value = !wasLiked
    likeCount.value = Math.max(0, prevCount + (wasLiked ? -1 : 1))
    pending.value = true
    try {
      const res = wasLiked ? await unlike() : await like()
      // Trust the server's canonical count/state.
      isLiked.value = res.liked
      likeCount.value = res.like_count
    } catch {
      isLiked.value = wasLiked
      likeCount.value = prevCount
    } finally {
      pending.value = false
    }
  }

  // Let a parent push external truth in (e.g. a fresh list fetch).
  function sync(newLiked, newCount) {
    isLiked.value = !!newLiked
    likeCount.value = newCount ?? 0
  }

  return { isLiked, likeCount, pending, toggle, sync }
}
