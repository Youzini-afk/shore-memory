/* eslint-disable @typescript-eslint/no-require-imports */
const fs = require('fs-extra')
const path = require('path')

const SRC_DIR = path.join(__dirname, '../src/components/avatar/native')
const DEST_DIR = path.join(__dirname, '../resources/native')

console.log('正在准备 Native 渲染核心...')

async function copyNative() {
  try {
    // 确保目标目录存在
    await fs.ensureDir(DEST_DIR)

    // 我们只复制 .node 核心文件，因为源码已被移除
    const files = await fs.readdir(SRC_DIR)
    const toCopy = files.filter((f) => f.endsWith('.node'))

    if (toCopy.length === 0) {
      console.error('错误: 在 native 目录中未找到 .node 二进制模块。无法继续构建。')
      process.exit(1)
    }

    for (const file of toCopy) {
      const src = path.join(SRC_DIR, file)
      const dest = path.join(DEST_DIR, file)
      await fs.copy(src, dest)
      console.log(`已复制: ${file} -> resources/native/`)
    }

    console.log('Native 渲染核心准备就绪！')
  } catch (e) {
    console.error('复制 Native 核心失败:', e.message)
    process.exit(1)
  }
}

copyNative()
