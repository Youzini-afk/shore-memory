<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import Sigma from 'sigma'
import { useGraphStore } from '@/stores/graph'
import type { GraphEdgeAttrs, GraphNodeAttrs } from '@/stores/graph'

const store = useGraphStore()
const { graph, selectedNodeId, hoveredNodeId, focusedNodes, layoutRunning } = storeToRefs(store)

const containerRef = ref<HTMLElement | null>(null)
const overlayRef = ref<HTMLCanvasElement | null>(null)

let sigma: Sigma<GraphNodeAttrs, GraphEdgeAttrs> | null = null
let rafId: number | null = null

/* ---------- Reducers ---------- */

function applyReducers() {
  if (!sigma) return
  const focused = focusedNodes.value
  const selected = selectedNodeId.value
  const hovered = hoveredNodeId.value

  sigma.setSetting('nodeReducer', (nodeId, data) => {
    const attrs = data as GraphNodeAttrs
    const isFocused = !focused || focused.has(nodeId)
    const isSelected = selected === nodeId
    const isHovered = hovered === nodeId
    return {
      ...attrs,
      highlighted: isSelected || isHovered,
      hidden: false,
      // 淡化未 focus 节点
      color: isFocused ? attrs.color : dimColor(attrs.color),
      size: isSelected ? attrs.size * 1.25 : attrs.size,
      zIndex: isSelected ? 2 : isHovered ? 1 : 0
    }
  })

  sigma.setSetting('edgeReducer', (edgeId, data) => {
    const attrs = data as GraphEdgeAttrs
    const g = graph.value
    if (!g) return attrs
    const [source, target] = g.extremities(edgeId)
    const focusedFlag =
      !focused || (focused.has(source) && focused.has(target))
    return {
      ...attrs,
      hidden: false,
      color: focusedFlag ? attrs.color : dimEdgeColor(attrs.color),
      size: focusedFlag ? attrs.size : Math.max(0.3, attrs.size * 0.6)
    }
  })

  sigma.refresh()
}

function dimColor(hex: string): string {
  // 把十六进制或 rgba 色打到 22% 亮度
  if (hex.startsWith('#')) {
    const rgb = hexToRgb(hex)
    if (!rgb) return hex
    return `rgba(${rgb.r},${rgb.g},${rgb.b},0.18)`
  }
  // rgba(...)
  return hex.replace(/rgba?\(([^)]+)\)/, (_, inner) => {
    const parts = String(inner).split(',').map((s) => s.trim())
    if (parts.length >= 3) {
      return `rgba(${parts[0]},${parts[1]},${parts[2]},0.18)`
    }
    return hex
  })
}

function dimEdgeColor(color: string): string {
  return color.replace(/rgba?\(([^)]+)\)/, (_, inner) => {
    const parts = String(inner).split(',').map((s) => s.trim())
    if (parts.length >= 3) {
      return `rgba(${parts[0]},${parts[1]},${parts[2]},0.05)`
    }
    return color
  })
}

function hexToRgb(hex: string): { r: number; g: number; b: number } | null {
  const m = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex)
  if (!m) return null
  return {
    r: parseInt(m[1], 16),
    g: parseInt(m[2], 16),
    b: parseInt(m[3], 16)
  }
}

/* ---------- Halo / Pulse overlay ---------- */

function resizeOverlay() {
  const container = containerRef.value
  const canvas = overlayRef.value
  if (!container || !canvas) return
  const dpr = window.devicePixelRatio || 1
  const rect = container.getBoundingClientRect()
  canvas.width = Math.floor(rect.width * dpr)
  canvas.height = Math.floor(rect.height * dpr)
  canvas.style.width = `${rect.width}px`
  canvas.style.height = `${rect.height}px`
  const ctx = canvas.getContext('2d')
  if (ctx) ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
}

