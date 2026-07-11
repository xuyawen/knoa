import { ref, watch } from 'vue'

export type Theme = 'light' | 'dark'

const STORAGE_KEY = 'knoa-theme'
const theme = ref<Theme>((localStorage.getItem(STORAGE_KEY) as Theme) || 'light')

function apply(t: Theme) {
  document.documentElement.setAttribute('data-theme', t)
  localStorage.setItem(STORAGE_KEY, t)
}

apply(theme.value)
watch(theme, apply)

export function useTheme() {
  const toggle = () => {
    theme.value = theme.value === 'dark' ? 'light' : 'dark'
  }
  return { theme, toggle }
}
