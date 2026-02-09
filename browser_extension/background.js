let socket = null
let isConnected = false
let reconnectAttempts = 0
const WS_URL = 'ws://localhost:9120/ws/browser'
const RECONNECT_ALARM_NAME = 'reconnect-alarm'
const CHECK_CONNECTION_ALARM_NAME = 'check-connection-alarm'

function connect() {
  if (socket) {
    if (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING) {
      console.log('Socket 已打开或正在连接，跳过...')
      return
    }
    socket.close()
  }

  console.log(`正在连接到 Pero 后端 ${WS_URL} (尝试第 ${reconnectAttempts + 1} 次)...`)
  socket = new WebSocket(WS_URL)

  socket.onopen = () => {
    console.log('已连接到 Pero 后端')
    isConnected = true
    reconnectAttempts = 0
    chrome.alarms.clear(RECONNECT_ALARM_NAME)
    // 连接成功后启动定期检查
    chrome.alarms.create(CHECK_CONNECTION_ALARM_NAME, { periodInMinutes: 1 })

    // 启动心跳
    startHeartbeat()

    // 连接后立即从活动标签页请求页面信息
    requestPageInfo()
  }

  socket.onmessage = (event) => {
    try {
      if (event.data === 'pong') {
        return
      }

      const message = JSON.parse(event.data)
      console.log('收到消息:', message)

      if (message.type === 'command') {
        handleCommand(message.data)
      }
    } catch (e) {
      console.error('解析消息失败:', e)
    }
  }

  socket.onclose = (event) => {
    console.log(`与 Pero 后端断开连接 (代码: ${event.code})`)
    isConnected = false
    socket = null
    stopHeartbeat()

    // 指数退避重连策略
    const delayMs = Math.min(30000, Math.pow(2, reconnectAttempts) * 1000)
    console.log(`将在 ${delayMs}ms 后尝试重连`)

    // 设置 alarm 作为唤醒 Service Worker 的兜底方案
    chrome.alarms.create(RECONNECT_ALARM_NAME, {
      delayInMinutes: Math.max(1 / 60, delayMs / 60000)
    })

    reconnectAttempts++
  }

  socket.onerror = (error) => {
    console.error('WebSocket 错误:', error)
  }
}

function requestPageInfo() {
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    if (tabs.length > 0) {
      const tabId = tabs[0].id
      // 发送获取页面信息的消息，如果失败则尝试重新注入脚本
      chrome.tabs.sendMessage(tabId, { type: 'getPageInfo' }, () => {
        if (chrome.runtime.lastError) {
          console.log('Content script 未就绪或发生错误:', chrome.runtime.lastError)
          // 如果无法建立连接，尝试重新注入脚本
          injectContentScript(tabId, () => {
            // 重试请求
            chrome.tabs.sendMessage(tabId, { type: 'getPageInfo' })
          })
        }
      })
    }
  })
}

function injectContentScript(tabId, callback, errorCallback) {
  chrome.scripting.executeScript(
    {
      target: { tabId: tabId },
      files: ['content_script.js']
    },
    () => {
      if (chrome.runtime.lastError) {
        console.error('注入脚本失败:', chrome.runtime.lastError)
        if (errorCallback) errorCallback(chrome.runtime.lastError)
      } else {
        console.log('脚本注入成功')
        if (callback) callback()
      }
    }
  )
}

// 闹钟监听器：处理重连和连接状态检查
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === RECONNECT_ALARM_NAME || alarm.name === CHECK_CONNECTION_ALARM_NAME) {
    if (!isConnected) {
      console.log('闹钟触发重连检查...')
      connect()
    }
  }
})

// 标签页激活时检查连接
chrome.tabs.onActivated.addListener(() => {
  if (!isConnected) {
    console.log('标签页已激活，检查连接...')
    connect()
  }
})

