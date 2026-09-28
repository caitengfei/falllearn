<script setup>
import { computed, onMounted, ref } from 'vue'
import { api, clusterColor } from '../../api'

const data = ref(null)
const err = ref('')
const loading = ref(false)
const lbTab = ref('points')
const showReset = ref(false)

async function load() {
  loading.value = true
  err.value = ''
  try {
    data.value = await api.statsOverview()
  } catch (e) {
    err.value = e.message
  }
  loading.value = false
}
onMounted(load)

const lb = computed(() => {
  if (!data.value) return []
  return lbTab.value === 'points' ? data.value.rank_points : lbTab.value === 'mastery' ? data.value.rank_mastery : data.value.rank_hours
})
const maxTrend = computed(() => Math.max(1, ...(data.value?.trend || []).map((t) => Math.max(t.points, 0))))

const toastMsg = ref('')
function toast(m) { toastMsg.value = m; setTimeout(() => (toastMsg.value = ''), 2400) }

async function doReset() {
  // 先确认再关弹窗（避免点「取消」弹窗已关、无法重开）
  if (!confirm('重置所有演示账号（S2026001-3）的学习痕迹并恢复基线？此操作不可撤销。')) return
  showReset.value = false
  try {
    await api.adminReset()
    await load()
    toast('重置完成')
  } catch (e) {
    alert(e.message)
  }
}
</script>

