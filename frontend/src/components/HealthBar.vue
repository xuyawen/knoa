<script setup lang="ts">
import { computed } from 'vue'
import type { HealthItem } from '@/types/api'
import Icon from './Icon.vue'

const props = defineProps<{ item: HealthItem }>()

const iconName = computed(() => {
  switch (props.item.kb) {
    case '合规库': return 'compliance'
    case '广告投放': return 'ads'
    case '物流仓储': return 'logistics'
    case '选品策略': return 'selection'
    case '客服话术': return 'service'
    default: return 'fire'
  }
})

const pct = computed(() => Math.round(props.item.healthScore * 100))

const band = computed<'good' | 'mid' | 'low'>(() => {
  const c = props.item.healthScore
  if (c >= 0.8) return 'good'
  if (c >= 0.6) return 'mid'
  return 'low'
})

const metrics = computed(() => {
  const it = props.item
  const fmt = (n: number) => `${Math.round(n * 100)}%`
  return [
    { label: '审核率', value: fmt(it.reviewRate) },
    { label: '可检索', value: fmt(it.retrievableRate) },
    {
      label: '新鲜度',
      value: it.freshnessHours == null
        ? '无文档'
        : it.freshnessHours < 24
          ? '今天'
          : it.freshnessHours < 24 * 7
            ? '本周'
            : it.freshnessHours < 24 * 30
              ? '本月'
              : '较旧',
    },
  ]
})

function relTime(iso: string): string {
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return ''
  const h = Math.max(0, (Date.now() - then) / 3.6e6)
  if (h < 1) return '刚刚更新'
  if (h < 24) return `${Math.floor(h)} 小时前更新`
  const d = Math.floor(h / 24)
  if (d === 1) return '昨天更新'
  if (d < 7) return `${d} 天前更新`
  return new Date(iso).toLocaleDateString('zh-CN') + ' 更新'
}
</script>

<template>
  <div class="card" :class="band">
    <div class="head">
      <div class="icon">
        <Icon :name="iconName" :size="15" />
      </div>
      <div class="meta">
        <div class="name">{{ item.kb }}</div>
        <div class="sub">{{ item.docCount }} 篇 · {{ relTime(item.updatedAt) }}</div>
      </div>
      <div class="score" :class="band">{{ pct }}<span class="pct">%</span></div>
    </div>

    <div class="bar">
      <div class="fill" :class="band" :style="{ width: pct + '%' }" />
    </div>

    <div class="metrics">
      <span v-for="m in metrics" :key="m.label" class="metric">
        <i>{{ m.label }}</i>{{ m.value }}
      </span>
    </div>
  </div>
</template>

<style scoped>
.card {
  background: var(--bg-subtle);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  transition: transform 0.25s cubic-bezier(0.16, 1, 0.3, 1),
    box-shadow 0.25s ease, border-color 0.25s ease;
}
.card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-float);
  border-color: var(--brand);
}

.head {
  display: flex;
  align-items: center;
  gap: 10px;
}
.icon {
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  border-radius: 8px;
  background: var(--bg-surface);
  color: var(--brand);
  display: flex;
  align-items: center;
  justify-content: center;
}
.meta {
  flex: 1;
  min-width: 0;
}
.name {
  font-size: 13px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.sub {
  font-size: 11px;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.score {
  flex-shrink: 0;
  font-size: 16px;
  font-weight: 700;
  font-family: var(--font-display);
  font-variant-numeric: tabular-nums;
}

.bar {
  height: 6px;
  border-radius: var(--radius-pill);
  background: var(--bg-surface);
  overflow: hidden;
}
.fill {
  height: 100%;
  border-radius: var(--radius-pill);
  transition: width 0.6s cubic-bezier(0.16, 1, 0.3, 1);
}
.fill.good { background: var(--success); }
.fill.mid { background: var(--warning); }
.fill.low { background: var(--danger); }

.caption {
  font-size: 11px;
  font-weight: 500;
}
.caption.good { color: var(--success); }
.caption.mid { color: var(--warning); }
.caption.low { color: var(--danger); }

.score.good { color: var(--success); }
.score.mid { color: var(--warning); }
.score.low { color: var(--danger); }
.score .pct {
  font-size: 11px;
  font-weight: 600;
  margin-left: 1px;
}

.metrics {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}
.metric {
  font-size: 11px;
  color: var(--text-secondary);
  font-weight: 500;
}
.metric i {
  font-style: normal;
  color: var(--text-placeholder);
  margin-right: 4px;
  font-weight: 400;
}
</style>
