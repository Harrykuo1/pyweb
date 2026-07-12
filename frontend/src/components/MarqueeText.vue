<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'

const props = defineProps({
  // The text to display. Falsy values render an empty marquee so the caller
  // can pass a possibly-null field straight through.
  text: { type: [String, Number], default: '' },
  // Pixels-per-second the text travels while scrolling.
  speed: { type: Number, default: 28 },
  // Gap (px) between the primary copy and its trailing ghost so the loop seam
  // stays invisible.
  gap: { type: Number, default: 32 },
  // Hover signal from the parent card. The text only scrolls while the card is
  // hovered AND the text overflows; at rest it shows an ellipsis.
  active: { type: Boolean, default: true },
})

const containerRef = ref(null)
const overflowing = ref(false)

const scrolling = computed(() => props.active && overflowing.value)

// At rest the text is the container's own inline content, so scrollWidth is
// the full text width and clientWidth the visible width. Only measure while
// NOT scrolling — once the flex track mounts, scrollWidth reflects both copies.
function measure() {
  const el = containerRef.value
  if (!el) return
  const containerW = el.clientWidth
  const textW = el.scrollWidth
  // +1 tolerates sub-pixel rounding that would otherwise flap.
  if (textW > containerW + 1) {
    overflowing.value = true
    const distance = textW + props.gap
    el.style.setProperty('--marquee-distance', `-${distance}px`)
    el.style.setProperty(
      '--marquee-duration',
      `${Math.max(3, distance / props.speed)}s`,
    )
  } else {
    overflowing.value = false
  }
}

// Measure on the rising edge of a hover (before the track mounts, so the
// reading stays clean) and whenever the text changes.
watch(
  () => props.active,
  (isActive) => {
    if (isActive) measure()
  },
)
watch(
  () => props.text,
  async () => {
    await nextTick()
    if (props.active) measure()
    else overflowing.value = false
  },
)

onMounted(async () => {
  await nextTick()
  if (props.active) measure()
})
</script>

<template>
  <span
    ref="containerRef"
    class="marquee"
    :class="{ 'is-scrolling': scrolling }"
  >
    <span v-if="scrolling" class="marquee__track">
      <span class="marquee__copy">{{ text }}</span>
      <span
        class="marquee__copy"
        aria-hidden="true"
        :style="{ paddingLeft: `${gap}px` }"
        >{{ text }}</span
      >
    </span>
    <template v-else>{{ text }}</template>
  </span>
</template>

<style scoped>
.marquee {
  display: block;
  width: 100%;
  overflow: hidden;
  white-space: nowrap;
  /* At rest the text is the block's own inline content, so this ellipsis
     clips overflow with a "…". */
  text-overflow: ellipsis;
}

/* Scrolling: a two-copy flex track translates in a single-direction loop.
   The ghost trails the primary by `gap`, so once the primary has moved one
   (text + gap) the ghost lands exactly where the primary began — the keyframe
   restart is seamless. Flex ignores inter-copy whitespace, keeping the seam
   exact. */
.marquee.is-scrolling {
  text-overflow: clip;
}

.marquee__track {
  display: inline-flex;
  will-change: transform;
  animation: marquee-scroll var(--marquee-duration, 6s) linear infinite;
}

.marquee__copy {
  flex: 0 0 auto;
}

@keyframes marquee-scroll {
  0% {
    transform: translateX(0);
  }
  100% {
    transform: translateX(var(--marquee-distance, 0));
  }
}
</style>
