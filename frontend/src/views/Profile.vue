<script setup lang="ts">
// 个人中心 — 参考用户设计图：顶部资料卡 + 统计 + 左（知识库/贡献）右（问答/贡献度/菜单）
import { computed, ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import { changePassword, updateUser } from '@/api/auth'
import { getSessions, getKnowledgeBases } from '@/api'
import Icon from '@/components/ui/Icon.vue'
import AppModal from '@/components/ui/AppModal.vue'
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

/* ---------- 编辑资料弹窗 ---------- */
const showEdit = ref(false)
const editTab = ref<'info' | 'security'>('info')
const editingInfo = ref(false)
const infoDraft = ref({ displayName: '', email: '', department: '', employeeId: '' })
const infoSaving = ref(false)

function syncInfoDraft() {
  const u = auth.user
  infoDraft.value = {
    displayName: u?.displayName || '',
    email: u?.email || '',
    department: u?.department || '',
    employeeId: u?.employeeId || '',
  }
}
function openEdit(tab: 'info' | 'security' = 'info') {
  editTab.value = tab
  syncInfoDraft()
  editingInfo.value = false
  resetPwd()
  showEdit.value = true
}

function startEditInfo() {
  editingInfo.value = true
}
function cancelEditInfo() {
  editingInfo.value = false
}
async function saveInfo() {
  if (!auth.user) return
  infoSaving.value = true
  try {
    await updateUser(auth.user.id, {
      displayName: infoDraft.value.displayName.trim() || null,
      email: infoDraft.value.email.trim() || null,
      department: infoDraft.value.department.trim() || null,
      employeeId: infoDraft.value.employeeId.trim() || null,
    })
    await auth.fetchMe()
    editingInfo.value = false
    toast.success('资料已更新')
  } catch (e: any) {
    toast.error(e?.message || '更新失败')
  } finally {
    infoSaving.value = false
  }
}

/* ---------- 修改密码 ---------- */
const pwdOld = ref('')
const pwdNew = ref('')
const pwdConfirm = ref('')
const saving = ref(false)
function resetPwd() {
  pwdOld.value = pwdNew.value = pwdConfirm.value = ''
}
async function onSubmitPassword() {
  if (!pwdOld.value || !pwdNew.value) {
    toast.error('请填写完整')
    return
  }
  if (pwdNew.value !== pwdConfirm.value) {
    toast.error('两次输入的新密码不一致')
    return
  }
  if (pwdNew.value.length < 6) {
    toast.error('新密码至少 6 位')
    return
  }
  saving.value = true
  try {
    await changePassword(pwdOld.value, pwdNew.value)
    toast.success('密码修改成功')
    resetPwd()
  } catch (e) {
    toast.error(e instanceof Error ? e.message : '修改失败，请重试')
  } finally {
    saving.value = false
  }
}
const pwdStrength = computed(() => {
  const v = pwdNew.value
  if (!v) return null
  let s = 0
  if (v.length >= 8) s++
  if (/[A-Z]/.test(v)) s++
  if (/[0-9]/.test(v)) s++
  if (/[^A-Za-z0-9]/.test(v)) s++
  if (s <= 1) return { level: 1, label: '弱', cls: 'str-weak' }
  if (s <= 2) return { level: 2, label: '中', cls: 'str-mid' }
  return { level: 3, label: '强', cls: 'str-strong' }
})
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
      <button class="btn btn-primary hero-edit" @click="openEdit('info')">
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
    <AppModal :show="showEdit" title="设置" wide @close="showEdit = false">
      <div class="edit-tabs">
        <button
          v-for="t in [
            { key: 'info', label: '基本信息' },
            { key: 'security', label: '安全设置' },
          ]"
          :key="t.key"
          class="edit-tab"
          :class="{ active: editTab === t.key }"
          @click="editTab = t.key as 'info' | 'security'"
        >
          {{ t.label }}
        </button>
      </div>

      <!-- 基本信息 -->
      <div v-if="editTab === 'info'" class="edit-body">
        <div class="info-grid">
          <div class="info-item">
            <span class="info-key">用户名</span>
            <span class="info-val">{{ auth.user?.username || '—' }}</span>
          </div>
          <div class="info-item">
            <span class="info-key">显示名称</span>
            <span v-if="!editingInfo" class="info-val">{{ auth.user?.displayName || '未设置' }}</span>
            <input v-else v-model="infoDraft.displayName" class="info-input" maxlength="50" placeholder="未设置" />
          </div>
          <div class="info-item">
            <span class="info-key">邮箱</span>
            <span v-if="!editingInfo" class="info-val">{{ auth.user?.email || '未设置' }}</span>
            <input v-else v-model="infoDraft.email" class="info-input" type="email" placeholder="未设置" />
          </div>
          <div class="info-item">
            <span class="info-key">部门</span>
            <span v-if="!editingInfo" class="info-val">{{ auth.user?.department || '未设置' }}</span>
            <input v-else v-model="infoDraft.department" class="info-input" placeholder="未设置" />
          </div>
          <div class="info-item">
            <span class="info-key">工号</span>
            <span v-if="!editingInfo" class="info-val">{{ auth.user?.employeeId || '未设置' }}</span>
            <input v-else v-model="infoDraft.employeeId" class="info-input" placeholder="未设置" />
          </div>
          <div class="info-item">
            <span class="info-key">角色权限</span>
            <span class="info-val"><span class="role-tag" :class="roleLabel === '管理员' ? 'r-admin' : roleLabel === '编辑者' ? 'r-editor' : 'r-viewer'">{{ roleLabel }}</span></span>
          </div>
          <div class="info-item">
            <span class="info-key">账号状态</span>
            <span class="info-val">
              <span class="dot-status" :class="auth.user?.isActive ? 'on' : 'off'" />
              {{ auth.user?.isActive ? '启用' : '停用' }}
            </span>
          </div>
          <div class="info-item">
            <span class="info-key">注册时间</span>
            <span class="info-val">{{ auth.user?.createdAt ? new Date(auth.user.createdAt).toLocaleDateString('zh-CN') : '—' }}</span>
          </div>
          <div class="info-item">
            <span class="info-key">用户 ID</span>
            <span class="info-val id-copy">{{ auth.user?.id || '—' }}</span>
          </div>
        </div>
      </div>

      <!-- 安全设置 -->
      <form v-else class="edit-body sec-form" @submit.prevent="onSubmitPassword">
        <div class="sec-field">
          <label class="sec-label">当前密码 <span class="req">*</span></label>
          <div class="sec-input-wrap">
            <Icon name="lock" :size="14" class="sec-icon" />
            <input v-model="pwdOld" type="password" autocomplete="current-password" class="sec-inp" placeholder="输入当前密码" />
          </div>
        </div>
        <div class="sec-field">
          <label class="sec-label">新密码 <span class="req">*</span></label>
          <div class="sec-input-wrap">
            <Icon name="key" :size="14" class="sec-icon" />
            <input v-model="pwdNew" type="password" autocomplete="new-password" class="sec-inp" placeholder="输入新密码（至少 6 位）" />
          </div>
          <div v-if="pwdNew" class="strength-bar">
            <div class="str-track">
              <div class="str-fill" :class="pwdStrength?.cls" :style="{ width: (pwdStrength?.level || 0) * 33.33 + '%' }" />
            </div>
            <span class="str-label" :class="pwdStrength?.cls">{{ pwdStrength?.label }}</span>
          </div>
        </div>
        <div class="sec-field">
          <label class="sec-label">确认新密码 <span class="req">*</span></label>
          <div class="sec-input-wrap">
            <Icon name="shield-check" :size="14" class="sec-icon" />
            <input v-model="pwdConfirm" type="password" autocomplete="new-password" class="sec-inp" placeholder="再次输入新密码" />
          </div>
          <p v-if="pwdConfirm && pwdNew !== pwdConfirm" class="field-error">两次输入的密码不一致</p>
        </div>
      </form>

      <template #foot>
        <template v-if="editTab === 'info'">
          <button v-if="!editingInfo" class="btn btn-ghost" @click="showEdit = false">关闭</button>
          <button v-if="!editingInfo" class="btn btn-primary" @click="startEditInfo">
            <Icon name="edit" :size="14" /> 编辑
          </button>
          <template v-else>
            <button class="btn btn-ghost" @click="cancelEditInfo">取消</button>
            <button class="btn btn-primary" :disabled="infoSaving" @click="saveInfo">
              <Icon v-if="infoSaving" name="loader" :size="14" class="spin" /> 保存
            </button>
          </template>
        </template>
        <template v-else>
          <button class="btn btn-ghost" @click="showEdit = false">关闭</button>
          <button class="btn btn-primary" :disabled="saving" @click="onSubmitPassword">
            <Icon v-if="saving" name="loader" :size="14" class="spin" /> 确认修改
          </button>
        </template>
      </template>
    </AppModal>
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

