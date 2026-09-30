<script setup>
import { computed, onMounted, ref } from 'vue'
import { api, auth } from '../../api'

const accounts = ref([])
const modal = ref(null) // {name, role, student_no, password}
const authSno = computed(() => auth.user?.student_no)
const toastMsg = ref('')
const err = ref('')
function toast(m) { toastMsg.value = m; setTimeout(() => (toastMsg.value = ''), 2400) }

async function load() {
  err.value = ''
  try {
    const r = await api.accounts()
    accounts.value = r.items
  } catch (e) {
    err.value = e.message // 页面级错误条 + 重试（表格空着时不能只弹 3 秒 toast）
  }
}
onMounted(() => { load(); loadInvites() })

// —— 邀请码（推荐方式：学生自助加入，教师不必逐个发号）——
const invites = ref([])
const invOpen = ref(false)
const invBusy = ref(false)
const invForm = ref({ note: '', max_uses: 60, days: 30 })
const invNew = ref(null)
async function loadInvites() {
  try {
    invites.value = (await api.invites()).items || []
  } catch (e) { /* 邀请码加载失败不阻塞账号表 */ }
}
async function doCreateInvite() {
  invBusy.value = true
  invNew.value = null
  try {
    invNew.value = await api.inviteCreate({
      note: (invForm.value.note || '').trim(),
      max_uses: Math.floor(Number(invForm.value.max_uses)) || 60,
      days: Math.floor(Number(invForm.value.days)) || 30,
    })
    await loadInvites()
    toast('邀请码已生成')
  } catch (e) { alert(e.message) } finally { invBusy.value = false }
}
async function toggleInvite(it) {
  try { await api.inviteUpdate(it.id, it.enabled ? 0 : 1); await loadInvites() } catch (e) { alert(e.message) }
}
async function delInvite(it) {
  if (!confirm(`删除邀请码 ${it.code}？（已注册的学生账号不受影响）`)) return
  try { await api.inviteDelete(it.id); await loadInvites(); toast('已删除') } catch (e) { alert(e.message) }
}
function copyText(t) {
  if (navigator.clipboard?.writeText) navigator.clipboard.writeText(t).then(() => toast('已复制到剪贴板'), () => alert(t))
  else alert(t)
}
const inviteLink = (p) => location.origin + p
const fmtDay = (ts) => new Date(ts * 1000).toLocaleDateString('zh-CN')

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
    <div v-if="err" class="card" style="border-color: #fca5a5; color: #b91c1c; margin-bottom: 14px">加载失败：{{ err }} <button class="btn sm" style="margin-left: 12px" @click="load">重试</button></div>

    <!-- 邀请码：学生自助注册（推荐；较逐个发号更省事，且隐私采集最小化） -->
    <div class="card" style="margin-bottom: 14px; border-color: #bbf7d0; background: linear-gradient(120deg, #f0fdf4, #ffffff 60%)">
      <div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap">
        <b style="font-size: 14px">🎟 邀请码 · 学生自助加入</b>
        <span style="font-size: 12px; color: var(--text-3)">
          生成班级邀请码让学生自行注册：只需昵称 + 自设密码，不采集手机号/邮箱/身份证，学号由平台分配
        </span>
        <button class="btn sm ghost" style="margin-left: auto" @click="invOpen = !invOpen">{{ invOpen ? '收起 ▴' : '展开 ▾' }}</button>
      </div>

      <div v-if="invOpen" style="display: flex; gap: 10px; margin-top: 12px; flex-wrap: wrap; align-items: flex-end">
        <div class="field" style="width: 200px"><label>班级备注（仅教师可见）</label><input v-model="invForm.note" placeholder="如：2026 级养老 1 班" /></div>
        <div class="field" style="width: 110px"><label>人数上限</label><input v-model="invForm.max_uses" /></div>
        <div class="field" style="width: 110px"><label>有效期（天）</label><input v-model="invForm.days" /></div>
        <button class="btn sm" :disabled="invBusy" @click="doCreateInvite">{{ invBusy ? '生成中…' : '生成邀请码' }}</button>
      </div>

      <div v-if="invNew" style="margin-top: 12px; font-size: 13px">
        <div style="color: #15803d; font-weight: 700">✓ 邀请码：<span class="mono" style="font-size: 15px">{{ invNew.code }}</span></div>
        <div style="margin-top: 6px; font-size: 12.5px; color: var(--text-2)">
          学生注册链接：<span class="mono">{{ inviteLink(invNew.path) }}</span>
          <button class="btn sm ghost" style="margin-left: 8px" @click="copyText(inviteLink(invNew.path))">复制链接</button>
          <button class="btn sm ghost" style="margin-left: 6px" @click="copyText(invNew.code)">只复制码</button>
        </div>
        <div style="margin-top: 6px; font-size: 12px; color: var(--text-3)">
          把链接或邀请码发到班级群即可（二维码可用任意工具对链接生成）
        </div>
      </div>

      <div v-if="invites.length" style="margin-top: 12px; overflow-x: auto">
        <table class="atable">
          <thead><tr><th>邀请码</th><th>备注</th><th>已用 / 上限</th><th>有效期至</th><th>状态</th><th style="width: 190px">操作</th></tr></thead>
          <tbody>
            <tr v-for="it in invites" :key="it.id">
              <td class="num">{{ it.code }}</td>
              <td>{{ it.note || '—' }}</td>
              <td>{{ it.used_count }} / {{ it.max_uses }}</td>
              <td style="font-size: 12px; color: var(--text-3)">{{ fmtDay(it.expires_at) }}</td>
              <td>
                <span v-if="!it.enabled" class="tag">已停用</span>
                <span v-else-if="it.expired" class="tag">已过期</span>
                <span v-else-if="it.full" class="tag">已满</span>
                <span v-else class="tag green">可用</span>
              </td>
              <td><div class="op">
                <button @click="copyText(inviteLink(it.path))">复制链接</button>
                <button v-if="it.mine" @click="toggleInvite(it)">{{ it.enabled ? '停用' : '启用' }}</button>
                <button v-if="it.mine" class="danger" @click="delInvite(it)">删除</button>
              </div></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

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