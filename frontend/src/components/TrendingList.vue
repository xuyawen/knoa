<script setup lang="ts">
import { computed } from 'vue'
import { useKnowledgeStore } from '@/stores/knowledge'
import Icon from './Icon.vue'

const knowledge = useKnowledgeStore()
const emit = defineEmits<{ (e: 'ask', q: string): void }>()

const trending = computed(() => knowledge.trending)