<script setup lang="ts">
// 模型配置 — 独立页面（遵循「一个页面一个文件」原则）。
// 配置真值在服务端（/api/settings 的 modelPrefs + preferredModel），前端不再用 localStorage。
import { ref, computed, onMounted } from 'vue'
import CustomSelect from '@/components/ui/CustomSelect.vue'
import { useToastStore } from '@/stores/toast'
import { useModelConfig, DEFAULT_MODEL_PREFS } from '@/composables/useModelConfig'

const toast = useToastStore()
const { state, load, save } = useModelConfig()

// ════════════════════════════════════════
// Section 1 — 生成参数
// ════════════════════════════════════════
const modelName = ref('agnes-2.0-flash')
const temperature = ref(Number(DEFAULT_MODEL_PREFS.temp))
const topP = ref(Number(DEFAULT_MODEL_PREFS.topP))
const maxTokens = ref(Number(DEFAULT_MODEL_PREFS.maxTokens))

const modelOptions = [
  { value: 'agnes-2.0-flash', label: 'agnes-2.0-flash（快速，适合日常问答）' },
  { value: 'agnes-2.0-pro', label: 'agnes-2.0-pro（强力，适合复杂推理）' },
  { value: 'gpt-4o', label: 'GPT-4o（OpenAI）' },
  { value: 'deepseek-chat', label: 'DeepSeek Chat' },
]
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

// 联网搜索 provider：auto 走后端 env 优先级降级，其余显式指定单一服务
const webProvider = ref(DEFAULT_MODEL_PREFS.webProvider as string)
const webProviderOptions = [
  { value: 'auto', label: '自动（按可用密钥优先级）' },
  { value: 'bocha', label: 'BoCha 博查（中文检索质量最佳）' },
  { value: 'tavily', label: 'Tavily（LLM 检索专用）' },
  { value: 'ddg', label: 'DuckDuckGo（无需密钥兜底）' },
]

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

// 从服务端加载已保存配置，填充表单（单一真值在服务端）
onMounted(async () => {
  await load()
  if (state.preferredModel) modelName.value = state.preferredModel
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
  }
  save(modelName.value, modelPrefs)
    .then(() => toast.success('模型配置已保存'))
    .catch((e: unknown) => toast.error(e instanceof Error ? e.message : '保存失败，请重试'))
}

