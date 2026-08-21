<script setup lang="ts">
// 模型配置 — 独立页面（遵循「一个页面一个文件」原则）。
// 配置真值在服务端（/api/settings），前端不再用 localStorage。
// 原「系统设置」页已并入本页「个人偏好」区块：侧边栏仅保留本菜单入口。
import { ref, computed, onMounted } from 'vue'
import CustomSelect from '@/components/ui/CustomSelect.vue'
import Icon from '@/components/ui/Icon.vue'
import { useToastStore } from '@/stores/toast'
import { useAuthStore } from '@/stores/auth'
import { useModelConfig, DEFAULT_MODEL_PREFS, MODEL_OPTIONS, VOICE_OPTIONS } from '@/composables/useModelConfig'
import { useTtsPreview } from '@/composables/useTtsPreview'
import { getSystemStatus } from '@/api'
import type { SystemStatus } from '@/types/api'

const toast = useToastStore()
const auth = useAuthStore()
const { state, load, save } = useModelConfig()
const { previewLoading, previewPlaying, previewVoice } = useTtsPreview()

// 后端运行配置概览（只读）：「当前状态」面板据此渲染，不再用写死值
// （此前前端写死 text-embedding-3-small，后端早已换成 text-embedding-v4——正是要防的脱节）
const sysStatus = ref<SystemStatus | null>(null)

// ════════════════════════════════════════
// Section 0 — 个人偏好（原「系统设置」页并入：模型 / 语音 / 输入习惯）
// ════════════════════════════════════════
const modelName = ref('')
const ttsEnabled = ref(false)
const ttsVoiceType = ref(Number(DEFAULT_MODEL_PREFS.ttsVoiceType))
const enterToSend = ref(Boolean(DEFAULT_MODEL_PREFS.enterToSend))

// ════════════════════════════════════════
// Section 1 — 生成参数
// ════════════════════════════════════════
const temperature = ref(Number(DEFAULT_MODEL_PREFS.temp))
const topP = ref(Number(DEFAULT_MODEL_PREFS.topP))
const maxTokens = ref(Number(DEFAULT_MODEL_PREFS.maxTokens))

const tokenOptions = [
  { value: 1000, label: '1000（简短回答）' },
  { value: 2000, label: '2000（默认）' },
  { value: 4000, label: '4000（长文详述）' },
  { value: 8000, label: '8000（超长输出）' },
]

// ════════════════════════════════════════
// Section 2 — 检索策略
// ════════════════════════════════════════
const retrievalTopK = ref(Number(DEFAULT_MODEL_PREFS.topK))
const webSearchEnabled = ref(DEFAULT_MODEL_PREFS.webSearch as boolean)
const sourceCount = ref(Number(DEFAULT_MODEL_PREFS.sourceCount))

const topKOptions = [3, 5, 8, 10].map(v => ({ value: v, label: `${v} 条` }))
const sourceOptions = [3, 5, 8, 10].map(v => ({ value: v, label: `${v} 条` }))

// 联网搜索 provider：仅国内 BoCha（境外 Tavily/DDG 已移除，生产网络不可达）
const webProvider = ref(DEFAULT_MODEL_PREFS.webProvider as string)
const webProviderOptions = [
  { value: 'auto', label: '自动（按可用密钥）' },
  { value: 'bocha', label: 'BoCha 博查（中文检索质量最佳）' },
]
// 依据后端真实配置动态标注未配置密钥的服务，避免用户选了永不生效的选项
const webProviderOpts = computed(() =>
  webProviderOptions.map((o) => {
    if (o.value === 'auto') return o
    const ok = sysStatus.value?.webProviders.includes(o.value) ?? true
    return ok ? o : { ...o, label: `${o.label}（未配置密钥）` }
  })
)
const PROVIDER_NAMES: Record<string, string> = { bocha: 'BoCha' }
const webProviderText = computed(() =>
  (sysStatus.value?.webProviders || []).map((p) => PROVIDER_NAMES[p] || p).join(' · ')
)
const RERANKER_LABELS: Record<string, string> = {
  auto: '自动（Cross-Encoder 优先）',
  'cross-encoder': 'Cross-Encoder 精排',
  'lexical-semantic': '词法-语义规则',
  disabled: '已停用',
}
const rerankerLabel = computed(() => RERANKER_LABELS[sysStatus.value?.reranker || ''] || sysStatus.value?.reranker || '—')
// TTS 服务未配置（后端无密钥）：语音播报开了也不会生效，给出警示提示
const ttsUnavailable = computed(() => sysStatus.value !== null && !sysStatus.value.ttsAvailable)

