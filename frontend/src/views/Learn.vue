<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api, auth, CLUSTERS, CLUSTER_QCOUNT, CLUSTER_KNOWLEDGE, clusterName } from '../api'

const route = useRoute()

// ---------- 聊天 ----------
const flow = ref([]) // {role:'me'|'ai', text} | {role:'q', question} | {role:'typing'}
const input = ref('')
const busy = ref(false)
const session = ref(null)
const logId = ref(null)
const inputEl = ref(null)
let pollTimer = null
let streamCtrl = null
let bubbleSeq = 0  // 流式气泡唯一 id（filter 后用 bid 定位，避免 raw/proxy 身份比较失效）

function push(m) {
  flow.value.push(m)
  nextTick(scrollBottom)
}
function scrollBottom() {
  const el = document.querySelector('.chat-flow')
  if (el) el.scrollTop = el.scrollHeight
}

async function send(preFilled) {
  const q = (preFilled ?? input.value).trim()
  if (!q || busy.value) return
  input.value = ''
  busy.value = true
  push({ role: 'me', text: q })
  push({ role: 'typing' })
  try {
    const r = await api.ask(q)
    session.value = r.session_id
    logId.value = r.log_id
    startStream(r.session_id, r.log_id)
  } catch (e) {
    flow.value.pop()
    push({ role: 'ai', text: '出错了：' + e.message })
    busy.value = false
  }
}

// —— SSE 流式接收（直连通道）：逐字渲染；失败自动回落轮询 ——
// 注意：必须通过 flow.value 的 reactive proxy 改 text（直接改 raw 对象不触发响应式，实测整段滞后到末尾才渲染）
async function startStream(sid, logIdV) {
  stopPoll()
  flow.value = flow.value.filter((m) => m.role !== 'typing' && !m.streaming)
  const bid = ++bubbleSeq
  flow.value.push({ role: 'ai', text: '', streaming: true, bid })
  const live = flow.value[flow.value.length - 1]
  nextTick(scrollBottom)
  streamCtrl = new AbortController()
  try {
    const res = await fetch(`/api/learn/stream?session_id=${encodeURIComponent(sid)}&log_id=${logIdV}`, {
      headers: { authorization: `Bearer ${auth.token}` }, signal: streamCtrl.signal
    })
    if (!res.ok || !res.body) throw new Error('stream 不可用')
    const reader = res.body.getReader()
    const dec = new TextDecoder()
    let bfr = ''
    while (true) {
      const rd = await reader.read()
      if (rd.done) break
      bfr += dec.decode(rd.value, { stream: true })
      let i
      while ((i = bfr.indexOf('\n\n')) >= 0) {
        const line = bfr.slice(0, i).trim()
        bfr = bfr.slice(i + 2)
        if (!line.startsWith('data: ')) continue
        let msg
        try { msg = JSON.parse(line.slice(6)) } catch { continue }
        if (msg.type === 'chunk') {
          live.text += msg.t
          nextTick(scrollBottom)
        } else if (msg.type === 'done') {
          live.text = msg.answer || live.text
          live.streaming = false
          busy.value = false
        } else if (msg.type === 'question') {
          flow.value = flow.value.filter((m) => m.bid !== bid)
          push({ role: 'q', question: msg.question, logId: logIdV })
          busy.value = false
        } else if (msg.type === 'failed' || msg.type === 'error') {
          live.text = '😵 ' + (msg.error || '出错了，请再试一次')
          live.streaming = false
          busy.value = false
        }
      }
    }
    live.streaming = false
    if (busy.value) startPoll() // 连接中断但状态未到：回落轮询兜底
  } catch (e) {
    if (e.name === 'AbortError') return
    live.streaming = false
    if (busy.value) startPoll() // 网络异常：回落轮询兜底
  }
}

function startPoll() {
  stopPoll()
  // 3s→5s：AI 生成 30-90s，3s 对 LLM 场景过密（性能专家评审意见）
  pollTimer = setInterval(poll, 5000)
  poll()
}
function stopPoll() {
  if (pollTimer) clearInterval(pollTimer)
  pollTimer = null
}
async function poll() {
  if (!session.value) return
  try {
    const s = await api.status(session.value, logId.value)
    if (s.status === 'question') {
      flow.value = flow.value.filter((m) => m.role !== 'typing' && !m.streaming)
      push({ role: 'q', question: s.question, logId: logId.value })
      stopPoll()
      return
    }
    if (s.status === 'done') {
      flow.value = flow.value.filter((m) => m.role !== 'typing' && !m.streaming)
      push({ role: 'ai', text: s.answer })
      busy.value = false
      stopPoll()
    }
    if (s.status === 'failed') {
      flow.value = flow.value.filter((m) => m.role !== 'typing' && !m.streaming)
      push({ role: 'ai', text: '😵 ' + (s.error || '出错了，请再试一次') })
      busy.value = false
      stopPoll()
    }
  } catch {
    /* 网络抖动继续轮询 */
  }
}