function resetDefaults() {
  modelName.value = 'agnes-2.0-flash'
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
  <div class="secondary-page">
    <div class="config-grid">

      <!-- ── Section 1：生成参数 ── -->
      <section class="card config-section">
        <div class="section-head">
          <h3 class="section-title">
            <span class="section-icon gen">G</span>
            生成参数
          </h3>
          <p class="section-desc">控制大模型回答的创造性和长度</p>
        </div>

        <div class="cfg-form">
          <div class="cfg-row">
            <label class="cfg-label">模型</label>
            <div class="cfg-control">
              <CustomSelect v-model="modelName" :options="modelOptions" />
              <span class="cfg-note">选择推理模型，不同模型速度和效果差异较大</span>
            </div>
          </div>

          <div class="cfg-row">
            <label class="cfg-label">温度</label>
            <div class="cfg-control">
              <div class="cfg-slider">
                <input type="range" min="0" max="1" step="0.1" v-model.number="temperature" class="cfg-range" />
                <span class="cfg-range-val">{{ temperature.toFixed(1) }}</span>
              </div>
              <span class="cfg-note">低值→稳定精确（事实查询推荐 0~0.3），高值→创意多样（写作/头脑风暴 0.7~1）</span>
            </div>
          </div>

          <div class="cfg-row">
            <label class="cfg-label">Top P</label>
            <div class="cfg-control">
              <div class="cfg-slider">
                <input type="range" min="0" max="1" step="0.05" v-model.number="topP" class="cfg-range" />
                <span class="cfg-range-val">{{ topP.toFixed(2) }}</span>
              </div>
              <span class="cfg-note">核采样阈值，与 Temperature 二选一调参即可。推荐保持 0.9 左右</span>
            </div>
          </div>

          <div class="cfg-row">
            <label class="cfg-label">最大生成长度</label>
            <div class="cfg-control">
              <CustomSelect v-model.number="maxTokens" :options="tokenOptions" />
              <span class="cfg-note">单次回答的最大 token 数。越长越费时耗资源</span>
            </div>
          </div>
        </div>
      </section>

      <!-- ── Section 2：检索策略 ── -->
      <section class="card config-section">
        <div class="section-head">
          <h3 class="section-title">
            <span class="section-icon ret">R</span>
            检索策略
          </h3>
          <p class="section-desc">控制 RAG 检索行为和来源展示</p>
        </div>

        <div class="cfg-form">
          <div class="cfg-row">
            <label class="cfg-label">召回数量 (Top K)</label>
            <div class="cfg-control">
              <CustomSelect v-model.number="retrievalTopK" :options="topKOptions" />
              <span class="cfg-note">每次检索从知识库召回的文档片段数量。越多覆盖面越广但噪声也越多</span>
            </div>
          </div>

          <div class="cfg-row">
            <label class="cfg-label">联网搜索</label>
            <div class="cfg-control cfg-switch-row">
              <button
                class="toggle-switch"
                :class="{ on: webSearchEnabled }"
                @click="webSearchEnabled = !webSearchEnabled"
                role="switch"
                :aria-checked="webSearchEnabled"
              >
                <span class="toggle-knob" />
              </button>
              <span class="cfg-note">{{ webSearchEnabled ? '已开启：实时信息（汇率/股价/新闻）会优先联网搜索' : '已关闭：仅使用知识库内文档回答' }}</span>
            </div>
          </div>

          <div class="cfg-row">
            <label class="cfg-label">搜索服务</label>
            <div class="cfg-control">
              <CustomSelect v-model="webProvider" :options="webProviderOptions" />
              <span class="cfg-note">指定联网搜索服务商；选「自动」则按后端可用密钥优先级降级</span>
            </div>
          </div>

          <div class="cfg-row">
            <label class="cfg-label">引用来源数</label>
            <div class="cfg-control">
              <CustomSelect v-model.number="sourceCount" :options="sourceOptions" />
              <span class="cfg-note">回答下方展示的参考来源条数上限</span>
            </div>
          </div>
        </div>
      </section>

      <!-- ── Section 3：回答风格 ── -->
      <section class="card config-section">
        <div class="section-head">
          <h3 class="section-title">
            <span class="section-icon sty">S</span>
            回答风格
          </h3>
          <p class="section-desc">定制 AI 的表达方式和展示选项</p>
        </div>

        <div class="cfg-form">
          <div class="cfg-row cfg-row--textarea">
            <label class="cfg-label">自定义人设指令</label>
            <div class="cfg-control">
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
              <span class="cfg-note">追加到系统默认 Prompt 之后，用于定制回答语气、格式约束或领域专精</span>
              <span class="cfg-badge pending">需后端支持</span>
            </div>
          </div>

          <div class="cfg-row">
            <label class="cfg-label">思考过程</label>
            <div class="cfg-control cfg-switch-row">
              <button
                class="toggle-switch"
                :class="{ on: showThinking }"
                @click="showThinking = !showThinking"
                role="switch"
                :aria-checked="showThinking"
              >
                <span class="toggle-knob" />
              </button>
              <span class="cfg-note">{{ showThinking ? '展示：回答前显示 AI 的决策推理过程' : '隐藏：直接给出最终答案' }}</span>
            </div>
          </div>

          <div class="cfg-row">
            <label class="cfg-label">简洁模式</label>
            <div class="cfg-control cfg-switch-row">
              <button
                class="toggle-switch"
                :class="{ on: conciseMode }"
                @click="conciseMode = !conciseMode"
                role="switch"
                :aria-checked="conciseMode"
              >
                <span class="toggle-knob" />
              </button>
              <span class="cfg-note">{{ conciseMode ? '开启：回答更精炼，省去冗余铺垫' : '关闭：完整详细回答（默认）' }}</span>
              <span class="cfg-badge pending">需后端支持</span>
            </div>
          </div>
        </div>
      </section>

      <!-- ── Section 4：系统状态 ── -->
      <section class="card config-section status-section">
        <div class="section-head">
          <h3 class="section-title">
            <span class="section-icon info">i</span>
            当前状态
          </h3>
          <p class="section-desc">后端运行配置概览（只读）</p>
        </div>

        <div class="status-grid">
          <div class="status-item">
            <span class="status-label">推理模型</span>
            <span class="status-value">{{ modelName }}</span>
          </div>
          <div class="status-item">
            <span class="status-label">Embedding 模型</span>
            <span class="status-value mono">text-embedding-3-small</span>
          </div>
          <div class="status-item">
            <span class="status-label">向量维度</span>
            <span class="status-value mono">1024</span>
          </div>
          <div class="status-item">
            <span class="status-label">重排器</span>
            <span class="status-value">cross-encoder</span>
          </div>
          <div class="status-item">
            <span class="status-label">图谱增强</span>
            <span class="status-value active">已启用</span>
          </div>
          <div class="status-item">
            <span class="status-label">记忆系统</span>
            <span class="status-value active">Mem0 已启用</span>
          </div>
        </div>
      </section>

      <!-- ── 操作栏 ── -->
      <div class="config-actions">
        <button class="btn btn-outline" @click="resetDefaults">恢复默认</button>
        <button class="btn btn-primary" @click="saveAll">保存配置</button>
      </div>

    </div>
  </div>
</template>

<style scoped>
/* ── 布局 ── */
.secondary-page {
  padding: 20px;
}
.config-grid {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* ── 卡片区块 ── */
.config-section {
  padding: 20px;
}
.section-head {
  margin-bottom: 20px;
  padding-bottom: 14px;
  border-bottom: 1px solid var(--border);
}
.section-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 4px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.section-icon {
  width: 26px; height: 26px;
  border-radius: 6px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 700;
  color: #fff;
  flex-shrink: 0;
}
.section-icon.gen { background: linear-gradient(135deg, #0958d9, #1677ff); }
.section-icon.ret { background: linear-gradient(135deg, #15803d, #22c55e); }
.section-icon.sty { background: linear-gradient(135deg, #7c3aed, #a78bfa); }
.section-icon.info {
  background: var(--bg-subtle);
  color: var(--text-secondary);
  font-style: italic;
  font-family: Georgia, serif;
  font-size: 15px;
}
.section-desc {
  font-size: 12.5px;
  color: var(--text-tertiary);
  margin: 0;
  padding-left: 34px;
}

/* ── 表单行 ── */
.cfg-form {
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.cfg-row {
  display: flex;
  align-items: flex-start;
  gap: 16px;
}
.cfg-row--textarea {
  max-width: 800px;
  align-items: stretch;
}
.cfg-label {
  width: 110px;
  flex-shrink: 0;
  padding-top: 2px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  text-align: right;
  line-height: 1.4;
}
.cfg-control {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 5px;
}
.cfg-switch-row {
  flex-direction: row;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

/* ── 滑块 ── */
.cfg-slider {
  max-width: 500px;
  display: flex;
  align-items: center;
  gap: 14px;
}
.cfg-range {
  flex: 1;
  min-width: 0;
  height: 4px;
  border-radius: 2px;
  background: var(--border);
  outline: none;
  -webkit-appearance: none;
  appearance: none;
}
.cfg-range::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 16px; height: 16px;
  border-radius: 50%;
  background: var(--brand);
  border: 2px solid var(--bg-surface);
  box-shadow: 0 1px 4px rgba(1, 77, 178, 0.35);
  cursor: pointer;
}
.cfg-range::-moz-range-thumb {
  width: 16px; height: 16px;
  border-radius: 50%;
  background: var(--brand);
  border: 2px solid var(--bg-surface);
  box-shadow: 0 1px 4px rgba(1, 77, 178, 0.35);
  cursor: pointer;
}
.cfg-range-val {
  min-width: 36px;
  text-align: right;
  font-size: 13px;
  font-weight: 600;
  color: var(--brand);
  font-family: var(--font-mono, 'Cascadia Code', 'Fira Code', Consolas, monospace);
}

/* ── 提示文字 & 徽标 ── */
.cfg-note {
  font-size: 12px;
  color: var(--text-tertiary);
  line-height: 1.5;
}
.cfg-badge {
  display: inline-flex;
  align-items: center;
  padding: 1px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 600;
  line-height: 1.7;
  white-space: nowrap;
  align-self: flex-start;
}
.cfg-badge.pending {
  background: #fff7e6;
  color: #ad6800;
}
.cfg-badge.active {
  background: #f0fdf4;
  color: #15803d;
}

/* ── 文本框 ── */
.cfg-textarea {
  width: 100%;
  min-height: 100px;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-surface);
  color: var(--text-primary);
  font-size: 13px;
  line-height: 1.6;
  resize: vertical;
  outline: none;
  transition: border-color var(--dur-fast) var(--ease-out);
  font-family: inherit;
}
.cfg-textarea:focus {
  border-color: var(--brand);
  box-shadow: 0 0 0 2px rgba(9, 88, 217, 0.1);
}
.cfg-textarea::placeholder {
  color: var(--text-tertiary);
}
.textarea-meta {
  display: flex;
  justify-content: flex-end;
}
.char-count {
  font-size: 11.5px;
  color: var(--text-tertiary);
  font-family: var(--font-mono, 'Cascadia Code', 'Fira Code', Consolas, monospace);
}

/* ── 开关 ── */
.toggle-switch {
  position: relative;
  width: 40px; height: 22px;
  border-radius: 11px;
  border: none;
  background: var(--border);
  cursor: pointer;
  transition: background var(--dur-fast) var(--ease-out);
  padding: 0;
  flex-shrink: 0;
}
.toggle-switch.on {
  background: var(--brand);
}
.toggle-knob {
  position: absolute;
  top: 2px; left: 2px;
  width: 18px; height: 18px;
  border-radius: 50%;
  background: #fff;
  box-shadow: 0 1px 3px rgba(0,0,0,.15);
  transition: transform var(--dur-fast) var(--ease-out);
}
.toggle-switch.on .toggle-knob {
  transform: translateX(18px);
}

/* ── 状态卡片 ── */
.status-section {
}
.status-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
}
.status-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 12px 14px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
}
.status-label {
  font-size: 11.5px;
  color: var(--text-tertiary);
  font-weight: 500;
}
.status-value {
  font-size: 13.5px;
  font-weight: 600;
  color: var(--text-primary);
}
.status-value.mono {
  font-family: var(--font-mono, 'Cascadia Code', 'Fira Code', Consolas, monospace);
  font-size: 12.5px;
}
.status-value.active {
  color: #15803d;
}

/* ── 操作栏 ── */
.config-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding-top: 4px;
}
.config-actions .btn {
  min-width: 100px;
}
</style>
