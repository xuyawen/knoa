// 模型配置统一从服务端读取/保存（/api/settings 的 modelPrefs + preferredModel）。
// 取代原先的 localStorage 持久化：单一真值在服务端，清缓存/换设备不再丢失，
// 且模型选择(name)与「系统设置」页的偏好模型共享 preferred_model 列，消除双写冲突。
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
}

// 模块级单例：ModelConfig 与 Chat 共享同一份服务端配置，一处保存全局可见。
const state = reactive({
  preferredModel: '' as string,
  prefs: { ...DEFAULT_MODEL_PREFS } as Record<string, any>,
  loaded: false,
})

async function load(): Promise<void> {
  if (state.loaded) return
  try {
    const s: Settings = await getSettings()
    if (s.preferredModel != null) state.preferredModel = s.preferredModel
    if (s.modelPrefs) Object.assign(state.prefs, s.modelPrefs)
    state.loaded = true
  } catch (e) {
    // 加载失败不阻塞 UI，回落默认值
    console.warn('[useModelConfig] load failed, using defaults', e)
  }
}

async function save(preferredModel: string | null, modelPrefs: Record<string, any>): Promise<void> {
  const saved = await updateSettings({ preferredModel, modelPrefs })
  if (saved.preferredModel != null) state.preferredModel = saved.preferredModel
  if (saved.modelPrefs) Object.assign(state.prefs, saved.modelPrefs)
}

export function useModelConfig() {
  return { state, load, save, DEFAULT_MODEL_PREFS }
}
