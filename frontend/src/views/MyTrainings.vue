<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../api'

const items = ref([])
const loading = ref(true)
const err = ref('')
const TAG = { '未开始': 'blue', '进行中': 'red', '已完成': 'green', '已结束': 'gray' }

async function load() {
  err.value = ''
  try {
    const r = await api.myTrainings()
    items.value = r.items || []
  } catch (e) {
    err.value = e.message
  } finally {
    loading.value = false
  }
}
onMounted(load)
</script>

<template>
  <div class="page">
    <div class="card">
      <div class="card-title">🎫 我的培训</div>
      <div style="font-size: 12px; color: var(--text-3); margin-top: -6px; margin-bottom: 12px">
        教师在「培训管理」为你报名的期次 · 完成状态由教师标记，这里实时同步
      </div>

      <div v-if="loading" style="padding: 40px; text-align: center; color: var(--text-3)">加载中…</div>
      <div v-else-if="err" class="card" style="border-color: #fca5a5; color: #b91c1c">
        加载失败：{{ err }} <button class="btn sm" style="margin-left: 10px" @click="load">重试</button>
      </div>
      <div v-else-if="!items.length" style="padding: 36px 16px; text-align: center; color: var(--text-3); line-height: 2">
        <div style="font-size: 34px">🎫</div>
        <b style="color: var(--text-2); font-size: 14px">暂无报名的培训</b>
        <div style="font-size: 12.5px">教师在管理端「培训管理」为你报名后，这里会实时显示培训期次与进度<br>（报名后首页也会出现「我的培训」卡片）</div>
      </div>

      <template v-else>
        <div v-for="t in items" :key="t.id" class="tcard">
          <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap">
            <b style="font-size: 15px">{{ t.title }}</b>
            <span v-if="t.batch" class="tag blue">{{ t.batch }}</span>
            <span class="tag" :class="TAG[t.label] || 'gray'" style="margin-left: auto">{{ t.label }}</span>
          </div>
          <div style="font-size: 12.5px; color: var(--text-3); margin-top: 6px">
            {{ t.start_date || '未开始' }} ~ {{ t.end_date || '待定' }}
            <span v-if="t.teacher"> · 带训教师 {{ t.teacher }}</span>
          </div>
          <div v-if="t.note" style="font-size: 12.5px; color: var(--text-2); margin-top: 4px">📌 {{ t.note }}</div>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.tcard {
  border: 1px solid var(--line); border-radius: 10px; padding: 12px 14px;
  margin-bottom: 10px; background: #fff;
}
.tcard:last-child { margin-bottom: 0; }
</style>