import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus, { ElMessage } from 'element-plus'
import 'element-plus/dist/index.css'

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
  (error) => handleAuthResponseError(error, { auth, router, message: ElMessage }),
)

app.mount('#app')
