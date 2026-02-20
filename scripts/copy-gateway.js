/* eslint-disable @typescript-eslint/no-require-imports */
const fs = require('fs')
const path = require('path')
const { execSync } = require('child_process')

const DEST_DIR = path.join(__dirname, '../resources/bin')
const GATEWAY_SRC_DIR = path.join(__dirname, '../gateway') // 内部网关源码
// const GATEWAY_SRC_FILE = path.join(GATEWAY_SRC_DIR, 'gateway.exe')
const GATEWAY_DEST_FILE = path.join(DEST_DIR, 'gateway.exe')

console.log('正在检查 Gateway 二进制文件...')

// 确保目标目录存在
if (!fs.existsSync(DEST_DIR)) {
  fs.mkdirSync(DEST_DIR, { recursive: true })
}

console.log('正在从内部源码构建/复制 Gateway:', GATEWAY_SRC_DIR)

if (fs.existsSync(path.join(GATEWAY_SRC_DIR, 'gateway/main.go'))) {
  try {
    // 检查 Go 是否已安装
    try {
      execSync('go version', { stdio: 'ignore' })
    } catch {
      console.warn('警告: Go 未安装或不在 PATH 中。跳过 Gateway 构建。')
      if (!fs.existsSync(GATEWAY_DEST_FILE)) {
        console.error('错误: 未找到 Gateway 二进制文件且无法使用 Go 构建。')
        process.exit(1)
      }
      // 如果二进制文件存在，则使用它
      return
    }

    console.log('正在运行 go build...')
    // 确保目标目录存在
    if (!fs.existsSync(DEST_DIR)) {
      fs.mkdirSync(DEST_DIR, { recursive: true })
    }

    // 直接构建到目标位置
    execSync(`go build -o "${GATEWAY_DEST_FILE}" ./gateway`, {
      cwd: GATEWAY_SRC_DIR,
      stdio: 'inherit'
    })

    if (fs.existsSync(GATEWAY_DEST_FILE)) {
      console.log('构建成功！Gateway 位于:', GATEWAY_DEST_FILE)
    } else {
      console.error('构建失败，未生成 gateway.exe')
      process.exit(1)
    }
  } catch (e) {
    console.error('构建 Gateway 失败:', e.message)
    process.exit(1)
  }
} else {
  console.error('未在以下位置找到 Gateway 源码: ' + GATEWAY_SRC_DIR)
  process.exit(1)
}
