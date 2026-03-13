/* eslint-disable @typescript-eslint/no-require-imports */
const fs = require('fs')
const path = require('path')
const { execSync } = require('child_process')
const https = require('https')
const AdmZip = require('adm-zip')

// 检测 GitHub Actions 环境
const IS_GITHUB_ACTIONS = process.env.GITHUB_ACTIONS === 'true'

const PYTHON_VERSION = '3.10.11'
// 使用淘宝镜像加速 Python 下载 (仅非 GitHub Actions 环境)
const PYTHON_MIRROR = 'https://npmmirror.com/mirrors/python'
const PYTHON_OFFICIAL = 'https://www.python.org/ftp/python'
const PYTHON_BASE_URL = IS_GITHUB_ACTIONS ? PYTHON_OFFICIAL : PYTHON_MIRROR
const PYTHON_URL = `${PYTHON_BASE_URL}/${PYTHON_VERSION}/python-${PYTHON_VERSION}-embed-amd64.zip`

const PROJECT_ROOT = path.resolve(__dirname, '..')
const RESOURCES_DIR = path.join(PROJECT_ROOT, 'resources')
const PYTHON_DEST = path.join(RESOURCES_DIR, 'python')
const SITE_PACKAGES = path.join(PYTHON_DEST, 'Lib', 'site-packages')
const BACKEND_DIR = path.join(PROJECT_ROOT, 'backend')

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

