<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../../api'

const trainings = ref([])
const students = ref([])
const modal = ref(null) // {title, batch, start_date, end_date, capacity, note, picks: Set}
const toastMsg = ref('')
function toast(m) { toastMsg.value = m; setTimeout(() => (toastMsg.value = ''), 2400) }

async function load() {
  const [t, s] = await Promise.all([api.trainings(), api.adminStudents()])
  trainings.value = t.items
  students.value = s.items.filter((x) => x.enabled)
}
onMounted(load)

function fmt(t) { return t ? new Date(t * 1000).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit' }) : '' }

function openCreate() {
  modal.value = { title: '', batch: '', start_date: '', end_date: '', capacity: 30, note: '', picks: new Set() }
}
function togglePick(sid) {
  const p = modal.value.picks
  p.has(sid) ? p.delete(sid) : p.add(sid)
}
async function save() {
  const m = modal.value
  if (!m.title.trim()) return alert('请填写培训名称')
  try {
    await api.trainingCreate({
      title: m.title, batch: m.batch, start_date: m.start_date, end_date: m.end_date,
      capacity: m.capacity, note: m.note, student_ids: [...m.picks]
    })
    modal.value = null
    await load()
    toast('培训已创建')
  } catch (e) { alert(e.message) }
}

async function enrollAll(t) {
  const ids = students.value.filter((s) => !t.students.some((x) => x.id === s.id)).map((s) => s.id)
  if (!ids.length) return toast('全部学生已报名')
  try {
    await api.trainingEnroll(t.id, ids, 'enrolled'); await load(); toast('已补报')
  } catch (e) { toast('补报失败：' + e.message) }
}
async function setDone(t, s, done) {
  const old = s.status
  s.status = done ? 'done' : 'enrolled'
  try {
    await api.trainingSetStatus(t.id, s.id, s.status); await load(); toast('已更新')
  } catch (e) {
    s.status = old
    toast('更新失败：' + e.message)
  }
}
async function remove(t) {
  if (!confirm(`删除培训「${t.title}」及其报名记录？`)) return
  try {
    await api.trainingDelete(t.id); await load(); toast('已删除')
  } catch (e) { alert(e.message) }
}
</script>

<template>
  <div class="page">
    <div style="display: flex; align-items: center; margin-bottom: 16px">
      <div style="font-size: 19px; font-weight: 700">培训管理</div>
      <span style="font-size: 12px; color: var(--text-3); margin-left: 10px">{{ trainings.length }} 期培训 · 报名 / 完成状态 → 统计页可见</span>
      <button class="btn sm" style="margin-left: auto" @click="openCreate">＋ 新建培训</button>
    </div>

    <div v-if="toastMsg" class="toast">{{ toastMsg }}</div>

    <div v-for="t in trainings" :key="t.id" class="card" style="margin-bottom: 14px">
      <div style="display: flex; align-items: flex-start; gap: 12px; flex-wrap: wrap">
        <div style="flex: 1; min-width: 260px">
          <div style="font-size: 15.5px; font-weight: 700">{{ t.title }} <span class="tag blue" v-if="t.batch">{{ t.batch }}</span></div>
          <div style="font-size: 12.5px; color: var(--text-3); margin-top: 4px">
            {{ t.start_date || '未定' }} ~ {{ t.end_date || '未定' }} · 容量 {{ t.capacity }} 人 · 负责：{{ t.teacher_name }}
            <span v-if="t.note" style="margin-left: 8px">{{ t.note }}</span>
          </div>
        </div>
        <div style="display: flex; gap: 18px; align-items: center">
          <div style="text-align: center">
            <div style="font-size: 20px; font-weight: 800">{{ t.enrolled }}</div>
            <div style="font-size: 11px; color: var(--text-3)">报名</div>
          </div>
          <div style="text-align: center">
            <div style="font-size: 20px; font-weight: 800; color: #15803d">{{ t.done }}</div>
            <div style="font-size: 11px; color: var(--text-3)">完成</div>
          </div>
          <div style="text-align: center">
            <div style="font-size: 20px; font-weight: 800; color: var(--primary)">{{ t.rate }}%</div>
            <div style="font-size: 11px; color: var(--text-3)">完成率</div>
          </div>
          <button class="btn sm ghost" @click="enrollAll(t)">一键补报</button>
          <button class="btn sm ghost" style="color: #b91c1c" @click="remove(t)">删除</button>
        </div>
      </div>
      <div v-if="t.students.length" style="margin-top: 14px; border-top: 1px solid var(--line); padding-top: 12px">
        <div style="display: flex; flex-wrap: wrap; gap: 8px">
          <span v-for="s in t.students" :key="s.id" style="display: inline-flex; align-items: center; gap: 6px; border: 1px solid var(--line); border-radius: 16px; padding: 3px 8px 3px 12px; font-size: 12.5px"
                :style="s.status === 'done' ? { background: '#e8f9ef', borderColor: '#a7f3d0', color: '#15803d' } : {}">
            {{ s.name }}（{{ s.student_no }}）
            <button style="font-size: 11px; padding: 1px 8px; border-radius: 8px; border: 1px solid currentColor; background: none; cursor: pointer"
                    @click="setDone(t, s, s.status !== 'done')">
              {{ s.status === 'done' ? '✓ 已完成' : '标记完成' }}
            </button>
          </span>
        </div>
      </div>
      <div v-else style="margin-top: 12px; font-size: 12.5px; color: var(--text-3)">暂无报名 —— 点「一键补报」或新建时勾选学生</div>
    </div>
    <div v-if="!trainings.length" class="card" style="color: var(--text-3); text-align: center; padding: 40px">
      还没有培训 —— 点右上角「新建培训」创建第一期（如：跌倒应急演练班·第 1 期）
    </div>

    <!-- 新建培训弹窗 -->
    <div v-if="modal" class="mask" @click.self="modal = null">
      <div class="modal">
        <div class="modal-h">新建培训<span class="more" @click="modal = null">✕</span></div>
        <div class="field"><label>培训名称 *</label><input v-model="modal.title" placeholder="如：跌倒应急演练班·第 2 期" /></div>
        <div class="mgrid c2">
          <div class="field"><label>批次</label><input v-model="modal.batch" placeholder="如：2026 秋" /></div>
          <div class="field"><label>容量（≥1，报名满员后无法再报）</label><input type="number" min="1" v-model.number="modal.capacity" /></div>
          <div class="field"><label>开始日期</label><input type="date" v-model="modal.start_date" /></div>
          <div class="field"><label>结束日期</label><input type="date" v-model="modal.end_date" /></div>
        </div>
        <div class="field"><label>备注</label><input v-model="modal.note" placeholder="考核方式 / 地点等" /></div>
        <div class="field">
          <label>初始报名（{{ modal.picks.size }} 人）</label>
          <div style="display: flex; flex-wrap: wrap; gap: 6px">
            <label v-for="s in students" :key="s.id" style="display: inline-flex; gap: 5px; align-items: center; font-size: 12.5px; border: 1px solid var(--line); border-radius: 14px; padding: 3px 10px; cursor: pointer"
                  :style="modal.picks.has(s.id) ? { background: 'var(--primary-light)', borderColor: 'var(--primary)', color: 'var(--primary)' } : {}">
              <input type="checkbox" :checked="modal.picks.has(s.id)" @change="togglePick(s.id)" style="display: none" />
              {{ s.name }}
            </label>
          </div>
        </div>
        <div style="display: flex; gap: 10px; margin-top: 14px">
          <button class="btn sm" @click="save">创建</button>
          <button class="btn sm ghost" @click="modal = null">取消</button>
        </div>
      </div>
    </div>
  </div>
</template>