/* eslint-disable @typescript-eslint/no-require-imports */
/**
 * electron-builder afterPack hook
 * 仅在 portable 构建模式下，将 .portable 标记文件放入 exe 同级目录。
 * 这样 env.ts 的 detectPortableMode() 才能正确检测到便携模式，
 * 确保数据目录使用本地 data/ 而不是 %APPDATA%。
 */
const fs = require('fs')
const path = require('path')

exports.default = async function (context) {
  // 只在 --dir (portable) 模式下写入标记文件
  // 在 nsis 安装模式下不需要这个文件
  const isDir = context.targets?.some(
    (t) => t.name === 'dir'
  )

  if (!isDir) {
    console.log('[AfterPack] 非 dir 模式，跳过 .portable 标记注入')
    return
  }

  const appOutDir = context.appOutDir
  const portableMarker = path.join(appOutDir, '.portable')

  try {
    fs.writeFileSync(portableMarker, 'PORTABLE_MODE=1\n', 'utf-8')
    console.log(`[AfterPack] ✅ .portable 标记文件已写入: ${portableMarker}`)
  } catch (e) {
    console.error(`[AfterPack] ❌ 写入 .portable 标记文件失败: ${e.message}`)
  }
}
