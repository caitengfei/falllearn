<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, auth, CLUSTERS, CLUSTER_QCOUNT, CLUSTER_KNOWLEDGE, clusterName, DEMO_GUIDE } from '../api'

const router = useRouter()
const me = ref({})
const points = ref(0)
const checkedIn = ref(false)
const weakTip = ref(null)
const timeline = ref([])
const lb = ref({ points: [], mastery: [], my_rank_points: null, my_rank_mastery: null })
const lbTab = ref('points')
const wrongByCluster = ref({})
const toast = ref(null)
const loadErr = ref('')

// ---------- 评委演示引导（首访卡；顶栏 ? 可随时重开弹窗） ----------
const showGuide = ref(!localStorage.getItem('fl_guide_v1'))
function dismissGuide() {
  localStorage.setItem('fl_guide_v1', '1')
  showGuide.value = false
}
function goGuide(g) {
  if (g.to === '/login') {
    auth.clear()
    router.push('/login')
    return
  }
  if (g.ask) {
    router.push({ path: g.to, query: { ask: g.ask } })
    return
  }
  router.push(g.to)
}

// ---------- Banner 轮播（DB 驱动：教师后台可换图/增删；自动 5s + 可点） ----------
const GRADS = [
  'linear-gradient(120deg, #7f1d1d, #b91c1c 55%, #e4393c)',
  'linear-gradient(120deg, #78350f, #b45309 55%, #f5a623)',
  'linear-gradient(120deg, #1e3a8a, #1d4ed8 55%, #3b82f6)',
  'linear-gradient(120deg, #064e3b, #047857 55%, #22c55e)',
  'linear-gradient(120deg, #312e81, #4338ca 55%, #6366f1)'
]
const ICONS = ['🛡', '⏱', '🏆', '📕', '🗺']
const CTA_BY_LINK = { '/learn': '开始学习', '/practice': '去练习', '/practice?menu=mock': '去模拟考', '/competition': '查看资料', '/wrong': '去复习' }
const slides = ref([
  { tag: '世赛 × 省赛 GZ063 双对标', title: '老年人跌倒 · 预防与应急处置', sub: '岗课赛证融通 · 把技能学成肌肉记忆', cta: '开始学习', to: '/learn', grad: GRADS[0], ic: '🛡', image: '' },
  { tag: '限时 12 分钟 · 100 分', title: '12 分钟理论模拟考', sub: '按竞赛口径组卷 · 倒计时交卷 · 逐题解析入错题本', cta: '去模拟考', to: '/practice?menu=mock', grad: GRADS[1], ic: '⏱', image: '' },
  { tag: '46 份真实文档', title: '比赛资料 · 官方规程与评分标准', sub: '世赛/全国赛/省赛规程与正式赛题 · M8 评分 · 三证国标与题库', cta: '查看资料', to: '/competition', grad: GRADS[2], ic: '🏆', image: '' },
  { tag: '间隔复习 · 连对 2 次掌握', title: '错题本 · 次日到期 → 第 3 天', sub: '每道错题自动入本 · 重答 / 讲解双模式 · 掌握后自动归档', cta: '去复习', to: '/wrong', grad: GRADS[3], ic: '📕', image: '' }
])
const notices = ref([])
const noticeOpen = ref(false)
const contentLoaded = ref(false)
async function loadContent() {
  try {
    const [pb, pn, meta] = await Promise.all([
      api.pubBanners(), api.pubNotices(), api.metaClusters().catch(() => null)
    ])
    if (pb.items?.length) {
      slides.value = pb.items.map((b, i) => ({
        tag: b.tag || '', title: b.title, sub: b.sub || '',
        cta: CTA_BY_LINK[b.link] || '去看看', to: b.link || '/',
        grad: GRADS[i % GRADS.length], ic: ICONS[i % ICONS.length], image: b.image || ''
      }))
    }
    notices.value = pn.items || []
    if (meta?.items?.length) {
      qcounts.value = Object.fromEntries(meta.items.map((x) => [x.id, x.qcount]))
    }
  } catch (e) {
    console.warn('内容接口不可用，用默认轮播', e)
  } finally {
    contentLoaded.value = true
  }
}
const slideIdx = ref(0)
let slideTimer = null
function startSlides() {
  stopSlides()
  slideTimer = setInterval(() => { slideIdx.value = (slideIdx.value + 1) % slides.value.length }, 5000)
}
function stopSlides() { if (slideTimer) { clearInterval(slideTimer); slideTimer = null } }
function goSlide(i) { slideIdx.value = i; startSlides() }

