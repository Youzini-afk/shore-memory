import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

// ES Module 下没有 __dirname，需要手动构造
const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

const envPath = path.join(__dirname, '../.env')
const pkgPath = path.join(__dirname, '../package.json')

// 1. 将 package.json 作为唯一的版本事实来源
if (!fs.existsSync(pkgPath)) {
  console.error('[Version Sync] package.json not found! Expected at:', pkgPath)
  process.exit(1)
}

const pkg = JSON.parse(fs.readFileSync(pkgPath, 'utf8'))
const version = pkg.version

console.log(`[Version Sync] Source of truth -> package.json: ${version}`)

function updateVersion() {
  let updated = false

  // 2. 同步到 .env (让后端能读取到一致的环境变量)
  if (fs.existsSync(envPath)) {
    const envContent = fs.readFileSync(envPath, 'utf-8')
    const match = envContent.match(/^PERO_VERSION\s*=\s*(.+)$/m)
    if (match) {
      const oldEnvVersion = match[1].replace(/['"]/g, '').trim()
      if (oldEnvVersion !== version) {
        const newEnvContent = envContent.replace(
          /^PERO_VERSION\s*=\s*(.+)$/m,
          `PERO_VERSION=${version}`
        )
        fs.writeFileSync(envPath, newEnvContent)
        console.log(`[Version Sync] .env updated to ${version}`)
        updated = true
      }
    } else {
      // 如果没有这个字段，直接追加
      fs.appendFileSync(envPath, `\nPERO_VERSION=${version}\n`)
      console.log(`[Version Sync] .env updated to ${version} (appended)`)
      updated = true
    }
  }

  // 3. 更新所有 TOML 配置（Python & Rust）
  const tomlPaths = [
    '../backend/pyproject.toml',
    '../backend/vision_core/pyproject.toml',
    '../backend/vision_core/Cargo.toml',
    '../backend/nit_core/interpreter/rust_binding/pyproject.toml',
    '../backend/nit_core/interpreter/rust_binding/Cargo.toml',
    '../backend/nit_core/nit_terminal_auditor/Cargo.toml',
    '../backend/nit_core/tools/work/CodeSearcher/src/Cargo.toml'
  ]

  for (const relPath of tomlPaths) {
    const fullPath = path.join(__dirname, relPath)
    if (fs.existsSync(fullPath)) {
      const content = fs.readFileSync(fullPath, 'utf8')
      // 匹配行首的 version = "..."
      const replaced = content.replace(/^version\s*=\s*".*"/m, `version = "${version}"`)
      if (content !== replaced) {
        fs.writeFileSync(fullPath, replaced)
        console.log(`[Version Sync] ${relPath.replace('../', '')} updated to ${version}`)
        updated = true
      }
    }
  }

  if (!updated) {
    console.log(`[Version Sync] All versions are already up-to-date (${version})`)
  }
}

updateVersion()
