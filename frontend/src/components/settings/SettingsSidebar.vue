<script setup>
import { computed } from 'vue'
import { ElIcon } from 'element-plus'

const props = defineProps({
  items: { type: Array, required: true },
  modelValue: { type: String, required: true },
})
const emit = defineEmits(['update:modelValue'])

const active = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

function select(key) {
  if (key !== active.value) active.value = key
}
</script>

<template>
  <nav class="settings-sidebar" aria-label="設定分類">
    <button
      v-for="item in items"
      :key="item.key"
      type="button"
      class="settings-sidebar__item"
      :class="{ 'is-active': item.key === active }"
      :aria-current="item.key === active ? 'page' : undefined"
      :data-test="`settings-tab-${item.key}`"
      @click="select(item.key)"
    >
      <span class="settings-sidebar__icon" aria-hidden="true">
        <el-icon :size="18">
          <component :is="item.icon" />
        </el-icon>
      </span>
      <span class="settings-sidebar__text">
        <span class="settings-sidebar__label">{{ item.label }}</span>
        <span v-if="item.description" class="settings-sidebar__hint">
          {{ item.description }}
        </span>
      </span>
    </button>
  </nav>
</template>

<style scoped>
.settings-sidebar {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px;
  background: var(--surface-0);
  border: 1px solid rgba(15, 23, 42, 0.06);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  position: sticky;
  top: 88px;
  align-self: flex-start;
}

.settings-sidebar__item {
  appearance: none;
  background: transparent;
  border: 0;
  cursor: pointer;
  text-align: left;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: var(--radius-md);
  color: var(--ink-700);
  font: inherit;
  width: 100%;
  transition: background-color var(--dur) var(--ease),
    color var(--dur) var(--ease);
}

.settings-sidebar__item:hover {
  background: rgba(99, 102, 241, 0.06);
  color: var(--brand-primary);
}

.settings-sidebar__item.is-active {
  background: linear-gradient(
    135deg,
    rgba(99, 102, 241, 0.12),
    rgba(139, 92, 246, 0.12)
  );
  color: var(--brand-primary);
}

.settings-sidebar__item.is-active .settings-sidebar__icon {
  color: var(--brand-primary);
}

.settings-sidebar__icon {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: rgba(99, 102, 241, 0.08);
  color: var(--brand-primary);
  flex: 0 0 auto;
}

.settings-sidebar__item.is-active .settings-sidebar__icon {
  background: linear-gradient(135deg, var(--brand-primary), var(--brand-accent));
  color: #ffffff;
  box-shadow: 0 4px 10px rgba(99, 102, 241, 0.25);
}

.settings-sidebar__text {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.settings-sidebar__label {
  font-size: 14px;
  font-weight: 600;
}

.settings-sidebar__hint {
  font-size: 12px;
  color: var(--ink-500);
  line-height: 1.4;
  margin-top: 2px;
}

.settings-sidebar__item.is-active .settings-sidebar__hint {
  color: var(--brand-primary);
  opacity: 0.78;
}

@media (max-width: 900px) {
  .settings-sidebar {
    position: static;
    flex-direction: row;
    overflow-x: auto;
    gap: 6px;
    padding: 6px;
  }

  .settings-sidebar__item {
    flex: 0 0 auto;
    padding: 8px 10px;
  }

  .settings-sidebar__hint {
    display: none;
  }
}
</style>
