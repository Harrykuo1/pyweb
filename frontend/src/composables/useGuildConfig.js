import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { authApi } from '../api/auth'
import { extractError } from '../utils/apiError'

// Discord guild ids are snowflakes — 17-20 digit integers. The OAuth login
// flow rejects users who aren't members of this guild, so an admin needs to
// be able to view and set it. Logic lives here; GuildConfigSection is
// presentation only.
const SNOWFLAKE = /^\d{17,20}$/

export function useGuildConfig() {
  const loading = ref(false)
  const saving = ref(false)
  const guildId = ref('')
  const original = ref('')

  async function load() {
    loading.value = true
    try {
      const cfg = await authApi.getGuildConfig()
      guildId.value = cfg.guild_id || ''
      original.value = guildId.value
    } catch {
      ElMessage.error('載入 Discord 群組設定失敗')
    } finally {
      loading.value = false
    }
  }

  const dirty = computed(() => guildId.value !== original.value)
  const valid = computed(() => SNOWFLAKE.test(guildId.value))

  async function save() {
    if (!valid.value) return ElMessage.error('群組 ID 必須是 17–20 位數字')
    saving.value = true
    try {
      const cfg = await authApi.setGuildConfig(guildId.value.trim())
      guildId.value = cfg.guild_id
      original.value = cfg.guild_id
      ElMessage.success('已更新 Discord 群組')
    } catch (err) {
      ElMessage.error(extractError(err, '儲存失敗，請稍後再試'))
    } finally {
      saving.value = false
    }
  }

  function reset() {
    guildId.value = original.value
  }

  onMounted(load)

  return { loading, saving, guildId, dirty, valid, load, save, reset }
}
