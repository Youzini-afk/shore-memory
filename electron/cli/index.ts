import { ServiceManager } from './serviceManager'
import { parseArgs } from '../main/utils/args'
import { TuiManager } from './tui/tuiManager'

export function startCli() {
  // 覆盖 console 以防止干扰 TUI
  // 我们静音控制台输出，因为服务 (python.ts 等) 使用 console.log
  // 这会破坏 TUI 布局。
  // 我们依赖 ServiceManager 事件来获取日志。
  console.log = () => {}
  console.error = () => {}
  console.warn = () => {}
  console.info = () => {}

  const args = parseArgs(process.argv)
  const manager = new ServiceManager()

  // 初始化 TUI
  const tui = new TuiManager(manager)

  tui.log('PeroCore CLI 模式正在初始化...')
  tui.log(`参数: ${JSON.stringify(args)}`)

  // 启动服务
  manager.startAll(args).catch((err) => {
    tui.log(`启动错误: ${err.message}`)
  })
}

// 如果直接通过 Node 运行，则自动启动
if (require.main === module) {
  startCli()
}