// ════════════════════════════════════════
// Section 3 — 回答风格
// ════════════════════════════════════════
const systemPrompt = ref(DEFAULT_MODEL_PREFS.systemPrompt as string)
const showThinking = ref(DEFAULT_MODEL_PREFS.showThinking as boolean)
const conciseMode = ref(DEFAULT_MODEL_PREFS.conciseMode as boolean) // default verbose

const promptPlaceholder = `可选：自定义 AI 人设或回答风格指令。
示例：
- 你是一位专业的技术文档助手，回答要严谨、引用来源。
- 用通俗易懂的语言解释，避免过多术语。
- 每个回答最后给出一个可操作的建议。

留空则使用系统默认 Prompt。`
const charCount = computed(() => systemPrompt.value.length)

// 滑块填充轨道：品牌色渐变到当前值位置（inline style 覆盖 CSS 灰底）
function sliderFill(val: number, min = 0, max = 1) {
  const p = ((val - min) / (max - min)) * 100
  return { background: `linear-gradient(90deg, var(--brand) ${p}%, var(--border) ${p}%)` }
}

// 保存成功时间（底部操作栏回显，给用户明确落定感）
const savedAt = ref('')

// 从服务端加载已保存配置，填充表单（单一真值在服务端）
onMounted(async () => {
  await load()
  modelName.value = state.preferredModel
  ttsEnabled.value = state.ttsEnabled
  ttsVoiceType.value = Number(state.prefs.ttsVoiceType) || 1002
  enterToSend.value = state.prefs.enterToSend !== false
  temperature.value = Number(state.prefs.temp)
  topP.value = Number(state.prefs.topP)
  maxTokens.value = Number(state.prefs.maxTokens)
  retrievalTopK.value = Number(state.prefs.topK)
  webSearchEnabled.value = Boolean(state.prefs.webSearch)
  sourceCount.value = Number(state.prefs.sourceCount)
  webProvider.value = String(state.prefs.webProvider)
  systemPrompt.value = String(state.prefs.systemPrompt ?? '')
  showThinking.value = Boolean(state.prefs.showThinking)
  conciseMode.value = Boolean(state.prefs.conciseMode)
  // 系统状态独立于表单，失败静默（面板回落为加载态/隐藏，不阻塞配置编辑）
  getSystemStatus().then((s) => { sysStatus.value = s }).catch(() => {})
})

// ════════════════════════════════════════
// 保存
// ════════════════════════════════════════
function saveAll() {
  const modelPrefs = {
    temp: temperature.value,
    topP: topP.value,
    maxTokens: maxTokens.value,
    topK: retrievalTopK.value,
    webSearch: webSearchEnabled.value,
    sourceCount: sourceCount.value,
    webProvider: webProvider.value,
    systemPrompt: systemPrompt.value,
    showThinking: showThinking.value,
    conciseMode: conciseMode.value,
    ttsVoiceType: Number(ttsVoiceType.value) || 1002,
    enterToSend: enterToSend.value,
  }
  save(modelName.value || null, modelPrefs, ttsEnabled.value)
    .then(() => {
      // 同步用户快照，Chat 的朗读按钮随 ttsEnabled 即时生效
      void auth.fetchMe()
      savedAt.value = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
      toast.success('配置已保存')
    })
    .catch((e: unknown) => toast.error(e instanceof Error ? e.message : '保存失败，请重试'))
}

