
import { ServiceManager } from './serviceManager'
import { parseArgs } from '../main/utils/args'
import { TuiManager } from './tui/tuiManager'

export function startCli() {
    // Override console to prevent interference with TUI
    // We mute console output because services (python.ts, etc.) use console.log 
    // which would corrupt the TUI layout. 
    // We rely on ServiceManager events for logs.
    console.log = () => {}
    console.error = () => {}
    console.warn = () => {}
    console.info = () => {}
    
    const args = parseArgs(process.argv)
    const manager = new ServiceManager()
    
    // Initialize TUI
    const tui = new TuiManager(manager)

    tui.log('PeroCore CLI Mode Initializing...')
    tui.log(`Args: ${JSON.stringify(args)}`)

    // Start Services
    manager.startAll(args).catch(err => {
        tui.log(`Startup Error: ${err.message}`)
    })
}

// Auto-start if running directly via Node
if (require.main === module) {
    startCli()
}
