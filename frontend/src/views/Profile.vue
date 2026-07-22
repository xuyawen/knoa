<script setup lang="ts">
// 个人中心 — 专业版（参考 Ant Design Pro 个人页）：左侧资料卡 + 右侧 Tab 内容区
import { computed, ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import { changePassword, updateUser } from '@/api/auth'
import { getSessions } from '@/api'
import Icon from '@/components/ui/Icon.vue'

const auth = useAuthStore()
const toast = useToastStore()

/* ---------- 角色标签 ---------- */
const ROLE_LABEL: Record<string, string> = { admin: '管理员', editor: '编辑者', viewer: '访客' }
const ROLE_CLASS: Record<string, string> = { admin: 'r-admin', editor: 'r-editor', viewer: 'r-viewer' }
const roleLabel = computed(() => ROLE_LABEL[auth.user?.role || 'viewer'] || auth.user?.role || '—')
const roleClass = computed(() => ROLE_CLASS[auth.user?.role || 'viewer'] || 'r-viewer')

const avatarLetter = computed(() => {
  const name = auth.user?.displayName || auth.user?.username || ''
  return name[0]?.toUpperCase() || '?'
})

/* ---------- 注册天数 ---------- */
const daysSince = computed(() => {
  if (!auth.user?.createdAt) return '—'
  const diff = Date.now() - new Date(auth.user.createdAt).getTime()
  const d = Math.floor(diff / 86400000)
  return d > 0 ? `${d} 天` : '今天'
})

/* ---------- 会话数（真实数据） ---------- */
const sessionCount = ref<number | null>(null)
onMounted(async () => {
  try {
    const list = await getSessions()
    sessionCount.value = list.length
  } catch {
    sessionCount.value = null
  }
})

/* ---------- Tab ---------- */
type TabKey = 'info' | 'security'
const activeTab = ref<TabKey>('info')

/* ---------- 基本信息：显示名可编辑 ---------- */
const editingInfo = ref(false)
const displayNameDraft = ref('')
const infoSaving = ref(false)

function startEditInfo() {
  displayNameDraft.value = auth.user?.displayName || ''
  editingInfo.value = true
}
function cancelEditInfo() {
  editingInfo.value = false
  displayNameDraft.value = ''
}
async function saveInfo() {
  if (!auth.user) return
  infoSaving.value = true
  try {
    await updateUser(auth.user.id, { displayName: displayNameDraft.value.trim() || null })
    await auth.fetchMe()
    editingInfo.value = false
    toast.success('资料已更新')
  } catch (e: any) {
    toast.error(e?.message || '更新失败')
  } finally {
    infoSaving.value = false
  }
}

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
    <div class="profile-grid">
      <!-- ====== 左侧资料卡 ====== -->
      <aside class="profile-rail card">
        <div class="rail-banner" />
        <div class="rail-body">
          <div class="rail-avatar">
            <span class="ra-text">{{ avatarLetter }}</span>
            <span class="ra-status" :class="auth.user?.isActive ? 'on' : 'off'" />
          </div>
          <h1 class="rail-name">{{ auth.user?.displayName || auth.user?.username || '—' }}</h1>
          <div class="rail-role">
            <span class="role-tag" :class="roleClass">{{ roleLabel }}</span>
            <span class="rail-uname">@{{ auth.user?.username }}</span>
          </div>

          <p class="rail-bio" v-if="auth.user?.displayName">
            这是你在 Knoa 智能知识库的工作账号，负责 {{ roleLabel }} 相关工作。
          </p>

          <!-- 统计 -->
          <div class="rail-stats">
            <div class="rs-item">
              <span class="rs-num">{{ daysSince }}</span>
              <span class="rs-label">注册时长</span>
            </div>
            <div class="rs-divider" />
            <div class="rs-item">
              <span class="rs-num">{{ sessionCount ?? '—' }}</span>
              <span class="rs-label">对话数</span>
            </div>
            <div class="rs-divider" />
            <div class="rs-item">
              <span class="rs-num" :class="auth.user?.isActive ? 'ok' : 'bad'">
                {{ auth.user?.isActive ? '正常' : '停用' }}
              </span>
              <span class="rs-label">状态</span>
            </div>
          </div>

          <button class="rail-edit" @click="activeTab = 'security'">
            <Icon name="key" :size="14" /> 修改密码
          </button>
        </div>
      </aside>

      <!-- ====== 右侧内容 ====== -->
      <div class="profile-main">
        <nav class="tab-nav card">
          <button
            v-for="t in [{ key: 'info', label: '基本信息', icon: 'user-circle' }, { key: 'security', label: '安全设置', icon: 'shield' }]"
            :key="t.key"
            class="tab-btn"
            :class="{ active: activeTab === t.key }"
            @click="activeTab = t.key as TabKey"
          >
            <Icon :name="t.icon" :size="14" />
            {{ t.label }}
          </button>
        </nav>

        <!-- 基本信息 -->
        <section v-if="activeTab === 'info'" class="tab-panel card">
          <h3 class="panel-title">
            基本信息
            <button v-if="!editingInfo" class="panel-edit" @click="startEditInfo">
              <Icon name="pen-line" :size="13" /> 编辑
            </button>
            <span v-else class="panel-edit-actions">
              <button class="panel-save" :disabled="infoSaving" @click="saveInfo">保存</button>
              <button class="panel-cancel" @click="cancelEditInfo">取消</button>
            </span>
          </h3>
          <p class="panel-desc">你的账户公开资料和权限信息。</p>
          <div class="info-grid">
            <div class="info-item">
              <span class="info-key">用户名</span>
              <span class="info-val">{{ auth.user?.username || '—' }}</span>
            </div>
            <div class="info-item">
              <span class="info-key">显示名称</span>
              <span v-if="!editingInfo" class="info-val">{{ auth.user?.displayName || '未设置' }}</span>
              <input
                v-else
                v-model="displayNameDraft"
                class="info-input"
                maxlength="50"
                :placeholder="auth.user?.displayName || '未设置'"
              />
            </div>
            <div class="info-item">
              <span class="info-key">角色权限</span>
              <span class="info-val"><span class="role-tag sm" :class="roleClass">{{ roleLabel }}</span></span>
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
        </section>

        <!-- 安全设置 -->
        <section v-if="activeTab === 'security'" class="tab-panel card">
          <h3 class="panel-title">修改登录密码</h3>
          <p class="panel-desc">定期更换密码有助于保护账户安全，新密码长度不少于 6 位。</p>
          <form class="sec-form" @submit.prevent="onSubmitPassword">
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
  </div>
</template>

<style scoped>
.profile-page { max-width: 1040px; }
.profile-grid {
  display: grid;
  grid-template-columns: 300px 1fr;
  gap: 20px;
  align-items: start;
}

/* ====== 左侧资料卡 ====== */
.profile-rail {
  overflow: hidden;
  padding: 0;
}
.rail-banner {
  height: 76px;
  background: linear-gradient(120deg, var(--brand), var(--brand-hover) 70%, var(--brand-active));
  position: relative;
}
.rail-banner::after {
  content: '';
  position: absolute;
  inset: 0;
  background: radial-gradient(circle at 80% 20%, rgba(255,255,255,0.25), transparent 60%);
}
.rail-body { padding: 0 22px 22px; }
.rail-avatar {
  position: relative;
  width: 76px; height: 76px;
  margin-top: -38px;
  margin-bottom: 14px;
  border-radius: 50%;
  background: var(--bg-surface);
  padding: 4px;
  box-shadow: 0 4px 14px rgba(0,0,0,0.25);
}
.ra-text {
  display: flex; align-items: center; justify-content: center;
  width: 100%; height: 100%;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--brand), var(--brand-active));
  color: var(--text-on-brand); font-size: 28px; font-weight: 700;
}
.ra-status {
  position: absolute; right: 6px; bottom: 6px;
  width: 14px; height: 14px; border-radius: 50%;
  border: 3px solid var(--bg-surface);
}
.ra-status.on { background: var(--success); }
.ra-status.off { background: var(--danger); }

