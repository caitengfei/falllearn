<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../../api'

const data = ref(null)
const err = ref('')
const tab = ref('trainings')
const tabs = [
  { id: 'trainings', label: '培训情况' },
  { id: 'students', label: '学生培训画像' },
  { id: 'teachers', label: '教师带训' }
]

async function load() {
  err.value = ''
  try {
    data.value = await api.statsTrainings()
  } catch (e) {
    err.value = e.message
  }
}
onMounted(load)

const totals = computed(() => {
  const t = data.value?.trainings || []
  return {
    n: t.length,
    enrolled: t.reduce((s, x) => s + x.enrolled, 0),
    done: t.reduce((s, x) => s + x.done, 0),
    rate: (() => {
      const e = t.reduce((s, x) => s + x.enrolled, 0)
      const d = t.reduce((s, x) => s + x.done, 0)
      return e ? Math.round((d * 100) / e) : 0
    })()
  }
})
</script>

<template>
  <div class="page" v-if="data">
    <div style="font-size: 19px; font-weight: 700; margin-bottom: 16px">培训情况统计</div>

    <div class="mgrid c4" style="margin-bottom: 16px">
      <div class="mcard"><div class="mk">培训期数</div><div class="mv">{{ totals.n }}</div><div class="ms">累计开设</div></div>
      <div class="mcard"><div class="mk">累计报名人次</div><div class="mv">{{ totals.enrolled }}</div><div class="ms">含重复报名</div></div>
      <div class="mcard"><div class="mk">累计完成人次</div><div class="mv" style="color: #15803d">{{ totals.done }}</div><div class="ms">教师标记完成</div></div>
      <div class="mcard hero"><div class="mk">总体完成率</div><div class="mv">{{ totals.rate }}%</div><div class="ms">完成 / 报名</div></div>
    </div>

    <div class="pills">
      <span v-for="t in tabs" :key="t.id" class="pill" :class="{ on: tab === t.id }" @click="tab = t.id">{{ t.label }}</span>
    </div>

    <!-- 培训情况 -->
    <div class="card" v-if="tab === 'trainings'">
      <table class="atable">
        <thead><tr><th>培训名称</th><th>批次</th><th>周期</th><th>负责教师</th><th>报名</th><th>完成</th><th style="width: 200px">完成率</th></tr></thead>
        <tbody>
          <tr v-for="t in data.trainings" :key="t.id">
            <td style="font-weight: 600">{{ t.title }}</td>
            <td><span class="tag blue" v-if="t.batch">{{ t.batch }}</span><span v-else style="color: var(--text-3)">—</span></td>
            <td style="color: var(--text-3); font-size: 12px" class="num">{{ t.start_date || '未定' }} ~ {{ t.end_date || '未定' }}</td>
            <td>{{ t.teacher_name }}</td>
            <td class="num">{{ t.enrolled }}</td>
            <td class="num" style="color: #15803d; font-weight: 700">{{ t.done }}</td>
            <td>
              <div class="bar-row" style="margin: 0">
                <div class="bt" style="flex: 1"><i :style="{ width: t.rate + '%', background: t.rate >= 60 ? '#22c55e' : '#f5a623' }"></i></div>
                <div class="bv">{{ t.rate }}%</div>
              </div>
            </td>
          </tr>
          <tr v-if="!data.trainings.length"><td colspan="7" style="color: var(--text-3); text-align: center; padding: 24px">暂无培训 —— 到「培训管理」创建</td></tr>
        </tbody>
      </table>
    </div>

    <!-- 学生培训画像 -->
    <div class="card" v-if="tab === 'students'">
      <div class="card-title">学生 · 培训 / 学时 / 学习行为</div>
      <table class="atable">
        <thead><tr><th>学号</th><th>姓名</th><th>报名培训</th><th>完成培训</th><th>学时</th><th>练习</th><th>AI 问答</th><th style="width: 160px">培训完成率</th></tr></thead>
        <tbody>
          <tr v-for="s in data.students" :key="s.student_no">
            <td class="num">{{ s.student_no }}</td>
            <td style="font-weight: 600">{{ s.name }}</td>
            <td class="num">{{ s.enrolled }}</td>
            <td class="num" :style="{ color: s.done ? '#15803d' : 'var(--text-3)' }">{{ s.done }}</td>
            <td class="num">{{ s.hours }} 学时</td>
            <td class="num">{{ s.practice }}</td>
            <td class="num">{{ s.ai_ask }}</td>
            <td>
              <div class="bar-row" style="margin: 0">
                <div class="bt" style="flex: 1"><i :style="{ width: (s.enrolled ? (s.done / s.enrolled) * 100 : 0) + '%', background: '#3b82f6' }"></i></div>
                <div class="bv">{{ s.enrolled ? Math.round((s.done / s.enrolled) * 100) + '%' : '—' }}</div>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 教师带训 -->
    <div class="card" v-if="tab === 'teachers'">
      <div class="card-title">教师 · 带训情况</div>
      <table class="atable">
        <thead><tr><th>教师</th><th>负责培训期数</th><th>班级启用学生</th><th>说明</th></tr></thead>
        <tbody>
          <tr v-for="t in data.teachers" :key="t.id">
            <td style="font-weight: 600">{{ t.name }} <span class="tag gold">教师</span></td>
            <td class="num" style="font-weight: 700">{{ t.trainings }}</td>
            <td class="num">{{ t.students }}</td>
            <td style="color: var(--text-3); font-size: 12px">全班启用学生数（学生不归属单个教师）；培训期数 = 该教师在「培训管理」创建的期数</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
  <div v-else class="page">
    <div v-if="err" class="card" style="border-color: #fca5a5; color: #b91c1c">加载失败：{{ err }} <button class="btn sm" style="margin-left: 12px" @click="load">重试</button></div>
    <div v-else class="card" style="color: var(--text-3)">加载中…</div>
  </div>
</template>