// ---------- 功能入口（7 项）----------
// 说明：原为 9 宫格，其中「学习日历」「排行榜」两项点击只是滚动到下方已展示的同一内容
// （同事审核建议 2：入口与其指向内容重复），已删除这两个入口为界面减负。
const icons = [
  { ic: '🗣', bg: '#3b82f6', lbl: 'AI 问答', to: '/learn' },
  { ic: '🗺', bg: '#8b5cf6', lbl: '知识地图', to: '/map' },
  { ic: '✏', bg: '#e4393c', lbl: '日常练习', to: '/practice' },
  { ic: '⏱', bg: '#f5a623', lbl: '12 分钟模拟考', to: '/practice?menu=mock' },
  { ic: '🏆', bg: '#0ea5e9', lbl: '比赛资料', to: '/competition' },
  { ic: '📕', bg: '#ef4444', lbl: '错题本', to: '/wrong' },
  { ic: '📊', bg: '#64748b', lbl: '掌握度报告', to: '/mine' }
]
function iconGo(it) {
  router.push(it.to)
}

// ---------- 知识卡片（6 簇 · 真实题量 + 掌握度进度条 + 点击原地详解） ----------
// 题量来自 /api/meta/clusters（DB 实时），拉取失败回退前端静态值
const qcounts = ref({ ...CLUSTER_QCOUNT })
const kcards = computed(() =>
  CLUSTERS.map((c) => ({
    ...c,
    level: me.value.mastery?.[c.id] ?? 0,
    qcount: qcounts.value[c.id] ?? 0,
    wrong: wrongByCluster.value[c.id] || 0,
    core: c.id === 'five' || c.id === 'fracture'
  }))
)
const openK = ref(null) // 当前展开详解的簇
const kdetail = computed(() => kcards.value.find((x) => x.id === openK.value) || null)
function askCluster() {
  const q = `${clusterName(openK.value)} 要点`
  openK.value = null
  router.push({ path: '/learn', query: { ask: q } })  // /learn?ask= 自动发送提问
}
function openClusterMap() {  // 知识地图已独立成页：跳 /map?cluster=xxx 并展开该簇
  const id = openK.value
  openK.value = null
  router.push({ path: '/map', query: { cluster: id } })
}

async function load() {
  loadContent() // 轮播/公告独立加载，不阻塞主体
  loadErr.value = ''
  try {
    const [m, t, l, wl, wh, lh] = await Promise.all([
      api.me(), api.today(), api.leaderboard(), api.wrongList('active'),
      api.quizWeak(),
      api.learnHistory()
    ])
    me.value = m
    points.value = m.points || 0
    checkedIn.value = t.checked_in
    lb.value = l
    const wrongItems = wl.items || []
    wrongByCluster.value = wrongItems.reduce((acc, x) => ((acc[x.cluster] = (acc[x.cluster] || 0) + 1), acc), {})
    weakTip.value = wh.weak?.length ? { id: wh.weak[0], name: clusterName(wh.weak[0]) } : null
    timeline.value = (lh.items || []).slice(0, 5).map((x) => ({
      t: new Date(x.at * 1000).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }),
      c: 'AI 问答', tag: x.question.slice(0, 14)
    }))
  } catch (e) {
    // 静默失败会让首页统计/排行/日历全为空，评委极易误判为"没数据"：改为可见错误条 + 重试
    loadErr.value = e.message || '加载失败'
    console.error(e)
  }
}

async function doCheckin() {
  if (checkedIn.value) return
  try {
    const r = await api.checkin()
    if (r.ok) {
      checkedIn.value = true
      points.value += 5
      showToast('签到成功 +5 积分')
    } else {
      showToast(r.msg || '今日已签到')
    }
  } catch (e) {
    showToast('签到失败：' + e.message)
  }
}

