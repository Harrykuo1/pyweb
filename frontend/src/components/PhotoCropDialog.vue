<script setup>
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { ElButton, ElDialog, ElMessage } from 'element-plus'
import Cropper from 'cropperjs'

const props = defineProps({
  modelValue: { type: Boolean, required: true },
  sourceFile: { type: File, default: null },
  // Defaults are tuned for the avatar use-case. Other call sites (e.g.
  // login-logo) override them to preserve transparency or use a smaller
  // canvas size.
  outputType: { type: String, default: 'image/jpeg' },
  outputQuality: { type: Number, default: 0.9 },
  outputSize: { type: Number, default: 512 },
  outputFilename: { type: String, default: 'photo' },
  title: { type: String, default: '裁切照片（1:1）' },
})

const emit = defineEmits(['update:modelValue', 'cropped'])

const EXT_BY_TYPE = {
  'image/jpeg': 'jpg',
  'image/png': 'png',
  'image/webp': 'webp',
}

const imgRef = ref(null)
const objectUrl = ref('')
let cropperInstance = null

const submitting = ref(false)

// cropperjs 2.x is web-component based. We pass a custom template so we can
// pin aspect-ratio="1" on the <cropper-selection> directly; default
// template would let users free-form crop.
// initial-center-size="contain" makes the loaded image fully fit the
// canvas (with letterboxing) instead of overflowing past the canvas at
// natural size — so users always see the full photo to crop against.
const CROPPER_TEMPLATE = `
  <cropper-canvas background>
    <cropper-image initial-center-size="contain" rotatable scalable skewable translatable></cropper-image>
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

// Reject any selection change that would push the crop box outside the
// image's currently rendered bounds. Cropperjs computes new (x, y, w, h)
// in canvas-pixel coordinates; we compare against the image element's
// DOM rect translated into the same coordinate space. preventDefault on
// the change event makes the box stop at the edge instead of bouncing
// or freezing the rest of the interaction.
function clampSelectionToImage(event) {
  if (!cropperInstance) return
  const image = cropperInstance.getCropperImage()
  const canvas = cropperInstance.getCropperCanvas()
  if (!image || !canvas) return
  const canvasRect = canvas.getBoundingClientRect()
  const imageRect = image.getBoundingClientRect()
  const ix = imageRect.left - canvasRect.left
  const iy = imageRect.top - canvasRect.top
  const iw = imageRect.width
  const ih = imageRect.height
  const { x, y, width, height } = event.detail
  if (
    x < ix - 0.5 ||
    y < iy - 0.5 ||
    x + width > ix + iw + 0.5 ||
    y + height > iy + ih + 0.5
  ) {
    event.preventDefault()
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

  // Wait for the image to actually load so getBoundingClientRect on it
  // returns the real rendered size; without this the rect is 0×0 and
  // the initial-fit math produces nonsense.
  const image = cropperInstance.getCropperImage()
  if (image && typeof image.$ready === 'function') {
    try { await image.$ready() } catch { /* image failed to load */ }
  }

  // For portrait / landscape photos contained in our 4:3 canvas, the
  // default initial-coverage selection can be larger than the image's
  // shorter side and end up partly outside the image. Re-center and
  // shrink the selection so it always fits comfortably inside the
  // image bounds before the clamp listener starts blocking changes.
  const selection = cropperInstance.getCropperSelection()
  const canvas = cropperInstance.getCropperCanvas()
  if (selection && image && canvas) {
    const canvasRect = canvas.getBoundingClientRect()
    const imageRect = image.getBoundingClientRect()
    if (imageRect.width > 0 && imageRect.height > 0) {
      const ix = imageRect.left - canvasRect.left
      const iy = imageRect.top - canvasRect.top
      const size = Math.min(imageRect.width, imageRect.height) * 0.8
      const x = ix + (imageRect.width - size) / 2
      const y = iy + (imageRect.height - size) / 2
      selection.$change(x, y, size, size, 1, true)
    }
    selection.addEventListener('change', clampSelectionToImage)
  }
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
    const size = props.outputSize
    const canvas = await selection.$toCanvas({ width: size, height: size })
    const blob = await new Promise((resolve) =>
      canvas.toBlob(resolve, props.outputType, props.outputQuality),
    )
    if (!blob) {
      ElMessage.error('裁切失敗，請重新選擇照片')
      return
    }
    const ext = EXT_BY_TYPE[props.outputType] ?? 'png'
    const file = new File(
      [blob],
      `${props.outputFilename}.${ext}`,
      { type: props.outputType },
    )
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
    :title="title"
    width="640"
    :close-on-click-modal="false"
    :append-to-body="true"
    @update:model-value="emit('update:modelValue', $event)"
    @closed="disposeCropper"
  >
    <div class="cropper-wrap">
      <img ref="imgRef" alt="待裁切照片" />
    </div>
    <p class="hint">拖曳選框調整位置、四角拖把控制大小（強制 1:1）；選框碰到照片邊界會自動停下。</p>

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
  /* Square-ish canvas so portrait, landscape and 1:1 photos all get a
     fair amount of working room. Capped via vh so very tall viewports
     don't blow up the dialog. */
  aspect-ratio: 4 / 3;
  max-height: 60vh;
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

/* The default ~7px square handles are hard to grab, especially on
   touch. Beef up the resize corner / edge handles so they're visible
   and easy to drag without pushing them off the image. */
.cropper-wrap :deep(cropper-handle[action$="-resize"]) {
  width: 16px;
  height: 16px;
  border-radius: 3px;
  background: rgba(255, 255, 255, 0.95);
  box-shadow: 0 1px 4px rgba(15, 23, 42, 0.35);
}

.hint {
  margin: 12px 0 0;
  font-size: 12px;
  color: #909399;
}
</style>
