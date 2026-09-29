<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, auth, clusterName, clusterColor } from '../api'

const route = useRoute()
const router = useRouter()
const menu = ref(['mock', 'teacher', 'retrain'].includes(route.query.menu) ? route.query.menu : 'daily')
const pill = ref('all')
const tasks = ref([])
const assignments = ref([])
const loading = ref(null)
const summary = ref({ practice_count: 0, last_score: null, wrong_active: 0 })

const menuItems = [
  { id: 'daily', label: '日常练习', ic: '✏' },
  { id: 'mock', label: '12 分钟模拟考', ic: '⏱' },
  { id: 'teacher', label: '教师布置', ic: '📋' },
  { id: 'retrain', label: '错题重答', ic: '📕' }
]

function buildTasks() {
  const s = summary.value
  return [
    {
      id: 'daily-1', menu: 'daily', title: '今日练习 · 按薄弱点组卷（10 题）',
      tag: ['针对性·薄弱簇优先', '难度自适应', '不限时'], color: '#e4393c', ic: '✏',
      status: 'ongoing', badge: s.practice_count ? '已完成 ' + s.practice_count + ' 组' : '未开始', canStart: true
    },
    {
      id: 'mock-1', menu: 'mock', title: '12 分钟理论模拟考 · 跌倒风险与急救',
      tag: ['限时 12 分钟', '10 题 100 分', '对标竞赛题型'], color: '#f5a623', ic: '⏱',
      status: 'todo', badge: '未参加', canStart: true, isMock: true
    }
  ]
}

const visible = computed(() => {
  let ts
  if (menu.value === 'teacher') {
    ts = assignments.value.map((a) => {
      const clusters = (a.clusters && a.clusters.length ? a.clusters.map(clusterName) : ['综合']).join(' · ')
      const due = a.due_at ? '截止 ' + new Date(a.due_at * 1000).toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' }) : '长期有效'
      const tag = [clusters, a.n + ' 题', a.minutes ? a.minutes + ' 分钟限时' : '不限时', due]
      const base = {
        id: 'asg-' + a.exam_id, menu: 'teacher', title: a.title,
        tag, color: '#2563eb', ic: '📋', exam_id: a.exam_id, attempt_id: a.attempt_id
      }
      if (a.status === 'done') return { ...base, status: 'done', badge: '已完成 ' + a.score + ' 分', canReview: true }
      if (a.status === 'open') return { ...base, status: 'ongoing', badge: '进行中', canStart: true }
      if (a.status === 'overdue') return { ...base, status: 'done', badge: '已截止', canReview: false }
      return { ...base, status: 'todo', badge: '待完成', canStart: true }
    })
  } else if (menu.value === 'retrain') {
    ts = [
      {
        id: 'retrain-1', title: '错题重答 · 待复习错题',
        tag: [`待复习 ${summary.value.wrong_active} 题`, '间隔复习 次日→第3天'], color: '#ef4444', ic: '📕',
        status: summary.value.wrong_active ? 'ongoing' : 'done',
        badge: summary.value.wrong_active ? '有错题待复习' : '全部复习完', canGoWrong: true
      }
    ]
  } else {
    ts = tasks.value.filter((t) => t.menu === menu.value)
  }
  if (pill.value === 'todo') ts = ts.filter((t) => t.status === 'todo')
  if (pill.value === 'ongoing') ts = ts.filter((t) => t.status === 'ongoing')
  if (pill.value === 'done') ts = ts.filter((t) => t.status === 'done')
  return ts
})

const err = ref('')
async function load() {
  tasks.value = buildTasks()
  err.value = ''
  try {
    const [s] = await Promise.all([api.quizSummary()])
    summary.value = s
    tasks.value = buildTasks()
  } catch (e) {
    err.value = e.message // 原为静默：统计恒为 0 且无提示
  }
  if (menu.value === 'teacher') loadAssignments()
}
async function loadAssignments() {
  try {
    assignments.value = (await api.quizAssignments()).items || []
  } catch (e) {
    assignments.value = []
    err.value = e.message
  }
}
watch(menu, (m) => { if (m === 'teacher') loadAssignments() })
onMounted(load)

async function start(t) {
  if (t.canGoWrong) {
    router.push('/wrong')
    return
  }
  loading.value = t.id
  try {
    const r = await api.quizStart(t.isMock ? 'mock' : 'daily', t.exam_id || 0)
    sessionStorage.setItem('exam_items', JSON.stringify(r.items))
    sessionStorage.setItem('exam_kind', r.kind || 'daily')
    sessionStorage.setItem('exam_title', r.title || '')
    sessionStorage.setItem('exam_time_limit', String(r.time_limit || 0))
    router.push('/exam/' + r.attempt_id)
  } catch (e) {
    alert('开卷失败：' + e.message)
  } finally {
    loading.value = null
  }
}

function viewResult(t) {
  sessionStorage.setItem('exam_review', String(t.attempt_id))
  router.push('/exam/' + t.attempt_id)
}
</script>

