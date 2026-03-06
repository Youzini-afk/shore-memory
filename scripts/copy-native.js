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

    // 定义要复制的文件列表 (napi-rs 输出标准)
    // 我们复制 index.js, package.json 以及所有的 .node 文件
    const files = await fs.readdir(SRC_DIR)
    const toCopy = files.filter(f => 
      f === 'index.js' || 
      f === 'package.json' || 
      f.endsWith('.node')
    )

    if (toCopy.length === 0) {
      console.warn('警告: 在 native 目录中未找到构建产物。请先运行 npm run build:native。')
      // 如果是在 GitHub Actions 中，这可能是一个错误
      if (process.env.GITHUB_ACTIONS) {
        process.exit(1)
      }
      return
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
