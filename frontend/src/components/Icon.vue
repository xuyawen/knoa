<script setup lang="ts">
defineProps<{ name: string; size?: number }>()
</script>

<template>
  <svg
    :width="size || 18"
    :height="size || 18"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.8"
    stroke-linecap="round"
    stroke-linejoin="round"
  >
    <template v-if="name === 'compliance'">
      <path d="M12 3l7 3v5c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6l7-3z" />
    </template>
    <template v-else-if="name === 'ads'">
      <path d="M4 9v6h4l8 4V5L8 9H4z" />
    </template>
    <template v-else-if="name === 'logistics'">
      <path d="M3 7l9-4 9 4v10l-9 4-9-4V7z" />
      <path d="M3 7l9 4 9-4M12 11v10" />
    </template>
    <template v-else-if="name === 'selection'">
      <circle cx="12" cy="12" r="9" />
      <circle cx="12" cy="12" r="4" />
      <path d="M12 3v3M12 18v3M3 12h3M18 12h3" />
    </template>
    <template v-else-if="name === 'service'">
      <path d="M21 12a8 8 0 01-11.5 7.2L4 20l1-4.5A8 8 0 1121 12z" />
    </template>
    <template v-else-if="name === 'bell'">
      <path d="M18 8a6 6 0 10-12 0c0 7-3 9-3 9h18s-3-2-3-9M13.7 21a2 2 0 01-3.4 0" />
    </template>
    <template v-else-if="name === 'search'">
      <circle cx="11" cy="11" r="7" />
      <path d="M21 21l-4.3-4.3" />
    </template>
    <template v-else-if="name === 'gear'">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.6 1.6 0 00.3 1.8l.1.1a2 2 0 11-2.8 2.8l-.1-.1a1.6 1.6 0 00-2.7 1.1V21a2 2 0 11-4 0v-.1A1.6 1.6 0 007 19.4l-.1.1a2 2 0 11-2.8-2.8l.1-.1A1.6 1.6 0 004.6 14H4.5a2 2 0 110-4h.1A1.6 1.6 0 006 7.4l-.1-.1a2 2 0 112.8-2.8l.1.1A1.6 1.6 0 0011 4.6V4.5a2 2 0 114 0v.1a1.6 1.6 0 002.7 1.1l.1-.1a2 2 0 112.8 2.8l-.1.1a1.6 1.6 0 001.1 2.7H21a2 2 0 110 4h-.1a1.6 1.6 0 00-1.5 1z" />
    </template>
    <template v-else-if="name === 'sun'">
      <circle cx="12" cy="12" r="4.5" />
      <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
    </template>
    <template v-else-if="name === 'moon'">
      <path d="M21 12.8A9 9 0 1111.2 3a7 7 0 009.8 9.8z" />
    </template>
    <template v-else-if="name === 'chevron-left'">
      <path d="M15 18l-6-6 6-6" />
    </template>
    <template v-else-if="name === 'chevron-right'">
      <path d="M9 18l6-6-6-6" />
    </template>
    <template v-else-if="name === 'chevron-down'">
      <path d="M6 9l6 6 6-6" />
    </template>
    <template v-else-if="name === 'home'">
      <path d="M3 10.5L12 3l9 7.5M5 9.5V21h14V9.5" />
    </template>
    <template v-else-if="name === 'library'">
      <path d="M4 4h4v16H4zM10 4h4v16h-4zM17 5l3 1-3 14-3-1z" />
    </template>
    <template v-else-if="name === 'user'">
      <circle cx="12" cy="8" r="3.5" />
      <path d="M5 20c0-3.6 3.1-6 7-6s7 2.4 7 6" />
    </template>
    <template v-else-if="name === 'chat'">
      <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2v10z" />
    </template>
    <template v-else-if="name === 'send'">
      <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />
    </template>
    <template v-else-if="name === 'paperclip'">
      <path d="M21 11l-9 9a4 4 0 01-6-6l9-9a3 3 0 014.2 0l-9 9a1.5 1.5 0 01-2.2 0 1.5 1.5 0 010-2.2l9-9" />
    </template>
    <template v-else-if="name === 'sparkle'">
      <path d="M12 5l1.8 5.2L19 12l-5.2 1.8L12 19l-1.8-5.2L5 12l5.2-1.8L12 5z" />
    </template>
    <template v-else-if="name === 'copy'">
      <rect x="9" y="9" width="11" height="11" rx="2" />
      <path d="M5 15V5a2 2 0 012-2h8" />
    </template>
    <template v-else-if="name === 'thumb-up'">
      <path d="M7 10v9H4a1 1 0 01-1-1v-7a1 1 0 011-1h3zm0 0l4-7a2 2 0 013.8 1.2L14 9h4.5a2 2 0 011.9 2.6l-1.3 4.4A2 2 0 0117.2 19H7" />
    </template>
    <template v-else-if="name === 'thumb-down'">
      <path d="M17 14V5h3a1 1 0 011 1v7a1 1 0 01-1 1h-3zm0 0l-4 7a2 2 0 01-3.8-1.2L10 15H5.5a2 2 0 01-1.9-2.6l1.3-4.4A2 2 0 016.8 5H17" />
    </template>
    <template v-else-if="name === 'menu'">
      <path d="M4 7h16M4 12h16M4 17h16" />
    </template>
    <template v-else-if="name === 'fire'">
      <path fill="currentColor" d="M12 3c1 3-1.5 4.5-1.5 7A2.5 2.5 0 0013 12c.5-1 .5-2 0-3 2 1.5 3.5 4 3.5 6.5A5.5 5.5 0 1112 3z" />
    </template>
    <template v-else-if="name === 'check'">
      <path d="M5 13l4 4L19 7" />
    </template>
    <template v-else-if="name === 'refresh'">
      <path d="M4 12a8 8 0 0115-2M20 12a8 8 0 01-15 2" />
      <path d="M19 3v4h-4M5 21v-4h4" />
    </template>
    <template v-else-if="name === 'plus'">
      <path d="M12 5v14M5 12h14" />
    </template>
    <template v-else-if="name === 'external'">
      <path d="M14 4h6v6M20 4l-9 9M19 14v5a1 1 0 01-1 1H5a1 1 0 01-1-1V6a1 1 0 011-1h5" />
    </template>
    <template v-else-if="name === 'graph'">
      <circle cx="6" cy="6" r="2.5" />
      <circle cx="18" cy="7.5" r="2.5" />
      <circle cx="12" cy="18" r="2.5" />
      <path d="M8 7.2l8 0M7.5 8.2l3.3 7.8M16.5 9.7l-3.3 6.8" />
    </template>
    <template v-else-if="name === 'alert-circle'">
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5M12 16h.01" />
    </template>
    <template v-else-if="name === 'clock'">
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </template>
    <template v-else-if="name === 'users'">
      <circle cx="9" cy="8" r="3" />
      <path d="M3 20c0-3.3 2.7-5.5 6-5.5s6 2.2 6 5.5" />
      <path d="M16 5.5a3 3 0 010 5.5M21 20c0-2.6-1.6-4.4-4-5" />
    </template>
    <template v-else-if="name === 'logout'">
      <path d="M15 4h3a1 1 0 011 1v14a1 1 0 01-1 1h-3" />
      <path d="M10 8l-4 4 4 4" />
      <path d="M6 12h11" />
    </template>
    <template v-else-if="name === 'inbox'">
      <path d="M4 13l3-8h10l3 8M4 13v6h16v-6M4 13h5l1 2h4l1-2h5" />
    </template>
    <template v-else-if="name === 'edit'">
      <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7" />
      <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4L18.5 2.5z" />
    </template>
    <template v-else-if="name === 'trash'">
      <path d="M4 7h16M9 7V5a2 2 0 012-2h2a2 2 0 012 2v2M6 7v12a2 2 0 002 2h8a2 2 0 002-2V7M10 11v6M14 11v6" />
    </template>
    <template v-else>
      <circle cx="12" cy="12" r="3" />
    </template>
  </svg>
</template>
