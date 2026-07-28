<script setup lang="ts">
// KB 成员管理弹窗（库级授权 / 严格隔离下的共享入口），从 DocumentLibrary.vue 拆出。
// 三个 Tab：个人成员 / 部门授权 / 有效权限预览。
import { ref, computed, watch } from 'vue'
import Icon from '@/components/ui/Icon.vue'
import AppModal from '@/components/ui/AppModal.vue'
import CustomSelect from '@/components/ui/CustomSelect.vue'
import DepartmentSelect from '@/components/ui/DepartmentSelect.vue'
import { useToastStore } from '@/stores/toast'
import { errMsg } from '@/utils/errmsg'
import { getKbMembers, setKbMembers, getKbDeptGrants, setKbDeptGrants, getKbEffectiveMembers, getDepartments } from '@/api'
import type { KBMember, KBDeptGrant, EffectiveMember, UserOut, DepartmentNode } from '@/types/api'
import UserSearchSelect from '@/components/ui/UserSearchSelect.vue'

const props = defineProps<{
  show: boolean
  kbId: string
  kbName: string
}>()

const emit = defineEmits<{ (e: 'close'): void }>()

const toast = useToastStore()

// --- Tab 状态 ---
const activeTab = ref<'members' | 'dept' | 'preview'>('members')
const tabs = [
  { key: 'members' as const, label: '个人成员' },
  { key: 'dept' as const, label: '部门授权' },
  { key: 'preview' as const, label: '有效权限预览' },
]

// --- 个人成员 ---
const memberRows = ref<KBMember[]>([])
const loading = ref(false)
const saving = ref(false)
const newUserLevel = ref<'view' | 'edit' | 'admin'>('view')
const excludeIds = computed(() => memberRows.value.map((m) => m.userId))

const levelOptions = [
  { label: '可查看', value: 'view' },
  { label: '可编辑', value: 'edit' },
  { label: '管理员', value: 'admin' },
]

// --- 部门授权 ---
const deptGrants = ref<KBDeptGrant[]>([])
const deptLoading = ref(false)
const deptSaving = ref(false)
const newDeptId = ref('')
// 部门名称查找表（选中即添加时解析名称）
const deptNameMap = ref<Record<string, string>>({})

// --- 有效权限预览 ---
const effectiveMembers = ref<EffectiveMember[]>([])
const previewLoading = ref(false)

// 每次打开时自动拉取成员列表
watch(
  () => props.show,
  (v) => {
    if (v) {
      activeTab.value = 'members'
      void load()
    }
  },
)

watch(activeTab, (tab) => {
  if (tab === 'dept') {
    if (!deptGrants.value.length) void loadDeptGrants()
    void loadDeptNames()
  }
  if (tab === 'preview') void loadPreview()
})

async function loadDeptNames() {
  try {
    const tree = await getDepartments()
    const map: Record<string, string> = {}
    const walk = (nodes: DepartmentNode[]) => {
      for (const n of nodes) {
        map[n.id] = n.name
        if (n.children?.length) walk(n.children)
      }
    }
    walk(tree)
    deptNameMap.value = map
  } catch { /* ignore */ }
}

// 选中部门即添加（仿照个人成员的 UserSearchSelect 交互）
watch(newDeptId, (id) => {
  if (!id) return
  if (deptGrants.value.some((g) => g.deptId === id)) {
    toast.warning('该部门已在授权列表中')
    newDeptId.value = ''
    return
  }
  deptGrants.value.push({
    id: `tmp_${Date.now()}`,
    deptId: id,
    deptName: deptNameMap.value[id] || '(未知部门)',
    level: 'view',
  })
  newDeptId.value = ''
})

async function load() {
  loading.value = true
  newUserLevel.value = 'view'
  try {
    memberRows.value = await getKbMembers(props.kbId)
  } catch (e: unknown) {
    toast.error(`加载成员失败：${errMsg(e)}`)
    emit('close')
  } finally {
    loading.value = false
  }
}

async function loadDeptGrants() {
  deptLoading.value = true
  try {
    deptGrants.value = await getKbDeptGrants(props.kbId)
  } catch (e: unknown) {
    toast.error(`加载部门授权失败：${errMsg(e)}`)
  } finally {
    deptLoading.value = false
  }
}

async function loadPreview() {
  previewLoading.value = true
  try {
    effectiveMembers.value = await getKbEffectiveMembers(props.kbId)
  } catch (e: unknown) {
    toast.error(`加载有效权限失败：${errMsg(e)}`)
  } finally {
    previewLoading.value = false
  }
}

