<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import { api, auth, clusterName, clusterColor } from '../api'

const route = useRoute()
const router = useRouter()
const items = ref(JSON.parse(sessionStorage.getItem('exam_items') || '[]'))
const kind = ref(sessionStorage.getItem('exam_kind') || 'daily')
const timeLimit = ref(parseInt(sessionStorage.getItem('exam_time_limit') || '0', 10))
const cur = ref(0)
const answers = ref(JSON.parse(sessionStorage.getItem('exam_answers') || '{}'))
const picked = ref('')
const submitted = ref(false)
const submitBusy = ref(false)
const result = ref(null)
const left = ref(timeLimit.value) // 剩余秒数
let tick = null

const title = computed(() =>
  kind.value === 'mock' ? '理论模拟考 · 跌倒风险与急救'
    : kind.value === 'teacher' ? (sessionStorage.getItem('exam_title') || '教师布置')
    : '日常练习 · 按薄弱点组卷')
const curItem = computed(() => items.value[cur.value] || null)

function persist() {
  sessionStorage.setItem('exam_answers', JSON.stringify(answers.value))
}

function choose(l) {
  if (!curItem.value || submitted.value) return
  if (curItem.value.type === '多选') {
    const set = new Set(picked.value)
    if (set.has(l)) set.delete(l)
    else set.add(l)
    picked.value = [...set].sort().join('')
  } else {
    picked.value = picked.value === l ? '' : l
  }
}

function go(d) {
  if (submitted.value) return
  cur.value = Math.min(Math.max(cur.value + d, 0), items.value.length - 1)
  picked.value = answers.value[String(curItem.value?.question_id)] || ''
}
function jump(i) {
  if (submitted.value) return
  cur.value = i
  picked.value = answers.value[String(curItem.value?.question_id)] || ''
}

function next() {
  const it = curItem.value
  if (!it || !picked.value) return
  answers.value[String(it.question_id)] = picked.value
  persist()
  if (cur.value < items.value.length - 1) go(1)
}
function prev() {
  answers.value[String(curItem.value?.question_id)] = picked.value
  persist()
  if (cur.value > 0) go(-1)
}

async function submit(silent = false) {
  // submitBusy 防连点：评委现场最怕「点了没反应又点一次」造成的重复提交
  if (submitted.value || submitBusy.value || !items.value.length) return
  if (!silent && !confirm(`还有 ${items.value.filter((it) => !answers.value[String(it.question_id)]).length} 题未作答，确定交卷？`)) return
  submitBusy.value = true
  stopTick()
  try {
    const r = await api.quizSubmit(Number(route.params.attemptId), answers.value)
    result.value = r
    submitted.value = true
    sessionStorage.removeItem('exam_items')
    sessionStorage.removeItem('exam_kind')
    sessionStorage.removeItem('exam_time_limit')
    sessionStorage.removeItem('exam_answers')
  } catch (e) {
    if (!silent) alert('交卷失败：' + e.message)
    else startTick() // 自动交卷失败：恢复倒计时（学生可手动再交）
  } finally {
    submitBusy.value = false
  }
}

function startTick() {
  if (!timeLimit.value) return
  tick = setInterval(() => {
    left.value -= 1
    if (left.value <= 0) {
      stopTick()
      submit(true) // 到时自动交卷
    }
  }, 1000)
}
function stopTick() {
  if (tick) clearInterval(tick)
  tick = null
}
const mmss = computed(() => {
  const s = Math.max(0, left.value)
  return String(Math.floor(s / 60)).padStart(2, '0') + ':' + String(s % 60).padStart(2, '0')
})

// 刷新恢复
onMounted(async () => {
  const reviewId = sessionStorage.getItem('exam_review')
  if (reviewId) {
    sessionStorage.removeItem('exam_review')
    try {
      result.value = await api.quizResult(Number(reviewId))
      submitted.value = true
    } catch (e) {
      alert('加载成绩失败：' + e.message)
    }
    return
  }
  if (!items.value.length) return // 无题：模板显示空态
  picked.value = answers.value[String(curItem.value?.question_id)] || ''
  startTick()
  window.addEventListener('beforeunload', warnLeave)
})
function warnLeave(e) {
  if (submitted.value || !items.value.length) return
  e.preventDefault()
  e.returnValue = ''
}
onBeforeRouteLeave(() => {
  if (submitted.value || !items.value.length) return true
  return confirm('答题尚未提交，确定离开吗？（作答已暂存在本标签页，可回来继续）')
})
onBeforeUnmount(() => {
  stopTick()
  window.removeEventListener('beforeunload', warnLeave)
})

