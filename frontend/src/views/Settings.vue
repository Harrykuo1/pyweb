<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElIcon } from 'element-plus'
import { Avatar, SetUp, User } from '@element-plus/icons-vue'

import AccountSection from '../components/settings/AccountSection.vue'
import AppearanceSection from '../components/settings/AppearanceSection.vue'
import GuildConfigSection from '../components/settings/GuildConfigSection.vue'
import InvitesSection from '../components/settings/InvitesSection.vue'
import MemberRoster from '../components/settings/MemberRoster.vue'
import PendingLinksSection from '../components/settings/PendingLinksSection.vue'
import SettingsSidebar from '../components/settings/SettingsSidebar.vue'
import SettingsSubTabs from '../components/settings/SettingsSubTabs.vue'
import SystemLimitsSection from '../components/settings/SystemLimitsSection.vue'
import { authApi } from '../api/auth'

// Two-level navigation: the sidebar lists three top-level GROUPS; each group
// opens a sub-tab bar of leaf sections. The leaf key is the single source of
// truth synced to the URL hash — a hash resolves to (group, sub).
const GROUPS = [
  {
    key: 'members',
    label: '成員與帳號',
    description: '成員名冊、邀請連結與待連結帳號',
    icon: Avatar,
    subs: [
      { key: 'roles', label: '成員名冊', component: MemberRoster },
      { key: 'invites', label: '邀請連結', component: InvitesSection },
      { key: 'pending-links', label: '待連結', component: PendingLinksSection },
    ],
  },
  {
    key: 'site',
    label: '網站設定',
    description: 'Discord 群組、登入頁外觀與上傳限制',
    icon: SetUp,
    subs: [
      { key: 'discord', label: 'Discord 群組', component: GuildConfigSection },
      { key: 'appearance', label: '登入頁外觀', component: AppearanceSection },
      // 'system' was one tab holding only job keys despite the name. It stays
      // as the jobs tab's key so existing bookmarks and links still resolve.
      {
        key: 'system',
        label: '求職參數',
        component: SystemLimitsSection,
        props: { group: 'job' },
      },
      {
        key: 'event-limits',
        label: '活動參數',
        component: SystemLimitsSection,
        props: { group: 'event' },
      },
    ],
  },
  {
    key: 'account',
    label: '我的帳號',
    description: '更新使用者名稱與密碼',
    icon: User,
    subs: [{ key: 'account', label: '我的帳號', component: AccountSection }],
  },
]

// Flatten to leaves, each tagged with its owning group for reverse lookup.
const ALL_SUBS = GROUPS.flatMap((g) => g.subs.map((s) => ({ ...s, group: g })))
const SUB_KEYS = new Set(ALL_SUBS.map((s) => s.key))
const DEFAULT_SUB = 'roles'

const route = useRoute()
const router = useRouter()

function keyFromHash(hash) {
  if (!hash) return DEFAULT_SUB
  const stripped = hash.replace(/^#/, '')
  return SUB_KEYS.has(stripped) ? stripped : DEFAULT_SUB
}

// `active` is the leaf key (source of truth); it drives the group derivation.
const active = ref(keyFromHash(route.hash))

const activeSub = computed(
  () => ALL_SUBS.find((s) => s.key === active.value) ?? ALL_SUBS[0],
)
const activeGroup = computed(() => activeSub.value.group)
const activeComponent = computed(() => activeSub.value.component)
// SystemLimitsSection is mounted twice, once per config group, so the
// leaf definition carries the props that tell the two apart.
const activeProps = computed(() => activeSub.value.props ?? {})

// Bridge the sidebar (which selects a GROUP) to the leaf source of truth:
// selecting a group lands on that group's first sub.
const activeGroupKey = computed({
  get: () => activeGroup.value.key,
  set: (gk) => {
    const group = GROUPS.find((g) => g.key === gk)
    if (group) active.value = group.subs[0].key
  },
})

// The roster's 產生邀請連結 button jumps to the invites sub-tab within the
// members group. Harmless on other leaves, which never emit generate-invite.
function goToInvites() {
  active.value = 'invites'
}

const pendingCount = ref(0)

function refreshPendingCount() {
  authApi
    .listPendingLinks()
    .then((links) => {
      pendingCount.value = links.length
    })
    .catch(() => {
      pendingCount.value = 0
    })
}

const subTabItems = computed(() =>
  activeGroup.value.subs.map((s) => ({
    key: s.key,
    label: s.label,
    badge: s.key === 'pending-links' ? pendingCount.value : undefined,
  })),
)

// Refresh the badge on mount and whenever the members group is (re-)entered,
// including sub switches within it. Never read it from the unmounted section.
watch(
  active,
  () => {
    if (activeGroup.value.key === 'members') refreshPendingCount()
  },
  { immediate: true },
)

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
      <SettingsSidebar v-model="activeGroupKey" :items="GROUPS" />

      <main
        class="settings-page__content"
        :data-test="`settings-active-${activeGroup.key}`"
      >
        <header class="settings-section__header">
          <span class="settings-section__icon" aria-hidden="true">
            <el-icon :size="22">
              <component :is="activeGroup.icon" />
            </el-icon>
          </span>
          <div class="settings-section__heading">
            <h2>{{ activeGroup.label }}</h2>
            <p v-if="activeGroup.description">
              {{ activeGroup.description }}
            </p>
          </div>
        </header>

        <SettingsSubTabs
          v-if="activeGroup.subs.length > 1"
          v-model="active"
          :items="subTabItems"
        />

        <div
          class="settings-section__body"
          :data-test="`settings-active-sub-${active}`"
        >
          <!-- Keyed by the leaf, not just the component: 求職參數 and
               活動參數 are the same component with different props, so
               without this Vue reuses the instance and the composable keeps
               whichever group it was given at setup. -->
          <component
            :is="activeComponent"
            :key="active"
            v-bind="activeProps"
            @generate-invite="goToInvites"
          />
        </div>
      </main>
    </div>
  </section>
</template>

<style scoped>
.settings-page {
  /* Wide enough that the member roster's table fits without a horizontal
     scroll at desktop widths; the sidebar takes 240 of it. */
  max-width: 1240px;
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
