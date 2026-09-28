<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../../api'

const notices = ref([])
const banners = ref([])
const nModal = ref(null)   // {id?, title, summary, content, start_date, end_date, pinned, enabled}
const bModal = ref(null)   // {id?, title, tag, sub, image, link, sort, enabled}
const msg = ref('')

const EMPTY_N = { id: null, title: '', summary: '', content: '', start_date: '', end_date: '', pinned: 0, enabled: 1 }
const EMPTY_B = { id: null, title: '', tag: '', sub: '', image: '', link: '/', sort: 0, enabled: 1 }

async function load() {
  err.value = ''
  try {
    const [n, b] = await Promise.all([api.notices(), api.banners()])
    notices.value = n.items
    banners.value = b.items
  } catch (e) {
    err.value = e.message
  }
}
onMounted(load)

const err = ref('')
function toast(t) { msg.value = t; setTimeout(() => (msg.value = ''), 2200) }
const maxSort = () => banners.value.reduce((m, b) => Math.max(m, b.sort || 0), 0)
function fmt(t) { return t ? new Date(t * 1000).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit' }) : '' }

// ---- 公告 ----
async function saveNotice() {
  const f = nModal.value
  if (!f.title.trim()) return alert('请填写标题')
  try {
    if (f.id) await api.noticeUpdate(f.id, f); else await api.noticeSave(f)
    nModal.value = null; await load(); toast('公告已保存')
  } catch (e) { alert(e.message) }
}
async function delNotice(n) {
  if (!confirm(`删除公告「${n.title}」？`)) return
  try {
    await api.noticeDelete(n.id); await load(); toast('已删除')
  } catch (e) { toast('删除失败：' + e.message) }
}
// 开关：串行 await + 失败回滚（修复 fire-and-forget 竞态）
async function toggleNotice(n, key) {
  const old = n[key]
  n[key] = n[key] ? 0 : 1
  try {
    await api.noticeUpdate(n.id, n)
    toast('已保存')
  } catch (e) {
    n[key] = old
    toast('保存失败：' + e.message)
  }
}

// ---- 轮播 ----
async function onPickImage(e) {
  const file = e.target.files[0]
  if (!file) return
  const ext = (file.name.split('.').pop() || '').toLowerCase()
  if (!['png', 'jpg', 'jpeg', 'webp', 'gif'].includes(ext)) {
    e.target.value = ''
    return alert('仅支持 png / jpg / jpeg / webp / gif 图片')
  }
  try {
    const r = await api.uploadImage(file)
    if (r.ok) { bModal.value.image = r.url; toast('图片已上传') }
    else alert(r.detail || '上传失败')
  } catch (err) { alert(err.message) }
}
async function saveBanner() {
  const f = bModal.value
  if (!f.title.trim()) return alert('请填写标题')
  try {
    if (f.id) await api.bannerUpdate(f.id, f); else await api.bannerSave(f)
    bModal.value = null; await load(); toast('轮播卡已保存')
  } catch (e) { alert(e.message) }
}
async function delBanner(b) {
  if (!confirm(`删除轮播卡「${b.title}」？`)) return
  try {
    await api.bannerDelete(b.id); await load(); toast('已删除')
  } catch (e) { toast('删除失败：' + e.message) }
}
// 上移/下移：重写相邻两张卡的 sort（修复传 banner 对象导致 422 被吞）
async function moveBanner(b, dir) {
  const i = banners.value.findIndex((x) => x.id === b.id)
  const j = i + dir
  if (j < 0 || j >= banners.value.length) return
  const a = { ...banners.value[i] }   // 被移动者
  const c = { ...banners.value[j] }   // 相邻者
  const sortOfC = c.sort || 0
  const sortOfA = a.sort || 0
  try {
    await Promise.all([
      api.bannerUpdate(a.id, { ...a, sort: sortOfC }),  // a 换到 c 的位置
      api.bannerUpdate(c.id, { ...c, sort: sortOfA })   // c 换到 a 的位置
    ])
    await load()
    toast('顺序已更新')
  } catch (e) {
    await load()
    toast('排序失败：' + e.message)
  }
}
async function toggleBanner(b, key) {
  const old = b[key]
  b[key] = b[key] ? 0 : 1
  try {
    await api.bannerUpdate(b.id, b)
    toast('已保存')
  } catch (e) {
    b[key] = old
    toast('保存失败：' + e.message)
  }
}
function openBannerModal() {
  bModal.value = { ...EMPTY_B, sort: maxSort() + 1 } // 新增默认追加到末尾
}
</script>

<template>
  <div class="page">
    <div style="font-size: 19px; font-weight: 700; margin-bottom: 16px">业务管理 · 课程预告 & 主界面轮播</div>

    <div v-if="err" class="card" style="border-color: #fca5a5; color: #b91c1c; margin-bottom: 14px">加载失败：{{ err }}</div>
    <div v-if="msg" class="toast">{{ msg }}</div>

    <!-- 课程预告 -->
    <div class="card" style="margin-bottom: 16px">
      <div class="card-title">课程预告 <span class="more" style="float: right" @click="nModal = { ...EMPTY_N }">＋ 新建预告</span></div>
      <table class="atable">
        <thead><tr><th>标题</th><th>摘要</th><th>生效区间</th><th>置顶</th><th>状态</th><th style="width: 130px">操作</th></tr></thead>
        <tbody>
          <tr v-for="n in notices" :key="n.id">
            <td style="font-weight: 600">{{ n.pinned ? '📌 ' : '' }}{{ n.title }}</td>
            <td style="color: var(--text-2); max-width: 260px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap">{{ n.summary }}</td>
            <td style="color: var(--text-3); font-size: 12px" class="num">{{ n.start_date || '不限' }} ~ {{ n.end_date || '不限' }}</td>
            <td>
              <span class="switch" :class="{ on: n.pinned === 1 }" @click="toggleNotice(n, 'pinned')">
                <i></i>
              </span>
            </td>
            <td>
              <span class="switch" :class="{ on: n.enabled === 1 }" @click="toggleNotice(n, 'enabled')">
                <i></i>
              </span>
            </td>
            <td><div class="op">
              <button @click="nModal = { ...n }">编辑</button>
              <button class="danger" @click="delNotice(n)">删除</button>
            </div></td>
          </tr>
          <tr v-if="!notices.length"><td colspan="6" style="color: var(--text-3); text-align: center; padding: 22px">暂无预告 —— 学生端首页顶部不显示公告条</td></tr>
        </tbody>
      </table>
    </div>

    <!-- 主界面轮播 -->
    <div class="card">
      <div class="card-title">主界面图片轮播 <span class="more" style="float: right" @click="openBannerModal">＋ 新增轮播卡</span></div>
      <p style="font-size: 12px; color: var(--text-3); margin: -4px 0 12px">
        学生端首页顶部轮播由这里驱动：支持上传背景图（≤4MB）或纯文字渐变卡；点击行为可配置跳转页面。
      </p>
      <table class="atable">
        <thead><tr><th style="width: 110px">预览</th><th>标题 / 标语</th><th>跳转</th><th style="width: 70px">排序</th><th style="width: 70px">启用</th><th style="width: 170px">操作</th></tr></thead>
        <tbody>
          <tr v-for="(b, i) in banners" :key="b.id">
            <td>
              <div style="width: 104px; height: 56px; border-radius: 8px; overflow: hidden; display: flex; align-items: center; justify-content: center; color: #fff; font-size: 12px; font-weight: 700"
                   :style="b.image ? {} : { background: 'linear-gradient(120deg, #b91c1c, #ef4444)' }">
                <img v-if="b.image" :src="b.image" style="width: 100%; height: 100%; object-fit: cover" />
                <span v-else>{{ b.title.length > 8 ? b.title.slice(0, 8) + '…' : b.title }}</span>
              </div>
            </td>
            <td>
              <div style="font-weight: 600">{{ b.title }}</div>
              <div style="font-size: 12px; color: var(--text-3)">{{ b.tag }} · {{ b.sub }}</div>
            </td>
            <td style="color: var(--text-3); font-size: 12px" class="num">{{ b.link }}</td>
            <td><div class="op">
              <button @click="moveBanner(b, -1)" title="上移">↑</button>
              <button @click="moveBanner(b, 1)" title="下移">↓</button>
            </div></td>
            <td>
              <span class="switch" :class="{ on: b.enabled === 1 }" @click="toggleBanner(b, 'enabled')">
                <i></i>
              </span>
            </td>
            <td><div class="op">
              <button @click="bModal = { ...b }">编辑</button>
              <button class="danger" @click="delBanner(b)">删除</button>
            </div></td>
          </tr>
          <tr v-if="!banners.length"><td colspan="6" style="color: var(--text-3); text-align: center; padding: 22px">暂无轮播卡 —— 学生端首页将不显示轮播，点右上角「＋ 新增轮播卡」添加</td></tr>
        </tbody>
      </table>
    </div>

    <!-- 公告编辑弹窗 -->
    <div v-if="nModal" class="mask" @click.self="nModal = null">
      <div class="modal">
        <div class="modal-h">{{ nModal.id ? '编辑预告' : '新建课程预告' }}<span class="more" @click="nModal = null">✕</span></div>
        <div class="field"><label>标题 *</label><input v-model="nModal.title" placeholder="如：10 月 12 日 14:00 跌倒应急演练（实训楼 203）" /></div>
        <div class="field"><label>摘要（首页公告条显示）</label><input v-model="nModal.summary" placeholder="一句话说明" /></div>
        <div class="field"><label>正文详情</label><textarea v-model="nModal.content" rows="3" placeholder="详细内容（可选）"></textarea></div>
        <div class="mgrid c2">
          <div class="field"><label>开始日期</label><input type="date" v-model="nModal.start_date" /></div>
          <div class="field"><label>结束日期</label><input type="date" v-model="nModal.end_date" /></div>
        </div>
        <div style="display: flex; gap: 16px; margin: 6px 0 16px; font-size: 13px">
          <label style="display: flex; gap: 6px; align-items: center; cursor: pointer"><input type="checkbox" :checked="nModal.pinned === 1" @change="nModal.pinned = nModal.pinned ? 0 : 1" /> 置顶</label>
          <label style="display: flex; gap: 6px; align-items: center; cursor: pointer"><input type="checkbox" :checked="nModal.enabled === 1" @change="nModal.enabled = nModal.enabled ? 0 : 1" /> 启用</label>
        </div>
        <div style="display: flex; gap: 10px"><button class="btn sm" @click="saveNotice">保存</button><button class="btn sm ghost" @click="nModal = null">取消</button></div>
      </div>
    </div>

    <!-- 轮播编辑弹窗 -->
    <div v-if="bModal" class="mask" @click.self="bModal = null">
      <div class="modal">
        <div class="modal-h">{{ bModal.id ? '编辑轮播卡' : '新增轮播卡' }}<span class="more" @click="bModal = null">✕</span></div>
        <div class="field"><label>标题 *</label><input v-model="bModal.title" placeholder="如：12 分钟理论模拟考" /></div>
        <div class="mgrid c2">
          <div class="field"><label>顶部标签</label><input v-model="bModal.tag" placeholder="如：限时 12 分钟" /></div>
          <div class="field"><label>副标题</label><input v-model="bModal.sub" placeholder="一句话卖点" /></div>
        </div>
        <div class="field">
          <label>背景图（不上传则用红色渐变文字卡）</label>
          <div style="display: flex; gap: 10px; align-items: center">
            <input type="file" accept="image/*" @change="onPickImage" style="font-size: 12px" />
            <img v-if="bModal.image" :src="bModal.image" style="width: 120px; height: 60px; object-fit: cover; border-radius: 8px; border: 1px solid var(--line)" />
            <button v-if="bModal.image" class="btn sm ghost" @click="bModal.image = ''">移除图片</button>
          </div>
        </div>
        <div class="mgrid c2">
          <div class="field"><label>点击跳转（前端路由）</label><input v-model="bModal.link" placeholder="/learn" /></div>
          <div class="field"><label>排序（数字越小越靠前）</label><input type="number" v-model.number="bModal.sort" /></div>
        </div>
        <label style="display: flex; gap: 6px; align-items: center; cursor: pointer; font-size: 13px; margin-bottom: 14px">
          <input type="checkbox" :checked="bModal.enabled === 1" @change="bModal.enabled = bModal.enabled ? 0 : 1" /> 启用（停用后学生端不显示）
        </label>
        <div style="display: flex; gap: 10px"><button class="btn sm" @click="saveBanner">保存</button><button class="btn sm ghost" @click="bModal = null">取消</button></div>
      </div>
    </div>
  </div>
</template>