<script setup>
import { computed, onMounted, ref } from 'vue'
import { api, CLUSTERS } from '../../api'

const studentsAll = ref([])
const classes = ref([])
const cls = ref('')            // 当前班级筛选：''=全部 / '__none__'=未分班 / 班级名
const sel = ref([])            // 勾选的学生 id
const loading = ref(false)
const err = ref('')
const toastMsg = ref('')
const modal = ref(null) // {name, password, class_name} 新建
const batchCls = ref('')       // 批量分配目标班级
const clsListId = 'cls-list-' + Math.random().toString(36).slice(2, 8)

// 名单分班（粘贴学号 → 整班归入）
const rosterCls = ref('')
const rosterText = ref('')
const rosterBusy = ref(false)

// 班级总览（按班级分组统计）
const perClass = computed(() => {
  const m = {}
  for (const s of studentsAll.value) {
    const k = s.class_name || '未分班'
    const g = m[k] || (m[k] = { name: k, n: 0, points: 0, mastery: 0, practice: 0, ai: 0, wrong: 0, hours: 0 })
    g.n++
    g.points += s.points || 0
    g.mastery += s.avg_mastery || 0
    g.practice += s.practice_count || 0
    g.ai += s.ai_ask || 0
    g.wrong += s.wrong_active || 0
    g.hours += s.hours || 0
  }
  const arr = Object.values(m).map((g) => ({ ...g,
    points: Math.round(g.points / g.n),
    mastery: (g.mastery / g.n).toFixed(1),
    hours: (g.hours / g.n).toFixed(1) }))
  arr.sort((a, b) => ((a.name === '未分班') - (b.name === '未分班')) || a.name.localeCompare(b.name, 'zh-CN'))
  return arr
})
const filtered = computed(() => {
  if (cls.value === '') return studentsAll.value
  if (cls.value === '__none__') return studentsAll.value.filter((s) => !s.class_name)
  return studentsAll.value.filter((s) => s.class_name === cls.value)
})

function toast(m) { toastMsg.value = m; setTimeout(() => (toastMsg.value = ''), 2600) }

async function load() {
  loading.value = true
  err.value = ''
  try {
    // 始终拉全量：班级总览需要全部数据，表格按筛选前端过滤
    const r = await api.adminStudents('')
    studentsAll.value = r.items
    classes.value = r.classes || []
    sel.value = []
  } catch (e) {
    err.value = e.message
  } finally {
    loading.value = false
  }
}
onMounted(load)

function switchCls(c) {
  cls.value = c
}
function toggleAll(e) {
  sel.value = e.target.checked ? filtered.value.map((s) => s.id) : []
}
function toggleOne(s) {
  const i = sel.value.indexOf(s.id)
  if (i >= 0) sel.value.splice(i, 1)
  else sel.value.push(s.id)
}
async function applyBatch() {
  if (!sel.value.length) return
  if (batchCls.value === '' && !confirm('把选中学生设为「未分班」？')) return
  try {
    const r = await api.studentsSetClass(sel.value, batchCls.value)
    toast(`已更新 ${r.updated} 名学生的班级`)
    await load()
  } catch (e) { toast('操作失败：' + e.message) }
}
async function applyRoster() {
  if (!rosterText.value.trim()) return toast('请粘贴学号名单')
  rosterBusy.value = true
  try {
    const r = await api.studentsClassRoster((rosterCls.value || '').trim(), rosterText.value)
    rosterText.value = ''
    let msg = `已将 ${r.updated} 名学号归入「${r.class_name}」`
    if (r.not_found.length) msg += `；${r.not_found.length} 个学号未找到（如 ${r.not_found.slice(0, 3).join('、')}）`
    toast(msg)
    await load()
  } catch (e) {
    toast('分班失败：' + e.message)
  } finally {
    rosterBusy.value = false
  }
}

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
    const r = await api.studentCreate({ name: m.name, password: m.password || '123456', class_name: m.class_name || '' })
    modal.value = null
    await load()
    toast(`已创建学生 ${r.student_no}（密码 ${m.password || '123456'}）`)
  } catch (e) { alert(e.message) }
}
</script>

