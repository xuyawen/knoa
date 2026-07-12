<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import AppSidebar from '@/components/AppSidebar.vue'
import TopBar from '@/components/TopBar.vue'
import Icon from '@/components/Icon.vue'
import { useKnowledgeStore } from '@/stores/knowledge'

const collapsed = ref(false)

// 接真实 KB 列表（含实时"待复核"角标），来自 /api/knowledge-bases
const knowledgeStore = useKnowledgeStore()
const knowledgeBases = computed(() => knowledgeStore.bases)

onMounted(() => knowledgeStore.load())
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
  gap: 6px;
  width: 100%;
}

.kb-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 11px 14px;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  font-size: 14px;
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
  width: 32px;
  height: 32px;
  border-radius: 8px;
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
