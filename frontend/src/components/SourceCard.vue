<script setup lang="ts">
import type { SourceItem } from '@/types/api'
import Icon from './Icon.vue'

const props = defineProps<{ source: SourceItem }>()
const emit = defineEmits<{
  (e: 'locate', id: number): void
  (e: 'open', chunkId: string): void
}>()

function isWeb(): boolean {
  return props.source.sourceType === 'web'
}

// 知识库来源：点击定位（右栏高亮）；联网来源：直接打开原文外链
function onCardClick() {
  if (isWeb() && props.source.url) {
    window.open(props.source.url, '_blank')
  } else {
    emit('locate', props.source.id)
  }
}

function onFootClick() {
  if (isWeb() && props.source.url) {
    window.open(props.source.url, '_blank')
  } else {
    emit('open', props.source.chunkId)
  }
}
</script>

<template>
  <button class="card" :class="{ web: isWeb() }" @click="onCardClick">
    <div class="head">
      <span class="tag" :class="isWeb() ? 'web' : 'kb'">
        <Icon :name="isWeb() ? 'external' : 'library'" :size="12" />
        {{ isWeb() ? '联网' : source.kb }}
      </span>
      <span v-if="!isWeb()" class="conf" :class="{ low: source.confidence < 0.9 }">
        {{ Math.round(source.confidence * 100) }}%
      </span>
    </div>
    <div class="title">{{ source.title }}</div>
    <div class="snippet">{{ source.snippet }}</div>
    <div class="foot" @click.stop="onFootClick">
      <span class="loc">{{ isWeb() ? '查看原文' : '查看溯源' }}</span>
      <Icon name="external" :size="13" />
    </div>
  </button>
</template>

<style scoped>
.card {
  display: block;
  width: 100%;
  text-align: left;
  background: var(--bg-subtle);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 12px 14px;
  margin-bottom: 10px;
  transition: border-color 0.15s ease, transform 0.12s ease;
}
.card:hover {
  border-color: var(--brand);
  transform: translateY(-1px);
}
.head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}
.tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  font-weight: 500;
}
.tag.kb {
  color: var(--brand);
}
.tag.web {
  color: var(--warning, #f59e0b);
  background: color-mix(in srgb, var(--warning, #f59e0b) 12%, transparent);
  padding: 1px 7px;
  border-radius: var(--radius-pill);
}
.card.web {
  border-color: color-mix(in srgb, var(--warning, #f59e0b) 35%, var(--border));
}
.card.web:hover {
  border-color: var(--warning, #f59e0b);
}
.conf {
  font-size: 12px;
  color: var(--success);
  font-weight: 600;
}
.conf.low {
  color: var(--danger);
}
.title {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 4px;
  line-height: 1.4;
}
.snippet {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.foot {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 8px;
  font-size: 12px;
  color: var(--brand);
}
</style>
