<script setup lang="ts">
import { ref } from 'vue'
import AppSidebar from '@/components/AppSidebar.vue'
import TopBar from '@/components/TopBar.vue'
import Icon from '@/components/Icon.vue'

const collapsed = ref(false)

/* 硬数据 — 后续对接 upload / 知识库 CRUD 接口后替换 */
const knowledgeBases = [
  { id: 'compliance', name: '合规库', icon: 'compliance', badge: '5 份待复核', badgeType: 'danger' },
  { id: 'ads', name: '广告投放', icon: 'ads' },
  { id: 'logistics', name: '物流仓储', icon: 'logistics' },
  { id: 'selection', name: '选品策略', icon: 'selection' },
  { id: 'service', name: '客服话术', icon: 'service' },
]
</script>

<template>
  <div class="kb-page">
    <AppSidebar :collapsed="collapsed" @collapse="collapsed = !collapsed" />
    <div class="main">
      <TopBar title="知识库" />
      <div class="body">
        <div class="kb-list">
          <button
            v-for="kb in knowledgeBases"
            :key="kb.id"
            class="kb-item"
          >
            <span class="kb-icon"><Icon :name="kb.icon" :size="20" /></span>
            <span class="kb-name">{{ kb.name }}</span>
            <span v-if="kb.badge" class="kb-badge" :class="kb.badgeType">{{ kb.badge }}</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.kb-page {
  display: flex;
  height: 100%;
  overflow-x: hidden;
}
.main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.body {
  flex: 1;
  padding: 24px 32px;
  overflow-y: auto;
}

.kb-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-width: 520px;
}

.kb-item {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px 18px;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  font-size: 15px;
  color: var(--text-primary);
  text-align: left;
  width: 100%;
  transition: border-color 0.15s ease, box-shadow 0.15s ease, transform 0.15s ease;
}
.kb-item:hover {
  border-color: var(--brand);
  box-shadow: var(--shadow-card);
  transform: translateY(-1px);
}

.kb-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: var(--radius-md);
  background: var(--bg-subtle);
  color: var(--text-secondary);
  flex-shrink: 0;
}

.kb-name {
  font-weight: 500;
  flex: 1;
}

.kb-badge {
  font-size: 12px;
  padding: 3px 10px;
  border-radius: var(--radius-pill);
  white-space: nowrap;
  flex-shrink: 0;
}
.kb-badge.danger {
  background: var(--danger-soft);
  color: var(--danger);
}

@media (max-width: 900px) {
  .body {
    padding: 16px;
  }
}
</style>
