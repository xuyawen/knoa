// 个人配置统一从服务端读取/保存（/api/settings 的 modelPrefs + preferredModel + ttsEnabled）。
// 取代原先的 localStorage 持久化：单一真值在服务端，清缓存/换设备不再丢失。
// 「模型配置」页(/chat/model)是全部个人偏好的唯一菜单入口（原「系统设置」页已并入，路由重定向）。
import { reactive } from 'vue'
import { getSettings, updateSettings } from '@/api'
import type { Settings } from '@/types/api'

// 前端默认值仅作「加载前/失败」占位；最终以服务端 /api/settings 返回为准。
// name(模型选择)走 preferredModel 列，不在此处。
export const DEFAULT_MODEL_PREFS: Record<string, unknown> = {
  temp: 0.3,
  topP: 0.9,
  maxTokens: 2000,
  topK: 5,
  webSearch: true,
  sourceCount: 5,
  webProvider: 'auto',
  systemPrompt: '',
  showThinking: true,
  conciseMode: false,
  ttsVoiceType: 1004, // 腾讯 TTS 音色：1002 成熟男声 | 1004 温润女声 | 1050 新闻女声
  enterToSend: true, // 对话页 Enter 发送（关闭后 Ctrl+Enter 发送）
}

// 问答模型选项（模型配置页与个人设置弹框共用）
export const MODEL_OPTIONS = [
  { value: '', label: '系统默认' },
  { value: 'agnes-2.0-flash', label: 'agnes-2.0-flash（快）' },
  { value: 'agnes-2.0-pro', label: 'agnes-2.0-pro（强）' },
  { value: 'gpt-4o', label: 'GPT-4o（OpenAI）' },
  { value: 'deepseek-chat', label: 'DeepSeek Chat' },
]

// 腾讯 TTS 音色选项（与后端 config 注释一致）
export const VOICE_OPTIONS = [
  { value: 1004, label: '温润女声（默认）' },
  { value: 1002, label: '成熟男声' },
  { value: 1050, label: '新闻女声' },
]

// 模块级单例：ModelConfig 与 Chat 共享同一份服务端配置，一处保存全局可见。
const state = reactive({
  preferredModel: '' as string,
  ttsEnabled: false,
  prefs: { ...DEFAULT_MODEL_PREFS } as Record<string, any>,
  loaded: false,
})

async function load(): Promise<void> {
  if (state.loaded) return
  try {
    const s: Settings = await getSettings()
    state.preferredModel = s.preferredModel ?? ''
    state.ttsEnabled = s.ttsEnabled
    if (s.modelPrefs) Object.assign(state.prefs, s.modelPrefs)
    state.loaded = true
  } catch {
    // 加载失败不阻塞 UI，回落默认值（不打印，避免生产环境控制台噪音）
  }
}

async function save(
  preferredModel: string | null,
  modelPrefs: Record<string, any>,
  ttsEnabled?: boolean,
): Promise<void> {
  const saved = await updateSettings({
    preferredModel,
    modelPrefs,
    ...(ttsEnabled !== undefined ? { ttsEnabled } : {}),
  })
  state.preferredModel = saved.preferredModel ?? ''
  state.ttsEnabled = saved.ttsEnabled
  if (saved.modelPrefs) Object.assign(state.prefs, saved.modelPrefs)
}

export function useModelConfig() {
  return { state, load, save, DEFAULT_MODEL_PREFS }
}
