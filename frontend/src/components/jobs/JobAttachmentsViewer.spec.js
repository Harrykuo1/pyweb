import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

import { jobAttachmentsApi } from '../../api/jobAttachments'
import JobAttachmentsViewer from './JobAttachmentsViewer.vue'

// Fixtures exercise both happy-path (LibreOffice produced a preview PDF
// → preview_available true) and degraded-path (conversion failed →
// preview_available false, frontend must fall back to a plain download).
const ATTACHMENTS = [
  {
    id: 1,
    job_id: 7,
    filename: 'report.pdf',
    mime_type: 'application/pdf',
    size_bytes: 100,
    uploaded_at: '2026-05-01T00:00:00+00:00',
    preview_available: false,
  },
  {
    id: 2,
    job_id: 7,
    filename: 'screenshot.png',
    mime_type: 'image/png',
    size_bytes: 80,
    uploaded_at: '2026-05-02T00:00:00+00:00',
    preview_available: false,
  },
  {
    id: 3,
    job_id: 7,
    filename: 'slides.pptx',
    mime_type:
      'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    size_bytes: 200,
    uploaded_at: '2026-05-03T00:00:00+00:00',
    preview_available: true,
  },
  {
    id: 4,
    job_id: 7,
    filename: 'resume.docx',
    mime_type:
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    size_bytes: 150,
    uploaded_at: '2026-05-04T00:00:00+00:00',
    preview_available: true,
  },
  {
    id: 5,
    job_id: 7,
    filename: 'broken.pptx',
    mime_type:
      'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    size_bytes: 200,
    uploaded_at: '2026-05-05T00:00:00+00:00',
    // Conversion failed on the server, so this office file degrades to
    // a download link rather than crashing the viewer.
    preview_available: false,
  },
]

