<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, clusterColor, DEMO_GUIDE } from '../../api'

const router = useRouter()
const data = ref(null)
const err = ref('')
const loading = ref(false)
const lbTab = ref('points')
const showReset = ref(false)

// —— 评委演示引导（教师端首访卡）——
const showGuide = ref(!localStorage.getItem('fl_guide_adm'))
function dismissGuide() {
  localStorage.setItem('fl_guide_adm', '1')
  showGuide.value = false
}
function goGuide(g) {
  router.push(g.to)
}

// —— 指标卡下钻 ——
const expanded = ref('') // 'active' | 'questions' | ''
const clusterQs = ref(null)
const hoursRef = ref(null)
let flashTimer = null

async function ensureClusterQs() {
  if (!clusterQs.value) {
    try {
      const r = await api.metaClusters()
      clusterQs.value = Array.isArray(r) ? r : (r.items || [])
    } catch (e) { clusterQs.value = [] }
  }
}
async function onCardClick(kind) {
  if (kind === 'active' || kind === 'questions') {
    if (expanded.value === kind) { expanded.value = ''; return }
    if (kind === 'questions') await ensureClusterQs()
    expanded.value = kind
  } else if (kind === 'students') {
    router.push('/admin/students')
  } else if (kind === 'asks') {
    router.push('/admin/stats?tab=students')
  } else if (kind === 'practices') {
    router.push('/admin/exams')
  } else if (kind === 'hours') {
    expanded.value = ''
    if (hoursRef.value) {
      hoursRef.value.scrollIntoView({ behavior: 'smooth', block: 'start' })
      hoursRef.value.classList.add('flash')
      clearTimeout(flashTimer)
      flashTimer = setTimeout(() => hoursRef.value && hoursRef.value.classList.remove('flash'), 1600)
    }
  }
}

async function load() {
  loading.value = true
  err.value = ''
  try {
    data.value = await api.statsOverview()
  } catch (e) {
    err.value = e.message
  }
  loading.value = false
}
onMounted(load)

const lb = computed(() => {
  if (!data.value) return []
  return lbTab.value === 'points' ? data.value.rank_points : lbTab.value === 'mastery' ? data.value.rank_mastery : data.value.rank_hours
})
const maxTrend = computed(() => Math.max(1, ...(data.value?.trend || []).map((t) => Math.max(t.points, 0))))

const toastMsg = ref('')
function toast(m) { toastMsg.value = m; setTimeout(() => (toastMsg.value = ''), 2400) }

async function doReset() {
  // 先确认再关弹窗（避免点「取消」弹窗已关、无法重开）
  if (!confirm('重置所有演示账号（S2026001-3）的学习痕迹并恢复基线？此操作不可撤销。')) return
  showReset.value = false
  try {
    await api.adminReset()
    await load()
    toast('重置完成')
  } catch (e) {
    alert(e.message)
  }
}
</script>

