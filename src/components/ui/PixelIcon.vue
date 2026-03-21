<template>
  <div
    class="pixel-icon inline-flex items-center justify-center transition-all duration-300"
    :class="[sizeClass, animationClass]"
  >
    <svg
      :viewBox="`0 0 ${viewBoxSize} ${viewBoxSize}`"
      class="w-full h-full transition-transform duration-500"
      fill="currentColor"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path :d="iconPath" />
    </svg>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  name: {
    type: String,
    required: true
  },
  size: {
    type: String,
    default: 'md' // xs, sm, md, lg, xl, 2xl, 3xl
  },
  // 动画类型: 'bounce', 'spin', 'pulse', 'hover-spin', 'hover-bounce'
  animation: {
    type: String,
    default: ''
  }
})

const viewBoxSize = 16

const sizeClass = computed(() => {
  return {
    'w-3 h-3': props.size === 'xs',
    'w-4 h-4': props.size === 'sm',
    'w-5 h-5': props.size === 'md',
    'w-6 h-6': props.size === 'lg',
    'w-8 h-8': props.size === 'xl',
    'w-10 h-10': props.size === '2xl',
    'w-12 h-12': props.size === '3xl'
  }
})

const animationClass = computed(() => {
  if (!props.animation) return ''
  return {
    'animate-pixel-bounce': props.animation === 'bounce',
    'animate-pixel-spin': props.animation === 'spin',
    'animate-pixel-pulse': props.animation === 'pulse',
    'hover-pixel-spin': props.animation === 'hover-spin',
    'hover-pixel-bounce': props.animation === 'hover-bounce'
  }
})

