<script setup lang="ts">
// KB 成员管理弹窗（库级授权 / 严格隔离下的共享入口），从 DocumentLibrary.vue 拆出。
// 打开时自加载成员与用户列表，保存成功后 emit('close')。
import { ref, computed, watch } from 'vue'
import Icon from '@/components/ui/Icon.vue'
import AppModal from '@/components/ui/AppModal.vue'
import CustomSelect from '@/components/ui/CustomSelect.vue'
import { useToastStore } from '@/stores/toast'
import { errMsg } from '@/utils/errmsg'
import { getKbMembers, setKbMembers } from '@/api'
import type { KBMember, UserOut } from '@/types/api'
import UserSearchSelect from '@/components/ui/UserSearchSelect.vue'

const props = defineProps<{
  show: boolean
  kbId: string
  kbName: string
}>()

const emit = defineEmits<{ (e: 'close'): void }>()

const toast = useToastStore()

const memberRows = ref<KBMember[]>([])
const loading = ref(false)
const saving = ref(false)
const newUserLevel = ref<'view' | 'edit' | 'admin'>('view')
// 已添加成员的用户 id，传给搜索选择器做排除，避免重复添加
const excludeIds = computed(() => memberRows.value.map((m) => m.userId))

const levelOptions = [
  { label: '可查看', value: 'view' },
  { label: '可编辑', value: 'edit' },
  { label: '管理员', value: 'admin' },
]

// 每次打开时重新拉取成员列表
watch(
  () => props.show,
  (v) => {
    if (v) void load()
  },
)

async function load() {
  loading.value = true
  newUserLevel.value = 'view'
  try {
    // 用户列表改由搜索选择器按需检索（getUserList 的 q 参数），此处只拉成员
    memberRows.value = await getKbMembers(props.kbId)
  } catch (e: unknown) {
    toast.error(`加载成员失败：${errMsg(e)}`)
    emit('close')
  } finally {
    loading.value = false
  }
}

// 搜索选择器选中用户即添加（使用当前选定的权限级别）
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
  if (!admins.length) {
    toast.error('至少保留一名管理员，否则知识库将无法管理')
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
</script>

<template>
  <AppModal :show="show" :title="`管理成员 · ${kbName}`" wide @close="emit('close')">
    <div v-if="loading" class="modal-hint">加载中…</div>
    <template v-else>
      <p class="member-tip">
        为该知识库添加成员并分配权限：<b>可查看</b>仅检索、<b>可编辑</b>可上传/删除文档、<b>管理员</b>可管理成员与库设置。至少保留一名管理员。
      </p>
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
        <div v-if="!memberRows.length" class="member-empty">暂无成员，请在下方添加。</div>
      </div>
      <div class="member-add">
        <CustomSelect v-model="newUserLevel" :options="levelOptions" width="110px" />
        <UserSearchSelect
          :exclude-ids="excludeIds"
          placeholder="搜索用户并点击添加"
          width="260px"
          @select="onUserSelect"
        />
      </div>
    </template>
    <template #foot>
      <button class="btn btn-ghost btn-sm" @click="emit('close')">取消</button>
      <button class="btn btn-primary btn-sm" :disabled="saving" @click="saveMembers">
        <span v-if="saving" class="spinner sm"></span> 保存
      </button>
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

.member-tip { margin: 0 0 14px; color: var(--text-tertiary); font-size: 12.5px; line-height: 1.6; }
.member-tip b { color: var(--text-secondary); }
.member-list { display: flex; flex-direction: column; gap: 8px; margin-bottom: 16px; }
.member-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  background: var(--bg-soft);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
}
.member-info { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.member-name { font-size: 13.5px; font-weight: 600; color: var(--text-primary); }
.member-uname { font-size: 12px; color: var(--text-tertiary); }
.member-empty { padding: 14px; text-align: center; color: var(--text-tertiary); font-size: 13px; background: var(--bg-soft); border: 1px dashed var(--border); border-radius: var(--radius-md); }
.member-add { display: flex; align-items: center; gap: 10px; padding-top: 14px; border-top: 1px solid var(--border); }
</style>