function resetDefaults() {
  modelName.value = ''
  ttsEnabled.value = false
  ttsVoiceType.value = 1002
  enterToSend.value = true
  temperature.value = 0.3
  topP.value = 0.9
  maxTokens.value = 2000
  retrievalTopK.value = 5
  webSearchEnabled.value = true
  sourceCount.value = 5
  webProvider.value = 'auto'
  systemPrompt.value = ''
  showThinking.value = true
  conciseMode.value = false
  toast.info('已恢复默认配置')
}
</script>

<template>
  <div class="page config-page fade-up">
    <div class="config-layout">

      <!-- ── 左栏：偏好 + 生成参数 + 回答风格 ── -->
      <div class="config-main">

        <!-- 个人偏好 -->
        <section class="card cfg-card">
          <div class="cfg-header">
            <span class="cfg-icon cfg-icon--muted"><Icon name="user" :size="15" /></span>
            <div class="cfg-heading">
              <h3 class="cfg-title">个人偏好</h3>
              <p class="cfg-subtitle">模型选择、语音播报与输入习惯</p>
            </div>
          </div>

          <div class="cfg-body">
            <div class="field field--row">
              <label class="field-label">问答模型</label>
              <CustomSelect v-model="modelName" :options="MODEL_OPTIONS" />
              <p class="field-hint">选「系统默认」则跟随管理员配置</p>
            </div>

            <div class="field field--row">
              <label class="field-label">语音播报</label>
              <div class="switch-group">
                <span class="switch-text">{{ ttsEnabled ? '已开启' : '已关闭' }}</span>
                <button class="switch" :class="{ on: ttsEnabled }" @click="ttsEnabled = !ttsEnabled" role="switch" :aria-checked="ttsEnabled">
                  <span class="switch-knob" />
                </button>
              </div>
              <p class="field-hint" :class="{ 'field-hint--warn': ttsUnavailable && ttsEnabled }">{{ ttsUnavailable ? '管理员未配置 TTS 服务，语音播报暂不可用' : (ttsEnabled ? 'AI 回答下方出现朗读按钮' : '回答不展示朗读按钮') }}</p>
            </div>

            <div v-if="ttsEnabled" class="field field--indent field--row">
              <label class="field-label">播报音色</label>
              <div class="voice-row">
                <CustomSelect v-model="ttsVoiceType" :options="VOICE_OPTIONS" />
                <button type="button" class="btn btn-outline btn-sm" :disabled="previewLoading" @click="previewVoice(Number(ttsVoiceType) || undefined)">
                  <Icon :name="previewPlaying ? 'square' : 'volume'" :size="14" />
                  {{ previewLoading ? '合成中…' : previewPlaying ? '停止' : '试听' }}
                </button>
              </div>
            </div>

            <div class="field field--row">
              <label class="field-label">Enter 发送</label>
              <div class="switch-group">
                <span class="switch-text">{{ enterToSend ? '已开启' : '已关闭' }}</span>
                <button class="switch" :class="{ on: enterToSend }" @click="enterToSend = !enterToSend" role="switch" :aria-checked="enterToSend">
                  <span class="switch-knob" />
                </button>
              </div>
              <p class="field-hint">{{ enterToSend ? 'Enter 发送 / Shift+Enter 换行' : 'Enter 换行 / Ctrl+Enter 发送' }}</p>
            </div>
          </div>
        </section>

        <!-- 生成参数 -->
        <section class="card cfg-card">
          <div class="cfg-header">
            <span class="cfg-icon cfg-icon--muted"><Icon name="settings" :size="15" /></span>
            <div class="cfg-heading">
              <h3 class="cfg-title">生成参数</h3>
              <p class="cfg-subtitle">控制大模型回答的创造性和长度</p>
            </div>
          </div>

          <div class="cfg-body">
            <div class="field-row-2col">
              <div class="field">
                <div class="field-top">
                  <label class="field-label">温度</label>
                  <span class="field-value">{{ temperature.toFixed(1) }}</span>
                </div>
                <input type="range" min="0" max="1" step="0.1" v-model.number="temperature" class="range-slider" :style="sliderFill(temperature)" />
                <div class="range-scale"><span>0</span><span>0.5</span><span>1</span></div>
                <p class="field-hint">低值稳定精确（推荐 0~0.3），高值创意多样</p>
              </div>

              <div class="field">
                <div class="field-top">
                  <label class="field-label">Top P</label>
                  <span class="field-value">{{ topP.toFixed(2) }}</span>
                </div>
                <input type="range" min="0" max="1" step="0.05" v-model.number="topP" class="range-slider" :style="sliderFill(topP)" />
                <div class="range-scale"><span>0</span><span>0.5</span><span>1</span></div>
                <p class="field-hint">核采样阈值，与温度二选一即可（推荐 0.9）</p>
              </div>
            </div>

            <div class="field field--row">
              <label class="field-label">最大生成长度</label>
              <CustomSelect v-model.number="maxTokens" :options="tokenOptions" />
              <p class="field-hint">单次回答最大 token 数</p>
            </div>
          </div>
        </section>

        <!-- 回答风格 -->
        <section class="card cfg-card">
          <div class="cfg-header">
            <span class="cfg-icon cfg-icon--muted"><Icon name="sparkles" :size="15" /></span>
            <div class="cfg-heading">
              <h3 class="cfg-title">回答风格</h3>
              <p class="cfg-subtitle">定制 AI 的表达方式和展示选项</p>
            </div>
          </div>

          <div class="cfg-body">
            <div class="field field--full">
              <label class="field-label">自定义人设指令</label>
              <div class="textarea-wrap">
                <textarea
                  v-model="systemPrompt"
                  class="cfg-textarea"
                  :placeholder="promptPlaceholder"
                  rows="5"
                  maxlength="2000"
                />
                <div class="textarea-meta">
                  <span class="char-count">{{ charCount }} / 2000</span>
                </div>
              </div>
              <p class="field-hint">追加到系统默认 Prompt 之后，用于定制语气、格式或领域专精</p>
            </div>

            <div class="field field--row">
              <label class="field-label">思考过程</label>
              <div class="switch-group">
                <span class="switch-text">{{ showThinking ? '展示' : '隐藏' }}</span>
                <button class="switch" :class="{ on: showThinking }" @click="showThinking = !showThinking" role="switch" :aria-checked="showThinking">
                  <span class="switch-knob" />
                </button>
              </div>
            </div>
            
            <div class="field field--row">
              <label class="field-label">简洁模式</label>
              <div class="switch-group">
                <span class="switch-text">{{ conciseMode ? '开启' : '关闭' }}</span>
                <button class="switch" :class="{ on: conciseMode }" @click="conciseMode = !conciseMode" role="switch" :aria-checked="conciseMode">
                  <span class="switch-knob" />
                </button>
              </div>
            </div>
          </div>
        </section>
      </div>

      <!-- ── 右栏：检索策略 + 系统状态 + 操作 ── -->
      <div class="config-side">

        <!-- 检索策略 -->
        <section class="card cfg-card">
          <div class="cfg-header">
            <span class="cfg-icon cfg-icon--muted"><Icon name="search" :size="15" /></span>
            <div class="cfg-heading">
              <h3 class="cfg-title">检索策略</h3>
              <p class="cfg-subtitle">控制 RAG 检索行为</p>
            </div>
          </div>

          <div class="cfg-body">
            <div class="field field--row">
              <label class="field-label">召回数量 (Top K)</label>
              <CustomSelect v-model.number="retrievalTopK" :options="topKOptions" />
            </div>

            <div class="field field--row">
              <label class="field-label">联网搜索</label>
              <div class="switch-group">
                <span class="switch-text">{{ webSearchEnabled ? '已开启' : '已关闭' }}</span>
                <button class="switch" :class="{ on: webSearchEnabled }" @click="webSearchEnabled = !webSearchEnabled" role="switch" :aria-checked="webSearchEnabled">
                  <span class="switch-knob" />
                </button>
              </div>
            </div>

            <div v-if="webSearchEnabled" class="field field--indent field--row">
              <label class="field-label">搜索服务</label>
              <CustomSelect v-model="webProvider" :options="webProviderOpts" />
            </div>

            <div class="field field--row">
              <label class="field-label">引用来源数</label>
              <CustomSelect v-model.number="sourceCount" :options="sourceOptions" />
            </div>
          </div>
        </section>

        <!-- 系统状态 -->
        <section class="card cfg-card">
          <div class="cfg-header">
            <span class="cfg-icon cfg-icon--muted"><Icon name="info" :size="15" /></span>
            <div class="cfg-heading">
              <h3 class="cfg-title">当前状态</h3>
              <p class="cfg-subtitle">后端运行配置概览（只读）</p>
            </div>
          </div>

          <div v-if="sysStatus" class="status-list">
            <div class="status-item">
              <span class="status-label">推理模型</span>
              <span class="status-val" :class="{ mono: !!modelName }">{{ modelName || `系统默认 · ${sysStatus.defaultModel}` }}</span>
            </div>
            <div class="status-item">
              <span class="status-label">Embedding</span>
              <span class="status-val mono">{{ sysStatus.embeddingModel }} · {{ sysStatus.embeddingDim }}d</span>
            </div>
            <div class="status-item">
              <span class="status-label">重排器</span>
              <span class="status-val">{{ rerankerLabel }}</span>
            </div>
            <div class="status-item">
              <span class="status-label">图谱增强</span>
              <span class="status-flag"><i class="dot" :class="sysStatus.graphEnabled ? 'dot--on' : 'dot--off'" />{{ sysStatus.graphEnabled ? '已启用' : '已停用' }}</span>
            </div>
            <div class="status-item">
              <span class="status-label">长期记忆</span>
              <span class="status-flag"><i class="dot" :class="sysStatus.memoryEnabled ? 'dot--on' : 'dot--off'" />{{ sysStatus.memoryEnabled ? 'Mem0 已启用' : '已停用' }}</span>
            </div>
            <div class="status-item">
              <span class="status-label">混合检索</span>
              <span class="status-flag"><i class="dot" :class="sysStatus.esEnabled ? 'dot--on' : 'dot--off'" />{{ sysStatus.esEnabled ? 'ES + pgvector' : 'pgvector' }}</span>
            </div>
            <div class="status-item">
              <span class="status-label">对话摘要</span>
              <span class="status-flag"><i class="dot" :class="sysStatus.convSummaryEnabled ? 'dot--on' : 'dot--off'" />{{ sysStatus.convSummaryEnabled ? '已启用' : '已停用' }}</span>
            </div>
            <div class="status-item">
              <span class="status-label">联网搜索</span>
              <span class="status-val">{{ webProviderText }}</span>
            </div>
            <div class="status-item">
              <span class="status-label">语音服务</span>
              <span class="status-flag"><i class="dot" :class="sysStatus.ttsAvailable ? 'dot--on' : 'dot--off'" />{{ sysStatus.ttsAvailable ? '腾讯云 TTS' : '未配置' }}</span>
            </div>
          </div>
          <div v-else class="status-empty">正在加载后端配置…</div>
        </section>

      </div>

    </div>

    <!-- ── 底部操作栏（全宽卡片，滚动时 sticky 悬浮，保存始终可触达） ── -->
    <section class="card cfg-actions-card">
      <div class="cfg-actions-inner">
        <span v-if="savedAt" class="save-note"><Icon name="check" :size="13" /> 已于 {{ savedAt }} 保存</span>
        <button class="btn btn-outline" @click="resetDefaults">恢复默认</button>
        <button class="btn btn-primary" @click="saveAll">保存配置</button>
      </div>
    </section>
  </div>
