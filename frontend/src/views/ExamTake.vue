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
        <div class="k">总分（100）</div>
      </div>
      <div class="grid-3 mt16">
        <div class="card" style="text-align: center; margin: 0"><div class="v mono">{{ result.max }}</div><div class="k">满分</div></div>
        <div class="card" style="text-align: center; margin: 0"><div class="v mono">{{ Math.round(result.score) }}%</div><div class="k">正确率</div></div>
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
      <div class="mt16" style="display: flex; gap: 10px; flex-wrap: wrap">
        <button class="btn sm" @click="router.push('/practice')">再练一组</button>
        <button class="btn sm ghost" @click="weakAgain()">再练一组薄弱题</button>
        <button class="btn sm ghost" @click="router.push('/wrong')">查看错题本</button>
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
          当前已选：<b class="mono" style="color: var(--primary)">{{ picked }}</b>（点「下一题」确认）
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
.opt-list { display: grid; gap: 10px; margin-top: 18px; }
.opt {
  border: 1.5px solid var(--line); border-radius: 10px; padding: 12px 14px;
  font-size: 14px; cursor: pointer; transition: all .12s; display: flex; gap: 10px;
}
.opt:hover { border-color: var(--primary); background: var(--primary-light); }
.opt.sel { border-color: var(--primary); background: var(--primary-light); font-weight: 600; }
.opt b { color: var(--primary); min-width: 18px; }
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
.nbtn.on { background: var(--primary); border-color: var(--primary); color: #fff; }
.time-warn { color: var(--primary); animation: blink 1s infinite; }
@keyframes blink { 50% { opacity: .4; } }
</style>