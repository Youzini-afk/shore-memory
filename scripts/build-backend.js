/* eslint-disable @typescript-eslint/no-require-imports */
const fs = require('fs')
const path = require('path')
const { execSync } = require('child_process')
const https = require('https')
const AdmZip = require('adm-zip')

// Configuration
// 配置
const PYTHON_VERSION = '3.10.11'
const PYTHON_URL = `https://www.python.org/ftp/python/${PYTHON_VERSION}/python-${PYTHON_VERSION}-embed-amd64.zip`
const PROJECT_ROOT = path.resolve(__dirname, '..')
const RESOURCES_DIR = path.join(PROJECT_ROOT, 'resources')
const PYTHON_DEST = path.join(RESOURCES_DIR, 'python')
const SITE_PACKAGES = path.join(PYTHON_DEST, 'Lib', 'site-packages')
const BACKEND_DIR = path.join(PROJECT_ROOT, 'backend')

// Colors for console output
// 控制台输出颜色
const colors = {
  reset: '\x1b[0m',
  bright: '\x1b[1m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  red: '\x1b[31m',
  cyan: '\x1b[36m'
}

function log(message, type = 'info') {
  const timestamp = new Date().toLocaleTimeString()
  const color =
    type === 'error'
      ? colors.red
      : type === 'success'
        ? colors.green
        : type === 'warning'
          ? colors.yellow
          : colors.cyan
  console.log(`${colors.bright}[${timestamp}] ${color}${message}${colors.reset}`)
}

async function downloadFile(url, dest) {
  return new Promise((resolve, reject) => {
    const file = fs.createWriteStream(dest)
    https
      .get(url, (response) => {
        if (response.statusCode !== 200) {
          reject(new Error(`Failed to download: ${response.statusCode}`))
          return
        }
        response.pipe(file)
        file.on('finish', () => {
          file.close()
          resolve()
        })
      })
      .on('error', (err) => {
        fs.unlink(dest, () => {})
        reject(err)
      })
  })
}

function ensureDir(dir) {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true })
  }
}

const GET_PIP_URL = 'https://bootstrap.pypa.io/get-pip.py'

async function setupPython() {
  log('Step 1: Setting up Embedded Python Environment...')

  ensureDir(PYTHON_DEST)
  const zipPath = path.join(RESOURCES_DIR, 'python.zip')
  const getPipPath = path.join(RESOURCES_DIR, 'get-pip.py')
  const pythonExe = path.join(PYTHON_DEST, 'python.exe')

  // 检查 Python 是否已安装
  if (fs.existsSync(pythonExe)) {
    log('Python environment appears to be already set up.', 'warning')
  } else {
    log(`Downloading Python ${PYTHON_VERSION}...`)
    try {
      await downloadFile(PYTHON_URL, zipPath)
      log('Download complete. Extracting...')

      const zip = new AdmZip(zipPath)
      zip.extractAllTo(PYTHON_DEST, true)

      fs.unlinkSync(zipPath) // 清理
      log('Extraction complete.', 'success')
    } catch (e) {
      log(`Failed to setup Python: ${e.message}`, 'error')
      process.exit(1)
    }
  }

  // 配置 .pth 文件以启用 site-packages
  const pthFile = path.join(
    PYTHON_DEST,
    `python${PYTHON_VERSION.split('.').slice(0, 2).join('')}._pth`
  )
  if (fs.existsSync(pthFile)) {
    let content = fs.readFileSync(pthFile, 'utf8')
    if (content.includes('#import site')) {
      content = content.replace('#import site', 'import site')
      fs.writeFileSync(pthFile, content)
      log('Updated .pth file to enable site-packages.', 'success')
    }
  }

  // 安装 pip 和 uv
  try {
    // 1. 检查/安装 pip
    try {
      execSync(`"${pythonExe}" -m pip --version`, { stdio: 'ignore' })
      log('pip is already installed in embedded Python.', 'success')
    } catch {
      log('pip not found. Installing via get-pip.py...')
      await downloadFile(GET_PIP_URL, getPipPath)
      execSync(`"${pythonExe}" "${getPipPath}" --no-warn-script-location`, { stdio: 'inherit' })
      fs.unlinkSync(getPipPath)
    }

    // 2. 安装 uv
    try {
      execSync(`"${pythonExe}" -m pip show uv`, { stdio: 'ignore' })
      log('uv is already installed.', 'success')
    } catch {
      log('Installing uv...')
      execSync(`"${pythonExe}" -m pip install uv --no-warn-script-location`, {
        stdio: 'inherit'
      })
    }
    // 3. 安装构建工具 (maturin)
    try {
      execSync(`"${pythonExe}" -m pip show maturin`, { stdio: 'ignore' })
    } catch {
      log('Installing maturin...')
      execSync(`"${pythonExe}" -m pip install maturin --no-warn-script-location`, {
        stdio: 'inherit'
      })
    }
  } catch (err) {
    log(`Failed to setup pip/uv: ${err.message}`, 'error')
    process.exit(1)
  }
}

