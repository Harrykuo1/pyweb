<script setup>
import { computed, ref, watch } from 'vue'

import { membersApi } from '../../api/members'

const props = defineProps({
  // The member whose photo to show. Null when the person has no member
  // profile (e.g. an admin) — then we always show the initial.
  memberId: { type: Number, default: null },
  // Drives the letter fallback and the alt text.
  name: { type: String, default: '' },
  size: { type: Number, default: 40 },
  // Defaults to true so a caller that only knows the id (e.g. the navbar)
  // still attempts the photo and falls back on a 404. Callers that know the
  // answer (the comment API returns it) pass false to skip the request.
  hasPhoto: { type: Boolean, default: true },
  // Cache-buster so a re-uploaded photo isn't served stale.
  photoUpdatedAt: { type: [String, Number], default: '' },
})

const loadError = ref(false)
// A new member (or a fresh photo) deserves another attempt after a prior 404.
watch(
  () => [props.memberId, props.photoUpdatedAt],
  () => {
    loadError.value = false
  },
)

const showPhoto = computed(
  () => props.memberId != null && props.hasPhoto && !loadError.value,
)
const src = computed(() =>
  props.memberId != null
    ? membersApi.photoUrl(props.memberId, props.photoUpdatedAt ?? '')
    : '',
)
// Spread to iterate by code point so a name that starts with an emoji or
// other astral character doesn't get sliced into half a surrogate pair.
const initial = computed(() => [...(props.name ?? '').trim()][0] ?? '?')
</script>

<template>
  <span
    class="member-avatar"
    :style="{
      width: `${size}px`,
      height: `${size}px`,
      fontSize: `${Math.round(size * 0.42)}px`,
    }"
    data-test="member-avatar"
  >
    <img
      v-if="showPhoto"
      :src="src"
      :alt="name ? `${name} 的頭像` : '成員頭像'"
      class="member-avatar__img"
      data-test="member-avatar-img"
      @error="loadError = true"
    />
    <span v-else class="member-avatar__initial" aria-hidden="true">
      {{ initial }}
    </span>
  </span>
</template>

<style scoped>
.member-avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  border-radius: 50%;
  overflow: hidden;
  font-weight: 700;
  line-height: 1;
  color: #fff;
  background: linear-gradient(
    135deg,
    var(--brand-primary, #6366f1),
    var(--brand-accent, #7c3aed)
  );
  user-select: none;
}

.member-avatar__img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.member-avatar__initial {
  text-transform: uppercase;
}
</style>
