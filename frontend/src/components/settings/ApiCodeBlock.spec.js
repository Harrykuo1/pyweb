import { afterEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, mount } from '@vue/test-utils'
import ApiCodeBlock from './ApiCodeBlock.vue'
enableAutoUnmount(afterEach)
afterEach(() => vi.unstubAllGlobals())
describe('API code examples', () => {
  it('copies the exact code and renders markup as text', async () => {
    const writeText = vi.fn().mockResolvedValue()
    vi.stubGlobal('navigator', { clipboard: { writeText } })
    const w = mount(ApiCodeBlock, {
      props: { code: '<script>bad()</script>\nnext' },
    })
    expect(w.find('script').exists()).toBe(false)
    await w.find('button').trigger('click')
    expect(writeText).toHaveBeenCalledWith('<script>bad()</script>\nnext')
    expect(w.text()).toContain('已複製')
  })
  it('supports clipboard fallback for plain HTTP deployments', async () => {
    vi.stubGlobal('navigator', {})
    const copy = vi.fn().mockReturnValue(true)
    const original = document.execCommand
    document.execCommand = copy
    try {
      const w = mount(ApiCodeBlock, { props: { code: 'docker exec' } })
      await w.find('button').trigger('click')
      expect(copy).toHaveBeenCalledWith('copy')
      expect(document.querySelector('textarea')).toBeNull()
      expect(w.text()).toContain('已複製')
    } finally {
      document.execCommand = original
    }
  })
  it('shows a useful message when copying is unavailable', async () => {
    vi.stubGlobal('navigator', {
      clipboard: { writeText: vi.fn().mockRejectedValue(new Error('denied')) },
    })
    const w = mount(ApiCodeBlock, { props: { code: 'sample' } })
    await w.find('button').trigger('click')
    expect(w.text()).toContain('請選取下方文字')
  })
})
