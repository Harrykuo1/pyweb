<script setup>
import { computed } from 'vue'

// Read-only renderer for a structured timeline. Each event is a
// card aligned along a gradient spine; the first event gets a
// violet treatment (start), the last gets emerald (closure / offer),
// the rest are indigo. D+N relative to the first event is a tabular
// pill in the card's header.
//
// Display order is the order events were entered. The editor never
// auto-sorts; the viewer must not either.
const props = defineProps({
  events: {
    type: Array,
    default: () => [],
  },
})

function _parseISODate(iso) {
  if (!iso) return null
  // Construct from local-time parts so the displayed date matches the
  // ISO string regardless of the viewer's timezone.
  const [y, m, d] = iso.split('-').map(Number)
  if (!y || !m || !d) return null
  return new Date(y, m - 1, d)
}

function _msPerDay() {
  return 24 * 60 * 60 * 1000
}

function _formatFullDate(date) {
  const y = date.getFullYear()
  const m = date.getMonth() + 1
  const d = date.getDate()
  return `${y}/${m}/${d}`
}

const enriched = computed(() => {
  const list = props.events ?? []
  if (list.length === 0) return []
  const firstDate = _parseISODate(list[0].date)
  if (!firstDate) return []

  return list.map((entry, index) => {
    const target = _parseISODate(entry.date)
    if (!target) {
      return {
        offsetLabel: '?',
        dateLabel: entry.date ?? '?',
        event: entry.event,
        position: _positionFor(index, list.length),
      }
    }
    const diffDays = Math.round((target - firstDate) / _msPerDay())
    const offsetLabel = diffDays >= 0 ? `D+${diffDays}` : `D${diffDays}`
    return {
      offsetLabel,
      dateLabel: _formatFullDate(target),
      event: entry.event,
      position: _positionFor(index, list.length),
    }
  })
})

function _positionFor(index, total) {
  if (index === 0) return 'first'
  if (index === total - 1) return 'last'
  return 'middle'
}
</script>

<template>
  <div class="timeline-display" data-test="timeline-display">
    <p v-if="enriched.length === 0" class="timeline-empty">尚無時程紀錄。</p>
    <ol
      v-else
      class="timeline-track"
      :class="{ 'is-singleton': enriched.length === 1 }"
    >
      <li
        v-for="(entry, index) in enriched"
        :key="index"
        :class="['timeline-event-card', `is-${entry.position}`]"
        data-test="timeline-display-item"
      >
        <span class="timeline-node" aria-hidden="true">
          <span class="timeline-node-pulse" />
        </span>
        <div class="timeline-content">
          <div class="timeline-header">
            <span class="timeline-date" data-test="timeline-display-date">
              {{ entry.dateLabel }}
            </span>
            <span class="timeline-offset" data-test="timeline-display-offset">
              {{ entry.offsetLabel }}
            </span>
          </div>
          <p class="timeline-event-text" data-test="timeline-display-event">
            {{ entry.event }}
          </p>
        </div>
      </li>
    </ol>
  </div>
</template>

<style scoped>
.timeline-display {
  --spine-x: 14px;
  --node-size: 14px;
  /* Gap from the spine to each card's left edge. Used by both
     .timeline-track (padding-left) and .timeline-node (left), so the
     two stay aligned when the gap is overridden at smaller widths. */
  --card-gap: 22px;
  position: relative;
  padding: 8px 4px 16px;
}

.timeline-empty {
  margin: 0;
  padding: 32px;
  text-align: center;
  color: var(--el-text-color-secondary);
  font-size: 14px;
}

.timeline-track {
  list-style: none;
  margin: 0;
  padding: 0 0 0 calc(var(--spine-x) + var(--card-gap));
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

/* The gradient spine running through every card. A single ::before
   keeps draws cheap and lets the gradient cover the full track in
   one continuous stroke. Singleton lists hide it because there's
   nothing to connect. */
.timeline-track::before {
  content: '';
  position: absolute;
  left: var(--spine-x);
  top: 14px;
  bottom: 14px;
  width: 2px;
  background: linear-gradient(
    180deg,
    #a855f7 0%,
    #6366f1 35%,
    #6366f1 65%,
    #10b981 100%
  );
  border-radius: 1px;
}

.timeline-track.is-singleton::before {
  display: none;
}

/* ------- Each event card ------- */
.timeline-event-card {
  position: relative;
  padding: 14px 18px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.65);
  backdrop-filter: blur(8px);
  border: 1px solid rgba(99, 102, 241, 0.12);
  box-shadow:
    0 1px 2px rgba(15, 23, 42, 0.04),
    0 4px 16px rgba(99, 102, 241, 0.05);
  transition:
    transform 220ms cubic-bezier(0.16, 1, 0.3, 1),
    box-shadow 220ms cubic-bezier(0.16, 1, 0.3, 1),
    border-color 220ms ease;
}

