<script setup>
import { computed, onMounted, ref } from 'vue'
import { api, auth, clusterName, CLUSTERS } from '../../api'

const items = ref([])
const err = ref('')
const students = ref([]
)
const fStatus = ref('done')
const fStudent = ref(0)
const detail = ref(null)   // {attempt, items}
const loading = ref(false)

// ---- 教师布置（闭环：建卷 → 学生端可见 → 完成统计）----
const asgList = ref([])
const asgLoading = ref(false)
const aForm = ref({ title: '', clusters: ['morse', 'env', 'five', 'fracture', 'record', 'cpr'], n: 10, minutes: 10, due_days: 7 })

async function loadAssignments() {
  asgLoading.value = true
  try {
    asgList.value = (await api.adminAssignments()).items || []
  } catch (e) {
    err.value = e.message
  } finally {
    asgLoading.value = false
  }
}

function toggleCluster(id) {
  const arr = aForm.value.clusters
  const i = arr.indexOf(id)
  if (i >= 0) arr.splice(i, 1)
  else arr.push(id)
}

async function doAssign() {
  if (!aForm.value.clusters.length) return toast('请至少勾选一个知识簇')
  asgLoading.value = true
  try {
    const r = await api.adminAssign(aForm.value)
    toast('已布置：' + r.title + '（' + r.n + ' 题）')
    aForm.value.title = ''
    await Promise.all([loadAssignments(), load()])
  } catch (e) {
    toast('布置失败：' + e.message)
  } finally {
    asgLoading.value = false
  }
}

async function delAssign(a) {
  if (!confirm('删除布置「' + a.title + '」？学生的作答记录会一并删除。')) return
  try {
    await api.adminAssignDelete(a.exam_id)
    toast('已删除')
    await Promise.all([loadAssignments(), load()])
  } catch (e) {
    toast('删除失败：' + e.message)
  }
}
const fmtDue = (t) => t ? new Date(t * 1000).toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' }) : '—'

// 布置成绩统计（平均分/满分/分布/各簇正确率/最弱簇/分班）
const asgDetail = ref(null)
function openAsgDetail(a) { asgDetail.value = a }
function fmtDist(a) {
  if (!a.score_dist || !Object.keys(a.score_dist).length) return '暂无交卷'
  return Object.entries(a.score_dist).map(([s, c]) => `${s}分×${c}`).join(' · ')
}
function fullPct(a) {
  return a.done ? Math.round((a.full_count || 0) * 100 / a.done) : 0
}

async function load() {
  loading.value = true
  err.value = ''
  try {
    // 列表与学生下拉同源筛选：列表与导出行为一致
    const [ex, st] = await Promise.all([api.adminExams(fStatus.value, fStudent.value), api.adminStudents()])
    items.value = ex.items
    students.value = st.items
  } catch (e) {
    err.value = e.message
  } finally {
    loading.value = false
  }
}
onMounted(() => { load(); loadAssignments() })

function fmt(t) {
  return t ? new Date(t * 1000).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : '—'
}
const kindName = (k) => ({ mock: '模拟考', daily: '日常练习', teacher: '教师布置', wrong: '错题重答' }[k] || k)
const statusName = (s) => ({ started: '进行中', done: '已完成', aborted: '已放弃', expired: '已超时' }[s] || s)

async function openDetail(a) {
  try {
    detail.value = await api.adminExamDetail(a.id)
  } catch (e) {
    toast(e.message)
  }
}
const toastMsg = ref('')
function toast(m) { toastMsg.value = m; setTimeout(() => (toastMsg.value = ''), 2400) }

// CSV 导出：fetch + Bearer 下载（location.href 无法带 token 会 401）
async function exportCsv() {
  if (!items.length && !fStatus.value) return toast('当前筛选下没有记录可导出')
  try {
    const res = await fetch(api.adminExamsCsv(fStatus.value, fStudent.value), {
      headers: { authorization: `Bearer ${auth.token}` }
    })
    if (!res.ok) {
      const d = await res.json().catch(() => ({}))
      throw new Error(d.detail || `HTTP ${res.status}`)
    }
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `exams-${Date.now()}.csv`
    document.body.appendChild(a)
    a.click()
    a.remove()
    setTimeout(() => URL.revokeObjectURL(url), 4000)
    toast('CSV 已下载')
  } catch (e) {
    toast('导出失败：' + e.message)
  }
}
const dStem = (s) => s.length > 60 ? s.slice(0, 60) + '…' : s
</script>