async function downloadFile(url, dest, maxRedirects = 5) {
  return new Promise((resolve, reject) => {
    https
      .get(url, { maxRedirects: 0 }, (response) => {
        // 处理重定向 (301, 302, 303, 307, 308)
        if ([301, 302, 303, 307, 308].includes(response.statusCode)) {
          if (maxRedirects <= 0) {
            reject(new Error('重定向次数过多'))
            return
          }
          const location = response.headers.location
          log(`检测到重定向：${response.statusCode} -> ${location}`, 'info')
          downloadFile(location, dest, maxRedirects - 1)
            .then(resolve)
            .catch(reject)
          return
        }

        if (response.statusCode !== 200) {
          reject(new Error(`Failed to download: ${response.statusCode}`))
          return
        }

        const file = fs.createWriteStream(dest)
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

// 如果不在 GitHub Actions 中，则仅使用清华镜像
const PIP_INDEX_ARGS = IS_GITHUB_ACTIONS ? '' : '-i https://pypi.tuna.tsinghua.edu.cn/simple'

async function setupPython() {
  log('步骤 1: 设置嵌入式 Python 环境...')

  ensureDir(PYTHON_DEST)
  const zipPath = path.join(RESOURCES_DIR, 'python.zip')
  const getPipPath = path.join(RESOURCES_DIR, 'get-pip.py')
  const pythonExe = path.join(PYTHON_DEST, 'python.exe')

  // 检查 Python 是否已安装
  if (fs.existsSync(pythonExe)) {
    log('Python 环境似乎已设置。', 'warning')
  } else {
    log(`正在下载 Python ${PYTHON_VERSION}...`)
    try {
      await downloadFile(PYTHON_URL, zipPath)
      log('下载完成。正在解压...')

      const zip = new AdmZip(zipPath)
      zip.extractAllTo(PYTHON_DEST, true)

      fs.unlinkSync(zipPath) // 清理
      log('解压完成。', 'success')
    } catch (e) {
      log(`Python 设置失败: ${e.message}`, 'error')
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
      log('已更新 .pth 文件以启用 site-packages。', 'success')
    }
  }

  // 安装 pip 和 uv
  try {
    // 1. 检查/安装 pip
    try {
      execSync(`"${pythonExe}" -m pip --version`, { stdio: 'ignore' })
      log('嵌入式 Python 中已安装 pip。', 'success')
    } catch {
      log('未找到 pip。正在通过 get-pip.py 安装...')
      // 下载 get-pip.py
      await downloadFile(GET_PIP_URL, getPipPath)
      // 使用清华源加速安装 pip (仅非 GitHub Actions 环境)
      execSync(`"${pythonExe}" "${getPipPath}" --no-warn-script-location ${PIP_INDEX_ARGS}`, {
        stdio: 'inherit'
      })
      fs.unlinkSync(getPipPath)
    }

    // 2. 安装 uv
    try {
      execSync(`"${pythonExe}" -m pip show uv`, { stdio: 'ignore' })
      log('uv 已安装。', 'success')
    } catch {
      log('正在安装 uv...')
      // 使用清华源 (仅非 GitHub Actions 环境)
      execSync(`"${pythonExe}" -m pip install uv --no-warn-script-location ${PIP_INDEX_ARGS}`, {
        stdio: 'inherit'
      })
    }
    // 3. 安装构建工具 (maturin)
    try {
      execSync(`"${pythonExe}" -m pip show maturin`, { stdio: 'ignore' })
    } catch {
      log('正在安装 maturin...')
      // 使用清华源 (仅非 GitHub Actions 环境)
      execSync(
        `"${pythonExe}" -m pip install maturin --no-warn-script-location ${PIP_INDEX_ARGS}`,
        {
          stdio: 'inherit'
        }
      )
    }
  } catch (err) {
    log(`设置 pip/uv 失败: ${err.message}`, 'error')
    process.exit(1)
  }
}

function installDependencies() {
  log('步骤 2: 通过 uv 安装 Python 依赖...')

  ensureDir(SITE_PACKAGES)
  const pythonExe = path.join(PYTHON_DEST, 'python.exe')

  try {
    // 使用 uv sync 从 pyproject.toml 安装依赖
    // 我们使用 `python -m uv pip sync` 或类似方法安装到当前环境
    // 由于我们处于嵌入式环境，应该指示 uv 安装到其中。

    log('正在从 pyproject.toml 同步依赖...')
    // 注意：对于嵌入式 Python，我们可以使用等同于 `uv pip install -r pyproject.toml` 的命令
    // 但 uv sync 依赖于 virtualenv。在这里，我们本质上是将嵌入式 Python 视为 venv。
    // 所以我们使用 `uv pip install` 针对系统进行安装。

    // 然而，标准的 `uv sync` 管理它自己的 .venv。
    // 策略：我们使用 `uv pip install .` 将项目及其依赖项安装到嵌入式 Python 中。

    // 我们需要确保使用安装在嵌入式 Python 中的 uv
    // 命令：python.exe -m uv pip install . --system（如果我们想安装到系统，但这已经是嵌入式的，所以它就是系统）
    // 实际上对于嵌入式 Python，只要我们指向它，`uv pip install` 就可以工作。
    // 使用清华源 (仅非 GitHub Actions 环境)
    const env = { ...process.env }
    if (!IS_GITHUB_ACTIONS) {
      env.UV_INDEX_URL = 'https://pypi.tuna.tsinghua.edu.cn/simple'
    }

    execSync(`"${pythonExe}" -m uv pip install "${BACKEND_DIR}"`, { stdio: 'inherit', env })

    log('依赖已通过 uv 成功安装。', 'success')
  } catch (e) {
    log(`安装依赖失败: ${e.message}`, 'error')
    process.exit(1)
  }
}

function buildRustExtensions() {
  log('步骤 3: 构建/安装 Rust 核心扩展...')

  const pythonExe = path.join(PYTHON_DEST, 'python.exe')

  // 检查嵌入式 Python 中的 maturin
  try {
    execSync(`"${pythonExe}" -m maturin --version`, { stdio: 'ignore' })
  } catch {
    log('在嵌入式 Python 中未找到 Maturin。正在安装...', 'warning')
    execSync(`"${pythonExe}" -m pip install maturin ${PIP_INDEX_ARGS}`, {
      stdio: 'inherit'
    })
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
    },
    {
      name: 'pero_social_core',
      path: path.join(BACKEND_DIR, 'social_core', 'Cargo.toml'),
      dir: path.join(BACKEND_DIR, 'social_core')
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
      log(`正在构建 ${ext.name}...`)
      try {
        // 使用嵌入式 Python 的 maturin 构建 wheel
        // 我们使用 --interpreter 确保它是为我们的嵌入式 Python 版本构建的

        // 确保 maturin 已安装
        try {
          execSync(`"${pythonExe}" -m maturin --version`, { stdio: 'ignore' })
        } catch {
          log('正在安装 maturin...', 'warning')
          execSync(`"${pythonExe}" -m pip install maturin ${PIP_INDEX_ARGS}`, { stdio: 'inherit' })
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
          log(`正在安装 ${wheel}...`)
          const wheelPath = path.join(distDir, wheel)
          execSync(`"${pythonExe}" -m pip install "${wheelPath}" --force-reinstall --no-deps`, {
            stdio: 'inherit'
          })
          // 清理 wheel
          fs.unlinkSync(wheelPath)
        } else {
          log(`未找到 ${ext.name} 的 wheel`, 'error')
        }
      } catch (e) {
        log(`构建/安装 ${ext.name} 失败: ${e.message}`, 'error')
      }
    }
  }

  // 清理 dist 目录
  if (fs.existsSync(distDir) && fs.readdirSync(distDir).length === 0) {
    fs.rmdirSync(distDir)
  }
}

function buildBinaryTools() {
  log('步骤 4: 构建二进制工具...')

  // 检查并复制现有二进制文件的辅助函数
  const checkAndCopy = (srcDirs, dest, name) => {
    for (const dir of srcDirs) {
      const possiblePath = path.join(dir, name)
      if (fs.existsSync(possiblePath)) {
        log(`在 ${possiblePath} 发现 ${name} 的现有二进制文件。正在复用...`, 'success')
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
      log('正在构建 CodeSearcher...')
      try {
        execSync(
          `cargo build --release --manifest-path "${path.join(codeSearcherSrc, 'Cargo.toml')}"`,
          { stdio: 'inherit' }
        )
        // 构建后再次尝试复制
        if (!checkAndCopy(searchPaths, codeSearcherDest, 'CodeSearcher.exe')) {
          log('构建后仍无法定位 CodeSearcher.exe', 'error')
        }
      } catch (e) {
        log(`构建 CodeSearcher 失败: ${e.message}`, 'error')
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
      log('正在构建 nit_terminal_auditor (Wasm)...')
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
          log('无法定位已构建的 nit_terminal_auditor.wasm', 'error')
        }
      } catch (e) {
        log(`构建 nit_terminal_auditor 失败: ${e.message}`, 'error')
      }
    }
  }
}

async function main() {
  log('开始本地后端构建流程...', 'bright')

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
