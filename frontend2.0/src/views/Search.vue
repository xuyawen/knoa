<script setup lang="ts">
// 智能搜索（对应截图 #4）：搜索框 + 高级筛选 + 结果卡片。
// 界面壳阶段：静态示例数据，未接后端检索。
import { ref } from 'vue'
import Icon from '@/components/ui/Icon.vue'

const q = ref('数据安全管理制度')
const advOpen = ref(true)

const results = [
  {
    title: '2026 数据安全管理制度',
    snippet: '本制度适用于公司全体员工的<mark>数据安全</mark>管理活动，明确<mark>数据</mark>分类分级、访问控制与审计要求……',
    source: ['安全管理制度', '数据安全'],
    type: 'PDF',
    time: '2026-07-20',
    scope: '部门可见',
    score: 0.94,
  },
  {
    title: '个人信息保护实施细则',
    snippet: '在处理个人信息时应当遵循最小必要原则，对敏感<mark>数据</mark>进行加密存储与传输，定期开展合规审查……',
    source: ['规章制度', '合规'],
    type: 'Word',
    time: '2026-07-18',
    scope: '公开可见',
    score: 0.87,
  },
  {
    title: '数据分级分类指南',
    snippet: '将<mark>数据</mark>划分为公开、内部、机密三级，不同级别对应不同的<mark>数据安全</mark>防护策略与共享范围……',
    source: ['培训资料', '数据安全'],
    type: 'Markdown',
    time: '2026-07-15',
    scope: '公司可见',
    score: 0.81,
  },
]
</script>

<template>
  <div class="page search fade-up">
    <header class="page-head">
      <div class="flex items-center">
        <h1 class="page-title">智能搜索</h1>
        <span class="todo-flag"><Icon name="sparkles" :size="12" />界面壳 · 示例数据</span>
      </div>
      <p class="page-sub">跨知识库语义检索，支持类型、时间、分类与权限多维过滤</p>
    </header>

    <!-- 搜索框 -->
    <div class="search-box card">
      <div class="search-input">
        <Icon name="search" :size="18" class="si" />
        <input v-model="q" class="input bare" placeholder="搜索文档、知识或问题…" />
        <button class="btn btn-primary btn-sm">搜索</button>
      </div>

      <button class="adv-toggle" @click="advOpen = !advOpen">
        <Icon name="filter" :size="15" />高级搜索
        <Icon name="chevron" :size="13" :style="`transform: rotate(${advOpen ? 90 : 0}deg); transition: transform .2s`" />
      </button>

      <div v-if="advOpen" class="adv">
        <div class="adv-item">
          <span class="adv-label">文件类型</span>
          <div class="chips">
            <span class="chip">PDF</span><span class="chip">Word</span><span class="chip">PPT</span><span class="chip">Excel</span><span class="chip on">全部</span>
          </div>
        </div>
        <div class="adv-item">
          <span class="adv-label">更新时间</span>
          <div class="chips">
            <span class="chip">一天内</span><span class="chip">一周内</span><span class="chip on">不限</span>
          </div>
        </div>
        <div class="adv-item">
          <span class="adv-label">文档分类</span>
          <div class="chips">
            <span class="chip">规章制度</span><span class="chip">产品手册</span><span class="chip">培训资料</span><span class="chip on">全部</span>
          </div>
        </div>
        <div class="adv-item">
          <span class="adv-label">权限范围</span>
          <div class="chips">
            <span class="chip">仅本人</span><span class="chip">部门</span><span class="chip">公司</span><span class="chip on">全部</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 结果统计 -->
    <div class="result-bar">
      找到约 <b>{{ results.length }}</b> 条结果（用时 0.23 秒）
      <div class="sort">
        <span class="text-tertiary text-sm">排序：</span>
        <span class="sort-on">相关度</span>
        <span class="text-tertiary">·</span>
        <span>时间</span>
      </div>
    </div>

    <!-- 结果列表 -->
    <div class="results">
      <article v-for="(r, i) in results" :key="i" class="card result">
        <div class="result-top">
          <Icon name="doc" :size="16" class="result-ic" />
          <h3 class="result-title">{{ r.title }}</h3>
          <span class="badge badge-muted">{{ r.type }}</span>
        </div>
        <p class="result-snippet" v-html="r.snippet" />
        <div class="result-foot">
          <span class="source">来源：{{ r.source.join(' › ') }}</span>
          <span class="flex-1" />
          <span class="text-tertiary text-xs">{{ r.time }}</span>
          <span class="badge badge-brand">{{ r.scope }}</span>
          <span class="score">匹配度 {{ Math.round(r.score * 100) }}%</span>
        </div>
      </article>
    </div>
  </div>
</template>

<style scoped>
.search-box { padding: 16px 18px; }
.search-input { display: flex; align-items: center; gap: 10px; }
.search-input .si { color: var(--text-tertiary); flex-shrink: 0; }
.input.bare { border: none; padding-left: 0; height: 38px; font-size: 15px; background: transparent; }
.input.bare:focus { box-shadow: none; }
.adv-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-top: 12px;
  font-size: 13px;
  color: var(--text-secondary);
}
.adv-toggle:hover { color: var(--brand); }
.adv {
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.adv-item { display: flex; align-items: center; gap: 14px; }
.adv-label { width: 64px; flex-shrink: 0; font-size: 13px; color: var(--text-secondary); }
.chips { display: flex; flex-wrap: wrap; gap: 8px; }
.chip {
  padding: 4px 13px;
  border-radius: var(--radius-pill);
  font-size: 12px;
  background: var(--bg-subtle);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all var(--dur-fast);
}
.chip:hover { color: var(--text-primary); }
.chip.on { background: var(--brand-soft); color: var(--brand); font-weight: 600; }

.result-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 20px 0 14px;
  font-size: 13px;
  color: var(--text-secondary);
}
.result-bar b { color: var(--text-primary); }
.sort { display: flex; align-items: center; gap: 6px; font-size: 13px; }
.sort-on { color: var(--brand); font-weight: 600; }

.results { display: flex; flex-direction: column; gap: 12px; }
.result { padding: 16px 18px; transition: box-shadow var(--dur-fast), transform var(--dur-fast); }
.result:hover { box-shadow: var(--shadow-float); transform: translateY(-1px); }
.result-top { display: flex; align-items: center; gap: 9px; margin-bottom: 8px; }
.result-ic { color: var(--brand); flex-shrink: 0; }
.result-title { margin: 0; font-size: 15px; font-weight: 600; }
.result-snippet { margin: 0 0 12px; font-size: 13px; color: var(--text-secondary); line-height: 1.7; }
.result-snippet :deep(mark) {
  background: var(--warning-soft);
  color: var(--text-primary);
  padding: 0 2px;
  border-radius: 3px;
  font-weight: 600;
}
.result-foot { display: flex; align-items: center; gap: 10px; font-size: 12px; }
.source { color: var(--text-tertiary); }
.score { color: var(--brand); font-weight: 600; }
</style>
