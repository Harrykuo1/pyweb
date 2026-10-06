import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ApiDocsSection from './ApiDocsSection.vue'
import { apiDocsApi } from '../../api/apiDocs'
import { useAuthStore } from '../../stores/auth'
vi.mock('../../api/apiDocs', () => ({ apiDocsApi: { get: vi.fn() } }))
enableAutoUnmount(afterEach)
function payload() {
  return {
    guide: {
      sections: [
        {
          id: 'token',
          title: '建立 token',
          body: '使用 Docker',
          snippets: [
            {
              label: '建立',
              language: 'bash',
              code: 'docker compose exec backend python -m app.activity_tokens create --guild-id 123 --name bot\ncurl {{origin}}/api/activity/batches',
            },
          ],
        },
      ],
      endpoint_notes: {
        'POST /api/activity/batches': {
          auth: 'Bot Bearer token',
          description: '批次上傳訊息',
        },
      },
    },
    openapi: {
      openapi: '3.1.0',
      paths: {
        '/api/activity/batches': {
          post: {
            summary: 'Ingest',
            requestBody: {
              required: true,
              content: {
                'application/json': {
                  schema: { $ref: '#/components/schemas/Batch' },
                },
              },
            },
            responses: {
              200: {
                description: 'Success',
                content: { 'application/json': { schema: { type: 'object' } } },
              },
            },
          },
        },
        '/api/activity/options': {
          get: {
            summary: 'Options',
            parameters: [
              {
                in: 'query',
                name: 'user_ids',
                schema: { type: 'array', items: { type: 'string' } },
              },
            ],
            responses: { 200: { description: 'OK' } },
          },
        },
      },
      components: {
        schemas: {
          Batch: {
            type: 'object',
            required: ['guild_id'],
            properties: { guild_id: { type: 'string' } },
          },
        },
      },
    },
  }
}
async function render() {
  const w = mount(ApiDocsSection)
  await flushPromises()
  return w
}
beforeEach(() => {
  setActivePinia(createPinia())
  useAuthStore().user = { role: 'admin' }
  vi.clearAllMocks()
  apiDocsApi.get.mockResolvedValue(payload())
})
describe('admin API documentation', () => {
  it('renders a copyable guide using the current origin', async () => {
    const w = await render()
    expect(w.text()).toContain('docker compose exec backend')
    expect(w.text()).toContain(window.location.origin)
    expect(w.text()).not.toContain('{{origin}}')
    expect(w.text()).toContain('2 個端點')
  })
  it.each(['member', 'viewer', null])(
    'does not request or expose docs for %s',
    async (role) => {
      useAuthStore().user = role ? { role } : null
      const w = await render()
      expect(apiDocsApi.get).not.toHaveBeenCalled()
      expect(w.text()).toBe('此頁面僅限管理員查看。')
      expect(w.find('pre').exists()).toBe(false)
    },
  )
  it('removes docs when admin preview is enabled', async () => {
    const w = await render()
    useAuthStore().previewAsMember = true
    await flushPromises()
    expect(w.text()).not.toContain('docker compose exec')
    expect(w.find('pre').exists()).toBe(false)
  })
  it('searches and selects endpoints with schemas, auth and empty state', async () => {
    const w = await render()
    await w.findAll('.docs-tabs button')[1].trigger('click')
    expect(w.findAll('.endpoint-list button')).toHaveLength(2)
    expect(w.find('.endpoint-detail').text()).toContain('Bot Bearer token')
    expect(w.find('.endpoint-detail').text()).toContain('guild_id')
    expect(w.find('.endpoint-detail').text()).toContain('必填')
    await w.find('input').setValue('options')
    expect(w.findAll('.endpoint-list button')).toHaveLength(1)
    expect(w.find('.endpoint-detail').text()).toContain('user_ids')
    await w.find('select').setValue('POST')
    expect(w.text()).toContain('找不到符合條件的 API')
    await w.find('input').setValue('批次')
    expect(w.findAll('.endpoint-list button')).toHaveLength(1)
  })
  it('retries errors and aborts when unmounted', async () => {
    apiDocsApi.get.mockRejectedValueOnce(new Error('offline'))
    const w = await render()
    expect(w.find('[role="alert"]').exists()).toBe(true)
    await w.find('[role="alert"] button').trigger('click')
    await flushPromises()
    expect(w.find('.intro').exists()).toBe(true)
    const signal = apiDocsApi.get.mock.lastCall[0]
    w.unmount()
    expect(signal.aborted).toBe(true)
  })
  it('does not reveal a delayed response after permission changes', async () => {
    let resolve
    apiDocsApi.get.mockImplementation(
      () =>
        new Promise((r) => {
          resolve = r
        }),
    )
    const w = await render()
    useAuthStore().user = { role: 'member' }
    await flushPromises()
    resolve(payload())
    await flushPromises()
    expect(w.find('pre').exists()).toBe(false)
  })
})
