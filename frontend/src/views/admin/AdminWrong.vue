<script setup>
import { onMounted, ref } from 'vue'
import { api, clusterName, clusterColor } from '../../api'

const data = ref(null)
const err = ref('')
const cls = ref('')            // ''=全部班级
const classes = ref([])

async function load() {
  err.value = ''
  try {
    const r = await api.statsWrong(cls.value)
    data.value = r
    classes.value = r.classes || []
  } catch (e) {
    err.value = e.message
  }
}
function switchCls(c) {
  cls.value = c
  load()
}
onMounted(load)
</script>

<template>
  <div class="page" v-if="data">
    <div style="font-size: 19px; font-weight: 700; margin-bottom: 12px">班级错题分析</div>
    <div class="pills" style="margin-bottom: 14px">
      <span class="pill" :class="{ on: cls === '' }" @click="switchCls('')">全部班级</span>
      <span v-for="c in classes" :key="c" class="pill" :class="{ on: cls === c }" @click="switchCls(c)">{{ c }}</span>
      <span class="pill" :class="{ on: cls === '__none__' }" @click="switchCls('__none__')">未分班</span>
    </div>
    <!-- 分班对比（按班级分开 · 最弱簇自动定位） -->
    <div class="card" style="margin-bottom: 14px">
      <div class="card-title">分班对比<span style="font-size: 11px; color: var(--text-3); font-weight: 400; margin-left: 8px">各班作答正确率与错题情况 · 最弱簇按该班全部作答自动定位</span></div>
      <table class="atable">
        <thead><tr><th>班级</th><th>学生</th><th>活跃错题</th><th>已掌握</th><th>总体正确率</th><th>最弱簇（自动定位）</th></tr></thead>
        <tbody>
          <tr v-for="p in (data.per_class || [])" :key="p.class">
            <td style="font-weight: 600">{{ p.class }}</td>
            <td class="num">{{ p.students }}</td>
            <td class="num" :style="{ color: p.active ? 'var(--primary)' : 'var(--text-3)' }">{{ p.active }}</td>
            <td class="num">{{ p.mastered }}</td>
            <td class="num" style="font-weight: 700">{{ p.rate != null ? p.rate + '%' : '—' }}</td>
            <td>
              <span v-if="p.weakest" class="tag" style="background: #fef2f2; color: #b91c1c; border: 1px solid #fecaca">
                {{ p.weakest.name }} · 正确率 {{ p.weakest.rate }}%
              </span>
              <span v-else style="color: var(--text-3); font-size: 12px">暂无作答记录</span>
            </td>
          </tr>
          <tr v-if="!(data.per_class || []).length"><td colspan="6" style="color: var(--text-3); text-align: center; padding: 18px">暂无学生数据</td></tr>
        </tbody>
      </table>
      <div v-if="!(data.classes || []).length" style="font-size: 12px; color: #b45309; background: #fffbeb; border: 1px solid #fde68a; border-radius: 8px; padding: 8px 12px; margin-top: 10px">
        当前还没有班级（学生都未分班）——到「学生管理 → 按名单批量分班」把学号名单粘贴归班后，这里会自动按班分开统计。
      </div>
    </div>
    <div class="card">
      <div class="card-title">班级 · 各知识点正确率（全部作答）</div>
      <div v-if="data.correct_rate.length">
        <div v-for="c in data.correct_rate" :key="c.cluster" class="wrow">
          <span class="wtag" :style="{ background: clusterColor(c.cluster) + '14', color: clusterColor(c.cluster) }">{{ clusterName(c.cluster) }}</span>
          <div class="bar-row" style="margin: 0; flex: 1">
            <div class="bt" style="flex: 1"><i :style="{ width: c.rate + '%', background: c.rate >= 80 ? '#22c55e' : c.rate >= 60 ? '#f5a623' : '#ef4444' }"></i></div>
            <div class="bv">{{ c.rate }}% · {{ c.n }} 题</div>
          </div>
        </div>
      </div>
      <div v-else style="color: var(--text-3); font-size: 13px; padding: 14px 0">学生还没有作答记录</div>

      <div class="subhead">高频错题 TOP 10（多少名学生的错题本里有这道题）</div>
      <table class="atable" v-if="data.top_wrong.length">
        <thead><tr><th style="width: 40px">#</th><th>题目</th><th>知识点</th><th>错题本学生数</th></tr></thead>
        <tbody>
          <tr v-for="(t, i) in data.top_wrong" :key="t.qid">
            <td class="num" style="font-weight: 700; color: i < 3 ? '#e4393c' : 'var(--text-3)'">{{ i + 1 }}</td>
            <td style="max-width: 420px"><span style="display: inline-block; max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap" :title="t.stem">{{ t.stem }}</span></td>
            <td><span class="tag" :style="{ background: clusterColor(t.cluster) + '14', color: clusterColor(t.cluster) }">{{ clusterName(t.cluster) }}</span></td>
            <td class="num" style="font-weight: 700; color: t.students_wrong >= 2 ? '#e4393c' : '#b45309'">{{ t.students_wrong }}</td>
          </tr>
        </tbody>
      </table>
      <div v-else style="color: var(--text-3); font-size: 13px; padding: 14px 0">班级暂无活跃错题 —— 等学生开始练习后这里会出现共性问题清单</div>
      <div class="wtip">教学建议：红色排名 = 多人共同的错误点，课堂上重点讲；配合「考试管理 · 布置练习」用对应知识点出一组题复测。</div>
    </div>
  </div>
  <div v-else class="page">
    <div v-if="err" class="card" style="border-color: #fca5a5; color: #b91c1c">加载失败：{{ err }} <button class="btn sm" style="margin-left: 12px" @click="load">重试</button></div>
    <div v-else class="card" style="color: var(--text-3)">加载中…</div>
  </div>
</template>

<style scoped>
.wrow { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
.wtag { font-size: 12px; font-weight: 700; padding: 3px 10px; border-radius: 6px; min-width: 74px; text-align: center; }
.subhead { font-size: 12.5px; font-weight: 700; color: var(--text-2); margin: 18px 0 10px; }
.wtip { font-size: 12px; color: var(--text-3); margin-top: 12px; line-height: 1.7; }
</style>