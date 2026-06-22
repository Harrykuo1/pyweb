<script setup></script>

<template>
  <div class="skeleton-card">
    <div class="skel-stripe shimmer"></div>
    <div class="skel-tag shimmer"></div>
    <div class="skel-line skel-line--title shimmer"></div>
    <div class="skel-line skel-line--sub shimmer"></div>
    <div class="skel-divider"></div>
    <div class="skel-line skel-line--meta shimmer"></div>
  </div>
</template>

<style scoped>
/* Mirrors the JobRecordCard shell (padding/border/radius) so the loading
   grid keeps the same footprint, but is self-contained — it does not
   borrow the .record-card base from the real card. */
.skeleton-card {
  position: relative;
  overflow: hidden;
  background: var(--surface-0);
  border: 1px solid rgba(15, 23, 42, 0.06);
  border-radius: var(--radius-lg);
  padding: 20px 20px 18px 26px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  pointer-events: none;
}

.skel-stripe {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 4px;
  background: rgba(15, 23, 42, 0.08);
}

.skel-tag {
  width: 56px;
  height: 18px;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.08);
}

.skel-line {
  height: 12px;
  background: rgba(15, 23, 42, 0.06);
  border-radius: 4px;
}

.skel-line--title {
  width: 70%;
  height: 16px;
}

.skel-line--sub {
  width: 50%;
}

.skel-line--meta {
  width: 80%;
  height: 10px;
}

.skel-divider {
  height: 1px;
  background: rgba(15, 23, 42, 0.06);
  margin-top: 4px;
}

.shimmer {
  position: relative;
  overflow: hidden;
}

.shimmer::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(
    90deg,
    transparent 0%,
    rgba(255, 255, 255, 0.55) 50%,
    transparent 100%
  );
  transform: translateX(-100%);
  animation: shimmer-sweep 1.5s ease-in-out infinite;
}

@keyframes shimmer-sweep {
  0% {
    transform: translateX(-100%);
  }
  100% {
    transform: translateX(100%);
  }
}

@media (max-width: 640px) {
  .skeleton-card {
    padding: 16px 16px 14px 20px;
  }
}
</style>
