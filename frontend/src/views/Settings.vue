<script setup lang="ts">
// 系统设置 — P8：偏好问答模型（透传进 ask 管线）+ 语音播报开关。
import { onMounted, ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import { getSettings, updateSettings } from '@/api'
import Icon from '@/components/ui/Icon.vue'
import CustomSelect from '@/components/ui/CustomSelect.vue'

const auth = useAuthStore()
const toast = useToastStore()

// 可选模型：与 Chat.vue 模型配置保持一致（agnes 系列）。
const MODEL_OPTIONS = [
  { value: '', label: '系统默认' },
  { value: 'agnes-2.0-flash', label: 'agnes-2.0-flash（快）' },
  { value: 'agnes-2.0-pro', label: 'agnes-2.0-pro（强）' },
]

const preferredModel = ref<string>('')
const ttsEnabled = ref(false)
const loading = ref(false)
const saving = ref(false)

onMounted(async () => {
  loading.value = true
  try {
    const s = await getSettings()
    preferredModel.value = s.preferredModel || ''
    ttsEnabled.value = s.ttsEnabled
  } catch {
    toast.error('加载设置失败，请刷新重试')
  } finally {
    loading.value = false
  }
})

async function onSave() {
  saving.value = true
  try {
    const saved = await updateSettings({
      preferredModel: preferredModel.value || null,
      ttsEnabled: ttsEnabled.value,
    })
    // 同步回 auth store（Chat 朗读按钮依赖 ttsEnabled，ask 管线依赖 preferredModel）
    await auth.fetchMe()
    toast.success('设置已保存')
    void saved
  } catch (e) {
    toast.error(e instanceof Error ? e.message : '保存失败，请重试')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="settings-page fade-up">
    <div class="settings-head">
      <h2 class="settings-title">系统设置</h2>
      <p class="settings-sub">配置你的问答偏好与语音播报。修改即时生效。</p>
    </div>

    <section class="card settings-card">
      <div v-if="loading" class="settings-loading">
        <Icon name="loader" :size="16" class="spin" /> 加载中…
      </div>

      <template v-else>
        <!-- 偏好模型 -->
        <div class="set-row">
          <div class="set-meta">
            <div class="set-label">偏好问答模型</div>
            <div class="set-hint">指定后，所有问答默认使用该模型；留空则使用系统默认。</div>
          </div>
          <div class="set-control">
            <CustomSelect v-model="preferredModel" :options="MODEL_OPTIONS" :disabled="saving" />
          </div>
        </div>

        <div class="set-divider" />

        <!-- 语音播报 -->
        <div class="set-row">
          <div class="set-meta">
            <div class="set-label">语音播报</div>
            <div class="set-hint">开启后，AI 回答下方出现朗读按钮，可一键播报回答内容。</div>
          </div>
          <div class="set-control">
            <button
              type="button"
              class="switch"
              :class="{ on: ttsEnabled }"
              role="switch"
              :aria-checked="ttsEnabled"
              @click="ttsEnabled = !ttsEnabled"
            >
              <span class="switch-knob" />
            </button>
          </div>
        </div>

        <div class="set-actions">
          <button class="btn btn-primary" :disabled="saving" @click="onSave">
            <Icon v-if="saving" name="loader" :size="14" class="spin" />
            {{ saving ? '保存中…' : '保存设置' }}
          </button>
        </div>
      </template>
    </section>
  </div>
</template>

<style scoped>
.settings-page { max-width: 720px; }
.settings-head { margin-bottom: 18px; }
.settings-title { margin: 0 0 4px; font-size: 20px; font-weight: 700; color: var(--text-primary); }
.settings-sub { margin: 0; font-size: 13px; color: var(--text-tertiary); }

.settings-card { padding: 8px 24px; }
.settings-loading { display: flex; align-items: center; gap: 8px; padding: 28px; color: var(--text-tertiary); font-size: 13px; }

.set-row { display: flex; align-items: center; justify-content: space-between; gap: 24px; padding: 20px 0; }
.set-meta { min-width: 0; }
.set-label { font-size: 14px; font-weight: 600; color: var(--text-primary); }
.set-hint { margin-top: 4px; font-size: 12.5px; color: var(--text-tertiary); line-height: 1.5; max-width: 460px; }
.set-control { flex-shrink: 0; }
.set-control .select { width: 200px; }

.set-divider { height: 1px; background: var(--border); }

.set-actions { display: flex; justify-content: flex-end; padding: 20px 0 12px; }

/* 开关 */
.switch {
  position: relative;
  width: 46px; height: 26px;
  border-radius: 13px;
  border: none;
  background: var(--border-strong);
  cursor: pointer;
  transition: background var(--dur-fast) var(--ease-out);
  flex-shrink: 0;
}
.switch.on { background: var(--brand); }
.switch-knob {
  position: absolute; top: 3px; left: 3px;
  width: 20px; height: 20px; border-radius: 50%;
  background: #fff;
  box-shadow: 0 1px 3px rgba(0,0,0,0.25);
  transition: transform var(--dur-fast) var(--ease-out);
}
.switch.on .switch-knob { transform: translateX(20px); }

.spin { animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