function weakAgain() {
  const ws = Object.entries(result.value?.per_cluster || {})
    .filter(([, v]) => (v.total || 0) - (v.correct || 0) > 0)
    .map(([k]) => k)
  router.push(ws.length ? { path: '/learn', query: { cluster: ws[0] } } : '/practice')
}

/* —— 成绩页：逐题对错与讲解 —— */
const openQ = ref({})
const onlyWrong = ref(false)
function toggleQ(i) { openQ.value[i] = !openQ.value[i] }
function toggleAll() {
  const ids = filteredDetail.value.map((_, i) => i)
  const anyClosed = ids.some((i) => !openQ.value[i])
  ids.forEach((i) => { openQ.value[i] = anyClosed })
}
const filteredDetail = computed(() =>
  (result.value?.detail || []).filter((q) => (onlyWrong.value ? !q.correct : true)))
const wrongCount = computed(() => (result.value?.detail || []).filter((q) => !q.correct).length)
function ansText(q) {
  const out = []
  for (const ch of (q.student_answer || '')) {
    const i = ord(ch)
    if (i >= 0 && i < (q.options || []).length) out.push(q.options[i])
  }
  return out.join('；') || '（未作答）'
}
function correctText(q) {
  const out = []
  for (const ch of (q.answer || '')) {
    const i = ord(ch)
    if (i >= 0 && i < (q.options || []).length) out.push(q.options[i])
  }
  return out.join('；')
}
function ord(ch) { return 'ABCD'.indexOf(ch) }

/* —— 再练一组：直接重开同类型新卷（后端每次重新组卷，7 天内不重复出题） —— */
const restarting = ref(false)
async function restart() {
  if (restarting.value) return
  restarting.value = true
  try {
    const k = kind.value === 'teacher' ? 'daily' : kind.value
    const cluster = sessionStorage.getItem('exam_cluster') || ''
    const r = (k === 'cluster' && cluster)
      ? await api.quizStart('cluster', 0, cluster)
      : await api.quizStart(k === 'mock' ? 'mock' : 'daily')
    sessionStorage.setItem('exam_items', JSON.stringify(r.items))
    sessionStorage.setItem('exam_kind', r.kind || 'daily')
    sessionStorage.setItem('exam_title', r.title || '')
    sessionStorage.setItem('exam_time_limit', String(r.time_limit || 0))
    sessionStorage.removeItem('exam_cluster')
    router.push('/exam/' + r.attempt_id)
  } catch (e) {
    alert('开卷失败：' + e.message)
  } finally {
    restarting.value = false
  }
}
</script>

