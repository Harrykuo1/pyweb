<script setup>
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
</script>

<template>
  <div class="home-page">
    <h2 class="welcome">歡迎，{{ auth.user?.username }}</h2>
    <p class="tagline">後續會在這裡放成員列表與實習紀錄入口。</p>
  </div>
</template>

<style scoped>
.home-page {
  padding: 8px 0;
}

.welcome {
  margin: 0 0 8px;
  font-size: 24px;
  color: #303133;
}

.tagline {
  color: #909399;
  margin: 0;
}
</style>
