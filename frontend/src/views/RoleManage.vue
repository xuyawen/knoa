<script setup lang="ts">
// 角色管理：列出全部角色，可新建/编辑/删除角色，并为角色赋予或移除权限。
// 仅用户管理员可见（路由守卫 + 后端 require_permission 双保险）。
import { ref, computed, onMounted } from 'vue'
import Icon from '@/components/ui/Icon.vue'
import AppModal from '@/components/ui/AppModal.vue'
import ConfirmDialog from '@/components/ui/ConfirmDialog.vue'
import { useToastStore } from '@/stores/toast'
import { createRole, deleteRole, getRoles, setRolePermissions, updateRole } from '@/api/auth'
import type { RoleOut, RoleCreate } from '@/types/api'
import { PERMISSIONS } from '@/types/api'

const toast = useToastStore()

const roles = ref<RoleOut[]>([])
const loading = ref(false)
const selectedId = ref<string | null>(null)

const selectedRole = computed(() => roles.value.find((r) => r.id === selectedId.value) || null)

// 当前选中角色的权限草稿（开关切换只改这里，保存才写后端）
const draftPerms = ref<Set<string>>(new Set())

async function loadRoles() {
  loading.value = true
  try {
    roles.value = await getRoles()
    if (!selectedId.value && roles.value.length) selectedId.value = roles.value[0].id
    syncDraft()
  } catch (e: any) {
    toast.error(`加载角色失败：${e?.message || e}`)
  } finally {
    loading.value = false
  }
}

function selectRole(id: string) {
  selectedId.value = id
  syncDraft()
}

function syncDraft() {
  draftPerms.value = new Set(selectedRole.value?.permissions ?? [])
}

function togglePerm(key: string) {
  const s = new Set(draftPerms.value)
  if (s.has(key)) s.delete(key)
  else s.add(key)
  draftPerms.value = s
}

// 权限相对服务端是否有改动
const dirty = computed(() => {
  const cur = new Set(selectedRole.value?.permissions ?? [])
  if (cur.size !== draftPerms.value.size) return true
  for (const k of draftPerms.value) if (!cur.has(k)) return true
  return false
})

async function savePerms() {
  if (!selectedRole.value) return
  try {
    const updated = await setRolePermissions(selectedRole.value.id, { permissions: [...draftPerms.value] })
    const idx = roles.value.findIndex((r) => r.id === updated.id)
    if (idx >= 0) roles.value[idx] = updated
    toast.success('权限已保存')
  } catch (e: any) {
    toast.error(`保存失败：${e?.message || e}`)
  }
}

/* ---------- 新建角色 ---------- */
const showCreate = ref(false)
const creating = ref(false)
const newForm = ref({ name: '', key: '', description: '', perms: new Set<string>() } as {
  name: string
  key: string
  description: string
  perms: Set<string>
})

function openCreate() {
  newForm.value = { name: '', key: '', description: '', perms: new Set() }
  showCreate.value = true
}
function toggleNewPerm(key: string) {
  const s = new Set(newForm.value.perms)
  if (s.has(key)) s.delete(key)
  else s.add(key)
  newForm.value.perms = s
}
async function confirmCreate() {
  if (!newForm.value.name.trim()) {
    toast.warning('角色名称必填')
    return
  }
  creating.value = true
  try {
    const payload: RoleCreate = {
      name: newForm.value.name.trim(),
      key: newForm.value.key.trim() || undefined,
      description: newForm.value.description.trim() || null,
      permissions: [...newForm.value.perms],
    }
    const created = await createRole(payload)
    roles.value.push(created)
    showCreate.value = false
    selectedId.value = created.id
    syncDraft()
    toast.success('角色已创建')
  } catch (e: any) {
    toast.error(`创建失败：${e?.message || e}`)
  } finally {
    creating.value = false
  }
}