function drawOverlay() {
  const canvas = overlayRef.value
  const g = graph.value
  const s = sigma
  if (!canvas || !g || !s) {
    rafId = requestAnimationFrame(drawOverlay)
    return
  }
  const ctx = canvas.getContext('2d')
  if (!ctx) {
    rafId = requestAnimationFrame(drawOverlay)
    return
  }
  const rect = canvas.getBoundingClientRect()
  ctx.clearRect(0, 0, rect.width, rect.height)

  const focused = focusedNodes.value
  const selected = selectedNodeId.value
  const hovered = hoveredNodeId.value
  const now = performance.now()

  ctx.save()
  ctx.globalCompositeOperation = 'lighter'

  g.forEachNode((nid, attrs) => {
    const inFocus = !focused || focused.has(nid)
    if (!inFocus) return
    const vp = s.graphToViewport({ x: attrs.x, y: attrs.y })
    const radius = Math.max(4, attrs.size)
    const base = selected === nid ? 6 : hovered === nid ? 4 : 2.4
    const haloRadius = radius * base
    const color = attrs.color
    const rgb = toRgb(color)
    if (!rgb) return

    const grad = ctx.createRadialGradient(vp.x, vp.y, radius * 0.4, vp.x, vp.y, haloRadius)
    const alphaCore = selected === nid ? 0.85 : hovered === nid ? 0.55 : 0.28
    grad.addColorStop(0, `rgba(${rgb.r},${rgb.g},${rgb.b},${alphaCore})`)
    grad.addColorStop(0.4, `rgba(${rgb.r},${rgb.g},${rgb.b},${alphaCore * 0.5})`)
    grad.addColorStop(1, `rgba(${rgb.r},${rgb.g},${rgb.b},0)`)
    ctx.fillStyle = grad
    ctx.beginPath()
    ctx.arc(vp.x, vp.y, haloRadius, 0, Math.PI * 2)
    ctx.fill()
  })

  // 脉冲边：仅 selected 节点的直连边
  if (selected && g.hasNode(selected)) {
    const src = g.getNodeAttributes(selected)
    const pSrc = s.graphToViewport({ x: src.x, y: src.y })
    ctx.globalCompositeOperation = 'lighter'
    g.forEachEdge(selected, (eid, attrs, _sid, _tid, _sattr, tattr) => {
      const pTgt = s.graphToViewport({ x: tattr.x, y: tattr.y })
      const dx = pTgt.x - pSrc.x
      const dy = pTgt.y - pSrc.y
      const dist = Math.hypot(dx, dy)
      if (dist < 4) return
      const progress = ((now / 700) + hashStr(eid)) % 1
      const cx = pSrc.x + dx * progress
      const cy = pSrc.y + dy * progress
      const pulseRgb =
        attrs.kind === 'supersede' ? { r: 244, g: 63, b: 94 } : { r: 124, g: 92, b: 255 }
      const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, 18)
      grad.addColorStop(0, `rgba(${pulseRgb.r},${pulseRgb.g},${pulseRgb.b},0.85)`)
      grad.addColorStop(0.5, `rgba(${pulseRgb.r},${pulseRgb.g},${pulseRgb.b},0.35)`)
      grad.addColorStop(1, `rgba(${pulseRgb.r},${pulseRgb.g},${pulseRgb.b},0)`)
      ctx.fillStyle = grad
      ctx.beginPath()
      ctx.arc(cx, cy, 18, 0, Math.PI * 2)
      ctx.fill()

      // 线段本身叠一条更亮的脉冲线
      ctx.strokeStyle = `rgba(${pulseRgb.r},${pulseRgb.g},${pulseRgb.b},0.5)`
      ctx.lineWidth = 1.5
      ctx.beginPath()
      ctx.moveTo(pSrc.x, pSrc.y)
      ctx.lineTo(pTgt.x, pTgt.y)
      ctx.stroke()
    })
  }

  ctx.restore()
  rafId = requestAnimationFrame(drawOverlay)
}

function toRgb(color: string): { r: number; g: number; b: number } | null {
  if (color.startsWith('#')) return hexToRgb(color)
  const m = /rgba?\(([^)]+)\)/.exec(color)
  if (!m) return null
  const parts = m[1].split(',').map((s) => Number(s.trim()))
  if (parts.length < 3) return null
  return { r: parts[0], g: parts[1], b: parts[2] }
}

