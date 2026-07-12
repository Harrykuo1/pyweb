import { describe, it, expect } from 'vitest'
import { sanitizeHtml } from './sanitizeHtml'

// The resume / job experience / event description previews render
// user-supplied Markdown as HTML through md-editor-v3. Without sanitizing
// that HTML, stored markup executes JavaScript in the viewer's session
// (stored XSS). sanitizeHtml is the shared guard wired into every preview
// surface via md-editor-v3's `sanitize` prop.
describe('sanitizeHtml', () => {
  it('strips <script> tags', () => {
    const out = sanitizeHtml('<p>hi</p><script>window.__x = 1</script>')
    expect(out).not.toMatch(/<script/i)
    expect(out).not.toContain('window.__x')
  })

  it('strips inline event handlers (onerror/ontoggle/onclick)', () => {
    const out = sanitizeHtml(
      '<img src=1 onerror="window.__x=1">' +
        '<details open ontoggle="window.__y=1">d</details>' +
        '<b onclick="window.__z=1">b</b>',
    )
    expect(out).not.toMatch(/onerror/i)
    expect(out).not.toMatch(/ontoggle/i)
    expect(out).not.toMatch(/onclick/i)
  })

  it('strips <iframe> (including srcdoc)', () => {
    const out = sanitizeHtml(
      '<iframe srcdoc="<script>alert(1)</script>"></iframe>',
    )
    expect(out).not.toMatch(/<iframe/i)
    expect(out).not.toMatch(/srcdoc/i)
  })

  it('neutralizes javascript: URLs in links', () => {
    const out = sanitizeHtml('<a href="javascript:window.__x=1">click</a>')
    expect(out).not.toMatch(/javascript:/i)
  })

  it('preserves safe formatting (bold, headings, lists, http links)', () => {
    const out = sanitizeHtml(
      '<h1>Title</h1><p><strong>bold</strong></p>' +
        '<ul><li>item</li></ul>' +
        '<a href="https://example.com">link</a>',
    )
    expect(out).toMatch(/<h1[^>]*>Title<\/h1>/i)
    expect(out).toMatch(/<strong>bold<\/strong>/i)
    expect(out).toMatch(/<li>item<\/li>/i)
    expect(out).toContain('href="https://example.com"')
  })

  it('coerces non-string input to an empty string', () => {
    expect(sanitizeHtml(null)).toBe('')
    expect(sanitizeHtml(undefined)).toBe('')
  })
})
