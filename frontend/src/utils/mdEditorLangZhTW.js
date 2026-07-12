// Traditional Chinese (zh-TW) language pack for md-editor-v3.
//
// md-editor-v3 ships only zh-CN and en-US. Our editors request language
// "zh-TW", which — being unregistered — silently fell back to the en-US
// base, and the read-only previews defaulted to zh-CN (Simplified). Register
// this pack via `config({ editorConfig: { languageUserDefined } })` and set
// language="zh-TW" on the previews so every markdown surface reads as
// Traditional Chinese (e.g. the code block's 複製程式碼 button).
export const mdEditorLangZhTW = {
  toolbarTips: {
    bold: '粗體',
    underline: '底線',
    italic: '斜體',
    strikeThrough: '刪除線',
    title: '標題',
    sub: '下標',
    sup: '上標',
    quote: '引用',
    unorderedList: '無序列表',
    orderedList: '有序列表',
    task: '任務列表',
    codeRow: '行內程式碼',
    code: '區塊程式碼',
    link: '連結',
    image: '圖片',
    table: '表格',
    mermaid: 'mermaid 圖',
    katex: 'katex 公式',
    revoke: '復原',
    next: '重做',
    save: '儲存',
    prettier: '美化',
    pageFullscreen: '瀏覽器全螢幕',
    fullscreen: '螢幕全螢幕',
    preview: '預覽',
    previewOnly: '僅預覽',
    htmlPreview: 'HTML 程式碼預覽',
    catalog: '目錄',
    github: '原始碼位址',
  },
  titleItem: {
    h1: '一級標題',
    h2: '二級標題',
    h3: '三級標題',
    h4: '四級標題',
    h5: '五級標題',
    h6: '六級標題',
  },
  imgTitleItem: {
    link: '加入連結',
    upload: '上傳圖片',
    clip2upload: '裁剪上傳',
  },
  linkModalTips: {
    linkTitle: '加入連結',
    imageTitle: '加入圖片',
    descLabel: '連結描述：',
    descLabelPlaceHolder: '請輸入描述...',
    urlLabel: '連結網址：',
    urlLabelPlaceHolder: '請輸入連結...',
    buttonOK: '確定',
  },
  clipModalTips: {
    title: '裁剪圖片上傳',
    buttonUpload: '上傳',
  },
  copyCode: {
    text: '複製程式碼',
    successTips: '已複製！',
    failTips: '複製失敗！',
  },
  mermaid: {
    flow: '流程圖',
    sequence: '時序圖',
    gantt: '甘特圖',
    class: '類別圖',
    state: '狀態圖',
    pie: '圓餅圖',
    relationship: '關係圖',
    journey: '旅程圖',
  },
  katex: {
    inline: '行內公式',
    block: '區塊公式',
  },
  footer: {
    markdownTotal: '字數',
    scrollAuto: '同步捲動',
  },
}
