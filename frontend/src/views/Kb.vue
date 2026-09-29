<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'

const router = useRouter()
const q = ref('')
const dim = ref('')
const items = ref(null)
const total = ref(0)
const loading = ref(false)
const err = ref('')
const doc = ref(null)      // {path, title, content}
let timer = null

const DIMS = [
  { id: '', name: '全部' },
  { id: '01-岗', name: '岗' },
  { id: '02-课', name: '课' },
  { id: '03-赛', name: '赛' },
  { id: '04-证', name: '证' },
  { id: '05-元数据', name: '元数据' }
]
const DIM_COLOR = { '01-岗': '#e4393c', '02-课': '#3b82f6', '03-赛': '#f5a623', '04-证': '#22c55e', '05-元数据': '#9ca3af' }

async function search() {
  loading.value = true
  err.value = ''
  try {
    const r = await api.kbSearch(q.value.trim(), dim.value)
    items.value = r.items
    total.value = r.total
  } catch (e) {
    err.value = e.message
  } finally {
    loading.value = false
  }
}
function onInput() {
  clearTimeout(timer)
  timer = setTimeout(search, 300)
}
watch(dim, search)
onMounted(search)
onBeforeUnmount(() => clearTimeout(timer))

// 迷你 markdown → html（先转义再还原标记，防注入）
function mdRender(text) {
  const esc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  const lines = text.split('\n')
  const out = []
  let inList = false
  for (let line of lines) {
    const raw = esc(line)
    const h = raw.match(/^(#{1,4})\s+(.*)$/)
    if (h) {
      if (inList) { out.push('</ul>'); inList = false }
      const lv = h[1].length
      out.push(`<h${lv + 2}>` + inline(h[2]) + `</h${lv + 2}>`)
      continue
    }
    if (/^\s*[-*]\s+/.test(raw)) {
      if (!inList) { out.push('<ul>'); inList = true }
      out.push('<li>' + inline(raw.replace(/^\s*[-*]\s+/, '')) + '</li>')
      continue
    }
    if (inList) { out.push('</ul>'); inList = false }
    if (/^\s*\|/.test(raw)) { out.push(`<div class="md-row">${inline(raw)}</div>`); continue }
    if (!raw.trim()) { out.push(''); continue }
    out.push(`<p>${inline(raw)}</p>`)
  }
  if (inList) out.push('</ul>')
  function inline(s) {
    return s.replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>').replace(/`([^`]+)`/g, '<code>$1</code>')
  }
  return out.join('\n')
}
const docHtml = computed(() => (doc.value ? mdRender(doc.value.content) : ''))

function open(d) {
  doc.value = d // 先显示标题占位，内容异步
}
async function loadDoc(d) {
  try {
    const r = await api.kbDoc(d.path)
    if (doc.value && doc.value.path === d.path) doc.value.content = r.content
  } catch (e) {
    doc.value && doc.value.path === d.path && (doc.value.content = '加载失败：' + e.message)
  }
}
function askAi() {
  if (!doc.value) return
  router.push({ path: '/learn', query: { ask: `「${doc.value.title}」这份文档的核心内容是什么？帮我划重点。` } })
}

// HTML 转义（v-html 前的强制步骤：KB 文档/检索片段不可信，防存储型 XSS）
function esc(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}
// 片段高亮（与后端一致的空白分词，逐词高亮）；先转义再插入 <mark>，杜绝 HTML 注入
function hi(s) {
  let out = esc(s)
  for (const k of q.value.trim().split(/\s+/).slice(0, 8)) {
    if (!k) continue
    const kk = esc(k) // 关键词同样转义后与转义文本匹配（& < > 等字符一致）
    if (!kk) continue
    out = out.replace(new RegExp(kk.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi'),
      (m) => '<mark>' + m + '</mark>')
  }
  return out
}
</script>

<template>
  <div class="page">
    <div class="khead">
      <div>
        <div class="kt">知识库</div>
        <div class="ks">46 份岗课赛证原始文档 · 全文检索 · 点击读原文</div>
      </div>
      <input v-model="q" class="ksearch" placeholder="搜索文档内容，如：Morse 量表 / 制动 / 上报时限…" @input="onInput" @keyup.enter="search" />
    </div>

    <div class="pills">
      <span v-for="d in DIMS" :key="d.id" class="pill" :class="{ on: dim === d.id }" @click="dim = d.id">{{ d.name }}</span>
      <span class="kcount" v-if="items">{{ q ? `${total} 个结果` : `共 ${total} 份文档` }}</span>
    </div>

    <div v-if="err" class="card" style="border-color: #fca5a5; color: #b91c1c">加载失败：{{ err }} <button class="btn sm" style="margin-left: 12px" @click="search">重试</button></div>

    <div v-else class="kgrid">
      <div v-if="loading" class="kloading">🔍 检索中…</div>
      <button v-for="it in items" :key="it.path" class="kcard" @click="open(it); loadDoc(it)">
        <span class="ktag" :style="{ background: DIM_COLOR[it.dim] + '14', color: DIM_COLOR[it.dim] }">{{ it.dim.slice(3, 4) || it.dim }}</span>
        <div class="kinfo">
          <div class="ktitle">{{ it.title }}</div>
          <div v-if="it.snippet" class="ksnip" v-html="hi(it.snippet)"></div>
          <div class="kmeta">{{ it.path }} · {{ Math.round(it.size / 1024) }} KB<template v-if="q && it.score"> · 相关度 {{ it.score }}</template></div>
        </div>
        <span class="karrow">›</span>
      </button>
      <div v-if="items && !items.length && !loading" class="card" style="color: var(--text-3)">没有匹配「{{ q }}」的文档 —— 换个词，或去「学习中心」问 AI 老师</div>
    </div>

    <!-- 文档阅读器 -->
    <div v-if="doc" class="dmask" @click.self="doc = null">
      <div class="dbox">
        <div class="dhead">
          <div>
            <div class="dtitle">{{ doc.title }}</div>
            <div class="dpath">{{ doc.path }}</div>
          </div>
          <div class="dact">
            <button class="btn sm ghost" @click="askAi">问 AI 老师</button>
            <button class="btn sm" @click="doc = null">关闭</button>
          </div>
        </div>
        <div class="dbody" v-html="docHtml"></div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.khead { display: flex; justify-content: space-between; align-items: flex-end; gap: 16px; margin-bottom: 14px; }
.kt { font-size: 19px; font-weight: 700; }
.ks { font-size: 12px; color: var(--text-3); margin-top: 2px; }
.ksearch { width: 420px; max-width: 55%; padding: 9px 14px; border: 1px solid var(--line); border-radius: 10px; font-size: 13px; outline: none; }
.ksearch:focus { border-color: var(--primary); }
.kcount { margin-left: auto; font-size: 12px; color: var(--text-3); }
.kgrid { display: flex; flex-direction: column; gap: 8px; }
.kcard { display: flex; align-items: center; gap: 12px; width: 100%; text-align: left; background: #fff; border: 1px solid var(--line); border-radius: 12px; padding: 12px 16px; cursor: pointer; transition: all .12s; }
.kcard:hover { border-color: var(--primary); box-shadow: 0 2px 10px rgba(228,57,60,.08); }
.kloading { grid-column: 1 / -1; font-size: 12.5px; color: var(--text-3); padding: 4px 2px; }
.ktag { font-size: 13px; font-weight: 700; padding: 6px 12px; border-radius: 8px; min-width: 40px; text-align: center; }
.kinfo { flex: 1; min-width: 0; }
.ktitle { font-size: 13.5px; font-weight: 600; }
.ksnip { font-size: 12px; color: var(--text-2); margin-top: 3px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.ksnip :deep(mark) { background: #fde68a; color: inherit; border-radius: 3px; padding: 0 2px; }
.kmeta { font-size: 11px; color: var(--text-3); margin-top: 3px; }
.karrow { font-size: 20px; color: var(--text-3); }
.dmask { position: fixed; inset: 0; background: rgba(15,23,42,.45); z-index: 60; display: flex; align-items: center; justify-content: center; padding: 24px; }
.dbox { background: #fff; border-radius: 14px; width: min(860px, 100%); max-height: 86vh; display: flex; flex-direction: column; overflow: hidden; }
.dhead { display: flex; justify-content: space-between; align-items: center; padding: 14px 18px; border-bottom: 1px solid var(--line); }
.dtitle { font-size: 15px; font-weight: 700; }
.dpath { font-size: 11.5px; color: var(--text-3); margin-top: 2px; }
.dact { display: flex; gap: 8px; }
.dbody { padding: 18px 22px; overflow-y: auto; font-size: 13px; line-height: 1.85; color: var(--text-1); }
.dbody :deep(h3) { font-size: 15px; margin: 16px 0 8px; }
.dbody :deep(h4) { font-size: 14px; margin: 14px 0 6px; }
.dbody :deep(p) { margin: 6px 0; }
.dbody :deep(ul) { margin: 6px 0; padding-left: 20px; }
.dbody :deep(li) { margin: 3px 0; }
.dbody :deep(code) { background: #f1f5f9; border-radius: 4px; padding: 1px 5px; font-size: 12px; }
.dbody :deep(.md-row) { font-family: ui-monospace, monospace; font-size: 12px; color: var(--text-2); white-space: pre; }
@media (max-width: 900px) {
  .khead { flex-direction: column; align-items: stretch; }
  .ksearch { width: 100%; max-width: none; }
}
</style>