</template>

<style scoped>
/* ── 页面布局：左右两栏 ── */
.config-layout {
  display: grid;
  grid-template-columns: 1fr 340px;
  gap: 20px;
  align-items: start;
}
.config-main {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.config-side {
  display: flex;
  flex-direction: column;
  gap: 20px;
  position: sticky;
  top: 0;
}

/* ── 卡片 ── */
.cfg-card {
  padding: 20px;
}

/* ── 卡片头部：图标 chip + 标题/副标题堆叠 ── */
.cfg-header {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 18px;
  padding-bottom: 14px;
  border-bottom: 1px solid var(--border);
}
.cfg-icon {
  width: 30px; height: 30px;
  border-radius: var(--radius-sm);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.cfg-icon--brand   { background: var(--brand-soft);   color: var(--brand); }
.cfg-icon--warning { background: var(--warning-soft); color: var(--warning); }
.cfg-icon--success { background: var(--success-soft); color: var(--success); }
.cfg-icon--info    { background: var(--info-soft);    color: var(--info); }
.cfg-icon--muted   { background: var(--bg-subtle);    color: var(--text-secondary); }
.cfg-heading {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.cfg-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
  line-height: 1.35;
}
.cfg-subtitle {
  font-size: 12.5px;
  color: var(--text-tertiary);
  margin: 0;
}

/* ── 表单体 ── */
.cfg-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* ── 字段（通用） ── */
.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.field--full {
  max-width: 100%;
}
.field--row {
  display: flex;
  flex-direction: row; /* 必须显式重置：.field 的 column 会让标签/控件垂直堆叠居中，布局崩坏 */
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 4px 16px;
}
.field--row .field-label {
  padding-top: 0;
  flex-shrink: 0;
}
.field--row > .field-hint {
  flex-basis: 100%;
  margin: 0;
}
.field--indent {
  padding-left: 16px;
  border-left: 2px solid var(--border);
}
.field-label {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
}
.field-hint {
  font-size: 12px;
  color: var(--text-tertiary);
  line-height: 1.4;
  margin: 0;
}
.field-hint--warn { color: var(--warning); }
.field-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 2px;
}
.field-value {
  font-size: 12px;
  font-weight: 600;
  color: var(--brand);
  background: var(--brand-soft);
  padding: 2px 9px;
  border-radius: var(--radius-pill);
  font-family: var(--font-mono, 'Cascadia Code', 'Fira Code', Consolas, monospace);
  letter-spacing: 0.2px;
}

/* ── 双列字段行 ── */
.field-row-2col {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

/* ── 开关 ── */
.switch-group {
  display: flex;
  align-items: center;
  gap: 8px;
}
.switch {
  position: relative;
  width: 36px; height: 20px;
  border-radius: 10px;
  border: none;
  background: var(--border);
  cursor: pointer;
  transition: background var(--dur-fast) var(--ease-out);
  padding: 0;
  flex-shrink: 0;
}
.switch.on { background: var(--brand); }
.switch-knob {
  position: absolute;
  top: 2px; left: 2px;
  width: 16px; height: 16px;
  border-radius: 50%;
  background: #fff;
  box-shadow: 0 1px 3px rgba(0,0,0,.15);
  transition: transform var(--dur-fast) var(--ease-out);
}
.switch.on .switch-knob {
  transform: translateX(16px);
}
.switch-text {
  font-size: 12.5px;
  color: var(--text-tertiary);
}

/* ── 滑块 ── */
.range-slider {
  width: 100%;
  height: 4px;
  border-radius: 2px;
  background: var(--border);
  outline: none;
  -webkit-appearance: none;
  appearance: none;
  cursor: pointer;
}
.range-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 16px; height: 16px;
  border-radius: 50%;
  background: var(--brand);
  border: 2px solid var(--bg-surface);
  box-shadow: 0 1px 4px rgba(9, 88, 217, 0.3);
  cursor: pointer;
}
.range-slider::-moz-range-thumb {
  width: 16px; height: 16px;
  border-radius: 50%;
  background: var(--brand);
  border: 2px solid var(--bg-surface);
  box-shadow: 0 1px 4px rgba(9, 88, 217, 0.3);
  cursor: pointer;
}
/* 滑块刻度尺：0 / 中点 / 1 参考值 */
.range-scale {
  display: flex;
  justify-content: space-between;
  margin-top: 4px;
  font-size: 10px;
  color: var(--text-placeholder);
  font-family: var(--font-mono, 'Cascadia Code', 'Fira Code', Consolas, monospace);
}

/* ── 文本框 ── */
.textarea-wrap {
  position: relative;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-surface);
  transition: border-color var(--dur-fast) var(--ease-out),
              box-shadow var(--dur-fast) var(--ease-out);
}
.textarea-wrap:focus-within {
  border-color: var(--brand);
  box-shadow: 0 0 0 3px rgba(9, 88, 217, 0.1);
}
.cfg-textarea {
  width: 100%;
  min-height: 110px;
  padding: 12px 14px;
  padding-bottom: 28px;
  border: none;
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--text-primary);
  font-size: 13px;
  line-height: 1.65;
  resize: none;
  outline: none;
  font-family: inherit;
}
.cfg-textarea::placeholder {
  color: var(--text-tertiary);
}
.textarea-meta {
  position: absolute;
  right: 16px;
  bottom: 6px;
  pointer-events: none;
}
.char-count {
  font-size: 11px;
  color: var(--text-quaternary, var(--text-tertiary));
  font-family: var(--font-mono, 'Cascadia Code', 'Fira Code', Consolas, monospace);
  letter-spacing: 0.2px;
}

