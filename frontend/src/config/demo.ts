// 演示账号自动填充配置
// 仅「生产构建」(import.meta.env.PROD) 生效；本地开发(npm run dev)不启用，避免干扰日常调试。
// 账号密码由 Vite 环境变量显式提供（frontend/.env 中的 VITE_DEMO_ACCOUNT / VITE_DEMO_PASSWORD），无默认值。
// 关闭：VITE_DEMO_FILL=false
const enabled =
  import.meta.env.PROD && (import.meta.env.VITE_DEMO_FILL ?? 'true') !== 'false'

export const demoCredentials =
  enabled && import.meta.env.VITE_DEMO_ACCOUNT && import.meta.env.VITE_DEMO_PASSWORD
    ? {
        account: import.meta.env.VITE_DEMO_ACCOUNT,
        password: import.meta.env.VITE_DEMO_PASSWORD,
      }
    : null