// 搜索选择器选中用户即添加
function onUserSelect(u: UserOut) {
  if (memberRows.value.some((m) => m.userId === u.id)) {
    toast.warning('该用户已在成员列表中')
    return
  }
  memberRows.value.push({
    userId: u.id,
    username: u.username,
    displayName: u.displayName,
    level: newUserLevel.value,
  })
  newUserLevel.value = 'view'
}

function removeMember(userId: string) {
  memberRows.value = memberRows.value.filter((m) => m.userId !== userId)
}

async function saveMembers() {
  const admins = memberRows.value.filter((m) => m.level === 'admin')
  const deptAdmins = deptGrants.value.filter((g) => g.level === 'admin')
  if (!admins.length && !deptAdmins.length) {
    toast.error('至少保留一名管理员（个人或部门），否则知识库将无法管理')
    return
  }
  saving.value = true
  try {
    const updated = await setKbMembers(props.kbId, {
      members: memberRows.value.map((m) => ({ userId: m.userId, level: m.level })),
    })
    memberRows.value = updated
    toast.success('成员权限已保存')
    emit('close')
  } catch (e: unknown) {
    toast.error(`保存失败：${errMsg(e)}`)
  } finally {
    saving.value = false
  }
}

// --- 部门授权操作 ---
function removeDeptGrant(deptId: string) {
  deptGrants.value = deptGrants.value.filter((g) => g.deptId !== deptId)
}

async function saveDeptGrants() {
  deptSaving.value = true
  try {
    deptGrants.value = await setKbDeptGrants(props.kbId, {
      grants: deptGrants.value.map((g) => ({ deptId: g.deptId, level: g.level })),
    })
    toast.success('部门授权已保存')
  } catch (e: unknown) {
    toast.error(`保存失败：${errMsg(e)}`)
  } finally {
    deptSaving.value = false
  }
}

function sourceLabel(source: string): string {
  if (source === 'direct') return '直接授权'
  return source.replace('dept:', '部门继承: ')
}
</script>

<template>
  <AppModal :show="show" :title="`管理成员 · ${kbName}`" wide @close="emit('close')">
    <!-- Tab 导航 -->
    <div class="tab-bar">
      <button
        v-for="t in tabs"
        :key="t.key"
        class="tab-btn"
        :class="{ active: activeTab === t.key }"
        @click="activeTab = t.key"
      >{{ t.label }}</button>
    </div>

    <!-- Tab 1: 个人成员 -->
    <div v-if="activeTab === 'members'">
      <div v-if="loading" class="modal-hint">加载中…</div>
      <template v-else>
        <div class="member-add">
          <UserSearchSelect
            :exclude-ids="excludeIds"
            placeholder="搜索用户名或姓名…"
            width="100%"
            @select="onUserSelect"
          />
        </div>
        <p class="member-footnote">提示：新成员默认为「可查看」权限，可在下方列表中调整级别。至少保留一名管理员。</p>
        <div class="member-list">
          <div v-for="m in memberRows" :key="m.userId" class="member-row">
            <div class="member-info">
              <span class="member-name">{{ m.displayName || m.username }}</span>
              <span class="member-uname">@{{ m.username }}</span>
            </div>
            <CustomSelect v-model="m.level" :options="levelOptions" width="110px" />
            <button class="action-btn" title="移除成员" @click="removeMember(m.userId)">
              <Icon name="close" :size="15" />
            </button>
          </div>
          <div v-if="!memberRows.length" class="member-empty">暂无成员</div>
        </div>
      </template>
    </div>

    <!-- Tab 2: 部门授权 -->
    <div v-if="activeTab === 'dept'">
      <div v-if="deptLoading" class="modal-hint">加载中…</div>
      <template v-else>
        <div class="member-add">
          <DepartmentSelect v-model="newDeptId" :allow-empty="false" placeholder="选择部门即添加…" width="100%" />
        </div>
        <p class="member-footnote">提示：授权给某部门后，该部门及其所有下级部门的用户均继承此权限。新添加默认为「可查看」。</p>
        <div class="member-list">
          <div v-for="g in deptGrants" :key="g.deptId" class="member-row">
            <div class="member-info">
              <span class="member-name">{{ g.deptName }}</span>
              <span class="member-uname">部门继承</span>
            </div>
            <CustomSelect v-model="g.level" :options="levelOptions" width="110px" />
            <button class="action-btn" title="移除部门" @click="removeDeptGrant(g.deptId)">
              <Icon name="close" :size="15" />
            </button>
          </div>
          <div v-if="!deptGrants.length" class="member-empty">暂无部门授权</div>
        </div>
      </template>
    </div>

    <!-- Tab 3: 有效权限预览 -->
    <div v-if="activeTab === 'preview'">
      <div v-if="previewLoading" class="modal-hint">加载中…</div>
      <template v-else>
        <p class="member-footnote">合并结果：个人显式优先，无个人记录则取部门继承。</p>
        <div class="member-list">
          <div v-for="m in effectiveMembers" :key="m.userId" class="member-row">
            <div class="member-info">
              <span class="member-name">{{ m.displayName || m.username }}</span>
              <span class="member-uname">@{{ m.username }}</span>
            </div>
            <span class="source-tag" :class="m.source === 'direct' ? 'tag-direct' : 'tag-dept'">
              {{ sourceLabel(m.source) }}
            </span>
            <span class="level-badge">{{ levelOptions.find(o => o.value === m.level)?.label || m.level }}</span>
          </div>
          <div v-if="!effectiveMembers.length" class="member-empty">无有效成员（开放库全员可见，不在此列出）</div>
        </div>
      </template>
    </div>

    <template #foot>
      <button class="btn btn-ghost btn-sm" @click="emit('close')">取消</button>
      <button
        v-if="activeTab === 'members'"
        class="btn btn-primary btn-sm"
        :disabled="saving"
        @click="saveMembers"
      ><span v-if="saving" class="spinner sm"></span> 保存成员</button>
      <button
        v-if="activeTab === 'dept'"
        class="btn btn-primary btn-sm"
        :disabled="deptSaving"
        @click="saveDeptGrants"
      ><span v-if="deptSaving" class="spinner sm"></span> 保存部门授权</button>
    </template>
  </AppModal>
