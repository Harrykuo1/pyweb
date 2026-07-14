<script setup>
defineProps({
  liked: { type: Boolean, default: false },
  count: { type: Number, default: 0 },
  // Disables the toggle while a request is in flight.
  pending: { type: Boolean, default: false },
})

const emit = defineEmits(['toggle', 'show-likers'])
</script>

<template>
  <div class="like-row" data-test="like-row">
    <button
      type="button"
      class="like-toggle"
      :class="{ 'is-liked': liked }"
      :disabled="pending"
      :aria-pressed="liked"
      aria-label="愛心"
      data-test="like-toggle"
      @click="emit('toggle')"
    >
      <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
        <path
          d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"
          :fill="liked ? 'currentColor' : 'none'"
          stroke="currentColor"
          stroke-width="1.8"
        />
      </svg>
    </button>
    <button
      type="button"
      class="like-count"
      :disabled="count === 0"
      data-test="like-count"
      @click="emit('show-likers')"
    >
      {{ count }}
    </button>
  </div>
</template>

<style scoped>
.like-row {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.like-toggle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 4px;
  border: 0;
  background: none;
  border-radius: 999px;
  color: var(--ink-400, #94a3b8);
  cursor: pointer;
  transition:
    color var(--dur, 0.15s) var(--ease, ease),
    transform var(--dur, 0.15s) var(--ease, ease);
}
.like-toggle:hover:not(:disabled) {
  color: #ef4444;
}
.like-toggle:active:not(:disabled) {
  transform: scale(0.86);
}
.like-toggle.is-liked {
  color: #ef4444;
}
.like-toggle:disabled {
  cursor: default;
  opacity: 0.7;
}

.like-count {
  border: 0;
  background: none;
  padding: 2px 4px;
  font-size: 13px;
  font-variant-numeric: tabular-nums;
  color: var(--ink-500, #64748b);
  cursor: pointer;
}
.like-count:hover:not(:disabled) {
  text-decoration: underline;
}
.like-count:disabled {
  cursor: default;
}
</style>
