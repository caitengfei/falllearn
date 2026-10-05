<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, auth, DEMO_GUIDE } from './api'

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
  { to: '/kb', label: '知识库' },
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

// —— 评委演示引导弹窗（顶栏 ? 按钮）——
const guideOpen = ref(false)
function goGuide(g) {
  guideOpen.value = false
  if (g.to === '/login') {
    auth.clear()
    router.push('/login')
    return
  }
  if (g.ask) {
    router.push({ path: g.to, query: { ask: g.ask } })
    return
  }
  router.push(g.to)
}
</script>

<template>
  <template v-if="!isPublic">
    <div class="topbar">
      <div class="topbar-inner">
        <div class="logo" role="button" tabindex="0" aria-label="返回首页"
          @click="router.push(isTeacher ? '/admin' : '/')"
          @keyup.enter="router.push(isTeacher ? '/admin' : '/')">
          <span class="logo-mark">康</span>
          <span>康养智行</span>
        </div>
        <span class="slogan hide-md" v-if="!isAdmin">智慧养老“岗课赛证”融通智能体</span>
        <span class="slogan hide-md" v-else style="color: var(--primary-text); font-weight: 600">教师管理后台</span>
        <div class="searchbox hide-sm" v-if="!isAdmin">
          🔍
          <input v-model="search" placeholder="搜一题 / 一个知识点，回车问 AI 老师" @keyup.enter="doSearch" />
        </div>
        <div class="topbar-right" style="margin-left: auto">
          <router-link v-if="isTeacher" :to="isAdmin ? '/' : '/admin'" class="back-student">{{ isAdmin ? '回学生端' : '进管理后台' }}</router-link>
          <!-- 顶栏铃铛/问号已按教师反馈移除（2026-10-05）：错题提醒在练习页概览条，演示引导首访自动弹出 -->
          <div class="userchip" role="button" tabindex="0" aria-label="个人中心"
            @click="router.push(isTeacher ? '/admin' : '/mine')"
            @keyup.enter="router.push(isTeacher ? '/admin' : '/mine')">
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
          <!-- 侧栏标题：品牌与角色已在顶栏呈现（"康养智行 / 教师管理后台"），此处不再重复 logo 与"管理后台"字样 -->
          <div class="side-head">教学管理</div>
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

  <!-- 评委演示引导弹窗 -->
  <div v-if="guideOpen" class="gm-mask" @click.self="guideOpen = false">
    <div class="gm-box">
      <div class="gm-head">
        <div class="gm-title">🎓 演示体验路径</div>
        <button class="gm-close" @click="guideOpen = false">✕</button>
      </div>
      <div class="gm-sub">6 步看懂平台全流程 · 每一步都能直接点开</div>
      <div class="gm-steps">
        <div v-for="(g, i) in DEMO_GUIDE.student" :key="i" class="gm-step" role="button" tabindex="0"
          @click="goGuide(g)" @keyup.enter="goGuide(g)">
          <span class="gm-ic">{{ g.ic }}</span>
          <span class="gm-num">{{ i + 1 }}</span>
          <div class="gm-step-b">
            <b>{{ g.t }}</b>
            <span>{{ g.d }}</span>
          </div>
          <span class="gm-go">›</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.back-student {
  font-size: 12.5px; color: var(--primary-text); background: var(--primary-light);
  padding: 5px 12px; border-radius: 8px; margin-right: 4px;
}
.back-student:hover { background: #fbd9d9; }
/* —— 评委演示引导弹窗 —— */
.gm-mask { position: fixed; inset: 0; background: rgba(15,23,42,.45); z-index: 70; display: flex; align-items: center; justify-content: center; padding: 24px; }
.gm-box { background: #fff; border-radius: 16px; width: min(560px, 100%); max-height: 86vh; overflow-y: auto; padding: 18px 20px 14px; box-shadow: 0 18px 50px rgba(0,0,0,.25); }
.gm-head { display: flex; justify-content: space-between; align-items: center; }
.gm-title { font-size: 16px; font-weight: 700; }
.gm-close { border: none; background: #f1f5f9; width: 28px; height: 28px; border-radius: 8px; cursor: pointer; color: var(--text-2); }
.gm-close:hover { background: #e2e8f0; }
.gm-sub { font-size: 12px; color: var(--text-3); margin: 4px 0 12px; }
.gm-steps { display: flex; flex-direction: column; gap: 8px; }
.gm-step { display: flex; align-items: center; gap: 10px; padding: 10px 12px; border: 1px solid var(--line); border-radius: 12px; cursor: pointer; transition: all .12s; }
.gm-step:hover { border-color: var(--primary); background: #fff5f5; }
.gm-ic { font-size: 18px; }
.gm-num { font-size: 12px; font-weight: 700; color: var(--primary-text); background: var(--primary-light); border-radius: 6px; padding: 2px 7px; }
.gm-step-b { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.gm-step-b b { font-size: 13px; }
.gm-step-b span { font-size: 11.5px; color: var(--text-3); margin-top: 1px; }
.gm-go { font-size: 18px; color: var(--text-3); }
</style>