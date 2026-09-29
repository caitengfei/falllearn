<script setup>
import { computed, onMounted, ref } from 'vue'
import { api, CLUSTERS, clusterName, clusterColor } from '../api'

const data = ref(null)
const err = ref('')
const ai = ref({ text: '', loading: false, error: '' })

async function load() {
  err.value = ''
  try {
    data.value = await api.quizReport()
  } catch (e) {
    err.value = e.message
  }
}
onMounted(load)

async function runAi() {
  if (ai.value.loading) return
  ai.value = { text: '', loading: true, error: '' }
  try {
    const r = await api.quizReportAi()
    ai.value.text = r.analysis
  } catch (e) {
    ai.value.error = e.message
  } finally {
    ai.value.loading = false
  }
}

// ---------- 得分趋势折线图 ----------
const W = 560, H = 220, PL = 40, PR = 18, PT = 18, PB = 30
const trend = computed(() => data.value?.score_trend || [])
const trendPts = computed(() => {
  const pts = trend.value
  const pw = W - PL - PR, ph = H - PT - PB
  if (!pts.length) return []
  const x = (i) => (pts.length === 1 ? PL + pw / 2 : PL + (pw * i) / (pts.length - 1))
  const y = (s) => PT + ((100 - s) / 100) * ph
  return pts.map((p, i) => ({ x: x(i), y: y(p.score), s: p.score, i }))
})
const trendLine = computed(() => trendPts.value.map((p) => `${p.x},${p.y}`).join(' '))
const gridY = [0, 25, 50, 75, 100].map((v) => ({ v, y: PT + ((100 - v) / 100) * (H - PT - PB) }))

// ---------- 14 天活跃柱状图 ----------
const act = computed(() => data.value?.activity || [])
const maxMin = computed(() => Math.max(1, ...act.value.map((a) => a.minutes)))
const actBars = computed(() => {
  const pw = W - PL - PR, ph = H - PT - PB
  const bw = (pw / 14) * 0.58
  return act.value.map((a, i) => {
    const h = (a.minutes / maxMin.value) * ph
    return { x: PL + (pw / 14) * i + (pw / 14 - bw) / 2, y: PT + ph - h, w: bw, h, m: a.minutes, d: a.day }
  })
})

const worst = computed(() => {
  const w = (data.value?.wrong_by_cluster || []).filter((x) => x.mastery < 60)
  return w.length ? w[0].cluster : ''
})

function fmtAt(ts) {
  const d = new Date(ts * 1000)
  return `${d.getMonth() + 1}/${d.getDate()}`
}
</script>

