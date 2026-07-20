<script setup lang="ts">
// 登录页 — 按 640.png 截图 1:1 还原。
// 浅色全局背景 | 左侧：深色标题 + 副标题 + 玻璃层叠3D插画(透明平台+蓝方块+浅色浮动图标)
// 右侧：浅色居中登录卡片（白底、无顶部导航栏）
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
    <!-- ====== 左侧品牌区 ====== -->
    <div class="login-brand">
      <h1 class="brand-title">企业智能知识库系统</h1>
      <p class="brand-desc">
        构建企业知识中枢，赋能智能决策与高效协作<br />
        让知识管理更简单，知识价值最大化
      </p>

      <!-- 3D 等距玻璃层叠插画 -->
      <div class="illus-area">
        <!-- 装饰竖线 -->
        <span class="deco-vline dv1"></span>
        <span class="deco-vline dv2"></span>

        <!-- 浮动图标（浅色圆角方块） -->
        <div class="float-badge fb-pie"><Icon name="chart" :size="18" /></div>
        <div class="float-badge fb-doc"><Icon name="doc" :size="16" /></div>
        <div class="float-badge fb-search"><Icon name="search" :size="18" /></div>
        <div class="float-badge fb-gear"><Icon name="settings" :size="16" /></div>

        <!-- 玻璃层叠平台 + 中心蓝色立方体 -->
        <div class="stack-scene">
          <!-- 从下到上四层玻璃平台（逐层缩小+上移） -->
          <div class="glass-layer gl4"></div>
          <div class="glass-layer gl3"></div>
          <div class="glass-layer gl2"></div>
          <div class="glass-layer gl1"></div>
          <!-- 中心蓝色立方体 -->
          <div class="cube-wrap">
            <div class="cube3d">
              <div class="cface ctop"></div>
              <div class="cface cfront"></div>
              <div class="cface cright"></div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ====== 右侧登录卡片（浅色）====== -->
    <div class="login-right">
      <div class="login-card">
        <h2 class="card-title">登录系统</h2>
        <p class="card-sub">欢迎登录企业智能知识库系统</p>

        <form @submit.prevent="handleLogin" class="lform">
          <!-- 账号 -->
          <div class="fld">
            <div class="ibox">
              <Icon name="user" :size="16" class="ficon" />
              <input v-model="form.username" type="text" placeholder="请输入账号" autocomplete="username" class="finp" />
            </div>
          </div>

          <!-- 密码 -->
          <div class="fld">
            <div class="ibox">
              <Icon name="lock" :size="16" class="ficon" />
              <input v-model="form.password" :type="showPwd ? 'text' : 'password'" placeholder="请输入密码" autocomplete="current-password" class="finp" />
              <button v-if="form.password" type="button" class="eye-btn" @click="showPwd = !showPwd">
                <Icon name="close" :size="12" />
              </button>
            </div>
          </div>

          <!-- 记住密码 + 忘记密码 -->
          <div class="fopts">
            <label class="cbl">
              <input type="checkbox" v-model="form.remember" />
              <span>记住密码</span>
            </label>
            <a href="#" class="flink">忘记密码？</a>
          </div>

          <!-- 登录按钮 -->
          <button type="submit" class="btn-login" :disabled="loading">
            {{ loading ? '登录中...' : '登录' }}
          </button>
        </form>

        <!-- 注册 -->
        <div class="cbottom">
          <span>还没有账号？</span><a href="#" class="rlink">立即注册</a>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* ========== 页面容器 — 淡蓝白渐变背景 ========== */
.login-page {
  display: flex;
  min-height: 100vh;
  background: linear-gradient(135deg, #F0F5FF 0%, #F7FAFC 45%, #FFFFFF 100%);
}

/* ========== 左侧品牌区 ========== */
.login-brand {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 0 64px;
}
.brand-title {
  font-size: 30px;
  font-weight: 800;
  color: #1E293B;           /* 深色粗体 — 截图实色 */
  letter-spacing: -0.01em;
  line-height: 1.25;
  margin: 0 0 14px 0;
}
.brand-desc {
  font-size: 14px;
  color: #64748B;           /* 中灰 */
  line-height: 1.75;
  max-width: 400px;
  margin: 0 0 52px 0;
}

/* ---------- 3D 玻璃层叠插画 ---------- */
.illus-area {
  position: relative;
  width: 340px;
  height: 300px;
}

/* 装饰竖线（淡蓝/灰色细条）*/
.deco-vline {
  position: absolute;
  width: 4px;
  border-radius: 2px;
  opacity: 0.22;
}
.dv1 {
  left: 58px;
  bottom: 35px;
  height: 46px;
  background: #93C5FD;       /* 淡蓝 */
}
.dv2 {
  right: 100px;
  bottom: 80px;
  height: 58px;
  background: #CBD5E1;       /* 浅灰 */
}

/* 浮动图标 badge（浅色圆角方块 — 白/极浅底+柔和阴影）*/
.float-badge {
  position: absolute;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  border-radius: 12px;
  background: #FFFFFF;
  color: #64748B;
  box-shadow: 0 4px 18px rgba(148, 163, 184, 0.25);
  animation: fy 3.2s ease-in-out infinite;
}
.fb-pie {
  top: 10px;
  left: 18px;
  animation-delay: 0s;
}
.fb-search {
  top: 55px;
  right: 15px;
  animation-delay: 0.8s;
  width: 40px;
  height: 40px;
}
.fb-doc {
  bottom: 105px;
  left: 32px;
  animation-delay: 1.6s;
  width: 38px;
  height: 38px;
}
.fb-gear {
  bottom: 60px;
  right: 26px;
  animation-delay: 2.3s;
  width: 36px;
  height: 36px;
}

@keyframes fy {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-10px); }
}