<template>
  <div class="page">
    <div v-if="err" class="card" style="border-color: #fca5a5; color: #b91c1c; margin-bottom: 12px">
      数据加载失败：{{ err }} <button class="btn sm" style="margin-left: 12px" @click="load">重试</button>
    </div>
    <div class="practice-grid">
      <!-- 左竖排菜单 -->
      <div class="card" style="padding: 10px">
        <div
          v-for="m in menuItems" :key="m.id"
          class="menu-item" :class="{ on: menu === m.id, off: m.off }"
          @click="!m.off && (menu = m.id)"
        >
          <span>{{ m.ic }}</span> {{ m.label }}
          <span v-if="m.off" class="off-tag">即将上线</span>
        </div>
      </div>

      <div>
        <div class="pstat-row">
          <div class="pstat"><div class="v mono">{{ summary.practice_count }}</div><div class="k">已完成组数</div></div>
          <div class="pstat"><div class="v mono">{{ summary.last_score ?? '—' }}</div><div class="k">最近得分</div></div>
          <div class="pstat"><div class="v mono">{{ summary.avg_score ?? '—' }}</div><div class="k">平均得分</div></div>
          <div class="pstat warn" @click="menu = 'retrain'"><div class="v mono">{{ summary.wrong_active }}</div><div class="k">待复习错题 ›</div></div>
        </div>
        <div class="pills">
          <span class="pill" :class="{ on: pill === 'all' }" @click="pill = 'all'">全部</span>
          <span class="pill" :class="{ on: pill === 'todo' }" @click="pill = 'todo'">未开始</span>
          <span class="pill" :class="{ on: pill === 'ongoing' }" @click="pill = 'ongoing'">进行中</span>
          <span class="pill" :class="{ on: pill === 'done' }" @click="pill = 'done'">已完成</span>
        </div>

        <div v-for="t in visible" :key="t.id" class="card" style="display: flex; gap: 16px; align-items: center; margin-bottom: 12px">
          <div class="rthumb" :style="{ background: t.color, width: '110px', height: '74px', fontSize: '26px', position: 'relative' }">
            {{ t.ic }}
            <span v-if="t.badge" class="badge-corner" :class="{ gold: t.status === 'todo' && t.badge === '未参加', green: t.status === 'done' }">{{ t.badge }}</span>
          </div>
          <div style="flex: 1; min-width: 0">
            <div class="rtitle" style="font-size: 15px">{{ t.title }}</div>
            <div style="margin-top: 7px">
              <span v-for="g in t.tag" :key="g" class="tag" :class="{ red: g.includes('针对性') || g.includes('限时'), gold: g.includes('对标') }">{{ g }}</span>
            </div>
            <div style="font-size: 12px; color: var(--text-3); margin-top: 7px" class="mono" v-if="t.menu === 'teacher'">
              教师已布置 · 完成后计入学习记录与班级统计
            </div>
          </div>
          <button v-if="t.canStart" class="btn sm" :disabled="loading === t.id" @click="start(t)">
            {{ loading === t.id ? '开卷中…' : (t.menu === 'teacher' && t.status === 'ongoing' ? '继续作答' : '开始') }}
          </button>
          <button v-else-if="t.canGoWrong" class="btn sm" @click="start(t)">去复习</button>
          <button v-else-if="t.canReview" class="btn sm ghost" @click="viewResult(t)">查看成绩</button>
        </div>
        <div v-if="!visible.length" class="card empty">{{ menu === 'teacher' ? '老师还没有布置练习 · 先去「日常练习」练一组吧' : '该分类下暂无任务' }}</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.practice-grid { display: grid; grid-template-columns: 170px 1fr; gap: 16px; align-items: start; }
.pstat-row { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; margin-bottom: 12px; }
.pstat { background: #fff; border: 1px solid var(--line); border-radius: 12px; padding: 10px 14px; }
.pstat .v { font-size: 19px; font-weight: 700; }
.pstat .k { font-size: 11.5px; color: var(--text-3); margin-top: 2px; }
.pstat.warn { cursor: pointer; transition: all .12s; }
.pstat.warn .v { color: var(--primary-text); }
.pstat.warn:hover { border-color: var(--primary); box-shadow: 0 2px 8px rgba(228,57,60,.10); }
@media (max-width: 640px) {
  .practice-grid { grid-template-columns: 1fr; }
  .menu-item { width: fit-content; }
  .pstat-row { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
.menu-item {
  padding: 10px 14px; border-radius: 8px; font-size: 13.5px; color: var(--text-2);
  cursor: pointer; display: flex; gap: 8px; align-items: center; margin-bottom: 4px;
}
.menu-item:hover { background: var(--bg); }
.menu-item.on { background: var(--primary-light); color: var(--primary-text); font-weight: 600; box-shadow: inset 3px 0 0 var(--primary); }
.menu-item.off { opacity: .55; cursor: not-allowed; }
.off-tag { margin-left: auto; font-size: 10px; background: var(--bg); color: var(--text-3); border-radius: 6px; padding: 1px 6px; }
.rthumb { border-radius: 8px; flex-shrink: 0; display: flex; align-items: center; justify-content: center; color: #fff; }
.badge-corner { position: absolute; top: 0; left: 0; background: #f5a623; color: #fff; font-size: 10px; padding: 2px 7px; border-radius: 0 0 7px 0; }
</style>