function installDependencies() {
  log('Step 2: Installing Python Dependencies via uv...')

  ensureDir(SITE_PACKAGES)
  const pythonExe = path.join(PYTHON_DEST, 'python.exe')

  try {
    // 使用 uv sync 从 pyproject.toml 安装依赖
    // 我们使用 `python -m uv pip sync` 或类似方法安装到当前环境
    // 由于我们处于嵌入式环境，应该指示 uv 安装到其中。

    log('Syncing dependencies from pyproject.toml...')
    // 注意：对于嵌入式 Python，我们可以使用等同于 `uv pip install -r pyproject.toml` 的命令
    // 但 uv sync 依赖于 virtualenv。在这里，我们本质上是将嵌入式 Python 视为 venv。
    // 所以我们使用 `uv pip install` 针对系统进行安装。

    // 然而，标准的 `uv sync` 管理它自己的 .venv。
    // 策略：我们使用 `uv pip install .` 将项目及其依赖项安装到嵌入式 Python 中。

    // 我们需要确保使用安装在嵌入式 Python 中的 uv
    // 命令：python.exe -m uv pip install . --system（如果我们想安装到系统，但这已经是嵌入式的，所以它就是系统）
    // 实际上对于嵌入式 Python，只要我们指向它，`uv pip install` 就可以工作。

    execSync(`"${pythonExe}" -m uv pip install "${BACKEND_DIR}"`, { stdio: 'inherit' })

    log('Dependencies installed successfully via uv.', 'success')
  } catch (e) {
    log(`Failed to install dependencies: ${e.message}`, 'error')
    process.exit(1)
  }
}

function buildRustExtensions() {
  log('Step 3: Building/Installing Rust Core Extensions...')

  const pythonExe = path.join(PYTHON_DEST, 'python.exe')

  // 检查嵌入式 Python 中的 maturin
  try {
    execSync(`"${pythonExe}" -m maturin --version`, { stdio: 'ignore' })
  } catch {
    log('Maturin not found in embedded Python. Installing...', 'warning')
    execSync(`"${pythonExe}" -m pip install maturin`, { stdio: 'inherit' })
  }

  const extensions = [
    {
      name: 'pero_memory_core',
      path: path.join(BACKEND_DIR, 'rust_core', 'Cargo.toml'),
      dir: path.join(BACKEND_DIR, 'rust_core')
    },
    {
      name: 'pero_vision_core',
      path: path.join(BACKEND_DIR, 'vision_core', 'Cargo.toml'),
      dir: path.join(BACKEND_DIR, 'vision_core')
    },
    {
      name: 'nit_rust_runtime',
      path: path.join(BACKEND_DIR, 'nit_core', 'interpreter', 'rust_binding', 'Cargo.toml'),
      dir: path.join(BACKEND_DIR, 'nit_core', 'interpreter', 'rust_binding')
    }
  ]

  const distDir = path.join(PROJECT_ROOT, 'dist_wheels')
  ensureDir(distDir)

  for (const ext of extensions) {
    if (!fs.existsSync(ext.path)) {
      log(`Skipping ${ext.name} (Cargo.toml not found)`, 'warning')
      continue
    }

    // In CI, if the package is already installed, skip building to avoid double-build issues
    // (The YAML workflow already builds and installs them using the system python)
    if (process.env.CI) {
      let installed = false
      try {
        execSync(`"${pythonExe}" -m pip show ${ext.name}`, { stdio: 'ignore' })
        installed = true
      } catch {
        try {
          const pkgName = ext.name.replace(/_/g, '-')
          execSync(`"${pythonExe}" -m pip show ${pkgName}`, { stdio: 'ignore' })
          installed = true
        } catch {
          // 忽略安装检查失败
        }
      }

      if (installed) {
        log(`${ext.name} is already installed (CI detected). Skipping rebuild.`, 'success')
        continue
      }
    }

    // 尝试在 target/wheels 中查找现有的 wheel 以重用
    const targetWheelsDir = path.join(ext.dir, 'target', 'wheels')
    let reused = false

    if (fs.existsSync(targetWheelsDir)) {
      const wheels = fs.readdirSync(targetWheelsDir).filter((f) => f.endsWith('.whl'))
      if (wheels.length > 0) {
        // 按时间排序，最新的在先
        wheels.sort((a, b) => {
          return (
            fs.statSync(path.join(targetWheelsDir, b)).mtime.getTime() -
            fs.statSync(path.join(targetWheelsDir, a)).mtime.getTime()
          )
        })
        const latestWheel = path.join(targetWheelsDir, wheels[0])
        log(`Found existing wheel for ${ext.name}: ${wheels[0]}. Reusing...`, 'success')

        try {
          execSync(`"${pythonExe}" -m pip install "${latestWheel}" --force-reinstall --no-deps`, {
            stdio: 'inherit'
          })
          reused = true
        } catch (e) {
          log(`Failed to install existing wheel: ${e.message}. Will attempt rebuild.`, 'warning')
        }
      }
    }

    if (!reused) {
      log(`Building ${ext.name}...`)
      try {
        // 使用嵌入式 Python 的 maturin 构建 wheel
        // 我们使用 --interpreter 确保它是为我们的嵌入式 Python 版本构建的

        // 确保 maturin 已安装
        try {
          execSync(`"${pythonExe}" -m maturin --version`, { stdio: 'ignore' })
        } catch {
          log('Installing maturin...', 'warning')
          execSync(`"${pythonExe}" -m pip install maturin`, { stdio: 'inherit' })
        }

        execSync(
          `"${pythonExe}" -m maturin build --release --manifest-path "${ext.path}" --out "${distDir}" --interpreter "${pythonExe}"`,
          { stdio: 'inherit' }
        )

        // 查找生成的 wheel
        const files = fs.readdirSync(distDir)
        const wheel = files.find(
          (f) => f.includes(ext.name.replace(/-/g, '_')) && f.endsWith('.whl')
        ) // Rust crate 名称使用下划线

        if (wheel) {
          log(`Installing ${wheel}...`)
          const wheelPath = path.join(distDir, wheel)
          execSync(`"${pythonExe}" -m pip install "${wheelPath}" --force-reinstall --no-deps`, {
            stdio: 'inherit'
          })
          // 清理 wheel
          fs.unlinkSync(wheelPath)
        } else {
          log(`Failed to find wheel for ${ext.name}`, 'error')
        }
      } catch (e) {
        log(`Failed to build/install ${ext.name}: ${e.message}`, 'error')
      }
    }
  }

  // 清理 dist 目录
  if (fs.existsSync(distDir) && fs.readdirSync(distDir).length === 0) {
    fs.rmdirSync(distDir)
  }
}

