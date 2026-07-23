import { ref, onMounted } from 'vue'
import { getTrending } from '@/api'
import type { TrendingItem } from '@/types/api'

// 热门搜索榜。
export function useTrending() {
  const trending = ref<TrendingItem[]>([])

  async function load() {
    try {
      trending.value = await getTrending()
    } catch {
      trending.value = []
    }
  }

  onMounted(load)
  return { trending, load }
}