</template>

<style scoped>
.modal-hint { color: var(--text-tertiary); text-align: center; padding: 20px 0; }
.spinner {
  width: 18px;
  height: 18px;
  border: 2px solid var(--border);
  border-top-color: var(--brand);
  border-radius: 50%;
  animation: member-spin 0.7s linear infinite;
}
.spinner.sm {
  width: 13px;
  height: 13px;
  border-width: 2px;
}
@keyframes member-spin { to { transform: rotate(360deg); } }

/* Tab 导航 */
.tab-bar {
  display: flex;
  gap: 4px;
  margin-bottom: 16px;
  border-bottom: 1px solid var(--border);
  padding-bottom: 8px;
}
.tab-btn {
  padding: 6px 14px;
  font-size: 13px;
  font-weight: 500;
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  transition: all var(--dur-fast) var(--ease-out);
}
.tab-btn:hover { background: var(--bg-hover); color: var(--text-primary); }
.tab-btn.active { background: var(--brand-soft, rgba(59,130,246,.1)); color: var(--brand); font-weight: 600; }

.action-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: var(--radius-sm);
  color: var(--text-tertiary);
  transition: all var(--dur-fast) var(--ease-out);
}
.action-btn:hover { background: var(--bg-hover); color: var(--text-primary); }

.member-list { display: flex; flex-direction: column; gap: 8px; }
.member-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  background: var(--bg-soft);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
}
.member-info { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.member-name { font-size: 13.5px; font-weight: 600; color: var(--text-primary); }
.member-uname { font-size: 12px; color: var(--text-tertiary); }
.member-empty { padding: 18px; text-align: center; color: var(--text-tertiary); font-size: 13px; background: var(--bg-soft); border: 1px dashed var(--border); border-radius: var(--radius-md); }

/* 添加区域 */
.member-add {
  padding: 14px 16px;
  background: var(--bg-surface);
  border: 1px dashed var(--border);
  border-radius: var(--radius-md);
  margin-bottom: 12px;
}
.member-footnote {
  margin: 8px 0;
  font-size: 12px;
  color: var(--text-tertiary);
  line-height: 1.5;
}

/* 有效权限预览 */
.source-tag {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 10px;
  white-space: nowrap;
}
.tag-direct { background: rgba(59,130,246,.1); color: var(--brand); }
.tag-dept { background: rgba(16,185,129,.1); color: #059669; }
.level-badge {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  min-width: 52px;
  text-align: right;
}
</style>