<template>
  <div class="page">
    <div style="display: flex; align-items: center; margin-bottom: 16px">
      <div style="font-size: 19px; font-weight: 700">数据总览</div>
      <span style="font-size: 12px; color: var(--text-3); margin-left: 10px">活跃 / 排行 / 学时 / 六簇分布</span>
      <div style="margin-left: auto; display: flex; gap: 8px">
        <button class="btn sm ghost" @click="load">{{ loading ? '刷新中…' : '↻ 刷新' }}</button>
        <button class="btn sm danger-ghost" @click="showReset = true">演示数据重置</button>
      </div>
    </div>

    <!-- 评委演示引导（教师端首访） -->
    <div v-if="showGuide" class="guide-card">
      <div class="gc-head">
        <div>
          <div class="gc-title">🎓 教师端演示路径 · 4 步</div>
          <div class="gc-sub">布置 → 统计 → 错题分析 → AI 管理</div>
        </div>
        <button class="gc-close" @click="dismissGuide">不再显示</button>
      </div>
      <div class="gc-grid">
        <div v-for="(g, i) in DEMO_GUIDE.teacher" :key="i" class="gc-step" @click="goGuide(g)">
          <span class="gc-ic">{{ g.ic }}</span>
          <span class="gc-num">{{ i + 1 }}</span>
          <div class="gc-step-b">
            <b>{{ g.t }}</b>
            <span>{{ g.d }}</span>
          </div>
          <span class="gc-go">›</span>
        </div>
      </div>
    </div>

    <div v-if="err" class="card" style="border-color: #fca5a5; color: #b91c1c; margin-bottom: 14px">加载失败：{{ err }} <button class="btn sm" style="margin-left: 12px" @click="load">重试</button></div>
    <div v-if="toastMsg" class="toast">{{ toastMsg }}</div>

    <template v-if="data">
      <!-- 核心指标（全部可下钻） -->
      <div class="mgrid c6" style="margin-bottom: 14px">
        <div class="mcard hero clickable" :class="{ on: expanded === 'active' }" @click="onCardClick('active')">
          <span class="hint">{{ expanded === 'active' ? '收起 ▴' : '明细 ▾' }}</span>
          <div class="mk">活跃人数（今日 / 7 日）</div>
          <div class="mv">{{ data.active.today }} <span style="font-size: 15px; opacity: .8">/ {{ data.active.week }}</span></div>
          <div class="ms">去重学生 · 签到/问答/练习</div>
        </div>
        <div class="mcard clickable" @click="onCardClick('students')">
          <span class="hint">管理 ↗</span>
          <div class="mk">在读学生</div><div class="mv">{{ data.cards.students }}</div><div class="ms">启用账号</div>
        </div>
        <div class="mcard clickable" :class="{ on: expanded === 'questions' }" @click="onCardClick('questions')">
          <span class="hint">{{ expanded === 'questions' ? '收起 ▴' : '分簇 ▾' }}</span>
          <div class="mk">题库规模</div><div class="mv">{{ data.cards.questions }}</div><div class="ms">含 AI 生成</div>
        </div>
        <div class="mcard clickable" @click="onCardClick('asks')">
          <span class="hint">画像 ↗</span>
          <div class="mk">AI 问答总量</div><div class="mv">{{ data.cards.asks }}</div><div class="ms">四栏格式问答</div>
        </div>
        <div class="mcard clickable" @click="onCardClick('practices')">
          <span class="hint">记录 ↗</span>
          <div class="mk">累计练习</div><div class="mv">{{ data.cards.practices }}</div><div class="ms">已交卷</div>
        </div>
        <div class="mcard clickable" @click="onCardClick('hours')">
          <span class="hint">表格 ▾</span>
          <div class="mk">累计学时</div><div class="mv">{{ data.cards.hours }}<span style="font-size: 13px"> h</span></div><div class="ms">平均掌握 {{ data.cards.avg_mastery }}%</div>
        </div>
      </div>

      <!-- 下钻面板：活跃明细 -->
      <div v-if="expanded === 'active'" class="card drill">
        <div class="card-title">活跃学生明细<span class="more" style="cursor: pointer" @click="expanded = ''">收起 ✕</span></div>
        <div class="mgrid c2">
          <div>
            <div style="font-size: 13px; font-weight: 600; margin-bottom: 8px">今日活跃（{{ data.active.today_list.length }} 人）</div>
            <div v-if="!data.active.today_list.length" style="color: var(--text-3); font-size: 13px; padding: 6px 0">今日暂无学生活跃</div>
            <div v-for="s in data.active.today_list" :key="'t' + s.student_no" class="drill-item">
              <span class="di-name">{{ s.name }}</span><span class="di-no">{{ s.student_no }}</span>
            </div>
          </div>
          <div>
            <div style="font-size: 13px; font-weight: 600; margin-bottom: 8px">近 7 日活跃（{{ data.active.week_list.length }} 人）</div>
            <div v-if="!data.active.week_list.length" style="color: var(--text-3); font-size: 13px; padding: 6px 0">近 7 日暂无学生活跃</div>
            <div v-for="s in data.active.week_list" :key="'w' + s.student_no" class="drill-item">
              <span class="di-name">{{ s.name }}</span><span class="di-no">{{ s.student_no }}</span>
            </div>
          </div>
        </div>
        <div style="font-size: 12px; color: var(--text-3); margin-top: 10px">活跃 = 签到 / AI 问答 / 练习交卷 / 学习行为，任一发生即计入</div>
      </div>

      <!-- 下钻面板：题库分簇 -->
      <div v-if="expanded === 'questions'" class="card drill">
        <div class="card-title">题库规模 · 六簇分布<span class="more" style="cursor: pointer" @click="expanded = ''">收起 ✕</span></div>
        <div class="mgrid c2" v-if="clusterQs">
          <div class="bar-row" v-for="c in clusterQs" :key="c.id">
            <div class="bl">{{ c.name }}</div>
            <div class="bt"><i :style="{ width: (c.qcount / Math.max(...clusterQs.map((x) => x.qcount), 1)) * 100 + '%', background: clusterColor(c.id) }"></i></div>
            <div class="bv">{{ c.qcount }} 题</div>
          </div>
          <div style="font-size: 12.5px; color: var(--text-2); line-height: 2; align-self: center">
            共 <b style="color: var(--text-1)">{{ data.cards.questions }}</b> 题，题型构成：
            <span v-for="(c, t) in data.qtypes" :key="t" style="margin-right: 10px">{{ t }} {{ c }}</span>
            新题可通过「AI 管理 → AI 出题」按知识簇生成入库，也可针对页面下方「班级弱项」定向补充。
          </div>
        </div>
        <div v-else style="color: var(--text-3); font-size: 13px; padding: 10px 0">加载簇分布中…</div>
      </div>

      <div class="mgrid c2" style="margin-bottom: 14px">
        <!-- 7 日积分趋势 -->
        <div class="card">
          <div class="card-title">近 7 日积分动态</div>
          <div class="chart-bars">
            <div class="cb" v-for="t in data.trend" :key="t.date">
              <div class="cv">{{ t.points }}</div>
              <div class="col" :style="{ height: (t.points / maxTrend) * 100 + '%' }"></div>
              <div class="cl">{{ t.date.slice(5) }}</div>
            </div>
          </div>
        </div>
        <!-- 六簇平均掌握度 -->
        <div class="card">
          <div class="card-title">六簇平均掌握度（%）</div>
          <div class="bar-row" v-for="c in data.clusters" :key="c.cluster">
            <div class="bl">{{ c.name }}</div>
            <div class="bt"><i :style="{ width: c.level + '%', background: clusterColor(c.cluster) }"></i></div>
            <div class="bv">{{ c.level }}%</div>
          </div>
        </div>
      </div>

      <div class="mgrid c2" style="margin-bottom: 14px">
        <!-- 排行榜 -->
        <div class="card">
          <div class="card-title">排行榜
            <span class="pills" style="margin: 0 0 0 auto; margin-left: auto">
              <span class="pill sm" :class="{ on: lbTab === 'points' }" @click="lbTab = 'points'">积分</span>
              <span class="pill sm" :class="{ on: lbTab === 'mastery' }" @click="lbTab = 'mastery'">掌握度</span>
              <span class="pill sm" :class="{ on: lbTab === 'hours' }" @click="lbTab = 'hours'">学时</span>
            </span>
          </div>
          <table class="atable">
            <thead><tr><th style="width: 46px">名次</th><th>学生</th><th style="width: 90px; text-align: right">数值</th></tr></thead>
            <tbody>
              <tr v-for="r in lb" :key="r.student_no">
                <td>{{ ['🥇', '🥈', '🥉'][r.rank - 1] || r.rank }}</td>
                <td>{{ r.name }} <span style="color: var(--text-3); font-size: 12px">{{ r.student_no }}</span></td>
                <td class="num" style="text-align: right; font-weight: 700">{{ r.value }}</td>
              </tr>
              <tr v-if="!lb.length"><td colspan="3" style="color: var(--text-3); text-align: center; padding: 18px">暂无学生数据</td></tr>
            </tbody>
          </table>
        </div>
        <!-- 题型 + 班级弱项 -->
        <div>
          <div class="card" style="margin-bottom: 14px">
            <div class="card-title">题库题型分布</div>
            <div class="bar-row" v-for="(c, t) in data.qtypes" :key="t" style="margin-bottom: 8px">
              <div class="bl">{{ t }}</div>
              <div class="bt"><i :style="{ width: (c / Math.max(...Object.values(data.qtypes), 1)) * 100 + '%', background: '#64748b' }"></i></div>
              <div class="bv">{{ c }} 题</div>
            </div>
          </div>
          <div class="card">
            <div class="card-title">班级弱项（答错率 Top）</div>
            <table class="atable">
              <tbody>
                <tr v-for="w in data.weak_clusters.slice(0, 5)" :key="w.cluster">
                  <td>{{ w.name }}</td>
                  <td style="color: var(--text-3); font-size: 12px">{{ w.n }} 次作答</td>
                  <td class="num" style="text-align: right; font-weight: 700" :style="{ color: w.rate > 50 ? 'var(--primary)' : 'var(--text-2)' }">{{ w.rate }}%</td>
                </tr>
                <tr v-if="!data.weak_clusters.length"><td style="color: var(--text-3); text-align: center; padding: 18px">暂无作答数据</td></tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- 学时统计 -->
      <div class="card" ref="hoursRef">
        <div class="card-title">学时统计（按学生）<span style="font-size: 11px; color: var(--text-3); font-weight: 400; margin-left: 8px">AI 问答按实际耗时 · 练习按交卷时长 · 复习按次</span></div>
        <table class="atable">
          <thead><tr><th style="width: 50px">#</th><th>学生</th><th>学号</th><th style="width: 110px; text-align: right">学时</th></tr></thead>
          <tbody>
            <tr v-for="(h, i) in data.hours" :key="h.student_no">
              <td>{{ i + 1 }}</td>
              <td>{{ h.name }}</td>
              <td style="color: var(--text-3)">{{ h.student_no }}</td>
              <td class="num" style="text-align: right; font-weight: 700">{{ h.hours }} 学时</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
    <div v-else-if="!err" class="card" style="color: var(--text-3)">加载中…</div>

    <!-- 重置确认 -->
    <div v-if="showReset" class="mask" @click.self="showReset = false">
      <div class="modal">
        <div class="modal-h">演示数据重置<span class="more" @click="showReset = false">✕</span></div>
        <p style="font-size: 13.5px; color: var(--text-2); line-height: 1.9">
          将清空 3 个演示学生（S2026001-3）的积分、掌握度、练习/模拟考记录、错题、对话、学时，并删除他们生成的考卷，把 S2026001 恢复到标准演示基线（128 分 / 3 道错题 / 一条四栏问答），S2026001-3 与 T2026 的密码将重置为 123456。其余账号、题库（含 AI 生成题）与管理数据不受影响。
        </p>
        <div style="display: flex; gap: 10px; margin-top: 18px">
          <button class="btn sm" @click="doReset">确认重置</button>
          <button class="btn sm ghost" @click="showReset = false">取消</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* —— 评委演示引导卡（教师端首访）—— */
