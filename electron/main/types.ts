export interface WindowLike {
  isDestroyed(): boolean
  webContents: {
    send(channel: string, ...args: any[]): void
  }
}