/* ── 音色行 ── */
.voice-row {
  display: flex;
  align-items: center;
  gap: 10px;
}
.voice-row .select { width: 200px; }

/* ── 状态列表 ── */
.status-list {
  display: flex;
  flex-direction: column;
  gap: 0;
}
.status-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 0;
  border-bottom: 1px solid var(--border);
}
.status-item:last-child {
  border-bottom: none;
}
.status-label {
  font-size: 12.5px;
  color: var(--text-tertiary);
  font-weight: 500;
}
.status-val {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
}
.status-val.mono {
  font-family: var(--font-mono, 'Cascadia Code', 'Fira Code', Consolas, monospace);
  font-size: 12px;
}
/* 状态指示点：启用绿点亮 / 停用灰点 */
.status-flag {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
}
.dot {
  width: 7px; height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}
.dot--on {
  background: var(--success);
  box-shadow: 0 0 6px color-mix(in srgb, var(--success) 55%, transparent);
}
.dot--off { background: var(--text-placeholder); }
.status-empty {
  padding: 18px 0;
  font-size: 12.5px;
  color: var(--text-tertiary);
  text-align: center;
}

/* ── 底部操作栏（全宽卡片，滚动时 sticky 悬浮） ── */
.cfg-actions-card {
  padding: 14px 20px;
  margin-top: 20px;
  box-shadow: var(--shadow-float);
}
.cfg-actions-inner {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 10px;
}
.save-note {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  margin-right: auto;
  font-size: 12.5px;
  color: var(--success);
}

/* ── 响应式 ── */
@media (max-width: 900px) {
  .config-layout {
    grid-template-columns: 1fr;
  }
  .config-side {
    position: static;
  }
  .field-row-2col {
    grid-template-columns: 1fr;
  }
}
</style>