async function pickOption(log_id, idx) {
  busy.value = true
  flow.value.push({ role: 'me', text: '（已选择选项 ' + (idx + 1) + '）' })
  nextTick(scrollBottom)
  try {
    await api.answer(log_id, idx)
    push({ role: 'typing' })
    startStream(session.value, logId.value)
  } catch (e) {
    push({ role: 'ai', text: '应答失败：' + e.message })
    busy.value = false
  }
}

// 四栏渲染（剥 markdown 加粗标记）
function clean(s) {
  return s.replace(/\*\*/g, '').trim()
}
function cols(text) {
  const m = text.match(/(【岗】[\s\S]*?)(?=【课】|$)/)
  const k = text.match(/(【课】[\s\S]*?)(?=【赛】|$)/)
  const s = text.match(/(【赛】[\s\S]*?)(?=【证】|$)/)
  const z = text.match(/(【证】[\s\S]*)$/)
  const pre = text.slice(0, text.indexOf('【岗】'))
  if (!m) return null
  return {
    pre: clean(pre),
    items: [
      { name: '岗', color: '#e4393c', body: clean(m[1]) },
      { name: '课', color: '#3b82f6', body: k ? clean(k[1]) : '' },
      { name: '赛', color: '#f5a623', body: s ? clean(s[1]) : '' },
      { name: '证', color: '#22c55e', body: z ? clean(z[1]) : '' }
    ].filter((x) => x.body.trim())
  }
}
// 来源解析：按行取「（来源：…）」整段（行内可能有嵌套括号）
function sources(text) {
  const out = new Set()
  for (const line of text.split('\n')) {
    const i = line.indexOf('（来源：')
    if (i < 0) continue
    const seg = line.slice(i)
    const j = seg.lastIndexOf('）')
    if (j > i) out.add(seg.slice(i + 3, j))
  }
  return [...out].map((s) => s.trim())
}

// ---------- 知识卡片 / 簇抽屉 ----------
const kfilter = ref('all')
const mastery = ref({})
const onlyWeak = ref(false)
const openCluster = ref(null)
const wrongByCluster = ref({})

const qcounts = ref({ ...CLUSTER_QCOUNT }) // /api/meta/clusters 实时值，失败回退静态
const kcards = computed(() =>
  CLUSTERS.filter((c) => kfilter.value === 'all' || c.id === kfilter.value)
    .map((c) => ({
      ...c, level: mastery.value[c.id] ?? 0,
      qcount: qcounts.value[c.id] ?? 0, wrong: wrongByCluster.value[c.id] || 0
    }))
    .filter((c) => !onlyWeak.value || c.level < 60)
)
const allWeakEmpty = computed(() => onlyWeak.value && kcards.value.length === 0)

// 怎么问 AI（05-元数据/学生使用指南.md 摘编）
const ASK_TIPS = [
  { q: '老人摔倒了怎么办', d: '直接问技能点' },
  { q: '考证考不考跌倒？实操怎么考？', d: '备考（证书）' },
  { q: '大赛跌倒环节怎么扣分？', d: '备赛（大赛）' },
  { q: '展开【赛】', d: '追问技巧：只讲深某一栏' }
]

async function load() {
  api.metaClusters().then((m) => {
    if (m.items?.length) qcounts.value = Object.fromEntries(m.items.map((x) => [x.id, x.qcount]))
  }).catch(() => {})
  try {
    const me = await api.me()
    mastery.value = me.mastery || {}
    // 历史回放：构建消息数组（不能用 map 里 push 副作用——会产出 undefined 数组致白屏）
    const lh = await api.learnHistory()
    const msgs = (lh.items || []).slice().reverse().flatMap((x) => [
      { role: 'me', text: x.question },
      { role: 'ai', text: x.answer }
    ])
    flow.value = msgs
    const wl = await api.wrongList('active')
    wrongByCluster.value = (wl.items || []).reduce((acc, x) => ((acc[x.cluster] = (acc[x.cluster] || 0) + 1), acc), {})
    // 深链：/learn?cluster=xxx 预置簇过滤+抽屉居中；/learn?k=xxx 预填提问；/learn?ask=xxx 自动发送
    if (route.query.cluster && CLUSTERS.some((c) => c.id === route.query.cluster)) {
      kfilter.value = route.query.cluster
      openCluster.value = route.query.cluster
      nextTick(() => document.getElementById('cluster-drawer')?.scrollIntoView({ behavior: 'smooth', block: 'center' }))
    }
    if (route.query.k) {
      input.value = String(route.query.k)
      nextTick(() => inputEl.value?.focus())
    }
    if (route.query.ask) {
      nextTick(() => send(String(route.query.ask)))
    }
  } catch (e) {
    console.error(e)
  }
}

