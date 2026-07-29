<script setup lang="ts">
// 成员管理页：按知识库管理「个人成员 / 部门授权 / 有效权限预览」。
// 顶部选择知识库，下方内嵌 KbMembersPanel（随所选库切换自动重载）。
// 支持 ?kb= query 预选（从知识库列表页「成员」按钮跳转带入），默认选第一个有权限的库。
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import CustomSelect from '@/components/ui/CustomSelect.vue'
import KbMembersPanel from '@/components/knowledge/KbMembersPanel.vue'
import { useKnowledgeStore } from '@/stores/knowledge'

const route = useRoute()
const store = useKnowledgeStore()

const selectedKb = ref('')

const kbOptions = computed(() =>
  store.bases.map((b) => ({ label: b.name, value: b.id })),
)

const selectedBase = computed(() => store.bases.find((b) => b.id === selectedKb.value) || null)

onMounted(async () => {
  await store.load()
  // 优先采用 query 预选；否则默认第一个有权限的库
  const q = route.query.kb
  const pre = typeof q === 'string' && store.bases.some((b) => b.id === q) ? q : ''
  selectedKb.value = pre || (store.bases[0]?.id ?? '')
})
</script>

<template>
  <div class="page kb-members fade-up">
    <section class="card km-select-card">
      <label class="km-label">知识库</label>
      <CustomSelect v-model="selectedKb" :options="kbOptions" width="320px" placeholder="选择知识库" />
    </section>

    <section v-if="selectedBase" class="card km-panel-card">
      <KbMembersPanel :kb-id="selectedBase.id" :kb-name="selectedBase.name" />
    </section>
    <section v-else class="card km-empty">
      <span>暂无可管理的知识库</span>
    </section>
  </div>
</template>

<style scoped>
.km-select-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px 20px;
  margin-bottom: 16px;
}
.km-label { font-size: 13px; color: var(--text-secondary); flex-shrink: 0; }
.km-panel-card { padding: 20px; }
.km-empty {
  display: flex; align-items: center; justify-content: center;
  min-height: 200px; color: var(--text-tertiary); font-size: 13px;
}
</style>
