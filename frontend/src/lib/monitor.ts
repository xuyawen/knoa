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
}

function send(ev: MonitorEvent): void {
  if (disabled) return
  const payload = {
    ...ev,
    ts: Date.now(),
    url: location.href,
    ua: navigator.userAgent,
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

  // 首屏性能埋点：navigation timing，验证"首屏 < 1.5s"是不是真的
  window.addEventListener('load', () => {
    setTimeout(() => {
      const nav = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming | undefined
      if (!nav) return
      send({
        type: 'perf.navigation',
        value: Math.round(nav.loadEventEnd - nav.startTime),
        domInteractive: Math.round(nav.domInteractive - nav.startTime),
        level: 'info',
      })
    }, 0)
  })
}
