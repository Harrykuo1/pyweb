<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps({
  // The text to display. Falsy values render as an empty marquee so the
  // caller can pass a possibly-null field straight through.
  text: { type: [String, Number], default: '' },
  // Pixels-per-second the track moves while scrolling. Choose a value
  // that reads comfortably; 28 ≈ a calm 2s per 60-char latin string.
  speed: { type: Number, default: 28 },
  // Gap (px) appended to each duplicated chunk so consecutive loops are
  // visually separated instead of running into themselves.
  gap: { type: Number, default: 32 },
  // Pause animation while the cursor is over the marquee, so the user
  // can read text that's currently mid-scroll.
  pauseOnHover: { type: Boolean, default: true },
})

const containerRef = ref(null)
const probeRef = ref(null)
const overflowing = ref(false)
const duration = ref(0)

// Measure whether the text overflows the container and, if so, derive
// an animation duration proportional to text length so short and long
// strings scroll at the same visual speed.
async function measure() {
  await nextTick()
  const container = containerRef.value
  const probe = probeRef.value
  if (!container || !probe) return
  const containerW = container.clientWidth
  const textW = probe.scrollWidth
  // +1 tolerates sub-pixel rounding that would otherwise flap.
  if (textW > containerW + 1) {
    overflowing.value = true
    duration.value = (textW + props.gap) / props.speed
  } else {
    overflowing.value = false
    duration.value = 0
  }
}

let resizeObserver = null

onMounted(() => {
  measure()
  if (typeof ResizeObserver !== 'undefined' && containerRef.value) {
    resizeObserver = new ResizeObserver(() => measure())
    resizeObserver.observe(containerRef.value)
  }
})

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
})

watch(
  () => props.text,
  () => measure(),
)
watch(
  () => props.speed,
  () => measure(),
)
watch(
  () => props.gap,
  () => measure(),
)

const trackStyle = computed(() => {
  if (!overflowing.value) return {}
  return {
    animationDuration: `${duration.value}s`,
  }
})

const chunkStyle = computed(() => {
  if (!overflowing.value) return {}
  // Tail gap lives on the chunk rather than as flex `gap` so the keyframe
  // can translate exactly one chunk-width for a seamless loop.
  return {
    paddingRight: `${props.gap}px`,
  }
})
</script>

<template>
  <span
    ref="containerRef"
    class="marquee"
    :class="{
      'is-scrolling': overflowing,
      'is-pauseable': pauseOnHover,
    }"
  >
    <span class="marquee__track" :style="trackStyle">
      <span ref="probeRef" class="marquee__chunk" :style="chunkStyle">
        {{ text }}
      </span>
      <span
        v-if="overflowing"
        class="marquee__chunk"
        :style="chunkStyle"
        aria-hidden="true"
      >
        {{ text }}
      </span>
    </span>
  </span>
</template>

<style scoped>
.marquee {
  display: block;
  overflow: hidden;
  white-space: nowrap;
  width: 100%;
}

.marquee__track {
  display: inline-flex;
  align-items: baseline;
  will-change: transform;
}

.marquee__chunk {
  flex: 0 0 auto;
}

/* Scrolling mode: translate by exactly one chunk's width (text + gap)
   each loop. Because the track has two identical chunks, -50% lands the
   second chunk exactly where the first chunk started — seamless. */
.marquee.is-scrolling .marquee__track {
  animation-name: marquee-scroll;
  animation-timing-function: linear;
  animation-iteration-count: infinite;
}

.marquee.is-scrolling.is-pauseable:hover .marquee__track,
.marquee.is-scrolling.is-pauseable:focus-within .marquee__track {
  animation-play-state: paused;
}

@keyframes marquee-scroll {
  0% {
    transform: translateX(0);
  }
  100% {
    transform: translateX(-50%);
  }
}

/* Honor reduced-motion preferences: never auto-scroll. The user can
   still hover to read past the truncation point — falling back to
   overflow-ellipsis would lose the indication that more text exists. */
@media (prefers-reduced-motion: reduce) {
  .marquee.is-scrolling .marquee__track {
    animation: none;
  }
}
</style>
