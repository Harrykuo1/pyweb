import client from './client'

// Public URL for inline preview / download links. The backend returns
// the raw binary on this path with Content-Disposition: inline so
// <embed src="..."> and <img src="..."> render in place.
export function attachmentUrl(jobId, attachmentId) {
  return `/api/jobs/${jobId}/attachments/${attachmentId}`
}

// Companion URL for Office documents that the backend has converted to
// PDF via OnlyOffice. Only resolves to a real PDF when the row's
// preview_available flag is true; the frontend falls back to a plain
// download link otherwise.
export function attachmentPreviewUrl(jobId, attachmentId) {
  return `/api/jobs/${jobId}/attachments/${attachmentId}/preview`
}

export const jobAttachmentsApi = {
  async list(jobId) {
    const { data } = await client.get(`/jobs/${jobId}/attachments`)
    return data
  },
  async upload(
    jobId,
    file,
    conflictStrategy = null,
    relativePath = null,
    onProgress = null,
  ) {
    const form = new FormData()
    form.append('file', file)
    if (conflictStrategy) {
      form.append('conflict_strategy', conflictStrategy)
    }
    if (relativePath) {
      form.append('relative_path', relativePath)
    }
    const config = {
      headers: { 'Content-Type': 'multipart/form-data' },
    }
    if (onProgress) {
      // axios surfaces transfer progress via this hook; evt.total may
      // be undefined when the server hasn't reported Content-Length —
      // skip the percent calc rather than reporting NaN%.
      config.onUploadProgress = (evt) => {
        if (evt.total) {
          onProgress(Math.round((evt.loaded / evt.total) * 100))
        }
      }
    }
    const { data } = await client.post(
      `/jobs/${jobId}/attachments`,
      form,
      config,
    )
    return data
  },
  async remove(jobId, attachmentId, password) {
    // axios needs `data:` (not the second positional arg) to send a body
    // on DELETE — matches the pattern in members.js.
    await client.delete(`/jobs/${jobId}/attachments/${attachmentId}`, {
      data: { password },
    })
  },
  async bulkRemove(jobId, ids, password) {
    const { data } = await client.post(
      `/jobs/${jobId}/attachments/bulk-delete`,
      { ids, password },
    )
    return data
  },
  async bulkDownload(jobId, ids) {
    // Server returns application/zip; ask axios to keep it as a Blob
    // so we can hand it straight to a hidden <a download> instead of
    // having axios coerce the bytes into a malformed string.
    const response = await client.post(
      `/jobs/${jobId}/attachments/bulk-download`,
      { ids },
      { responseType: 'blob' },
    )
    return response.data
  },
}
