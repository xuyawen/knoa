<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const username = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

onMounted(() => {
  if (auth.isAuthed) router.replace((route.query.redirect as string) || '/')
})

async function onSubmit() {
  error.value = ''
  if (!username.value || !password.value) {
    error.value = '请输入用户名和密码'
    return
  }
  loading.value = true
  try {
    await auth.login(username.value.trim(), password.value)
    router.replace((route.query.redirect as string) || '/')
  } catch (e) {
    error.value = e instanceof Error ? e.message : '登录失败'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <div class="aurora" />
    <div class="login-card">
      <div class="brand">
        <div class="logo">知</div>
        <div class="brand-text">
          <span class="brand-name">知海 Knoa</span>
          <span class="brand-sub">企业知识库 · 智能问答</span>
        </div>
      </div>

      <form class="form" @submit.prevent="onSubmit">
        <label class="field">
          <span class="label">用户名</span>
          <input v-model="username" type="text" autocomplete="username" placeholder="请输入用户名" />
        </label>
        <label class="field">
          <span class="label">密码</span>
          <input v-model="password" type="password" autocomplete="current-password" placeholder="请输入密码" />
        </label>

        <p v-if="error" class="error">{{ error }}</p>

        <button class="submit" type="submit" :disabled="loading">
          {{ loading ? '登录中…' : '登 录' }}
        </button>
      </form>

      <p class="hint">默认管理员：admin / admin123（请尽快在 .env 修改）</p>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
  background: var(--bg);
}
.aurora {
  position: absolute;
  inset: -20%;
  background:
    radial-gradient(38% 38% at 22% 22%, var(--brand-soft), transparent 70%),
    radial-gradient(40% 40% at 80% 72%, var(--brand-soft), transparent 72%);
  filter: blur(48px);
  opacity: 0.55;
}
.login-card {
  position: relative;
  width: 380px;
  max-width: calc(100vw - 40px);
  padding: 32px 28px;
  border-radius: var(--radius-lg);
  background: var(--bg-surface);
  border: 1px solid var(--border);
  box-shadow: var(--shadow-float);
  display: flex;
  flex-direction: column;
  gap: 22px;
}
.brand { display: flex; align-items: center; gap: 12px; }
.logo {
  width: 40px; height: 40px; border-radius: var(--radius-md);
  background: var(--brand); color: #fff;
  display: flex; align-items: center; justify-content: center;
  font-family: var(--font-display); font-weight: 600; font-size: 22px;
}
.brand-text { display: flex; flex-direction: column; line-height: 1.25; }
.brand-name { font-family: var(--font-display); font-weight: 600; font-size: 18px; }
.brand-sub { font-size: 12px; color: var(--text-secondary); }

.form { display: flex; flex-direction: column; gap: 14px; }
.field { display: flex; flex-direction: column; gap: 6px; }
.label { font-size: 13px; color: var(--text-secondary); }
.field input {
  height: 42px; padding: 0 14px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: var(--bg-subtle);
  color: var(--text-primary);
  font-size: 14px;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}
.field input:focus {
  outline: none;
  border-color: var(--brand);
  box-shadow: 0 0 0 3px var(--brand-soft);
}
.error { margin: 0; font-size: 13px; color: var(--danger); }
.submit {
  height: 44px; border: none; border-radius: var(--radius-md);
  background: var(--brand); color: #fff;
  font-size: 15px; font-weight: 600; cursor: pointer;
  transition: transform 0.15s ease, filter 0.15s ease;
}
.submit:hover:not(:disabled) { filter: brightness(1.06); transform: translateY(-1px); }
.submit:disabled { opacity: 0.6; cursor: default; }
.hint { margin: 0; font-size: 12px; color: var(--text-secondary); text-align: center; }
</style>
