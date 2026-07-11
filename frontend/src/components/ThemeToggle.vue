<script setup lang="ts">
import { useTheme } from '@/composables/useTheme'
import Icon from './Icon.vue'

const { theme, toggle } = useTheme()
</script>

<template>
  <button
    class="theme-toggle"
    :class="theme"
    @click="toggle"
    :title="theme === 'dark' ? '切换到亮色' : '切换到暗色'"
    aria-label="切换主题"
  >
    <span class="track">
      <span class="knob">
        <Icon :name="theme === 'dark' ? 'moon' : 'sun'" :size="11" />
      </span>
    </span>
  </button>
</template>

<style scoped>
.theme-toggle {
  padding: 0;
  display: inline-flex;
  align-items: center;
}
.track {
  position: relative;
  width: 35px;
  height: 19px;
  border-radius: var(--radius-pill);
  background: var(--bg-subtle);
  border: 1px solid var(--border);
  transition: background 0.2s ease, border-color 0.2s ease;
}
.knob {
  position: absolute;
  top: 1.5px;
  left: 1.5px;
  width: 15px;
  height: 15px;
  border-radius: 50%;
  background: var(--brand);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: transform 0.22s cubic-bezier(0.16, 1, 0.3, 1);
}
.theme-toggle.dark .knob {
  transform: translateX(16px);
}
</style>
