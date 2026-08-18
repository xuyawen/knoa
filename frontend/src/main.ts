import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './style.css'
import { installMonitor, vueErrorHandler } from '@/lib/monitor'
import { siteTitle } from '@/utils/branding'

// 全局错误捕获 + 首屏性能埋点，挂到 Vue errorHandler 同步生效
installMonitor()

// 站点 title 按访问方式切换：IP 直连用 Knoa 品牌名，域名用备案主体名
document.title = siteTitle()

const app = createApp(App)
app.config.errorHandler = vueErrorHandler
app.use(createPinia())
app.use(router)
app.mount('#app')
