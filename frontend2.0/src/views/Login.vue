<script setup lang="ts">
// 登录页 — 按 640.png 截图 1:1 还原。
// 左侧品牌区（标题+副标题+3D插画），右侧登录卡片。
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
    <!-- 左侧品牌区 -->
    <div class="login-brand">
      <h1 class="brand-title">企业智能知识库系统</h1>
      <p class="brand-desc">
        构建企业知识中枢，赋能智能决策与高效协作<br />
        让知识管理更简单，知识价值最大化
      </p>
      <!-- 3D 等距插画：用纯 CSS/SVG 模拟截图中的蓝色层叠方块 + 浮动图标 -->
      <div class="illustration">
        <!-- 底层平台 -->
        <div class="iso-base"></div>
        <div class="iso-layer iso-layer-2"></div>
        <div class="iso-layer iso-layer-3"></div>
        <div class="iso-cube">
          <div class="cube-face cube-top"></div>
          <div class="cube-face cube-front"></div>
          <div class="cube-face cube-right"></div>
        </div>
        <!-- 浮动图标 -->
        <div class="float-icon float-chart"><Icon name="chart" :size="22" /></div>
        <div class="float-icon float-search"><Icon name="search" :size="20" /></div>
        <div class="float-icon float-doc"><Icon name="doc" :size="18" /></div>
        <div class="float-icon float-link"><Icon name="link" :size="16" /></div>
        <!-- 装饰竖条 -->
        <div class="deco-bar deco-bar-1"></div>
        <div class="deco-bar deco-bar-2"></div>
        <div class="deco-bar deco-bar-3"></div>
      </div>
    </div>

    <!-- 右侧登录卡片 -->
    <div class="login-card-wrap">
      <div class="login-card">
        <h2 class="card-title">登录系统</h2>
        <p class="card-sub">欢迎登录企业智能知识库系统</p>

        <form @submit.prevent="handleLogin" class="login-form">
          <div class="field">
            <div class="input-wrap">
              <Icon name="user" :size="16" class="field-icon" />
              <input v-model="form.username" type="text" placeholder="请输入账号" autocomplete="username" class="input" />
            </div>
          </div>

          <div class="field">
            <div class="input-wrap">
              <Icon name="lock" :size="16" class="field-icon" />
              <input v-model="form.password" :type="showPwd ? 'text' : 'password'" placeholder="请输入密码" autocomplete="current-password" class="input" />
              <button type="button" class="pwd-toggle" @click="showPwd = !showPwd">
                <Icon :name="showPwd ? 'eye' : 'close'" :size="14" />
              </button>
            </div>
          </div>

          <div class="field-row">
            <label class="checkbox-label">
              <input type="checkbox" v-model="form.remember" />
              <span>记住密码</span>
            </label>
            <a href="#" class="forgot-link">忘记密码？</a>
          </div>

          <button type="submit" class="btn btn-primary btn-login" :disabled="loading">
            {{ loading ? '登录中...' : '登录' }}
          </button>
        </form>

        <div class="card-footer">
          <span class="footer-text">还没有账号？</span>
          <a href="#" class="register-link">立即注册</a>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  display: flex;
  min-height: 100vh;
  background: linear-gradient(135deg, #EEF4FF 0%, #F5F8FC 40%, #FFFFFF 100%);
}

/* ====== 左侧品牌区 ====== */
.login-brand {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 0 60px;
}
.brand-title {
  font-size: 34px;
  font-weight: 800;
  color: var(--text-primary);
  letter-spacing: -0.02em;
  line-height: 1.2;
  margin-bottom: 12px;
}
.brand-desc {
  font-size: 15px;
  color: var(--text-secondary);
  line-height: 1.7;
  max-width: 420px;
  margin-bottom: 48px;
}

/* 3D 插画 */
.illustration {
  position: relative;
  width: 320px;
  height: 260px;
}

/* 底座 */
.iso-base {
  position: absolute;
  bottom: 10px;
  left: 50%;
  transform: translateX(-50%);
  width: 220px;
  height: 18px;
  background: linear-gradient(90deg, transparent, rgba(1, 77, 178, 0.08), transparent);
  border-radius: 50%;
  filter: blur(6px);
}
.iso-layer {
  position: absolute;
  bottom: 28px;
  left: 50%;
  transform: translateX(-50%) rotateX(60deg);
  width: 160px;
  height: 100px;
  border: 1.5px solid rgba(1, 77, 178, 0.12);
  border-radius: 10px;
  background: rgba(1, 77, 178, 0.03);
}
.iso-layer-2 { transform: translateX(-50%) rotateX(60deg) translateY(-30px) scale(0.85); }
.iso-layer-3 { transform: translateX(-50%) rotateX(60deg) translateY(-58px) scale(0.72); }

