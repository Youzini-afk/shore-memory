/* eslint-disable @typescript-eslint/no-require-imports */
const fs = require('fs')
const path = require('path')
const { execSync } = require('child_process')

const DEST_DIR = path.join(__dirname, '../resources/bin')
const GATEWAY_SRC_DIR = path.join(__dirname, '../gateway') // 内部网关源码
// const GATEWAY_SRC_FILE = path.join(GATEWAY_SRC_DIR, 'gateway.exe')
const GATEWAY_DEST_FILE = path.join(DEST_DIR, 'gateway.exe')

console.log('Checking Gateway binary...')

// 确保目标目录存在
if (!fs.existsSync(DEST_DIR)) {
  fs.mkdirSync(DEST_DIR, { recursive: true })
}

console.log('Building/Copying gateway from internal source:', GATEWAY_SRC_DIR)

if (fs.existsSync(path.join(GATEWAY_SRC_DIR, 'gateway/main.go'))) {
  try {
    // Check if Go is installed
    try {
      execSync('go version', { stdio: 'ignore' })
    } catch {
      console.warn('Warning: Go is not installed or not in PATH. Skipping Gateway build.')
      if (!fs.existsSync(GATEWAY_DEST_FILE)) {
        console.error('Error: Gateway binary not found and Go is not available to build it.')
        process.exit(1)
      }
      // If binary exists, use it
      return
    }

    console.log('Running go build...')
    // Ensure destination directory exists
    if (!fs.existsSync(DEST_DIR)) {
      fs.mkdirSync(DEST_DIR, { recursive: true })
    }

    // 直接构建到目标位置
    execSync(`go build -o "${GATEWAY_DEST_FILE}" ./gateway`, {
      cwd: GATEWAY_SRC_DIR,
      stdio: 'inherit'
    })

    if (fs.existsSync(GATEWAY_DEST_FILE)) {
      console.log('Build successful! Gateway placed at:', GATEWAY_DEST_FILE)
    } else {
      console.error('Build failed to produce gateway.exe')
      process.exit(1)
    }
  } catch (e) {
    console.error('Failed to build gateway:', e.message)
    process.exit(1)
  }
} else {
  console.error('Gateway source not found at ' + GATEWAY_SRC_DIR)
  process.exit(1)
}
