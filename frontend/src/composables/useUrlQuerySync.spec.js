import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { effectScope, nextTick, reactive } from 'vue'

import { useUrlQuerySync } from './useUrlQuerySync'

// A minimal field schema mirroring how Jobs configures the composable:
// a renamed key (sortKey→sort) with a default, a free-text field, and a
// debounced search field.
function makeFields() {
  return {
    sortKey: {
      queryKey: 'sort',
      parse: (v) => (typeof v === 'string' ? v : 'created_at'),
      serialize: (v) => (v !== 'created_at' ? v : undefined),
    },
    kind: {
      parse: (v) => (typeof v === 'string' ? v : ''),
      serialize: (v) => v || undefined,
    },
    q: {
      parse: (v) => (typeof v === 'string' ? v : ''),
      serialize: (v) => v || undefined,
      debounce: 300,
    },
  }
}

// effectScope lets us call onUnmounted-using composables outside a
// component and dispose them deterministically.
function run(fn) {
  const scope = effectScope()
  let result
  scope.run(() => {
    result = fn()
  })
  return { result, dispose: () => scope.stop() }
}

beforeEach(() => {
  vi.useFakeTimers()
})

afterEach(() => {
  vi.useRealTimers()
})

describe('useUrlQuerySync', () => {
  it('seeds state from the URL via each field parse, honoring queryKey', () => {
    const route = reactive({ query: { sort: 'company', kind: 'fulltime', q: 'sys' } })
    const router = { replace: vi.fn() }
    const { result } = run(() =>
      useUrlQuerySync({ route, router, fields: makeFields() }),
    )

    expect(result.sortKey.value).toBe('company')
    expect(result.kind.value).toBe('fulltime')
    expect(result.q.value).toBe('sys')
  })

  it('applies defaults when the URL is empty', () => {
    const route = reactive({ query: {} })
    const { result } = run(() =>
      useUrlQuerySync({ route, router: { replace: vi.fn() }, fields: makeFields() }),
    )
    expect(result.sortKey.value).toBe('created_at')
    expect(result.kind.value).toBe('')
  })

  it('writes a changed non-debounced field to the URL and strips defaults', async () => {
    const route = reactive({ query: {} })
    const router = { replace: vi.fn() }
    const onChange = vi.fn()
    const { result } = run(() =>
      useUrlQuerySync({ route, router, fields: makeFields(), onChange }),
    )

    result.kind.value = 'fulltime'
    await nextTick()

    expect(router.replace).toHaveBeenLastCalledWith({ query: { kind: 'fulltime' } })
    expect(onChange).toHaveBeenCalledTimes(1)
  })

  it('omits a field from the URL once it returns to its default', async () => {
    const route = reactive({ query: { sort: 'company' } })
    const router = { replace: vi.fn() }
    const { result } = run(() =>
      useUrlQuerySync({ route, router, fields: makeFields() }),
    )

    result.sortKey.value = 'created_at'
    await nextTick()

    expect(router.replace).toHaveBeenLastCalledWith({ query: {} })
  })

  it('debounces the flagged field for both the URL write and onChange', async () => {
    const route = reactive({ query: {} })
    const router = { replace: vi.fn() }
    const onChange = vi.fn()
    const { result } = run(() =>
      useUrlQuerySync({ route, router, fields: makeFields(), onChange }),
    )

    result.q.value = 'a'
    result.q.value = 'ab'
    await nextTick()
    expect(router.replace).not.toHaveBeenCalled()
    expect(onChange).not.toHaveBeenCalled()

    vi.advanceTimersByTime(300)
    expect(router.replace).toHaveBeenLastCalledWith({ query: { q: 'ab' } })
    expect(onChange).toHaveBeenCalledTimes(1)
  })

  it('preserves foreign keys across a filter rewrite', async () => {
    const route = reactive({ query: { detail: '7' } })
    const router = { replace: vi.fn() }
    const { result } = run(() =>
      useUrlQuerySync({
        route,
        router,
        fields: makeFields(),
        preserveKeys: ['detail'],
      }),
    )

    result.kind.value = 'internship'
    await nextTick()

    expect(router.replace).toHaveBeenLastCalledWith({
      query: { kind: 'internship', detail: '7' },
    })
  })

  it('clears pending debounce timers on unmount', async () => {
    const route = reactive({ query: {} })
    const router = { replace: vi.fn() }
    const { result, dispose } = run(() =>
      useUrlQuerySync({ route, router, fields: makeFields() }),
    )

    result.q.value = 'typing'
    dispose()
    vi.advanceTimersByTime(300)

    expect(router.replace).not.toHaveBeenCalled()
  })
})