.rail-name { margin: 0; font-size: 19px; font-weight: 700; color: var(--text-primary); }
.rail-role { display: flex; align-items: center; gap: 8px; margin-top: 8px; }
.rail-uname { font-size: 13px; color: var(--text-tertiary); font-family: monospace; }
.rail-bio { margin: 14px 0 0; font-size: 13px; color: var(--text-secondary); line-height: 1.6; }

.rail-stats {
  display: flex; align-items: center;
  margin-top: 18px; padding: 16px 0;
  border-top: 1px solid var(--border);
  border-bottom: 1px solid var(--border);
}
.rs-item { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 3px; }
.rs-num { font-size: 16px; font-weight: 700; color: var(--text-primary); }
.rs-num.ok { color: var(--success); }
.rs-num.bad { color: var(--danger); }
.rs-label { font-size: 12px; color: var(--text-tertiary); }
.rs-divider { width: 1px; height: 28px; background: var(--border); }

.rail-edit {
  margin-top: 20px;
  width: 100%; height: 40px;
  display: inline-flex; align-items: center; justify-content: center; gap: 6px;
  border: 1px solid var(--border); border-radius: var(--radius-md);
  background: var(--bg-subtle); color: var(--text-primary);
  font-size: 13px; font-weight: 500; font-family: inherit; cursor: pointer;
  transition: all var(--dur-fast);
}
.rail-edit:hover { border-color: var(--brand); color: var(--brand); background: var(--brand-soft); }

/* 角色标签 */
.role-tag {
  display: inline-flex; padding: 3px 11px; border-radius: var(--radius-pill);
  font-size: 12px; font-weight: 600;
}
.role-tag.sm { padding: 1px 9px; font-size: 11px; }
.r-admin { color: var(--brand); background: var(--brand-soft); }
.r-editor { color: var(--accent-amber); background: var(--accent-amber-soft); }
.r-viewer { color: var(--text-secondary); background: var(--bg-subtle); }

