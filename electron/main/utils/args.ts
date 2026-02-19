export interface CliArgs {
  debug: boolean
  noNapcat: boolean
  noGateway: boolean
  port: number
}

export function parseArgs(argv: string[]): CliArgs {
  const args: CliArgs = {
    debug: argv.includes('--debug'),
    noNapcat: argv.includes('--no-napcat'),
    noGateway: argv.includes('--no-gateway'),
    port: 9120 // 默认端口
  }

  // 解析特定值
  const portIndex = argv.indexOf('--port')
  if (portIndex !== -1 && portIndex + 1 < argv.length) {
    const portVal = parseInt(argv[portIndex + 1], 10)
    if (!isNaN(portVal)) {
      args.port = portVal
    }
  }

  return args
}
