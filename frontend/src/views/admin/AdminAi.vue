<script setup>
import { computed, onMounted, ref } from 'vue'
import { api, CLUSTERS, clusterName } from '../../api'

const tab = ref('model')
const tabs = [
  { id: 'model', label: '🤖 模型选择' },
  { id: 'kb', label: '📚 知识库' },
  { id: 'gen', label: '✍️ AI 出题' },
  { id: 'grade', label: '⚖️ AI 判卷' }
]
const toastMsg = ref('')
function toast(m) { toastMsg.value = m; setTimeout(() => (toastMsg.value = ''), 2600) }

// ================= 模型选择 =================
const models = ref([])       // groups
const modelCurrent = ref(null)
const modelCurrentSession = ref(null) // 未手动设置时，任务会话的默认模型
const modelLoading = ref(false)
const modelMsg = ref('')
const modelPick = ref(null)  // {provider, model}

async function loadModels() {
  modelLoading.value = true
  modelMsg.value = ''
  try {
    const r = await api.aiModels()
    models.value = r.items || []
    modelCurrent.value = r.current
    modelCurrentSession.value = r.current_session
  } catch (e) {
    modelMsg.value = e.message
  }
  modelLoading.value = false
}
onMounted(loadModels)

// 同名模型跨渠道出现时（如 deepseek-v4-flash），用渠道短名区分
const flatModels = computed(() => {
  const ids = models.value.flatMap((g) => g.models.map((m) => m.id))
  const dup = new Set(ids.filter((x, i) => ids.indexOf(x) !== i))
  return models.value.flatMap((g) => g.models.map((m) => ({
    ...m,
    provider: g.id,
    providerName: g.name,
    providerShort: g.short || g.name,
    label: dup.has(m.id) ? `${m.id}（${g.short || g.name}）` : m.id
  })))
})

async function pickModel(m) {
  modelPick.value = m
}
async function applyModel() {
  const m = modelPick.value
  if (!m) return
  modelLoading.value = true
  try {
    await api.aiModel(m.provider, m.id)
    modelCurrent.value = { provider: m.provider, model: m.id }
    modelMsg.value = `✓ 已切换：AI 问答 / AI 出题 / AI 判卷 现在使用 ${m.id}`
    setTimeout(() => (modelMsg.value = ''), 4000)
  } catch (e) {
    modelMsg.value = '⚠ ' + e.message
  }
  modelLoading.value = false
}

// ================= 知识库 =================
const kb = ref([])
const kbRoot = ref('')
const kbNew = ref(null) // {path, content}
const kbFilter = ref('')
const kbLoading = ref(false)

async function loadKb() {
  kbLoading.value = true
  try {
    const r = await api.aiKb()
    kb.value = r.items
    kbRoot.value = r.root
  } finally {
    kbLoading.value = false
  }
}
onMounted(loadKb)

const kbFiltered = computed(() =>
  kbFilter.value ? kb.value.filter((x) => x.path.toLowerCase().includes(kbFilter.value.toLowerCase())) : kb.value)

async function writeKb(f, force = false) {
  try {
    await api.aiKbWrite(f.path, f.content, force)
  } catch (e) {
    // 已存在同名文档：确认后才允许覆盖（KB 是真实教研材料，防误覆盖）
    if (!force && e.message.includes('已存在')) {
      if (confirm(`知识库已存在文档\n${f.path}\n\n继续将覆盖原内容，确认覆盖？`)) return writeKb(f, true)
      return
    }
    throw e
  }
}
async function saveKbNew() {
  const f = kbNew.value
  if (!f.path.trim() || !f.content.trim()) return alert('请填写路径和内容')
  try {
    await writeKb(f)
    kbNew.value = null
    await loadKb()
    toast('已写入知识库，新会话提问即可检索到')
  } catch (e) { alert(e.message) }
}
async function delKb(f) {
  if (!confirm(`删除知识库文件\n${f.path}？（AI 后续将无法检索该文档）`)) return
  try {
    await api.aiKbDelete(f.path)
    await loadKb()
    toast('已删除')
  } catch (e) { alert(e.message) }
}
function kbSize(n) { return n > 1024 ? (n / 1024).toFixed(1) + ' KB' : n + ' B' }

// ================= AI 出题 =================
const genForm = ref({ cluster_id: 'five', count: 10, qtypes: '单选,判断' })
const genBusy = ref(false)
const genResult = ref(null) // {items, model, elapsed, raw}
const genMsg = ref('')

