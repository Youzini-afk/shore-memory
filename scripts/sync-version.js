const fs = require('fs')
const path = require('path')

const envPath = path.join(__dirname, '../.env')
const pkgPath = path.join(__dirname, '../package.json')
const pyTomlPath = path.join(__dirname, '../backend/pyproject.toml')

let version = '0.8.51' // Default fallback

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

  // 3. Update backend/pyproject.toml
  if (fs.existsSync(pyTomlPath)) {
    let pyToml = fs.readFileSync(pyTomlPath, 'utf8')
    const replaced = pyToml.replace(/^version\s*=\s*".*"/m, `version = "${version}"`)
    if (pyToml !== replaced) {
      fs.writeFileSync(pyTomlPath, replaced)
      console.log(`[Version Sync] backend/pyproject.toml updated to ${version}`)
      updated = true
    }
  }

  if (!updated) {
    console.log(`[Version Sync] All versions are already up-to-date (${version})`)
  }
}

updateVersion()