.guide-card {
  background: linear-gradient(120deg, #fff5f5, #ffffff 55%);
  border: 1px solid #fbd9d9; border-radius: 14px; padding: 14px 16px; margin-bottom: 14px;
}
.gc-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
.gc-title { font-size: 14.5px; font-weight: 700; color: #9f1239; }
.gc-sub { font-size: 11.5px; color: var(--text-3); margin-top: 2px; }
.gc-close {
  border: none; background: #fff; color: var(--text-2); font-size: 11.5px;
  border: 1px solid var(--line); border-radius: 8px; padding: 5px 10px; cursor: pointer;
}
.gc-close:hover { border-color: var(--primary); color: var(--primary); }
.gc-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; margin-top: 12px; }
.gc-step {
  display: flex; align-items: center; gap: 8px; background: #fff; min-width: 0;
  border: 1px solid var(--line); border-radius: 11px; padding: 9px 11px; cursor: pointer; transition: all .12s;
}
.gc-step:hover { border-color: var(--primary); box-shadow: 0 2px 10px rgba(228,57,60,.08); transform: translateY(-1px); }
.gc-ic { font-size: 17px; }
.gc-num { font-size: 11px; font-weight: 700; color: var(--primary); background: var(--primary-light); border-radius: 6px; padding: 1px 6px; }
.gc-step-b { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.gc-step-b b { font-size: 12.5px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.gc-step-b span { font-size: 11px; color: var(--text-3); margin-top: 1px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.gc-go { font-size: 16px; color: var(--text-3); }
@media (max-width: 1100px) { .gc-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 640px) { .gc-grid { grid-template-columns: minmax(0, 1fr); } }
/* 指标卡：可下钻 */
.mcard.clickable { cursor: pointer; position: relative; transition: transform .15s ease, box-shadow .15s ease, border-color .15s ease; }
.mcard.clickable:hover { transform: translateY(-2px); box-shadow: 0 6px 16px rgba(15, 23, 42, .10); border-color: #cbd5e1; }
.mcard.clickable.on { border-color: var(--primary); box-shadow: 0 0 0 2px rgba(59, 130, 246, .18); }
.mcard.hero.clickable:hover { box-shadow: 0 8px 20px rgba(228, 57, 60, .35); border-color: transparent; }
.mcard.hero.clickable.on { box-shadow: 0 0 0 3px rgba(255, 255, 255, .55); }
.hint { position: absolute; top: 10px; right: 12px; font-size: 11px; color: var(--text-3); opacity: .75; transition: color .15s ease, opacity .15s ease; }
.mcard.clickable:hover .hint { color: var(--primary); opacity: 1; }
.mcard.hero.clickable .hint { color: rgba(255, 255, 255, .85); }
.mcard.hero.clickable:hover .hint { color: #fff; }

/* 下钻面板 */
.drill { margin-bottom: 14px; animation: drillIn .18s ease; }
@keyframes drillIn { from { opacity: 0; transform: translateY(-6px); } to { opacity: 1; transform: none; } }
.drill-item { display: flex; align-items: center; gap: 10px; padding: 7px 2px; border-bottom: 1px dashed var(--line); font-size: 13.5px; }
.drill-item:last-child { border-bottom: none; }
.di-name { font-weight: 600; }
.di-no { color: var(--text-3); font-size: 12px; }

/* 学时表高亮闪烁（点击「累计学时」卡后） */
.flash { animation: cardFlash 1.6s ease; }
@keyframes cardFlash {
  0% { box-shadow: 0 0 0 0 rgba(59, 130, 246, .55); border-color: var(--primary); }
  40% { box-shadow: 0 0 0 6px rgba(59, 130, 246, .28); }
  100% { box-shadow: 0 0 0 0 rgba(59, 130, 246, 0); }
}
</style>