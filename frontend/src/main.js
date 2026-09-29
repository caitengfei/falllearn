import { createApp } from 'vue'
import App from './App.vue'
import { router } from './router'
import './styles/main.css'

const app = createApp(App)
app.use(router)
// 全局错误兜底：单个组件异常不再整页白屏（现场演示保险），并留下控制台线索便于排查
app.config.errorHandler = (err, _inst, info) => {
  console.error('[falllearn] uncaught error:', info, err)
}
router.onError((err) => {
  console.error('[falllearn] router error:', err)
})
app.mount('#app')
