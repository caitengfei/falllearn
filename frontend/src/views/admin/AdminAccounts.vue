<script setup>
import { computed, onMounted, ref } from 'vue'
import { api, auth } from '../../api'

const accounts = ref([])
const modal = ref(null) // {name, role, student_no, password}
const authSno = computed(() => auth.user?.student_no)
const toastMsg = ref('')
function toast(m) { toastMsg.value = m; setTimeout(() => (toastMsg.value = ''), 2400) }

async function load() {
  try {
    const r = await api.accounts()
    accounts.value = r.items
  } catch (e) { toast('加载失败：' + e.message) }
}
onMounted(load)

function fmt(t) { return t ? new Date(t * 1000).toLocaleDateString('zh-CN') : '' }

async function saveNew() {
  const m = modal.value
  if (!m.name.trim()) return alert('请填写姓名')
  try {
    const r = await api.accountCreate({
      name: m.name, role: m.role, student_no: m.student_no || '', password: m.password || '123456'
    })
    modal.value = null
    await load()
    toast(`已创建 ${m.role === 'teacher' ? '教师' : '学生'}账号 ${r.student_no}（密码 ${m.password || '123456'}）`)
  } catch (e) { alert(e.message) }
}
async function toggleEnabled(a) {
  if (a.student_no === authSno.value) return alert('不能停用自己的账号')
  if (a.enabled && !confirm(`停用账号 ${a.student_no}（${a.name}）？停用后该账号无法登录。`)) return
  const old = a.enabled
  a.enabled = old ? 0 : 1
  try {
    await api.accountUpdate(a.id, { enabled: a.enabled, password: '' })
    await load()
  } catch (e) {
    a.enabled = old
    alert(e.message)
  }
}
async function resetPwd(a) {
  if (!confirm(`把 ${a.name} 的密码重置为 123456？`)) return
  try {
    await api.accountUpdate(a.id, { enabled: a.enabled, password: '123456' })
    toast(`密码已重置为 123456`)
  } catch (e) { alert(e.message) }
}
async function remove(a) {
  if (!confirm(`物理删除账号 ${a.student_no}（${a.name}）及其全部学习数据？此操作不可恢复！`)) return
  try {
    await api.accountDelete(a.id)
    await load()
    toast('已删除')
  } catch (e) { alert(e.message) }
}

// —— 批量发号（真实试用 / 班级批量建学生账号）——
const batchOpen = ref(false)
const batchBusy = ref(false)
const batchForm = ref({ prefix: 'S20261', count: 10, password: '123456', name_tpl: '同学{seq}' })
const batchRes = ref(null)
async function doBatch() {
  const f = batchForm.value
  const n = Math.floor(Number(f.count))
  if (!n || n < 1 || n > 100) return alert('数量填 1–100')
  batchBusy.value = true
  batchRes.value = null
  try {
    const r = await api.accountBatch({ prefix: f.prefix.trim(), count: n, password: f.password, name_tpl: f.name_tpl || '同学{seq}' })
    batchRes.value = r
    await load()
  } catch (e) { alert(e.message) } finally { batchBusy.value = false }
}
</script>

