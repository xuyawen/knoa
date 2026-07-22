<script setup lang="ts">
// 个人中心 — 参考用户设计图：顶部资料卡 + 统计 + 左（知识库/贡献）右（问答/贡献度/菜单）
import { computed, ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import { getSessions, getKnowledgeBases } from '@/api'
import Icon from '@/components/ui/Icon.vue'
import UserProfileSettingsModal from '@/components/user/UserProfileSettingsModal.vue'
import type { ChatSession, Paginated, KnowledgeBasesResponse } from '@/types/api'

const auth = useAuthStore()
const toast = useToastStore()

const ROLE_LABEL: Record<string, string> = { admin: '管理员', editor: '编辑者', viewer: '访客' }
const roleLabel = computed(() => ROLE_LABEL[auth.user?.role || 'viewer'] || auth.user?.role || '—')

const displayName = computed(() => auth.user?.displayName || auth.user?.username || '—')
const avatarLetter = computed(() => displayName.value[0]?.toUpperCase() || '?')
const department = computed(() => auth.user?.department || '—')
const email = computed(() => auth.user?.email || '—')
const employeeId = computed(() => auth.user?.employeeId || '—')

/* ---------- 真实数据加载 ---------- */
const loading = ref(true)
const sessionsData = ref<Paginated<ChatSession> | null>(null)
const kbData = ref<KnowledgeBasesResponse | null>(null)
onMounted(async () => {
  try {
    const [sList, kbResp] = await Promise.all([
      getSessions(1, 3),
      getKnowledgeBases(1, 4),
    ])
    sessionsData.value = sList
    kbData.value = kbResp
  } catch {
    toast.error('加载个人数据失败')
  } finally {
    loading.value = false
  }
})

/* ---------- 统计 ---------- */
const stats = computed(() => [
  { label: '贡献文档', value: '—' }, // ponytail: 后端暂无用户贡献文档 API，先占位
  { label: '提问', value: sessionsData.value?.total ?? 0 },
  { label: '采纳回答', value: '—' }, // ponytail: 后端暂无采纳统计 API，先占位
  { label: '加入知识库', value: kbData.value?.total ?? 0 },
])

/* ---------- 我的知识库 ---------- */
const KB_PALETTE = ['#014DB2', '#0EA5E9', '#8B5CF6', '#F59E0B', '#10B981', '#EF4444']
function kbColor(name: string) {
  let hash = 0
  for (const c of name) hash = c.charCodeAt(0) + ((hash << 5) - hash)
  return KB_PALETTE[Math.abs(hash) % KB_PALETTE.length]
}
const myKBs = computed(() =>
  (kbData.value?.knowledgeBases ?? []).slice(0, 4).map((kb) => ({
    ...kb,
    initial: kb.name[0] || '?',
    color: kbColor(kb.name),
  })),
)

/* ---------- 我的问答（用会话标题兜底） ---------- */
const myQuestions = computed(() =>
  (sessionsData.value?.items ?? []).slice(0, 3).map((s) => ({
    title: s.title || '未命名问题',
    meta: s.msgCount > 1 ? `${s.msgCount - 1} 个来源 · 已回答` : '新提问',
  })),
)

/* ---------- 近期贡献（mock，后端暂无贡献流 API） ---------- */
const recentContribs = [
  { title: '亚马逊美国站退货政策 2026 更新', action: '编辑', time: '3 小时前' },
  { title: '北美站 Prime Day 备货清单', action: '新增', time: '昨天' },
]

/* ---------- 编辑资料弹窗（复用 UserProfileSettingsModal）---------- */
const showEdit = ref(false)
</script>

<template>
  <div class="profile-page fade-up">
    <!-- ====== 顶部资料卡 ====== -->
    <section class="hero-card card">
      <div class="hero-main">
        <div class="hero-avatar" :style="{ background: 'linear-gradient(135deg, var(--brand), var(--brand-hover))' }">
          <span class="ha-text">{{ avatarLetter }}</span>
        </div>
        <div class="hero-info">
          <h1 class="hero-name">{{ displayName }}</h1>
          <p class="hero-meta">
            <span>{{ roleLabel }}</span>
            <span class="dot" />
            <span>{{ department }}</span>
          </p>
          <p class="hero-contact">{{ email }} · 工号 {{ employeeId }}</p>
        </div>
      </div>
      <button class="btn btn-primary hero-edit" @click="showEdit = true">
        <Icon name="settings" :size="14" /> 设置
      </button>
    </section>

    <!-- ====== 统计行 ====== -->
    <section class="stats-row">
      <div v-for="s in stats" :key="s.label" class="stat-card card" :class="{ dim: s.value === '—' }">
        <span class="stat-num">{{ s.value }}</span>
        <span class="stat-label">{{ s.label }}</span>
      </div>
    </section>

    <!-- ====== 主体分栏 ====== -->
    <div class="content-grid">
      <div class="content-left">
        <!-- 我的知识库 -->
        <section class="section-card card">
          <h2 class="section-title">我的知识库</h2>
          <div v-if="myKBs.length" class="kb-list">
            <div v-for="kb in myKBs" :key="kb.id" class="kb-item">
              <div class="kb-icon" :style="{ background: kb.color }">
                <span class="kb-initial">{{ kb.initial }}</span>
              </div>
              <div class="kb-body">
                <div class="kb-name-row">
                  <span class="kb-name">{{ kb.name }}</span>
                  <span class="kb-role">{{ roleLabel }}</span>
                </div>
                <p class="kb-meta">{{ kb.documentCount }} 篇文档</p>
              </div>
            </div>
          </div>
          <div v-else class="empty-state">
            <Icon name="folder" :size="28" />
            <span>暂无加入的知识库</span>
          </div>
        </section>

        <!-- 我的近期贡献 -->
        <section class="section-card card">
          <h2 class="section-title">我的近期贡献</h2>
          <div class="contrib-list">
            <div v-for="(c, i) in recentContribs" :key="i" class="contrib-item">
              <p class="contrib-title">{{ c.title }}</p>
              <p class="contrib-meta">{{ c.action }} · {{ c.time }}</p>
            </div>
          </div>
        </section>
      </div>

      <div class="content-right">
        <!-- 我的问答 -->
        <section class="section-card card">
          <h2 class="section-title">我的问答</h2>
          <div v-if="myQuestions.length" class="qa-list">
            <div v-for="(q, i) in myQuestions" :key="i" class="qa-item">
              <p class="qa-title">{{ q.title }}</p>
              <p class="qa-meta">{{ q.meta }}</p>
            </div>
          </div>
          <div v-else class="empty-state">
            <Icon name="chat" :size="28" />
            <span>还没有提问</span>
          </div>
        </section>

      </div>
    </div>

    <!-- ====== 设置弹窗 ====== -->
    <UserProfileSettingsModal :show="showEdit" @close="showEdit = false" />
  </div>
</template>

<style scoped>
.profile-page {
  max-width: 1100px;
  margin: 0 auto;
}

/* ====== 顶部资料卡 ====== */
.hero-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 28px 32px;
  margin-bottom: 18px;
}
.hero-main {
  display: flex;
  align-items: center;
  gap: 22px;
}
.hero-avatar {
  width: 82px;
  height: 82px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  box-shadow: var(--shadow-float);
}
.ha-text {
  font-size: 32px;
  font-weight: 700;
  color: #fff;
}
.hero-info {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.hero-name {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.01em;
  color: var(--text-primary);
}
.hero-meta {
  margin: 0;
  font-size: 14px;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  gap: 10px;
}
.hero-meta .dot {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: var(--text-tertiary);
}
.hero-contact {
  margin: 0;
  font-size: 13px;
  color: var(--text-tertiary);
}
.hero-edit {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

/* ====== 统计行 ====== */
.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 18px;
}
.stat-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 22px 24px;
}
.stat-num {
  font-size: 28px;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--text-primary);
}
.stat-card.dim .stat-num { color: var(--text-tertiary); }
.stat-label {
  font-size: 13px;
  color: var(--text-tertiary);
}

