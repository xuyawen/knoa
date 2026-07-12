<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useKnowledgeStore } from '@/stores/knowledge'
import { useChatStore } from '@/stores/chat'
import Icon from './Icon.vue'

const route = useRoute()
const knowledge = useKnowledgeStore()
const chat = useChatStore()

defineProps<{
  collapsed?: boolean
  mobileOpen?: boolean
}>()

const emit = defineEmits<{
  (e: 'collapse'): void
  (e: 'close'): void
}>()

const bases = computed(() => knowledge.bases)

// 确保在任何页面刷新都能加载知识库列表
onMounted(() => {
  knowledge.load()
})
</script>

<template>
  <aside
    class="sidebar"
    :class="{ collapsed, 'mobile-open': mobileOpen }"
  >
    <!-- 品牌区 -->
    <div class="brand">
      <router-link to="/" class="brand-link">
        <div class="logo">知</div>
        <div class="brand-text">
          <span class="brand-name">知海 Knoa</span>
          <span class="brand-sub">跨境运营知识库</span>
        </div>
      </router-link>
      <button class="collapse" @click="emit('collapse')" :title="collapsed ? '展开' : '收起'">
        <Icon name="chevron-left" :size="18" />
      </button>
    </div>

    <!-- 工作区切换（回到对话首页） -->
    <router-link to="/" class="workspace-switch">
      <div v-if="!collapsed" class="ws-name">全部知识</div>
      <Icon name="chevron-down" :size="16" />
    </router-link>

    <!-- 知识库导航 -->
    <nav class="nav">
      <div v-show="!collapsed" class="nav-label">知识库</div>
      <router-link
        v-for="kb in bases"
        :key="kb.id"
        :to="'/knowledge-bases/' + kb.id"
        class="nav-item"
        :class="{ active: route.path === '/knowledge-bases/' + kb.id }"
      >
        <span class="nav-icon"><Icon :name="kb.icon" :size="18" /></span>
        <span v-show="!collapsed" class="nav-name">{{ kb.name }}</span>
        <span v-if="kb.badge && !collapsed" class="nav-badge" :class="kb.badgeType">{{ kb.badge }}</span>
      </router-link>
    </nav>

    <!-- 工作区次级入口 -->
    <nav class="nav secondary">
      <div class="nav-label">工作区</div>
      <router-link to="/knowledge-bases" class="nav-item plain" active-class="active">
        <span class="nav-name">文档管理</span>
      </router-link>
      <button class="nav-item plain" @click="chat.toggleHistory()">
        <span class="nav-name">问答记录</span>
      </button>
    </nav>

    <!-- 底部用户卡 -->
    <div class="user-card">
      <div class="avatar">运</div>
      <div class="user-info">
        <span class="user-name">运营小王</span>
        <span class="user-role">运营专家</span>
      </div>
      <button class="settings" title="设置">
        <Icon name="gear" :size="16" />
      </button>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  width: var(--sidebar-w);
  flex-shrink: 0;
  min-width: 0;
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-subtle);
  border-right: 1px solid var(--border);
  padding: 16px 16px 12px;
  gap: 4px;
  overflow-y: auto;
  transition: width 0.22s ease, transform 0.22s ease;
}
.collapsed {
  width: 76px;
  padding-left: 12px;
  padding-right: 12px;
}
.collapsed .brand-text,
.collapsed .nav-name,
.collapsed .nav-badge,
.collapsed .nav-label,
.collapsed .ws-name,
.collapsed .user-info,
.collapsed .settings {
  display: none;
}
.collapsed .workspace-switch {
  display: none;
}
.collapsed .user-card {
  justify-content: center;
  padding: 10px 0;
}
.collapsed .brand {
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 6px 0 10px;
  gap: 6px;
}
.collapsed .collapse {
  margin-left: 0;
}
.collapsed .nav-item {
  justify-content: center;
  padding: 0;
}

/* 品牌区 */
.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px 8px 8px;
  min-height: 44px;
}
.brand-link {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
  min-width: 0;
}
.logo {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-md);
  background: var(--brand);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-display);
  font-weight: 600;
  font-size: 18px;
  flex-shrink: 0;
}
.brand-text {
  display: flex;
  flex-direction: column;
  line-height: 1.2;
  min-width: 0;
}
.brand-name {
  font-family: var(--font-display);
  font-weight: 600;
  font-size: 15px;
}
.brand-sub {
  font-size: 11px;
  color: var(--text-secondary);
  white-space: nowrap;
}
.collapse {
  margin-left: auto;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  border-radius: var(--radius-sm);
  width: 24px;
  height: 24px;
  justify-content: center;
  transition: background 0.15s ease, transform 0.2s ease;
}
.collapse:hover {
  background: var(--bg-surface);
}
.collapsed .collapse {
  transform: rotate(180deg);
}

/* 工作区切换 */
.workspace-switch {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 4px;
  padding: 9px 12px;
  border-radius: var(--radius-md);
  background: var(--bg-surface);
  border: 1px solid var(--border);
  font-weight: 500;
  color: var(--text-primary);
  font-size: 14px;
  transition: border-color 0.15s ease;
}
.workspace-switch:hover {
  border-color: var(--brand);
}

/* 导航 */
.nav {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-top: 8px;
}
.nav.secondary {
  margin-top: 14px;
}
.nav-label {
  font-size: 11px;
  color: var(--text-secondary);
  padding: 6px 12px 4px;
  letter-spacing: 0.04em;
}
.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  height: 40px;
  padding: 0 12px;
  border-radius: var(--radius-md);
  color: var(--text-primary);
  font-size: 14px;
  text-align: left;
  width: 100%;
  transition: background 0.15s ease, color 0.15s ease;
}
.nav-item:hover {
  background: var(--bg-surface);
}
.nav-item.active {
  background: var(--brand);
  color: #fff;
}
.nav-item.active .nav-icon {
  color: #fff;
}
.nav-icon {
  display: flex;
  width: 20px;
  justify-content: center;
  color: var(--text-secondary);
  flex-shrink: 0;
}
.nav-name {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.nav-badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: var(--radius-pill);
  white-space: nowrap;
}
.nav-badge.danger {
  background: var(--danger-soft);
  color: var(--danger);
}
.nav-item.active .nav-badge.danger {
  background: rgba(255, 255, 255, 0.22);
  color: #fff;
}
.nav-item.plain .nav-name {
  color: var(--text-secondary);
}

/* 用户卡 */
.user-card {
  margin-top: auto;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: var(--radius-md);
  background: var(--bg-surface);
  border: 1px solid var(--border);
}
.avatar {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-pill);
  background: var(--brand-soft);
  color: var(--brand);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 13px;
  flex-shrink: 0;
}
.user-info {
  display: flex;
  flex-direction: column;
  line-height: 1.3;
  min-width: 0;
}
.user-name {
  font-size: 13px;
  font-weight: 500;
}
.user-role {
  font-size: 11px;
  color: var(--text-secondary);
}
.settings {
  margin-left: auto;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
}
.settings:hover {
  color: var(--brand);
}

/* 移动端抽屉 */
@media (max-width: 900px) {
  .sidebar {
    position: fixed;
    z-index: 40;
    top: 0;
    left: 0;
    width: var(--sidebar-w);
    transform: translateX(-100%);
    box-shadow: var(--shadow-float);
  }
  .sidebar.mobile-open {
    transform: translateX(0);
  }
  .collapse {
    display: none;
  }
}
</style>
