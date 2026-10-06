<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useAuthStore } from '../../stores/auth'
import { apiDocsApi } from '../../api/apiDocs'
import ApiCodeBlock from './ApiCodeBlock.vue'
import {
  operations,
  referencedSchemas,
  resolveSchema,
  schemaType,
} from './apiDocUtils'
const auth = useAuthStore()
const data = ref(null)
const loading = ref(false)
const error = ref('')
const tab = ref('guide')
const search = ref('')
const method = ref('')
const selected = ref('POST /api/activity/batches')
const origin = window.location.origin
let controller
let generation = 0
async function load() {
  controller?.abort()
  const current = ++generation
  data.value = null
  error.value = ''
  if (!auth.isAdmin) {
    loading.value = false
    return
  }
  controller = new AbortController()
  loading.value = true
  try {
    const response = await apiDocsApi.get(controller.signal)
    if (generation === current && auth.isAdmin) data.value = response
  } catch (err) {
    if (generation === current && !controller.signal.aborted)
      error.value =
        err.response?.status === 403
          ? '此頁面僅限管理員查看。'
          : 'API 文件載入失敗，請稍後重試。'
  } finally {
    if (generation === current) loading.value = false
  }
}
watch(() => auth.isAdmin, load, { immediate: true })
onBeforeUnmount(() => {
  ++generation
  controller?.abort()
})
const all = computed(() => operations(data.value?.openapi))
const filtered = computed(() => {
  const term = search.value.trim().toLowerCase()
  return all.value.filter(
    (op) =>
      (!method.value || op.method === method.value) &&
      `${op.key} ${op.summary || ''} ${op.tags?.join(' ') || ''} ${data.value.guide.endpoint_notes[op.key]?.description || ''}`
        .toLowerCase()
        .includes(term),
  )
})
const active = computed(
  () =>
    filtered.value.find((op) => op.key === selected.value) || filtered.value[0],
)
const note = computed(() => data.value?.guide.endpoint_notes[active.value?.key])
const bodyContent = computed(() =>
  Object.entries(active.value?.requestBody?.content || {}),
)
const models = computed(() =>
  active.value ? referencedSchemas(active.value, data.value.openapi) : {},
)
const pretty = (value) => JSON.stringify(value, null, 2)
const exampleCode = (code) => code.replaceAll('{{origin}}', origin)
function fields(schema) {
  const resolved = resolveSchema(schema, data.value.openapi)
  return Object.entries(resolved.properties || {}).map(([name, field]) => ({
    name,
    schema: field,
    required: resolved.required?.includes(name) || false,
  }))
}
function download() {
  const url = URL.createObjectURL(
    new Blob([pretty(data.value.openapi)], { type: 'application/json' }),
  )
  const link = document.createElement('a')
  link.href = url
  link.download = 'pyweb-openapi.json'
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
</script>
<template>
  <section v-if="auth.isAdmin" class="api-docs" :aria-busy="loading">
    <p v-if="loading" class="state" role="status">正在載入 API 文件…</p>
    <div v-else-if="error" class="state" role="alert">
      {{ error }} <button type="button" @click="load">重新載入</button>
    </div>
    <template v-else-if="data">
      <div class="intro">
        <div>
          <span class="eyebrow">DEVELOPER GUIDE</span>
          <h3>讓你的 Bot 與社群資料連線</h3>
          <p>從第一個 token 到批次同步，在這裡找到串接方式。</p>
        </div>
        <span class="admin-badge">管理員專用</span>
      </div>
      <div class="connection">
        <span>API BASE URL</span><code>{{ origin }}/api</code
        ><small
          >{{ all.length }} 個端點 · OpenAPI {{ data.openapi.openapi }}</small
        >
      </div>
      <nav class="docs-tabs" aria-label="API 文件分類">
        <button
          type="button"
          :aria-current="tab === 'guide' ? 'page' : undefined"
          @click="tab = 'guide'"
        >
          快速開始</button
        ><button
          type="button"
          :aria-current="tab === 'reference' ? 'page' : undefined"
          @click="tab = 'reference'"
        >
          API 參考 <small>{{ all.length }}</small></button
        ><button type="button" class="download" @click="download">
          下載 OpenAPI
        </button>
      </nav>
      <div v-if="tab === 'guide'" class="guide">
        <article v-for="section in data.guide.sections" :key="section.id">
          <h4>{{ section.title }}</h4>
          <p>{{ section.body }}</p>
          <ApiCodeBlock
            v-for="(snippet, index) in section.snippets"
            :key="index"
            :code="exampleCode(snippet.code)"
            :label="snippet.label"
            :language="snippet.language"
          />
        </article>
      </div>
      <div v-else class="reference">
        <p class="reference-note">
          此清單取自目前部署版本的 API 規格。Bot token 僅能呼叫標示 Bearer token
          的寫入端點；其他功能依各端點的
          session、角色與資源權限驗證。內部服務路徑不列入對外 API。
        </p>
        <div class="search">
          <input
            v-model="search"
            type="search"
            aria-label="搜尋 API"
            placeholder="搜尋路徑、功能或分類…"
          /><select v-model="method" aria-label="HTTP 方法">
            <option value="">所有方法</option>
            <option
              v-for="verb in [
                'GET',
                'POST',
                'PUT',
                'PATCH',
                'DELETE',
                'HEAD',
                'OPTIONS',
              ]"
              :key="verb"
            >
              {{ verb }}
            </option>
          </select>
        </div>
        <p class="result-count">{{ filtered.length }} 個符合的端點</p>
        <div class="endpoint-list" aria-label="API 端點">
          <button
            v-for="op in filtered"
            :key="op.key"
            type="button"
            :aria-pressed="active?.key === op.key"
            @click="selected = op.key"
          >
            <span class="method" :class="op.method.toLowerCase()">{{
              op.method
            }}</span
            ><code>{{ op.path }}</code
            ><span class="endpoint-summary">{{ op.summary }}</span>
          </button>
        </div>
        <p v-if="!filtered.length" class="state">
          找不到符合條件的 API，請調整搜尋文字或方法。
        </p>
        <article v-if="active" class="endpoint-detail">
          <div class="endpoint-title">
            <span class="method" :class="active.method.toLowerCase()">{{
              active.method
            }}</span>
            <h4>{{ active.path }}</h4>
          </div>
          <p class="auth-note">
            {{
              note?.auth ||
              (active.security?.some((s) => s.ActivityBotToken)
                ? 'Bot Bearer token'
                : '網站端點 · 依登入、角色與資源權限規則')
            }}
          </p>
          <p>{{ note?.description || active.description || active.summary }}</p>
          <h5>參數</h5>
          <div v-if="active.parameters.length" class="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>名稱／位置</th>
                  <th>格式</th>
                  <th>要求</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="param in active.parameters"
                  :key="`${param.in}:${param.name}`"
                >
                  <td>
                    <code>{{ param.name }}</code
                    ><small>{{ param.in }}</small>
                  </td>
                  <td>
                    {{ schemaType(param.schema)
                    }}<small v-if="param.description">{{
                      param.description
                    }}</small
                    ><small v-if="param.schema?.enum"
                      >可選：{{ param.schema.enum.join('、') }}</small
                    ><small v-if="param.schema?.default !== undefined"
                      >預設：{{ pretty(param.schema.default) }}</small
                    >
                  </td>
                  <td>{{ param.required ? '必填' : '選填' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p v-else class="empty">無路徑或 query 參數。</p>
          <h5>
            請求本體
            <small v-if="active.requestBody">{{
              active.requestBody.required ? '必填' : '選填'
            }}</small>
          </h5>
          <p v-if="!bodyContent.length" class="empty">不需要請求本體。</p>
          <div v-for="[contentType, content] in bodyContent" :key="contentType">
            <code class="content-type">{{ contentType }}</code>
            <div v-if="fields(content.schema).length" class="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>欄位</th>
                    <th>格式</th>
                    <th>要求</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="field in fields(content.schema)" :key="field.name">
                    <td>
                      <code>{{ field.name }}</code>
                    </td>
                    <td>
                      {{ schemaType(field.schema)
                      }}<small v-if="field.schema.description">{{
                        field.schema.description
                      }}</small>
                    </td>
                    <td>{{ field.required ? '必填' : '選填' }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
          <h5>回應</h5>
          <div class="responses">
            <div v-for="(response, status) in active.responses" :key="status">
              <strong>{{ status }}</strong
              ><span>{{ response.description }}</span
              ><code
                v-for="(content, contentType) in response.content"
                :key="contentType"
                >{{ schemaType(content.schema) }} · {{ contentType }}</code
              >
            </div>
          </div>
          <p class="reference-note">
            規格列出的回應之外，驗證或權限檢查可能回傳
            401／403，流量與本體限制可能回傳 429／413。詳細說明見「快速開始」。
          </p>
          <details>
            <summary>完整端點規格</summary>
            <ApiCodeBlock
              :code="pretty(active)"
              label="端點 OpenAPI"
              language="json"
            />
          </details>
          <details v-for="(schema, name) in models" :key="name">
            <summary>{{ name }} <small>資料結構與限制</small></summary>
            <ApiCodeBlock
              :code="pretty(schema)"
              :label="name"
              language="json"
            />
          </details>
        </article>
      </div>
    </template>
  </section>
  <p v-else role="alert">此頁面僅限管理員查看。</p>
</template>
<style scoped>
.api-docs {
  min-width: 0;
}
.intro {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
}
.eyebrow {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 1.7px;
  color: var(--brand-primary);
}
h3 {
  margin: 8px 0;
  font-size: 22px;
  letter-spacing: -0.5px;
  color: var(--ink-900);
}
p {
  font-size: 13px;
  color: var(--ink-500);
  line-height: 1.9;
}
.intro p {
  margin: 0;
}
.admin-badge {
  color: #7661c1;
  background: #f1edfb;
  padding: 6px 10px;
  border-radius: 20px;
  font-size: 10px;
  white-space: nowrap;
}
.connection {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  background: #f7f8fc;
  border: 1px solid #e8eaf4;
  border-radius: 12px;
  padding: 16px;
  margin: 24px 0;
}
.connection > span {
  font-size: 9px;
  letter-spacing: 1px;
  font-weight: 700;
  color: #9795ad;
}
.connection code {
  color: #5e5490;
  font-size: 12px;
  overflow-wrap: anywhere;
}
.connection small {
  font-size: 10px;
  color: #9294a6;
  margin-left: auto;
}
button {
  cursor: pointer;
  font: inherit;
}
.docs-tabs {
  display: flex;
  gap: 8px;
  border-bottom: 1px solid #e8eaf0;
  margin-bottom: 24px;
}
.docs-tabs button {
  border: 0;
  border-bottom: 2px solid transparent;
  background: none;
  padding: 12px 10px;
  font-size: 13px;
  color: #8c8b9f;
}
.docs-tabs button[aria-current] {
  color: var(--brand-primary);
  border-bottom-color: var(--brand-primary);
  font-weight: 600;
}
.docs-tabs small {
  border-radius: 5px;
  background: #f2f0fb;
  padding: 2px 5px;
  font-size: 10px;
}
.docs-tabs .download {
  margin-left: auto;
  font-size: 11px;
}
.guide article + article {
  margin-top: 32px;
  padding-top: 24px;
  border-top: 1px solid #edf0f5;
}
h4 {
  margin: 0 0 12px;
  color: var(--ink-700);
  font-size: 16px;
}
h5 {
  font-size: 13px;
  margin: 24px 0 12px;
  color: #6c6581;
}
h5 small,
summary small {
  font-size: 10px;
  color: #9690a5;
  margin-left: 8px;
  font-weight: 400;
}
.search {
  display: flex;
  gap: 10px;
}
.search input {
  flex: 1;
  min-width: 0;
}
.search input,
.search select {
  border: 1px solid #e2deed;
  padding: 11px;
  border-radius: 9px;
  color: #6c6581;
  background: white;
  font: inherit;
  font-size: 12px;
}
.result-count {
  font-size: 11px;
}
.endpoint-list {
  max-height: 300px;
  overflow-y: auto;
  border: 1px solid #e5e4ef;
  border-radius: 12px;
}
.endpoint-list button {
  width: 100%;
  display: flex;
  align-items: center;
  text-align: left;
  gap: 12px;
  padding: 12px;
  background: white;
  border: 0;
  border-bottom: 1px solid #f0eef5;
}
.endpoint-list button[aria-pressed='true'] {
  background: #f4f1fe;
}
.endpoint-list code {
  color: #6c6480;
  font-size: 11px;
  overflow-wrap: anywhere;
}
.endpoint-summary {
  font-size: 10px;
  color: #9b96a7;
  margin-left: auto;
  max-width: 32%;
}
.method {
  display: inline-block;
  min-width: 50px;
  text-align: center;
  padding: 4px 5px;
  border-radius: 5px;
  color: #74638c;
  background: #f2edf9;
  font-size: 9px;
  font-weight: 700;
  flex-shrink: 0;
}
.get {
  color: #4389b8;
  background: #eaf3fc;
}
.post {
  color: #329380;
  background: #e7f6f0;
}
.patch,
.put {
  color: #b1853b;
  background: #fcf3e3;
}
.delete {
  color: #c56c79;
  background: #fceef0;
}
.endpoint-detail {
  margin-top: 24px;
  border: 1px solid #e8e5f1;
  border-radius: 14px;
  padding: 20px;
  min-width: 0;
}
.endpoint-title {
  display: flex;
  gap: 10px;
  align-items: center;
}
.endpoint-title h4 {
  overflow-wrap: anywhere;
  margin: 0;
  font-family: monospace;
  font-size: 14px;
  min-width: 0;
}
.auth-note {
  font-size: 11px;
  color: #8c77b5;
}
.table-scroll {
  overflow-x: auto;
}
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 11px;
  text-align: left;
}
th {
  color: #9b95ab;
  background: #faf9fc;
  font-weight: 500;
}
th,
td {
  padding: 11px 9px;
  border-bottom: 1px solid #efedf4;
  vertical-align: top;
}
td {
  color: #716b80;
  overflow-wrap: anywhere;
}
td small {
  display: block;
  font-size: 10px;
  color: #a49daf;
  margin-top: 5px;
}
.content-type {
  font-size: 10px;
  color: #998cae;
  display: block;
  margin: 10px 0;
}
.empty,
.reference-note {
  color: #9991a5;
  font-size: 11px;
}
.responses > div {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  border-bottom: 1px solid #efedf4;
  padding: 12px 0;
  font-size: 11px;
  color: #9a91a5;
}
.responses strong {
  color: #766b89;
}
.responses code {
  font-size: 10px;
  overflow-wrap: anywhere;
}
details {
  border-top: 1px solid #ece8f1;
  margin-top: 12px;
  padding-top: 12px;
}
summary {
  font-size: 12px;
  color: #7c6e99;
  cursor: pointer;
  overflow-wrap: anywhere;
}
.state {
  text-align: center;
  padding: 40px 10px;
}
@media (max-width: 640px) {
  h3 {
    font-size: 18px;
  }
  .intro {
    flex-direction: column;
  }
  .connection {
    gap: 8px;
  }
  .connection small {
    margin-left: 0;
    width: 100%;
  }
  .docs-tabs {
    gap: 2px;
  }
  .docs-tabs button {
    padding: 10px 6px;
    font-size: 12px;
  }
  .endpoint-summary {
    display: none;
  }
  .endpoint-detail {
    padding: 14px 10px;
  }
}
</style>