/* ---------- 删除角色 ---------- */
const deleteTarget = ref<RoleOut | null>(null)
function onDelete(r: RoleOut) {
  if (r.isBuiltin) {
    toast.warning('内置角色不可删除')
    return
  }
  deleteTarget.value = r
}
async function confirmDelete() {
  const r = deleteTarget.value
  deleteTarget.value = null
  if (!r) return
  try {
    await deleteRole(r.id)
    roles.value = roles.value.filter((x) => x.id !== r.id)
    if (selectedId.value === r.id) selectedId.value = roles.value[0]?.id ?? null
    syncDraft()
    toast.success(`已删除角色：${r.name}`)
  } catch (e: any) {
    toast.error(`删除失败：${e?.message || e}`)
  }
}

/* ---------- 编辑名称/描述 ---------- */
const editingName = ref(false)
const nameDraft = ref({ name: '', description: '' })
function openEditName() {
  if (!selectedRole.value) return
  nameDraft.value = { name: selectedRole.value.name, description: selectedRole.value.description || '' }
  editingName.value = true
}
async function saveName() {
  if (!selectedRole.value) return
  try {
    const updated = await updateRole(selectedRole.value.id, {
      name: nameDraft.value.name.trim(),
      description: nameDraft.value.description.trim() || null,
    })
    const idx = roles.value.findIndex((r) => r.id === updated.id)
    if (idx >= 0) roles.value[idx] = updated
    editingName.value = false
    toast.success('角色信息已更新')
  } catch (e: any) {
    toast.error(`更新失败：${e?.message || e}`)
  }
}

onMounted(loadRoles)
</script>