function hashStr(s: string): number {
  let h = 0
  for (let i = 0; i < s.length; i += 1) h = (h * 31 + s.charCodeAt(i)) | 0
  return (h & 0xffff) / 0xffff
}

/* ---------- Sigma lifecycle ---------- */

function createSigma() {
  const g = graph.value
  const el = containerRef.value
  if (!g || !el) return
  destroySigma()
  sigma = new Sigma<GraphNodeAttrs, GraphEdgeAttrs>(g, el, {
    renderLabels: true,
    labelColor: { color: '#9097AB' },
    labelSize: 11,
    labelWeight: '500',
    labelFont: 'Inter, ui-sans-serif, system-ui',
    labelDensity: 0.55,
    labelGridCellSize: 120,
    labelRenderedSizeThreshold: 10,
    defaultNodeColor: '#7C5CFF',
    defaultEdgeColor: 'rgba(124,92,255,0.25)',
    hideEdgesOnMove: g.order > 1200,
    hideLabelsOnMove: true,
    enableEdgeEvents: false,
    zIndex: true,
    minCameraRatio: 0.08,
    maxCameraRatio: 12
  })

  // events
  sigma.on('clickNode', ({ node }) => {
    store.selectedNodeId = node
  })
  sigma.on('clickStage', () => {
    store.selectedNodeId = null
  })
  sigma.on('enterNode', ({ node }) => {
    store.hoveredNodeId = node
  })
  sigma.on('leaveNode', () => {
    store.hoveredNodeId = null
  })

  applyReducers()

  // Fit on first render
  requestAnimationFrame(() => {
    if (sigma) {
      const camera = sigma.getCamera()
      camera.animatedReset({ duration: 300 })
    }
  })
}

function destroySigma() {
  if (sigma) {
    try {
      sigma.kill()
    } catch {
      /* noop */
    }
    sigma = null
  }
}

function handleResize() {
  resizeOverlay()
  if (sigma) sigma.refresh()
}

/* ---------- wiring ---------- */

onMounted(() => {
  resizeOverlay()
  if (graph.value) createSigma()
  rafId = requestAnimationFrame(drawOverlay)
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  if (rafId !== null) cancelAnimationFrame(rafId)
  rafId = null
  destroySigma()
})

// Graph 实例变化（fetch/agent 切换）→ 重新建 sigma
watch(graph, () => {
  if (graph.value) createSigma()
  else destroySigma()
})

// 状态变化 → 重刷 reducer
watch([focusedNodes, selectedNodeId, hoveredNodeId], () => applyReducers())

// 布局运行时，sigma 会随 graph 更新自动重绘。只需确保初始动作
watch(layoutRunning, (running) => {
  if (!running && sigma) sigma.refresh()
})

defineExpose({
  fit() {
    if (!sigma) return
    sigma.getCamera().animatedReset({ duration: 320 })
  },
  zoomIn() {
    if (!sigma) return
    sigma.getCamera().animatedZoom({ duration: 200 })
  },
  zoomOut() {
    if (!sigma) return
    sigma.getCamera().animatedUnzoom({ duration: 200 })
  }
})
</script>

<template>
  <div
    ref="containerRef"
    class="relative w-full h-full"
    style="background:
      radial-gradient(circle at 30% 20%, rgba(124,92,255,0.08), transparent 42%),
      radial-gradient(circle at 75% 78%, rgba(56,189,248,0.05), transparent 42%),
      #0A0A10"
  >
    <canvas
      ref="overlayRef"
      class="absolute inset-0 pointer-events-none"
    />
    <!-- subtle grid overlay -->
    <div
      aria-hidden="true"
      class="pointer-events-none absolute inset-0 opacity-[0.08]"
      style="background-image:
        linear-gradient(rgba(124,92,255,0.25) 1px, transparent 1px),
        linear-gradient(90deg, rgba(124,92,255,0.25) 1px, transparent 1px);
        background-size: 48px 48px, 48px 48px;
        mask-image: radial-gradient(circle at center, black 50%, transparent 90%);"
    />
  </div>
</template>