/* ====== 主体分栏 ====== */
.content-grid {
  display: grid;
  grid-template-columns: 1.4fr 1fr;
  gap: 18px;
  align-items: start;
}
.content-left,
.content-right {
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.section-card {
  padding: 22px 24px;
}
.section-title {
  margin: 0 0 18px;
  font-size: 15px;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.01em;
}

/* ====== 知识库列表 ====== */
.kb-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.kb-item {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px;
  border-radius: var(--radius-lg);
  background: var(--bg-subtle);
  transition: background var(--dur-fast) var(--ease-out);
}
.kb-item:hover { background: var(--bg-hover); }
.kb-icon {
  width: 44px;
  height: 44px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.kb-initial {
  font-size: 18px;
  font-weight: 700;
  color: #fff;
}
.kb-body {
  flex: 1;
  min-width: 0;
}
.kb-name-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.kb-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}
.kb-role {
  font-size: 12px;
  font-weight: 600;
  padding: 2px 10px;
  border-radius: var(--radius-pill);
  color: var(--brand);
  background: var(--brand-soft);
  flex-shrink: 0;
}
.kb-meta {
  margin: 5px 0 0;
  font-size: 12.5px;
  color: var(--text-tertiary);
}

/* ====== 贡献/问答列表 ====== */
.contrib-list,
.qa-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.contrib-item,
.qa-item {
  padding-bottom: 14px;
  border-bottom: 1px solid var(--border);
}
.contrib-item:last-child,
.qa-item:last-child {
  padding-bottom: 0;
  border-bottom: none;
}
.contrib-title,
.qa-title {
  margin: 0 0 5px;
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  line-height: 1.4;
}
.contrib-meta,
.qa-meta {
  margin: 0;
  font-size: 12.5px;
  color: var(--text-tertiary);
}
.qa-meta { color: var(--success); }

/* ====== 空态 ====== */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 28px;
  color: var(--text-tertiary);
  font-size: 13px;
}

@media (max-width: 900px) {
  .content-grid { grid-template-columns: 1fr; }
  .stats-row { grid-template-columns: repeat(2, 1fr); }
  .hero-card { flex-direction: column; align-items: flex-start; }
  .hero-edit { width: 100%; justify-content: center; }
}
@media (max-width: 560px) {
  .stats-row { grid-template-columns: 1fr; }
  .info-grid { grid-template-columns: 1fr; }
  .hero-card { padding: 22px; }
}
</style>
