import { defineStore } from 'pinia'
import { ref } from 'vue'

// 主题 store：light / dark / system 三态。
// 持久化到 localStorage，并把 data-theme 写到 <html> 上驱动 CSS 变量切换。
type ThemeMode = 'light' | 'dark' | 'system'

function systemPrefersDark(): boolean {
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false
}

function resolve(mode: ThemeMode): 'light' | 'dark' {
  if (mode === 'system') return systemPrefersDark() ? 'dark' : 'light'
  return mode
}

export const useThemeStore = defineStore('theme', () => {
  const mode = ref<ThemeMode>(
    (localStorage.getItem('knoa-theme') as ThemeMode) || 'system',
  )

  function apply() {
    document.documentElement.setAttribute('data-theme', resolve(mode.value))
  }

  function init() {
    apply()
    // 跟随系统：监听系统主题变化
    window
      .matchMedia?.('(prefers-color-scheme: dark)')
      .addEventListener('change', () => {
        if (mode.value === 'system') apply()
      })
  }

  function setMode(next: ThemeMode) {
    mode.value = next
    localStorage.setItem('knoa-theme', next)
    apply()
  }

  function cycle() {
    const order: ThemeMode[] = ['light', 'dark', 'system']
    const idx = order.indexOf(mode.value)
    setMode(order[(idx + 1) % order.length])
  }

  return { mode, init, setMode, cycle, apply }
})