<template>
  <div class="page" v-if="data">
    <div class="rhead">
      <div>
        <div class="rt">我的学习报告</div>
        <div class="rs">近 14 天学习数据 · 每日自动更新</div>
      </div>
    </div>

    <div class="mgrid c4" style="margin-bottom: 14px">
      <div class="mcard"><div class="mk">累计完成练习</div><div class="mv">{{ data.practice_count }}</div><div class="ms">日常 / 模拟 / 布置</div></div>
      <div class="mcard"><div class="mk">平均得分</div><div class="mv" :style="{ color: data.avg_score >= 80 ? '#15803d' : data.avg_score != null ? '#b45309' : '' }">{{ data.avg_score ?? '—' }}</div><div class="ms">满分 100</div></div>
      <div class="mcard"><div class="mk">近 14 天学时</div><div class="mv">{{ data.total_hours_14d }}</div><div class="ms">练习 + 复习</div></div>
      <div class="mcard hero"><div class="mk">错题本</div><div class="mv">{{ data.wrong_active + data.wrong_mastered }}</div><div class="ms">待巩固 {{ data.wrong_active }} · 已掌握 {{ data.wrong_mastered }}</div></div>
    </div>

    <div class="rgrid">
      <div class="card">
        <div class="card-title">得分趋势</div>
        <svg v-if="trendPts.length" :viewBox="`0 0 ${W} ${H}`" class="chart">
          <g v-for="g in gridY" :key="g.v">
            <line :x1="PL" :x2="W - PR" :y1="g.y" :y2="g.y" stroke="#eef0f3" />
            <text :x="PL - 8" :y="g.y + 4" text-anchor="end" font-size="10" fill="#9ca3af">{{ g.v }}</text>
          </g>
          <polyline :points="trendLine" fill="none" stroke="#e4393c" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round" />
          <g v-for="p in trendPts" :key="p.i">
            <circle :cx="p.x" :cy="p.y" r="4" fill="#fff" stroke="#e4393c" stroke-width="2" />
            <text :x="p.x" :y="p.y - 10" text-anchor="middle" font-size="11" font-weight="700" fill="#374151">{{ p.s }}</text>
            <text :x="p.x" :y="H - 10" text-anchor="middle" font-size="10" fill="#9ca3af">{{ fmtAt(trend[p.i].at) }}</text>
          </g>
        </svg>
        <div v-else class="empty">还没有完成过练习 —— 去「练习考试」完成第一组，趋势图就会长出来</div>
      </div>

      <div class="card">
        <div class="card-title">近 14 天学习活跃（分钟）</div>
        <svg :viewBox="`0 0 ${W} ${H}`" class="chart">
          <line :x1="PL" :x2="W - PR" :y1="H - PB" :y2="H - PB" stroke="#eef0f3" />
          <g v-for="(b, i) in actBars" :key="i">
            <rect :x="b.x" :y="b.y" :width="b.w" :height="Math.max(b.h, b.m > 0 ? 2 : 0)" rx="2"
                  :fill="b.m > 0 ? '#3b82f6' : '#eef0f3'" />
            <text v-if="b.m > 0" :x="b.x + b.w / 2" :y="b.y - 5" text-anchor="middle" font-size="9" fill="#6b7280">{{ b.m }}</text>
            <text :x="b.x + b.w / 2" :y="H - 10" text-anchor="middle" font-size="9" fill="#9ca3af">{{ b.d.slice(3) }}</text>
          </g>
        </svg>
      </div>
    </div>

    <div class="card" style="margin-top: 14px">
      <div class="card-title-row">
        <div class="card-title" style="margin: 0">AI 学习分析</div>
        <button class="btn sm" :disabled="ai.loading || !data.practice_count && !data.wrong_active" @click="runAi">
          <span v-if="ai.loading" class="spin"></span>{{ ai.loading ? 'AI 分析中…（约 10 秒）' : ai.text ? '重新生成' : '生成 AI 分析' }}
        </button>
      </div>
      <p v-if="ai.text" class="aitext">{{ ai.text }}</p>
      <p v-else-if="ai.error" class="aierr">生成失败：{{ ai.error }} <button class="btn sm ghost" @click="runAi">重试</button></p>
      <p v-else class="aisub">让 AI 导师基于你的练习得分、错题分布与知识点正确率，生成一段个性化诊断与学习建议（约 10 秒）。</p>
    </div>

    <div class="card" style="margin-top: 14px">
      <div class="card-title">错题知识点分布</div>
      <div v-if="data.wrong_by_cluster.length">
        <div v-for="w in data.wrong_by_cluster" :key="w.cluster" class="wrow">
          <span class="wtag" :style="{ background: clusterColor(w.cluster) + '14', color: clusterColor(w.cluster) }">{{ clusterName(w.cluster) }}</span>
          <div class="bar-row" style="margin: 0; flex: 1">
            <div class="bt" style="flex: 1; display: flex; height: 12px">
              <i style="background: #ef4444" :style="{ width: (w.active / (w.total || 1)) * 100 + '%' }"></i>
              <i style="background: #22c55e" :style="{ width: (w.mastered / (w.total || 1)) * 100 + '%' }"></i>
            </div>
            <div class="bv" style="min-width: 110px">待巩固 {{ w.active }} · 已掌握 {{ w.mastered }}</div>
          </div>
          <span class="tag" :class="w.mastery >= 60 ? 'green' : 'red'">掌握度 {{ w.mastery }}%</span>
        </div>
        <div class="wlegend"><i style="background:#ef4444"></i>待巩固 <i style="background:#22c55e; margin-left: 10px"></i>已掌握（连对 2 次）</div>
      </div>
      <div v-else class="empty">错题本还是空的 —— 继续保持，或者去「练习考试」挑战一下薄弱知识点</div>

      <template v-if="data.correct_rate.length">
        <div class="subhead">各知识点正确率（全部作答）</div>
        <div v-for="c in data.correct_rate" :key="c.cluster" class="wrow">
          <span class="wtag" :style="{ background: clusterColor(c.cluster) + '14', color: clusterColor(c.cluster) }">{{ clusterName(c.cluster) }}</span>
          <div class="bar-row" style="margin: 0; flex: 1">
            <div class="bt" style="flex: 1"><i :style="{ width: c.rate + '%', background: c.rate >= 80 ? '#22c55e' : c.rate >= 60 ? '#f5a623' : '#ef4444' }"></i></div>
            <div class="bv">{{ c.rate }}% · {{ c.n }} 题</div>
          </div>
        </div>
      </template>
    </div>

    <div class="card" style="margin-top: 14px" v-if="worst">
      <div class="card-title">薄弱点提示</div>
      <p class="tip">当前掌握度最低的知识点是「<b>{{ clusterName(worst) }}</b>」—— 建议到「练习考试 · 日常练习」抽一组该知识点的题目，或用「学习中心」的 AI 老师追问它的要点。</p>
    </div>
  </div>
  <div class="page" v-else>
    <div v-if="err" class="card" style="border-color: #fca5a5; color: #b91c1c">加载失败：{{ err }} <button class="btn sm" style="margin-left: 12px" @click="load">重试</button></div>
    <div v-else class="card" style="color: var(--text-3)">加载中…</div>
  </div>