/* ====== 编辑弹窗内 ====== */
.edit-tabs {
  display: flex;
  gap: 2px;
  padding: 4px;
  background: var(--bg-subtle);
  border-radius: var(--radius-md);
  margin-bottom: 20px;
}
.edit-tab {
  flex: 1;
  padding: 8px 12px;
  border-radius: var(--radius-md);
  border: none;
  background: transparent;
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 500;
  font-family: inherit;
  cursor: pointer;
  transition: all var(--dur-fast) var(--ease-out);
}
.edit-tab:hover { color: var(--text-primary); }
.edit-tab.active {
  background: var(--bg-surface);
  color: var(--brand);
  font-weight: 600;
  box-shadow: var(--shadow-sm);
}
.edit-body { min-height: 180px; }

.info-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px 28px;
}
.info-item { display: flex; flex-direction: column; gap: 7px; }
.info-key {
  font-size: 11.5px;
  font-weight: 600;
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
.info-val {
  font-size: 14px;
  color: var(--text-primary);
  font-weight: 500;
  min-height: 22px;
}
.id-copy { font-family: monospace; font-size: 13px; color: var(--text-tertiary); }
.info-input {
  padding: 7px 11px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-strong);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-size: 13px;
  font-family: inherit;
  transition: all var(--dur-fast) var(--ease-out);
}
.info-input:focus {
  border-color: var(--brand); outline: none;
  box-shadow: 0 0 0 3px var(--brand-ring);
}
.role-tag {
  display: inline-flex;
  padding: 2px 10px;
  border-radius: var(--radius-pill);
  font-size: 12px;
  font-weight: 600;
}
.r-admin { color: var(--brand); background: var(--brand-soft); }
.r-editor { color: var(--accent-amber); background: var(--accent-amber-soft); }
.r-viewer { color: var(--text-secondary); background: var(--bg-subtle); }
.dot-status {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 6px;
  vertical-align: middle;
}
.dot-status.on { background: var(--success); box-shadow: 0 0 6px color-mix(in srgb, var(--success) 50%, transparent); }
.dot-status.off { background: var(--danger); }

