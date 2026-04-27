<script setup>
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { ElButton, ElDialog, ElMessage } from 'element-plus'
import Cropper from 'cropperjs'

const props = defineProps({
  modelValue: { type: Boolean, required: true },
  sourceFile: { type: File, default: null },
})

const emit = defineEmits(['update:modelValue', 'cropped'])

const imgRef = ref(null)
const objectUrl = ref('')
let cropperInstance = null

const submitting = ref(false)

// cropperjs 2.x is web-component based. We pass a custom template so we can
// pin aspect-ratio="1" on the <cropper-selection> directly; default
// template would let users free-form crop.
const CROPPER_TEMPLATE = `
  <cropper-canvas background>
    <cropper-image rotatable scalable skewable translatable></cropper-image>
    <cropper-shade hidden></cropper-shade>
    <cropper-handle action="select" plain></cropper-handle>
    <cropper-selection initial-coverage="0.7" aspect-ratio="1" movable resizable>
      <cropper-grid role="grid" covered></cropper-grid>
      <cropper-crosshair centered></cropper-crosshair>
      <cropper-handle action="move" theme-color="rgba(255, 255, 255, 0.35)"></cropper-handle>
      <cropper-handle action="n-resize"></cropper-handle>
      <cropper-handle action="e-resize"></cropper-handle>
      <cropper-handle action="s-resize"></cropper-handle>
      <cropper-handle action="w-resize"></cropper-handle>
      <cropper-handle action="ne-resize"></cropper-handle>
      <cropper-handle action="nw-resize"></cropper-handle>
      <cropper-handle action="se-resize"></cropper-handle>
      <cropper-handle action="sw-resize"></cropper-handle>
    </cropper-selection>
  </cropper-canvas>
`

function disposeCropper() {
  if (cropperInstance) {
    cropperInstance.destroy()
    cropperInstance = null
  }
  if (objectUrl.value) {
    URL.revokeObjectURL(objectUrl.value)
    objectUrl.value = ''
  }
}

async function setupCropper() {
  if (!props.sourceFile) return
  if (objectUrl.value) URL.revokeObjectURL(objectUrl.value)
  objectUrl.value = URL.createObjectURL(props.sourceFile)
  // el-dialog mounts its body lazily; wait one tick so v-if renders the
  // <img ref="imgRef"> before we hand it to Cropper.
  await nextTick()
  if (!imgRef.value) return
  imgRef.value.src = objectUrl.value
  await nextTick()
  if (cropperInstance) cropperInstance.destroy()
  cropperInstance = new Cropper(imgRef.value, { template: CROPPER_TEMPLATE })
}

watch(
  () => [props.modelValue, props.sourceFile],
  async ([open, file]) => {
    if (open && file) {
      await setupCropper()
    } else if (!open) {
      disposeCropper()
    }
  },
  { immediate: true },
)

onBeforeUnmount(disposeCropper)

function close() {
  emit('update:modelValue', false)
}

async function handleConfirm() {
  if (!cropperInstance) return
  const selection = cropperInstance.getCropperSelection()
  if (!selection) {
    ElMessage.error('裁切失敗，請重新選擇照片')
    return
  }

  submitting.value = true
  try {
    // Render at 512x512 — generous for an avatar, well under the 5 MB cap
    // and identical width/height makes downstream <img> sizing trivial.
    const canvas = await selection.$toCanvas({ width: 512, height: 512 })
    const blob = await new Promise((resolve) =>
      canvas.toBlob(resolve, 'image/jpeg', 0.9),
    )
    if (!blob) {
      ElMessage.error('裁切失敗，請重新選擇照片')
      return
    }
    const file = new File([blob], 'photo.jpg', { type: 'image/jpeg' })
    emit('cropped', file)
    close()
  } finally {
    submitting.value = false
  }
}

defineExpose({ handleConfirm })
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    title="裁切照片（1:1）"
    width="640"
    :close-on-click-modal="false"
    :z-index="9000"
    @update:model-value="emit('update:modelValue', $event)"
    @closed="disposeCropper"
  >
    <div class="cropper-wrap">
      <img ref="imgRef" alt="待裁切照片" />
    </div>
    <p class="hint">拖曳選框調整位置；四角拖把控制大小（強制 1:1）。</p>

    <template #footer>
      <el-button @click="close">取消</el-button>
      <el-button
        type="primary"
        :loading="submitting"
        data-test="crop-confirm"
        @click="handleConfirm"
      >
        套用裁切
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.cropper-wrap {
  width: 100%;
  height: 420px;
  background: #f5f7fa;
  border-radius: 8px;
  overflow: hidden;
}

.cropper-wrap img {
  display: block;
  max-width: 100%;
  max-height: 100%;
}

/* cropperjs 2.x renders into a <cropper-canvas> custom element. The default
   display: inline collapses the canvas inside our fixed-height wrap, so
   force it to fill the available box. */
.cropper-wrap :deep(cropper-canvas) {
  display: block;
  width: 100%;
  height: 100%;
}

.hint {
  margin: 12px 0 0;
  font-size: 12px;
  color: #909399;
}
</style>
