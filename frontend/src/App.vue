<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, auth } from './api'

const route = useRoute()
const router = useRouter()
const dueCount = ref(0)
const search = ref('')
const isPublic = computed(() => !!route.meta.public)
const isAdmin = computed(() => route.path.startsWith('/admin'))

async function refreshDue() {
  if (!auth.ready) return
  if (isAdmin.value) return // 管理页不显示错题铃铛，跳过无用请求
  try {
    const w = await api.wrongList('active')
    dueCount.value = w.due_count || 0
  } catch {}
}
// 登录成功后 SPA 内不重挂 App：watch auth 触发刷新（登录页进首页角标才能亮）
watch(() => auth.ready, (v) => { if (v) refreshDue() })
watch(() => route.path, (p) => { if (!p.startsWith('/admin')) refreshDue() })
onMounted(refreshDue)

const tabs = [
  { to: '/', label: '首页' },
  { to: '/learn', label: '学习中心' },
  { to: '/practice', label: '练习考试' },
  { to: '/report', label: '学习报告' },
  { to: '/competition', label: '比赛资料' },
  { to: '/wrong', label: '错题本' },
  { to: '/mine', label: '我的' }
]
const isTeacher = computed(() => auth.user?.role === 'teacher')

const sideNav = [
  { group: '总览', items: [
    { to: '/admin', ic: '📊', label: '数据总览' }
  ]},
  { group: '业务管理', items: [
    { to: '/admin/content', ic: '📢', label: '课程预告 · 轮播' },
    { to: '/admin/exams', ic: '📝', label: '考试管理' },
    { to: '/admin/students', ic: '🎓', label: '学生管理' },
    { to: '/admin/accounts', ic: '👥', label: '账号管理' },
    { to: '/admin/trainings', ic: '🗂', label: '培训管理' }
  ]},
  { group: '统计分析', items: [
    { to: '/admin/stats', ic: '📈', label: '培训情况统计' }
  ]},
  { group: 'AI 管理', items: [
    { to: '/admin/ai', ic: '🤖', label: 'AI 管理' }
  ]}
]

function doSearch() {
  const q = search.value.trim()
  if (!q) return
  search.value = ''
  router.push({ path: '/learn', query: { k: q } })
}

function logout() {
  api.logout().catch(() => {})
  auth.clear()
  location.href = '/login'
}
</script>

<template>
  <template v-if="!isPublic">
    <div class="topbar">
      <div class="topbar-inner">
        <div class="logo" @click="router.push(isTeacher ? '/admin' : '/')">
          <span class="logo-mark">跌</span>
          <span>防跌学堂</span>
        </div>
        <span class="slogan hide-md" v-if="!isAdmin">老年人跌倒预防与应急处置 · 岗课赛证融通</span>
        <span class="slogan hide-md" v-else style="color: var(--primary); font-weight: 600">教师管理后台</span>
        <div class="searchbox hide-sm" v-if="!isAdmin">
          🔍
          <input v-model="search" placeholder="搜一题 / 一个知识点，回车问 AI 老师" @keyup.enter="doSearch" />
        </div>
        <div class="topbar-right" style="margin-left: auto">
          <router-link v-if="isTeacher" to="/" class="back-student">{{ isAdmin ? '回学生端' : '进管理后台' }}</router-link>
          <div class="bell" title="错题本" @click="router.push('/wrong')" v-if="!isAdmin">
            🔔
            <span v-if="dueCount" class="dot">{{ dueCount }}</span>
          </div>
          <div class="userchip" @click="router.push(isTeacher ? '/admin' : '/mine')">
            <div class="avatar">{{ (auth.user?.name || '学')[0] }}</div>
            <div class="userchip-text">
              <div class="uname">{{ auth.user?.name }}</div>
              <div class="udept hide-md">{{ auth.user?.role === 'teacher' ? '教师' : auth.user?.student_no }}</div>
            </div>
          </div>
          <button class="btn sm dark" @click="logout">退出</button>
        </div>
      </div>
    </div>
    <template v-if="isAdmin">
      <div class="admin-wrap">
        <aside class="admin-side">
          <div class="side-head"><span class="logo-mark">跌</span> 管理后台</div>
          <template v-for="g in sideNav" :key="g.group">
            <div class="side-group">{{ g.group }}</div>
            <router-link v-for="it in g.items" :key="it.to" :to="it.to">
              <span class="ic">{{ it.ic }}</span>{{ it.label }}
            </router-link>
          </template>
        </aside>
        <main class="admin-main"><router-view /></main>
      </div>
    </template>
    <template v-else>
      <div class="navtabs">
        <div class="navtabs-inner">
          <router-link v-for="t in tabs" :key="t.to" :to="t.to">{{ t.label }}</router-link>
        </div>
      </div>
      <router-view />
    </template>
  </template>
  <router-view v-else />
</template>

<style scoped>
.back-student {
  font-size: 12.5px; color: var(--primary); background: var(--primary-light);
  padding: 5px 12px; border-radius: 8px; margin-right: 4px;
}
.back-student:hover { background: #fbd9d9; }
</style>