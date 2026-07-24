<script setup lang="ts">
// 首页大盘 — 热门内容（热门搜索榜 / 问答榜 / 知识缺口榜）。
import { computed, onMounted, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useKnowledgeStore } from '@/stores/knowledge'
import Icon from '@/components/ui/Icon.vue'
import { getHotAsk, getKnowledgeGaps } from '@/api'
import '@/assets/dashboard.css'
import type { HotQueryItem } from '@/types/api'

const kb = useKnowledgeStore()
const { trending } = storeToRefs(kb)

const topTrending = computed(() => trending.value.slice(0, 8))

const hotAsk = ref<HotQueryItem[]>([])
const knowledgeGaps = ref<HotQueryItem[]>([])
async function loadHotContent() {
  const [a, g] = await Promise.all([getHotAsk(), getKnowledgeGaps()])
  hotAsk.value = a
  knowledgeGaps.value = g
}

onMounted(() => {
  if (!kb.loaded) kb.load()
  void loadHotContent()
})
</script>

<template>
  <div class="dashboard">
    <div class="chart-panel card">
      <div class="panel-head"><span class="panel-title">热门搜索榜</span><Icon name="fire" :size="14" class="phint"/></div>
      <div v-if="topTrending.length" class="trend-list">
        <div v-for="(t,i) in topTrending" :key="t.question" class="trend-item">
          <span class="trend-rank" :class="'rk-'+Math.min(i+1,3)">{{ i+1 }}</span>
          <span class="trend-q">{{ t.question }}</span>
          <span class="trend-count">{{ t.count }}</span>
        </div>
      </div>
      <div v-else class="empty-hint">暂无热门搜索数据</div>
    </div>

    <div class="charts-row docs-row">
      <div class="chart-panel card">
        <div class="panel-head"><span class="panel-title">热门问答榜</span><Icon name="message" :size="14" class="phint"/></div>
        <div v-if="hotAsk.length" class="trend-list">
          <div v-for="(t,i) in hotAsk" :key="t.query" class="trend-item">
            <span class="trend-rank" :class="'rk-'+Math.min(i+1,3)">{{ i+1 }}</span>
            <span class="trend-q">{{ t.query }}</span>
            <span class="trend-count">{{ t.count }}</span>
          </div>
        </div>
        <div v-else class="empty-hint">近 30 天暂无问答记录</div>
      </div>

      <div class="chart-panel card">
        <div class="panel-head"><span class="panel-title">知识缺口榜</span><Icon name="alert" :size="14" class="phint"/></div>
        <div v-if="knowledgeGaps.length" class="trend-list">
          <div v-for="(t,i) in knowledgeGaps" :key="t.query" class="trend-item">
            <span class="trend-rank" :class="'rk-'+Math.min(i+1,3)">{{ i+1 }}</span>
            <span class="trend-q">{{ t.query }}</span>
            <span class="trend-count">{{ t.count }}</span>
          </div>
        </div>
        <div v-else class="empty-hint">近 30 天暂无知识缺口</div>
      </div>
    </div>
  </div>
</template>
