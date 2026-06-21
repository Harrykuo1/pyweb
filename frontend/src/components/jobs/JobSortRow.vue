<script setup>
defineProps({
  options: { type: Array, required: true }, // [{ key, label }]
  sortKey: { type: String, required: true },
  sortOrder: { type: String, required: true },
})
defineEmits(['toggle'])
</script>

<template>
  <div class="sort-row">
    <span class="sort-label">排序</span>
    <button
      v-for="opt in options"
      :key="opt.key"
      type="button"
      :class="['sort-pill', { 'is-active': sortKey === opt.key }]"
      :data-test="`sort-${opt.key}`"
      @click="$emit('toggle', opt.key)"
    >
      {{ opt.label }}
      <span v-if="sortKey === opt.key" class="sort-arrow" aria-hidden="true">
        {{ sortOrder === 'asc' ? '↑' : '↓' }}
      </span>
    </button>
  </div>
</template>

<style scoped>
.sort-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
}

.sort-label {
  font-size: 12px;
  color: var(--ink-500);
  margin-right: 4px;
  letter-spacing: 0.04em;
}

.sort-pill {
  border: 1px solid rgba(15, 23, 42, 0.08);
  background: var(--surface-0);
  color: var(--ink-700);
  padding: 5px 12px;
  font-size: 12px;
  font-weight: 500;
  border-radius: 999px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  transition: background-color var(--dur) var(--ease),
    color var(--dur) var(--ease), border-color var(--dur) var(--ease),
    box-shadow var(--dur) var(--ease);
}

.sort-pill:hover {
  border-color: rgba(99, 102, 241, 0.4);
  color: var(--brand-primary-hover);
}

.sort-pill.is-active {
  background: linear-gradient(135deg, var(--brand-primary), var(--brand-accent));
  color: var(--surface-0);
  border-color: transparent;
  box-shadow: 0 6px 16px -4px rgba(99, 102, 241, 0.45);
}

.sort-arrow {
  font-size: 11px;
}

@media (max-width: 640px) {
  /* Compact sort row: drop the "排序" label and tighten pills so the
     options sit on one or two cleaner lines. Mirrors Members. */
  .sort-label {
    display: none;
  }

  .sort-row {
    gap: 4px;
  }

  .sort-pill {
    padding: 4px 10px;
    font-size: 11px;
  }
}
</style>