<template>
  <div class="page">
    <div style="display: flex; align-items: center; margin-bottom: 12px">
      <div style="font-size: 19px; font-weight: 700">学生管理</div>
      <span style="font-size: 12px; color: var(--text-3); margin-left: 10px">{{ studentsAll.length }} 名在读 · 掌握度/学时/错题实时统计</span>
      <button class="btn sm" style="margin-left: auto" @click="modal = { name: '', password: '123456', class_name: batchCls }">＋ 新增学生</button>
    </div>

    <!-- 班级总览（按班级分开统计） -->
    <div class="card" style="margin-bottom: 14px">
      <div class="card-title">班级总览<span style="font-size: 11px; color: var(--text-3); font-weight: 400; margin-left: 8px">按班级分开统计 · 随学生数据实时计算</span></div>
      <table class="atable">
        <thead>
          <tr><th>班级</th><th>在读</th><th>平均积分</th><th>平均掌握</th><th>练习完成</th><th>AI 问答</th><th>活跃错题</th><th>人均学时</th></tr>
        </thead>
        <tbody>
          <tr v-for="c in perClass" :key="c.name" :style="{ background: c.name === '未分班' && c.n > 0 ? '#fffbeb' : '' }">
            <td style="font-weight: 600">{{ c.name }}<span v-if="c.name === '未分班' && c.n > 0" style="font-size: 11px; color: #b45309; font-weight: 400; margin-left: 6px">建议尽快分班</span></td>
            <td class="num" style="font-weight: 700">{{ c.n }}</td>
            <td class="num">{{ c.points }}</td>
            <td class="num">{{ c.mastery }}%</td>
            <td class="num">{{ c.practice }}</td>
            <td class="num">{{ c.ai }}</td>
            <td class="num" :style="{ color: c.wrong ? 'var(--primary)' : 'var(--text-3)' }">{{ c.wrong }}</td>
            <td class="num">{{ c.hours }}</td>
          </tr>
          <tr v-if="!perClass.length"><td colspan="8" style="color: var(--text-3); text-align: center; padding: 18px">暂无学生</td></tr>
        </tbody>
      </table>
    </div>

    <!-- 名单分班 -->
    <div class="card" style="margin-bottom: 14px">
      <div class="card-title">按名单批量分班<span style="font-size: 11px; color: var(--text-3); font-weight: 400; margin-left: 8px">把纸质名单上的学号整段粘贴进来，一次归入一个班</span></div>
      <div style="display: flex; gap: 10px; flex-wrap: wrap; align-items: flex-start; margin-top: 10px">
        <div class="field" style="margin: 0; width: 260px">
          <label>目标班级</label>
          <input v-model="rosterCls" :list="clsListId" placeholder="班级名（留空 = 移为未分班）" style="width: 100%" />
          <datalist :id="clsListId"><option v-for="c in classes" :key="c" :value="c" /></datalist>
        </div>
        <div class="field" style="margin: 0; flex: 1; min-width: 280px">
          <label>学号名单（换行 / 逗号 / 空格分隔均可）</label>
          <textarea v-model="rosterText" rows="3" style="width: 100%; resize: vertical"
                    placeholder="如：&#10;S2026010&#10;S2026011, S2026012&#10;S2026013 S2026014"></textarea>
        </div>
        <button class="btn sm" style="margin-top: 22px" :disabled="rosterBusy" @click="applyRoster">
          {{ rosterBusy ? '分班中…' : '应用分班' }}
        </button>
      </div>
      <p style="font-size: 12px; color: var(--text-3); margin-top: 8px">
        提示：后续用「账号管理 → 邀请码」发码时填上班级名，新注册学生会自动归班，无需再补录。
      </p>
    </div>

    <!-- 班级筛选 -->
    <div class="pills" style="margin-bottom: 14px">
      <span class="pill" :class="{ on: cls === '' }" @click="switchCls('')">全部</span>
      <span v-for="c in classes" :key="c" class="pill" :class="{ on: cls === c }" @click="switchCls(c)">{{ c }}</span>
      <span class="pill" :class="{ on: cls === '__none__' }" @click="switchCls('__none__')">未分班</span>
    </div>

    <!-- 批量分配（勾选） -->
    <div v-if="sel.length" class="card" style="display: flex; align-items: center; gap: 12px; padding: 12px 18px; margin-bottom: 12px">
      <b style="font-size: 13.5px">已选 {{ sel.length }} 名学生</b>
      <select v-model="batchCls" style="padding: 7px 10px; border: 1px solid var(--line); border-radius: 8px; font-size: 13px">
        <option value="">未分班</option>
        <option v-for="c in classes" :key="c" :value="c">{{ c }}</option>
        <option v-if="batchCls && !classes.includes(batchCls)" :value="batchCls">{{ batchCls }}</option>
      </select>
      <input v-model="batchCls" placeholder="或输入新班级名（如：2026级高职医养照护服务1班）"
             style="flex: 1; min-width: 220px; padding: 7px 10px; border: 1px solid var(--line); border-radius: 8px; font-size: 13px" />
      <button class="btn sm" @click="applyBatch">应用</button>
      <button class="btn sm ghost" @click="sel = []">取消选择</button>
    </div>

    <div v-if="err" class="card" style="border-color: #fca5a5; color: #b91c1c; margin-bottom: 14px">加载失败：{{ err }} <button class="btn sm" style="margin-left: 12px" @click="load">重试</button></div>
    <div v-if="toastMsg" class="toast">{{ toastMsg }}</div>

    <div class="card">
      <table class="atable">
        <thead>
          <tr>
            <th style="width: 34px"><input type="checkbox" :checked="sel.length && sel.length === filtered.length" @change="toggleAll" /></th>
            <th>学号</th><th>姓名</th><th>班级</th><th>积分</th><th>平均掌握</th>
            <th>六簇掌握度</th><th>练习</th><th>AI 问答</th><th>错题</th><th>学时</th><th>勋章</th><th>培训</th><th>状态</th><th style="width: 150px">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="s in filtered" :key="s.id">
            <td><input type="checkbox" :checked="sel.includes(s.id)" @change="toggleOne(s)" /></td>
            <td class="num">{{ s.student_no }}</td>
            <td style="font-weight: 600">{{ s.name }}</td>
            <td style="font-size: 12px; color: var(--text-2)">{{ s.class_name || '未分班' }}</td>
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
          <tr v-if="!filtered.length"><td colspan="15" style="color: var(--text-3); text-align: center; padding: 20px">该班级暂无学生</td></tr>
        </tbody>
      </table>
    </div>

    <div v-if="modal" class="mask" @click.self="modal = null">
      <div class="modal">
        <div class="modal-h">新增学生<span class="more" @click="modal = null">✕</span></div>
        <div class="field"><label>姓名 *</label><input v-model="modal.name" placeholder="如：赵小棠" /></div>
        <div class="field"><label>班级（可选）</label><input v-model="modal.class_name" :list="'cls-new-list'" placeholder="如：2026级高职医养照护服务1班" />
          <datalist id="cls-new-list"><option v-for="c in classes" :key="c" :value="c" /></datalist>
        </div>
        <div class="field"><label>初始密码（默认 123456）</label><input v-model="modal.password" /></div>
        <p style="font-size: 12px; color: var(--text-3)">学号自动生成（S2026xxx 递增），创建后即可用账号登录学生端。</p>
        <div style="display: flex; gap: 10px; margin-top: 14px">
          <button class="btn sm" @click="saveNew()">创建</button>
          <button class="btn sm ghost" @click="modal = null">取消</button>
        </div>
      </div>
    </div>
  </div>
</template>