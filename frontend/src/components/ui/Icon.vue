<script setup lang="ts">
// 图标层：kebab name -> lucide-vue-next 组件。lucide 默认 stroke=currentColor、
// stroke-width=2、round linecap/join、24x24，与旧内联 SVG 视觉一致。
// 显式 import 保 tree-shake，不 import * 全量。
import { computed } from 'vue'
import type { Component } from 'vue'
import {
  LayoutDashboard, FileText, Search, MessageSquare, Share2, Shield,
  User, UserCircle, Settings, Bell, LogOut, Lock, Key, ShieldCheck, Loader2,
  ChevronRight, ChevronDown,
  Sun, Moon, Monitor, Plus, Minus, X, Check, AlertTriangle, Pencil, Trash2,
  MoreHorizontal, Menu, Folder, Upload, Download, Archive, File, FileSpreadsheet,
  Presentation, FileType, Filter, RefreshCw, Eye, LayoutGrid, BarChart3, Users,
  Flame, Clock, History, List, Globe, UsersRound, CircleDot, Link2, PanelLeftClose,
  Maximize2, Paperclip, Send, Copy, ArrowDownToLine, AppWindow, Star, Tag, Calendar, Sparkles,
  Info, Heart,
  ArrowUpRight, ArrowDownRight, Pin, UserPlus, Volume2,
  BrainCircuit, BookMarked, ThumbsUp, ThumbsDown, PenLine, ArrowUp, Square,
} from 'lucide-vue-next'

const props = defineProps<{ name: string; size?: number | string }>()

const ICONS: Record<string, Component> = {
  dashboard: LayoutDashboard, doc: FileText, search: Search, chat: MessageSquare,
  graph: Share2, shield: Shield, user: User, 'user-circle': UserCircle,
  settings: Settings, bell: Bell,
  logout: LogOut, lock: Lock, key: Key, 'shield-check': ShieldCheck, loader: Loader2, chevron: ChevronRight, 'chevron-down': ChevronDown,
  sun: Sun, moon: Moon, monitor: Monitor, plus: Plus, minus: Minus, close: X,
  check: Check, alert: AlertTriangle, edit: Pencil, trash: Trash2, more: MoreHorizontal,
  menu: Menu, folder: Folder, upload: Upload, download: Download, archive: Archive,
  file: File, excel: FileSpreadsheet, pptx: Presentation, pdf: FileType, filter: Filter,
  refresh: RefreshCw, eye: Eye, grid: LayoutGrid, chart: BarChart3, users: Users,
  fire: Flame, clock: Clock, history: History, list: List, globe: Globe, team: UsersRound,
  node: CircleDot, link: Link2, collapse: PanelLeftClose, expand: Maximize2, attach: Paperclip,
  send: Send, copy: Copy, export: ArrowDownToLine, view: AppWindow, gridview: LayoutGrid,
  listview: List, star: Star, tag: Tag, calendar: Calendar, sparkles: Sparkles,
  info: Info, heart: Heart, warning: AlertTriangle,
  'arrow-up-right': ArrowUpRight, 'arrow-down-right': ArrowDownRight,
  pin: Pin, 'user-plus': UserPlus,
  volume: Volume2,
  'pen-line': PenLine, 'brain-circuit': BrainCircuit, 'book-marked': BookMarked,
  'thumbs-up': ThumbsUp, 'thumbs-down': ThumbsDown, 'arrow-up': ArrowUp, square: Square,
}

const comp = computed(() => ICONS[props.name] ?? AlertTriangle)
const dim = computed(() => (typeof props.size === 'number' ? `${props.size}px` : props.size) || '18px')
</script>

<template>
  <component :is="comp" :size="dim" />
</template>
