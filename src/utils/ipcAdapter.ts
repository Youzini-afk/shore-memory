
declare global {
  interface Window {
    electron?: {
      invoke: (channel: string, ...args: any[]) => Promise<any>;
      on: (channel: string, listener: (event: any, ...args: any[]) => void) => () => void;
    };
  }
}

const isElectron = () => !!window.electron;

// Web Bridge Support
let ws: WebSocket | null = null;
const listeners = new Map<string, Set<(payload: any) => void>>();

const initWs = () => {
  if (isElectron() || ws) return;

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  // Use current host (works for Docker/CLI serving the frontend)
  const wsUrl = `${protocol}//${window.location.host}`;
  
  console.log('[IPC Adapter] Connecting to Web Bridge:', wsUrl);
  ws = new WebSocket(wsUrl);

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (data.type === 'event' && data.channel) {
        const handlers = listeners.get(data.channel);
        if (handlers) {
          // WebBridge sends args as array. We typically use the first arg as payload.
          const payload = data.args && data.args.length > 0 ? data.args[0] : undefined;
          handlers.forEach(h => h(payload));
        }
      }
    } catch (e) {
      console.error('[IPC Adapter] WS Message Parse Error:', e);
    }
  };

  ws.onclose = () => {
    console.log('[IPC Adapter] Web Bridge Disconnected. Reconnecting in 3s...');
    ws = null;
    setTimeout(initWs, 3000);
  };

  ws.onerror = (err) => {
    console.error('[IPC Adapter] Web Bridge Connection Error:', err);
  };
};

// Auto-init in browser mode
if (!isElectron()) {
  // Delay slightly to ensure window.location is ready/stable
  setTimeout(initWs, 100);
}

export const invoke = async (cmd: string, args?: any) => {
  if (isElectron()) {
    return window.electron!.invoke(cmd, args);
  }

  // Browser Mode via HTTP Bridge
  try {
    // Wrap args in array as WebBridge expects ...args
    const response = await fetch(`/api/ipc/${cmd}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(args !== undefined ? [args] : [])
    });

    if (!response.ok) {
      throw new Error(`HTTP Error: ${response.status} ${response.statusText}`);
    }

    const data = await response.json();
    if (data.error) {
      throw new Error(data.error);
    }
    return data.result;

  } catch (e) {
    console.error(`[IPC Adapter] Failed to invoke '${cmd}':`, e);
    
    // Fallback for specific UI-only commands that might fail safely
    if (cmd.startsWith('window-')) return null;
    
    throw e;
  }
}

export const listen = async (event: string, handler: (payload: any) => void) => {
  if (isElectron()) {
    return window.electron!.on(event, (_e: any, ...args: any[]) => handler(args[0]));
  }

  // Browser Mode via WebSocket
  if (!listeners.has(event)) {
    listeners.set(event, new Set());
  }
  listeners.get(event)!.add(handler);

  // Return unsubscribe function
  return () => {
    const handlers = listeners.get(event);
    if (handlers) {
      handlers.delete(handler);
      if (handlers.size === 0) {
        listeners.delete(event);
      }
    }
  };
}

export const emit = async (event: string, payload?: any) => {
  if (isElectron()) {
    return window.electron!.invoke('emit_event', { event, payload });
  }

  // Browser Mode: 'emit' is effectively an invoke to 'emit_event'
  return invoke('emit_event', { event, payload });
}
