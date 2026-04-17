/// <reference types="vite/client" />

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<Record<string, never>, Record<string, never>, unknown>
  export default component
}

interface ImportMetaEnv {
  readonly VITE_SHORE_API?: string
  readonly VITE_SHORE_API_KEY?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
