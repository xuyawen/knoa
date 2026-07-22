<script setup lang="ts">
// 登录页 — 按 18_2.svg / login-page-spec.md 1:1 还原。
// 左面板：浅灰底 + Logo + 品牌文案 + 装饰插画（立方体/平台/环绕图标）
// 右面板：白色底 + 居中登录卡片（账号/密码/记住我/SSO）
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import Icon from '@/components/ui/Icon.vue'

const auth = useAuthStore()
const router = useRouter()
const toast = useToastStore()

const form = ref({ username: '', password: '', remember: true })
const loading = ref(false)

async function handleLogin() {
  if (!form.value.username || !form.value.password) return
  loading.value = true
  try {
    await auth.login(form.value.username, form.value.password)
    const redirect = (router.currentRoute.value.query.redirect as string) || '/dashboard'
    router.push(redirect)
  } catch (e) {
    toast.error(e instanceof Error ? e.message : '登录失败，请重试')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <!-- ====== 左面板 ====== -->
    <div class="left-panel">
      <div class="brand-header">
        <div class="logo-box">K</div>
        <span class="logo-text">企业智能知识库系统</span>
      </div>

      <div class="brand-text">
        <h1 class="brand-title">企业智能知识库系统</h1>
        <p class="brand-desc">
          构建企业知识中枢，赋能智能决策与高效协作<br />
          让知识管理更简单，知识价值最大化
        </p>
      </div>

      <div class="spacer" />

      <!-- 装饰插画：712×480 -->
      <div class="illustration">
        <div class="platform platform-bottom" />
        <div class="platform platform-middle" />
        <div class="platform platform-top" />

        <div class="cube-scene">
          <svg class="cube-svg" viewBox="0 0 130 130" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path fill="#014DB2" d="M65 0L130 32.5L130 97.5L65 130L0 97.5L0 32.5L65 0Z" />
            <path fill="#3B82F6" d="M65 0L130 32.5L65 65L0 32.5L65 0Z" />
            <path fill="#1E40AF" d="M130 32.5L65 65L65 130L130 97.5Z" />
            <path fill="#60A5FA" d="M0 32.5L65 65L65 130L0 97.5Z" />
          </svg>
        </div>

        <div class="icon-circle ic-chart"><Icon name="chart" :size="24" /></div>
        <div class="icon-circle ic-search"><Icon name="search" :size="24" /></div>
        <div class="icon-circle ic-doc"><Icon name="doc" :size="24" /></div>
        <div class="icon-circle ic-settings"><Icon name="settings" :size="24" /></div>
      </div>
    </div>

    <!-- ====== 右面板 ====== -->
    <div class="right-panel">
      <div class="login-card">
        <div class="card-header">
          <h2 class="card-title">欢迎登录</h2>
          <p class="card-subtitle">企业智能知识库系统</p>
        </div>

        <form @submit.prevent="handleLogin" class="login-form">
          <div class="field">
            <label class="field-label">账号</label>
            <input
              v-model="form.username"
              type="text"
              class="field-input"
              placeholder="请输入手机号 / 邮箱"
              autocomplete="username"
            />
          </div>

          <div class="field">
            <label class="field-label">密码</label>
            <input
              v-model="form.password"
              type="password"
              class="field-input"
              placeholder="请输入密码"
              autocomplete="current-password"
            />
          </div>

          <div class="options-row">
            <label class="remember">
              <input type="checkbox" v-model="form.remember" class="checkbox-input" />
              <span class="checkbox-check"><Icon name="check" :size="10" /></span>
              <span class="remember-text">记住我</span>
            </label>
            <a href="#" class="forgot-link">忘记密码？</a>
          </div>

          <button type="submit" class="btn-login" :disabled="loading">
            {{ loading ? '登录中...' : '登 录' }}
          </button>
        </form>

        <div class="sso-divider">
          <span class="line" />
          <span class="divider-text">其他登录方式</span>
          <span class="line" />
        </div>

        <div class="sso-row">
          <button type="button" class="sso-btn">企业微信</button>
          <button type="button" class="sso-btn">钉钉</button>
        </div>
      </div>

      <p class="footer-note">企业智能知识库系统 · 内部系统 仅供授权人员使用</p>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  display: flex;
  width: 100%;
  min-height: 100vh;
  background: #fff;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}

.left-panel {
  flex: 0 0 55%;
  display: flex;
  flex-direction: column;
  padding: 40px;
  background: #f2f4f7;
  position: relative;
  min-width: 760px;
  min-height: 760px;
}

.brand-header {
  display: flex;
  align-items: center;
  gap: 10px;
}

.logo-box {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: #014db2;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: 'Outfit', sans-serif;
  font-weight: 700;
  font-size: 18px;
}

.logo-text {
  font-family: 'Inter', sans-serif;
  font-size: 14px;
  font-weight: 500;
  color: #0a1628;
}

.brand-text {
  margin-top: 24px;
}

.brand-title {
  font-family: 'Outfit', sans-serif;
  font-size: 40px;
  font-weight: 700;
  color: #0a1628;
  line-height: 1.2;
  margin: 0;
}

.brand-desc {
  margin-top: 12px;
  font-size: 14px;
  font-weight: 400;
  color: #6b7280;
  line-height: 1.75;
}

.spacer {
  flex: 1;
}

.illustration {
  position: absolute;
  left: 40px;
  bottom: 40px;
  width: 712px;
  height: 480px;
}

.platform {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  border-radius: 999px;
}

.platform-bottom {
  top: 406px;
  width: 540px;
  height: 36px;
  background: linear-gradient(180deg, #e4eaf3, #dce3ee);
}

.platform-middle {
  top: 376px;
  width: 420px;
  height: 28px;
  background: linear-gradient(180deg, #edf1f7, #e5ebf2);
}

.platform-top {
  top: 350px;
  width: 300px;
  height: 22px;
  background: linear-gradient(180deg, #fbfcfe, #f4f7fb);
}

.cube-scene {
  position: absolute;
  left: 257px;
  top: 150px;
  width: 200px;
  height: 200px;
  cursor: pointer;
}

.cube-svg {
  display: block;
  width: 100%;
  height: 100%;
  transform-origin: 50% 62%;
  transition: transform 0.45s cubic-bezier(0.2, 0.8, 0.2, 1), filter 0.45s;
}

/* 鼠标移入方块：立方体轻轻抬头 + 蓝色辉光呼吸 */
.cube-scene:hover .cube-svg {
  transform: scale(1.06) rotate(-3deg);
  filter: drop-shadow(0 16px 22px rgba(1, 77, 178, 0.38));
  animation: cube-pulse 1.8s ease-in-out infinite;
}

.icon-circle {
  position: absolute;
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: #fff;
  border: 1px solid #e5e7eb;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #6b7280;
  box-shadow: 0 4px 16px rgba(10, 23, 40, 0.06);
  animation: fy 3.2s ease-in-out infinite;
  transition: color 0.3s, border-color 0.3s, box-shadow 0.3s;
}

/* 鼠标移入方块：四周图标圈点亮成品牌蓝并加速浮动放大 */
.cube-scene:hover ~ .icon-circle {
  color: #014db2;
  border-color: #cfe0f7;
  box-shadow: 0 8px 22px rgba(1, 77, 178, 0.18);
  animation-name: fy-hover;
  animation-duration: 1.7s;
}

.ic-chart {
  left: 157px;
  top: 60px;
  animation-delay: 0s;
}

.ic-search {
  left: 493px;
  top: 60px;
  animation-delay: 0.8s;
}

.ic-doc {
  left: 109px;
  top: 228px;
  animation-delay: 1.6s;
}

.ic-settings {
  left: 541px;
  top: 228px;
  animation-delay: 2.3s;
}

@keyframes fy {
  0%,
  100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-10px);
  }
}

@keyframes cube-pulse {
  0%,
  100% {
    transform: scale(1.06) rotate(-3deg);
  }
  50% {
    transform: scale(1.1) rotate(-3deg);
  }
}

@keyframes fy-hover {
  0%,
  100% {
    transform: translateY(0) scale(1.12);
  }
  50% {
    transform: translateY(-16px) scale(1.2);
  }
}

.right-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  background: #fff;
  min-width: 420px;
  min-height: 760px;
  padding: 40px;
}

.login-card {
  width: 420px;
  padding: 40px;
  border-radius: 16px;
  background: #fff;
  border: 1px solid #eaeaea;
  box-shadow: 0 12px 32px rgba(10, 23, 40, 0.08);
}

.card-header {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 20px;
}

.card-title {
  font-family: 'Outfit', sans-serif;
  font-size: 28px;
  font-weight: 700;
  color: #0a1628;
  margin: 0;
}

.card-subtitle {
  font-size: 14px;
  font-weight: 400;
  color: #6b7280;
  margin: 0;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.field-label {
  font-size: 13px;
  font-weight: 500;
  color: #0a1628;
}

.field-input {
  width: 100%;
  height: 44px;
  padding: 0 14px;
  font-size: 14px;
  font-weight: 400;
  color: #0a1628;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  outline: none;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
  box-sizing: border-box;
}

.field-input::placeholder {
  color: #9ca3af;
}

.field-input:focus {
  border-color: #014db2;
  box-shadow: 0 0 0 3px rgba(1, 77, 178, 0.12);
}

.options-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.remember {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  user-select: none;
}

.checkbox-input {
  position: absolute;
  opacity: 0;
  width: 0;
  height: 0;
}

.checkbox-check {
  width: 16px;
  height: 16px;
  border-radius: 4px;
  background: #014db2;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s ease, border-color 0.2s ease;
  border: 1px solid #014db2;
}

.checkbox-input:not(:checked) + .checkbox-check {
  background: #fff;
  border-color: #e5e7eb;
  color: transparent;
}

.remember-text {
  font-size: 13px;
  font-weight: 400;
  color: #6b7280;
}

.forgot-link {
  font-size: 13px;
  font-weight: 500;
  color: #014db2;
  text-decoration: none;
}

.forgot-link:hover {
  text-decoration: underline;
}

.btn-login {
  width: 100%;
  height: 48px;
  border-radius: 8px;
  border: none;
  background: #014db2;
  color: #fff;
  font-family: 'Outfit', sans-serif;
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 2px;
  cursor: pointer;
  transition: background 0.2s ease;
}

.btn-login:hover {
  background: #0d5fd1;
}

.btn-login:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.sso-divider {
  display: flex;
  align-items: center;
  gap: 12px;
  height: auto;
  margin-top: 20px;
}

.line {
  flex: 1;
  height: 1px;
  background: #eaeaea;
}

.divider-text {
  font-size: 12px;
  font-weight: 400;
  color: #9ca3af;
  white-space: nowrap;
}

.sso-row {
  display: flex;
  gap: 12px;
  margin-top: 20px;
}

.sso-btn {
  flex: 1;
  height: 44px;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
  background: #fff;
  color: #0a1628;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: border-color 0.2s ease, background 0.2s ease;
}

.sso-btn:hover {
  border-color: #014db2;
  background: #f8fafd;
}

.footer-note {
  font-size: 12px;
  font-weight: 400;
  color: #9ca3af;
  text-align: center;
  margin: 0;
}

@media (max-width: 1100px) {
  .left-panel {
    display: none;
  }
  .right-panel {
    min-width: auto;
    width: 100%;
  }
}
</style>
