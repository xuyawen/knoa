// 语音试听逻辑（模型配置页与个人设置弹框共用）：
// 用当前所选音色即时合成示例文案；播放中再点一次停止；卸载自动清理。
import { ref, onBeforeUnmount } from 'vue'
import { ttsSpeak } from '@/api'
import { useToastStore } from '@/stores/toast'
import { errMsg } from '@/utils/errmsg'

const PREVIEW_TEXT = '你好，这是知海知识库的语音播报效果试听。'

export function useTtsPreview() {
  const toast = useToastStore()
  const previewLoading = ref(false)
  const previewPlaying = ref(false)
  let audioEl: HTMLAudioElement | null = null

  async function previewVoice(voiceType?: number) {
    // 播放中 → 再点一次停止
    if (previewPlaying.value) {
      audioEl?.pause()
      audioEl = null
      previewPlaying.value = false
      return
    }
    if (previewLoading.value) return
    previewLoading.value = true
    try {
      const { audio, contentType } = await ttsSpeak(PREVIEW_TEXT, voiceType)
      audioEl = new Audio(`data:${contentType};base64,${audio}`)
      audioEl.onended = () => {
        previewPlaying.value = false
        audioEl = null
      }
      previewPlaying.value = true
      await audioEl.play()
    } catch (e: unknown) {
      previewPlaying.value = false
      audioEl = null
      toast.error(`试听失败：${errMsg(e)}`)
    } finally {
      previewLoading.value = false
    }
  }

  // 组件卸载（含弹框关闭）时停止试听
  onBeforeUnmount(() => {
    audioEl?.pause()
    audioEl = null
  })

  return { previewLoading, previewPlaying, previewVoice }
}
