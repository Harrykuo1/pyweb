import { afterEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref } from 'vue'

import { useOutsideClick } from './useOutsideClick'

function mountHost({ isOpen, refs, onClose }) {
  const Host = {
    setup() {
      useOutsideClick({ isOpen, refs, onClose })
      return () => null
    },
  }
  return mount(Host)
}

afterEach(() => {
  document.body.innerHTML = ''
})

describe('useOutsideClick', () => {
  it('calls onClose for an outside click only while open', () => {
    const isOpen = ref(false)
    const inside = document.createElement('div')
    document.body.appendChild(inside)
    const onClose = vi.fn()
    mountHost({ isOpen, refs: [ref(inside)], onClose })

    // Closed → ignored.
    document.dispatchEvent(new MouseEvent('click'))
    expect(onClose).not.toHaveBeenCalled()

    isOpen.value = true
    document.dispatchEvent(new MouseEvent('click'))
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('does not close when the click lands inside one of the refs', () => {
    const isOpen = ref(true)
    const inside = document.createElement('div')
    const child = document.createElement('span')
    inside.appendChild(child)
    document.body.appendChild(inside)
    const onClose = vi.fn()
    mountHost({ isOpen, refs: [ref(inside)], onClose })

    child.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    expect(onClose).not.toHaveBeenCalled()
  })

  it('closes on Escape while open', () => {
    const isOpen = ref(true)
    const onClose = vi.fn()
    mountHost({ isOpen, refs: [], onClose })
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('removes its listeners on unmount', () => {
    const isOpen = ref(true)
    const onClose = vi.fn()
    const wrapper = mountHost({ isOpen, refs: [], onClose })
    wrapper.unmount()
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    expect(onClose).not.toHaveBeenCalled()
  })
})
