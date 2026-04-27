<script setup>
import { RouterView } from 'vue-router'

import Navbar from '../components/Navbar.vue'
</script>

<template>
  <div class="auth-layout">
    <Navbar />
    <main class="content">
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.auth-layout {
  min-height: 100vh;
  background: #f5f7fa;
}

.content {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
}

@media (max-width: 640px) {
  .content {
    padding: 12px;
  }
}
</style>