beforeEach(() => {})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('JobAttachmentsViewer.vue', () => {
  it('renders a list of attachment rows by default (no inline previews)', async () => {
    vi.spyOn(jobAttachmentsApi, 'list').mockResolvedValue(ATTACHMENTS)
    const wrapper = mount(JobAttachmentsViewer, { props: { jobId: 7 } })
    await flushPromises()

    for (const a of ATTACHMENTS) {
      expect(wrapper.find(`[data-test="viewer-item-${a.id}"]`).exists()).toBe(
        true,
      )
    }
    // Previews are only rendered after a row is clicked.
    expect(wrapper.find('[data-test="viewer-pdf-1"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="viewer-image-2"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="viewer-preview-pane"]').exists()).toBe(
      false,
    )
  })

  it('office files without a server-side preview degrade to download links', async () => {
    vi.spyOn(jobAttachmentsApi, 'list').mockResolvedValue(ATTACHMENTS)
    const wrapper = mount(JobAttachmentsViewer, { props: { jobId: 7 } })
    await flushPromises()

    // broken.pptx → preview_available=false, so download anchor.
    const brokenLink = wrapper.find('[data-test="viewer-download-5"]')
    expect(brokenLink.exists()).toBe(true)
    expect(brokenLink.attributes('download')).toBe('broken.pptx')

    // PDF, image, and successfully-converted office files expose the
    // "click to preview" anchor instead.
    expect(wrapper.find('[data-test="viewer-open-1"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="viewer-open-2"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="viewer-open-3"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="viewer-open-4"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="viewer-download-1"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="viewer-download-3"]').exists()).toBe(false)
  })

  it('previewable row click opens the inline preview pane (PDF)', async () => {
    vi.spyOn(jobAttachmentsApi, 'list').mockResolvedValue(ATTACHMENTS)
    const wrapper = mount(JobAttachmentsViewer, { props: { jobId: 7 } })
    await flushPromises()

    const link = wrapper.find('[data-test="viewer-open-1"]')
    expect(link.exists()).toBe(true)
    // The list anchor's href points at the binary so it would work as a
    // download fallback, but the click is hijacked to render inline.
    expect(link.attributes('href')).toBe('/api/jobs/7/attachments/1')
    expect(link.attributes('download')).toBeUndefined()

    await link.trigger('click')
    await flushPromises()

    const pane = wrapper.find('[data-test="viewer-preview-pane"]')
    expect(pane.exists()).toBe(true)
    const pdf = wrapper.find('[data-test="viewer-pdf-1"]')
    expect(pdf.exists()).toBe(true)
    expect(pdf.attributes('src')).toBe('/api/jobs/7/attachments/1')
    expect(pdf.attributes('type')).toBe('application/pdf')
    // Once the preview is open, the original list is hidden.
    expect(wrapper.find('[data-test="viewer-item-2"]').exists()).toBe(false)
  })

  it('previewable row click opens the inline preview pane (image)', async () => {
    vi.spyOn(jobAttachmentsApi, 'list').mockResolvedValue(ATTACHMENTS)
    const wrapper = mount(JobAttachmentsViewer, { props: { jobId: 7 } })
    await flushPromises()

    await wrapper.find('[data-test="viewer-open-2"]').trigger('click')
    await flushPromises()

    const img = wrapper.find('[data-test="viewer-image-2"]')
    expect(img.exists()).toBe(true)
    expect(img.attributes('src')).toBe('/api/jobs/7/attachments/2')
    expect(img.attributes('alt')).toBe('screenshot.png')
  })

  it('clicking the inline image opens the zoom viewer with sibling images', async () => {
    // Two image attachments so the modal viewer's url-list has more
    // than one entry — verifies we feed it the whole current-folder
    // image set, not just the clicked one.
    const list = [
      { ...ATTACHMENTS[1] }, // id 2, screenshot.png
      {
        id: 20,
        job_id: 7,
        filename: 'screenshot2.png',
        mime_type: 'image/png',
        size_bytes: 80,
        uploaded_at: '2026-05-02T00:00:00+00:00',
        preview_available: false,
      },
    ]
    vi.spyOn(jobAttachmentsApi, 'list').mockResolvedValue(list)
    const wrapper = mount(JobAttachmentsViewer, {
      props: { jobId: 7 },
      attachTo: document.body,
    })
    await flushPromises()

    await wrapper.find('[data-test="viewer-open-2"]').trigger('click')
    await flushPromises()
    expect(wrapper.vm.imageViewerOpen).toBe(false)

    await wrapper.find('[data-test="viewer-image-2"]').trigger('click')
    await flushPromises()

    expect(wrapper.vm.imageViewerOpen).toBe(true)
    expect(wrapper.vm.imageUrlsAtCurrentView).toEqual([
      '/api/jobs/7/attachments/2',
      '/api/jobs/7/attachments/20',
    ])
    expect(wrapper.vm.selectedImageIndex).toBe(0)
  })

  it('explicit 放大 button also opens the zoom viewer', async () => {
    vi.spyOn(jobAttachmentsApi, 'list').mockResolvedValue(ATTACHMENTS)
    const wrapper = mount(JobAttachmentsViewer, {
      props: { jobId: 7 },
      attachTo: document.body,
    })
    await flushPromises()
    await wrapper.find('[data-test="viewer-open-2"]').trigger('click')
    await flushPromises()

    await wrapper.find('[data-test="viewer-image-zoom"]').trigger('click')
    await flushPromises()
    expect(wrapper.vm.imageViewerOpen).toBe(true)
  })

  it('previewable office file (pptx) opens the inline preview pane against /preview', async () => {
    vi.spyOn(jobAttachmentsApi, 'list').mockResolvedValue(ATTACHMENTS)
    const wrapper = mount(JobAttachmentsViewer, { props: { jobId: 7 } })
    await flushPromises()

    await wrapper.find('[data-test="viewer-open-3"]').trigger('click')
    await flushPromises()

    const officeEmbed = wrapper.find('[data-test="viewer-office-3"]')
    expect(officeEmbed.exists()).toBe(true)
    expect(officeEmbed.attributes('src')).toBe(
      '/api/jobs/7/attachments/3/preview',
    )
    expect(officeEmbed.attributes('type')).toBe('application/pdf')
  })

  it('previewable office file (docx) opens the inline preview pane against /preview', async () => {
    vi.spyOn(jobAttachmentsApi, 'list').mockResolvedValue(ATTACHMENTS)
    const wrapper = mount(JobAttachmentsViewer, { props: { jobId: 7 } })
    await flushPromises()

    await wrapper.find('[data-test="viewer-open-4"]').trigger('click')
    await flushPromises()

    const officeEmbed = wrapper.find('[data-test="viewer-office-4"]')
    expect(officeEmbed.exists()).toBe(true)
    expect(officeEmbed.attributes('src')).toBe(
      '/api/jobs/7/attachments/4/preview',
    )
  })

  it('back button returns from the preview pane to the list', async () => {
    vi.spyOn(jobAttachmentsApi, 'list').mockResolvedValue(ATTACHMENTS)
    const wrapper = mount(JobAttachmentsViewer, { props: { jobId: 7 } })
    await flushPromises()

    await wrapper.find('[data-test="viewer-open-1"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-test="viewer-pdf-1"]').exists()).toBe(true)

    await wrapper.find('[data-test="viewer-back"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-test="viewer-preview-pane"]').exists()).toBe(
      false,
    )
    expect(wrapper.find('[data-test="viewer-item-1"]').exists()).toBe(true)
  })

  it('preview pane has a download link with the original filename', async () => {
    vi.spyOn(jobAttachmentsApi, 'list').mockResolvedValue(ATTACHMENTS)
    const wrapper = mount(JobAttachmentsViewer, { props: { jobId: 7 } })
    await flushPromises()

    await wrapper.find('[data-test="viewer-open-1"]').trigger('click')
    await flushPromises()

    const dl = wrapper.find('[data-test="viewer-preview-download"]')
    expect(dl.attributes('href')).toBe('/api/jobs/7/attachments/1')
    expect(dl.attributes('download')).toBe('report.pdf')
  })

  it('shows an empty state when there are no attachments', async () => {
    vi.spyOn(jobAttachmentsApi, 'list').mockResolvedValue([])
    const wrapper = mount(JobAttachmentsViewer, { props: { jobId: 7 } })
    await flushPromises()

    expect(wrapper.text()).toContain('尚無附件')
    expect(wrapper.find('[data-test="viewer-item-1"]').exists()).toBe(false)
  })

  it('shows an error banner when the API fails', async () => {
    vi.spyOn(jobAttachmentsApi, 'list').mockRejectedValue(new Error('boom'))
    const wrapper = mount(JobAttachmentsViewer, { props: { jobId: 7 } })
    await flushPromises()

    expect(wrapper.text()).toContain('載入附件失敗')
  })

  describe('folder-tree browsing', () => {
    const NESTED = [
      {
        id: 10,
        job_id: 7,
        filename: 'top-level.pdf',
        mime_type: 'application/pdf',
        size_bytes: 1,
        uploaded_at: '2026-05-01T00:00:00+00:00',
        preview_available: false,
      },
      {
        id: 11,
        job_id: 7,
        filename: 'src/foo.pdf',
        mime_type: 'application/pdf',
        size_bytes: 1,
        uploaded_at: '2026-05-01T00:00:00+00:00',
        preview_available: false,
      },
      {
        id: 12,
        job_id: 7,
        filename: 'src/components/Bar.png',
        mime_type: 'image/png',
        size_bytes: 1,
        uploaded_at: '2026-05-01T00:00:00+00:00',
        preview_available: false,
      },
      {
        id: 13,
        job_id: 7,
        filename: 'src/components/Baz.png',
        mime_type: 'image/png',
        size_bytes: 1,
        uploaded_at: '2026-05-01T00:00:00+00:00',
        preview_available: false,
      },
    ]

    it('root listing shows top-level files and folder folders only', async () => {
      vi.spyOn(jobAttachmentsApi, 'list').mockResolvedValue(NESTED)
      const wrapper = mount(JobAttachmentsViewer, { props: { jobId: 7 } })
      await flushPromises()

      // top-level.pdf is a file at root.
      expect(wrapper.find('[data-test="viewer-item-10"]').exists()).toBe(true)
      // src/ is the only folder visible from root.
      expect(wrapper.find('[data-test="viewer-folder-src"]').exists()).toBe(
        true,
      )
      // Files deeper than root must NOT appear at this level.
      expect(wrapper.find('[data-test="viewer-item-11"]').exists()).toBe(false)
      expect(wrapper.find('[data-test="viewer-item-12"]').exists()).toBe(false)
      // Folder count reflects every descendant file, not just direct children.
      expect(wrapper.find('[data-test="viewer-folder-src"]').text()).toContain(
        '3 個檔案',
      )
    })

    it('clicking a folder drills down and shows its contents', async () => {
      vi.spyOn(jobAttachmentsApi, 'list').mockResolvedValue(NESTED)
      const wrapper = mount(JobAttachmentsViewer, { props: { jobId: 7 } })
      await flushPromises()

      await wrapper.find('[data-test="viewer-folder-src"]').trigger('click')
      await flushPromises()

      // Now we're inside src/: foo.pdf is a direct child file, components
      // is the only subfolder visible.
      expect(wrapper.find('[data-test="viewer-item-11"]').exists()).toBe(true)
      expect(
        wrapper.find('[data-test="viewer-folder-components"]').exists(),
      ).toBe(true)
      // Root-level top-level.pdf must no longer appear.
      expect(wrapper.find('[data-test="viewer-item-10"]').exists()).toBe(false)
    })

    it('breadcrumb lets the user jump back to an ancestor path in one click', async () => {
      vi.spyOn(jobAttachmentsApi, 'list').mockResolvedValue(NESTED)
      const wrapper = mount(JobAttachmentsViewer, { props: { jobId: 7 } })
      await flushPromises()

      await wrapper.find('[data-test="viewer-folder-src"]').trigger('click')
      await flushPromises()
      await wrapper
        .find('[data-test="viewer-folder-components"]')
        .trigger('click')
      await flushPromises()

      // Now at src/components — file rows are the two PNGs.
      expect(wrapper.find('[data-test="viewer-item-12"]').exists()).toBe(true)
      expect(wrapper.find('[data-test="viewer-item-13"]').exists()).toBe(true)

      // Click the root breadcrumb to jump straight back.
      await wrapper.find('[data-test="breadcrumb-0"]').trigger('click')
      await flushPromises()

      expect(wrapper.find('[data-test="viewer-item-10"]').exists()).toBe(true)
      expect(wrapper.find('[data-test="viewer-folder-src"]').exists()).toBe(
        true,
      )
    })

    it('file row uses the basename within the current folder', async () => {
      vi.spyOn(jobAttachmentsApi, 'list').mockResolvedValue(NESTED)
      const wrapper = mount(JobAttachmentsViewer, { props: { jobId: 7 } })
      await flushPromises()

      await wrapper.find('[data-test="viewer-folder-src"]').trigger('click')
      await flushPromises()

      // foo.pdf, NOT src/foo.pdf — display name strips the current
      // path prefix so the row reads naturally.
      const row = wrapper.find('[data-test="viewer-item-11"]')
      expect(row.text()).toContain('foo.pdf')
      expect(row.text()).not.toContain('src/foo.pdf')
    })
  })

  describe('text / markdown preview', () => {
    const TEXTY = [
      {
        id: 30,
        job_id: 7,
        filename: 'NOTES.md',
        mime_type: 'text/markdown',
        size_bytes: 1024,
        uploaded_at: '2026-05-01T00:00:00+00:00',
        preview_available: false,
      },
      {
        id: 31,
        job_id: 7,
        filename: 'app.log',
        mime_type: 'text/plain',
        size_bytes: 2048,
        uploaded_at: '2026-05-01T00:00:00+00:00',
        preview_available: false,
      },
      {
        id: 32,
        job_id: 7,
        filename: 'huge.txt',
        // 3 MB, over the 2 MB inline-preview cap — must degrade to a
        // download link rather than try to render in the page.
        mime_type: 'text/plain',
        size_bytes: 3 * 1024 * 1024,
        uploaded_at: '2026-05-01T00:00:00+00:00',
        preview_available: false,
      },
    ]

    function mockFetchText(body) {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: true,
        text: vi.fn().mockResolvedValue(body),
      })
    }

    afterEach(() => {
      delete globalThis.fetch
    })

    it('text file (.log) under 2 MB renders inside a <pre> source block', async () => {
      vi.spyOn(jobAttachmentsApi, 'list').mockResolvedValue(TEXTY)
      mockFetchText('line one\nline two\n')

      const wrapper = mount(JobAttachmentsViewer, { props: { jobId: 7 } })
      await flushPromises()

      await wrapper.find('[data-test="viewer-open-31"]').trigger('click')
      await flushPromises()

      const src = wrapper.find('[data-test="viewer-text-source"]')
      expect(src.exists()).toBe(true)
      expect(src.text()).toContain('line one')
      expect(src.text()).toContain('line two')
      // Plain text never gets the source/render toggle.
      expect(wrapper.find('[data-test="viewer-text-toggle"]').exists()).toBe(
        false,
      )
    })

    it('markdown preview defaults to rendered view + offers source toggle', async () => {
      vi.spyOn(jobAttachmentsApi, 'list').mockResolvedValue(TEXTY)
      mockFetchText('# Hello\n\nbody text.')

      const wrapper = mount(JobAttachmentsViewer, { props: { jobId: 7 } })
      await flushPromises()
      await wrapper.find('[data-test="viewer-open-30"]').trigger('click')
      await flushPromises()

      // Rendered mode initially: MdPreview component is mounted.
      expect(wrapper.find('[data-test="viewer-text-rendered"]').exists()).toBe(
        true,
      )
      expect(wrapper.find('[data-test="viewer-text-source"]').exists()).toBe(
        false,
      )

      // Toggle button flips the view to raw source.
      await wrapper.find('[data-test="viewer-text-toggle"]').trigger('click')
      await flushPromises()
      expect(wrapper.find('[data-test="viewer-text-source"]').exists()).toBe(
        true,
      )
      expect(wrapper.find('[data-test="viewer-text-source"]').text()).toContain(
        '# Hello',
      )
    })

    it('files larger than 2 MB degrade to a download link instead of inline preview', async () => {
      vi.spyOn(jobAttachmentsApi, 'list').mockResolvedValue(TEXTY)

      const wrapper = mount(JobAttachmentsViewer, { props: { jobId: 7 } })
      await flushPromises()

      // huge.txt → over cap → "點擊下載" anchor, no preview hijack.
      expect(wrapper.find('[data-test="viewer-download-32"]').exists()).toBe(
        true,
      )
      expect(wrapper.find('[data-test="viewer-open-32"]').exists()).toBe(false)
    })

    it('shows an error banner when the text body fails to load', async () => {
      vi.spyOn(jobAttachmentsApi, 'list').mockResolvedValue(TEXTY)
      globalThis.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 })

      const wrapper = mount(JobAttachmentsViewer, { props: { jobId: 7 } })
      await flushPromises()
      await wrapper.find('[data-test="viewer-open-31"]').trigger('click')
      await flushPromises()

      expect(wrapper.find('[data-test="viewer-text-error"]').exists()).toBe(
        true,
      )
    })

    it('text/markdown preview offers the same fullscreen button as PDFs', async () => {
      vi.spyOn(jobAttachmentsApi, 'list').mockResolvedValue(TEXTY)
      mockFetchText('# heading')

      const wrapper = mount(JobAttachmentsViewer, { props: { jobId: 7 } })
      await flushPromises()
      await wrapper.find('[data-test="viewer-open-30"]').trigger('click')
      await flushPromises()

      // Fullscreen affordance applies to text/markdown too — long markdown
      // is exactly the case where 480px feels cramped, so the same toggle
      // that PDFs and images use should be available here.
      expect(wrapper.find('[data-test="viewer-fullscreen"]').exists()).toBe(
        true,
      )
    })

    it('back button clears the previously loaded text', async () => {
      vi.spyOn(jobAttachmentsApi, 'list').mockResolvedValue(TEXTY)
      mockFetchText('hello')

      const wrapper = mount(JobAttachmentsViewer, { props: { jobId: 7 } })
      await flushPromises()
      await wrapper.find('[data-test="viewer-open-31"]').trigger('click')
      await flushPromises()
      expect(wrapper.find('[data-test="viewer-text-source"]').text()).toContain(
        'hello',
      )

      await wrapper.find('[data-test="viewer-back"]').trigger('click')
      await flushPromises()

      // We're back at the list, and re-entering must not show stale text
      // — re-open should refetch.
      expect(wrapper.find('[data-test="viewer-text-source"]').exists()).toBe(
        false,
      )
    })
  })

  describe('fullscreen preview', () => {
    let requestFullscreenSpy
    let exitFullscreenSpy
    let fullscreenEl = null

    beforeEach(() => {
      requestFullscreenSpy = vi.fn(function () {
        fullscreenEl = this
        document.dispatchEvent(new Event('fullscreenchange'))
        return Promise.resolve()
      })
      exitFullscreenSpy = vi.fn(() => {
        fullscreenEl = null
        document.dispatchEvent(new Event('fullscreenchange'))
        return Promise.resolve()
      })
      // happy-dom doesn't ship requestFullscreen on Element, so seed it.
      HTMLElement.prototype.requestFullscreen = requestFullscreenSpy
      document.exitFullscreen = exitFullscreenSpy
      Object.defineProperty(document, 'fullscreenElement', {
        configurable: true,
        get: () => fullscreenEl,
      })
    })

    afterEach(() => {
      fullscreenEl = null
      delete HTMLElement.prototype.requestFullscreen
      delete document.exitFullscreen
      // Best-effort cleanup so subsequent tests don't see a leaked getter.
      try {
        delete document.fullscreenElement
      } catch {
        /* read-only on some envs; the new beforeEach will overwrite anyway */
      }
    })

    it('clicking 全螢幕 requests fullscreen on the preview surface', async () => {
      vi.spyOn(jobAttachmentsApi, 'list').mockResolvedValue(ATTACHMENTS)
      const wrapper = mount(JobAttachmentsViewer, {
        props: { jobId: 7 },
        attachTo: document.body,
      })
      await flushPromises()
      await wrapper.find('[data-test="viewer-open-1"]').trigger('click')
      await flushPromises()

      await wrapper.find('[data-test="viewer-fullscreen"]').trigger('click')
      await flushPromises()

      expect(requestFullscreenSpy).toHaveBeenCalledTimes(1)
      const surface = wrapper.find(
        '[data-test="viewer-preview-surface"]',
      ).element
      expect(requestFullscreenSpy.mock.instances[0]).toBe(surface)

      // After the fullscreenchange event, the button label flips.
      expect(wrapper.find('[data-test="viewer-fullscreen"]').text()).toContain(
        '退出全螢幕',
      )
    })

    it('clicking 退出全螢幕 calls document.exitFullscreen', async () => {
      vi.spyOn(jobAttachmentsApi, 'list').mockResolvedValue(ATTACHMENTS)
      const wrapper = mount(JobAttachmentsViewer, {
        props: { jobId: 7 },
        attachTo: document.body,
      })
      await flushPromises()
      await wrapper.find('[data-test="viewer-open-1"]').trigger('click')
      await flushPromises()

      // Enter fullscreen first.
      await wrapper.find('[data-test="viewer-fullscreen"]').trigger('click')
      await flushPromises()

      await wrapper.find('[data-test="viewer-fullscreen"]').trigger('click')
      await flushPromises()

      expect(exitFullscreenSpy).toHaveBeenCalledTimes(1)
      expect(wrapper.find('[data-test="viewer-fullscreen"]').text()).toContain(
        '全螢幕',
      )
      expect(
        wrapper.find('[data-test="viewer-fullscreen"]').text(),
      ).not.toContain('退出')
    })
  })
})
