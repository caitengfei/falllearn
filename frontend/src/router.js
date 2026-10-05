import { createRouter, createWebHistory } from 'vue-router'
import { auth } from './api'

const T = { role: 'teacher' }
const routes = [
  { path: '/login', component: () => import('./views/Login.vue'), meta: { public: true } },
  // 邀请码自助注册（学生）：/register?code=FD-XXXXXX
  { path: '/register', component: () => import('./views/Register.vue'), meta: { public: true } },
  { path: '/', component: () => import('./views/Home.vue') },
  { path: '/learn', component: () => import('./views/Learn.vue') },
  // 知识地图独立页（原与 AI 问答同屏；同事反馈：点 AI 问答时不应同时出现知识地图）
  { path: '/map', component: () => import('./views/Map.vue') },
  { path: '/kb', component: () => import('./views/Kb.vue') },
  { path: '/competition', component: () => import('./views/Competition.vue') },
  { path: '/practice', component: () => import('./views/Practice.vue') },
  { path: '/report', component: () => import('./views/Report.vue') },
  { path: '/exam/:attemptId', component: () => import('./views/ExamTake.vue') },
  { path: '/wrong', component: () => import('./views/Wrong.vue') },
  { path: '/mine', component: () => import('./views/Mine.vue') },
  // 管理后台（教师）
  { path: '/admin', component: () => import('./views/admin/AdminOverview.vue'), meta: T },
  { path: '/admin/content', component: () => import('./views/admin/AdminContent.vue'), meta: T },
  { path: '/admin/exams', component: () => import('./views/admin/AdminExams.vue'), meta: T },
  { path: '/admin/students', component: () => import('./views/admin/AdminStudents.vue'), meta: T },
  { path: '/admin/accounts', component: () => import('./views/admin/AdminAccounts.vue'), meta: T },
  { path: '/admin/trainings', component: () => import('./views/admin/AdminTrainings.vue'), meta: T },
  { path: '/admin/stats', component: () => import('./views/admin/AdminStats.vue'), meta: T },
  { path: '/admin/wrong', component: () => import('./views/admin/AdminWrong.vue'), meta: T },
  { path: '/admin/ai', component: () => import('./views/admin/AdminAi.vue'), meta: T },
  { path: '/:pathMatch(.*)*', component: () => import('./views/NotFound.vue') }
]

export const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 })
})

router.beforeEach((to) => {
  if (!to.meta.public && !auth.ready) return { path: '/login', query: { next: to.fullPath } }
  if (to.path === '/login' && auth.ready) return '/'
  if (to.meta.role && auth.user?.role !== to.meta.role) return '/'
})