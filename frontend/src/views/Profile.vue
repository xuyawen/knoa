<script setup lang="ts">
// 个人中心 — 专业版：头像信息卡 + 快速统计 + Tab 切换（账户信息 / 安全设置）
import { computed, ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import { changePassword } from '@/api/auth'
import Icon from '@/components/ui/Icon.vue'

const auth = useAuthStore()
const toast = useToastStore()

/* ---------- 角色标签 ---------- */
const ROLE_LABEL: Record<string, string> = { admin: '管理员', editor: '编辑者', viewer: '访客' }
const ROLE_CLASS: Record<string, string> = { admin: 'r-admin', editor: 'r-editor', viewer: 'r-viewer' }
const roleLabel = computed(() => ROLE_LABEL[auth.user?.role || 'viewer'] || auth.user?.role || '—')
const roleClass = computed(() => ROLE_CLASS[auth.user?.role || 'viewer'] || 'r-viewer')

/* ---------- 头像首字母 ---------- */
const avatarLetter = computed(() => {
  const name = auth.user?.displayName || auth.user?.username || ''
  return name[0]?.toUpperCase() || '?'
})

/* ---------- 时间格式化 ---------- */
const createdAt = computed(() =>
  auth.user?.createdAt ? new Date(auth.user.createdAt).toLocaleDateString('zh-CN') : '—',
)

/* ---------- Tab 切换 ---------- */
type TabKey = 'info' | 'security'
const activeTab = ref<TabKey>('info')

/* ---------- 安全：修改密码 ---------- */
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

/* ---------- 密码强度指示 ---------- */
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
    <!-- ====== 顶部个人信息卡 ====== -->
    <section class="profile-header card">
      <div class="ph-left">
        <div class="avatar-ring">
          <span class="avatar-text">{{ avatarLetter }}</span>
        </div>
        <div class="ph-info">
          <h1 class="ph-name">{{ auth.user?.displayName || auth.user?.username || '—' }}</h1>
          <div class="ph-meta">
            <span class="role-tag" :class="roleClass">{{ roleLabel }}</span>
            <span class="ph-divider">|</span>
            <span class="ph-id">@{{ auth.user?.username || '—' }}</span>
          </div>
          <p class="ph-desc" v-if="auth.user?.displayName">{{ auth.user.displayName }} · {{ roleLabel }}账号</p>
        </div>
      </div>
      <div class="ph-right">
        <div class="stat-mini">
          <span class="stat-num">{{ auth.user?.isActive ? '正常' : '停用' }}</span>
          <span class="stat-label">状态</span>
        </div>
        <div class="stat-mini">
          <span class="stat-num">{{ createdAt }}</span>
          <span class="stat-label">注册时间</span>
        </div>
      </div>
    </section>

    <!-- ====== 主内容区 ====== -->
    <div class="profile-body">
      <!-- Tab 导航 -->
      <nav class="tab-nav card">
        <button
          v-for="t in [{ key: 'info', label: '账户信息', icon: 'user-circle' }, { key: 'security', label: '安全设置', icon: 'shield' }]"
          :key="t.key"
          class="tab-btn"
          :class="{ active: activeTab === t.key }"
          @click="activeTab = t.key as TabKey"
        >
          <Icon :name="t.icon" :size="14" />
          {{ t.label }}
        </button>
      </nav>

      <!-- ====== 账户信息 ====== -->
      <section v-if="activeTab === 'info'" class="tab-panel card">
        <h3 class="panel-title">基本信息</h3>
        <div class="info-grid">
          <div class="info-item">
            <label class="info-key">用户名</label>
            <div class="info-val">{{ auth.user?.username || '—' }}</div>
          </div>
          <div class="info-item">
            <label class="info-key">显示名称</label>
            <div class="info-val">{{ auth.user?.displayName || '未设置' }}</div>
          </div>
          <div class="info-item">
            <label class="info-key">角色权限</label>
            <div class="info-val"><span class="role-tag sm" :class="roleClass">{{ roleLabel }}</span></div>
          </div>
          <div class="info-item">
            <label class="info-key">账号状态</label>
            <div class="info-val">
              <span class="dot-status" :class="auth.user?.isActive ? 'on' : 'off'" />
              {{ auth.user?.isActive ? '启用' : '停用' }}
            </div>
          </div>
          <div class="info-item">
            <label class="info-key">创建时间</label>
            <div class="info-val">{{ createdAt }}</div>
          </div>
          <div class="info-item">
            <label class="info-key">用户 ID</label>
            <div class="info-val id-copy">{{ auth.user?.id || '—' }}</div>
          </div>
        </div>
      </section>

      <!-- ====== 安全设置 ====== -->
      <section v-if="activeTab === 'security'" class="tab-panel card">
        <h3 class="panel-title">修改登录密码</h3>
        <p class="panel-desc">定期更换密码有助于保护账户安全。新密码长度不少于 6 位。</p>

        <form class="sec-form" @submit.prevent="onSubmitPassword">
          <div class="sec-field">
            <label class="sec-label">当前密码 <span class="req">*</span></label>
            <div class="sec-input-wrap">
              <Icon name="lock" :size="14" class="sec-icon" />
              <input v-model="pwdOld" type="password" autocomplete="current-password"
                class="sec-inp" placeholder="输入当前密码" />
            </div>
          </div>

          <div class="sec-field">
            <label class="sec-label">新密码 <span class="req">*</span></label>
            <div class="sec-input-wrap">
              <Icon name="key" :size="14" class="sec-icon" />
              <input v-model="pwdNew" type="password" autocomplete="new-password"
                class="sec-inp" placeholder="输入新密码（至少 6 位）" />
            </div>
            <!-- 强度条 -->
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
              <input v-model="pwdConfirm" type="password" autocomplete="new-password"
                class="sec-inp" placeholder="再次输入新密码" />
            </div>
            <p v-if="pwdConfirm && pwdNew !== pwdConfirm" class="field-error">两次输入的密码不一致</p>
          </div>

          <div class="sec-actions">
            <button type="button" class="btn btn-ghost btn-sm" @click="resetPwd">重置</button>
            <button type="submit" class="btn btn-primary" :disabled="saving">
              <Icon v-if="saving" name="loader" :size="14" class="spin" />
              {{ saving ? '保存中…' : '确认修改' }}
            </button>
          </div>
        </form>
      </section>
    </div>
  </div>
</template>

<style scoped>
/* ---- 页面容器 ---- */
.profile-page {
  max-width: 900px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* ====== 顶部个人信息卡 ====== */
.profile-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 28px 30px;
}
.ph-left { display: flex; align-items: center; gap: 20px; }

.avatar-ring {
  width: 68px; height: 68px; border-radius: 50%;
  background: linear-gradient(135deg, var(--brand), #7c3aed);
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 4px 16px rgba(59, 130, 246, 0.35);
  flex-shrink: 0;
}
.avatar-text {
  font-size: 26px; font-weight: 700; color: #fff;
  letter-spacing: -0.5px;
}

.ph-info { display: flex; flex-direction: column; gap: 4px; }
.ph-name {
  margin: 0; font-size: 22px; font-weight: 700;
  color: var(--text-primary); line-height: 1.2;
}
.ph-meta { display: flex; align-items: center; gap: 8px; margin-top: 2px; }
.ph-divider { color: var(--border-strong); font-size: 12px; }
.ph-id { font-size: 13px; color: var(--text-tertiary); font-family: monospace; }
.ph-desc { margin: 4px 0 0; font-size: 13px; color: var(--text-secondary); }

.ph-right { display: flex; gap: 28px; }
.stat-mini {
  display: flex; flex-direction: column; align-items: flex-end; gap: 2px;
}
.stat-num { font-size: 15px; font-weight: 600; color: var(--text-primary); }
.stat-label { font-size: 12px; color: var(--text-tertiary); }

/* 角色标签 */
.role-tag {
  display: inline-flex; padding: 3px 10px; border-radius: var(--radius-pill);
  font-size: 12px; font-weight: 600;
}
.role-tag.sm { padding: 1px 8px; font-size: 11px; }
.r-admin { color: var(--brand); background: var(--brand-soft); }
.r-editor { color: #f59e0b; background: rgba(245,158,11,0.12); }
.r-viewer { color: var(--text-secondary); background: var(--bg-subtle); }

/* ====== Tab 导航 ===== */
.tab-nav {
  display: flex; gap: 2px; padding: 4px;
}
.tab-btn {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 10px 18px; border-radius: var(--radius-md);
  font-size: 14px; font-weight: 500;
  color: var(--text-secondary); background: transparent;
  cursor: pointer; transition: all var(--dur-fast);
  border: none; font-family: inherit;
}
.tab-btn:hover { color: var(--text-primary); background: var(--bg-hover); }
.tab-btn.active {
  color: var(--brand); background: var(--brand-soft);
  font-weight: 600;
}

/* ====== 面板通用 ===== */
.tab-panel { padding: 26px 28px; }
.panel-title {
  margin: 0 0 4px; font-size: 16px; font-weight: 700; color: var(--text-primary);
}
.panel-desc { margin: 0 0 22px; font-size: 13px; color: var(--text-tertiary); line-height: 1.5; }

/* ====== 账户信息网格 ====== */
.info-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 18px 32px;
}
.info-item { display: flex; flex-direction: column; gap: 6px; }
.info-key {
  font-size: 12px; font-weight: 500; color: var(--text-tertiary);
  text-transform: uppercase; letter-spacing: 0.5px;
}
.info-val {
  font-size: 14px; color: var(--text-primary); font-weight: 500;
  min-height: 22px;
}
.id-copy {
  font-family: monospace; font-size: 13px; color: var(--text-tertiary);
}

.dot-status {
  display: inline-block; width: 8px; height: 8px; border-radius: 50%;
  margin-right: 6px; vertical-align: middle;
}
.dot-status.on { background: var(--success); box-shadow: 0 0 6px rgba(34,197,94,0.5); }
.dot-status.off { background: var(--danger); }

/* ====== 安全表单 ===== */
.sec-form { display: flex; flex-direction: column; gap: 20px; max-width: 420px; }
.sec-field { display: flex; flex-direction: column; gap: 6px; }
.sec-label {
  font-size: 13px; font-weight: 500; color: var(--text-secondary);
}
.req { color: var(--danger); }

.sec-input-wrap {
  position: relative; display: flex; align-items: center;
}
.sec-icon {
  position: absolute; left: 12px; color: var(--text-tertiary);
  pointer-events: none;
}
.sec-inp {
  width: 100%; height: 42px; padding: 0 12px 0 36px;
  border: 1px solid var(--border); border-radius: var(--radius-md);
  font-size: 13.5px; color: var(--text-primary);
  background: var(--bg-subtle); font-family: inherit;
  transition: all var(--dur-fast); box-sizing: border-box;
}
.sec-inp:focus {
  outline: none; border-color: var(--brand);
  box-shadow: 0 0 0 3px var(--brand-ring);
  background: var(--bg-surface);
}
.sec-inp::placeholder { color: var(--text-tertiary); }

/* 密码强度 */
.strength-bar { display: flex; align-items: center; gap: 10px; margin-top: 2px; }
.str-track {
  flex: 1; height: 4px; border-radius: 2px;
  background: var(--border); overflow: hidden;
}
.str-fill { height: 100%; border-radius: 2px; transition: all 0.25s ease; }
.str-weak { background: var(--danger); }
.str-mid { background: #f59e0b; }
.str-strong { background: var(--success); }
.str-label { font-size: 11px; font-weight: 600; min-width: 20px; text-align: right; }
.str-weak.str-label, .str-mid.str-label { color: var(--text-secondary); }
.str-strong.str-label { color: var(--success); }

.field-error { margin: 2px 0 0; font-size: 12px; color: var(--danger); }

/* 操作按钮 */
.sec-actions {
  display: flex; gap: 10px; margin-top: 4px;
}
.spin { animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

/* 响应式 */
@media (max-width: 720px) {
  .profile-header { flex-direction: column; align-items: flex-start; gap: 16px; }
  .ph-right { width: 100%; justify-content: flex-start; gap: 24px; }
  .info-grid { grid-template-columns: 1fr; }
}
</style>
