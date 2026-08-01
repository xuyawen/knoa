/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_DEMO_FILL?: string
  readonly VITE_DEMO_ACCOUNT?: string
  readonly VITE_DEMO_PASSWORD?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<Record<string, unknown>, Record<string, unknown>, unknown>
  export default component
}