async function doGenerate() {
  genBusy.value = true
  genMsg.value = ''
  genResult.value = null
  try {
    genResult.value = await api.aiGenerate(genForm.value.cluster_id, genForm.value.count, genForm.value.qtypes)
  } catch (e) {
    genMsg.value = e.message
  }
  genBusy.value = false
}
async function saveQuestions() {
  if (!genResult.value?.items?.length) return
  try {
    const r = await api.aiQuestionsSave(genResult.value.items)
    alert(`已入库 ${r.count} 题（来源标注「AI 生成」），学生练习/模拟考会自动抽到`)
    genResult.value = null
  } catch (e) { alert(e.message) }
}

// ================= AI 判卷 =================
const attempts = ref([])
const gradeAttempt = ref(0)
const gradeBusy = ref(false)
const gradeResult = ref(null)
const gradeMsg = ref('')

async function loadAttempts() {
  try {
    const r = await api.adminExams('done')
    attempts.value = r.items.slice(0, 50)
  } catch (e) {
    gradeMsg.value = '加载已交卷失败：' + e.message
  }
}
onMounted(loadAttempts)
async function doGrade() {
  if (gradeBusy.value) return // 防重复提交
  if (!gradeAttempt.value) return alert('请选择一份已交卷')
  gradeBusy.value = true
  gradeMsg.value = ''
  gradeResult.value = null
  try {
    gradeResult.value = await api.aiGrade(gradeAttempt.value)
  } catch (e) {
    gradeMsg.value = e.message
  }
  gradeBusy.value = false
}
const gradeAttemptInfo = computed(() => attempts.value.find((a) => a.id === gradeAttempt.value))
const diffName = (n) => ({ 1: '低', 2: '中', 3: '高' }[n] || n)
</script>

