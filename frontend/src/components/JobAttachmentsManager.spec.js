import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { ElMessage, ElMessageBox } from 'element-plus'

import { jobAttachmentsApi } from '../api/jobAttachments'
import { settingsApi } from '../api/settings'
import JobAttachmentsManager from './JobAttachmentsManager.vue'
import AttachmentConflictDialog from './AttachmentConflictDialog.vue'

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

    expect(upload).toHaveBeenCalledWith(7, file, null)
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

    expect(upload).toHaveBeenCalledWith(7, file, 'overwrite')
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

  it('confirms then deletes the attachment via the API', async () => {
    vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm')
    const remove = vi.spyOn(jobAttachmentsApi, 'remove').mockResolvedValue()

    const wrapper = mount(JobAttachmentsManager, { props: { jobId: 7 } })
    await flushPromises()

    await wrapper.find('[data-test="delete-1"]').trigger('click')
    await flushPromises()

    expect(remove).toHaveBeenCalledWith(7, 1)
    expect(wrapper.vm.attachments.some((a) => a.id === 1)).toBe(false)
  })

  it('does not delete when the confirm dialog is cancelled', async () => {
    vi.spyOn(ElMessageBox, 'confirm').mockRejectedValue('cancel')
    const remove = vi.spyOn(jobAttachmentsApi, 'remove')

    const wrapper = mount(JobAttachmentsManager, { props: { jobId: 7 } })
    await flushPromises()

    await wrapper.find('[data-test="delete-1"]').trigger('click')
    await flushPromises()

    expect(remove).not.toHaveBeenCalled()
    expect(wrapper.vm.attachments.some((a) => a.id === 1)).toBe(true)
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
