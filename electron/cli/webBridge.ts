import http from 'http'
import { WebSocketServer, WebSocket } from 'ws'
import fs from 'fs'
import path from 'path'
import { ipcRegistry } from '../main/utils/ipcRegistry'
import { paths } from '../main/utils/env'
import mime from 'mime-types'

export class WebBridge {
  private server: http.Server
  private wss: WebSocketServer
  private port: number
  private staticRoot: string

  constructor(port: number = 9120) {
    this.port = port
    // Default to serving dist (frontend build) if it exists, otherwise a placeholder
    this.staticRoot = path.join(paths.app, 'dist')

    this.server = http.createServer(this.handleRequest.bind(this))
    this.wss = new WebSocketServer({ server: this.server })

    this.setupWebSocket()
  }

  private setupWebSocket() {
    this.wss.on('connection', (ws) => {
      // console.log('[WebBridge] Client connected')

      ws.on('message', async (message) => {
        try {
          const data = JSON.parse(message.toString())
          // Handle WS-based IPC invoke (optional, if we want full duplex via WS)
          if (data.type === 'invoke' && data.channel) {
            try {
              const result = await ipcRegistry.invoke(data.channel, ...(data.args || []))
              ws.send(
                JSON.stringify({
                  type: 'response',
                  id: data.id,
                  result
                })
              )
            } catch (e: any) {
              ws.send(
                JSON.stringify({
                  type: 'error',
                  id: data.id,
                  error: e.message
                })
              )
            }
          }
        } catch (e) {
          // Ignore malformed
        }
      })
    })
  }

  private async handleRequest(req: http.IncomingMessage, res: http.ServerResponse) {
    // Enable CORS
    res.setHeader('Access-Control-Allow-Origin', '*')
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type')

    if (req.method === 'OPTIONS') {
      res.writeHead(200)
      res.end()
      return
    }

    const url = new URL(req.url || '/', `http://${req.headers.host}`)

    // API Routes
    if (url.pathname.startsWith('/api/ipc/')) {
      const channel = url.pathname.replace('/api/ipc/', '')

      if (req.method === 'POST') {
        let body = ''
        req.on('data', (chunk) => (body += chunk))
        req.on('end', async () => {
          try {
            const args = JSON.parse(body || '[]')
            const result = await ipcRegistry.invoke(channel, ...args)
            res.writeHead(200, { 'Content-Type': 'application/json' })
            res.end(JSON.stringify({ result }))
          } catch (e: any) {
            res.writeHead(500, { 'Content-Type': 'application/json' })
            res.end(JSON.stringify({ error: e.message }))
          }
        })
      } else {
        res.writeHead(405)
        res.end('Method Not Allowed')
      }
      return
    }

    // Static File Serving
    const filePath = path.join(this.staticRoot, url.pathname === '/' ? 'index.html' : url.pathname)

    // Security check: prevent directory traversal
    if (!filePath.startsWith(this.staticRoot)) {
      res.writeHead(403)
      res.end('Forbidden')
      return
    }

    if (fs.existsSync(filePath) && fs.statSync(filePath).isFile()) {
      const contentType = mime.lookup(filePath) || 'application/octet-stream'
      res.writeHead(200, { 'Content-Type': contentType })
      fs.createReadStream(filePath).pipe(res)
    } else {
      // SPA Fallback: serve index.html for non-API routes
      const indexPath = path.join(this.staticRoot, 'index.html')
      if (fs.existsSync(indexPath)) {
        res.writeHead(200, { 'Content-Type': 'text/html' })
        fs.createReadStream(indexPath).pipe(res)
      } else {
        res.writeHead(404)
        res.end('Not Found (and index.html missing)')
      }
    }
  }

  // Send message to all connected clients (simulating webContents.send)
  broadcast(channel: string, ...args: any[]) {
    const payload = JSON.stringify({
      type: 'event',
      channel,
      args
    })

    this.wss.clients.forEach((client) => {
      if (client.readyState === WebSocket.OPEN) {
        client.send(payload)
      }
    })
  }

  start() {
    return new Promise<void>((resolve, reject) => {
      this.server
        .listen(this.port, () => {
          console.log(`[WebBridge] Server running on http://localhost:${this.port}`)
          resolve()
        })
        .on('error', reject)
    })
  }

  stop() {
    return new Promise<void>((resolve) => {
      this.wss.close()
      this.server.close(() => resolve())
    })
  }
}
