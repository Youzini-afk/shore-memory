function updateStatus() {
  chrome.runtime.sendMessage({ type: 'getStatus' }, (response) => {
    const statusSpan = document.getElementById('status')
    const attemptsSpan = document.getElementById('attempts')

    if (response) {
      if (response.connected) {
        statusSpan.innerHTML = '<span class="indicator"></span>已连接'
        statusSpan.className = 'value status-connected'
      } else {
        statusSpan.innerHTML = '<span class="indicator"></span>未连接'
        statusSpan.className = 'value status-disconnected'
      }
      attemptsSpan.textContent = `${response.attempts || 0} 次`
    }
  })
}

document.getElementById('reconnect').addEventListener('click', () => {
  const statusSpan = document.getElementById('status')
  statusSpan.innerHTML = '<span class="indicator"></span>正在连接...'
  statusSpan.className = 'value status-connecting'

  chrome.runtime.sendMessage({ type: 'reconnect' }, () => {
    // 延迟 1.5 秒更新状态，让用户看到“正在连接”的动画
    setTimeout(updateStatus, 1500)
  })
})

// 初始状态检查
updateStatus()
// 弹窗打开时每 2 秒刷新一次状态
setInterval(updateStatus, 2000)
