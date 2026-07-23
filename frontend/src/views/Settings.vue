<script setup lang="ts">
// 系统设置页面：复用 SystemSettingsPanel。
import SystemSettingsPanel from '@/components/user/SystemSettingsPanel.vue'
</script>

<template>
  <div class="settings-page fade-up">
    <div class="settings-head">
      <h2 class="settings-title">系统设置</h2>
      <p class="settings-sub">配置你的问答偏好与语音播报。修改即时生效。</p>
    </div>

    <section class="card settings-card">
      <SystemSettingsPanel />
    </section>
  </div>
</template>

<style scoped>
.settings-page { max-width: 720px; }
.settings-head { margin-bottom: 18px; }
.settings-title { margin: 0 0 4px; font-size: 20px; font-weight: 700; color: var(--text-primary); }
.settings-sub { margin: 0; font-size: 13px; color: var(--text-tertiary); }
.settings-card { padding: 20px; }
</style>