function showToast(msg) {
  toast.value = msg
  setTimeout(() => { toast.value = null }, 2200)
}

onMounted(() => { load(); startSlides() })
onBeforeUnmount(stopSlides)
</script>

<template>
  <div class="page">
    <!-- 评委演示引导（首访展示，可不再显示；顶栏 ? 重开） -->
    <div v-if="showGuide" class="guide-card">
      <div class="gc-head">
        <div>
          <div class="gc-title">🎓 演示体验路径 · 6 步看懂平台</div>
          <div class="gc-sub">每一步都能直接点开 · 右上角「？」随时重开</div>
        </div>
        <button class="gc-close" @click="dismissGuide">不再显示</button>
      </div>
      <div class="gc-grid">
        <div v-for="(g, i) in DEMO_GUIDE.student" :key="i" class="gc-step" @click="goGuide(g)">
          <span class="gc-ic">{{ g.ic }}</span>
          <span class="gc-num">{{ i + 1 }}</span>
          <div class="gc-step-b">
            <b>{{ g.t }}</b>
            <span>{{ g.d }}</span>
          </div>
          <span class="gc-go">›</span>
        </div>
      </div>
    </div>
    <div v-if="loadErr" class="card" style="border-color: #fca5a5; color: #b91c1c; margin-bottom: 12px">
      首页数据加载失败：{{ loadErr }} <button class="btn sm" style="margin-left: 12px" @click="load">重试</button>
    </div>
    <!-- 课程预告公告条（教师后台配置） -->
    <div v-if="notices.length" class="notice-strip" @click="noticeOpen = true">
      <span class="ns-ic">📢</span>
      <span class="ns-tx">
        <b>{{ notices[0].title }}</b>
        <span v-if="notices.length > 1" style="color: var(--text-3)">（共 {{ notices.length }} 条预告，点击查看全部）</span>
        <span v-else-if="notices[0].summary" style="color: var(--text-3)"> · {{ notices[0].summary }}</span>
      </span>
      <span class="ns-more">›</span>
    </div>
    <div class="grid-3">
      <!-- 左：学生卡 -->
      <div class="card stu-card">
        <div class="stu-head">
          <div class="avatar-big">{{ (auth.user?.name || '学')[0] }}</div>
          <div>
            <div class="stu-name">{{ auth.user?.name }}</div>
            <div class="stu-badge">{{ auth.user?.role === 'teacher' ? '教师' : '养老专业 2026 级' }} · {{ me.badge_count || 0 }} 枚勋章 🎖</div>
          </div>
        </div>
        <div class="checkin-row">
          <span>📆 每日签到积分 +5</span>
          <button class="btn-sm" :disabled="checkedIn" @click="doCheckin">{{ checkedIn ? '已签到' : '签到' }}</button>
        </div>
        <div class="stu-stats">
          <div class="stat-item"><div class="v mono">{{ me.practice_count || 0 }}</div><div class="k">完成练习</div></div>
          <div class="stat-item"><div class="v mono">{{ points }}</div><div class="k">积分</div></div>
          <div class="stat-item"><div class="v mono">{{ me.wrong_due || 0 }}</div><div class="k">错题到期</div></div>
          <div class="stat-item"><div class="v mono">{{ me.last_score ?? '—' }}</div><div class="k">上次得分</div></div>
        </div>
      </div>

      <!-- 中：Banner 轮播 + 九宫格 -->
      <div>
        <div
          v-if="contentLoaded"
          class="banner"
          :style="slides[slideIdx].image ? { backgroundImage: `url(${slides[slideIdx].image})`, backgroundSize: 'cover', backgroundPosition: 'center' } : { background: slides[slideIdx].grad }"
          @mouseenter="stopSlides" @mouseleave="startSlides"
        >
          <div class="banner-deco" v-if="!slides[slideIdx].image">{{ slides[slideIdx].ic }}</div>
          <div style="position: relative; z-index: 1">
            <div class="b-tag">{{ slides[slideIdx].tag }}</div>
            <h2>{{ slides[slideIdx].title }}</h2>
            <p>{{ slides[slideIdx].sub }}</p>
            <button class="b-cta" @click="router.push(slides[slideIdx].to)">{{ slides[slideIdx].cta }} ›</button>
          </div>
          <div class="banner-dots">
            <i v-for="(s, i) in slides" :key="i" :class="{ on: i === slideIdx }" @click="goSlide(i)"></i>
          </div>
        </div>
        <div v-else class="banner" style="background: linear-gradient(120deg, #7f1d1d, #b91c1c 55%, #e4393c); display: flex; align-items: center; justify-content: center; color: rgba(255,255,255,.7); font-size: 13px">加载轮播中…</div>
        <div class="card mt16">
          <div class="icon-grid">
            <div v-for="it in icons" :key="it.lbl" class="icon-item" @click="iconGo(it)">
              <div class="ic" :style="{ background: it.bg }">{{ it.ic }}</div>
              <div class="lbl">{{ it.lbl }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- 右：弱项提醒 -->
      <div>
        <div class="card">
          <div class="card-title">今日弱项提醒</div>
          <template v-if="weakTip">
            <div style="font-size: 13.5px; line-height: 1.8">
              你的「<b style="color: var(--primary-text)">{{ weakTip.name }}</b>」掌握度偏低，建议先复习该簇再做练习。
            </div>
            <button class="btn sm ghost mt16" style="width: 100%" @click="router.push({ path: '/learn', query: { cluster: weakTip.id } })">去学一下</button>
            <button class="btn sm" style="width: 100%; margin-top: 8px" @click="router.push('/practice')">去练习</button>
          </template>
          <div v-else style="font-size: 13.5px; color: var(--text-2)">全簇达标！挑战 12 分钟模拟考吧 🏆</div>
        </div>
        <div class="card mt16" style="cursor: pointer" @click="router.push('/mine')">
          <div class="card-title">积分与勋章</div>
          <div style="font-size: 12.5px; color: var(--text-3)">看积分明细与勋章墙 · 积分商城（C 期上线）</div>
        </div>
      </div>
    </div>

    <div class="grid-2">
      <div class="card" id="cal-card">
        <div class="card-title">学习日历</div>
        <div class="tl" v-if="timeline.length">
          <div v-for="(t, i) in timeline" :key="i" class="tl-item">
            <div class="t">{{ t.t }}</div>
            <div class="c">{{ t.c }} <span class="tag blue ellipsis" style="max-width: 220px">{{ t.tag }}</span></div>
          </div>
        </div>
        <div v-else class="empty">还没有学习记录，去问 AI 老师第一句吧</div>
      </div>
      <div class="card" id="rank-card">
        <div class="card-title">
          排行榜
          <span class="pills" style="margin-left: auto">
            <span class="pill sm" :class="{ on: lbTab === 'points' }" @click="lbTab = 'points'">积分</span>
            <span class="pill sm" :class="{ on: lbTab === 'mastery' }" @click="lbTab = 'mastery'">掌握度</span>
          </span>
        </div>
        <div style="font-size: 13px; margin-bottom: 10px; color: var(--text-2)">
          我的排名：<b class="mono" style="font-size: 16px; color: var(--primary-text)">
            {{ lbTab === 'points' ? (lb.my_rank_points || '-') : (lb.my_rank_mastery || '-') }}
          </b>
        </div>
        <template v-if="lbTab === 'points'">
          <div v-for="(r, i) in lb.points.slice(0, 5)" :key="r.rank" class="row-item">
            <div style="width: 22px; text-align: center; font-size: 16px">{{ i < 3 ? ['🥇', '🥈', '🥉'][i] : r.rank }}</div>
            <div class="rmain"><div class="rtitle">{{ r.name }} <span v-if="r.me" class="tag red">我</span></div></div>
            <div class="mono" style="font-weight: 700">{{ r.points }}</div>
          </div>
        </template>
        <template v-else>
          <div v-for="r in lb.mastery.slice(0, 5)" :key="r.rank" class="row-item">
            <div style="width: 22px; text-align: center; font-size: 16px">{{ ['🥇', '🥈', '🥉'][r.rank - 1] || r.rank }}</div>
            <div class="rmain"><div class="rtitle">{{ r.name }} <span v-if="r.me" class="tag red">我</span></div></div>
            <div class="mono" style="font-weight: 700">{{ r.total }}</div>
          </div>
        </template>
      </div>
    </div>

    <div class="card mt16">
      <div class="card-title">知识卡片 · 六簇 × 岗课赛证 <span style="font-size: 11px; color: var(--text-3); font-weight: 400">点一张卡看知识点</span><span class="more" @click="router.push('/map')">全部 ›</span></div>
      <div class="kgrid">
        <div v-for="c in kcards" :key="c.id" class="kcard" @click="openK = c.id">
          <span v-if="c.core" class="badge-corner">核心</span>
          <div class="cover" :style="{ background: c.color }">{{ c.name.slice(0, 2) }}</div>
          <div class="kbody">
            <div class="kname">{{ c.name }}</div>
            <div class="kmeta">
              <span class="mono">{{ c.qcount }} 题</span>
              <span v-if="c.wrong" class="mono" style="color: var(--primary-text)">错 {{ c.wrong }}</span>
            </div>
            <div class="kbar"><i :style="{ width: c.level + '%', background: c.color }"></i></div>
            <div class="kmeta" style="margin-top: 4px"><span>掌握 {{ c.level }}%</span><span class="kd-more">详解 ›</span></div>
          </div>
        </div>
      </div>
    </div>

    <!-- 簇详解弹窗（点知识卡原地打开） -->
    <div v-if="kdetail" class="mask" @click.self="openK = null">
      <div class="modal" style="max-width: 540px">
        <div class="modal-h">
          {{ kdetail.name }} · 知识点详解
          <span v-if="kdetail.core" class="tag red" style="margin-left: 8px">核心</span>
          <span class="more" @click="openK = null">✕</span>
        </div>
        <div style="display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 12px">
          <span class="tag" :style="{ background: kdetail.color + '18', color: kdetail.color }">{{ kdetail.qcount }} 题入库</span>
          <span v-if="kdetail.wrong" class="tag red">你的错题 {{ kdetail.wrong }}</span>
          <span v-else class="tag green">暂无错题</span>
        </div>
        <div style="font-size: 12.5px; color: var(--text-2); margin-bottom: 6px">我的掌握度 <b class="mono" :style="{ color: kdetail.color }">{{ kdetail.level }}%</b></div>
        <div class="kbar" style="height: 7px; margin-bottom: 14px"><i :style="{ width: kdetail.level + '%', background: kdetail.color }"></i></div>
        <ul class="home-kp">
          <li v-for="(kp, i) in (CLUSTER_KNOWLEDGE[kdetail.id] || [])" :key="i">{{ kp }}</li>
        </ul>
        <div style="font-size: 12px; color: var(--text-3); margin-top: 12px; line-height: 1.8">
          💡 点「问 AI」，AI 老师按【岗】【课】【赛】【证】四栏讲透这一簇，每栏标注知识库原文出处。
        </div>
        <div style="display: flex; gap: 10px; margin-top: 16px; flex-wrap: wrap">
          <button class="btn sm" @click="askCluster()">问 AI 讲这一簇</button>
          <button class="btn sm ghost" @click="openClusterMap()">知识地图看这一簇</button>
          <button v-if="kdetail.wrong" class="btn sm ghost" @click="openK = null; router.push('/wrong')">重做这簇错题</button>
        </div>
      </div>
    </div>

    <!-- 课程预告弹窗 -->
    <div v-if="noticeOpen" class="mask" @click.self="noticeOpen = false">
      <div class="modal">
        <div class="modal-h">课程预告<span class="more" @click="noticeOpen = false">✕</span></div>
        <div v-for="n in notices" :key="n.id" style="padding: 12px 0; border-bottom: 1px solid var(--line)">
          <div style="font-weight: 700; font-size: 14px">{{ n.pinned ? '📌 ' : '' }}{{ n.title }}</div>
          <div v-if="n.summary" style="font-size: 12.5px; color: var(--text-2); margin-top: 3px">{{ n.summary }}</div>
          <div v-if="n.content" style="font-size: 12.5px; color: var(--text-2); margin-top: 6px; white-space: pre-wrap">{{ n.content }}</div>
        </div>
      </div>
    </div>

    <div v-if="toast" class="toast">{{ toast }}</div>
  </div>
</template>

<style scoped>
/* —— 评委演示引导卡（首访）—— */
.guide-card {
  background: linear-gradient(120deg, #fff5f5, #ffffff 55%);
  border: 1px solid #fbd9d9; border-radius: 14px; padding: 14px 16px; margin-bottom: 14px;
}
.gc-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
.gc-title { font-size: 14.5px; font-weight: 700; color: #9f1239; }
.gc-sub { font-size: 11.5px; color: var(--text-3); margin-top: 2px; }
.gc-close {
  border: none; background: #fff; color: var(--text-2); font-size: 11.5px;
  border: 1px solid var(--line); border-radius: 8px; padding: 8px 12px; cursor: pointer;
}
.gc-close:hover { border-color: var(--primary); color: var(--primary-text); }
.gc-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; margin-top: 12px; }
.gc-step {
  display: flex; align-items: center; gap: 8px; background: #fff; min-width: 0;
  border: 1px solid var(--line); border-radius: 11px; padding: 9px 11px; cursor: pointer; transition: all .12s;
}
.gc-step:hover { border-color: var(--primary); box-shadow: 0 2px 10px rgba(228,57,60,.08); transform: translateY(-1px); }
.gc-ic { font-size: 17px; }
.gc-num { font-size: 11px; font-weight: 700; color: var(--primary-text); background: var(--primary-light); border-radius: 6px; padding: 1px 6px; }
.gc-step-b { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.gc-step-b b { font-size: 12.5px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.gc-step-b span { font-size: 11px; color: var(--text-3); margin-top: 1px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.gc-go { font-size: 16px; color: var(--text-3); }
@media (max-width: 1100px) { .gc-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 640px) { .gc-grid { grid-template-columns: minmax(0, 1fr); } }
.kd-more { margin-left: auto; color: var(--text-3); font-size: 11px; }
.kcard:hover .kd-more { color: var(--primary-text); }
.home-kp {
  margin: 8px 0 0 18px; font-size: 13px; color: var(--text-2); line-height: 2;
}
.banner-deco {
  position: absolute; right: 26px; top: 50%; transform: translateY(-50%);
  font-size: 74px; opacity: .28; pointer-events: none;
}
.b-tag {
  display: inline-block; background: rgba(255, 255, 255, .18); color: #fff;
  font-size: 11.5px; padding: 2px 10px; border-radius: 10px; margin-bottom: 8px;
}
.b-cta {
  margin-top: 12px; background: #fff; color: var(--text); border-radius: 8px;
  font-size: 13px; font-weight: 600; padding: 9px 16px; transition: transform .15s;
}
.b-cta:hover { transform: translateY(-1px); }
.kgrid { display: grid; grid-template-columns: repeat(6, 1fr); gap: 12px; }
.kbar {
  height: 5px; background: var(--bg); border-radius: 3px; overflow: hidden; margin-top: 7px;
}
.kbar i { display: block; height: 100%; border-radius: 3px; transition: width .4s; }
.toast {
  position: fixed; left: 50%; bottom: 40px; transform: translateX(-50%);
  background: #1f2430; color: #fff; font-size: 13px; padding: 9px 18px;
  border-radius: 8px; z-index: 200; box-shadow: var(--shadow-2);
}
.notice-strip {
  display: flex; align-items: center; gap: 10px; background: linear-gradient(90deg, #fff7ed, #fef4e2);
  border: 1px solid #fde4bd; border-radius: 10px; padding: 9px 14px; margin-bottom: 14px;
  cursor: pointer; font-size: 13px; transition: .15s;
}
.notice-strip:hover { border-color: var(--gold); box-shadow: var(--shadow); }
.notice-strip .ns-ic { font-size: 15px; }
.notice-strip .ns-tx { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.notice-strip .ns-more { color: var(--gold); font-weight: 700; }
</style>