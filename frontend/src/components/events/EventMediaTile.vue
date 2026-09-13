<script setup>
import { computed } from 'vue'
import { ElIcon } from 'element-plus'
import { Loading, VideoPlay, WarningFilled } from '@element-plus/icons-vue'

// One cell of the media grid. Photos and videos share it because a ready
// video is a poster frame with a play badge — the only cells that look
// different are the ones with no image to show yet.
const props = defineProps({
  item: { type: Object, required: true },
})

defineEmits(['open'])

const isVideo = computed(() => props.item.type === 'video')
const isProcessing = computed(
  () => isVideo.value && props.item.status === 'processing',
)
const isFailed = computed(() => isVideo.value && props.item.status === 'failed')
const isPlayable = computed(
  () => isVideo.value && props.item.status === 'ready',
)

const duration = computed(() => {
  const total = props.item.durationSeconds
  if (!total && total !== 0) return ''
  const m = Math.floor(total / 60)
  const s = String(total % 60).padStart(2, '0')
  return `${m}:${s}`
})

const label = computed(() => {
  if (isProcessing.value) return '影片處理中'
  if (isFailed.value) return '影片處理失敗'
  if (isVideo.value)
    return `播放影片${duration.value ? ` ${duration.value}` : ''}`
  return '查看照片'
})
</script>

<template>
  <button
    type="button"
    class="media-tile"
    :class="{ 'is-blank': !item.thumbUrl }"
    :disabled="isProcessing"
    :aria-label="label"
    data-test="gallery-thumb"
    :data-media-key="item.key"
    @click="$emit('open', item)"
  >
    <img
      v-if="item.thumbUrl"
      :src="item.thumbUrl"
      :alt="item.caption || ''"
      loading="lazy"
    />

    <span
      v-if="isProcessing"
      class="media-tile__state"
      data-test="media-processing"
    >
      <el-icon class="is-spinning"><Loading /></el-icon>
      <span>處理中…</span>
    </span>

    <span
      v-else-if="isFailed"
      class="media-tile__state is-failed"
      data-test="media-failed"
    >
      <el-icon><WarningFilled /></el-icon>
      <span>處理失敗</span>
    </span>

    <span v-else-if="isPlayable" class="media-tile__play" aria-hidden="true">
      <el-icon :size="26"><VideoPlay /></el-icon>
    </span>

    <span
      v-if="isPlayable && duration"
      class="media-tile__duration"
      aria-hidden="true"
    >
      {{ duration }}
    </span>
  </button>
</template>

<style scoped>
.media-tile {
  position: relative;
  display: block;
  width: 100%;
  aspect-ratio: 1 / 1;
  padding: 0;
  border: none;
  border-radius: var(--radius-md);
  overflow: hidden;
  cursor: pointer;
  background: var(--surface-2);
}

.media-tile:disabled {
  cursor: default;
}

.media-tile img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

/* A processing or failed video has no frame to show yet, so the cell needs
   to hold its own shape rather than collapsing. */
.media-tile.is-blank {
  display: grid;
  place-items: center;
  border: 1px dashed rgba(15, 23, 42, 0.16);
}

.media-tile__state {
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--ink-500);
}

.media-tile__state.is-failed {
  color: var(--el-color-danger, #c45656);
}

.is-spinning {
  animation: media-tile-spin 1s linear infinite;
}

@keyframes media-tile-spin {
  to {
    transform: rotate(360deg);
  }
}

@media (prefers-reduced-motion: reduce) {
  .is-spinning {
    animation: none;
  }
}

/* Play badge sits over the poster; the scrim keeps it legible on a bright
   frame without dimming the whole thumbnail. */
.media-tile__play {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  color: #fff;
  background: rgba(15, 23, 42, 0.28);
}

.media-tile__duration {
  position: absolute;
  right: 6px;
  bottom: 6px;
  padding: 1px 6px;
  border-radius: var(--radius-sm);
  background: rgba(15, 23, 42, 0.72);
  color: #fff;
  font-size: 11px;
  font-variant-numeric: tabular-nums;
}
</style>
