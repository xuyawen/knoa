<script setup lang="ts">
// 内联图标集：用 currentColor 继承文字色，随主题/语义自动变色。
// 避免引入图标库，保持壳阶段零额外依赖。
import { computed } from 'vue'

const props = defineProps<{ name: string; size?: number | string }>()

const paths: Record<string, string> = {
  // ---- 导航 / 布局 ----
  dashboard: 'M3 3h8v8H3zM13 3h8v5h-8zM13 11h8v10h-8zM3 13h8v8H3z',
  doc: 'M6 2h8l4 4v16H6zM14 6h-3V3',
  search: 'M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zm0 2a5 5 0 1 1 0 10 5 5 0 0 1 0-10zM16 16l4 4',
  chat: 'M4 4h16v11H9l-4 4zM7 8h10M7 11h6',
  graph: 'M5 6a2 2 0 1 0 0-4 2 2 0 0 0 0 4zM19 8a2 2 0 1 0 0-4 2 2 0 0 0 0 4zM12 20a2 2 0 1 0 0-4 2 2 0 0 0 0 4zM6.5 4.5l4 13M17.5 4.5l-4 13M7 6h10',
  shield: 'M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6z',

  // ---- 用户 / 系统 ----
  user: 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4 21c0-4 3.5-6 8-6s8 2 8 6',
  settings:
    'M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6zM19 12l1.5-1-1-1.7-2 .4a6 6 0 0 0-1.1-1.3l.4-2-1.7-1L15 6.4a6 6 0 0 0-1.4-.8L13 4H11l-.6 1.6A6 6 0 0 0 9 6.4L7.3 5.7l-1.7 1 .4 2A6 6 0 0 0 4.9 9.4l-2-.4-1 1.7L3.5 12 2 13l1 1.7 2-.4a6 6 0 0 0 1.1 1.3l-.4 2 1.7 1L9 17.6a6 6 0 0 0 1.4.8L11 20h2l.6-1.6a6 6 0 0 0 1.4-.8l1.7.7 1.7-1-.4-2a6 6 0 0 0 1.1-1.3l2 .4 1-1.7z',
  bell: 'M12 3a5 5 0 0 0-5 5v4l-2 3h14l-2-3V8a5 5 0 0 0-5-5zM10 20a2 2 0 0 0 4 0',
  logout: 'M14 4h4v16h-4M10 8l-4 4 4 4M6 12h11',

  // ---- 箭头 ----
  chevron: 'M9 6l6 6-6 6',
  'chevron-down': 'M6 9l6 6 6-6',

  // ---- 主题切换 ----
  sun: 'M12 7a5 5 0 1 0 0 10 5 5 0 0 0 0-10zM12 1v3M12 20v3M1 12h3M20 12h3M4 4l2 2M18 18l2 2M20 4l-2 2M6 18l-2 2',
  moon: 'M21 13a8 8 0 1 1-9-10 6 6 0 0 0 9 10z',
  monitor: 'M3 4h18v12H3zM8 20h8M12 16v4',

  // ---- 操作 ----
  plus: 'M12 5v14M5 12h14',
  close: 'M6 6l12 12M18 6L6 18',
  check: 'M5 12l4 4 10-11',
  alert: 'M12 3l9 16H3zM12 10v4M12 17v.5',
  edit: 'M4 20l4-1 11-11-3-3L5 16zM14 6l3 3',
  trash: 'M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13',
  more: 'M5 12a1.6 1.6 0 1 0 0-.01zM12 12a1.6 1.6 0 1 0 0-.01zM19 12a1.6 1.6 0 1 0 0-.01z',
  menu: 'M4 6h16M4 12h16M4 18h16',

  // ---- 文件 / 文件夹 ----
  folder: 'M3 6h6l2 2h10v11H3z',
  upload: 'M12 15V4M8 9l4-5 4 5M4 19h16',
  download: 'M12 4v11M8 11l4 4 4-4M4 19h16',
  archive: 'M3 4h18v2H3zM5 8v12h14V8zM9 12h6',
  file: 'M6 2h8l4 4v16H6zM14 6h-3V3',
  excel: 'M4 4h16v16H4zM9 9h6M9 12h4M9 15h6',
  pptx: 'M4 4h16v16H4zM9 9h6M9 12h6M9 15h4',
  pdf: 'M4 4h16v16H4zM9 9v6M12 9v6M15 9v6',

  // ---- 搜索 / 筛选 ----
  filter: 'M3 5h18l-7 8v6l-4 2v-8z',
  refresh: 'M4 12a8 8 0 0 1 14-5l2 2M20 12a8 8 0 0 1-14 5l-2-2M18 4v5h-5M6 20v-5h5',
  eye: 'M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7zM12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z',

  // ---- 数据 / 图表 ----
  grid: 'M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z',
  chart: 'M4 20V10M10 20V4M16 20v-8M22 20v-4',
  users: 'M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75',
  fire: 'M12 23c-4.97 0-9-3.58-9-8 0-2.52.99-4.76 2.6-6.48C7.24 6.77 9.5 5.5 12 5c-1 2-2 3.5-2 5.5 0 2.5 1.5 4 3.5 4 .83 0 1.5-.67 1.5-1.5 0-.66-.42-1.22-1-1.44C15.56 11.09 18 8.5 18 5c0 .34-.03.68-.08 1C19.86 7.78 21 10.26 21 13c0 4.42-4.03 10-9 10z',
  clock: 'M12 6v6l4 2M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z',
  history: 'M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8M3 3v5h5',
  list: 'M4 6h16M4 12h16M4 18h16',
  globe: 'M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10zm0-2a8 8 0 1 1 0-16 8 8 0 0 1 0 16z M3 12h18',
  team: 'M16 21v-2a4 4 0 0 0-4-4h-4a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75',

  // ---- 图谱专用 ----
  node: 'M12 2l9 5-9 5-9-5zM3 17l9 5 9-5M3 12l9 5 9-5',
  link: 'M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71',

  // ---- 布局操作 ----
  collapse: 'M4 15l4-4-4-4M12 19V5M20 15l-4-4 4-4',
  expand: 'M15 4l-4 4 4 4M12 5v14M9 20l-4-4 4-4',

  // ---- 其他 UI ----
  attach: 'M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48',
  send: 'M22 2L11 13M22 2l-7 20-4-9-9-4 20-7',
  copy: 'M8 4h10a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h2',
  export: 'M12 15V4M8 10l4-5 4 5M4 19h16',
  view: 'M4 4h16v12H4zM8 20h8',
  gridview: 'M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z',
  listview: 'M4 6h16M4 12h16M4 18h16',
  star: 'M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z',
  tag: 'M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82zM7 7h.01',
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