<template>
  <div class="page role-mgmt fade-up">
    <div class="rm-body">
      <!-- 左侧：角色列表 -->
      <section class="card rm-list">
        <div class="rm-h-row">
          <h3 class="rm-h">角色</h3>
          <button class="btn btn-primary btn-sm" @click="openCreate"><Icon name="plus" :size="13" /> 新建角色</button>
        </div>
        <div v-if="loading" class="rm-loading"><Icon name="loader" :size="18" class="spin" /> 加载中…</div>
        <ul v-else class="rm-cards">
          <li
            v-for="r in roles"
            :key="r.id"
            class="rm-card"
            :class="{ active: r.id === selectedId }"
            @click="selectRole(r.id)"
          >
            <div class="rm-card-top">
              <span class="rm-name">{{ r.name }}</span>
              <span v-if="r.isBuiltin" class="builtin-tag">内置</span>
            </div>
            <div class="rm-key">{{ r.key }}</div>
            <div class="rm-desc">{{ r.description || '—' }}</div>
            <div class="rm-card-actions" @click.stop>
              <button class="action-btn" title="编辑信息" @click="selectRole(r.id); openEditName()"><Icon name="edit" :size="14" /></button>
              <button class="action-btn" title="删除角色" :disabled="r.isBuiltin" @click="onDelete(r)"><Icon name="trash" :size="14" /></button>
            </div>
          </li>
        </ul>
      </section>

      <!-- 右侧：权限矩阵 -->
      <section class="card rm-detail">
        <template v-if="selectedRole">
          <div class="rm-d-h">
            <div>
              <h3 class="rm-h">
                {{ selectedRole.name }}
                <span v-if="selectedRole.isBuiltin" class="builtin-tag">内置</span>
              </h3>
              <div class="rm-key">{{ selectedRole.key }}</div>
            </div>
            <button class="btn btn-ghost btn-sm" @click="openEditName"><Icon name="edit" :size="13" /> 编辑信息</button>
          </div>

          <p class="rm-desc-full">{{ selectedRole.description || '暂无描述' }}</p>

          <h4 class="rm-sub">权限配置</h4>
          <div class="perm-rows">
            <div v-for="p in PERMISSIONS" :key="p.key" class="perm-row">
              <div class="perm-meta">
                <span class="perm-label">{{ p.label }}</span>
                <span class="perm-group">{{ p.group }}</span>
              </div>
              <label class="switch" @click.prevent="togglePerm(p.key)">
                <input type="checkbox" :checked="draftPerms.has(p.key)" />
                <span class="switch-track"><span class="switch-knob" /></span>
                <span class="switch-text">{{ draftPerms.has(p.key) ? '已授予' : '未授予' }}</span>
              </label>
            </div>
          </div>

          <div class="rm-foot">
            <button class="btn btn-primary btn-sm" :disabled="!dirty" @click="savePerms">
              {{ dirty ? '保存权限' : '无改动' }}
            </button>
          </div>
        </template>
        <div v-else class="rm-empty">请选择左侧角色</div>
      </section>
    </div>

    <!-- 新建角色弹窗 -->
    <AppModal :show="showCreate" title="新建角色" @close="showCreate = false">
      <div class="form-row">
        <label class="form-label">角色名称</label>
        <input v-model="newForm.name" class="form-input" placeholder="如：审核员" />
      </div>
      <div class="form-row">
        <label class="form-label">角色 Key</label>
        <input v-model="newForm.key" class="form-input" placeholder="留空自动生成（custom_xxx）" />
      </div>
      <div class="form-row">
        <label class="form-label">描述</label>
        <input v-model="newForm.description" class="form-input" placeholder="可选" />
      </div>
      <div class="form-row form-row-col">
        <label class="form-label">初始权限</label>
        <div class="perm-checks">
          <label v-for="p in PERMISSIONS" :key="p.key" class="perm-check" @click.prevent="toggleNewPerm(p.key)">
            <input type="checkbox" :checked="newForm.perms.has(p.key)" />
            <span>{{ p.label }}</span>
          </label>
        </div>
      </div>
      <template #foot>
        <button class="btn btn-ghost btn-sm" @click="showCreate = false">取消</button>
        <button class="btn btn-primary btn-sm" :disabled="creating" @click="confirmCreate">
          {{ creating ? '创建中…' : '创建' }}
        </button>
      </template>
    </AppModal>

    <!-- 编辑名称/描述弹窗 -->
    <AppModal :show="editingName" title="编辑角色信息" @close="editingName = false">
      <div class="form-row">
        <label class="form-label">角色名称</label>
        <input v-model="nameDraft.name" class="form-input" />
      </div>
      <div class="form-row">
        <label class="form-label">描述</label>
        <input v-model="nameDraft.description" class="form-input" />
      </div>
      <template #foot>
        <button class="btn btn-ghost btn-sm" @click="editingName = false">取消</button>
        <button class="btn btn-primary btn-sm" @click="saveName">保存</button>
      </template>
    </AppModal>

    <ConfirmDialog
      :show="!!deleteTarget"
      title="删除角色"
      :message="deleteTarget ? `确认删除角色「${deleteTarget.name}」？该角色下的用户将失去对应权限，操作不可恢复。` : ''"
      confirm-text="删除"
      danger
      @close="deleteTarget = null"
      @confirm="confirmDelete"
    />
  </div>
</template>

