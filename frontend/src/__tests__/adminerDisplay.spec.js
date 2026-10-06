// @vitest-environment node
import { readFileSync } from 'node:fs'
import { Window } from 'happy-dom'
import { afterEach, describe, expect, it } from 'vitest'

const script = readFileSync(
  new URL('../../../adminer/display.js', import.meta.url),
  'utf8',
)
let window

afterEach(async () => {
  await window?.happyDOM.close()
})

async function render(data = '77,848,576', index = '215,146,496') {
  window = new Window()
  window.document.body.innerHTML = `
    <table id="overview">
      <thead><tr><td></td><th>Table</th><th>Engine</th>
        <th><a href="?order=Data_length">Data</a></th>
        <th><a href="?order=Index_length">Indexes</a></th>
        <th><a href="?order=Data_free">Free</a></th><th>Sequence</th><th>Rows</th><th>Comment</th>
      </tr></thead>
      <tbody><tr id="probe"><td><input type="checkbox"></td><th>probe</th><td>table</td>
        <td><a id="Data_length-probe" href="?create=probe">${data}</a></td>
        <td><a id="Index_length-probe" href="?indexes=probe">${index}</a></td>
        <td><a id="Data_free-probe">?</a></td><td>123</td><td>~ 494,997</td><td>note</td>
      </tr>
      <tr id="view"><td></td><th>view</th><td colspan="5">View</td><td>?</td><td>view note</td></tr>
      <tr id="total"><td></td><th>Total</th><td></td>
        <td id="sum-Data_length">${data}</td><td id="sum-Index_length">${index}</td><td id="sum-Data_free">0</td>
      </tr></tbody>
    </table>
    <table id="query"><tr><td>77,848,576</td><td>?</td></tr></table>`
  window.eval(script)
  await window.happyDOM.whenAsyncComplete()
  return window.document
}

describe('Adminer table capacity display', () => {
  it.each([
    ['0', '0 bytes'],
    ['1,023', '1,023 bytes'],
    ['8,192', '8 KiB'],
    ['77,848,576', '74.24 MiB'],
    ['1,073,741,824', '1 GiB'],
    ['1,099,511,627,776', '1 TiB'],
    ['1,125,899,906,842,624', '1 PiB'],
    ['1,152,921,504,606,846,976', '1 EiB'],
  ])('formats %s with an exact byte tooltip', async (raw, formatted) => {
    const document = await render(raw, raw)
    for (const id of [
      'Data_length-probe',
      'Index_length-probe',
      'sum-Data_length',
      'sum-Index_length',
    ]) {
      expect(document.getElementById(id).textContent).toBe(formatted)
      expect(document.getElementById(id).title).toBe(`${raw} bytes`)
    }
    expect(
      document.getElementById('Data_length-probe').getAttribute('href'),
    ).toBe('?create=probe')
  })

  it('hides the free-space column without shifting views, rows or comments', async () => {
    const document = await render()
    expect(document.querySelector('thead tr').cells[5].style.display).toBe(
      'none',
    )
    expect(
      document.getElementById('Data_free-probe').closest('td').style.display,
    ).toBe('none')
    expect(document.getElementById('sum-Data_free').style.display).toBe('none')
    expect(document.getElementById('view').cells[2].colSpan).toBe(4)
    expect(document.getElementById('view').cells[3].textContent).toBe('?')
    expect(document.getElementById('probe').cells[7].textContent).toBe(
      '~ 494,997',
    )
    expect(document.getElementById('probe').cells[8].textContent).toBe('note')
    expect(document.querySelector('input[type="checkbox"]')).not.toBeNull()
    expect(document.querySelector('#query td').textContent).toBe('77,848,576')
  })

  it('formats delayed statistics and subsequent refreshes without repeating column removal', async () => {
    const document = await render('?', '')
    const cell = document.getElementById('Data_length-probe')
    const sum = document.getElementById('sum-Data_length')
    expect(cell.textContent).toBe('?')
    expect(sum.textContent).toBe('?')
    cell.innerHTML = '8,192'
    sum.innerHTML = '16,384'
    await window.happyDOM.whenAsyncComplete()
    expect(cell.textContent).toBe('8 KiB')
    expect(sum.textContent).toBe('16 KiB')
    cell.firstChild.textContent = '1,048,576'
    await window.happyDOM.whenAsyncComplete()
    expect(cell.textContent).toBe('1 MiB')
    expect(cell.title).toBe('1,048,576 bytes')
    expect(document.getElementById('view').cells[2].colSpan).toBe(4)
  })

  it('leaves other Adminer pages unchanged', async () => {
    window = new Window()
    window.document.body.innerHTML = '<table><tr><td>8192</td></tr></table>'
    window.eval(script)
    await window.happyDOM.whenAsyncComplete()
    expect(window.document.querySelector('td').textContent).toBe('8192')
  })
})