.sec-form { display: flex; flex-direction: column; gap: 18px; max-width: 420px; }
.sec-field { display: flex; flex-direction: column; gap: 7px; }
.sec-label { font-size: 13px; font-weight: 500; color: var(--text-secondary); }
.req { color: var(--danger); }
.sec-input-wrap { position: relative; display: flex; align-items: center; }
.sec-icon { position: absolute; left: 12px; color: var(--text-tertiary); pointer-events: none; }
.sec-inp {
  width: 100%; height: 42px; padding: 0 12px 0 36px;
  border: 1px solid var(--border); border-radius: var(--radius-md);
  font-size: 13.5px; color: var(--text-primary);
  background: var(--bg-subtle); font-family: inherit;
  transition: all var(--dur-fast) var(--ease-out); box-sizing: border-box;
}
.sec-inp:focus {
  outline: none; border-color: var(--brand);
  box-shadow: 0 0 0 3px var(--brand-ring); background: var(--bg-surface);
}
.sec-inp::placeholder { color: var(--text-tertiary); }

.strength-bar { display: flex; align-items: center; gap: 10px; margin-top: 2px; }
.str-track { flex: 1; height: 4px; border-radius: 2px; background: var(--border); overflow: hidden; }
.str-fill { height: 100%; border-radius: 2px; transition: all 0.25s ease; }
.str-weak { background: var(--danger); }
.str-mid { background: var(--accent-amber); }
.str-strong { background: var(--success); }
.str-label { font-size: 11px; font-weight: 600; min-width: 20px; text-align: right; }
.field-error { margin: 2px 0 0; font-size: 12px; color: var(--danger); }

.spin { animation: spin 0.9s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

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