<template>
  <div class="page">
    <div style="font-size: 19px; font-weight: 700; margin-bottom: 6px">AI 管理</div>
    <p style="font-size: 12.5px; color: var(--text-3); margin-bottom: 14px">
      模型自由选择（本机 DSH 实时目录）· 知识库维护 · AI 按簇出题入库 · AI 复核判卷
    </p>
    <div class="pills">
      <span v-for="t in tabs" :key="t.id" class="pill" :class="{ on: tab === t.id }" @click="tab = t.id">{{ t.label }}</span>
    </div>
    <div v-if="toastMsg" class="toast">{{ toastMsg }}</div>

    <!-- ============ 模型选择 ============ -->
    <template v-if="tab === 'model'">
      <div class="card">
        <div class="card-title">
          AI 模型选择
          <span v-if="modelCurrent" class="tag green" style="margin-left: 8px">当前（已设置）：{{ modelCurrent.model }}</span>
          <span v-else-if="modelCurrentSession" class="tag blue" style="margin-left: 8px">当前：{{ modelCurrentSession }}（会话默认，未手动设置）</span>
        </div>
        <p style="font-size: 12.5px; color: var(--text-3); margin: -4px 0 12px">
          选择后点击「应用」：AI 出题与判卷立即使用所选模型；学生端 AI 问答在下次提问时切换。模型目录来自本机 DSH 实时探测；渠道标注为 freehub 的是免费渠道（GLM / DeepSeek / SenseNova）。
        </p>
        <div v-if="modelMsg" class="card" style="padding: 10px 14px; margin-bottom: 12px; font-size: 13px; border-color: modelMsg.startsWith('✓') ? '#86efac' : '#fca5a5'; background: modelMsg.startsWith('✓') ? '#f0fdf4' : '#fef2f2'; color: modelMsg.startsWith('✓') ? '#15803d' : '#b91c1c">{{ modelMsg }}</div>
        <div v-if="modelLoading && !models.length" style="color: var(--text-3); padding: 20px 0">正在探测模型目录…（首次需与 DSH 建立任务会话，约 10–60 秒，请耐心等待）</div>
        <div class="model-pick" v-else>
          <div v-for="m in flatModels" :key="m.provider + m.id" class="mp" :class="{ on: modelPick?.id === m.id && modelPick?.provider === m.provider }" @click="pickModel(m)">
            <div class="mn">{{ m.label }}<span v-if="modelCurrent?.model === m.id && modelCurrent?.provider === m.provider" class="mtag">使用中</span></div>
            <div class="md">{{ m.providerName }}{{ m.description ? ' · ' + m.description : '' }}</div>
          </div>
        </div>
        <div style="display: flex; gap: 10px; margin-top: 16px">
          <button class="btn sm" :disabled="!modelPick || modelLoading" @click="applyModel">
            {{ modelLoading ? '切换中…' : '应用到平台（AI 问答 + 出题 + 判卷）' }}
          </button>
          <button class="btn sm ghost" @click="loadModels">↻ 重新探测</button>
        </div>
      </div>
    </template>

    <!-- ============ 知识库 ============ -->
    <template v-if="tab === 'kb'">
      <div class="card" style="margin-bottom: 14px">
        <div class="card-title">知识库文档（{{ kb.length }}）
          <span class="more" style="float: right" @click="kbNew = { path: '05-元数据/补充说明.md', content: '' }">＋ 新增文档</span>
        </div>
        <p style="font-size: 12px; color: var(--text-3); margin: -4px 0 10px">
          工作区：{{ kbRoot }} —— AI 老师每次问答前从这里检索取材；对**新会话**即时生效（已打开的学习会话需结束后重开才用新文档）。
        </p>
        <input v-model="kbFilter" placeholder="按路径过滤…" style="width: 260px; margin-bottom: 12px; padding: 7px 12px; border: 1px solid var(--line); border-radius: 8px; font-size: 13px" />
        <div v-if="kbLoading && !kb.length" style="color: var(--text-3)">加载中…</div>
        <div v-for="f in kbFiltered" :key="f.path" class="kb-item">
          <span style="font-size: 15px">{{ f.path.includes('01') ? '🏷' : f.path.includes('02') ? '📖' : f.path.includes('03') ? '🏆' : f.path.includes('04') ? '📜' : '🗂' }}</span>
          <div style="flex: 1; min-width: 0">
            <div class="kb-path">{{ f.path }}</div>
            <div class="kb-head">{{ f.head }}</div>
          </div>
          <div class="kb-meta num">{{ kbSize(f.size) }}<br />{{ new Date(f.mtime * 1000).toLocaleDateString('zh-CN') }}</div>
          <button class="btn sm ghost" style="color: #b91c1c; flex-shrink: 0" @click="delKb(f)">删除</button>
        </div>
      </div>

      <div v-if="kbNew" class="card">
        <div class="card-title">新增知识库文档<span class="more" style="float: right" @click="kbNew = null">✕</span></div>
        <div class="field"><label>相对路径（二级以内，.md）</label><input v-model="kbNew.path" placeholder="如：05-元数据/补充说明.md 或 03-赛/新增扣分点.md" /></div>
        <div class="field"><label>内容（Markdown）</label><textarea v-model="kbNew.content" rows="8" placeholder="# 标题&#10;正文…（AI 会按四栏取材并标注来源）"></textarea></div>
        <div style="display: flex; gap: 10px"><button class="btn sm" @click="saveKbNew">写入知识库</button><button class="btn sm ghost" @click="kbNew = null">取消</button></div>
      </div>
    </template>

    <!-- ============ AI 出题 ============ -->
    <template v-if="tab === 'gen'">
      <div class="card" style="margin-bottom: 14px">
        <div class="card-title">AI 按簇出题（基于知识库真实内容）</div>
        <div class="mgrid c3" style="margin: 10px 0 14px">
          <div class="field" style="margin: 0">
            <label>知识簇</label>
            <select v-model="genForm.cluster_id">
              <option v-for="c in CLUSTERS" :key="c.id" :value="c.id">{{ c.name }}</option>
            </select>
          </div>
          <div class="field" style="margin: 0">
            <label>题量（3–20）</label>
            <input type="number" v-model.number="genForm.count" min="3" max="20" />
          </div>
          <div class="field" style="margin: 0">
            <label>题型（逗号分隔）</label>
            <input v-model="genForm.qtypes" placeholder="单选,多选,判断" />
          </div>
        </div>
        <div style="display: flex; gap: 10px; align-items: center">
          <button class="btn sm" :disabled="genBusy" @click="doGenerate">
            {{ genBusy ? 'AI 出题中…（约 1–3 分钟，别关页面）' : '✍️ 生成题目' }}
          </button>
          <span style="font-size: 12px; color: var(--text-3)">流程：AI 读知识库取材 → 输出 JSON → 你审阅 → 一键入库（来源标注「AI 生成」）</span>
        </div>
        <div v-if="genMsg" style="margin-top: 12px; font-size: 13px; color: #b91c1c">⚠ {{ genMsg }}</div>
      </div>

      <div v-if="genResult" class="card">
        <div class="card-title">
          生成预览（{{ genResult.items.length }} 题 · {{ clusterName(genForm.cluster_id) }} · {{ genResult.model }} · 耗时 {{ genResult.elapsed }}s）
          <span class="op" style="float: right">
            <button class="btn sm" @click="saveQuestions">✓ 确认入库</button>
            <button class="btn sm ghost" @click="genResult = null">放弃</button>
          </span>
        </div>
        <div v-for="(q, i) in genResult.items" :key="i" class="qprev">
          <div class="qstem">{{ i + 1 }}.（{{ q.qtype }} · 难度 {{ diffName(q.difficulty) }}）{{ q.stem }}</div>
          <div v-if="q.options?.length" style="display: flex; flex-direction: column; gap: 2px">
            <div v-for="(o, j) in q.options" :key="j" class="qopt">{{ String.fromCharCode(65 + j) }}. {{ o }}</div>
          </div>
          <div class="qans">答案：{{ q.answer }}{{ q.qtype === '判断' ? (q.answer === 'A' ? '（对）' : '（错）') : '' }}</div>
        </div>
        <div v-if="genResult.raw" style="font-size: 11.5px; color: var(--text-3); margin-top: 8px">（解析不完整，AI 原始输出节选：{{ genResult.raw.slice(0, 160) }}…）</div>
      </div>
    </template>

    <!-- ============ AI 判卷 ============ -->
    <template v-if="tab === 'grade'">
      <div class="card" style="margin-bottom: 14px">
        <div class="card-title">AI 复核判卷</div>
        <p style="font-size: 12.5px; color: var(--text-3); margin: -4px 0 12px">
          选一份已交卷 → AI 逐题复核（标准答案对照 + 语义等价判断）→ 与规则判分对比，差异题高亮。
        </p>
        <div v-if="!attempts.length" style="font-size: 13px; color: var(--text-3); padding: 14px 16px; background: var(--bg); border-radius: 8px">
          暂无已交卷 —— 学生在「练习考试」完成日常练习或模拟考并交卷后，这里即可选择试卷做 AI 复核（小卷通常 10 秒左右，大卷 1–2 分钟）
        </div>
        <div v-else class="mgrid c2">
          <div class="field" style="margin: 0">
            <label>选择已交卷（最近 50 份）</label>
            <select v-model.number="gradeAttempt">
              <option :value="0" disabled>请选择…</option>
              <option v-for="a in attempts" :key="a.id" :value="a.id">
                {{ a.student_name }}（{{ a.student_no }}）· {{ a.exam_title }} · {{ a.score }} 分
              </option>
            </select>
          </div>
          <div style="display: flex; align-items: flex-end; gap: 8px">
            <button class="btn sm" :disabled="gradeBusy || !gradeAttempt" @click="doGrade">
              {{ gradeBusy ? 'AI 判卷中…（10 秒–2 分钟）' : '⚖️ 开始 AI 判卷' }}
            </button>
            <button class="btn sm ghost" :disabled="gradeBusy" @click="loadAttempts">↻ 刷新卷单</button>
          </div>
        </div>
        <div v-if="gradeMsg" style="margin-top: 12px; font-size: 13px; color: #b91c1c">⚠ {{ gradeMsg }}</div>
      </div>

      <div v-if="gradeResult" class="card">
        <div class="card-title">
          判卷结果 · {{ gradeAttemptInfo?.student_name }}
          <span class="tag blue" style="margin-left: 8px">规则判分 {{ gradeResult.rule_score }}</span>
          <span class="tag" :class="gradeResult.diff === 0 ? 'green' : 'red'" style="margin-left: 4px">AI 复核 {{ gradeResult.ai_score }}（差 {{ gradeResult.diff > 0 ? '+' : '' }}{{ gradeResult.diff }}）</span>
        </div>
        <p style="font-size: 12px; color: var(--text-3); margin: 2px 0 12px">{{ gradeResult.correct }} / {{ gradeResult.n }} 题判对 · 耗时 {{ gradeResult.elapsed }}s · 差异题（规则判错但 AI 认为对 / 反之）见下</p>
        <div v-for="d in gradeResult.detail" :key="d.qid" style="display: flex; gap: 10px; padding: 10px 0; border-bottom: 1px solid var(--line); font-size: 13px">
          <span style="width: 22px; height: 22px; border-radius: 50%; flex-shrink: 0; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 700; color: #fff"
                :style="{ background: d.correct ? '#22c55e' : '#e4393c' }">{{ d.correct ? '✓' : '✗' }}</span>
          <div style="flex: 1; min-width: 0">
            <div style="font-weight: 600">{{ d.stem }}</div>
            <div style="font-size: 12px; color: var(--text-2); margin-top: 2px">
              标准 {{ d.answer }} · 学生 {{ d.student_answer || '（未答）' }}
              <span v-if="d.reason" style="color: var(--text-3)">· AI：{{ d.reason }}</span>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>