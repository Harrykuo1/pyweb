import { describe, expect, it, vi } from 'vitest'

import { useLikeToggle } from './useLikeToggle'

describe('useLikeToggle', () => {
  it('initializes from the given liked/count', () => {
    const { isLiked, likeCount } = useLikeToggle({
      liked: true,
      count: 5,
      like: vi.fn(),
      unlike: vi.fn(),
    })
    expect(isLiked.value).toBe(true)
    expect(likeCount.value).toBe(5)
  })

  it('optimistically likes, then reconciles with the server truth', async () => {
    const like = vi.fn().mockResolvedValue({ like_count: 6, liked: true })
    const { isLiked, likeCount, toggle } = useLikeToggle({
      liked: false,
      count: 5,
      like,
      unlike: vi.fn(),
    })
    const p = toggle()
    // Flips immediately, before the request resolves.
    expect(isLiked.value).toBe(true)
    expect(likeCount.value).toBe(6)
    await p
    expect(like).toHaveBeenCalledOnce()
    expect(likeCount.value).toBe(6)
  })

  it('optimistically unlikes when already liked', async () => {
    const unlike = vi.fn().mockResolvedValue({ like_count: 4, liked: false })
    const { isLiked, likeCount, toggle } = useLikeToggle({
      liked: true,
      count: 5,
      like: vi.fn(),
      unlike,
    })
    await toggle()
    expect(unlike).toHaveBeenCalledOnce()
    expect(isLiked.value).toBe(false)
    expect(likeCount.value).toBe(4)
  })

  it('reverts to the prior state on error', async () => {
    const like = vi.fn().mockRejectedValue(new Error('boom'))
    const { isLiked, likeCount, toggle } = useLikeToggle({
      liked: false,
      count: 5,
      like,
      unlike: vi.fn(),
    })
    await toggle()
    expect(isLiked.value).toBe(false)
    expect(likeCount.value).toBe(5)
  })

  it('ignores a toggle while a request is pending', async () => {
    let resolve
    const like = vi
      .fn()
      .mockImplementation(() => new Promise((r) => (resolve = r)))
    const { toggle } = useLikeToggle({
      liked: false,
      count: 0,
      like,
      unlike: vi.fn(),
    })
    toggle()
    toggle() // should be ignored while the first is in flight
    expect(like).toHaveBeenCalledOnce()
    resolve({ like_count: 1, liked: true })
  })

  it('sync() pushes external truth in', () => {
    const { isLiked, likeCount, sync } = useLikeToggle({
      liked: false,
      count: 0,
      like: vi.fn(),
      unlike: vi.fn(),
    })
    sync(true, 9)
    expect(isLiked.value).toBe(true)
    expect(likeCount.value).toBe(9)
  })
})
