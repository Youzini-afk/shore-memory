export const theme = {
  text: '#E8E3D5',
  dim: '#7B7F87',
  accent: '#F6C453', // 黄色/橙色
  accentSoft: '#F2A65A',
  border: '#3C414B',
  userBg: '#2B2F36',
  userText: '#F3EEE0',
  systemText: '#9BA3B2',
  error: '#F97066', // 红色
  success: '#7DD3A5', // 绿色
  info: '#8CC8FF', // 偏蓝色
  bg: '#1a1b26', // 深色背景

  // UI 特定
  focusBorder: '#F6C453', // 与强调色相同
  blurBorder: '#565f89', // 更浅的灰色以获得更好的可见性
  selectionBg: '#F6C453',
  selectionFg: '#1a1b26', // 强调色背景上的深色文本
  popupBg: '#24283b', // 比背景稍浅

  // 状态颜色
  running: '#9ece6a', // 亮绿色
  stopped: '#f7768e', // 红色
  starting: '#e0af68', // 橙色
  unknown: '#565f89' // 灰色
}

// 将文本包装在 blessed 标签中的辅助函数
export const format = {
  fg: (color: string, text: string) => `{${color}-fg}${text}{/${color}-fg}`,
  bg: (color: string, text: string) => `{${color}-bg}${text}{/${color}-bg}`,
  bold: (text: string) => `{bold}${text}{/bold}`,
  center: (text: string) => `{center}${text}{/center}`,
  right: (text: string) => `{right}${text}{/right}`
}
