<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElIcon } from 'element-plus'
import { Picture, SetUp, User } from '@element-plus/icons-vue'

import AccountSection from '../components/settings/AccountSection.vue'
import AppearanceSection from '../components/settings/AppearanceSection.vue'
import SettingsSidebar from '../components/settings/SettingsSidebar.vue'
import SystemLimitsSection from '../components/settings/SystemLimitsSection.vue'

// Section registry — order here is the order shown in the sidebar.
// Each entry advertises its key (used for URL hash + active state),
// label, short description, and the icon component for the rail.
const SECTIONS = [
  {
    key: 'account',
    label: '帳號管理',
    description: '管理員與檢視者帳號',
    icon: User,
  },
  {
    key: 'appearance',
    label: '網站外觀',
    description: '登入頁 Logo',
    icon: Picture,
  },
  {
    key: 'system',
    label: '系統參數',
    description: '附件數量與大小',
    icon: SetUp,
  },
]

const VALID_KEYS = new Set(SECTIONS.map((s) => s.key))
const DEFAULT_KEY = SECTIONS[0].key

const route = useRoute()
const router = useRouter()

function keyFromHash(hash) {
  if (!hash) return DEFAULT_KEY
  const stripped = hash.replace(/^#/, '')
  return VALID_KEYS.has(stripped) ? stripped : DEFAULT_KEY
}

const active = ref(keyFromHash(route.hash))

onMounted(() => {
  // If the URL has no hash (or an unknown one), normalize it so deep-links
  // round-trip cleanly. replace (not push) avoids polluting browser history.
  if (`#${active.value}` !== route.hash) {
    router.replace({ hash: `#${active.value}` })
  }
})

watch(
  () => route.hash,
  (next) => {
    active.value = keyFromHash(next)
  },
)

watch(active, (next) => {
  if (`#${next}` !== route.hash) {
    router.replace({ hash: `#${next}` })
  }
})

const activeSection = computed(
  () => SECTIONS.find((s) => s.key === active.value) ?? SECTIONS[0],
)
</script>

<template>
  <section class="settings-page">
    <header class="settings-page__header">
      <div class="settings-page__title-row">
        <h1 class="settings-page__title">設定</h1>
        <span class="settings-page__accent" aria-hidden="true"></span>
      </div>
      <p class="settings-page__subtitle">管理帳號、外觀與系統參數</p>
    </header>

    <div class="settings-page__body">
      <SettingsSidebar v-model="active" :items="SECTIONS" />

      <main
        class="settings-page__content"
        :data-test="`settings-active-${active}`"
      >
        <header class="settings-section__header">
          <span class="settings-section__icon" aria-hidden="true">
            <el-icon :size="22">
              <component :is="activeSection.icon" />
            </el-icon>
          </span>
          <div class="settings-section__heading">
            <h2>{{ activeSection.label }}</h2>
            <p v-if="activeSection.description">
              {{ activeSection.description }}
            </p>
          </div>
        </header>

        <div class="settings-section__body">
          <AccountSection v-if="active === 'account'" />
          <AppearanceSection v-else-if="active === 'appearance'" />
          <SystemLimitsSection v-else-if="active === 'system'" />
        </div>
      </main>
    </div>
  </section>
</template>

<style scoped>
.settings-page {
  max-width: 1080px;
  margin: 0 auto;
}

/* ---------- Page header ---------- */
.settings-page__header {
  margin-bottom: 28px;
}

.settings-page__title-row {
  display: flex;
  align-items: center;
  gap: 16px;
}

.settings-page__title {
  margin: 0;
  font-size: 28px;
  font-weight: 700;
  letter-spacing: -0.02em;
  background: linear-gradient(
    135deg,
    var(--brand-primary) 0%,
    var(--brand-accent) 100%
  );
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}

.settings-page__accent {
  flex: 1;
  height: 1px;
  background: linear-gradient(
    90deg,
    rgba(99, 102, 241, 0.3) 0%,
    rgba(99, 102, 241, 0) 100%
  );
}

.settings-page__subtitle {
  margin: 10px 0 0;
  color: var(--ink-500);
  font-size: 14px;
  letter-spacing: 0.01em;
}

/* ---------- Body ---------- */
.settings-page__body {
  display: grid;
  grid-template-columns: 240px minmax(0, 1fr);
  gap: 24px;
  align-items: start;
}

.settings-page__content {
  background: var(--surface-0);
  border: 1px solid rgba(15, 23, 42, 0.06);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-md);
  padding: 28px 32px;
  min-height: 420px;
}

/* ---------- Section header ---------- */
.settings-section__header {
  display: flex;
  align-items: center;
  gap: 14px;
  margin: 0 0 24px;
  padding-bottom: 20px;
  border-bottom: 1px solid rgba(15, 23, 42, 0.06);
}

.settings-section__icon {
  width: 44px;
  height: 44px;
  border-radius: var(--radius-md);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #ffffff;
  background: linear-gradient(
    135deg,
    var(--brand-primary),
    var(--brand-accent)
  );
  box-shadow: 0 6px 16px rgba(99, 102, 241, 0.28);
  flex: 0 0 auto;
}

.settings-section__heading {
  min-width: 0;
}

.settings-section__heading h2 {
  margin: 0 0 4px;
  font-size: 20px;
  font-weight: 700;
  letter-spacing: -0.01em;
}

.settings-section__heading p {
  margin: 0;
  color: var(--ink-500);
  font-size: 13px;
}

.settings-section__body {
  /* Sections control their own internal layout; this just contains them. */
  min-height: 280px;
}

@media (max-width: 900px) {
  .settings-page__body {
    grid-template-columns: minmax(0, 1fr);
  }

  .settings-page__content {
    padding: 22px 20px;
  }
}

@media (max-width: 640px) {
  .settings-page__title {
    font-size: 24px;
  }

  .settings-section__icon {
    width: 38px;
    height: 38px;
  }
}
</style>
