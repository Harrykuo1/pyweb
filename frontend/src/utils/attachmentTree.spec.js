import { describe, expect, it } from 'vitest'

import {
  attachmentsUnder,
  breadcrumbSegments,
  buildListing,
  joinPath,
} from './attachmentTree'

const ATTACHMENTS = [
  { id: 1, filename: 'top.pdf' },
  { id: 2, filename: 'src/foo.pdf' },
  { id: 3, filename: 'src/components/Bar.png' },
  { id: 4, filename: 'src/components/Baz.png' },
  { id: 5, filename: 'docs/readme.md' },
]

describe('buildListing', () => {
  it('root shows top-level files and folders only', () => {
    const { folders, files } = buildListing(ATTACHMENTS, '')

    expect(files.map((f) => f.attachment.id)).toEqual([1])
    expect(folders.map((f) => f.name)).toEqual(['docs', 'src'])
  })

  it('folder count is total descendants, not just direct children', () => {
    const { folders } = buildListing(ATTACHMENTS, '')
    const src = folders.find((f) => f.name === 'src')
    expect(src.count).toBe(3)
  })

  it('drilled-in path lists files directly under it plus its subfolders', () => {
    const { folders, files } = buildListing(ATTACHMENTS, 'src')

    expect(files.map((f) => f.attachment.id)).toEqual([2])
    expect(folders.map((f) => f.name)).toEqual(['components'])
  })

  it('files at a deeper path use only their basename for displayName', () => {
    const { files } = buildListing(ATTACHMENTS, 'src/components')

    expect(files.map((f) => f.displayName)).toEqual(['Bar.png', 'Baz.png'])
  })

  it('sorts naturally so "Section 2" comes before "Section 10"', () => {
    const numbered = [
      { id: 1, filename: 'Section 10.pdf' },
      { id: 2, filename: 'Section 2.pdf' },
    ]
    const { files } = buildListing(numbered, '')
    expect(files.map((f) => f.displayName)).toEqual([
      'Section 2.pdf',
      'Section 10.pdf',
    ])
  })

  it('drilled-in path with no files returns empty lists', () => {
    const { folders, files } = buildListing(ATTACHMENTS, 'src/components/nope')
    expect(folders).toEqual([])
    expect(files).toEqual([])
  })
})

describe('breadcrumbSegments', () => {
  it('root has just the synthetic root label', () => {
    expect(breadcrumbSegments('')).toEqual([{ name: '附件', path: '' }])
  })

  it('appends each path segment with its cumulative path', () => {
    expect(breadcrumbSegments('src/components')).toEqual([
      { name: '附件', path: '' },
      { name: 'src', path: 'src' },
      { name: 'components', path: 'src/components' },
    ])
  })

  it('honors a custom root label', () => {
    expect(breadcrumbSegments('', '檔案')).toEqual([
      { name: '檔案', path: '' },
    ])
  })
})

describe('joinPath', () => {
  it('returns child when parent is empty', () => {
    expect(joinPath('', 'foo.pdf')).toBe('foo.pdf')
  })

  it('returns parent when child is empty', () => {
    expect(joinPath('src', '')).toBe('src')
  })

  it('joins with "/" when both parts are present', () => {
    expect(joinPath('src/components', 'Foo.vue')).toBe(
      'src/components/Foo.vue',
    )
  })
})

describe('attachmentsUnder', () => {
  it('returns every descendant at any depth', () => {
    const ids = attachmentsUnder(ATTACHMENTS, 'src').map((a) => a.id)
    expect(ids.sort()).toEqual([2, 3, 4])
  })

  it('empty path means everything', () => {
    expect(attachmentsUnder(ATTACHMENTS, '').length).toBe(ATTACHMENTS.length)
  })

  it('matches only at "/" boundaries', () => {
    // "src" must not absorb a sibling folder whose name starts with "src".
    const mixed = [
      { id: 1, filename: 'src/a.pdf' },
      { id: 2, filename: 'src-archived/b.pdf' },
    ]
    expect(attachmentsUnder(mixed, 'src').map((a) => a.id)).toEqual([1])
  })
})
