<script setup lang="ts">
// 登录页 — 按 Clipboard_Screenshot.png 截图 1:1 还原。
// 左侧：浅灰白底 + 淡色水印标题 + 副标题 + 蓝色 3D 立方体 + 深色浮动图标
// 右侧：深色(暗底)居中登录卡片
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import Icon from '@/components/ui/Icon.vue'

const auth = useAuthStore()
const router = useRouter()

const form = ref({ username: '', password: '', remember: false })
const showPwd = ref(false)
const loading = ref(false)

async function handleLogin() {
  if (!form.value.username || !form.value.password) return
  loading.value = true
  try {
    await auth.login(form.value.username, form.value.password)
    router.push('/dashboard')
  } catch (e) {
    // 静默失败，壳阶段
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <!-- ====== 左侧品牌区（浅色底）====== -->
    <div class="login-brand">
      <h1 class="brand-title">企业智能知识库系统</h1>
      <p class="brand-desc">
        构建企业知识中枢，赋能智能决策与高效协作<br />
        让知识管理更简单，知识价值最大化
      </p>

      <!-- 3D 插画区 -->
      <div class="illustration">
        <!-- 装饰竖线 -->
        <span class="deco-line dl-1"></span>
        <span class="deco-line dl-2"></span>

        <!-- 浮动图标（深色圆角方块） -->
        <div class="float-badge fb-search"><Icon name="search" :size="18" /></div>
        <div class="float-badge fb-chart"><Icon name="chart" :size="18" /></div>
        <div class="float-badge fb-doc"><Icon name="doc" :size="16" /></div>
        <div class="float-badge fb-gear"><Icon name="settings" :size="16" /></div>

        <!-- 中心蓝色等距立方体 -->
        <div class="cube-scene">
          <div class="iso-cube">
            <div class="face face-top"></div>
            <div class="face face-front"></div>
            <div class="face face-right"></div>
          </div>
        </div>
      </div>
    </div>

    <!-- ====== 右侧登录区（深色卡片）====== -->
    <div class="login-panel">
      <div class="login-card">
        <h2 class="card-title">登录系统</h2>
        <p class="card-subtitle">欢迎登录企业智能知识库系统</p>

        <form @submit.prevent="handleLogin" class="login-form">
          <!-- 账号 -->
          <div class="field">
            <div class="input-box">
              <Icon name="user" :size="16" class="field-icon" />
              <input
                v-model="form.username"
                type="text"
                placeholder="请输入账号"
                autocomplete="username"
                class="field-input"
              />
            </div>
          </div>

          <!-- 密码 -->
          <div class="field">
            <div class="input-box">
              <Icon name="lock" :size="16" class="field-icon" />
              <input
                v-model="form.password"
                :type="showPwd ? 'text' : 'password'"
                placeholder="请输入密码"
                autocomplete="current-password"
                class="field-input"
              />
              <button v-if="form.password" type="button" class="clear-btn" @click="form.password = ''">
                <Icon name="close" :size="12" />
              </button>
            </div>
          </div>

          <!-- 记住密码 / 忘记密码 -->
          <div class="field-options">
            <label class="cb-label">
              <input type="checkbox" v-model="form.remember" />
              <span>记住密码</span>
            </label>
            <a href="#" class="forgot">忘记密码？</a>
          </div>

          <!-- 登录按钮 -->
          <button type="submit" class="btn-login" :disabled="loading">
            {{ loading ? '登录中...' : '登录' }}
          </button>
        </form>

        <!-- 注册入口 -->
        <div class="card-bottom">
          <span>还没有账号？</span><a href="#" class="reg-link">立即注册</a>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* ========== 页面容器 ========== */
.login-page {
  display: flex;
  min-height: 100vh;
  background: #F8FAFC;
}

/* ========== 左侧品牌区 ========== */
.login-brand {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 0 70px;
}
.brand-title {
  font-size: 32px;
  font-weight: 700;
  color: #CBD5E1;           /* 极淡灰色 — 截图里像水印 */
  letter-spacing: 0.03em;
  line-height: 1.25;
  margin: 0 0 14px 0;
}
.brand-desc {
  font-size: 14px;
  color: #94A3B8;
  line-height: 1.75;
  max-width: 400px;
  margin: 0 0 52px 0;
}

/* ---------- 3D 插画 ---------- */
.illustration {
  position: relative;
  width: 340px;
  height: 280px;
}

/* 装饰竖线 */
.deco-line {
  position: absolute;
  width: 3px;
  border-radius: 2px;
  opacity: 0.18;
}
.dl-1 {
  left: 62px;
  bottom: 30px;
  height: 44px;
  background: #3B82F6;
}
.dl-2 {
  right: 95px;
  top: 50%;
  height: 60px;
  background: #64748B;
}

/* 浮动图标 badge（深色圆角方块 + 白/浅图标）*/
.float-badge {
  position: absolute;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 42px;
  height: 42px;
  border-radius: 11px;
  background: #1E293B;
  color: #94A3B8;
  box-shadow: 0 4px 14px rgba(15, 23, 42, 0.18);
  animation: floatY 3s ease-in-out infinite;
}
.fb-search {
  top: 12px;
  left: 20px;
  animation-delay: 0s;
}
.fb-chart {
  top: 8px;
  right: 40px;
  animation-delay: 0.7s;
  width: 38px;
  height: 38px;
}
.fb-doc {
  bottom: 90px;
  left: 28px;
  animation-delay: 1.4s;
  width: 36px;
  height: 36px;
}
.fb-gear {
  bottom: 55px;
  right: 22px;
  animation-delay: 2.1s;
  width: 34px;
  height: 34px;
}

@keyframes floatY {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-9px); }
}

