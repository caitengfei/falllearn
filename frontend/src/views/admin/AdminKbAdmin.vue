<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../../api'

const data = ref(null)
const kw = ref('')
const modal = ref(null)
const cfg = ref({ embed: null, rerank: null })
const toastMsg = ref('')
const err = ref('')
const embedding = ref('')  // 'all' | docPath | ''

function toast(m) { toastMsg.value = m; setTimeout(() => (toastMsg.value = ''), 2600) }
function fmtTime(t) { return t ? new Date(t * 1000).toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : '—' }

const filtered = computed(() => {
  if (!data.value) return []
  const k = kw.value.trim().toLowerCase()
  if (!k) return data.value.items
  return data.value.items.filter((x) => x.title.toLowerCase().includes(k) || x.path.toLowerCase().includes(k) || x.snippet.toLowerCase().includes(k))
})

async function load() {
  err.value = ''
  try {
    const [d, c] = await Promise.all([api.kbAdmin(), api.kbConfig()])
    data.value = d
    cfg.value = {
      embed: c.embed || { base_url: '', api_key: '', model: '' },
      rerank: c.rerank || { base_url: '', api_key: '', model: '' }
    }
  } catch (e) {
    err.value = e.message
  }
}
onMounted(load)

function openCreate() {
  if (!data.value) return
  modal.value = { mode: 'create', dim: data.value.dims[0], title: '', content: '', path: '', tab: 'text', file: null, saving: false }
}
async function openEdit(it) {
  try {
    const doc = await api.kbDoc(it.path)
    const body = (doc.content || '').replace(/^#\s*[^\n]*\n+/, '').replace(/^>\s*来源：[^\n]*\n+/, '')
    modal.value = { mode: 'edit', dim: it.dim, title: it.title, content: body, path: it.path, tab: 'text', file: null, saving: false }
  } catch (e) { alert('读取文档失败：' + e.message) }
}

async function saveModal() {
  const m = modal.value
  m.saving = true
  try {
    if (m.mode === 'create' && m.tab === 'file') {
      if (!m.file) throw new Error('请选择文件')
      const r = await api.kbUpload(m.file, m.dim, m.title)
      toast(`已上传并入库：${r.path}（${r.chars} 字）`)
    } else {
      const r = await api.kbSave({ dim: m.dim, title: m.title, content: m.content, path: m.path })
      toast(r.created ? '已新增' : '已保存')
    }
    modal.value = null
    await load()
  } catch (e) {
    alert(e.message)
  } finally {
    if (modal.value) modal.value.saving = false
  }
}

async function del(it) {
  if (!confirm(`删除「${it.title}」？（移入回收站 knowledge/.trash，可人工恢复）`)) return
  try {
    await api.kbDelete(it.path)
    toast('已删除')
    await load()
  } catch (e) { alert(e.message) }
}

async function embDoc(path) {
  if (!cfg.value.embed?.configured) return alert('请先在下方「向量/重排模型」配置嵌入 API 并保存')
  embedding.value = path
  try {
    const r = await api.kbEmbed(path)
    toast(`已向量化 ${r.chunks} 块（${r.model}）`)
  } catch (e) { alert('向量化失败：' + e.message) }
  finally { embedding.value = '' }
}
async function embAll() {
  if (!cfg.value.embed?.configured) return alert('请先在下方「向量/重排模型」配置嵌入 API 并保存')
  if (!confirm(`将全库 ${data.value.total} 篇文档分块调用嵌入 API（按字数计费，确认？）`)) return
  embedding.value = 'all'
  try {
    const r = await api.kbEmbed('')
    toast(`全库已向量化：${r.docs} 篇 / ${r.chunks} 块（${r.model}）`)
  } catch (e) { alert('向量化失败：' + e.message) }
  finally { embedding.value = '' }
}

async function saveCfg(kind) {
  const c = cfg.value[kind]
  try {
    await api.kbConfigSave(kind, { base_url: c.base_url, api_key: c.api_key, model: c.model })
    toast(kind === 'embed' ? '嵌入配置已保存' : '重排配置已保存')
    await load()
  } catch (e) { alert(e.message) }
}
</script>

<template>
  <div class="page">
    <div style="display: flex; align-items: center; margin-bottom: 14px; flex-wrap: wrap; gap: 8px">
      <div style="font-size: 19px; font-weight: 700">📚 知识库管理</div>
      <span style="font-size: 12px; color: var(--text-3)">
        共 {{ data ? data.total : '…' }} 篇 · 与学生端「知识库」和 AI 问答同源 —— 保存后立即可被学生搜索、被 AI 引用
      </span>
      <button class="btn sm" style="margin-left: auto" :disabled="!data" @click="openCreate">＋ 新增知识</button>
    </div>

    <div v-if="toastMsg" class="toast">{{ toastMsg }}</div>
    <div v-if="err" class="card" style="border-color: #fca5a5; color: #b91c1c; margin-bottom: 14px">
      加载失败：{{ err }} <button class="btn sm" style="margin-left: 12px" @click="load">重试</button>
    </div>

    <!-- 分类统计 -->
    <div v-if="data" class="stat-grid">
      <div v-for="(s, d) in data.stats" :key="d" class="stat-card">
        <div class="stat-d">{{ d }}</div>
        <div class="stat-n">{{ s.count }} <i>篇</i></div>
        <div class="stat-c">{{ s.chars.toLocaleString() }} 字</div>
      </div>
    </div>

    <!-- 文档列表 -->
    <div v-if="data" class="card">
      <div style="display: flex; gap: 10px; align-items: center; margin-bottom: 10px; flex-wrap: wrap">
        <input v-model="kw" placeholder="搜标题 / 路径 / 摘要" style="width: 240px" />
        <span style="font-size: 12px; color: var(--text-3)">{{ filtered.length }} 篇</span>
        <button class="btn sm ghost" style="margin-left: auto" :disabled="embedding !== ''" @click="embAll">
          {{ embedding === 'all' ? '全库向量化中…' : '⚡ 全库向量化' }}
        </button>
      </div>
      <table class="atable">
        <thead><tr><th>文档</th><th>分类</th><th>字数</th><th>更新时间</th><th>操作</th></tr></thead>
        <tbody>
          <tr v-for="it in filtered" :key="it.path">
            <td>
              <b>{{ it.title }}</b>
              <div style="font-size: 11.5px; color: var(--text-3); max-width: 430px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap">{{ it.snippet || it.path }}</div>
            </td>
            <td><span class="tag gray">{{ it.dim }}</span></td>
            <td class="num">{{ it.chars.toLocaleString() }}</td>
            <td class="num">{{ fmtTime(it.mtime) }}</td>
            <td style="white-space: nowrap">
              <button class="btn sm ghost" :disabled="embedding !== ''" @click="embDoc(it.path)">{{ embedding === it.path ? '向量化中…' : '向量化' }}</button>
              <button class="btn sm ghost" @click="openEdit(it)">编辑</button>
              <button class="btn sm ghost" style="color: #b91c1c" @click="del(it)">删除</button>
            </td>
          </tr>
          <tr v-if="!filtered.length"><td colspan="5" style="color: var(--text-3); text-align: center; padding: 24px">无匹配文档</td></tr>
        </tbody>
      </table>
    </div>

    <!-- 向量 / 重排模型配置 -->
    <div v-if="data" class="card">
      <div class="card-title">🧮 向量 / 重排模型（可选 · 知识量大时启用）</div>
      <div style="font-size: 12px; color: var(--text-3); margin: -4px 0 12px; line-height: 1.7">
        默认不配置 = 纯本地关键词检索（现状不变）。配置后：① 可对文档分块向量化；② 学生端检索自动走「关键词 + 向量余弦 + 重排」三级融合，长尾问题召回率更高。<br>
        ⚠️ 合规提示：配置后本库全文与学生的检索词会发送到你选择的 API 服务，请确认数据合规后再启用（OpenAI 兼容格式）。
      </div>
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px">
        <div v-for="k in ['embed', 'rerank']" :key="k" style="border: 1px solid var(--line); border-radius: 10px; padding: 12px">
          <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 10px">
            <b style="font-size: 13.5px">{{ k === 'embed' ? '嵌入 Embedding（向量化）' : '重排 Rerank（结果重排）' }}</b>
            <span class="tag" :class="cfg[k]?.configured ? 'green' : 'gray'">{{ cfg[k]?.configured ? '已配置' : '未配置' }}</span>
          </div>
          <div class="field"><label>API 地址</label><input v-model="cfg[k].base_url" placeholder="如 https://api.example.com/v1" /></div>
          <div class="field"><label>API Key</label><input type="password" v-model="cfg[k].api_key" placeholder="掩码显示；不修改则保持原密钥" /></div>
          <div class="field"><label>模型名</label><input v-model="cfg[k].model" :placeholder="k === 'embed' ? '如 bge-m3 / text-embedding-3-small' : '如 bge-reranker-v2-m3 / cohere-rerank'" /></div>
          <button class="btn sm" @click="saveCfg(k)">保存{{ k === 'embed' ? '嵌入' : '重排' }}配置</button>
        </div>
      </div>
    </div>

    <!-- 新增 / 编辑弹窗 -->
    <div v-if="modal" class="mask" @click.self="modal = null">
      <div class="modal" style="max-width: 660px">
        <div class="modal-h">{{ modal.mode === 'edit' ? '编辑知识' : '新增知识' }}<span class="more" @click="modal = null">✕</span></div>

        <template v-if="modal.mode === 'create'">
          <div style="display: flex; gap: 8px; margin-bottom: 12px">
            <button class="btn sm" :style="modal.tab === 'text' ? {} : { background: 'var(--line)', color: 'var(--text-2)' }" @click="modal.tab = 'text'">手动录入</button>
            <button class="btn sm" :style="modal.tab === 'file' ? {} : { background: 'var(--line)', color: 'var(--text-2)' }" @click="modal.tab = 'file'">文件上传</button>
          </div>
          <div class="field"><label>分类</label>
            <select v-model="modal.dim"><option v-for="d in data.dims" :key="d" :value="d">{{ d }}</option></select>
          </div>
          <template v-if="modal.tab === 'text'">
            <div class="field"><label>标题</label><input v-model="modal.title" placeholder="如：跌倒五步处置操作细则" /></div>
            <div class="field"><label>正文</label><textarea v-model="modal.content" rows="9" placeholder="粘贴教学内容（至少 20 字）…"></textarea></div>
          </template>
          <template v-else>
            <div class="field"><label>文件（.txt / .pdf / .docx / .md，≤8MB）</label>
              <input type="file" accept=".txt,.pdf,.docx,.md" @change="(e) => (modal.file = e.target.files[0])" />
            </div>
            <div v-if="modal.file" style="font-size: 12px; color: var(--text-3); margin: -6px 0 10px">
              已选：{{ modal.file.name }}（{{ (modal.file.size / 1024).toFixed(0) }}KB）—— 上传后自动提取文字入库，原件存档备查
            </div>
            <div class="field"><label>标题（可选，默认用文件名）</label><input v-model="modal.title" placeholder="留空则用文件名" /></div>
          </template>
        </template>

        <template v-else>
          <div class="field"><label>分类</label>
            <select v-model="modal.dim"><option v-for="d in data.dims" :key="d" :value="d">{{ d }}</option><option v-if="!data.dims.includes(modal.dim)" :value="modal.dim">{{ modal.dim }}</option></select>
          </div>
          <div class="field"><label>标题</label><input v-model="modal.title" /></div>
          <div class="field"><label>正文</label><textarea v-model="modal.content" rows="12"></textarea></div>
        </template>

        <div style="display: flex; gap: 10px; margin-top: 14px">
          <button class="btn sm" :disabled="modal.saving" @click="saveModal">{{ modal.saving ? '保存中…' : '保存' }}</button>
          <button class="btn sm ghost" @click="modal = null">取消</button>
        </div>
        <div style="font-size: 11.5px; color: var(--text-3); margin-top: 10px; line-height: 1.7">
          💡 保存后学生端「知识库」搜索与 AI 问答立即可见（同一数据源，无需另行发布）。
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.stat-grid {
  display: grid; grid-template-columns: repeat(6, 1fr); gap: 10px; margin-bottom: 14px;
}
.stat-card {
  border: 1px solid var(--line); border-radius: 10px; padding: 10px 12px; background: #fff;
}
.stat-d { font-size: 12px; color: var(--text-3); font-weight: 600; }
.stat-n { font-size: 20px; font-weight: 700; margin-top: 2px; font-family: var(--mono, monospace); }
.stat-n i { font-style: normal; font-size: 11px; color: var(--text-3); font-weight: 400; }
.stat-c { font-size: 11.5px; color: var(--text-3); margin-top: 1px; }
@media (max-width: 900px) { .stat-grid { grid-template-columns: repeat(3, 1fr); } }
</style>