<template>
  <div class="page">
    <div style="display: flex; align-items: center; margin-bottom: 16px">
      <div style="font-size: 19px; font-weight: 700">账号管理</div>
      <span style="font-size: 12px; color: var(--text-3); margin-left: 10px">学生 / 教师账号 · 创建、停用、重置密码、删除</span>
      <button class="btn sm" style="margin-left: auto" @click="modal = { name: '', role: 'student', student_no: '', password: '123456' }">＋ 新建账号</button>
    </div>

    <div v-if="toastMsg" class="toast">{{ toastMsg }}</div>

    <div class="card" style="margin-bottom: 14px">
      <div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap">
        <b style="font-size: 14px">👥 批量发号</b>
        <span style="font-size: 12px; color: var(--text-3)">真实试用 / 班级批量创建学生账号（单次 ≤100，已存在自动跳过）</span>
        <button class="btn sm ghost" style="margin-left: auto" @click="batchOpen = !batchOpen">{{ batchOpen ? '收起 ▴' : '展开 ▾' }}</button>
      </div>
      <div v-if="batchOpen" style="display: flex; gap: 10px; margin-top: 12px; flex-wrap: wrap; align-items: flex-end">
        <div class="field" style="width: 150px"><label>学号前缀（+两位序号）</label><input v-model="batchForm.prefix" placeholder="S20261" /></div>
        <div class="field" style="width: 90px"><label>数量</label><input v-model="batchForm.count" /></div>
        <div class="field" style="width: 110px"><label>初始密码</label><input v-model="batchForm.password" /></div>
        <div class="field" style="width: 150px"><label>姓名模板（{seq}=序号）</label><input v-model="batchForm.name_tpl" placeholder="同学{seq}" /></div>
        <button class="btn sm" :disabled="batchBusy" @click="doBatch">{{ batchBusy ? '创建中…' : '批量创建' }}</button>
      </div>
      <div v-if="batchRes" style="margin-top: 12px; font-size: 12.5px; line-height: 1.9">
        <span v-if="batchRes.created" style="color: #16a34a; font-weight: 600">✓ 已创建 {{ batchRes.created }} 个</span>
        <span v-if="batchRes.skipped && batchRes.skipped.length" style="color: #b45309; margin-left: 8px">跳过（已存在）：{{ batchRes.skipped.join(' ') }}</span>
        <div v-if="batchRes.items && batchRes.items.length" style="font-family: ui-monospace, monospace; color: var(--text-2); background: var(--bg); border-radius: 8px; padding: 8px 12px; margin-top: 6px; word-break: break-all">
          {{ batchRes.items.join('　') }}
        </div>
      </div>
    </div>

    <div class="card">
      <table class="atable">
        <thead><tr><th>学号 / 工号</th><th>姓名</th><th>角色</th><th>创建日期</th><th>状态</th><th style="width: 240px">操作</th></tr></thead>
        <tbody>
          <tr v-for="a in accounts" :key="a.id">
            <td class="num">{{ a.student_no }} <span v-if="a.student_no === auth.user?.student_no" class="tag red">我</span></td>
            <td style="font-weight: 600">{{ a.name }}</td>
            <td><span class="tag" :class="a.role === 'teacher' ? 'gold' : 'blue'">{{ a.role === 'teacher' ? '教师' : '学生' }}</span></td>
            <td style="color: var(--text-3); font-size: 12px">{{ fmt(a.created_at) }}</td>
            <td><span class="switch" :class="{ on: a.enabled === 1 }" @click="toggleEnabled(a)"><i></i></span></td>
            <td><div class="op">
              <button @click="resetPwd(a)">重置密码</button>
              <button v-if="a.student_no !== auth.user?.student_no" class="danger" @click="remove(a)">删除</button>
            </div></td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="modal" class="mask" @click.self="modal = null">
      <div class="modal">
        <div class="modal-h">新建账号<span class="more" @click="modal = null">✕</span></div>
        <div class="field"><label>姓名 *</label><input v-model="modal.name" /></div>
        <div class="mgrid c2">
          <div class="field">
            <label>角色</label>
            <select v-model="modal.role">
              <option value="student">学生</option>
              <option value="teacher">教师</option>
            </select>
          </div>
          <div class="field"><label>初始密码</label><input v-model="modal.password" /></div>
        </div>
        <div class="field"><label>账号（留空自动分配：学生 S2026xxx / 教师 T2026xxx 递增）</label><input v-model="modal.student_no" placeholder="可选" /></div>
        <div style="display: flex; gap: 10px; margin-top: 14px">
          <button class="btn sm" @click="saveNew">创建</button>
          <button class="btn sm ghost" @click="modal = null">取消</button>
        </div>
      </div>
    </div>
  </div>
</template>