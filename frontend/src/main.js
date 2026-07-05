import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus, { ElMessage } from 'element-plus'
import 'element-plus/dist/index.css'
import { config as configMdEditor } from 'md-editor-v3'

import '@fontsource/inter/400.css'
import '@fontsource/inter/500.css'
import '@fontsource/inter/600.css'
import '@fontsource/inter/700.css'
import '@fontsource/noto-sans-tc/400.css'
import '@fontsource/noto-sans-tc/500.css'
import '@fontsource/noto-sans-tc/700.css'

import './style.css'
import App from './App.vue'
import router from './router'
import client, { handleAuthResponseError } from './api/client'
import { useAuthStore } from './stores/auth'

// Force every <a> rendered through md-editor-v3's MdPreview / editor
// preview pane to open in a new tab. Both reading paths (resume,
// experience, legacy timeline_md) link out to external resources
// (LinkedIn, company sites, etc.) and yanking the user out of the
// SPA to follow them is hostile UX. rel="noopener noreferrer" is
// the standard companion for new-tab links to prevent the opened
// page from referencing window.opener.
configMdEditor({
  markdownItConfig(md) {
    const defaultLinkOpen =
      md.renderer.rules.link_open ||
      ((tokens, idx, options, _env, self) =>
        self.renderToken(tokens, idx, options))
    md.renderer.rules.link_open = (tokens, idx, options, env, self) => {
      tokens[idx].attrSet('target', '_blank')
      tokens[idx].attrSet('rel', 'noopener noreferrer')
      return defaultLinkOpen(tokens, idx, options, env, self)
    }
  },
})

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(ElementPlus)

// Wire the 401 interceptor here — after pinia is installed (so the
// auth store is reachable) and after router is set up, but before
// mount so no API call is made before the handler is in place.
const auth = useAuthStore()
client.interceptors.response.use(
  (response) => response,
  (error) =>
    handleAuthResponseError(error, { auth, router, message: ElMessage }),
)

app.mount('#app')
