<script setup>
import { onMounted, ref } from 'vue'
import { api, clusterName, clusterColor } from '../../api'

const data = ref(null)
const err = ref('')

async function load() {
  err.value = ''
  try {
    data.value = await api.statsWrong()
  } catch (e) {
    err.value = e.message
  }
}
onMounted(load)
</script>

<template>
  <div class="page" v-if="data">
    <div style="font-size: 19px; font-weight: 700; margin-bottom: 16px">班级错题分析</div>
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