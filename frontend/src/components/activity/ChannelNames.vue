<script setup>
import { ref } from 'vue'
import { ElOption, ElSelect } from 'element-plus'
import { useAuthStore } from '../../stores/auth'
import { activityApi } from '../../api/activity'
const props = defineProps({
  channels: { type: Array, required: true },
  names: { type: Object, required: true },
})
const emit = defineEmits(['saved'])
const auth = useAuthStore()
const open = ref(false)
const selected = ref('')
const name = ref('')
const busy = ref(false)
const error = ref('')
function choose(id) {
  name.value = props.names[id] || ''
  error.value = ''
}
async function save() {
  if (!selected.value || !name.value.trim() || busy.value) return
  busy.value = true
  error.value = ''
  try {
    await activityApi.updateChannel(selected.value, name.value.trim())
    emit('saved')
    open.value = false
  } catch {
    error.value = '名稱儲存失敗，請稍後再試。'
  } finally {
    busy.value = false
  }
}
</script>
<template>
  <div v-if="auth.isAdmin" class="channel-editor">
    <button type="button" :aria-expanded="open" @click="open = !open">
      {{ open ? '收起名稱管理' : '管理頻道名稱' }}
    </button>
    <form v-if="open" @submit.prevent="save">
      <el-select
        v-model="selected"
        filterable
        aria-label="要命名的頻道"
        placeholder="選擇頻道"
        @change="choose"
      >
        <el-option
          v-for="id in channels"
          :key="id"
          :value="id"
          :label="`${names[id] || '未命名'} · ${id}`"
        />
      </el-select>
      <input
        v-model="name"
        required
        maxlength="100"
        aria-label="頻道名稱"
        placeholder="頻道名稱"
        :disabled="busy"
      />
      <small>新名稱也會套用到歷史資料；Bot 下次同步較新的名稱時會更新。</small>
      <p v-if="error" role="alert">{{ error }}</p>
      <button type="submit" :disabled="busy || !selected || !name.trim()">
        {{ busy ? '儲存中…' : '儲存名稱' }}
      </button>
    </form>
  </div>
</template>
<style scoped>
.channel-editor {
  margin-top: 16px;
}
button {
  border: 1px solid #ded6f4;
  background: #f5f1ff;
  color: #6d4abe;
  border-radius: 9px;
  padding: 8px 12px;
  cursor: pointer;
  font: inherit;
  font-size: 12px;
}
button:disabled {
  opacity: 0.5;
  cursor: default;
}
form {
  display: grid;
  gap: 10px;
  margin-top: 12px;
}
input {
  min-width: 0;
  border: 1px solid #ddd;
  border-radius: 8px;
  padding: 10px;
  font: inherit;
}
small {
  color: #81808e;
  line-height: 1.6;
}
p {
  color: #b44450;
  font-size: 12px;
}
</style>
