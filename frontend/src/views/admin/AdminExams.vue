<script setup>
import { computed, onMounted, ref } from 'vue'
import { api, auth, clusterName } from '../../api'

const items = ref([])
const err = ref('')
const students = ref([]
)
const fStatus = ref('done')
const fStudent = ref(0)
const detail = ref(null)   // {attempt, items}
const loading = ref(false)

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
onMounted(load)

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

    <div v-if="err" class="card" style="border-color: #fca5a5; color: #b91c1c; margin-bottom: 14px">加载失败：{{ err }}</div>
    <div v-if="toastMsg" class="toast">{{ toastMsg }}</div>

    <div class="card" style="margin-bottom: 16px">
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
              <div v-if="q.feedback && !q.correct" style="font-size: 12px; color: var(--primary); margin-top: 3px">{{ q.feedback }}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>