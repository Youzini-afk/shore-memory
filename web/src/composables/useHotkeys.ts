import { onMounted, onUnmounted } from 'vue'

/**
 * \u5168\u5c40\u5feb\u6377\u952e\u6ce8\u518c\u3002
 *
 * \u7528\u6cd5\uff1a
 *   useHotkey('mod+enter', () => submit())
 *   useHotkey('mod+k', (e) => { e.preventDefault(); focusSearch() })
 *
 * - `mod` \u5728 mac \u4e0a\u4ee3\u8868 \u2318\uff0c\u5176\u5b83\u5e73\u53f0\u4ee3\u8868 Ctrl\u3002
 * - key \u90e8\u5206\u5ffd\u7565\u5927\u5c0f\u5199\u3002
 * - \u5982\u679c\u4e8b\u4ef6\u53d1\u751f\u5728 input/textarea/contenteditable \u4e2d\u4e14\u6ca1\u6309\u4fee\u9970\u952e\uff0c\u9ed8\u8ba4\u4e0d\u89e6\u53d1\uff08ignoreInEditables=true\uff09\u3002
 */
export interface HotkeyOptions {
  /** \u5f53 input/textarea \u805a\u7126\u4e14\u6ca1\u6709\u4efb\u4f55\u4fee\u9970\u952e\u65f6\u8df3\u8fc7\u3002\u9ed8\u8ba4 true\u3002 */
  ignoreInEditables?: boolean
  /** \u89e6\u53d1\u65f6\u81ea\u52a8 preventDefault\u3002\u9ed8\u8ba4 false\u3002 */
  preventDefault?: boolean
  /** \u89e6\u53d1\u65f6\u81ea\u52a8 stopPropagation\u3002\u9ed8\u8ba4 false\u3002 */
  stopPropagation?: boolean
}

type KeyHandler = (evt: KeyboardEvent) => void

function isMac(): boolean {
  if (typeof navigator === 'undefined') return false
  return /Mac|iPod|iPhone|iPad/.test(navigator.platform)
}

function parseSpec(spec: string): {
  key: string
  needMod: boolean
  needShift: boolean
  needAlt: boolean
} {
  const parts = spec.toLowerCase().split('+').map((s) => s.trim())
  const key = parts[parts.length - 1]
  return {
    key,
    needMod: parts.includes('mod') || parts.includes('ctrl') || parts.includes('meta'),
    needShift: parts.includes('shift'),
    needAlt: parts.includes('alt') || parts.includes('option')
  }
}

function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false
  const tag = target.tagName
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true
  if (target.isContentEditable) return true
  return false
}

export function useHotkey(spec: string, handler: KeyHandler, opts: HotkeyOptions = {}): void {
  const { key, needMod, needShift, needAlt } = parseSpec(spec)
  const ignoreInEditables = opts.ignoreInEditables ?? true

  const listener = (evt: KeyboardEvent) => {
    if (evt.key.toLowerCase() !== key) return
    const modPressed = isMac() ? evt.metaKey : evt.ctrlKey
    if (needMod && !modPressed) return
    if (!needMod && (evt.metaKey || evt.ctrlKey)) return
    if (needShift !== evt.shiftKey) return
    if (needAlt !== evt.altKey) return

    // \u7f16\u8f91\u5143\u7d20\u4e2d\u7684\u975e\u4fee\u9970\u952e\u5ffd\u7565
    if (!needMod && ignoreInEditables && isEditableTarget(evt.target)) return

    if (opts.preventDefault) evt.preventDefault()
    if (opts.stopPropagation) evt.stopPropagation()
    handler(evt)
  }

  onMounted(() => window.addEventListener('keydown', listener))
  onUnmounted(() => window.removeEventListener('keydown', listener))
}

/** \u4fee\u9970\u952e\u5feb\u6377\u952e\u7684\u663e\u793a\u6587\u672c\uff0c\u4f9b\u754c\u9762\u6e32\u67d3\u3002 */
export function hotkeyLabel(spec: string): string {
  const mac = isMac()
  return spec
    .split('+')
    .map((s) => s.trim().toLowerCase())
    .map((part) => {
      switch (part) {
        case 'mod':
        case 'meta':
          return mac ? '\u2318' : 'Ctrl'
        case 'ctrl':
          return 'Ctrl'
        case 'shift':
          return '\u21e7'
        case 'alt':
        case 'option':
          return mac ? '\u2325' : 'Alt'
        case 'enter':
          return '\u21b5'
        case 'escape':
          return 'Esc'
        default:
          return part.length === 1 ? part.toUpperCase() : part
      }
    })
    .join(mac ? '' : ' + ')
}
