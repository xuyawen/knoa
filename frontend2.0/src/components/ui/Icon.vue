<script setup lang="ts">
// 内联图标集：用 currentColor 继承文字色，随主题/语义自动变色。
// 避免引入图标库，保持壳阶段零额外依赖。
import { computed } from 'vue'

const props = defineProps<{ name: string; size?: number | string }>()

const paths: Record<string, string> = {
  dashboard: 'M3 3h8v8H3zM13 3h8v5h-8zM13 11h8v10h-8zM3 13h8v8H3z',
  doc: 'M6 2h8l4 4v16H6zM14 6h-3V3',
  search: 'M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zm0 2a5 5 0 1 1 0 10 5 5 0 0 1 0-10zM16 16l4 4',
  chat: 'M4 4h16v11H9l-4 4zM7 8h10M7 11h6',
  graph: 'M5 6a2 2 0 1 0 0-4 2 2 0 0 0 0 4zM19 8a2 2 0 1 0 0-4 2 2 0 0 0 0 4zM12 20a2 2 0 1 0 0-4 2 2 0 0 0 0 4zM6.5 4.5l4 13M17.5 4.5l-4 13M7 6h10',
  shield: 'M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6z',
  user: 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4 21c0-4 3.5-6 8-6s8 2 8 6',
  settings:
    'M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6zM19 12l1.5-1-1-1.7-2 .4a6 6 0 0 0-1.1-1.3l.4-2-1.7-1L15 6.4a6 6 0 0 0-1.4-.8L13 4H11l-.6 1.6A6 6 0 0 0 9 6.4L7.3 5.7l-1.7 1 .4 2A6 6 0 0 0 4.9 9.4l-2-.4-1 1.7L3.5 12 2 13l1 1.7 2-.4a6 6 0 0 0 1.1 1.3l-.4 2 1.7 1L9 17.6a6 6 0 0 0 1.4.8L11 20h2l.6-1.6a6 6 0 0 0 1.4-.8l1.7.7 1.7-1-.4-2a6 6 0 0 0 1.1-1.3l2 .4 1-1.7z',
  bell: 'M12 3a5 5 0 0 0-5 5v4l-2 3h14l-2-3V8a5 5 0 0 0-5-5zM10 20a2 2 0 0 0 4 0',
  sun: 'M12 7a5 5 0 1 0 0 10 5 5 0 0 0 0-10zM12 1v3M12 20v3M1 12h3M20 12h3M4 4l2 2M18 18l2 2M20 4l-2 2M6 18l-2 2',
  moon: 'M21 13a8 8 0 1 1-9-10 6 6 0 0 0 9 10z',
  monitor: 'M3 4h18v12H3zM8 20h8M12 16v4',
  logout: 'M14 4h4v16h-4M10 8l-4 4 4 4M6 12h11',
  plus: 'M12 5v14M5 12h14',
  folder: 'M3 6h6l2 2h10v11H3z',
  filter: 'M3 5h18l-7 8v6l-4 2v-8z',
  upload: 'M12 15V4M8 9l4-5 4 5M4 19h16',
  chevron: 'M9 6l6 6-6 6',
  close: 'M6 6l12 12M18 6L6 18',
  check: 'M5 12l4 4 10-11',
  alert: 'M12 3l9 16H3zM12 10v4M12 17v.5',
  sparkles: 'M12 3l1.5 4L18 8l-4.5 1.5L12 14l-1.5-4.5L6 8l4.5-1zM18 14l.8 2.2L21 17l-2.2.8L18 20l-.8-2.2L15 17l2.2-.8z',
  more: 'M5 12a1.6 1.6 0 1 0 0-.01zM12 12a1.6 1.6 0 1 0 0-.01zM19 12a1.6 1.6 0 1 0 0-.01z',
  menu: 'M4 6h16M4 12h16M4 18h16',
  refresh: 'M4 12a8 8 0 0 1 14-5l2 2M20 12a8 8 0 0 1-14 5l-2-2M18 4v5h-5M6 20v-5h5',
  eye: 'M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7zM12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z',
  download: 'M12 4v11M8 11l4 4 4-4M4 19h16',
  edit: 'M4 20l4-1 11-11-3-3L5 16zM14 6l3 3',
  trash: 'M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13',
}

const d = computed(() => paths[props.name] ?? '')
const dim = computed(() => (typeof props.size === 'number' ? `${props.size}px` : props.size) || '18px')
</script>

<template>
  <svg
    :width="dim"
    :height="dim"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="2"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <path :d="d" />
  </svg>
</template>
