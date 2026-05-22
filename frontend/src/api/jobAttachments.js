import client from './client'

// Public URL for inline preview / download links. The backend returns
// the raw binary on this path with Content-Disposition: inline so
// <embed src="..."> and <img src="..."> render in place.
export function attachmentUrl(jobId, attachmentId) {
  return `/api/jobs/${jobId}/attachments/${attachmentId}`
}

export const jobAttachmentsApi = {
  async list(jobId) {
    const { data } = await client.get(`/jobs/${jobId}/attachments`)
    return data
  },
  async upload(jobId, file, conflictStrategy = null) {
    const form = new FormData()
    form.append('file', file)
    if (conflictStrategy) {
      form.append('conflict_strategy', conflictStrategy)
    }
    const { data } = await client.post(
      `/jobs/${jobId}/attachments`,
      form,
      { headers: { 'Content-Type': 'multipart/form-data' } },
    )
    return data
  },
  async remove(jobId, attachmentId) {
    await client.delete(`/jobs/${jobId}/attachments/${attachmentId}`)
  },
}
