import { defineStore } from 'pinia'
import { ref } from 'vue'

// 全局 UI 状态：目前只管命令面板（Command Palette）的开关。
// 放在独立 store 而非 chat store，语义更清晰，且任意组件都能唤起。
export const useUiStore = defineStore('ui', () => {
  const paletteOpen = ref(false)

  function openPalette() {
    paletteOpen.value = true
  }
  function closePalette() {
    paletteOpen.value = false
  }
  function togglePalette() {
    paletteOpen.value = !paletteOpen.value
  }

  return { paletteOpen, openPalette, closePalette, togglePalette }
})
