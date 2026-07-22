<script setup lang="ts">
// 个人设置弹框：基本信息 / 安全设置 / 系统设置 三个 tab。
// 复用于个人中心页面的"设置"按钮，以及顶部导航"账号设置"菜单。
import { computed, ref, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import { changePassword, updateUser } from '@/api/auth'
import Icon from '@/components/ui/Icon.vue'
import AppModal from '@/components/ui/AppModal.vue'
import SystemSettingsPanel from './SystemSettingsPanel.vue'

const props = withDefaults(
  defineProps<{
    show: boolean
    initialTab?: 'info' | 'security' | 'system'
  }>(),
  { initialTab: 'info' },
)
const emit = defineEmits<{ (e: 'close'): void }>()

const auth = useAuthStore()
const toast = useToastStore()

const ROLE_LABEL: Record<string, string> = { admin: '管理员', editor: '编辑者', viewer: '访客' }
const roleLabel = computed(() => ROLE_LABEL[auth.user?.role || 'viewer'] || auth.user?.role || '—')

/* ---------- tab 状态 ---------- */
const editTab = ref<'info' | 'security' | 'system'>(props.initialTab)
const editingInfo = ref(false)
const infoDraft = ref({ displayName: '', email: '', department: '', employeeId: '' })
const infoSaving = ref(false)
const systemSettingsRef = ref<InstanceType<typeof SystemSettingsPanel> | null>(null)
const systemSaving = ref(false)

function syncInfoDraft() {
  const u = auth.user
  infoDraft.value = {
    displayName: u?.displayName || '',
    email: u?.email || '',
    department: u?.department || '',
    employeeId: u?.employeeId || '',
  }
}

// 每次打开时重置到 initialTab，并同步草稿
watch(
  () => props.show,
  (v) => {
    if (v) {
      editTab.value = props.initialTab
      editingInfo.value = false
      resetPwd()
      syncInfoDraft()
    }
  },
)

function startEditInfo() {
  editingInfo.value = true
}
function cancelEditInfo() {
  editingInfo.value = false
}

async function onSaveSystem() {
  if (!systemSettingsRef.value) return
  systemSaving.value = true
  try {
    await systemSettingsRef.value.onSave()
  } finally {
    systemSaving.value = false
  }
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
  <AppModal :show="show" title="设置" wide @close="emit('close')">
    <div class="edit-tabs">
      <button
        v-for="t in [
          { key: 'info', label: '基本信息' },
          { key: 'security', label: '安全设置' },
          { key: 'system', label: '系统设置' },
        ]"
        :key="t.key"
        class="edit-tab"
        :class="{ active: editTab === t.key }"
        @click="editTab = t.key as 'info' | 'security' | 'system'"
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
    <form v-else-if="editTab === 'security'" class="edit-body sec-form" @submit.prevent="onSubmitPassword">
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

    <!-- 系统设置 -->
    <div v-else class="edit-body">
      <SystemSettingsPanel ref="systemSettingsRef" />
    </div>

    <template #foot>
      <template v-if="editTab === 'info'">
        <button v-if="!editingInfo" class="btn btn-ghost" @click="emit('close')">关闭</button>
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
      <template v-else-if="editTab === 'security'">
        <button class="btn btn-ghost" @click="emit('close')">关闭</button>
        <button class="btn btn-primary" :disabled="saving" @click="onSubmitPassword">
          <Icon v-if="saving" name="loader" :size="14" class="spin" /> 确认修改
        </button>
      </template>
      <template v-else>
        <button class="btn btn-ghost" @click="emit('close')">关闭</button>
        <button class="btn btn-primary" :disabled="systemSaving" @click="onSaveSystem">
          <Icon v-if="systemSaving" name="loader" :size="14" class="spin" /> 保存设置
        </button>
      </template>
    </template>
  </AppModal>
</template>

<style scoped>
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
.edit-body { min-height: 360px; }

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
</style>