/* 主方块 */
.iso-cube {
  position: absolute;
  bottom: 55px;
  left: 50%;
  transform: translateX(-50%);
  width: 80px;
  height: 80px;
  transform-style: preserve-3d;
  transform: translateX(-50%) rotateX(-15deg) rotateY(-25deg);
}
.cube-face {
  position: absolute;
  width: 100%;
  height: 100%;
  border-radius: 10px;
  backface-visibility: hidden;
}
.cube-top {
  background: linear-gradient(135deg, #4DA0FF, #2563EB);
  transform: translateZ(40px);
}
.cube-front {
  background: linear-gradient(180deg, #1E6FEA, #0C52BF);
  transform: rotateX(90deg) translateZ(40px);
}
.cube-right {
  background: linear-gradient(180deg, #1659CE, #0B42A0);
  transform: rotateY(90deg) translateZ(40px);
}

/* 浮动图标 */
.float-icon {
  position: absolute;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  border-radius: 12px;
  background: var(--bg-surface);
  box-shadow: 0 4px 16px rgba(1, 77, 178, 0.12);
  color: var(--brand);
  animation: float 3s ease-in-out infinite;
}
.float-chart { top: 5px; right: 35px; animation-delay: 0s; }
.float-search { top: 65px; left: 10px; animation-delay: 0.7s; width: 38px; height: 38px; }
.float-doc { bottom: 75px; left: 45px; animation-delay: 1.4s; width: 36px; height: 36px; }
.float-link { bottom: 30px; right: 20px; animation-delay: 2.1s; width: 34px; height: 34px; }

@keyframes float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-8px); }
}

/* 装饰竖条 */
.deco-bar {
  position: absolute;
  width: 4px;
  border-radius: 2px;
  opacity: 0.25;
}
.deco-bar-1 { bottom: 20px; left: 85px; height: 40px; background: var(--brand); }
.deco-bar-2 { bottom: 35px; left: 210px; height: 56px; background: #10B981; }
.deco-bar-3 { top: 45px; left: 200px; height: 32px; background: #8B5CF6; }

/* ====== 右侧登录卡片 ====== */
.login-card-wrap {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
  min-width: 440px;
}
.login-card {
  width: 380px;
  background: var(--bg-surface);
  border-radius: var(--radius-xl);
  padding: 40px 36px 32px;
  box-shadow: var(--shadow-float);
}
.card-title {
  text-align: center;
  font-size: 22px;
  font-weight: 700;
  margin-bottom: 6px;
  color: var(--text-primary);
}
.card-sub {
  text-align: center;
  font-size: 13px;
  color: var(--text-tertiary);
  margin-bottom: 32px;
}

/* 表单 */
.login-form {
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.field { display: flex; flex-direction: column; gap: 6px; }

.input-wrap {
  position: relative;
  display: flex;
  align-items: center;
}
.field-icon {
  position: absolute;
  left: 13px;
  color: var(--text-tertiary);
  pointer-events: none;
  z-index: 1;
}
.input-wrap .input {
  padding-left: 38px;
  height: 44px;
  font-size: 14px;
  border-color: var(--border);
  border-radius: var(--radius-md);
  transition: all var(--dur-fast);
}
.pwd-toggle {
  position: absolute;
  right: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: var(--radius-sm);
  color: var(--text-tertiary);
  cursor: pointer;
  z-index: 1;
}
.pwd-toggle:hover {
  background: var(--bg-hover);
  color: var(--text-secondary);
}

.field-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.checkbox-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--text-secondary);
  cursor: pointer;
}
.checkbox-label input[type='checkbox'] {
  accent-color: var(--brand);
  width: 15px;
  height: 15px;
}
.forgot-link {
  font-size: 13px;
  color: var(--brand);
  text-decoration: none;
}
.forgot-link:hover { text-decoration: underline; }

.btn-login {
  height: 46px;
  font-size: 15px;
  font-weight: 600;
  border-radius: var(--radius-md);
  margin-top: 4px;
}

.card-footer {
  text-align: center;
  margin-top: 24px;
  font-size: 13px;
}
.footer-text { color: var(--text-tertiary); }
.register-link {
  color: var(--brand);
  font-weight: 500;
  text-decoration: none;
  margin-left: 4px;
}
.register-link:hover { text-decoration: underline; }
</style>