function buildBinaryTools() {
  log('Step 4: Building Binary Tools...')

  // 检查并复制现有二进制文件的辅助函数
  const checkAndCopy = (srcDirs, dest, name) => {
    for (const dir of srcDirs) {
      const possiblePath = path.join(dir, name)
      if (fs.existsSync(possiblePath)) {
        log(`Found existing binary for ${name} at ${possiblePath}. Reusing...`, 'success')
        fs.copyFileSync(possiblePath, dest)
        return true
      }
    }
    return false
  }

  // 1. CodeSearcher
  const codeSearcherSrc = path.join(BACKEND_DIR, 'nit_core/tools/work/CodeSearcher/src')
  const codeSearcherDest = path.join(
    BACKEND_DIR,
    'nit_core/tools/work/CodeSearcher/CodeSearcher.exe'
  )

  if (fs.existsSync(path.join(codeSearcherSrc, 'Cargo.toml'))) {
    // 首先检查现有的
    const searchPaths = [
      path.join(codeSearcherSrc, 'target/release'),
      path.join(codeSearcherSrc, '../target/release'),
      path.join(PROJECT_ROOT, 'target/release')
    ]

    if (!checkAndCopy(searchPaths, codeSearcherDest, 'CodeSearcher.exe')) {
      log('Building CodeSearcher...')
      try {
        execSync(
          `cargo build --release --manifest-path "${path.join(codeSearcherSrc, 'Cargo.toml')}"`,
          { stdio: 'inherit' }
        )
        // 构建后再次尝试复制
        if (!checkAndCopy(searchPaths, codeSearcherDest, 'CodeSearcher.exe')) {
          log('Could not locate built CodeSearcher.exe even after build', 'error')
        }
      } catch (e) {
        log(`Failed to build CodeSearcher: ${e.message}`, 'error')
      }
    }
  }

  // 2. nit_terminal_auditor (Wasm)
  const auditorSrc = path.join(BACKEND_DIR, 'nit_core/nit_terminal_auditor')
  const auditorDest = path.join(BACKEND_DIR, 'nit_core/tools/work/TerminalExecutor/auditor.wasm')

  if (fs.existsSync(path.join(auditorSrc, 'Cargo.toml'))) {
    const searchPaths = [
      path.join(auditorSrc, 'target/wasm32-unknown-unknown/release'),
      path.join(PROJECT_ROOT, 'target/wasm32-unknown-unknown/release')
    ]

    if (!checkAndCopy(searchPaths, auditorDest, 'nit_terminal_auditor.wasm')) {
      log('Building nit_terminal_auditor (Wasm)...')
      try {
        try {
          execSync('rustup target add wasm32-unknown-unknown', { stdio: 'ignore' })
        } catch {
          // 忽略 target 已存在的错误
        }

        execSync(
          `cargo build --release --target wasm32-unknown-unknown --manifest-path "${path.join(auditorSrc, 'Cargo.toml')}"`,
          { stdio: 'inherit' }
        )

        if (!checkAndCopy(searchPaths, auditorDest, 'nit_terminal_auditor.wasm')) {
          log('Could not locate built nit_terminal_auditor.wasm', 'error')
        }
      } catch (e) {
        log(`Failed to build nit_terminal_auditor: ${e.message}`, 'error')
      }
    }
  }
}

async function main() {
  log('Starting Local Backend Build Process...', 'bright')

  await setupPython()
  installDependencies()
  buildRustExtensions()
  buildBinaryTools()

  log('Backend Build Process Completed!', 'success')
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})
