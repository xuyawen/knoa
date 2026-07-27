// 语音播报（TTS）逻辑，从 Chat.vue 拆出：
// 同一条消息 toggle 停止、切换消息先停旧再播新、组件卸载时统一清理。
import { ref, onBeforeUnmount } from 'vue'
import { ttsSpeak } from '@/api'
import { useToastStore } from '@/stores/toast'
import { useModelConfig } from '@/composables/useModelConfig'

export function useTts() {
  const toast = useToastStore()
  // 音色跟随个人设置（系统设置页保存，单例共享）
  const { state } = useModelConfig()
  const playingId = ref<string | null>(null)
  let audioEl: HTMLAudioElement | null = null

  async function speak(id: string, content: string) {
    if (!content) return
    // 若当前正在播放同一条 → 停止播报（toggle off）
    if (playingId.value === id) {
      stopSpeak()
      return
    }
    // 正在播放其他消息 → 先停旧再播新
    if (playingId.value && audioEl) {
      stopSpeak()
    }
    playingId.value = id
    try {
      const voice = Number(state.prefs.ttsVoiceType) || undefined
      const { audio, contentType } = await ttsSpeak(content, voice)
      audioEl = new Audio(`data:${contentType};base64,${audio}`)
      audioEl.onended = () => { playingId.value = null; audioEl = null }
      await audioEl.play()
    } catch (e) {
      playingId.value = null
      audioEl = null
      toast.error(e instanceof Error ? e.message : '语音播报失败')
    }
  }

  function stopSpeak() {
    if (audioEl) { audioEl.pause(); audioEl = null }
    playingId.value = null
  }

  // 组件卸载时停止播放，避免对已销毁实例继续回调
  onBeforeUnmount(stopSpeak)

  return { playingId, speak, stopSpeak }
}
