<script setup>
import { onBeforeUnmount, ref } from 'vue'
const props = defineProps({
  code: { type: String, required: true },
  label: { type: String, default: '範例' },
  language: { type: String, default: '' },
})
const status = ref('')
let timer
async function copy() {
  try {
    if (navigator.clipboard?.writeText)
      await navigator.clipboard.writeText(props.code)
    else {
      const input = document.createElement('textarea')
      const previous = document.activeElement
      input.value = props.code
      input.style.position = 'fixed'
      input.style.opacity = '0'
      document.body.appendChild(input)
      try {
        input.select()
        if (!document.execCommand('copy')) throw new Error('copy unavailable')
      } finally {
        input.remove()
        previous?.focus()
      }
    }
    status.value = '已複製'
  } catch {
    status.value = '無法自動複製，請選取下方文字'
  }
  clearTimeout(timer)
  timer = setTimeout(() => {
    status.value = ''
  }, 4000)
}
onBeforeUnmount(() => clearTimeout(timer))
</script>
<template>
  <div class="api-code">
    <div class="code-heading">
      <span
        >{{ label }} <small>{{ language }}</small></span
      ><button type="button" :aria-label="`複製${label}`" @click="copy">
        複製
      </button>
    </div>
    <p v-if="status" role="status">{{ status }}</p>
    <pre tabindex="0"><code>{{ code }}</code></pre>
  </div>
</template>
<style scoped>
.api-code {
  min-width: 0;
  border: 1px solid #e2e7f0;
  border-radius: 12px;
  overflow: hidden;
  margin: 14px 0;
}
.code-heading {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  background: #f5f7fb;
  color: #64748b;
  font-size: 12px;
}
.code-heading small {
  margin-left: 8px;
  color: #969cb0;
}
button {
  border: 1px solid #dedcf0;
  background: white;
  color: #7161c5;
  padding: 4px 10px;
  border-radius: 6px;
  cursor: pointer;
  flex-shrink: 0;
  font: inherit;
}
pre {
  margin: 0;
  padding: 18px;
  overflow-x: auto;
  background: #192237;
  color: #dfe7fa;
  font-size: 12px;
  line-height: 1.9;
  tab-size: 2;
}
p {
  margin: 0;
  padding: 8px 14px;
  color: #7161c5;
  font-size: 12px;
}
</style>
