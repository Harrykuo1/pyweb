import { describe, it, expect } from 'vitest'
import { mdEditorLangZhTW } from './mdEditorLangZhTW'

describe('mdEditorLangZhTW', () => {
  it('translates the visible labels to Traditional Chinese', () => {
    // The code-block copy button was the reported Simplified string.
    expect(mdEditorLangZhTW.copyCode.text).toBe('複製程式碼')
    expect(mdEditorLangZhTW.toolbarTips.bold).toBe('粗體')
    expect(mdEditorLangZhTW.toolbarTips.preview).toBe('預覽')
  })

  it('has no Simplified-only characters in the copy-code label', () => {
    // Guards against a Simplified string sneaking back in.
    expect(mdEditorLangZhTW.copyCode.text).not.toContain('复')
    expect(mdEditorLangZhTW.copyCode.text).not.toContain('码')
  })
})