<template>
  <div class="page">
    <div style="display: flex; align-items: center; margin-bottom: 16px">
      <div style="font-size: 19px; font-weight: 700">数据总览</div>
      <span style="font-size: 12px; color: var(--text-3); margin-left: 10px">活跃 / 排行 / 学时 / 六簇分布</span>
      <div style="margin-left: auto; display: flex; gap: 8px">
        <button class="btn sm ghost" @click="load">{{ loading ? '刷新中…' : '↻ 刷新' }}</button>
        <button class="btn sm danger-ghost" @click="showReset = true">演示数据重置</button>
      </div>
    </div>

    <div v-if="err" class="card" style="border-color: #fca5a5; color: #b91c1c; margin-bottom: 14px">加载失败：{{ err }} <button class="btn sm" style="margin-left: 12px" @click="load">重试</button></div>
    <div v-if="toastMsg" class="toast">{{ toastMsg }}</div>

    <template v-if="data">
      <!-- 核心指标 -->
      <div class="mgrid c6" style="margin-bottom: 14px">
        <div class="mcard hero">
          <div class="mk">活跃人数（今日 / 7 日）</div>
          <div class="mv">{{ data.active.today }} <span style="font-size: 15px; opacity: .8">/ {{ data.active.week }}</span></div>
          <div class="ms">去重学生 · 签到/问答/练习</div>
        </div>
        <div class="mcard"><div class="mk">在读学生</div><div class="mv">{{ data.cards.students }}</div><div class="ms">启用账号</div></div>
        <div class="mcard"><div class="mk">题库规模</div><div class="mv">{{ data.cards.questions }}</div><div class="ms">含 AI 生成</div></div>
        <div class="mcard"><div class="mk">AI 问答总量</div><div class="mv">{{ data.cards.asks }}</div><div class="ms">四栏格式问答</div></div>
        <div class="mcard"><div class="mk">累计练习</div><div class="mv">{{ data.cards.practices }}</div><div class="ms">已交卷</div></div>
        <div class="mcard"><div class="mk">累计学时</div><div class="mv">{{ data.cards.hours }}<span style="font-size: 13px"> h</span></div><div class="ms">平均掌握 {{ data.cards.avg_mastery }}%</div></div>
      </div>

      <div class="mgrid c2" style="margin-bottom: 14px">
        <!-- 7 日积分趋势 -->
        <div class="card">
          <div class="card-title">近 7 日积分动态</div>
          <div class="chart-bars">
            <div class="cb" v-for="t in data.trend" :key="t.date">
              <div class="cv">{{ t.points }}</div>
              <div class="col" :style="{ height: (t.points / maxTrend) * 100 + '%' }"></div>
              <div class="cl">{{ t.date.slice(5) }}</div>
            </div>
          </div>
        </div>
        <!-- 六簇平均掌握度 -->
        <div class="card">
          <div class="card-title">六簇平均掌握度（%）</div>
          <div class="bar-row" v-for="c in data.clusters" :key="c.cluster">
            <div class="bl">{{ c.name }}</div>
            <div class="bt"><i :style="{ width: c.level + '%', background: clusterColor(c.cluster) }"></i></div>
            <div class="bv">{{ c.level }}%</div>
          </div>
        </div>
      </div>

      <div class="mgrid c2" style="margin-bottom: 14px">
        <!-- 排行榜 -->
        <div class="card">
          <div class="card-title">排行榜
            <span class="pills" style="margin: 0 0 0 auto; margin-left: auto">
              <span class="pill sm" :class="{ on: lbTab === 'points' }" @click="lbTab = 'points'">积分</span>
              <span class="pill sm" :class="{ on: lbTab === 'mastery' }" @click="lbTab = 'mastery'">掌握度</span>
              <span class="pill sm" :class="{ on: lbTab === 'hours' }" @click="lbTab = 'hours'">学时</span>
            </span>
          </div>
          <table class="atable">
            <thead><tr><th style="width: 46px">名次</th><th>学生</th><th style="width: 90px; text-align: right">数值</th></tr></thead>
            <tbody>
              <tr v-for="r in lb" :key="r.student_no">
                <td>{{ ['🥇', '🥈', '🥉'][r.rank - 1] || r.rank }}</td>
                <td>{{ r.name }} <span style="color: var(--text-3); font-size: 12px">{{ r.student_no }}</span></td>
                <td class="num" style="text-align: right; font-weight: 700">{{ r.value }}</td>
              </tr>
              <tr v-if="!lb.length"><td colspan="3" style="color: var(--text-3); text-align: center; padding: 18px">暂无学生数据</td></tr>
            </tbody>
          </table>
        </div>
        <!-- 题型 + 班级弱项 -->
        <div>
          <div class="card" style="margin-bottom: 14px">
            <div class="card-title">题库题型分布</div>
            <div class="bar-row" v-for="(c, t) in data.qtypes" :key="t" style="margin-bottom: 8px">
              <div class="bl">{{ t }}</div>
              <div class="bt"><i :style="{ width: (c / Math.max(...Object.values(data.qtypes), 1)) * 100 + '%', background: '#64748b' }"></i></div>
              <div class="bv">{{ c }} 题</div>
            </div>
          </div>
          <div class="card">
            <div class="card-title">班级弱项（答错率 Top）</div>
            <table class="atable">
              <tbody>
                <tr v-for="w in data.weak_clusters.slice(0, 5)" :key="w.cluster">
                  <td>{{ w.name }}</td>
                  <td style="color: var(--text-3); font-size: 12px">{{ w.n }} 次作答</td>
                  <td class="num" style="text-align: right; font-weight: 700" :style="{ color: w.rate > 50 ? 'var(--primary)' : 'var(--text-2)' }">{{ w.rate }}%</td>
                </tr>
                <tr v-if="!data.weak_clusters.length"><td style="color: var(--text-3); text-align: center; padding: 18px">暂无作答数据</td></tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- 学时统计 -->
      <div class="card">
        <div class="card-title">学时统计（按学生）<span style="font-size: 11px; color: var(--text-3); font-weight: 400; margin-left: 8px">AI 问答按实际耗时 · 练习按交卷时长 · 复习按次</span></div>
        <table class="atable">
          <thead><tr><th style="width: 50px">#</th><th>学生</th><th>学号</th><th style="width: 110px; text-align: right">学时</th></tr></thead>
          <tbody>
            <tr v-for="(h, i) in data.hours" :key="h.student_no">
              <td>{{ i + 1 }}</td>
              <td>{{ h.name }}</td>
              <td style="color: var(--text-3)">{{ h.student_no }}</td>
              <td class="num" style="text-align: right; font-weight: 700">{{ h.hours }} 学时</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
    <div v-else-if="!loading" class="card" style="color: var(--text-3)">加载中…</div>

    <!-- 重置确认 -->
    <div v-if="showReset" class="mask" @click.self="showReset = false">
      <div class="modal">
        <div class="modal-h">演示数据重置<span class="more" @click="showReset = false">✕</span></div>
        <p style="font-size: 13.5px; color: var(--text-2); line-height: 1.9">
          将清空 3 个演示学生（S2026001-3）的积分、掌握度、练习/模拟考记录、错题、对话、学时，并删除他们生成的考卷，把 S2026001 恢复到标准演示基线（128 分 / 3 道错题 / 一条四栏问答），S2026001-3 与 T2026 的密码将重置为 123456。其余账号、题库（含 AI 生成题）与管理数据不受影响。
        </p>
        <div style="display: flex; gap: 10px; margin-top: 18px">
          <button class="btn sm" @click="doReset">确认重置</button>
          <button class="btn sm ghost" @click="showReset = false">取消</button>
        </div>
      </div>
    </div>
  </div>
</template>