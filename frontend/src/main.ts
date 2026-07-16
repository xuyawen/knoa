import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './style.css'
import { installMonitor, vueErrorHandler } from './lib/monitor'

// 全局错误捕获 + 首屏性能埋点，挂到 Vue errorHandler 同步生效
installMonitor()
const app = createApp(App)
app.config.errorHandler = vueErrorHandler
app.use(createPinia()).use(router).mount('#app')
