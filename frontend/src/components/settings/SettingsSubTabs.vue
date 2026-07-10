<script setup>
const props = defineProps({
  // Each item: { key, label, badge? }
  items: { type: Array, required: true },
  // The active leaf key.
  modelValue: { type: String, required: true },
})
const emit = defineEmits(['update:modelValue'])

function select(key) {
  if (key !== props.modelValue) emit('update:modelValue', key)
}
</script>

<template>
  <div class="settings-subtabs" role="tablist">
    <button
      v-for="item in items"
      :key="item.key"
      type="button"
      role="tab"
      class="settings-subtabs__item"
      :class="{ 'is-active': item.key === modelValue }"
      :aria-selected="item.key === modelValue ? 'true' : 'false'"
      :data-test="`settings-subtab-${item.key}`"
      @click="select(item.key)"
    >
      <span class="settings-subtabs__label">{{ item.label }}</span>
      <span
        v-if="item.badge > 0"
        class="settings-subtabs__badge"
        :data-test="`settings-subtab-badge-${item.key}`"
        >{{ item.badge }}</span
      >
    </button>
  </div>
</template>

<style scoped>
.settings-subtabs {
  display: flex;
  gap: 4px;
  margin: 0 0 24px;
  padding: 4px;
  background: rgba(15, 23, 42, 0.03);
  border-radius: var(--radius-md);
  /* Mobile: let the bar scroll rather than wrap or clip. */
  overflow-x: auto;
  scrollbar-width: thin;
}

.settings-subtabs__item {
  appearance: none;
  background: transparent;
  border: 0;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border-radius: var(--radius-sm);
  color: var(--ink-500);
  font: inherit;
  font-size: 14px;
  font-weight: 600;
  white-space: nowrap;
  flex: 0 0 auto;
  transition:
    background-color var(--dur) var(--ease),
    color var(--dur) var(--ease);
}

.settings-subtabs__item:hover {
  color: var(--brand-primary);
}

.settings-subtabs__item.is-active {
  background: var(--surface-0);
  color: var(--brand-primary);
  box-shadow: var(--shadow-sm);
}

.settings-subtabs__badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 9px;
  background: var(--brand-primary);
  color: #ffffff;
  font-size: 11px;
  font-weight: 700;
  line-height: 1;
}
</style>