/* ---------- 玻璃层叠平台 ---------- */
.stack-scene {
  position: absolute;
  bottom: 20px;
  left: 50%;
  transform: translateX(-50%);
  perspective: 600px;
}
.glass-layer {
  position: absolute;
  left: 50%;
  transform: translateX(-50%) rotateX(65deg);
  border: 1.5px solid rgba(147, 197, 253, 0.35);
  border-radius: 14px;
  background: linear-gradient(180deg, rgba(219, 234, 254, 0.55) 0%, rgba(191, 219, 254, 0.3) 100%);
  box-shadow: 0 6px 24px rgba(59, 130, 246, 0.08);
}
/* 四层从下到上，逐层缩小并上移 */
.gl4 { width: 200px; height: 24px; bottom: 0; }
.gl3 { width: 176px; height: 22px; bottom: 22px; }
.gl2 { width: 152px; height: 20px; bottom: 42px; }
.gl1 { width: 128px; height: 18px; bottom: 60px; }

/* 中心蓝色立方体 */
.cube-wrap {
  position: absolute;
  bottom: 68px;
  left: 50%;
  transform: translateX(-50%) translateY(-12px);
}
.cube3d {
  position: relative;
  width: 64px;
  height: 64px;
  transform-style: preserve-3d;
  transform: rotateX(-18deg) rotateY(-26deg);
}
.cface {
  position: absolute;
  width: 100%;
  height: 100%;
  border-radius: 9px;
  backface-visibility: hidden;
}
.ctop {
  background: linear-gradient(145deg, #60A5FA, #3B82F6);
  transform: translateZ(32px);
}
.cfront {
  background: linear-gradient(180deg, #2563EB, #1D4ED8);
  transform: rotateX(90deg) translateZ(32px);
}
.cright {
  background: linear-gradient(180deg, #1E40AF, #1E3A8A);
  transform: rotateY(90deg) translateZ(32px);
}

/* ========== 右侧登录区 ========== */
.login-right {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48px;
  min-width: 480px;
}

/* 登录卡片 — 浅色白底 */
.login-card {
  width: 380px;
  padding: 44px 38px 36px;
  border-radius: 16px;
  background: #FFFFFF;         /* 白底！不是暗底 */
  border: 1px solid #E2E8F0;
  box-shadow: 0 4px 24px rgba(148, 163, 184, 0.12);
}
.card-title {
  text-align: center;
  font-size: 21px;
  font-weight: 700;
  color: #1E293B;             /* 深色标题 */
  margin: 0 0 6px 0;
}
.card-sub {
  text-align: center;
  font-size: 13px;
  color: #94A3B8;             /* 灰色副标题 */
  margin: 0 0 30px 0;
}

/* 表单 */
.lform {
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.fld {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

/* 输入框 — 浅色风格（白底+细边框+左图标）*/
.ibox {
  position: relative;
  display: flex;
  align-items: center;
}
.ficon {
  position: absolute;
  left: 13px;
  color: #94A3B8;
  pointer-events: none;
  z-index: 1;
}
.finp {
  width: 100%;
  height: 44px;
  padding: 0 14px 0 40px;
  font-size: 13.5px;
  color: #1E293B;
  background: #F8FAFC;
  border: 1px solid #E2E8F0;
  border-radius: 10px;
  outline: none;
  transition: all 0.2s ease;
  box-sizing: border-box;
}
.finp::placeholder {
  color: #94A3B8;
}
.finp:focus {
  border-color: #3B82F6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.12);
  background: #FFFFFF;
}

.eye-btn {
  position: absolute;
  right: 11px;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: 6px;
  border: none;
  background: transparent;
  color: #94A3B8;
  cursor: pointer;
}
.eye-btn:hover {
  background: #F1F5F9;
  color: #64748B;
}

/* 记住密码 + 忘记密码 */
.fopts {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 2px;
}
.cbl {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #64748B;
  cursor: pointer;
}
.cbl input[type='checkbox'] {
  accent-color: #3B82F6;
  width: 15px;
  height: 15px;
}
.flink {
  font-size: 13px;
  color: #3B82F6;
  text-decoration: none;
}
.flink:hover {
  text-decoration: underline;
  color: #2563EB;
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
  box-shadow: 0 4px 16px rgba(37, 99, 235, 0.3);
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

/* 底部注册 */
.cbottom {
  text-align: center;
  margin-top: 22px;
  font-size: 13px;
  color: #94A3B8;
}
.rlink {
  color: #3B82F6;
  font-weight: 500;
  text-decoration: none;
  margin-left: 4px;
}
.rlink:hover {
  text-decoration: underline;
  color: #2563EB;
}
</style>