function askCluster() {
  const name = clusterName(openCluster.value)
  openCluster.value = null
  send(name + ' 要点')
}

onMounted(load)
onBeforeUnmount(() => {
  stopPoll()
  if (streamCtrl) streamCtrl.abort()
})
</script>

<template>
  <div class="page">
    <div class="learn-grid">
      <!-- 左：对话 -->
      <div class="card chat-card">
        <div class="card-title">🎓 AI 老师 <span class="more">答案均取材自 46 份知识库文档并标注来源</span></div>
        <div class="chat-flow">
          <div v-if="!flow.length" class="empty" style="padding: 70px 20px">
            <div style="font-size: 40px">👋</div>
            <div style="margin-top: 10px; font-size: 14px; color: var(--text-2)">我是你的 AI 老师，只答「老年人跌倒」一个技能点，<br>但会按【岗】【课】【赛】【证】四栏讲透，每栏标来源。</div>
            <div style="display: flex; gap: 8px; flex-wrap: wrap; justify-content: center; margin-top: 16px">
              <button v-for="t in ASK_TIPS" :key="t.q" class="chip-ask" @click="send(t.q)">
                {{ t.q }} <span style="opacity: .6">{{ t.d }}</span>
              </button>
            </div>
          </div>
          <div v-for="(m, i) in flow" :key="i" class="msg" :class="m.role">
            <template v-if="m.role === 'q'">
              <div class="qcard">
                <div class="qtitle">❓ {{ m.question.header || '请选择' }}</div>
                <div class="qdesc" style="margin-bottom: 10px">{{ m.question.question }}</div>
                <div v-for="o in m.question.options" :key="o.id" class="qopt" @click="pickOption(m.logId, Number(o.id))">
                  <b>{{ o.label }}</b>
                  <div v-if="o.description" class="qopt-d">{{ o.description }}</div>
                </div>
              </div>
            </template>
            <template v-else>
              <div class="mava">{{ m.role === 'me' ? '我' : 'AI' }}</div>
              <div class="bubble" :class="m.role">
                <template v-if="m.role === 'typing'"><span class="typing"><i></i><i></i><i></i></span></template>
                <template v-else-if="m.role === 'ai' && cols(m.text)">
                  <div v-if="cols(m.text).pre" class="pre">{{ cols(m.text).pre }}</div>
                  <div class="fourcol">
                    <div v-for="c in cols(m.text).items" :key="c.name" class="col">
                      <div class="col-h" :style="{ background: c.color + '14', color: c.color }">{{ c.name }}</div>
                      <div class="col-b">{{ c.body }}</div>
                    </div>
                  </div>
                </template>
                <template v-else-if="m.role === 'ai'">
                  <div class="plain">{{ m.text }}<span v-if="m.streaming" class="caret">▍</span></div>
                </template>
                <template v-else>{{ m.text }}</template>
                <div v-if="m.role === 'ai' && sources(m.text).length" class="src">
                  来源：{{ sources(m.text).join('；') }}
                </div>
              </div>
            </template>
          </div>
        </div>
        <div class="chat-input">
          <textarea v-model="input" ref="inputEl" rows="2" placeholder="问我任何关于老年人跌倒的问题，如：Morse 量表怎么判风险等级？"
            @keyup.enter.exact="send()"></textarea>
          <button class="btn" :disabled="busy || !input.trim()" @click="send()">
            <span v-if="busy" class="spinner"></span>
            {{ busy ? '思考中…' : '发送' }}
          </button>
        </div>
      </div>

      <!-- 右：知识地图 -->
      <div>
        <div class="card">
          <div class="card-title">🗺 知识地图 <span class="more" style="font-weight: 400">点击一簇看知识点</span></div>
          <div class="chips">
            <span class="chip" :class="{ on: kfilter === 'all' }" @click="kfilter = 'all'">全部</span>
            <span v-for="c in CLUSTERS" :key="c.id" class="chip" :class="{ on: kfilter === c.id }" @click="kfilter = c.id">{{ c.name }}</span>
          </div>
          <label class="onlyweak">
            <input type="checkbox" v-model="onlyWeak" /> 仅看薄弱（&lt;60）
          </label>
          <div v-if="allWeakEmpty" style="font-size: 12px; color: var(--text-3); padding: 8px 2px">没有低于 60% 的薄弱簇（全部达标）—— 取消筛选查看全部 6 簇</div>
          <div class="kmap">
            <div v-for="c in kcards" :key="c.id" class="kcard" @click="openCluster = c.id">
              <span v-if="c.id === 'five' || c.id === 'fracture'" class="badge-corner">核心</span>
              <div class="cover" :style="{ background: c.color }">{{ c.short || c.name.slice(0, 2) }}</div>
              <div class="kbody">
                <div class="kname">{{ c.name }}</div>
                <div class="kmeta"><span class="mono">{{ c.qcount }} 题</span><span>掌握 {{ c.level }}%</span></div>
                <div class="kbar"><i :style="{ width: c.level + '%', background: c.color }"></i></div>
              </div>
            </div>
          </div>
        </div>

        <!-- 簇详解抽屉 -->
        <div v-if="openCluster" id="cluster-drawer" class="card mt16">
          <div class="card-title">
            {{ clusterName(openCluster) }} · 知识点详解
            <span class="more" @click="openCluster = null">关闭 ✕</span>
          </div>
          <ul class="cluster-kp">
            <li v-for="(kp, i) in (CLUSTER_KNOWLEDGE[openCluster] || [])" :key="i">{{ kp }}</li>
          </ul>
          <div style="font-size: 12px; color: var(--text-3); margin-top: 10px">
            题库 {{ qcounts[openCluster] ?? 0 }} 题 · 你的错题 {{ wrongByCluster[openCluster] || 0 }} 题
          </div>
          <button class="btn sm mt16" style="width: 100%" @click="askCluster()">帮我讲这一簇（AI 四栏详解）</button>
          <div style="font-size: 12px; color: var(--text-3); margin-top: 10px; line-height: 1.8">
            💡 追问技巧：回答出来后，可以接着问「展开【赛】」「第 3 条扣分点具体是什么操作？」
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.learn-grid { display: grid; grid-template-columns: 1fr 380px; gap: 16px; align-items: start; }
@media (max-width: 900px) { .learn-grid { grid-template-columns: 1fr; } }
.bubble.ai { background: var(--bg); }
.msg.ai .mava { background: #e4393c; }
.msg.me .mava { background: #64748b; }
.chip-ask {
  border: 1px solid var(--line); background: #fff; border-radius: 14px;
  font-size: 12px; padding: 5px 12px; color: var(--text-2); transition: all .15s;
}
.chip-ask:hover { border-color: var(--primary); color: var(--primary); }
.cluster-kp {
  margin: 8px 0 0 18px; font-size: 13px; color: var(--text-2); line-height: 2;
}
.kbar {
  height: 5px; background: var(--bg); border-radius: 3px; overflow: hidden; margin-top: 6px;
}
.kbar i { display: block; height: 100%; border-radius: 3px; transition: width .4s; }
.kmap { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.kmap .kcard .cover { height: 56px; font-size: 18px; }
/* 四栏 */
.pre { font-size: 13px; color: var(--text-2); margin-bottom: 8px; }
.fourcol { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 6px; }
.fourcol .col { background: #fff; border: 1px solid var(--line); border-radius: 8px; overflow: hidden; }
.fourcol .col-h {
  font-size: 12px; font-weight: 700; padding: 3px 10px;
  display: flex; align-items: center; gap: 4px;
}
.fourcol .col-h::before { content: "【" attr(data-x) "】"; display: none; }
.fourcol .col-b {
  padding: 8px 10px; font-size: 12.5px; color: var(--text-2);
  white-space: pre-wrap; line-height: 1.75;
}
.plain { white-space: pre-wrap; line-height: 1.8; }
.caret { display: inline-block; margin-left: 1px; color: var(--primary); animation: caretblink 1s steps(1) infinite; }
@keyframes caretblink { 50% { opacity: 0; } }
.qtitle { font-size: 13px; font-weight: 700; margin-bottom: 4px; }
.qdesc { font-size: 13px; color: var(--text-2); }
.qopt {
  text-align: left; border: 1px solid var(--line); border-radius: 8px;
  padding: 9px 12px; font-size: 13px; margin-top: 6px; transition: all .12s;
}
.qopt:hover { border-color: var(--primary); background: var(--primary-light); }
.qopt-d { font-size: 11.5px; color: var(--text-3); margin-top: 2px; }
@media (max-width: 900px) {
  .fourcol { grid-template-columns: 1fr; }
}
</style>