</template>

<style scoped>
.rhead { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
.rt { font-size: 19px; font-weight: 700; }
.rs { font-size: 12px; color: var(--text-3); margin-top: 2px; }
.mgrid.c4 { grid-template-columns: repeat(4, 1fr); }
.rgrid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.chart { width: 100%; height: auto; display: block; }
.empty { color: var(--text-3); font-size: 13px; padding: 26px 10px; text-align: center; }
.card-title-row { display: flex; justify-content: space-between; align-items: center; }
.aitext { font-size: 13.5px; line-height: 1.85; color: var(--text-1); background: #f7f8fa; border-radius: 10px; padding: 12px 14px; margin: 10px 0 4px; }
.aierr { color: #b91c1c; font-size: 13px; margin: 10px 0 4px; display: flex; align-items: center; gap: 6px; }
.aisub { color: var(--text-3); font-size: 12.5px; margin: 8px 0 4px; }
.spin { display: inline-block; width: 12px; height: 12px; border: 2px solid rgba(255,255,255,.4); border-top-color: #fff; border-radius: 50%; animation: sp .7s linear infinite; margin-right: 5px; vertical-align: -2px; }
@keyframes sp { to { transform: rotate(360deg); } }
.wrow { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
.wtag { font-size: 12px; font-weight: 700; padding: 3px 10px; border-radius: 6px; min-width: 74px; text-align: center; }
.bv { font-size: 12px; color: var(--text-2); min-width: 90px; text-align: right; }
.wlegend { font-size: 11.5px; color: var(--text-3); margin: 2px 0 4px; display: flex; align-items: center; }
.wlegend i { width: 10px; height: 10px; border-radius: 3px; display: inline-block; margin-right: 4px; }
.subhead { font-size: 12.5px; font-weight: 700; color: var(--text-2); margin: 16px 0 10px; }
.tip { font-size: 13px; color: var(--text-2); line-height: 1.8; margin: 4px 0; }
@media (max-width: 900px) {
  .mgrid.c4 { grid-template-columns: repeat(2, 1fr); }
  .rgrid { grid-template-columns: 1fr; }
}
/* 窄屏：错题分布行改为两行（标签+掌握度一行，进度条整行），避免 390px 挤压 */
@media (max-width: 640px) {
  .wrow { flex-wrap: wrap; }
  .wrow .bar-row { flex-basis: 100%; order: 3; }
  .wrow .tag { margin-left: auto; }
}
</style>