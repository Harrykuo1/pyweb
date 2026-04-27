import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

import Cropper from 'cropperjs'
import PhotoCropDialog from './PhotoCropDialog.vue'

// vi.mock is hoisted above imports — Cropper is the mocked default.
vi.mock('cropperjs', () => {
  const fakeSelection = {
    $toCanvas: vi.fn(async () => ({
      toBlob(cb) {
        cb(new Blob(['cropped'], { type: 'image/jpeg' }))
      },
    })),
  }
  const fakeInstance = {
    destroy: vi.fn(),
    getCropperSelection: vi.fn(() => fakeSelection),
  }
  // `new Cropper(...)` is invoked with `new`; an arrow function cannot
  // be used as a constructor, so use a regular function expression.
  const Mock = vi.fn(function () {
    return fakeInstance
  })
  return { default: Mock }
})

vi.mock('element-plus', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    ElMessage: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
  }
})

beforeEach(() => {
  // happy-dom does not implement URL.createObjectURL out of the box.
  if (typeof URL.createObjectURL !== 'function') {
    URL.createObjectURL = vi.fn(() => 'blob:mock')
    URL.revokeObjectURL = vi.fn()
  }
  Cropper.mockClear()
})

afterEach(() => {
  vi.clearAllMocks()
  document.body.innerHTML = ''
})

function makeFile() {
  return new File(['raw'], 'a.png', { type: 'image/png' })
}

describe('PhotoCropDialog', () => {
  it('does not initialise the cropper while closed', () => {
    mount(PhotoCropDialog, {
      props: { modelValue: false, sourceFile: makeFile() },
    })
    expect(Cropper).not.toHaveBeenCalled()
  })

  it('initialises the cropper when opened with a file', async () => {
    const wrapper = mount(PhotoCropDialog, {
      props: { modelValue: false, sourceFile: null },
    })
    await wrapper.setProps({ modelValue: true, sourceFile: makeFile() })
    await flushPromises()

    expect(Cropper).toHaveBeenCalledTimes(1)
    // Template arg pins the 1:1 aspect-ratio on cropper-selection.
    const [, options] = Cropper.mock.calls[0]
    expect(options.template).toContain('aspect-ratio="1"')
  })

  it('confirm emits cropped with a File and closes the dialog', async () => {
    const wrapper = mount(PhotoCropDialog, {
      props: { modelValue: false, sourceFile: null },
    })
    await wrapper.setProps({ modelValue: true, sourceFile: makeFile() })
    await flushPromises()

    await wrapper.vm.handleConfirm()
    await flushPromises()

    const cropped = wrapper.emitted('cropped')
    expect(cropped).toBeTruthy()
    expect(cropped[0][0]).toBeInstanceOf(File)
    expect(cropped[0][0].type).toBe('image/jpeg')
    expect(wrapper.emitted('update:modelValue')).toContainEqual([false])
  })

  it('honors outputType / outputSize / outputFilename props', async () => {
    const wrapper = mount(PhotoCropDialog, {
      props: {
        modelValue: false,
        sourceFile: null,
        outputType: 'image/png',
        outputSize: 256,
        outputFilename: 'logo',
      },
    })
    await wrapper.setProps({ modelValue: true, sourceFile: makeFile() })
    await flushPromises()

    await wrapper.vm.handleConfirm()
    await flushPromises()

    const file = wrapper.emitted('cropped')[0][0]
    expect(file.type).toBe('image/png')
    expect(file.name).toBe('logo.png')
  })

  it('renders custom title when provided', async () => {
    const wrapper = mount(PhotoCropDialog, {
      props: {
        modelValue: true,
        sourceFile: makeFile(),
        title: '裁切 Logo',
      },
      attachTo: document.body,
    })
    await flushPromises()
    expect(document.body.innerHTML).toContain('裁切 Logo')
  })
})
