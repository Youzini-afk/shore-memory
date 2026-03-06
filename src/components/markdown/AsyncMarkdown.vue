<template>
  <div ref="container" class="async-markdown">
    <div v-if="!isRendered" class="skeleton-loader">
      <div class="skeleton-line" style="width: 100%"></div>
      <div class="skeleton-line" style="width: 80%"></div>
      <div class="skeleton-line" style="width: 60%"></div>
    </div>
    <div v-else class="markdown-body" v-html="renderedContent"></div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { marked } from 'marked'
import dompurify from 'dompurify'
import hljs from 'highlight.js'
import 'highlight.js/styles/atom-one-dark.css'

const props = defineProps({
  content: {
    type: String,
    required: true
  }
})

const container = ref(null)
const isRendered = ref(false)
const renderedContent = ref('')
let observer = null

// 配置 marked 使用 highlight.js
const renderer = new marked.Renderer()
renderer.code = ({ text, lang }) => {
  const language = lang && hljs.getLanguage(lang) ? lang : ''
  const highlighted = language
    ? hljs.highlight(text, { language }).value
    : hljs.highlightAuto(text).value
  return `<pre><code class="hljs language-${language}">${highlighted}</code></pre>`
}

marked.use({ renderer })

const render = () => {
  try {
    // 允许重复调用以支持内容更新
    // if (isRendered.value) return

    // 自定义渲染逻辑 (从 DashboardView 迁移)
    let formatted = props.content || ''

    if (!formatted.trim()) {
      renderedContent.value = ''
      isRendered.value = true
      return
    }

    // ... (rest of the logic remains the same, but let's make it cleaner)
    // 仅保留少数仍在使用的功能性 XML 标签 (如核心记忆)
    const triggers = [{ tag: 'MEMORY', title: '核心记忆', icon: '💾' }]
    const replacements = []

    // 1. 先提取触发器，替换为占位符
    triggers.forEach(({ tag, title, icon }) => {
      const regex = new RegExp(`<\\s*${tag}\\s*>([\\s\\S]*?)<\\s*/\\s*${tag}\\s*>`, 'gi')
      formatted = formatted.replace(regex, (match, jsonStr) => {
        try {
          const cleanJson = jsonStr
            .trim()
            .replace(/&quot;/g, '"')
            .replace(/&lt;/g, '<')
            .replace(/&gt;/g, '>')
            .replace(/&amp;/g, '&')

          const data = JSON.parse(cleanJson)
          let detailsHtml = ''

          if (tag.toUpperCase() === 'MEMORY') {
            const tagHtml = (data.tags || [])
              .map((t) => `<span class="pero-tag">${t}</span>`)
              .join('')
            detailsHtml = `
              <div class="pero-memory-content">${data.content || ''}</div>
              <div class="pero-tag-cloud">${tagHtml}</div>
            `
          }

          const placeholder = `PERO_TRIG_${replacements.length}_ID`
          replacements.push({
            placeholder,
            html: `<div class="trigger-block ${tag.toLowerCase()}">
              <details>
                <summary class="trigger-header">
                  <span class="trigger-icon">${icon}</span>
                  <span class="trigger-title">${title}</span>
                  <span class="expand-arrow">▶</span>
                </summary>
                <div class="trigger-body">${detailsHtml}</div>
              </details>
            </div>`
          })
          return placeholder
        } catch {
          return match
        }
      })
    })

    // 2. 解析 Markdown
    let html = marked.parse(formatted)

    // 3. 将占位符替换回 HTML
    replacements.forEach(({ placeholder, html: replacementHtml }) => {
      html = html.replace(placeholder, replacementHtml)
    })

    // 4. 净化 (Sanitize)
    let sanitized = dompurify.sanitize(html)

    // 降级处理：如果结果为空但源内容不为空，使用原始内容（包裹在 p 标签中）
    if (!sanitized && formatted.trim().length > 0) {
      const escaped = formatted
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;')
      sanitized = `<p>${escaped}</p>`
    }

    renderedContent.value = sanitized
    isRendered.value = true
  } catch (err) {
    console.error('渲染 Markdown 失败:', err)
    renderedContent.value = `<div class="p-4 text-red-400 border border-red-500/30 bg-red-500/10 pixel-border-sm-dark">
      <div class="font-bold mb-1">渲染失败</div>
      <div class="text-xs opacity-80">${err.message}</div>
    </div>`
    isRendered.value = true
  }
}

onMounted(() => {
  render()
})

watch(
  () => props.content,
  () => {
    render()
  }
)

onUnmounted(() => {
  if (observer) observer.disconnect()
})

watch(
  () => props.content,
  () => {
    isRendered.value = false
    render()
  }
)
</script>

<style>
/* markdown-body 的全局样式 */
.markdown-body {
  font-size: 14px;
  line-height: 1.6;
}
/* 移除强制颜色以允许继承 */
.markdown-body pre {
  background-color: #282c34; /* Atom One Dark 背景 */
  border-radius: 6px;
  padding: 1em;
  overflow-x: auto;
}
</style>

<style scoped>
.skeleton-loader {
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.skeleton-line {
  height: 12px;
  background: #f0f2f5;
  border-radius: 4px;
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0% {
    opacity: 0.6;
  }
  50% {
    opacity: 1;
  }
  100% {
    opacity: 0.6;
  }
}

.async-markdown {
  min-height: 40px; /* 防止布局抖动 */
}
</style>
