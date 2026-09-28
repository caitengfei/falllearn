<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { auth } from '../api'

const router = useRouter()

// 知识库 03-赛 官方文档（静态目录；正文经 AI 问答触达 DSH 知识库）
const contestDocs = [
  {
    ic: '🏆', color: '#e4393c',
    title: '赛项规程 · 世界职业院校技能大赛',
    sub: '健康养老与婴幼儿托育赛道（2025 起）· 老年人跌倒情景为考核载体',
    chips: ['世赛主赛道', '官方规程'],
    ask: '世界职业院校技能大赛健康养老赛道里，跌倒情景怎么考？关键要求是什么？'
  },
  {
    ic: '📜', color: '#f5a623',
    title: '赛项规程 · 山东省技能兴鲁职业技能大赛',
    sub: '养老护理员赛项（GZ063）· 12 分钟跌倒应急处置情景模块',
    chips: ['省赛 GZ063', '12 分钟情景'],
    ask: '山东省技能兴鲁大赛养老护理员赛项（GZ063）的 12 分钟跌倒情景怎么分配时间和步骤？'
  },
  {
    ic: '📜', color: '#3b82f6',
    title: '赛项规程 · 省职业院校技能大赛（高职组）',
    sub: '健康养老照护赛项 · 养老机构照护全流程',
    chips: ['高职组', '官方规程'],
    ask: '省职业院校技能大赛高职组健康养老照护赛项，跌倒相关考核内容有哪些？'
  },
  {
    ic: '📜', color: '#0ea5e9',
    title: '赛项规程 · 省职业院校技能大赛（高职组）',
    sub: '老年护理与保健赛项 · 老年护理实操主线',
    chips: ['高职组', '官方规程'],
    ask: '省赛高职组老年护理与保健赛项里，老年人跌倒处置考哪些能力？'
  },
  {
    ic: '📊', color: '#22c55e',
    title: '评分标准 · 安全防护与应急处置模块',
    sub: 'M8 六项给分点 · 风险识别 / 分型处理 / 记录上报逐条分值',
    chips: ['M8 六项评分', '给分点'],
    ask: '评分标准里安全防护与应急处置模块的 M8 六项各给多少分？分别怎么给分？'
  },
  {
    ic: '⚠️', color: '#ef4444',
    title: '常见扣分点总结',
    sub: '备赛避雷：顺序错 / 未制动即搬动 / 漏记录上报 等高频失分',
    chips: ['备赛必读', '扣分点'],
    ask: '跌倒应急处置的常见扣分点有哪些？怎样逐条避免？'
  },
  {
    ic: '🎖', color: '#8b5cf6',
    title: '获奖项目训练记录',
    sub: '历届获奖队伍的训练安排与方法复盘',
    chips: ['获奖复盘'],
    ask: '获奖项目的训练记录里，跌倒模块是怎么训练的？有什么可借鉴的方法？'
  }
]

// 04-证 考证资料
const certDocs = [
  { ic: '📗', title: '养老护理员职业技能等级证书 · 考核标准', sub: '五级/四级/三级分级 · 实操情景 + 理论 · 60 分合格', ask: '养老护理员职业技能等级证书考不考跌倒？实操怎么考、多少分合格？' },
  { ic: '📘', title: '健康照护师职业技能等级证书 · 考核标准', sub: '四能四评 · 风险识别与应急处置条款', ask: '健康照护师证书的考核里，跌倒风险与应急处置占什么比重？' },
  { ic: '📙', title: '老年人能力评估师 · 考核标准', sub: '能力评估全流程 · 跌倒风险评估为必考项', ask: '老年人能力评估师考试里，Morse 量表跌倒评估怎么考？' },
  { ic: '🧾', title: '实操考核试题 · 跌倒预防与应急处理', sub: '两道 12 分钟 100 分官方评分表 · 与省赛同构', ask: '实操考核试题里两道跌倒情景题的评分表怎么构成？M8 分型处理 15 分怎么拿？' }
]

// 02-课 课程资源
const courseDocs = [
  { ic: '📖', title: '教案 · 跌倒的防护与急救', sub: '项目三主线教学 · 五步法重难点拆解', ask: '教案里五步法的重难点是怎么拆解教学的？' },
  { ic: '📝', title: '实训任务单 · 跌倒应急处置', sub: '情景 A/B 考核脚本 · 决策正确 15 分', ask: '实训任务单考核考什么？情景 A 和 B 分别怎么决策？' },
  { ic: '🎯', title: '课程标准 · 老年人安全照护与急救技术', sub: '任务拆解与考核要求 · 岗课赛证映射依据', ask: '课程标准里项目二的四个任务分别对应什么考核要求？' },
  { ic: '🗺', title: '知识点梳理 · 六簇 × 岗课赛证对照', sub: '一个知识点、四个落点 · 学习索引页', ask: '六个知识点簇各自映射到岗、赛、证的哪些落点？' }
]

