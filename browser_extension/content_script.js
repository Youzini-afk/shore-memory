// 简化页面内容并转换为 Markdown 格式
function getSimplifiedContent() {
  let content = ''
  content += '# ' + document.title + '\n\n'
  content += 'URL: ' + window.location.href + '\n\n'

  const elements = document.body.querySelectorAll('h1, h2, h3, p, a, button, input, textarea')

  elements.forEach((el) => {
    if (el.offsetParent === null) return // 跳过隐藏元素

    // 检查元素或其父级是否被隐藏
    let current = el
    while (current) {
      if (
        current.getAttribute &&
        (current.getAttribute('aria-hidden') === 'true' ||
          current.style.display === 'none' ||
          current.style.visibility === 'hidden')
      ) {
        return
      }
      current = current.parentElement
    }

    let text = el.innerText ? el.innerText.trim() : ''
    if (!text && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA')) {
      text = `[输入框: ${el.placeholder || el.name || el.id || '文本字段'}]`
    }

    if (text) {
      if (el.tagName.startsWith('H')) {
        content += `\n### ${text}\n`
      } else if (el.tagName === 'A') {
        content += `[链接: ${text}](${el.href})\n`
      } else if (el.tagName === 'BUTTON') {
        content += `[按钮: ${text}]\n`
      } else {
        content += `${text}\n`
      }
    }
  })

  return content
}

// 发送页面信息
function sendPageInfo() {
  const info = {
    title: document.title,
    url: window.location.href,
    markdown: getSimplifiedContent()
  }
  chrome.runtime.sendMessage({ type: 'pageInfoUpdate', data: info })
}

// 监听来自后台脚本的命令
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'execute_command') {
    const { command, target, text } = message.data
    handleCommand(command, target, text)
      .then((result) => {
        const newContent = getSimplifiedContent()
        sendResponse({ status: 'success', result: result, page_content: newContent })
        sendPageInfo()
      })
      .catch((err) => {
        sendResponse({ status: 'error', error: err.toString() })
      })
    return true
  } else if (message.type === 'getPageInfo') {
    sendPageInfo()
    sendResponse({ status: 'sent' })
  }
})

async function handleCommand(command, target, text) {
  if (command === 'click') {
    const el = findElement(target)
    if (el) {
      el.click()
      return `点击了元素: ${target}`
    } else {
      throw new Error(`未找到元素: ${target}`)
    }
  } else if (command === 'type') {
    const el = findElement(target)
    if (el) {
      el.value = text
      el.dispatchEvent(new Event('input', { bubbles: true }))
      el.dispatchEvent(new Event('change', { bubbles: true }))
      return `在 ${target} 中输入了 "${text}"`
    } else {
      throw new Error(`未找到元素: ${target}`)
    }
  } else if (command === 'scroll') {
    if (text === 'up') {
      window.scrollBy(0, -window.innerHeight / 2)
    } else {
      window.scrollBy(0, window.innerHeight / 2)
    }
    return '已滚动'
  }
  throw new Error(`未知命令: ${command}`)
}

function findElement(target) {
  if (!target) return null

  const targetLower = target.toLowerCase()

  // 尝试使用 XPath 查找
  if (target.startsWith('/') || target.startsWith('(')) {
    try {
      const result = document.evaluate(
        target,
        document,
        null,
        XPathResult.FIRST_ORDERED_NODE_TYPE,
        null
      )
      if (result.singleNodeValue) return result.singleNodeValue
    } catch {
      // ignore
    }
  }

  // 尝试使用 CSS 选择器查找
  try {
    const el = document.querySelector(target)
    if (el) return el
  } catch {
    // ignore
  }

  // 尝试精确文本匹配（忽略大小写）
  const allElements = document.querySelectorAll('button, a, p, span, h1, h2, h3, h4, h5, h6, label')
  for (let el of allElements) {
    const text = (el.innerText || '').trim().toLowerCase()
    if (text === targetLower && el.offsetParent !== null) {
      return el
    }
  }

  // 尝试模糊文本匹配
  for (let el of allElements) {
    const text = (el.innerText || '').trim().toLowerCase()
    if (text.includes(targetLower) && el.offsetParent !== null) {
      // 返回包含文本的最深层元素
      if (el.children.length === 0) return el

      // 如果有子元素，检查子元素是否也匹配
      let hasMatchingChild = false
      for (let child of el.children) {
        if ((child.innerText || '').toLowerCase().includes(targetLower)) {
          hasMatchingChild = true
          break
        }
      }
      if (!hasMatchingChild) return el
    }
  }

  // 尝试通过占位符、名称、ID 或 aria-label 匹配输入控件
  const inputs = document.querySelectorAll('input, textarea, [role="button"], [aria-label]')
  for (let el of inputs) {
    if (
      (el.placeholder && el.placeholder.toLowerCase().includes(targetLower)) ||
      (el.name && el.name.toLowerCase().includes(targetLower)) ||
      (el.id && el.id.toLowerCase().includes(targetLower)) ||
      (el.getAttribute('aria-label') &&
        el.getAttribute('aria-label').toLowerCase().includes(targetLower))
    ) {
      return el
    }
  }

  return null
}

// 初始化：延迟发送页面信息以确保加载完成
setTimeout(sendPageInfo, 1000)
window.addEventListener('load', sendPageInfo)
