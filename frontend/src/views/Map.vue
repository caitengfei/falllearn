<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, CLUSTERS, CLUSTER_KNOWLEDGE, CLUSTER_QCOUNT, clusterColor } from '../api'

const route = useRoute()
const router = useRouter()

const kfilter = ref('all')
const onlyWeak = ref(false)
const openCluster = ref('')
const mastery = ref({})
const wrongByCluster = ref({})
const qcounts = ref({ ...CLUSTER_QCOUNT })
const err = ref('')
const docs = ref({})       // clusterId -> [{path,title,dim}]
const docBusy = ref('')

/* 六簇的定位与检索词：与《老年人安全照护与急救技术》课程标准项目三的知识点拆解一致，
   并与省级赛项 GZ063 跌倒情景的考核要点对齐。 */
const CLUSTER_META = {
  morse: { why: '评估关：先判断风险高低，决定后续照护强度（Morse 量表是机构标准与赛项通用的评估工具）', q: 'Morse 量表 风险评估 条目 计分 等级' },
  env: { why: '预防关：环境与个人因素的排查整改，是机构预防跌倒规范（MZ/T 185）的核心要求', q: '环境 排查 照明 地面 防滑 扶手 通道' },
  five: { why: '应急关：跌倒发生后的标准处置主线，省赛 GZ063 12 分钟情景的评分主轴', q: '跌倒后 标准处置流程 应急处置 步骤 评估意识' },
  fracture: { why: '鉴别关：判断有无骨折与重伤，"未制动即搬动"属重扣分/一票否决点', q: '骨折 认定 制动 畸形 骨擦感 搬动' },
  record: { why: '文书关：记录与上报既是岗位要求，也是竞赛评分项与责任证据链', q: '记录 上报 记录单 时限 上报对象' },
  cpr: { why: '抢救关：意识不清/呼吸心跳骤停时的最后防线，理论高频考点', q: 'CPR 心肺复苏 呼吸心跳骤停 启动条件' }
}

const cards = computed(() =>
  CLUSTERS
    .filter((c) => kfilter.value === 'all' || c.id === kfilter.value)
    .map((c) => ({
      ...c,
      level: mastery.value[c.id] ?? 0,
      qcount: qcounts.value[c.id] ?? 0,
      wrong: wrongByCluster.value[c.id] || 0,
      why: CLUSTER_META[c.id]?.why || ''
    }))
    .filter((c) => !onlyWeak.value || c.level < 60)
)
const weakCount = computed(() => CLUSTERS.filter((c) => (mastery.value[c.id] ?? 0) < 60).length)
const allWeakEmpty = computed(() => onlyWeak.value && cards.value.length === 0)

async function openDetail(id) {
  openCluster.value = openCluster.value === id ? '' : id
  if (!openCluster.value || docs.value[id]) return
  docBusy.value = id
  try {
    const r = await api.kbSearch(CLUSTER_META[id]?.q || id)
    docs.value = { ...docs.value, [id]: (r.items || []).slice(0, 5) }
  } catch {
    docs.value = { ...docs.value, [id]: [] }
  }
  docBusy.value = ''
}

function gotoKb(d) {
  router.push({ path: '/kb', query: { q: d.title } })
}
function askCluster(id) {
  router.push({ path: '/learn', query: { k: (CLUSTER_META[id]?.q || id) + ' 是什么' } })
}
function practiceCluster(id) {
  router.push({ path: '/practice', query: { cluster: id } })
}

onMounted(async () => {
  err.value = ''
  try {
    const [m, wl] = await Promise.all([api.me(), api.wrongList('active')])
    mastery.value = m.mastery || {}
    wrongByCluster.value = (wl.items || []).reduce((a, x) => ((a[x.cluster] = (a[x.cluster] || 0) + 1), a), {})
  } catch (e) {
    err.value = e.message
  }
  api.metaClusters()
    .then((m) => { if (m.items?.length) qcounts.value = Object.fromEntries(m.items.map((x) => [x.id, x.qcount])) })
    .catch(() => {})
  // 深链：/map?cluster=xxx 直接展开该簇
  if (route.query.cluster && CLUSTERS.some((c) => c.id === route.query.cluster)) openDetail(String(route.query.cluster))
})
</script>

