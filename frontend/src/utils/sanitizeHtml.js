import DOMPurify from 'dompurify'

// Shared sanitizer for every md-editor-v3 preview surface (resume, job
// experience/timeline, event description). md-editor-v3 renders raw HTML
// from user-supplied Markdown; passing this as its `sanitize` prop strips
// scripts, event handlers, iframes and javascript: URLs so stored markup
// cannot execute in a viewer's session. DOMPurify's defaults keep the safe
// formatting tags Markdown produces.
export function sanitizeHtml(html) {
  if (typeof html !== 'string') return ''
  return DOMPurify.sanitize(html)
}