/* ====== 右侧 ====== */
.profile-main { display: flex; flex-direction: column; gap: 16px; }
.tab-nav { display: flex; gap: 2px; padding: 4px; }
.tab-btn {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 10px 18px; border-radius: var(--radius-md);
  font-size: 14px; font-weight: 500;
  color: var(--text-secondary); background: transparent;
  cursor: pointer; border: none; font-family: inherit; transition: all var(--dur-fast);
}
.tab-btn:hover { color: var(--text-primary); background: var(--bg-hover); }
.tab-btn.active { color: var(--brand); background: var(--brand-soft); font-weight: 600; }

.tab-panel { padding: 26px 28px; }
.panel-title { margin: 0 0 4px; font-size: 16px; font-weight: 700; color: var(--text-primary); display: flex; align-items: center; gap: 10px; }
.panel-desc { margin: 0 0 22px; font-size: 13px; color: var(--text-tertiary); line-height: 1.5; }

.info-grid {
  display: grid; grid-template-columns: 1fr 1fr; gap: 18px 32px;
}
.info-item { display: flex; flex-direction: column; gap: 6px; }
.info-key {
  font-size: 12px; font-weight: 500; color: var(--text-tertiary);
  text-transform: uppercase; letter-spacing: 0.5px;
}
.info-val { font-size: 14px; color: var(--text-primary); font-weight: 500; min-height: 22px; }
.id-copy { font-family: monospace; font-size: 13px; color: var(--text-tertiary); }

/* 基本信息编辑态 */
.panel-edit {
  margin-left: auto;
  display: inline-flex; align-items: center; gap: 4px;
  padding: 4px 11px; border-radius: var(--radius-md);
  border: 1px solid var(--border); background: var(--bg-subtle);
  color: var(--text-secondary); font-size: 12px; font-family: inherit; cursor: pointer;
  transition: all var(--dur-fast);
}
.panel-edit:hover { border-color: var(--brand); color: var(--brand); background: var(--brand-soft); }
.panel-edit-actions { margin-left: auto; display: inline-flex; gap: 8px; }
.panel-save {
  padding: 4px 14px; border-radius: var(--radius-md);
  border: 1px solid var(--brand); background: var(--brand); color: var(--text-on-brand);
  font-size: 12px; font-family: inherit; cursor: pointer;
}
.panel-save:disabled { opacity: 0.6; cursor: default; }
.panel-cancel {
  padding: 4px 14px; border-radius: var(--radius-md);
  border: 1px solid var(--border); background: var(--bg-subtle);
  color: var(--text-secondary); font-size: 12px; font-family: inherit; cursor: pointer;
}
.info-input {
  flex: 1; padding: 6px 10px; border-radius: var(--radius-md);
  border: 1px solid var(--border-strong); background: var(--bg-surface);
  color: var(--text-primary); font-size: 13px; font-family: inherit;
}
.info-input:focus { border-color: var(--brand); outline: none; }
.dot-status {
  display: inline-block; width: 8px; height: 8px; border-radius: 50%;
  margin-right: 6px; vertical-align: middle;
}
.dot-status.on { background: var(--success); box-shadow: 0 0 6px color-mix(in srgb, var(--success) 50%, transparent); }
.dot-status.off { background: var(--danger); }

/* ====== 安全表单 ====== */
.sec-form { display: flex; flex-direction: column; gap: 20px; max-width: 420px; }
.sec-field { display: flex; flex-direction: column; gap: 6px; }
.sec-label { font-size: 13px; font-weight: 500; color: var(--text-secondary); }
.req { color: var(--danger); }
.sec-input-wrap { position: relative; display: flex; align-items: center; }
.sec-icon { position: absolute; left: 12px; color: var(--text-tertiary); pointer-events: none; }
.sec-inp {
  width: 100%; height: 42px; padding: 0 12px 0 36px;
  border: 1px solid var(--border); border-radius: var(--radius-md);
  font-size: 13.5px; color: var(--text-primary);
  background: var(--bg-subtle); font-family: inherit;
  transition: all var(--dur-fast); box-sizing: border-box;
}
.sec-inp:focus { outline: none; border-color: var(--brand); box-shadow: 0 0 0 3px var(--brand-ring); background: var(--bg-surface); }
.sec-inp::placeholder { color: var(--text-tertiary); }

.strength-bar { display: flex; align-items: center; gap: 10px; margin-top: 2px; }
.str-track { flex: 1; height: 4px; border-radius: 2px; background: var(--border); overflow: hidden; }
.str-fill { height: 100%; border-radius: 2px; transition: all 0.25s ease; }
.str-weak { background: var(--danger); }
.str-mid { background: var(--accent-amber); }
.str-strong { background: var(--success); }
.str-label { font-size: 11px; font-weight: 600; min-width: 20px; text-align: right; }
.field-error { margin: 2px 0 0; font-size: 12px; color: var(--danger); }

.sec-actions { display: flex; gap: 10px; margin-top: 4px; }
.spin { animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

@media (max-width: 840px) {
  .profile-grid { grid-template-columns: 1fr; }
  .info-grid { grid-template-columns: 1fr; }
}
</style>