<template>
  <div class="page" style="max-width: 1080px">
    <div class="card" style="margin-bottom: 14px">
      <div class="card-title">🗺 知识地图 · 六簇知识点</div>
      <div style="font-size: 12.5px; color: var(--text-2); line-height: 1.85">
        六簇来自《老年人安全照护与急救技术》课程项目三「跌倒的防护与急救」的知识点拆解，
        并与省级赛项 <b>GZ063</b> 跌倒情景的考核要点对齐：
        <b>Morse 评估</b>（评估关）· <b>环境防控</b>（预防关）· <b>五步处置</b>（应急关）·
        <b>骨折识别</b>（鉴别关）· <b>记录上报</b>（文书关）· <b>CPR 启动</b>（抢救关）。
        点开任一簇可看知识点、关联知识库文档与练题入口。
      </div>
      <div style="font-size: 12px; color: var(--text-3); margin-top: 8px">
        当前薄弱簇（掌握度 &lt; 60）：<b :style="{ color: weakCount ? 'var(--primary-text)' : 'inherit' }">{{ weakCount }}</b> / 6
      </div>
    </div>

    <div v-if="err" class="card" style="border-color: #fca5a5; color: #b91c1c; margin-bottom: 14px">
      数据加载失败：{{ err }} <button class="btn sm" style="margin-left: 12px" @click="$router.go(0)">刷新</button>
    </div>

    <div class="pills">
      <span class="pill" :class="{ on: kfilter === 'all' }" @click="kfilter = 'all'">全部</span>
      <span v-for="c in CLUSTERS" :key="c.id" class="pill" :class="{ on: kfilter === c.id }" @click="kfilter = c.id">{{ c.name }}</span>
    </div>
    <label class="onlyweak">
      <input type="checkbox" v-model="onlyWeak" /> 仅看薄弱（&lt;60）
    </label>
    <div v-if="allWeakEmpty" class="card" style="font-size: 12.5px; color: var(--text-3)">
      没有低于 60% 的薄弱簇（全部达标）—— 取消筛选查看全部 6 簇
    </div>

    <div class="kmap">
      <div v-for="c in cards" :key="c.id" class="kcard" :class="{ on: openCluster === c.id }" @click="openDetail(c.id)">
        <span v-if="c.id === 'five' || c.id === 'fracture'" class="badge-corner">核心</span>
        <div class="cover" :style="{ background: c.color }">{{ c.short || c.name.slice(0, 2) }}</div>
        <div class="kbody">
          <div class="kname">{{ c.name }}</div>
          <div class="kmeta">
            <span class="mono">{{ c.qcount }} 题</span>
            <span>掌握 {{ c.level }}%</span>
            <span v-if="c.wrong" class="mono" style="color: var(--primary-text)">错 {{ c.wrong }}</span>
          </div>
          <div class="kbar"><i :style="{ width: c.level + '%', background: c.color }"></i></div>
        </div>
      </div>
    </div>

    <!-- 簇详情 -->
    <div v-if="openCluster" class="card mt16">
      <div class="card-title">
        {{ CLUSTERS.find((c) => c.id === openCluster)?.name }} · 知识点与资源
        <span class="more" @click="openCluster = ''">收起 ✕</span>
      </div>
      <div style="font-size: 12.5px; color: var(--text-2); background: var(--bg); border-radius: 8px; padding: 9px 12px; line-height: 1.8">
        🎯 {{ CLUSTER_META[openCluster]?.why }}
      </div>

      <div style="font-size: 13px; font-weight: 700; margin: 14px 0 6px">核心知识点</div>
      <ul class="cluster-kp">
        <li v-for="(kp, i) in (CLUSTER_KNOWLEDGE[openCluster] || [])" :key="i">{{ kp }}</li>
      </ul>

      <div style="font-size: 13px; font-weight: 700; margin: 14px 0 6px">
        关联知识库文档
        <span style="font-weight: 400; font-size: 11.5px; color: var(--text-3)">（按该簇关键词实时检索，点击可读原文）</span>
      </div>
      <div v-if="docBusy === openCluster" style="font-size: 12.5px; color: var(--text-3)">检索中…</div>
      <div v-else-if="(docs[openCluster] || []).length" class="docs">
        <div v-for="d in docs[openCluster]" :key="d.path" class="doc-item" role="button" tabindex="0"
          @click="gotoKb(d)" @keyup.enter="gotoKb(d)">
          <span class="dimtag" :style="{ background: (CLUSTERS.find((c) => c.id === openCluster)?.color || '#64748b') + '18', color: CLUSTERS.find((c) => c.id === openCluster)?.color }">{{ d.dim }}</span>
          <span class="dt">{{ d.title }}</span>
          <span class="go">读原文 ›</span>
        </div>
      </div>
      <div v-else style="font-size: 12.5px; color: var(--text-3)">未检索到关联文档（可在知识库页手动搜索）</div>

      <div style="font-size: 12px; color: var(--text-3); margin-top: 12px">
        题库 {{ qcounts[openCluster] ?? 0 }} 题 · 你的错题 {{ wrongByCluster[openCluster] || 0 }} 题 ·
        掌握度 {{ mastery[openCluster] ?? 0 }}%
      </div>

      <div style="display: flex; gap: 10px; margin-top: 14px; flex-wrap: wrap">
        <button class="btn sm" @click="practiceCluster(openCluster)">练这一簇</button>
        <button class="btn sm ghost" @click="askCluster(openCluster)">问 AI 讲这一簇</button>
        <button class="btn sm ghost" @click="router.push('/kb')">去知识库</button>
      </div>
    </div>

    <div class="card mt16" style="font-size: 12.5px; color: var(--text-2); line-height: 1.85">
      💡 <b>学习建议</b>：先看掌握度最低的簇（点击卡片展开知识点与文档），再点「练这一簇」做 5–10 题；
      错题会进入错题本按「次日 → 第 3 天」间隔复习，连续答对 2 次即记为掌握。
    </div>
  </div>
