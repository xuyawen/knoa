import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getKnowledgeBases, getTrending } from '@/api'
import type { KnowledgeBase, HealthItem, TrendingItem } from '@/types/api'

export const useKnowledgeStore = defineStore('knowledge', () => {
  const bases = ref<KnowledgeBase[]>([])
  const health = ref<HealthItem[]>([])
  const trending = ref<TrendingItem[]>([])
  const activeBase = ref<string | null>(null) // null = 全部知识
  const loaded = ref(false)

  async function load() {
    if (loaded.value) return
    try {
      const [kbResp, trendResp] = await Promise.all([
        getKnowledgeBases(),
        getTrending(),
      ])
      bases.value = kbResp.knowledgeBases
      health.value = kbResp.health
      trending.value = trendResp
      loaded.value = true
    } catch (e) {
      console.error('Failed to load knowledge data:', e)
    }
  }

  function selectBase(id: string | null) {
    activeBase.value = id
  }

  return { bases, health, trending, activeBase, loaded, load, selectBase }
})
