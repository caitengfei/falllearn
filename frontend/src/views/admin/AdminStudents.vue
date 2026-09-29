<script setup>
import { onMounted, ref } from 'vue'
import { api, CLUSTERS } from '../../api'

const students = ref([])
const loading = ref(false)
const err = ref('')
const toastMsg = ref('')
const modal = ref(null) // {name, password, enabled} 新建

function toast(m) { toastMsg.value = m; setTimeout(() => (toastMsg.value = ''), 2400) }

async function load() {
  loading.value = true
  err.value = ''
  try {
    const r = await api.adminStudents()
    students.value = r.items
  } catch (e) {
    err.value = e.message
  } finally {
    loading.value = false
  }
}
onMounted(load)

// 停用/启用双向确认（停用=破坏性操作）
async function toggleEnabled(s) {
  if (s.enabled && !confirm(`停用 ${s.name}（${s.student_no}）？停用后该学生将无法登录。`)) return
  if (!s.enabled && !confirm(`确认启用 ${s.name}（${s.student_no}）？`)) return
  const old = s.enabled
  s.enabled = old ? 0 : 1
  try {
    await api.studentUpdate(s.id, { name: s.name, password: '', enabled: s.enabled })
    toast('已保存')
  } catch (e) {
    s.enabled = old
    toast('操作失败：' + e.message)
  }
}
async function resetPwd(s) {
  if (!confirm(`把 ${s.name} 的密码重置为 123456？`)) return
  try {
    await api.studentUpdate(s.id, { name: s.name, password: '123456', enabled: s.enabled })
    toast(`${s.name} 密码已重置为 123456`)
  } catch (e) { toast('重置失败：' + e.message) }
}
async function saveNew() {
  const m = modal.value
  if (!m.name.trim()) return alert('请填写姓名')
  try {
    const r = await api.studentCreate({ name: m.name, password: m.password || '123456' })
    modal.value = null
    await load()
    toast(`已创建学生 ${r.student_no}（密码 ${m.password || '123456'}）`)
  } catch (e) { alert(e.message) }
}
</script>

<template>
  <div class="page">
    <div style="display: flex; align-items: center; margin-bottom: 16px">
      <div style="font-size: 19px; font-weight: 700">学生管理</div>
      <span style="font-size: 12px; color: var(--text-3); margin-left: 10px">{{ students.length }} 名在读 · 掌握度/学时/错题实时统计</span>
      <button class="btn sm" style="margin-left: auto" @click="modal = { name: '', password: '123456' }">＋ 新增学生</button>
    </div>

    <div v-if="err" class="card" style="border-color: #fca5a5; color: #b91c1c; margin-bottom: 14px">加载失败：{{ err }} <button class="btn sm" style="margin-left: 12px" @click="load">重试</button></div>
    <div v-if="toastMsg" class="toast">{{ toastMsg }}</div>

    <div class="card">
      <table class="atable">
        <thead>
          <tr>
            <th>学号</th><th>姓名</th><th>积分</th><th>平均掌握</th>
            <th>六簇掌握度</th><th>练习</th><th>AI 问答</th><th>错题</th><th>学时</th><th>勋章</th><th>培训</th><th>状态</th><th style="width: 150px">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="s in students" :key="s.id">
            <td class="num">{{ s.student_no }}</td>
            <td style="font-weight: 600">{{ s.name }}</td>
            <td class="num" style="font-weight: 700">{{ s.points }}</td>
            <td class="num">{{ s.avg_mastery }}%</td>
            <td>
              <div style="display: flex; gap: 3px">
                <div v-for="c in CLUSTERS" :key="c.id" :title="`${c.name} ${s.mastery[c.id] || 0}%`"
                     style="width: 14px; height: 14px; border-radius: 3px"
                     :style="{ background: (s.mastery[c.id] || 0) >= 60 ? c.color : '#e5e7eb' }"></div>
              </div>
            </td>
            <td class="num">{{ s.practice_count }}</td>
            <td class="num">{{ s.ai_ask }}</td>
            <td class="num" :style="{ color: s.wrong_active ? 'var(--primary)' : 'var(--text-3)' }">{{ s.wrong_active }}</td>
            <td class="num">{{ s.hours }} 学时</td>
            <td class="num">{{ s.badge_count }}</td>
            <td class="num">{{ s.enroll_count }}</td>
            <td>
              <span class="switch" :class="{ on: s.enabled === 1 }" @click="toggleEnabled(s)"><i></i></span>
            </td>
            <td><div class="op">
              <button @click="resetPwd(s)">重置密码</button>
            </div></td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="modal" class="mask" @click.self="modal = null">
      <div class="modal">
        <div class="modal-h">新增学生<span class="more" @click="modal = null">✕</span></div>
        <div class="field"><label>姓名 *</label><input v-model="modal.name" placeholder="如：赵小棠" /></div>
        <div class="field"><label>初始密码（默认 123456）</label><input v-model="modal.password" /></div>
        <p style="font-size: 12px; color: var(--text-3)">学号自动生成（S2026xxx 递增），创建后即可用账号登录学生端。</p>
        <div style="display: flex; gap: 10px; margin-top: 14px">
          <button class="btn sm" @click="saveNew">创建</button>
          <button class="btn sm ghost" @click="modal = null">取消</button>
        </div>
      </div>
    </div>
  </div>
</template>