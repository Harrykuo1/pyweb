import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

import DeleteWithPasswordDialog from './DeleteWithPasswordDialog.vue'

let wrapper = null

beforeEach(() => {
  document.body.innerHTML = ''
})

afterEach(() => {
  if (wrapper) {
    wrapper.unmount()
    wrapper = null
  }
  document.body.innerHTML = ''
})

function open(props = {}) {
  wrapper = mount(DeleteWithPasswordDialog, {
    attachTo: document.body,
    props: {
      modelValue: true,
      title: '刪除成員',
      itemName: 'Alice',
      warning: '此操作無法復原',
      loading: false,
      errorMessage: '',
      ...props,
    },
  })
  return wrapper
}

function passwordComponent(w) {
  // Find the ElInput bound to the password field. The dialog only
  // mounts one ElInput so this lookup is unambiguous.
  return w.findComponent({ name: 'ElInput' })
}

function confirmButton() {
  return Array.from(document.querySelectorAll('button')).find(
    (b) => b.textContent.trim() === '刪除',
  )
}

function cancelButton() {
  return Array.from(document.querySelectorAll('button')).find(
    (b) => b.textContent.trim() === '取消',
  )
}

describe('DeleteWithPasswordDialog', () => {
  it('renders the title, item name, and warning text', async () => {
    open({ itemName: 'Alice', warning: '永久刪除' })
    await flushPromises()
    expect(document.body.textContent).toContain('刪除成員')
    expect(document.body.textContent).toContain('Alice')
    expect(document.body.textContent).toContain('永久刪除')
  })

  it('emits confirm with the typed password on submit', async () => {
    const w = open()
    await flushPromises()

    await passwordComponent(w).setValue('my-pw')
    confirmButton(w)?.click()
    await flushPromises()

    expect(w.emitted('confirm')).toBeTruthy()
    expect(w.emitted('confirm')[0]).toEqual(['my-pw'])
  })

  it('does not emit confirm when password is empty', async () => {
    const w = open()
    await flushPromises()

    confirmButton(w)?.click()
    await flushPromises()

    expect(w.emitted('confirm')).toBeFalsy()
  })

  it('does not emit confirm while loading', async () => {
    const w = open({ loading: true })
    await flushPromises()

    await passwordComponent(w).setValue('any')
    confirmButton(w)?.click()
    await flushPromises()

    expect(w.emitted('confirm')).toBeFalsy()
  })

  it('renders an error message when errorMessage is set', async () => {
    open({ errorMessage: '密碼錯誤' })
    await flushPromises()
    const err = document.querySelector('[data-test="delete-error"]')
    expect(err).not.toBeNull()
    expect(err.textContent).toContain('密碼錯誤')
  })

  it('cancel button emits update:modelValue=false', async () => {
    const w = open()
    await flushPromises()

    cancelButton(w)?.click()
    await flushPromises()

    expect(w.emitted('update:modelValue')).toBeTruthy()
    expect(w.emitted('update:modelValue').at(-1)).toEqual([false])
  })

  it('clears the password field when reopened', async () => {
    const w = open()
    await flushPromises()
    await passwordComponent(w).setValue('typed-once')
    expect(passwordComponent(w).props('modelValue')).toBe('typed-once')

    await w.setProps({ modelValue: false })
    await flushPromises()
    await w.setProps({ modelValue: true })
    await flushPromises()

    expect(passwordComponent(w).props('modelValue')).toBe('')
  })
})