// 标签页更新完成后检查连接
chrome.tabs.onUpdated.addListener((tabId, changeInfo) => {
  if (changeInfo.status === 'complete' && !isConnected) {
    console.log('标签页更新完成，检查连接...')
    connect()
  }
})

function handleCommand(commandData) {
  // 在后台脚本中处理导航命令
  if (commandData.command === 'open_url') {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (tabs.length > 0) {
        chrome.tabs.update(tabs[0].id, { url: commandData.url }, () => {
          sendCommandResult(commandData.requestId, {
            status: 'success',
            result: '导航已开始'
          })
        })
      } else {
        chrome.tabs.create({ url: commandData.url }, () => {
          sendCommandResult(commandData.requestId, {
            status: 'success',
            result: '在新标签页中开始导航'
          })
        })
      }
    })
    return
  }

  // 后退命令
  if (commandData.command === 'back') {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (tabs.length > 0) {
        chrome.tabs.goBack(tabs[0].id, () => {
          sendCommandResult(commandData.requestId, { status: 'success', result: '已后退' })
        })
      } else {
        sendCommandResult(commandData.requestId, { error: '未找到活动标签页' })
      }
    })
    return
  }

  // 刷新命令
  if (commandData.command === 'refresh') {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (tabs.length > 0) {
        chrome.tabs.reload(tabs[0].id, {}, () => {
          sendCommandResult(commandData.requestId, { status: 'success', result: '页面已刷新' })
        })
      } else {
        sendCommandResult(commandData.requestId, { error: '未找到活动标签页' })
      }
    })
    return
  }

  // 查找活动标签页以执行其他命令
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    if (tabs.length === 0) {
      sendCommandResult(commandData.requestId, { error: '未找到活动标签页' })
      return
    }
    const tabId = tabs[0].id

    chrome.tabs.sendMessage(tabId, { type: 'execute_command', data: commandData }, (response) => {
      if (chrome.runtime.lastError) {
        console.error('向 Content Script 发送消息错误:', chrome.runtime.lastError)

        // 尝试注入脚本并重试
        injectContentScript(
          tabId,
          () => {
            chrome.tabs.sendMessage(
              tabId,
              { type: 'execute_command', data: commandData },
              (retryResponse) => {
                if (chrome.runtime.lastError) {
                  sendCommandResult(commandData.requestId, {
                    error: chrome.runtime.lastError.message
                  })
                } else {
                  sendCommandResult(commandData.requestId, retryResponse)
                }
              }
            )
          },
          (err) => {
            // 注入失败（如 chrome:// 页面），立即返回错误
            sendCommandResult(commandData.requestId, {
              error: '注入 Content Script 失败: ' + err.message
            })
          }
        )
      } else {
        sendCommandResult(commandData.requestId, response)
      }
    })
  })
}

function sendCommandResult(requestId, result) {
  if (socket && isConnected && socket.readyState === WebSocket.OPEN) {
    socket.send(
      JSON.stringify({
        type: 'command_result',
        data: {
          requestId: requestId,
          ...result
        }
      })
    )
  }
}

let heartbeatInterval = null
function startHeartbeat() {
  stopHeartbeat()
  heartbeatInterval = setInterval(() => {
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send('ping')
    }
  }, 30000)
}

function stopHeartbeat() {
  if (heartbeatInterval) {
    clearInterval(heartbeatInterval)
    heartbeatInterval = null
  }
}

// 监听来自 Content Script 或 Popup 的消息
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'pageInfoUpdate') {
    // 将页面信息转发给后端
    if (socket && isConnected && socket.readyState === WebSocket.OPEN) {
      socket.send(
        JSON.stringify({
          type: 'page_info',
          data: message.data
        })
      )
    }
  } else if (message.type === 'getStatus') {
    sendResponse({
      connected: isConnected,
      attempts: reconnectAttempts,
      url: WS_URL
    })
  } else if (message.type === 'reconnect') {
    reconnectAttempts = 0
    connect()
    sendResponse({ status: '尝试重连中' })
  }
})

// 初始化连接
connect()