<style scoped>
.rm-body {
  display: grid;
  grid-template-columns: 320px 1fr;
  gap: 16px;
  align-items: start;
}
.rm-list { padding: 20px; }
.rm-h { margin: 0; font-size: 15px; font-weight: 600; color: var(--text-primary); }
.rm-h-row { display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; }
.rm-loading { display: flex; align-items: center; gap: 8px; color: var(--text-tertiary); font-size: 13px; padding: 20px 0; }
.rm-cards { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 10px; }
.rm-card {
  position: relative; padding: 12px 14px; border: 1px solid var(--border); border-radius: var(--radius-lg);
  cursor: pointer; transition: all var(--dur-fast); background: var(--bg-surface);
}
.rm-card:hover { border-color: var(--brand); }
.rm-card.active { border-color: var(--brand); box-shadow: 0 0 0 3px var(--brand-ring); }
.rm-card-top { display: flex; align-items: center; gap: 8px; }
.rm-name { font-size: 14px; font-weight: 600; color: var(--text-primary); }
.rm-key { font-size: 12px; color: var(--text-tertiary); margin-top: 2px; font-family: var(--font-mono); }
.rm-desc { font-size: 12px; color: var(--text-secondary); margin-top: 6px; line-height: 1.5;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.rm-card-actions { position: absolute; top: 10px; right: 10px; display: flex; gap: 2px; opacity: 0; transition: opacity var(--dur-fast); }
.rm-card:hover .rm-card-actions { opacity: 1; }
.action-btn {
  display: flex; align-items: center; justify-content: center; width: 26px; height: 26px;
  border-radius: var(--radius-sm); color: var(--text-secondary); background: transparent; cursor: pointer; transition: all var(--dur-fast);
}
.action-btn:hover { background: var(--bg-hover); color: var(--text-primary); }
.action-btn:disabled { opacity: 0.35; cursor: not-allowed; }

.rm-detail { padding: 20px; min-height: 360px; }
.rm-d-h { display: flex; align-items: flex-start; justify-content: space-between; }
.rm-key { font-size: 12px; color: var(--text-tertiary); margin-top: 4px; font-family: var(--font-mono); }
.rm-desc-full { margin: 12px 0 0; font-size: 13px; color: var(--text-secondary); line-height: 1.6; }
.rm-sub { margin: 20px 0 12px; font-size: 14px; font-weight: 600; color: var(--text-primary); }
.perm-rows { display: flex; flex-direction: column; gap: 2px; }
.perm-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: 11px 4px; border-bottom: 1px solid var(--border);
}
.perm-row:last-child { border-bottom: none; }
.perm-meta { display: flex; align-items: baseline; gap: 10px; }
.perm-label { font-size: 13.5px; color: var(--text-primary); }
.perm-group { font-size: 12px; color: var(--text-tertiary); }
.rm-foot { margin-top: 18px; display: flex; justify-content: flex-end; }
.rm-empty { display: flex; align-items: center; justify-content: center; height: 300px; color: var(--text-tertiary); }

.builtin-tag {
  display: inline-block; padding: 1px 7px; border-radius: var(--radius-pill);
  font-size: 10px; font-weight: 500; color: var(--accent-blue); background: var(--accent-blue-soft);
}

/* 开关 */
.switch { display: inline-flex; align-items: center; gap: 8px; cursor: pointer; }
.switch input { display: none; }
.switch-track {
  width: 38px; height: 22px; border-radius: var(--radius-pill); background: var(--border-strong);
  position: relative; transition: background var(--dur-fast);
}
.switch-knob {
  position: absolute; top: 2px; left: 2px; width: 18px; height: 18px; border-radius: 50%; background: #fff; transition: transform var(--dur-fast);
}
.switch input:checked + .switch-track { background: var(--brand); }
.switch input:checked + .switch-track .switch-knob { transform: translateX(16px); }
.switch-text { font-size: 13px; color: var(--text-secondary); }

/* 表单 */
.form-row { display: flex; align-items: center; gap: 12px; margin-bottom: 14px; }
.form-row-col { align-items: flex-start; }
.form-label { width: 76px; flex-shrink: 0; font-size: 13px; color: var(--text-secondary); }
.form-input {
  flex: 1; height: 36px; padding: 0 12px; border: 1px solid var(--border); border-radius: var(--radius-md);
  font-size: 13px; background: var(--bg-surface); color: var(--text-primary); transition: all var(--dur-fast);
}
.form-input:focus { outline: none; border-color: var(--brand); box-shadow: 0 0 0 3px var(--brand-ring); }
.perm-checks { flex: 1; display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.perm-check {
  display: flex; align-items: center; gap: 7px; font-size: 13px; color: var(--text-secondary);
  padding: 6px 8px; border: 1px solid var(--border); border-radius: var(--radius-md); cursor: pointer;
}
.perm-check input { accent-color: var(--brand); }

.spin { animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

@media (max-width: 900px) {
  .rm-body { grid-template-columns: 1fr; }
}
</style>