const icons = {
  // 核心记忆 (🧠) - 像素化脑部轮廓
  brain: 'M4 4h8v2h2v6h-2v2H4v-2H2V6h2V4zm2 2v2h4V6H6z',

  // 对话日志 (💬) - 像素化气泡
  chat: 'M2 2h12v8H8l-4 4v-4H2V2zm2 2v4h8V4H4z',

  // 待办任务 (⚡) - 像素化闪电
  flash: 'M9 2H5l-2 6h4l-2 6 8-8H8l2-4z',

  // 宠物脚印 (🐾) - 像素化肉垫
  paw: 'M3 5h2v2H3V5zm10 0h-2v2h2V5zm-8 4h6v4H5V9zm-3 1h2v2H2v-2zm12 0h-2v2h2v-2z',

  // 星星/火花 (✨) - 像素化十字星
  sparkle: 'M7 2h2v2H7V2zm0 10h2v2H7v-2zm-5-5h2v2H2V7zm10 0h2v2h-2V7zm-3-1h2v2H9V6zm-4 0h2v2H5V6z',

  // 想法/故事 (💭) - 像素化云朵气泡
  thought: 'M5 2h6v2h2v4h-2v2h-2v2H7v-2H5v-2H3V4h2V2z',

  // 教程/书籍 (📚) - 像素化书本
  book: 'M3 2h10v12H3V2zm2 2v8h6V4H5z',

  // 日期 (📅) - 像素化日历
  calendar: 'M2 2h12v12H2V2zm2 4v6h8V6H4zm1-3h2v2H5V3zm5 0h2v2h-2V3z',

  // 排序 (⏳/🕰️) - 像素化沙漏
  hourglass: 'M3 2h10v2h-2v2l-2 2 2 2v2h2v2H3v-2h2v-2l2-2-2-2V4H3V2z',

  // 收藏/心形 (💗) - 像素化心形
  heart:
    'M4 3h2v2H4V3zm6 0h2v2h-2V3zm-8 2h2v2H2V5zm12 0h-2v2h2V5zm-12 2h2v2H2V7zm12 0h-2v2h2V7zm-10 2h2v2H4V9zm6 0h2v2h-2V9zm-4 2h2v2H6v-2z',

  // 重要/星形 (⭐) - 像素化五角星
  star: 'M7 2h2v3h3v2h-2v3h2v2h-3v2H7v-2H4v-2h2v-3H4V7h3V2z',

  // 桌面端 (💻) - 像素化显示器
  desktop: 'M2 3h12v8H2V3zm2 2v4h8V5H4zm2 7h4v2H6v-2z',

  // 移动端 (📱) - 像素化手机
  mobile: 'M5 2h6v12H5V2zm2 2v8h2V4H7z',

  // 眼睛 (👁️) - 像素化眼睛
  eye: 'M2 6h2V4h8v2h2v4h-2v2H4v-2H2V6zm4 0v4h4V6H6z',

  // 归档 (🗄️) - 像素化抽屉/文件夹
  archive: 'M2 3h12v10H2V3zm2 2v2h8V5H4zm0 4v2h8V9H4z',

  // 工具 (🛠️) - 像素化扳手
  tool: 'M10 2l4 4-2 2-4-4 2-2zM3 9l4 4-5 1 1-5z',

  // 刷新 (🔃) - 像素化箭头圆圈
  refresh: 'M13 2v4h-4V5h2V3H5v7h2v2H3v-3h2V5h8V2z M3 14v-4h4v1H5v2h6V6h-2V4h4v10H3z',

  // 时钟 (🕰️/⏳)
  clock: 'M6 2h4v2h2v2h2v4h-2v2h-2v2H6v-2H4v-2H2V6h2V4h2V2zm2 3v4h3v2H7V5h1z',

  // 情感 - 开心 (😊)
  'mood-happy': 'M2 2h12v12H2V2zm3 3v2h2V5H5zm4 0v2h2V5H9zm-5 5v2h8v-2H4z',

  // 情感 - 难过 (😔)
  'mood-sad': 'M2 2h12v12H2V2zm3 3v2h2V5H5zm4 0v2h2V5H9zm1 6v-2H6v2h4z',

  // 情感 - 一般 (😐)
  'mood-neutral': 'M2 2h12v12H2V2zm3 3v2h2V5H5zm4 0v2h2V5H9zm-1 6h4v-1H8v1z',

  // 情感 - 生气 (😠)
  'mood-angry': 'M2 2h12v12H2V2zm2 2l2 2H4V4zm8 0l-2 2h2V4zm-8 6h8v2H4v-2z',

  // 兴奋 (🤩)
  'mood-excited': 'M2 2h12v12H2V2zm2 2l2 2-2 2V4zm8 0l-2 2 2 2V4zm-8 6l4 2 4-2v2H4v-2z',

  // 用户组 (👥)
  users: 'M3 10v4h4v-4H3zm6 0v4h4v-4H9zm-4-6v4h4V4H5zm4-2v2h2V2H9z',

  // 叶子 (🍃)
  leaf: 'M8 2h4v2h2v4h-2v2H8v4H6v-4H4v-2H2V4h2V2h4z',

  // 水晶球 (🔮)
  crystal: 'M4 2h8v2h2v8h-2v2H4v-2H2V4h2V2zm2 10h4v2H6v-2z',

  // 灯泡 (💡)
  lightbulb: 'M5 2h6v2h2v6h-2v2h-2v2H7v-2H5v-2H3V4h2V2zm2 10h2v2H7v-2z',

  // 鞭炮/危险 (🧨)
  firecracker: 'M6 2h4v2h2v10h-2v2H6v-2H4V4h2V2zm2 0h1v1H8V2z',

  // 拼图/记忆块 (🧩)
  puzzle: 'M2 4h4V2h4v2h4v4h2v4h-2v4H10v-2H6v2H2V4z',

  // 握手/约定 (🤝)
  handshake: 'M2 6h4v2H2V6zm10 0h2v2h-2V6zm-6 2h4v2H6V8zm-2 2h2v2H4v-2zm6 0h2v2h-2v-2z',

  // 调色盘/情感 (🎨)
  palette: 'M2 4h12v10H2V4zm3 2v2h2V6H5zm4 0v2h2V6H9zm-4 4v2h2v-2H5z',

  // 铅笔/日志 (📝)
  pencil: 'M10 2l4 4-6 6-4 2 2-4 6-6zM3 13h2v1H3v-1z',

  // 链接 (🔗)
  link: 'M2 6h6v2H2V6zm6 2h6v2H8V8zm-4 2h6v2H4v-2z',

  // 火 (🔥)
  fire: 'M7 2h2v2H7V2zm-2 4h2v2H5V6zm4 0h2v2H9V6zm-2 4h2v2H7v-2z',

  // 搜索 (🔍)
  search: 'M2 2h8v2h2v6h-2v2H2V2zm2 2v6h4V4H4zm8 8h2v2h-2v-2z',

  // 列表 (📋)
  list: 'M3 4h2v2H3V4zm4 0h6v2H7V4zm-4 4h2v2H3V8zm4 0h6v2H7V8zm-4 4h2v2H3v-2zm4 0h6v2H7v-2z',

  // 图表/网络 (📊/🕸️)
  chart: 'M2 10h2v4H2v-4zm4-4h2v8H6V6zm4-4h2v12h-2V2zm4 4h2v8h-2V6z',

  // 垃圾桶 (🗑️)
  trash: 'M5 2h6v2h2v2h-2v8H5V6H3V4h2V2zm2 4v6h2V6H7z',

  // 设置 (⚙️)
  settings: 'M6 2h4v2h2v2h2v4h-2v2h-2v2H6v-2H4v-2h2V6h2V4h2V2zm2 4v4h4V6H8z',

  // 终端 (💻/⌨️)
  terminal: 'M2 4h12v8H2V4zm2 2v4h8V6H4z',

  // 加号 (➕)
  plus: 'M7 2h2v4h4v2H9v4H7V8H3V6h4V2z',

  // 减号 (➖)
  minus: 'M4 7h8v2H4V7z',

  // 地球 (🌐)
  globe: 'M6 2h4v2h2v2h2v4h-2v2h-2v2H6v-2H4v-2H2V6h2V4h2V2zm2 4v4h4V6H8z',

  // 用户 (👤)
  user: 'M6 3h4v2h2v2h-2v2H6V7H4V5h2V3zm-2 6h8v2h2v4H2v-4h2V9z',

  // 警告 (⚠️)
  alert: 'M7 2h2v2h2v2h2v2h2v4H1v-4h2V6h2V4h2V2zm1 4v3h-1V6h1zm-1 5h2v2H7v-2z',

  // 下载/导入 (⬇️)
  download: 'M7 2h2v6h2l-3 3-3-3h2V2zm-5 10h12v2H2v-2z',

  // 机器人 (🤖)
  robot:
    'M4 3h8v9H4V3zm2 2v2h1v-2H6zm3 0v2h1v-2H9zm-3 5h6v1H6v-1z M3 6h1v3H3V6zm10 0h1v3h-1V6z M7 1h2v2H7V1z',

  // 向下箭头 (🔽)
  'chevron-down': 'M3 5h2v2h2v2h2v-2h2v-2h2v2h-2v2h-2v2h-2v-2h-2v-2h-2v-2z',

  // 向上箭头 (🔼)
  'chevron-up': 'M3 11h2v-2h2v-2h2v2h2v2h2v-2h-2v-2h-2v-2h-2v2h-2v2h-2v2z',

  // 向右箭头 (▶️)
  'chevron-right': 'M5 3h2v2h2v2h2v2h-2v2h-2v2H5v-2h2v-2h2v-2h-2V7H5V3z',

  // 方块/最大化 (🔲)
  square: 'M3 3h10v10H3V3zm2 2v6h6V5H5z',

  // 复制/还原 (❐)
  copy: 'M5 5h8v8H5V5zm-2-2h8v2H3v8H1V3h2z',

  // 公文包 (💼)
  briefcase: 'M5 2h6v2h2v8H3V4h2V2zm2 2v2h2V4H7zm-2 4h6v2H5V8z',

  // 收件箱 (📥)
  inbox: 'M2 3h12v10H2V3zm2 2v4h2v2h4V9h2V5H4zm0 6v2h8v-2H4z',

  // 勾选/完成 (✔️) - 优化为更标准的像素勾勾 🌸
  check: 'M2 9h2v2h2v2h2v-2h2v-2h2v-2h2v-2h-2v2h-2v2h-2v2H6v-2H4v-2H2v2z',

  // 关闭/删除 (✖️)
  close: 'M3 3h2v2h2v2h2V5h2V3h2v2h-2v2h-2v2h2v2h2v2h-2v-2h-2v-2H7v2H5v2H3v-2h2V9H3V7h2V5H3V3z',

  // 发送 (📤)
  send: 'M2 12h2v-1h2v-1h2v-1h2v-1h2v-1h2v-1h-2v-1h-2v-1h-2v-1h-2v-1h-2v-1H2v11z',

  // 保存 (💾)
  save: 'M3 2h10v12H3V2zm2 2v3h6V4H5zm0 10v-4h6v4H5z',

  // 麦克风 (🎤)
  mic: 'M7 2h2v6H7V2zm-2 4h2v2H5V6zm6 0h-2v2h2V6zm-3 4h2v2H8v-2z',

  // 耳机 (🎧)
  headphones: 'M2 7h3v6H2V7zm9 0h3v6h-3V7zM5 3h6v2h2v2h-2V5H5V7H3V5h2V3z',

  // 静音 (🔇)
  'volume-x':
    'M2 6h2v4H2V6zm3-2h2v8H5V4zm3-2h2v12H8V2z M13 5h2v2h-2V5zm4 4h2v2h-2V9zm-4 4h2v2h-2v-2zm4-8h2v2h-2V5z',

  // 钥匙 (🔑)
  key: 'M6 6h2v2h2v2h2v2h2v-2h2v-2h-2V6h-2V4H6v2zm-2 2h2v2H4V8zm8 6h2v2h-2v-2z',

  // 退出 (🚪)
  logout: 'M4 3h8v2H6v6h6v2H4V3zm7 2h3v2h-3V5zm3 2h3v2h-3V7zm-3 2h3v2h-3V9z',

  // 门 - 关闭 (🚪)
  'door-closed': 'M4 2h8v12H4V2zm6 6h2v2h-2V8z',

  // 门 - 打开 (🚪)
  'door-open': 'M4 2h2v12H4V2zm4 1l4 2v8l-4 2V3zm2 6h2v2h-2V9z',

  // 信息 (ℹ️)
  info: 'M7 2h2v2H7V2zm0 4h2v8H7V6z',

  // 编辑 (✏️)
  edit: 'M10 2l4 4-6 6-4 2 2-4 6-6zM3 13h2v1H3v-1z',

  // 图片 (🖼️)
  image: 'M2 3h12v10H2V3zm2 2v6h8V5H4zm2 2h2v2H6V7z',

  // 音量 (🔊)
  volume: 'M2 6h3v4H2V6zm4-1h2v6H6V5zm3-2h2v10H9V3z',

  // 引用 (❝)
  quote: 'M3 4h4v4H3V4zm2 6h2v2H5v-2zm6-6h4v4h-4V4zm2 6h2v2h-2v-2z',

  // 文件夹 (📁)
  folder: 'M2 4h4l2 2h6v8H2V4zm2 2v6h8V6H8L6 4H4z',

  // 打开文件夹 (📂)
  'folder-open': 'M2 4h4l2 2h6v8H2V4zm2 3h8v5H4V7zm0-1h10v1H2V6z',

  // 新建文件夹 (📂+)
  'folder-plus': 'M2 4h4l2 2h6v8H2V4zm2 2v6h8V6H8L6 4H4zm3 2h2v1H9v2H8V9H6V8h2V6z',

  // 文件 (📄)
  file: 'M3 2h8l4 4v10H3V2zm1 1v12h10V7h-3V3H4zm7 0v3h3l-3-3z',

  // 代码 (💻)
  code: 'M5 4l-3 4 3 4 1.5-1.5L4 8l2.5-2.5L5 4zm6 0l-1.5 1.5L12 8l-2.5 2.5L11 12l3-4-3-4z',

  // 布局 (⊞)
  layout: 'M2 2h12v12H2V2zm2 2v3h3V4H4zm5 0v3h3V4H9zm-5 5v3h3V9H4zm5 0v3h3V9H9z',

  // 首页 (🏠)
  home: 'M8 2L2 8h2v6h3v-4h2v4h3V8h2L8 2z',

  // 建筑 (🏢)
  building: 'M4 2h8v12H4V2zm2 2v2h4V4H6zm0 4v2h4V8H6zm0 4v2h4v-2H6z',

  // 定位 (📍)
  'map-pin': 'M5 2h6v2h2v4h-2v2h-2v4H7v-4H5V8H3V4h2V2zm2 2v2h2V4H7z',

  // 机器人 (🤖) - 别名
  bot: 'M4 3h8v9H4V3zm2 2v2h1v-2H6zm3 0v2h1v-2H9zm-3 5h6v1H6v-1z M3 6h1v3H3V6zm10 0h1v3h-1V6z M7 1h2v2H7V1z',

  // 加载 (↻) - 类似刷新
  loader: 'M13 2v4h-4V5h2V3H5v7h2v2H3v-3h2V5h8V2z M3 14v-4h4v1H5v2h6V6h-2V4h4v10H3z',

  // 菜单 (☰)
  menu: 'M3 4h10v2H3V4zm0 4h10v2H3V8zm0 4h10v2H3v-2z',

  // CPU (芯片)
  cpu: 'M4 4h8v8H4V4zm2 2v4h4V6H6zm-2-2H2v2h2V4zm0 4H2v2h2V8zm0 4H2v2h2v-2zm4-8V2h2v2H8zm4 0V2h2v2h-2zm0 4h2v2h-2V8zm0 4h2v2h-2v-2zm-4 4v2h2v-2H8zm-4 0v2h2v-2H4z',

  // 数据库 (🗄️)
  database: 'M4 2h8v3H4V2zm0 5h8v3H4V7zm0 5h8v3H4v-3z',

  // 电源 (⏻)
  power:
    'M7 2h2v6H7V2zm-3 2h2v2H4V4zm8 0h2v2h-2V4zm2 4h2v4h-2V8zm-2 4h2v2h-2v-2zm-8 0h2v2H4v-2zm-2-4h2v4H2V8z',

  // 盾牌 (🛡️)
  shield: 'M3 2h10v4l-5 8-5-8V2zm2 2v2l3 5 3-5V4H5z',

  // 游戏手柄 (🎮)
  gamepad: 'M2 6h12v6H2V6zm2 2v2h2V8H4zm6 0h2v2h-2V8z',

  // 圆圈 (⭕)
  circle: 'M6 2h4v2h2v2h2v4h-2v2h-2v2H6v-2H4v-2H2V6h2V4h2V2zm0 2v8h4V4H6z',

  // 插头 (🔌)
  plug: 'M6 2h4v4h-4V2zm2 4v2H4v2h2v4h4v-4h2V8H8V6zm0 6v2h-2v2h2v-2h2v-2H8z',

  // 猫咪 (🐱)
  cat: 'M2 4v3h2v2h8V7h2V4h-2v2h-1V4H9v2H7V4H5v2H4V4H2zm3 6h6v2H5v-2zm1 3h4v1H6v-1z',

  // 活动/脉冲 (📈)
  activity: 'M2 8h3l2-4 3 8 3-8 2 4h3'
}

const iconPath = computed(() => icons[props.name] || icons['sparkle'])
</script>

<style scoped>
.pixel-icon {
  image-rendering: pixelated;
}

@keyframes pixel-bounce {
  0%,
  100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-20%);
  }
}

@keyframes pixel-spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

@keyframes pixel-pulse {
  0%,
  100% {
    transform: scale(1);
    opacity: 1;
  }
  50% {
    transform: scale(1.1);
    opacity: 0.8;
  }
}

.animate-pixel-bounce {
  animation: pixel-bounce 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) infinite;
}

.animate-pixel-spin {
  animation: pixel-spin 2s linear infinite;
}

.animate-pixel-pulse {
  animation: pixel-pulse 1.5s ease-in-out infinite;
}

.hover-pixel-spin:hover svg {
  animation: pixel-spin 1s linear infinite;
}

.hover-pixel-bounce:hover svg {
  animation: pixel-bounce 0.4s cubic-bezier(0.34, 1.56, 0.64, 1) infinite;
}
</style>
