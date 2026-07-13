<script setup>
import { ElDialog } from 'element-plus'

import MemberAvatar from './members/MemberAvatar.vue'

defineProps({
  modelValue: { type: Boolean, required: true },
  likers: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  title: { type: String, default: '按愛心的人' },
})

const emit = defineEmits(['update:modelValue'])
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    :title="title"
    width="360"
    :teleported="false"
    data-test="likers-dialog"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <p v-if="loading" class="likers-hint" data-test="likers-loading">載入中…</p>
    <p
      v-else-if="likers.length === 0"
      class="likers-hint"
      data-test="likers-empty"
    >
      還沒有人按愛心。
    </p>
    <ul v-else class="liker-list">
      <li
        v-for="l in likers"
        :key="l.user_id"
        class="liker-item"
        data-test="liker-item"
      >
        <MemberAvatar
          :member-id="l.member_id"
          :name="l.display_name"
          :has-photo="l.has_photo"
          :photo-updated-at="l.photo_updated_at"
          :size="32"
        />
        <span class="liker-name">{{ l.display_name || '未知成員' }}</span>
      </li>
    </ul>
  </el-dialog>
</template>

<style scoped>
.likers-hint {
  margin: 0;
  padding: 8px 0;
  color: var(--ink-500, #64748b);
  font-size: 14px;
}

.liker-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 50vh;
  overflow-y: auto;
}

.liker-item {
  display: flex;
  align-items: center;
  gap: 10px;
}

.liker-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--ink-900, #0f172a);
}
</style>