/* 中心蓝色立方体 */
.cube-scene {
  position: absolute;
  bottom: 40px;
  left: 50%;
  transform: translateX(-50%);
  perspective: 500px;
}
.iso-cube {
  position: relative;
  width: 72px;
  height: 72px;
  transform-style: preserve-3d;
  transform: rotateX(-18deg) rotateY(-28deg);
}
.face {
  position: absolute;
  width: 100%;
  height: 100%;
  border-radius: 10px;
  backface-visibility: hidden;
}
.face-top {
  background: linear-gradient(145deg, #60A5FA, #3B82F6);
  transform: translateZ(36px);
}
.face-front {
  background: linear-gradient(180deg, #2563EB, #1D4ED8);
  transform: rotateX(90deg) translateZ(36px);
}
.face-right {
  background: linear-gradient(180deg, #1E40AF, #1E3A8A);
  transform: rotateY(90deg) translateZ(36px);
}

/* ========== 右侧登录面板 ========== */
.login-panel {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48px;
  min-width: 480px;
  /* 深色背景 — 和左侧形成对比 */
  background: linear-gradient(160deg, #0F172A 0%, #1E293B 100%);
}

/* 登录卡片 */
.login-card {
  width: 380px;
  padding: 44px 38px 36px;
  border-radius: 18px;
  /* 卡片本身也是深色但比面板稍亮 */
  background: rgba(30, 41, 59, 0.65);
  border: 1px solid rgba(148, 163, 184, 0.08);
  backdrop-filter: blur(12px);
}
.card-title {
  text-align: center;
  font-size: 21px;
  font-weight: 700;
  color: #F1F5F9;
  margin: 0 0 6px 0;
}
.card-subtitle {
  text-align: center;
  font-size: 13px;
  color: #94A3B8;
  margin: 0 0 30px 0;
}

/* 表单 */
.login-form {
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

/* 输入框（深色风格）*/
.input-box {
  position: relative;
  display: flex;
  align-items: center;
}
.field-icon {
  position: absolute;
  left: 13px;
  color: #64748B;
  pointer-events: none;
  z-index: 1;
}
.field-input {
  width: 100%;
  height: 44px;
  padding: 0 14px 0 40px;
  font-size: 13.5px;
  color: #E2E8F0;
  background: rgba(51, 65, 85, 0.45);
  border: 1px solid rgba(71, 85, 105, 0.6);
  border-radius: 10px;
  outline: none;
  transition: all 0.2s ease;
}
.field-input::placeholder {
  color: #64748B;
}
.field-input:focus {
  border-color: #3B82F6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.15);
  background: rgba(51, 65, 85, 0.6);
}

.clear-btn {
  position: absolute;
  right: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: 6px;
  border: none;
  background: transparent;
  color: #64748B;
  cursor: pointer;
}
.clear-btn:hover {
  background: rgba(148, 163, 184, 0.12);
  color: #94A3B8;
}

/* 记住密码 / 忘记密码 行 */
.field-options {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 2px;
}
.cb-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #94A3B8;
  cursor: pointer;
}
.cb-label input[type='checkbox'] {
  accent-color: #3B82F6;
  width: 15px;
  height: 15px;
}
.forgot {
  font-size: 13px;
  color: #60A5FA;
  text-decoration: none;
}
.forgot:hover {
  text-decoration: underline;
  color: #93C5FD;
}

/* 登录按钮 */
.btn-login {
  width: 100%;
  height: 46px;
  font-size: 15px;
  font-weight: 600;
  color: #fff;
  background: linear-gradient(135deg, #3B82F6, #2563EB);
  border: none;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s ease;
  margin-top: 4px;
}
.btn-login:hover {
  background: linear-gradient(135deg, #2563EB, #1D4ED8);
  box-shadow: 0 4px 16px rgba(37, 99, 235, 0.35);
  transform: translateY(-1px);
}
.btn-login:active {
  transform: translateY(0);
}
.btn-login:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  transform: none;
}

/* 底部注册入口 */
.card-bottom {
  text-align: center;
  margin-top: 22px;
  font-size: 13px;
  color: #64748B;
}
.reg-link {
  color: #60A5FA;
  font-weight: 500;
  text-decoration: none;
  margin-left: 4px;
}
.reg-link:hover {
  text-decoration: underline;
  color: #93C5FD;
}
</style>