// 01-岗 岗位标准
const postDocs = [
  { ic: '🩺', title: '临床标准处置流程', sub: '发现跌倒后标准动作 · 骨折疑诊处理 · 急救指征', ask: '临床标准处置流程里，发现老人跌倒后的标准动作顺序是什么？' },
  { ic: '📋', title: '养老护理员国家职业技能标准（风险应对）', sub: '2019 年版 · 风险识别与防控条款', ask: '国家职业技能标准里「风险应对」条款对跌倒有哪些要求？' },
  { ic: '🛡', title: '安全提示要点', sub: '环境风险排查 · 搬动禁忌（骨折端移位）', ask: '安全提示要点里，哪些搬动方式是禁忌的？为什么？' },
  { ic: '🧮', title: '跌倒风险评估工具 · Morse 量表', sub: '6 条目计分 · 低危 <25 / 中危 25–44 / 高危 ≥45', ask: 'Morse 量表 6 个条目怎么计分？低危中危高危的分界是多少？' }
]

function askAI(q) {
  if (!auth.ready) { router.push('/login'); return }
  router.push({ path: '/learn', query: { k: q } })
}
function goMock() {
  router.push({ path: '/practice', query: { menu: 'mock' } })
}
</script>

<template>
  <div class="page" style="max-width: 1080px">
    <div class="card" style="background: linear-gradient(135deg, #fff5f5, #fff); border: 1px solid #fbd9d9">
      <div style="display: flex; gap: 14px; align-items: flex-start">
        <div style="font-size: 34px">🏅</div>
        <div>
          <div style="font-size: 17px; font-weight: 700">岗课赛证融通资料库</div>
          <div style="font-size: 13px; color: var(--text-2); margin-top: 4px; line-height: 1.8">
            26 份真实文档（世赛/省赛规程 · 官方评分标准 · 三证考核标准 · 课程教案 · 岗位标准），全部带官方来源分级。
            点「问 AI 讲解」可让 AI 老师按【岗】【课】【赛】【证】四栏拆解，并标注原文出处。
          </div>
          <div style="margin-top: 10px; display: flex; gap: 8px">
            <button class="btn sm" @click="goMock">按竞赛标准做 12 分钟模拟考</button>
            <button class="btn sm ghost" @click="askAI('大赛跌倒环节怎么扣分？')">问：大赛跌倒环节怎么扣分？</button>
          </div>
        </div>
      </div>
    </div>

    <div class="card mt16">
      <div class="card-title">🏆 比赛资料 · 03-赛（7 份官方文档）</div>
      <div v-for="d in contestDocs" :key="d.title + d.sub" class="doc-row">
        <div class="doc-ic" :style="{ background: d.color + '18', color: d.color }">{{ d.ic }}</div>
        <div style="flex: 1; min-width: 0">
          <div style="font-size: 14px; font-weight: 600">{{ d.title }}</div>
          <div style="font-size: 12.5px; color: var(--text-2); margin-top: 3px">{{ d.sub }}</div>
          <div style="margin-top: 6px">
            <span v-for="c in d.chips" :key="c" class="tag">{{ c }}</span>
          </div>
        </div>
        <button class="btn sm ghost" @click="askAI(d.ask)">问 AI 讲解 ›</button>
      </div>
    </div>

    <div class="grid-2">
      <div class="card mt16">
        <div class="card-title">📜 考证资料 · 04-证</div>
        <div v-for="d in certDocs" :key="d.title" class="doc-row">
          <div class="doc-ic" style="background: #ecfdf5; color: #059669">{{ d.ic }}</div>
          <div style="flex: 1; min-width: 0">
            <div style="font-size: 13.5px; font-weight: 600">{{ d.title }}</div>
            <div style="font-size: 12px; color: var(--text-2); margin-top: 2px">{{ d.sub }}</div>
          </div>
          <button class="btn sm ghost" @click="askAI(d.ask)">问 AI ›</button>
        </div>
      </div>
      <div class="card mt16">
        <div class="card-title">📚 课程资源 · 02-课</div>
        <div v-for="d in courseDocs" :key="d.title" class="doc-row">
          <div class="doc-ic" style="background: #eff6ff; color: #2563eb">{{ d.ic }}</div>
          <div style="flex: 1; min-width: 0">
            <div style="font-size: 13.5px; font-weight: 600">{{ d.title }}</div>
            <div style="font-size: 12px; color: var(--text-2); margin-top: 2px">{{ d.sub }}</div>
          </div>
          <button class="btn sm ghost" @click="askAI(d.ask)">问 AI ›</button>
        </div>
      </div>
    </div>

    <div class="card mt16">
      <div class="card-title">🩺 岗位标准 · 01-岗</div>
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 4px 24px">
        <div v-for="d in postDocs" :key="d.title" class="doc-row">
          <div class="doc-ic" style="background: #fef4e2; color: #d97706">{{ d.ic }}</div>
          <div style="flex: 1; min-width: 0">
            <div style="font-size: 13.5px; font-weight: 600">{{ d.title }}</div>
            <div style="font-size: 12px; color: var(--text-2); margin-top: 2px">{{ d.sub }}</div>
          </div>
          <button class="btn sm ghost" @click="askAI(d.ask)">问 AI ›</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.doc-row {
  display: flex; align-items: center; gap: 14px;
  padding: 12px 4px; border-bottom: 1px solid var(--line);
}
.doc-row:last-child { border-bottom: none; }
.doc-ic {
  width: 42px; height: 42px; border-radius: 10px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center; font-size: 20px;
}
</style>