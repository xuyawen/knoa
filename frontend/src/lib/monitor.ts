// 零依赖前端可观测：全局错误捕获 + 首屏性能埋点，上报到后端 /api/events
// ponytail: 不引依赖，best-effort，任何上报失败都静默，绝不阻塞业务
// 上报用 sendBeacon（页面卸载也能发）/ fetch keepalive 兜底

let endpoint = '/api/events'
let disabled = false

interface MonitorEvent {
  type: string
  message?: string
  stack?: string
  info?: string
  value?: number
  domInteractive?: number
  level?: 'info' | 'warn' | 'error'
  /** HTTP 方法（GET/POST/PUT/DELETE 等） */
  method?: string
  /** HTTP 状态码 */
  statusCode?: number
  /** 请求路径（不含域名，如 /api/knowledge-bases/kb_xxx/documents） */
  path?: string
  /** 请求体参数（POST/PUT/PATCH 时携带，截断到 500 字符） */
  requestBody?: string
  /** X-Request-ID（后端响应头，用于跨前后端日志关联） */
  rid?: string
  /** 请求耗时（毫秒） */
  elapsedMs?: number
}

function send(ev: MonitorEvent): void {
  if (disabled) return
  const payload = {
    ...ev,
    ts: Date.now(),
    // 脱敏：去掉 URL 查询串（可能含 token / redirect 等敏感参数），并裁切过长堆栈
    url: location.href.split('?')[0],
    ua: navigator.userAgent,
  }
  if (typeof payload.stack === 'string' && payload.stack.length > 1500) {
    payload.stack = payload.stack.slice(0, 1500) + '…'
  }
  try {
    const blob = new Blob([JSON.stringify(payload)], { type: 'application/json' })
    if (navigator.sendBeacon && navigator.sendBeacon(endpoint, blob)) return
  } catch {
    /* fall through to fetch */
  }
  fetch(endpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    keepalive: true,
  }).catch(() => {})
}

export function report(ev: MonitorEvent): void {
  send(ev)
}

// 供 main.ts 挂到 app.config.errorHandler，捕获 Vue 组件渲染/生命周期异常
export function vueErrorHandler(err: unknown, _instance: unknown, info: string): void {
  const e = err as Error
  send({ type: 'vue.error', message: e?.message, stack: e?.stack, info, level: 'error' })
}

export function installMonitor(opts?: { endpoint?: string }): void {
  if (opts?.endpoint) endpoint = opts.endpoint

  window.addEventListener('error', (e: ErrorEvent) => {
    if (e.error) {
      send({ type: 'window.error', message: e.message, stack: e.error.stack, level: 'error' })
    } else {
      // 资源加载失败（img/script/css）走这里，e.error 为 null
      const t = e.target as (HTMLElement & { src?: string; href?: string }) | null
      send({ type: 'resource.error', message: `failed: ${t?.src || t?.href || 'unknown'}`, level: 'warn' })
    }
  })

  window.addEventListener('unhandledrejection', (e: PromiseRejectionEvent) => {
    const r = e.reason as Error
    send({
      type: 'unhandledrejection',
      message: r?.message || String(e.reason),
      stack: r?.stack,
      level: 'error',
    })
  })

  // 首屏性能埋点：此前只上报 loadEventEnd/domInteractive 两个裸数字，
  // 在系统事件页无任何可读性（方法/路径/状态码/消息全空），已移除。
  // 若后续需要性能监控，可接入 Web Vitals（LCP/FID/CLS）并携带页面 URL。
}
