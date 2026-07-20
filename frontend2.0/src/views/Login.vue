<script setup lang="ts">
// 登录页（对应截图 #13）：居中卡片 + 品牌，纯界面壳，未接后端。
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import Icon from '@/components/ui/Icon.vue'

const router = useRouter()
const auth = useAuthStore()
const toast = useToastStore()

const username = ref('admin')
const password = ref('')
const remember = ref(true)
const loading = ref(false)

function onSubmit() {
  if (!username.value || !password.value) {
    toast.warning('请输入账号和密码')
    return
  }
  // TODO(功能接入): 替换为真实登录请求 + token 持久化
  loading.value = true
  window.setTimeout(() => {
    loading.value = false
    auth.login(username.value, password.value)
    toast.success('登录成功（界面壳，未接后端）')
    router.push('/dashboard')
  }, 500)
}
</script>

<template>
  <div class="login">
    <!-- 品牌侧栏 -->
    <div class="login-aside">
      <div class="aside-glow" />
      <div class="aside-brand">
        <img src="/favicon.svg" alt="Knoa" class="aside-logo" />
        <span>Knoa</span>
      </div>
      <div class="aside-copy">
        <h1>企业智能知识库</h1>
        <p>多源知识归集 · 语义检索 · AI 一键问答 · 知识沉淀与可视化</p>
      </div>
      <ul class="aside-points">
        <li><Icon name="check" :size="15" /> 统一知识资产，告别信息孤岛</li>
        <li><Icon name="check" :size="15" /> 权限可控的精准检索与生成</li>
        <li><Icon name="check" :size="15" /> 知识图谱驱动持续沉淀</li>
      </ul>
    </div>

    <!-- 表单卡片 -->
    <div class="login-card-wrap">
      <div class="login-card">
        <div class="login-head">
          <h2>欢迎回来</h2>
          <p>登录以继续使用 Knoa 智能知识库</p>
        </div>

        <form class="login-form" @submit.prevent="onSubmit">
          <label class="field-label">账号</label>
          <div class="input-icon">
            <Icon name="user" :size="16" />
            <input v-model="username" class="input" placeholder="请输入账号" autocomplete="username" />
          </div>

          <label class="field-label" style="margin-top: 14px">密码</label>
          <div class="input-icon">
            <Icon name="shield" :size="16" />
            <input
              v-model="password"
              class="input"
              type="password"
              placeholder="请输入密码"
              autocomplete="current-password"
            />
          </div>

          <div class="login-row">
            <label class="remember">
              <input v-model="remember" type="checkbox" />
              <span>记住密码</span>
            </label>
            <a class="link" @click.prevent="toast.info('界面壳阶段暂未实现')">忘记密码？</a>
          </div>

          <button class="btn btn-primary login-submit" :disabled="loading">
            {{ loading ? '登录中…' : '登 录' }}
          </button>
        </form>

        <div class="login-foot">
          还没有账号？<a class="link" @click.prevent="toast.info('界面壳阶段暂未实现')">立即注册</a>
        </div>
      </div>
      <div class="login-tip">演示环境 · 界面壳阶段，登录不校验后端</div>
    </div>
  </div>
</template>

<style scoped>
.login {
  min-height: 100vh;
  display: flex;
  background: var(--bg-page);
}
.login-aside {
  position: relative;
  flex: 1.1;
  padding: 48px 56px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 28px;
  color: #fff;
  background: linear-gradient(135deg, #014DB2 0%, #0B2E6B 60%, #013A87 100%);
  overflow: hidden;
}
.aside-glow {
  position: absolute;
  width: 520px;
  height: 520px;
  right: -160px;
  top: -160px;
  background: radial-gradient(circle, rgba(255, 255, 255, 0.22), transparent 70%);
  filter: blur(8px);
}
.aside-brand {
  display: flex;
  align-items: center;
  gap: 11px;
  font-size: 22px;
  font-weight: 700;
  position: relative;
}
.aside-logo {
  width: 40px;
  height: 40px;
  border-radius: 11px;
}
.aside-copy h1 {
  font-size: 30px;
  font-weight: 700;
  margin: 0 0 10px;
  letter-spacing: -0.01em;
}
.aside-copy p {
  margin: 0;
  max-width: 420px;
  color: rgba(255, 255, 255, 0.82);
  line-height: 1.7;
}
.aside-points {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
  position: relative;
}
.aside-points li {
  display: flex;
  align-items: center;
  gap: 10px;
  color: rgba(255, 255, 255, 0.92);
}
.aside-points :deep(svg) {
  color: #7DD3FC;
}

.login-card-wrap {
  flex: 0.9;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 32px;
  gap: 14px;
}
.login-card {
  width: 100%;
  max-width: 380px;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-float);
  padding: 32px 30px;
}
.login-head h2 {
  margin: 0 0 6px;
  font-size: 22px;
  font-weight: 700;
}
.login-head p {
  margin: 0 0 22px;
  color: var(--text-secondary);
  font-size: 13px;
}
.input-icon {
  position: relative;
  display: flex;
  align-items: center;
}
.input-icon :deep(svg) {
  position: absolute;
  left: 12px;
  color: var(--text-tertiary);
}
.input-icon .input {
  padding-left: 38px;
}
.login-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 16px 0 20px;
  font-size: 13px;
}
.remember {
  display: flex;
  align-items: center;
  gap: 7px;
  color: var(--text-secondary);
  cursor: pointer;
}
.remember input {
  accent-color: var(--brand);
}
.link {
  color: var(--brand);
  cursor: pointer;
  font-weight: 500;
}
.link:hover {
  text-decoration: underline;
}
.login-submit {
  width: 100%;
  height: var(--btn-h-lg);
  font-size: 15px;
  letter-spacing: 0.1em;
}
.login-foot {
  margin-top: 18px;
  text-align: center;
  font-size: 13px;
  color: var(--text-secondary);
}
.login-tip {
  font-size: 12px;
  color: var(--text-tertiary);
}
</style>
