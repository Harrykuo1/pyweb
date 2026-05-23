import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { ElMessage, ElMessageBox } from 'element-plus'

import { jobAttachmentsApi } from '../api/jobAttachments'
import { settingsApi } from '../api/settings'
import JobAttachmentsManager from './JobAttachmentsManager.vue'
import AttachmentConflictDialog from './AttachmentConflictDialog.vue'
import DeleteWithPasswordDialog from './DeleteWithPasswordDialog.vue'

const SAMPLE_CONFIG = {
  fields: [
    { key: 'max_attachments_per_job', value: 5, type: 'int' },
    { key: 'max_attachment_mb', value: 20, type: 'int' },
  ],
}

const SAMPLE_LIST = [
  {
    id: 1,
    job_id: 7,
    filename: 'report.pdf',
    mime_type: 'application/pdf',
    size_bytes: 1024,
    uploaded_at: '2026-05-01T00:00:00+00:00',
  },
]

beforeEach(() => {
  vi.spyOn(settingsApi, 'getConfig').mockResolvedValue(SAMPLE_CONFIG)
  vi.spyOn(jobAttachmentsApi, 'list').mockResolvedValue([...SAMPLE_LIST])
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('JobAttachmentsManager.vue', () => {
  it('renders existing attachments and the configured count cap', async () => {
    const wrapper = mount(JobAttachmentsManager, { props: { jobId: 7 } })
    await flushPromises()

    expect(wrapper.find('[data-test="attachment-row-1"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="attachment-counter"]').text()).toContain('1')
    expect(wrapper.find('[data-test="attachment-counter"]').text()).toContain('5')
  })

  it('shows an upload-status banner while a batch is in flight', async () => {
    let releaseUpload
    vi.spyOn(jobAttachmentsApi, 'upload').mockImplementation(
      () => new Promise((resolve) => {
        releaseUpload = () => resolve({
          id: 2,
          job_id: 7,
          filename: 'deck.pptx',
          mime_type: 'application/pptx',
          size_bytes: 100,
          uploaded_at: '2026-05-02T00:00:00+00:00',
          preview_available: false,
        })
      }),
    )

    const wrapper = mount(JobAttachmentsManager, { props: { jobId: 7 } })
    await flushPromises()

    const file = new File([new Uint8Array([1])], 'deck.pptx', {
      type: 'application/pptx',
    })
    wrapper.vm.handleFileSelected({ raw: file })
    await flushPromises()

    const banner = wrapper.find('[data-test="upload-status"]')
    expect(banner.exists()).toBe(true)
    expect(banner.text()).toContain('deck.pptx')
    expect(banner.text()).toContain('Office 檔案')

    releaseUpload()
    await flushPromises()

    expect(wrapper.find('[data-test="upload-status"]').exists()).toBe(false)
  })

  it('uploads a new file with no conflict_strategy when name is unique', async () => {
    const upload = vi.spyOn(jobAttachmentsApi, 'upload').mockResolvedValue({
      id: 2,
      job_id: 7,
      filename: 'new.pdf',
      mime_type: 'application/pdf',
      size_bytes: 100,
      uploaded_at: '2026-05-02T00:00:00+00:00',
    })

    const wrapper = mount(JobAttachmentsManager, { props: { jobId: 7 } })
    await flushPromises()

    const file = new File([new Uint8Array([1])], 'new.pdf', { type: 'application/pdf' })
    wrapper.vm.handleFileSelected({ raw: file })
    await flushPromises()

    expect(upload).toHaveBeenCalledWith(7, file, null, file.name)
    expect(wrapper.vm.attachments.some((a) => a.id === 2)).toBe(true)
  })

  it('opens the conflict dialog when a name collides, then uploads with the chosen strategy', async () => {
    const upload = vi.spyOn(jobAttachmentsApi, 'upload').mockResolvedValue({
      id: 3,
      job_id: 7,
      filename: 'report.pdf',
      mime_type: 'application/pdf',
      size_bytes: 200,
      uploaded_at: '2026-05-03T00:00:00+00:00',
    })

    const wrapper = mount(JobAttachmentsManager, { props: { jobId: 7 } })
    await flushPromises()

    const file = new File([new Uint8Array([1])], 'report.pdf', { type: 'application/pdf' })
    wrapper.vm.handleFileSelected({ raw: file })
    // Microtask resolves so processBatch runs, then the dialog opens.
    await flushPromises()

    expect(wrapper.vm.conflictDialogOpen).toBe(true)
    const dialog = wrapper.findComponent(AttachmentConflictDialog)
    dialog.vm.$emit('resolved', { 'report.pdf': 'overwrite' })
    await flushPromises()

    expect(upload).toHaveBeenCalledWith(7, file, 'overwrite', file.name)
  })

  it('skips files when the user picks "skip" in the conflict dialog', async () => {
    const upload = vi.spyOn(jobAttachmentsApi, 'upload')

    const wrapper = mount(JobAttachmentsManager, { props: { jobId: 7 } })
    await flushPromises()

    const file = new File([new Uint8Array([1])], 'report.pdf', { type: 'application/pdf' })
    wrapper.vm.handleFileSelected({ raw: file })
    await flushPromises()

    wrapper
      .findComponent(AttachmentConflictDialog)
      .vm.$emit('resolved', { 'report.pdf': 'skip' })
    await flushPromises()

    expect(upload).not.toHaveBeenCalled()
  })

  it('cancelling the conflict dialog aborts the whole batch', async () => {
    const upload = vi.spyOn(jobAttachmentsApi, 'upload')

    const wrapper = mount(JobAttachmentsManager, { props: { jobId: 7 } })
    await flushPromises()

    const fileA = new File([new Uint8Array([1])], 'a.pdf', { type: 'application/pdf' })
    const fileB = new File([new Uint8Array([2])], 'report.pdf', {
      type: 'application/pdf',
    })
    wrapper.vm.handleFileSelected({ raw: fileA })
    wrapper.vm.handleFileSelected({ raw: fileB })
    await flushPromises()

    wrapper
      .findComponent(AttachmentConflictDialog)
      .vm.$emit('resolved', null)
    await flushPromises()

    expect(upload).not.toHaveBeenCalled()
  })

  it('shows an error toast when the API rejects the upload as too large', async () => {
    vi.spyOn(jobAttachmentsApi, 'upload').mockRejectedValue(
      Object.assign(new Error('413'), { response: { status: 413 } }),
    )
    const error = vi.spyOn(ElMessage, 'error').mockImplementation(() => {})

    const wrapper = mount(JobAttachmentsManager, { props: { jobId: 7 } })
    await flushPromises()

    const file = new File([new Uint8Array([1])], 'new.pdf', { type: 'application/pdf' })
    wrapper.vm.handleFileSelected({ raw: file })
    await flushPromises()

    expect(error).toHaveBeenCalled()
    expect(error.mock.calls[0][0]).toContain('new.pdf')
    expect(error.mock.calls[0][0]).toContain('大小上限')
  })

  it('opens the password-confirm dialog before calling the API on single delete', async () => {
    const remove = vi.spyOn(jobAttachmentsApi, 'remove').mockResolvedValue()

    const wrapper = mount(JobAttachmentsManager, { props: { jobId: 7 } })
    await flushPromises()

    await wrapper.find('[data-test="delete-1"]').trigger('click')
    await flushPromises()
    // Dialog opens, API hasn't fired yet — password must be entered first.
    expect(wrapper.vm.deleteDialogOpen).toBe(true)
    expect(remove).not.toHaveBeenCalled()

    wrapper.findComponent(DeleteWithPasswordDialog).vm.$emit('confirm', 'admin-pw')
    await flushPromises()

    expect(remove).toHaveBeenCalledWith(7, 1, 'admin-pw')
    expect(wrapper.vm.attachments.some((a) => a.id === 1)).toBe(false)
    expect(wrapper.vm.deleteDialogOpen).toBe(false)
  })

  it('shows a "密碼錯誤" inline error when the API rejects with 422', async () => {
    vi.spyOn(jobAttachmentsApi, 'remove').mockRejectedValue(
      Object.assign(new Error('422'), { response: { status: 422 } }),
    )

    const wrapper = mount(JobAttachmentsManager, { props: { jobId: 7 } })
    await flushPromises()

    await wrapper.find('[data-test="delete-1"]').trigger('click')
    await flushPromises()
    wrapper.findComponent(DeleteWithPasswordDialog).vm.$emit('confirm', 'wrong')
    await flushPromises()

    expect(wrapper.vm.deleteError).toBe('密碼錯誤')
    // Dialog stays open so the user can retry — only the input clears.
    expect(wrapper.vm.deleteDialogOpen).toBe(true)
    expect(wrapper.vm.attachments.some((a) => a.id === 1)).toBe(true)
  })

  it('folder upload sends each file with its webkitRelativePath', async () => {
    const upload = vi.spyOn(jobAttachmentsApi, 'upload').mockResolvedValue({
      id: 5,
      job_id: 7,
      filename: 'src/foo.pdf',
      mime_type: 'application/pdf',
      size_bytes: 100,
      uploaded_at: '2026-05-04T00:00:00+00:00',
    })

    const wrapper = mount(JobAttachmentsManager, { props: { jobId: 7 } })
    await flushPromises()

    const fileA = new File([new Uint8Array([1])], 'foo.pdf', { type: 'application/pdf' })
    const fileB = new File([new Uint8Array([2])], 'bar.pdf', { type: 'application/pdf' })
    Object.defineProperty(fileA, 'webkitRelativePath', { value: 'src/foo.pdf' })
    Object.defineProperty(fileB, 'webkitRelativePath', { value: 'src/sub/bar.pdf' })

    wrapper.vm.handleFolderPicked({ target: { files: [fileA, fileB], value: 'x' } })
    await flushPromises()

    const calls = upload.mock.calls
    expect(calls).toHaveLength(2)
    expect(calls[0][3]).toBe('src/foo.pdf')
    expect(calls[1][3]).toBe('src/sub/bar.pdf')
  })

  it('folder upload silently skips OS metadata files (.DS_Store, Thumbs.db, desktop.ini)', async () => {
    const upload = vi.spyOn(jobAttachmentsApi, 'upload').mockResolvedValue({
      id: 6,
      job_id: 7,
      filename: 'src/foo.pdf',
      mime_type: 'application/pdf',
      size_bytes: 1,
      uploaded_at: '2026-05-04T00:00:00+00:00',
    })

    const wrapper = mount(JobAttachmentsManager, { props: { jobId: 7 } })
    await flushPromises()

    const good = new File([new Uint8Array([1])], 'foo.pdf', { type: 'application/pdf' })
    const ds = new File([new Uint8Array([1])], '.DS_Store', { type: 'application/octet-stream' })
    const thumbs = new File([new Uint8Array([1])], 'Thumbs.db', { type: 'application/octet-stream' })
    Object.defineProperty(good, 'webkitRelativePath', { value: 'src/foo.pdf' })
    Object.defineProperty(ds, 'webkitRelativePath', { value: 'src/.DS_Store' })
    Object.defineProperty(thumbs, 'webkitRelativePath', { value: 'src/sub/Thumbs.db' })

    wrapper.vm.handleFolderPicked({
      target: { files: [good, ds, thumbs], value: 'x' },
    })
    await flushPromises()

    // Only the real file reaches the API; the junk siblings never
    // even hit the conflict-resolution step.
    expect(upload).toHaveBeenCalledTimes(1)
    expect(upload.mock.calls[0][3]).toBe('src/foo.pdf')
  })

  it('does not delete when the password-confirm dialog is closed without confirming', async () => {
    const remove = vi.spyOn(jobAttachmentsApi, 'remove')

    const wrapper = mount(JobAttachmentsManager, { props: { jobId: 7 } })
    await flushPromises()

    await wrapper.find('[data-test="delete-1"]').trigger('click')
    await flushPromises()
    wrapper.vm.deleteDialogOpen = false
    await flushPromises()

    expect(remove).not.toHaveBeenCalled()
    expect(wrapper.vm.attachments.some((a) => a.id === 1)).toBe(true)
  })

  describe('folder-aware uploads', () => {
    const NESTED_LIST = [
      {
        id: 1,
        job_id: 7,
        filename: 'root.pdf',
        mime_type: 'application/pdf',
        size_bytes: 1,
        uploaded_at: '2026-05-01T00:00:00+00:00',
        preview_available: false,
      },
      {
        id: 2,
        job_id: 7,
        filename: 'src/foo.pdf',
        mime_type: 'application/pdf',
        size_bytes: 1,
        uploaded_at: '2026-05-01T00:00:00+00:00',
        preview_available: false,
      },
    ]

    it('upload at root uses bare filename as relpath', async () => {
      jobAttachmentsApi.list.mockResolvedValue(NESTED_LIST)
      const upload = vi.spyOn(jobAttachmentsApi, 'upload').mockResolvedValue({
        id: 99,
        job_id: 7,
        filename: 'new.pdf',
        mime_type: 'application/pdf',
        size_bytes: 1,
        uploaded_at: '2026-05-02T00:00:00+00:00',
        preview_available: false,
      })

      const wrapper = mount(JobAttachmentsManager, { props: { jobId: 7 } })
      await flushPromises()

      const file = new File([new Uint8Array([1])], 'new.pdf', {
        type: 'application/pdf',
      })
      wrapper.vm.handleFileSelected({ raw: file })
      await flushPromises()

      expect(upload.mock.calls[0][3]).toBe('new.pdf')
    })

    it('upload from inside a folder prefixes filename with the current path', async () => {
      jobAttachmentsApi.list.mockResolvedValue(NESTED_LIST)
      const upload = vi.spyOn(jobAttachmentsApi, 'upload').mockResolvedValue({
        id: 99,
        job_id: 7,
        filename: 'src/new.pdf',
        mime_type: 'application/pdf',
        size_bytes: 1,
        uploaded_at: '2026-05-02T00:00:00+00:00',
        preview_available: false,
      })

      const wrapper = mount(JobAttachmentsManager, { props: { jobId: 7 } })
      await flushPromises()

      // Drill into src/.
      await wrapper.find('[data-test="manager-folder-src"]').trigger('click')
      await flushPromises()

      const file = new File([new Uint8Array([1])], 'new.pdf', {
        type: 'application/pdf',
      })
      wrapper.vm.handleFileSelected({ raw: file })
      await flushPromises()

      expect(upload.mock.calls[0][3]).toBe('src/new.pdf')
    })

    it('folder upload from inside a folder nests the picked tree under it', async () => {
      jobAttachmentsApi.list.mockResolvedValue(NESTED_LIST)
      const upload = vi.spyOn(jobAttachmentsApi, 'upload').mockResolvedValue({
        id: 99,
        job_id: 7,
        filename: 'src/utils/a.py',
        mime_type: 'text/x-python',
        size_bytes: 1,
        uploaded_at: '2026-05-02T00:00:00+00:00',
        preview_available: false,
      })

      const wrapper = mount(JobAttachmentsManager, { props: { jobId: 7 } })
      await flushPromises()
      await wrapper.find('[data-test="manager-folder-src"]').trigger('click')
      await flushPromises()

      const a = new File([new Uint8Array([1])], 'a.py', { type: 'text/x-python' })
      const b = new File([new Uint8Array([1])], 'b.py', { type: 'text/x-python' })
      Object.defineProperty(a, 'webkitRelativePath', { value: 'utils/a.py' })
      Object.defineProperty(b, 'webkitRelativePath', { value: 'utils/b.py' })

      wrapper.vm.handleFolderPicked({
        target: { files: [a, b], value: 'x' },
      })
      await flushPromises()

      expect(upload.mock.calls[0][3]).toBe('src/utils/a.py')
      expect(upload.mock.calls[1][3]).toBe('src/utils/b.py')
    })

    it('breadcrumb root link jumps back without losing state', async () => {
      jobAttachmentsApi.list.mockResolvedValue(NESTED_LIST)
      const wrapper = mount(JobAttachmentsManager, { props: { jobId: 7 } })
      await flushPromises()

      await wrapper.find('[data-test="manager-folder-src"]').trigger('click')
      await flushPromises()
      expect(wrapper.find('[data-test="attachment-row-2"]').exists()).toBe(true)

      await wrapper.find('[data-test="manager-breadcrumb-0"]').trigger('click')
      await flushPromises()
      expect(wrapper.find('[data-test="attachment-row-1"]').exists()).toBe(true)
      expect(wrapper.find('[data-test="manager-folder-src"]').exists()).toBe(true)
    })
  })

  describe('bulk selection & delete', () => {
    const TREE_LIST = [
      {
        id: 1,
        job_id: 7,
        filename: 'root.pdf',
        mime_type: 'application/pdf',
        size_bytes: 1,
        uploaded_at: '2026-05-01T00:00:00+00:00',
        preview_available: false,
      },
      {
        id: 2,
        job_id: 7,
        filename: 'top.pdf',
        mime_type: 'application/pdf',
        size_bytes: 1,
        uploaded_at: '2026-05-01T00:00:00+00:00',
        preview_available: false,
      },
      {
        id: 3,
        job_id: 7,
        filename: 'src/foo.pdf',
        mime_type: 'application/pdf',
        size_bytes: 1,
        uploaded_at: '2026-05-01T00:00:00+00:00',
        preview_available: false,
      },
      {
        id: 4,
        job_id: 7,
        filename: 'src/components/Bar.png',
        mime_type: 'image/png',
        size_bytes: 1,
        uploaded_at: '2026-05-01T00:00:00+00:00',
        preview_available: false,
      },
    ]

    it('shows the bulk bar only after at least one row is ticked', async () => {
      jobAttachmentsApi.list.mockResolvedValue(TREE_LIST)

      const wrapper = mount(JobAttachmentsManager, { props: { jobId: 7 } })
      await flushPromises()

      expect(wrapper.find('[data-test="bulk-bar"]').exists()).toBe(false)

      wrapper.vm.toggleFileSelection(1, true)
      await flushPromises()

      const bar = wrapper.find('[data-test="bulk-bar"]')
      expect(bar.exists()).toBe(true)
      expect(bar.text()).toContain('1')
    })

    it('select-all picks every visible folder + file in the current path', async () => {
      jobAttachmentsApi.list.mockResolvedValue(TREE_LIST)
      const wrapper = mount(JobAttachmentsManager, { props: { jobId: 7 } })
      await flushPromises()

      wrapper.vm.toggleSelectAllVisible(true)
      await flushPromises()

      // Root has files id 1, 2 + folder "src".
      expect(wrapper.vm.selectedFileIds.has(1)).toBe(true)
      expect(wrapper.vm.selectedFileIds.has(2)).toBe(true)
      expect(wrapper.vm.selectedFolderPaths.has('src')).toBe(true)
      // selectionCount is rows; selectedAttachmentIds is the expanded
      // bulk-delete payload (root files + everything under src/).
      expect(wrapper.vm.selectionCount).toBe(3)
      expect([...wrapper.vm.selectedAttachmentIds].sort()).toEqual([1, 2, 3, 4])
    })

    it('bulk delete confirm → POSTs every id under the selection with password', async () => {
      jobAttachmentsApi.list.mockResolvedValue(TREE_LIST)
      const bulkRemove = vi
        .spyOn(jobAttachmentsApi, 'bulkRemove')
        .mockResolvedValue({ deleted: 3 })

      const wrapper = mount(JobAttachmentsManager, { props: { jobId: 7 } })
      await flushPromises()

      // Tick file id 1 + folder "src" (covers ids 3, 4).
      wrapper.vm.toggleFileSelection(1, true)
      wrapper.vm.toggleFolderSelection('src', true)
      await flushPromises()

      await wrapper.find('[data-test="bulk-delete"]').trigger('click')
      await flushPromises()
      // Password gate: dialog open, API not called yet.
      expect(wrapper.vm.deleteDialogOpen).toBe(true)
      expect(bulkRemove).not.toHaveBeenCalled()

      wrapper.findComponent(DeleteWithPasswordDialog).vm.$emit('confirm', 'admin-pw')
      await flushPromises()

      expect(bulkRemove).toHaveBeenCalledTimes(1)
      const [jobIdArg, ids, pw] = bulkRemove.mock.calls[0]
      expect(jobIdArg).toBe(7)
      expect([...ids].sort()).toEqual([1, 3, 4])
      expect(pw).toBe('admin-pw')

      // Local state purged + selection cleared.
      expect(wrapper.vm.attachments.find((a) => a.id === 1)).toBeUndefined()
      expect(wrapper.vm.attachments.find((a) => a.id === 3)).toBeUndefined()
      expect(wrapper.vm.attachments.find((a) => a.id === 4)).toBeUndefined()
      expect(wrapper.vm.attachments.find((a) => a.id === 2)).toBeDefined()
      expect(wrapper.vm.selectionCount).toBe(0)
    })

    it('closing the password dialog without confirming keeps the selection', async () => {
      jobAttachmentsApi.list.mockResolvedValue(TREE_LIST)
      const bulkRemove = vi.spyOn(jobAttachmentsApi, 'bulkRemove')

      const wrapper = mount(JobAttachmentsManager, { props: { jobId: 7 } })
      await flushPromises()
      wrapper.vm.toggleFileSelection(1, true)
      await flushPromises()

      await wrapper.find('[data-test="bulk-delete"]').trigger('click')
      await flushPromises()
      wrapper.vm.deleteDialogOpen = false
      await flushPromises()

      expect(bulkRemove).not.toHaveBeenCalled()
      expect(wrapper.vm.selectedFileIds.has(1)).toBe(true)
    })

    it('folder delete confirm → bulk-removes every descendant with password', async () => {
      jobAttachmentsApi.list.mockResolvedValue(TREE_LIST)
      const bulkRemove = vi
        .spyOn(jobAttachmentsApi, 'bulkRemove')
        .mockResolvedValue({ deleted: 2 })

      const wrapper = mount(JobAttachmentsManager, { props: { jobId: 7 } })
      await flushPromises()

      await wrapper
        .find('[data-test="delete-folder-src"]')
        .trigger('click')
      await flushPromises()
      wrapper.findComponent(DeleteWithPasswordDialog).vm.$emit('confirm', 'admin-pw')
      await flushPromises()

      expect(bulkRemove).toHaveBeenCalledTimes(1)
      const [, ids, pw] = bulkRemove.mock.calls[0]
      expect([...ids].sort()).toEqual([3, 4])
      expect(pw).toBe('admin-pw')
      // The two surviving root files are still on screen.
      expect(wrapper.vm.attachments.map((a) => a.id).sort()).toEqual([1, 2])
    })

    it('clicking a folder row drills in even when its delete button is also rendered', async () => {
      jobAttachmentsApi.list.mockResolvedValue(TREE_LIST)
      const wrapper = mount(JobAttachmentsManager, { props: { jobId: 7 } })
      await flushPromises()

      await wrapper.find('[data-test="manager-folder-src"]').trigger('click')
      await flushPromises()

      // Drilled into src/, "foo.pdf" should be visible as a file row.
      expect(wrapper.find('[data-test="attachment-row-3"]').exists()).toBe(true)
    })

    it('clears selection when the user navigates into a folder', async () => {
      jobAttachmentsApi.list.mockResolvedValue(TREE_LIST)
      const wrapper = mount(JobAttachmentsManager, { props: { jobId: 7 } })
      await flushPromises()

      wrapper.vm.toggleFileSelection(1, true)
      await flushPromises()
      expect(wrapper.vm.selectionCount).toBe(1)

      await wrapper.find('[data-test="manager-folder-src"]').trigger('click')
      await flushPromises()

      expect(wrapper.vm.selectionCount).toBe(0)
    })
  })

  describe('transient "new folder" button', () => {
    const NESTED = [
      {
        id: 100,
        job_id: 7,
        filename: 'top.pdf',
        mime_type: 'application/pdf',
        size_bytes: 1,
        uploaded_at: '2026-05-01T00:00:00+00:00',
        preview_available: false,
      },
      {
        id: 101,
        job_id: 7,
        filename: 'src/a.pdf',
        mime_type: 'application/pdf',
        size_bytes: 1,
        uploaded_at: '2026-05-01T00:00:00+00:00',
        preview_available: false,
      },
    ]

    it('opens a name prompt and navigates into the new folder on confirm', async () => {
      jobAttachmentsApi.list.mockResolvedValue(NESTED)
      vi.spyOn(ElMessageBox, 'prompt').mockResolvedValue({
        action: 'confirm',
        value: 'planning',
      })

      const wrapper = mount(JobAttachmentsManager, { props: { jobId: 7 } })
      await flushPromises()

      await wrapper.find('[data-test="folder-create-button"]').trigger('click')
      await flushPromises()

      expect(wrapper.vm.currentPath).toBe('planning')
      // No DB write happens — folder is purely a navigation state. The
      // list is untouched until the first upload lands.
      expect(wrapper.vm.attachments).toHaveLength(NESTED.length)
    })

    it('uploads from inside the new folder prefix the relpath with its name', async () => {
      jobAttachmentsApi.list.mockResolvedValue(NESTED)
      vi.spyOn(ElMessageBox, 'prompt').mockResolvedValue({
        action: 'confirm',
        value: 'planning',
      })
      const upload = vi.spyOn(jobAttachmentsApi, 'upload').mockResolvedValue({
        id: 999,
        job_id: 7,
        filename: 'planning/notes.md',
        mime_type: 'text/markdown',
        size_bytes: 1,
        uploaded_at: '2026-05-02T00:00:00+00:00',
        preview_available: false,
      })

      const wrapper = mount(JobAttachmentsManager, { props: { jobId: 7 } })
      await flushPromises()
      await wrapper.find('[data-test="folder-create-button"]').trigger('click')
      await flushPromises()

      const file = new File([new Uint8Array([1])], 'notes.md', {
        type: 'text/markdown',
      })
      wrapper.vm.handleFileSelected({ raw: file })
      await flushPromises()

      expect(upload.mock.calls[0][3]).toBe('planning/notes.md')
    })

    it('rejects names that collide with an existing folder at the same level', async () => {
      jobAttachmentsApi.list.mockResolvedValue(NESTED)
      // Root has "src" as a folder. The prompt's inputValidator must
      // refuse "src" so the user doesn't end up in a confused state
      // where the breadcrumb says new-folder but the listing is the
      // pre-existing one.
      const prompt = vi.spyOn(ElMessageBox, 'prompt').mockImplementation(
        async (_msg, _title, opts) => {
          const verdict = opts.inputValidator('src')
          expect(verdict).toContain('已存在')
          throw 'cancel'
        },
      )

      const wrapper = mount(JobAttachmentsManager, { props: { jobId: 7 } })
      await flushPromises()
      await wrapper.find('[data-test="folder-create-button"]').trigger('click')
      await flushPromises()

      expect(prompt).toHaveBeenCalledTimes(1)
      expect(wrapper.vm.currentPath).toBe('')
    })

    it('rejects names with path separators', async () => {
      jobAttachmentsApi.list.mockResolvedValue(NESTED)
      vi.spyOn(ElMessageBox, 'prompt').mockImplementation(
        async (_msg, _title, opts) => {
          expect(opts.inputValidator('a/b')).toContain('不可含有')
          expect(opts.inputValidator('..')).toContain('不可使用')
          expect(opts.inputValidator('   ')).toContain('不可空白')
          throw 'cancel'
        },
      )

      const wrapper = mount(JobAttachmentsManager, { props: { jobId: 7 } })
      await flushPromises()
      await wrapper.find('[data-test="folder-create-button"]').trigger('click')
      await flushPromises()
    })

    it('cancelling the prompt leaves currentPath unchanged', async () => {
      jobAttachmentsApi.list.mockResolvedValue(NESTED)
      vi.spyOn(ElMessageBox, 'prompt').mockRejectedValue('cancel')

      const wrapper = mount(JobAttachmentsManager, { props: { jobId: 7 } })
      await flushPromises()
      await wrapper.find('[data-test="folder-create-button"]').trigger('click')
      await flushPromises()

      expect(wrapper.vm.currentPath).toBe('')
    })

    it('is disabled when the attachment count is already at the cap', async () => {
      const full = Array.from({ length: 5 }, (_, i) => ({
        id: i + 1,
        job_id: 7,
        filename: `f${i + 1}.pdf`,
        mime_type: 'application/pdf',
        size_bytes: 1,
        uploaded_at: '2026-05-01T00:00:00+00:00',
        preview_available: false,
      }))
      jobAttachmentsApi.list.mockResolvedValue(full)

      const wrapper = mount(JobAttachmentsManager, { props: { jobId: 7 } })
      await flushPromises()

      // Cap reached → upload zone hides → folder-create button hidden too.
      expect(
        wrapper.find('[data-test="folder-create-button"]').exists(),
      ).toBe(false)
    })
  })

  it('hides the upload zone once the attachment count cap is reached', async () => {
    const fullList = Array.from({ length: 5 }, (_, i) => ({
      id: i + 1,
      job_id: 7,
      filename: `f${i + 1}.pdf`,
      mime_type: 'application/pdf',
      size_bytes: 100,
      uploaded_at: '2026-05-01T00:00:00+00:00',
    }))
    jobAttachmentsApi.list.mockResolvedValue(fullList)

    const wrapper = mount(JobAttachmentsManager, { props: { jobId: 7 } })
    await flushPromises()

    expect(wrapper.find('[data-test="attachment-uploader"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('已達上限')
  })
})