<template>
  <div class="page">
    <div style="display: flex; align-items: center; margin-bottom: 16px">
      <div style="font-size: 19px; font-weight: 700">考试管理</div>
      <span style="font-size: 12px; color: var(--text-3); margin-left: 10px">{{ items.length }} 条记录 · 可导出 CSV</span>
      <button class="btn sm gold" style="margin-left: auto" @click="exportCsv">⬇ 导出 CSV</button>
    </div>

    <div v-if="err" class="card" style="border-color: #fca5a5; color: #b91c1c; margin-bottom: 14px">加载失败：{{ err }} <button class="btn sm" style="margin-left: 12px" @click="load">重试</button></div>
    <div v-if="toastMsg" class="toast">{{ toastMsg }}</div>

    <!-- 教师布置（闭环） -->
    <div class="card" style="margin-bottom: 16px">
      <div class="card-title" style="display: flex; align-items: center; gap: 10px">
        布置练习
        <span style="font-size: 12px; font-weight: 400; color: var(--text-3)">选知识簇组卷 · 学生在「练习考试 · 教师布置」可见并作答</span>
      </div>
      <div style="display: flex; gap: 10px; flex-wrap: wrap; margin-top: 12px; align-items: center">
        <div class="field" style="margin: 0; flex: 1; min-width: 200px">
          <input v-model="aForm.title" type="text" placeholder="标题（留空自动生成，如：教师布置·五步处置…）" style="width: 100%">
        </div>
        <div class="field" style="margin: 0">
          <select v-model.number="aForm.n">
            <option :value="5">5 题</option>
            <option :value="10">10 题</option>
            <option :value="15">15 题</option>
            <option :value="20">20 题</option>
          </select>
        </div>
        <div class="field" style="margin: 0">
          <select v-model.number="aForm.minutes">
            <option :value="0">不限时</option>
            <option :value="5">5 分钟</option>
            <option :value="10">10 分钟</option>
            <option :value="15">15 分钟</option>
            <option :value="20">20 分钟</option>
          </select>
        </div>
        <div class="field" style="margin: 0">
          <select v-model.number="aForm.due_days">
            <option :value="3">3 天内有效</option>
            <option :value="7">7 天内有效</option>
            <option :value="14">14 天内有效</option>
            <option :value="30">30 天内有效</option>
          </select>
        </div>
        <button class="btn sm" :disabled="asgLoading" @click="doAssign">{{ asgLoading ? '布置中…' : '＋ 布置' }}</button>
      </div>
      <div style="display: flex; gap: 8px; flex-wrap: wrap; margin-top: 10px">
        <span v-for="c in CLUSTERS" :key="c.id" class="pill sm" :class="{ on: aForm.clusters.includes(c.id) }" @click="toggleCluster(c.id)">
          {{ c.name }}
        </span>
      </div>

      <table class="atable" style="margin-top: 14px">
        <thead><tr><th>布置</th><th>知识簇</th><th>题量</th><th>限时</th><th>截止</th><th>完成情况</th><th>平均分</th><th>满分</th><th>最弱簇（自动定位）</th><th style="width: 150px">操作</th></tr></thead>
        <tbody>
          <tr v-for="a in asgList" :key="a.exam_id">
            <td style="max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap" :title="a.title">{{ a.title }}</td>
            <td style="font-size: 12px; color: var(--text-2)">{{ a.clusters.length ? a.clusters.map(clusterName).join('·') : '综合' }}</td>
            <td class="num">{{ a.n }}</td>
            <td class="num">{{ a.minutes ? a.minutes + ' 分钟' : '不限时' }}</td>
            <td class="num" style="font-size: 12px">{{ fmtDue(a.due_at) }}</td>
            <td>
              <span class="tag" :class="a.rate >= 60 ? 'green' : a.rate >= 30 ? 'blue' : 'gray'">{{ a.done }}/{{ a.total_students }} 人 · {{ a.rate }}%</span>
            </td>
            <td class="num" style="font-weight: 700">{{ a.avg_score != null ? a.avg_score + ' / ' + a.max_score : '—' }}</td>
            <td class="num"><b :style="{ color: (a.full_count || 0) ? '#b45309' : 'var(--text-3)' }">{{ a.full_count || 0 }}</b><span style="font-size: 11px; color: var(--text-3)"> 人（{{ fullPct(a) }}%）</span></td>
            <td>
              <span v-if="a.weakest" class="tag" style="background: #fef2f2; color: #b91c1c; border: 1px solid #fecaca">{{ a.weakest.name }} · {{ a.weakest.rate }}%</span>
              <span v-else style="color: var(--text-3); font-size: 12px">—</span>
            </td>
            <td>
              <button class="btn sm" @click="openAsgDetail(a)">成绩统计</button>
              <button class="btn sm ghost" @click="delAssign(a)">删除</button>
            </td>
          </tr>
          <tr v-if="!asgList.length"><td colspan="10" style="color: var(--text-3); text-align: center; padding: 20px">还没有布置过练习 —— 选好知识簇点「＋ 布置」</td></tr>
        </tbody>
      </table>
    </div>

    <div class="card" style="margin-bottom: 16px">
      <div class="card-title">作答记录（学生 × 试卷 × 得分）</div>
      <div class="pills" style="margin-bottom: 10px">
        <span class="pill sm" :class="{ on: fStatus === 'done' }" @click="fStatus = 'done'; load()">已交卷</span>
        <span class="pill sm" :class="{ on: fStatus === 'open' }" @click="fStatus = 'open'; load()">进行中</span>
        <span class="pill sm" :class="{ on: fStatus === '' }" @click="fStatus = ''; load()">全部</span>
      </div>
      <div class="field" style="margin: 0; max-width: 240px">
        <select v-model.number="fStudent" @change="load()">
          <option :value="0">全部学生</option>
          <option v-for="s in students" :key="s.id" :value="s.id">{{ s.name }}（{{ s.student_no }}）</option>
        </select>
      </div>
      <table class="atable">
        <thead><tr><th>学号</th><th>姓名</th><th>试卷</th><th>类型</th><th>开始</th><th>交卷</th><th>用时</th><th>得分</th><th style="width: 90px">操作</th></tr></thead>
        <tbody>
          <tr v-for="a in items" :key="a.id">
            <td class="num">{{ a.student_no }}</td>
            <td>{{ a.student_name }}</td>
            <td style="max-width: 220px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap">{{ a.exam_title }}</td>
            <td><span class="tag" :class="a.kind === 'mock' ? 'gold' : 'blue'">{{ kindName(a.kind) }}</span></td>
            <td style="color: var(--text-3); font-size: 12px" class="num">{{ fmt(a.started_at) }}</td>
            <td style="color: var(--text-3); font-size: 12px" class="num">{{ fmt(a.submitted_at) }}</td>
            <td class="num">{{ a.minutes != null ? a.minutes + ' 分' : '—' }}</td>
            <td>
              <b v-if="a.status === 'done'" class="num" style="font-size: 15px" :style="{ color: a.score >= 60 ? '#15803d' : 'var(--primary)' }">{{ a.score }}</b>
              <span v-else class="tag" :class="a.status === 'started' ? 'blue' : 'gray'">{{ statusName(a.status) }}</span>
            </td>
            <td><button class="btn sm ghost" @click="openDetail(a)">逐题明细</button></td>
          </tr>
          <tr v-if="!items.length"><td colspan="9" style="color: var(--text-3); text-align: center; padding: 28px">暂无考试记录 —— 学生在「练习考试」完成日常练习/模拟考并交卷后，记录会出现在这里</td></tr>
        </tbody>
      </table>
    </div>

    <!-- 布置成绩统计弹窗（总体 + 各簇正确率 + 分班） -->
    <div v-if="asgDetail" class="mask" @click.self="asgDetail = null">
      <div class="modal" style="max-width: 720px">
        <div class="modal-h">
          {{ asgDetail.title }} · 成绩统计
          <span class="more" @click="asgDetail = null">✕</span>
        </div>
        <div style="display: flex; gap: 10px; flex-wrap: wrap; margin: 4px 0 14px">
          <div class="tag" style="background: #f8fafc; border: 1px solid var(--line); font-size: 13px; padding: 8px 14px">
            平均分 <b style="font-size: 15px; color: var(--primary)">{{ asgDetail.avg_score != null ? asgDetail.avg_score : '—' }}</b> / {{ asgDetail.max_score }}
          </div>
          <div class="tag" style="background: #fffbeb; border: 1px solid #fde68a; font-size: 13px; padding: 8px 14px">
            满分 <b style="font-size: 15px; color: #b45309">{{ asgDetail.full_count || 0 }}</b> 人（{{ fullPct(asgDetail) }}%）
          </div>
          <div class="tag" style="background: #f8fafc; border: 1px solid var(--line); font-size: 12.5px; padding: 8px 14px">
            得分分布 {{ fmtDist(asgDetail) }}
          </div>
        </div>
        <div style="font-size: 13px; font-weight: 700; margin-bottom: 8px">各知识点正确率<span v-if="asgDetail.weakest" style="margin-left: 8px; font-weight: 400; color: var(--text-3)">最弱：{{ asgDetail.weakest.name }}（{{ asgDetail.weakest.rate }}%）</span></div>
        <div v-for="c in (asgDetail.clusters_stat || [])" :key="c.cluster" class="bar-row" style="margin-bottom: 7px">
          <div class="bl" style="min-width: 86px">{{ c.name }}</div>
          <div class="bt" style="flex: 1"><i :style="{ width: c.rate + '%', background: c.cluster === asgDetail.weakest?.cluster ? '#ef4444' : (c.rate >= 80 ? '#22c55e' : c.rate >= 60 ? '#f5a623' : '#ef4444') }"></i></div>
          <div class="bv">{{ c.rate }}%（{{ c.ok }}/{{ c.n }}）</div>
        </div>
        <div v-if="!(asgDetail.clusters_stat || []).length" style="color: var(--text-3); font-size: 13px; padding: 8px 0">还没有学生交卷</div>
        <div style="font-size: 13px; font-weight: 700; margin: 16px 0 8px">分班统计<span style="margin-left: 8px; font-weight: 400; color: var(--text-3)">按学生所属班级分开</span></div>
        <table class="atable">
          <thead><tr><th>班级</th><th>交卷</th><th>平均分</th><th>满分</th><th>最弱簇</th></tr></thead>
          <tbody>
            <tr v-for="p in (asgDetail.per_class || [])" :key="p.class">
              <td style="font-weight: 600">{{ p.class }}</td>
              <td class="num">{{ p.done }} 人</td>
              <td class="num" style="font-weight: 700">{{ p.avg_score != null ? p.avg_score + ' / ' + asgDetail.max_score : '—' }}</td>
              <td class="num">{{ p.full_count || 0 }} 人</td>
              <td>
                <span v-if="p.weakest" class="tag" style="background: #fef2f2; color: #b91c1c; border: 1px solid #fecaca">{{ p.weakest.name }} · {{ p.weakest.rate }}%</span>
                <span v-else style="color: var(--text-3); font-size: 12px">—</span>
              </td>
            </tr>
            <tr v-if="!(asgDetail.per_class || []).length"><td colspan="5" style="color: var(--text-3); text-align: center; padding: 14px">暂无交卷记录</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 逐题明细弹窗 -->
    <div v-if="detail" class="mask" @click.self="detail = null">
      <div class="modal" style="max-width: 760px">
        <div class="modal-h">
          {{ detail.attempt.student_name }} · {{ detail.attempt.exam_title }}
          <span class="tag" :class="detail.attempt.score >= 60 ? 'green' : 'red'" style="margin-left: 10px">得分 {{ detail.attempt.score }}</span>
          <span class="more" @click="detail = null">✕</span>
        </div>
        <div v-for="(q, i) in detail.items" :key="q.question_id" style="border-bottom: 1px solid var(--line); padding: 12px 0">
          <div style="display: flex; gap: 8px; align-items: flex-start">
            <span style="width: 22px; height: 22px; border-radius: 50%; flex-shrink: 0; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 700; color: #fff"
                  :style="{ background: q.correct ? '#22c55e' : '#e4393c' }">{{ q.correct ? '✓' : '✗' }}</span>
            <div style="flex: 1">
              <div style="font-size: 13.5px; font-weight: 600">{{ i + 1 }}. {{ q.stem }}</div>
              <div style="font-size: 12px; color: var(--text-3); margin: 4px 0">
                {{ clusterName(q.cluster) }} · {{ q.type }}
                <span v-if="q.source_doc" style="margin-left: 8px">来源：{{ q.source_doc.slice(0, 30) }}</span>
              </div>
              <div style="font-size: 12.5px; color: var(--text-2); display: flex; gap: 14px; flex-wrap: wrap">
                <span>标准答案：<b style="color: #15803d">{{ q.answer }}</b></span>
                <span>学生答案：<b :style="{ color: q.correct ? '#15803d' : 'var(--primary)' }">{{ q.student_answer || '（未答）' }}</b></span>
              </div>
              <div v-if="q.feedback && !q.correct" style="font-size: 12px; color: var(--primary-text); margin-top: 3px">{{ q.feedback }}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>