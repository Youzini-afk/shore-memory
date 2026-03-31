const fs = require('fs')
const path = require('path')

const envPath = path.join(__dirname, '../.env')
const pkgPath = path.join(__dirname, '../package.json')
const pyTomlPath = path.join(__dirname, '../backend/pyproject.toml')

let version = '0.8.54' // Default fallback

// 1. Read version from .env
if (fs.existsSync(envPath)) {
  const envContent = fs.readFileSync(envPath, 'utf-8')
  // Match PERO_VERSION=x.y.z
  const match = envContent.match(/^PERO_VERSION\s*=\s*(.+)$/m)
  if (match) {
    version = match[1].replace(/['"]/g, '').trim()
  } else {
    console.log('[Version Sync] PERO_VERSION not found in .env, using default version:', version)
  }
} else {
  console.log('[Version Sync] .env not found, using default version:', version)
}

function updateVersion() {
  let updated = false

  // 2. Update package.json
  if (fs.existsSync(pkgPath)) {
    const pkg = JSON.parse(fs.readFileSync(pkgPath, 'utf8'))
    if (pkg.version !== version) {
      pkg.version = version
      fs.writeFileSync(pkgPath, JSON.stringify(pkg, null, 2) + '\n')
      console.log(`[Version Sync] package.json updated to ${version}`)
      updated = true
    }
  }

  // 3. Update TOML configs (Python and Rust)
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
      let content = fs.readFileSync(fullPath, 'utf8')
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