<template>
  <div class="page" style="max-width: 880px">
    <!-- 无题（直接访问/刷新后） -->
    <div v-if="!items.length && !result" class="card" style="padding: 60px 24px; text-align: center">
      <div style="font-size: 44px">🗂</div>
      <div style="margin-top: 10px; font-size: 15px; font-weight: 600">没有进行中的练习</div>
      <div style="font-size: 12.5px; color: var(--text-3); margin-top: 6px">练习卷只保留在当前标签页，刷新后请从「练习考试」重新开卷</div>
      <button class="btn mt16" style="margin-top: 18px" @click="router.push('/practice')">去练习考试</button>
    </div>

    <!-- 结果页 -->
    <div v-else-if="result" class="card" style="padding: 30px">
      <div class="score-ring">
        <div class="v mono" style="font-size: 34px">{{ result.score }}</div>
        <div class="k">总分（{{ result.max }}）</div>
      </div>
      <div class="grid-3 mt16">
        <div class="card" style="text-align: center; margin: 0"><div class="v mono">{{ result.max }}</div><div class="k">满分</div></div>
        <div class="card" style="text-align: center; margin: 0"><div class="v mono">{{ result.max ? Math.round(result.score / result.max * 100) : 0 }}%</div><div class="k">正确率</div></div>
        <div class="card" style="text-align: center; margin: 0"><div class="v mono">{{ kind === 'mock' ? '12:00' : ((result && result.minutes) ? result.minutes + ' 分钟' : '不限时') }}</div><div class="k">限时</div></div>
      </div>
      <div class="mt16">
        <div class="card-title">各簇得分（10 分/题）</div>
        <div v-for="(v, k) in result.per_cluster" :key="k" class="row-item">
          <div style="width: 24px" class="dot" :style="{ background: clusterColor(k) }"></div>
          <div class="rmain"><div class="rtitle" style="font-size: 13px">{{ clusterName(k) }}</div></div>
          <div class="mono" style="font-weight: 700">{{ v.correct * 10 }} / {{ v.total * 10 }}</div>
        </div>
      </div>

      <!-- 逐题对错与讲解 -->
      <div class="mt16">
        <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 8px">
          <div class="card-title" style="margin: 0">逐题对错与讲解（{{ result.detail.length }} 题 / 错 {{ wrongCount }} 题）</div>
          <button class="btn sm ghost" style="margin-left: auto" @click="onlyWrong = !onlyWrong">{{ onlyWrong ? '查看全部' : '只看错题' }}</button>
          <button class="btn sm ghost" @click="toggleAll">全部展开 / 收起</button>
        </div>
        <div v-for="(q, i) in filteredDetail" :key="q.question_id" class="qrow" :class="{ bad: !q.correct }">
          <div style="display: flex; gap: 10px; align-items: center; cursor: pointer" @click="toggleQ(i)">
            <span class="qbadge" :class="q.correct ? 'ok' : 'no'">{{ q.correct ? '✓ 对' : '✗ 错' }}</span>
            <span class="tag">{{ clusterName(q.cluster) }}</span>
            <span class="tag blue">{{ q.type }}</span>
            <span style="font-size: 13px; flex: 1; min-width: 0" class="qstem">{{ q.stem }}</span>
            <span class="mono" style="font-size: 11px; color: var(--text-3)">{{ openQ[i] ? '▲' : '▼' }}</span>
          </div>
          <div v-if="openQ[i]" style="margin-top: 12px; border-top: 1px dashed var(--line); padding-top: 12px">
            <div style="font-size: 13.5px; line-height: 1.8">{{ q.stem }}</div>
            <div style="font-size: 13px; color: var(--text-2); margin-top: 8px; line-height: 1.9">
              <div v-for="(o, oi) in q.options" :key="oi"
                :style="{ color: (q.answer || '').includes('ABCD'[oi]) ? 'var(--success)' : (q.student_answer || '').includes('ABCD'[oi]) && !q.correct ? 'var(--primary-text)' : 'inherit', fontWeight: (q.answer || '').includes('ABCD'[oi]) ? 700 : 400 }">
                {{ 'ABCD'[oi] }}. {{ o }}{{ (q.answer || '').includes('ABCD'[oi]) ? '　✓ 正确答案' : '' }}{{ !(q.correct) && (q.student_answer || '').includes('ABCD'[oi]) ? '　← 你的作答' : '' }}
              </div>
            </div>
            <div style="font-size: 12.5px; margin-top: 8px">
              你的作答：<b class="mono" :style="{ color: q.correct ? 'var(--success)' : 'var(--primary-text)' }">{{ ansText(q) }}</b>
              <span v-if="!q.correct" style="margin-left: 14px">正确：<b class="mono" style="color: var(--success)">{{ q.answer }}（{{ correctText(q) }}）</b></span>
            </div>
            <div v-if="q.explanation" class="explain">
              <b>📖 讲解：</b>{{ q.explanation }}
            </div>
            <div v-else class="explain">📖 讲解：<span style="color: var(--text-3)">本题依据以下材料</span></div>
            <div style="font-size: 12px; color: var(--text-3); margin-top: 6px">出处：<span class="mono">{{ q.source_doc }}</span></div>
          </div>
        </div>
      </div>

      <div class="mt16" style="display: flex; gap: 10px; flex-wrap: wrap">
        <button class="btn sm" :disabled="restarting" @click="restart()">{{ restarting ? '开卷中…' : '再练一组（重新组卷）' }}</button>
        <button class="btn sm ghost" @click="weakAgain()">去学薄弱簇</button>
        <button class="btn sm ghost" @click="router.push('/wrong')">查看错题本</button>
        <button class="btn sm ghost" @click="router.push('/practice')">练习与专项</button>
        <button class="btn sm ghost" @click="router.push('/')">回首页</button>
      </div>
    </div>

    <!-- 答题页 -->
    <template v-else>
      <div class="card exam-head" style="display: flex; align-items: center; gap: 12px; padding: 14px 20px; flex-wrap: wrap">
        <div class="exam-title" style="font-weight: 700; font-size: 15px">{{ title }}</div>
        <div v-if="timeLimit" class="mono" style="margin-left: auto; font-size: 18px; font-weight: 700" :class="{ 'time-warn': left <= 120 }">
          ⏱ {{ mmss }}
        </div>
        <div style="font-size: 12.5px; color: var(--text-3); white-space: nowrap" :style="timeLimit ? { marginLeft: '16px' } : { marginLeft: 'auto' }">
          第 {{ cur + 1 }} / {{ items.length }} 题
        </div>
      </div>

      <div class="card mt16" style="padding: 24px">
        <div style="display: flex; gap: 8px; margin-bottom: 14px">
          <span class="tag" :class="curItem.type === '多选' ? 'blue' : 'red'">{{ curItem.type }}</span>
          <span class="tag gold">{{ clusterName(curItem.cluster) }}</span>
        </div>
        <div style="font-size: 15.5px; line-height: 1.8">{{ curItem.stem }}</div>
        <div class="opt-list">
          <div v-for="(o, i) in curItem.options" :key="i"
            class="opt" :class="{ sel: (curItem.type === '多选' ? picked.includes('ABCD'[i]) : picked === 'ABCD'[i]) }"
            @click="choose('ABCD'[i])">
            <b>{{ 'ABCD'[i] }}</b> {{ o }}
          </div>
        </div>
        <div v-if="picked" style="font-size: 12px; color: var(--text-3); margin-top: 10px">
          当前已选：<b class="mono" style="color: var(--primary-text)">{{ picked }}</b>（点「下一题」确认）
        </div>
        <div style="display: flex; gap: 10px; margin-top: 22px">
          <button class="btn sm ghost" :disabled="cur === 0" @click="prev">上一题</button>
          <button class="btn sm" :disabled="!picked" @click="next">下一题（确认）</button>
          <button class="btn sm ghost" style="margin-left: auto" :disabled="submitBusy" @click="submit()">{{ submitBusy ? '交卷中…' : '交卷' }}</button>
        </div>
      </div>

      <!-- 答题卡 -->
      <div class="card mt16" style="display: flex; flex-wrap: wrap; gap: 8px; align-items: center; padding: 14px 20px">
        <span style="font-size: 12.5px; color: var(--text-3)">答题卡</span>
        <button v-for="(it, i) in items" :key="it.question_id" class="nbtn"
          :class="{ on: i === cur, done: !!answers[String(it.question_id)] }" @click="jump(i)">{{ i + 1 }}</button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.qrow { border: 1px solid var(--line); border-radius: 10px; padding: 12px 16px; margin-bottom: 8px; background: #fff; }
.qrow.bad { border-color: #f3c1c1; background: #fffafa; }
.qbadge { border-radius: 6px; padding: 2px 8px; font-size: 12px; font-weight: 700; flex-shrink: 0; }
.qbadge.ok { background: var(--success-light); color: var(--success); }
.qbadge.no { background: #fdeaea; color: var(--primary-text); }
.qstem { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.explain { font-size: 13px; line-height: 1.8; margin-top: 10px; background: var(--bg); border-radius: 8px; padding: 10px 12px; color: var(--text-2); }
@media (max-width: 640px) { .qstem { white-space: normal; } }
.opt-list { display: grid; gap: 10px; margin-top: 18px; }
.opt {
  border: 1.5px solid var(--line); border-radius: 10px; padding: 12px 14px;
  font-size: 14px; cursor: pointer; transition: all .12s; display: flex; gap: 10px;
}
.opt:hover { border-color: var(--primary); background: var(--primary-light); }
.opt.sel { border-color: var(--primary); background: var(--primary-light); font-weight: 600; }
.opt b { color: var(--primary-text); min-width: 18px; }
.nbtn {
  width: 34px; height: 34px; border-radius: 8px; border: 1.5px solid var(--line);
  font-size: 12.5px; background: #fff; color: var(--text-2);
}
.nbtn:focus-visible { outline: 2px solid var(--primary); outline-offset: 1px; }
@media (max-width: 640px) {
  .exam-title { width: 100%; }
  .exam-head { gap: 8px; }
}
.nbtn.done { background: var(--success-light); border-color: var(--success); color: var(--success); font-weight: 700; }
.nbtn.on { background: var(--primary-deep); border-color: var(--primary); color: #fff; }
.time-warn { color: var(--primary-text); animation: blink 1s infinite; }
@keyframes blink { 50% { opacity: .4; } }
</style>