.timeline-event-card:hover {
  transform: translateX(3px);
  border-color: rgba(99, 102, 241, 0.28);
  box-shadow:
    0 1px 2px rgba(15, 23, 42, 0.06),
    0 8px 24px rgba(99, 102, 241, 0.16);
}

/* First event: violet — the kickoff. */
.timeline-event-card.is-first {
  background: linear-gradient(
    135deg,
    rgba(245, 243, 255, 0.95),
    rgba(237, 233, 254, 0.85)
  );
  border-color: rgba(168, 85, 247, 0.28);
}

/* Last event: emerald — the outcome / offer. Slightly stronger
   shadow to draw the eye. */
.timeline-event-card.is-last {
  background: linear-gradient(
    135deg,
    rgba(236, 253, 245, 0.95),
    rgba(209, 250, 229, 0.85)
  );
  border-color: rgba(16, 185, 129, 0.32);
  box-shadow:
    0 1px 2px rgba(15, 23, 42, 0.04),
    0 8px 32px rgba(16, 185, 129, 0.16);
}

/* ------- Spine node ------- */
.timeline-node {
  position: absolute;
  /* Dot sits on the spine: card's left edge is at `--card-gap` from the
     spine, so shift the dot left by that gap, then by half the node so
     the centre lands on the spine, plus 1px for the spine's 2px width. */
  left: calc(-1 * var(--card-gap) - var(--node-size) / 2 + 1px);
  /* Centre on the card vertically, regardless of how many lines the
     event text takes — single-line vs wrapped events used to make
     the dots sit visibly above centre. */
  top: 50%;
  transform: translateY(-50%);
  /* border-box keeps the rendered size at exactly --node-size; without
     it the 3px border pushes the visual circle 3px right of the spine. */
  box-sizing: border-box;
  width: var(--node-size);
  height: var(--node-size);
  border-radius: 50%;
  background: white;
  border: 3px solid #6366f1;
  z-index: 1;
}

.is-first .timeline-node {
  background: #a855f7;
  border-color: #a855f7;
  box-shadow: 0 0 0 3px rgba(168, 85, 247, 0.22);
}

.is-last .timeline-node {
  background: #10b981;
  border-color: #10b981;
  box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.22);
}

/* Subtle pulse on the last node so the "outcome" stands out without
   being noisy — keyframes are tiny so it doesn't overwhelm. */
.is-last .timeline-node-pulse {
  position: absolute;
  inset: -3px;
  border-radius: 50%;
  border: 2px solid rgba(16, 185, 129, 0.5);
  animation: timeline-pulse 2.4s ease-out infinite;
}

@keyframes timeline-pulse {
  0% {
    transform: scale(1);
    opacity: 0.7;
  }
  100% {
    transform: scale(1.9);
    opacity: 0;
  }
}

/* ------- Card header (date + offset) ------- */
.timeline-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 4px;
  flex-wrap: nowrap;
  min-width: 0;
}

.timeline-date {
  font-size: 13px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.01em;
  color: #4338ca;
  white-space: nowrap;
}

.is-first .timeline-date {
  color: #7e22ce;
}

.is-last .timeline-date {
  color: #047857;
}

.timeline-offset {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.06em;
  padding: 2px 9px;
  border-radius: 999px;
  background: rgba(99, 102, 241, 0.14);
  color: #4338ca;
  white-space: nowrap;
  flex: 0 0 auto;
}

.is-first .timeline-offset {
  background: rgba(168, 85, 247, 0.16);
  color: #7e22ce;
}

.is-last .timeline-offset {
  background: rgba(16, 185, 129, 0.18);
  color: #047857;
}

/* ------- Event text ------- */
.timeline-event-text {
  margin: 0;
  font-size: 15px;
  font-weight: 500;
  line-height: 1.55;
  color: #1e293b;
  word-break: break-word;
}

.is-last .timeline-event-text {
  font-weight: 600;
  color: #064e3b;
}

@media (max-width: 600px) {
  .timeline-display {
    --card-gap: 16px;
  }
  .timeline-event-card {
    padding: 12px 14px;
  }
  .timeline-event-text {
    font-size: 14px;
  }
}
</style>
