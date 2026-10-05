export const EVENT_ACTIVITY_LABELS = {
  event_created: '新增了活動紀錄',
  event_updated: '更新了活動紀錄',
  event_comment_created: '在活動中留言',
  event_comment_updated: '編輯了活動留言',
}

export function timelineItemKey(item) {
  const id = item.comment_id ?? item.event_id ?? item.job_id ?? item.member_id
  return `${item.type}:${id}`
}