</template>

<style scoped>
.kmap { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; margin-top: 12px; }
@media (max-width: 640px) { .kmap { grid-template-columns: minmax(0, 1fr); } }
.kcard { position: relative; display: flex; gap: 12px; align-items: center; background: #fff; border: 1px solid var(--line);
  border-radius: 12px; padding: 12px; cursor: pointer; transition: all .15s; }
.kcard:hover { border-color: var(--primary); box-shadow: 0 2px 10px rgba(228, 57, 60, .08); transform: translateY(-1px); }
.kcard.on { border-color: var(--primary); box-shadow: 0 0 0 2px var(--primary-light); }
.badge-corner { position: absolute; top: -1px; right: -1px; background: var(--primary); color: #fff; font-size: 10.5px;
  padding: 2px 8px; border-radius: 0 12px 0 10px; }
.cover { width: 46px; height: 46px; border-radius: 12px; color: #fff; font-weight: 800; font-size: 15px;
  display: flex; align-items: center; justify-content: center; flex: none; }
.kbody { flex: 1; min-width: 0; }
.kname { font-size: 14px; font-weight: 700; }
.kmeta { display: flex; gap: 10px; font-size: 11.5px; color: var(--text-3); margin: 3px 0 5px; flex-wrap: wrap; }
.kbar { height: 5px; background: var(--bg); border-radius: 3px; overflow: hidden; }
.kbar i { display: block; height: 100%; }
.cluster-kp { margin: 0; padding-left: 20px; font-size: 13px; line-height: 1.9; color: var(--text-2); }
.docs { display: flex; flex-direction: column; gap: 6px; }
.doc-item { display: flex; align-items: center; gap: 8px; border: 1px solid var(--line); border-radius: 8px;
  padding: 7px 10px; font-size: 12.5px; cursor: pointer; transition: all .12s; }
.doc-item:hover { border-color: var(--primary); background: var(--bg); }
.dimtag { font-size: 10.5px; padding: 1px 6px; border-radius: 4px; flex: none; }
.dt { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.go { color: var(--primary-text); font-size: 11.5px; flex: none; }
</style>
