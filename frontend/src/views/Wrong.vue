<script setup>
import { onMounted, ref } from 'vue'
import { router } from '../router'
import { api, clusterName, clusterColor } from '../api'

const list = ref([])
const pill = ref('active')
const loading = ref(true)
const modal = ref(null) // {mode:'explain'|'redo', q}
const picked = ref('')
const reviewResult = ref(null)
const busy = ref(false)

async function load() {
  loading.value = true
  try {
    const r = await api.wrongList(pill.value)
    list.value = r.items || []
  } catch {}
  loading.value = false
}
onMounted(load)

function openExplain(q) {
  modal.value = { mode: 'explain', q }
  reviewResult.value = null
}
function openRedo(q) {
  modal.value = { mode: 'redo', q }
  picked.value = ''
  reviewResult.value = null
}
function shortSource(s) {
  if (!s) return ''
  // 显示文件名 + 目录段，截断过长路径
  const name = s.split(/[\\/（]/)[0] || s
  return name.length > 34 ? name.slice(0, 34) + '…' : name
}

async function doReview() {
  const m = modal.value
  if (!m || !picked.value) return
  busy.value = true
  try {
    const r = await api.wrongReview(m.q.id, picked.value)
    reviewResult.value = r
    if (r.correct) setTimeout(() => { modal.value = null; load() }, 2000)
  } catch (e) {
    alert(e.message)
  }
  busy.value = false
}
</script>

<template>
  <div class="page" style="max-width: 880px">
    <div class="card" style="padding: 12px 20px; display: flex; align-items: center; gap: 10px; font-size: 13px">
      <span>📕 错题本</span>
      <span class="tag red">待复习 {{ list.length }}</span>
      <span style="color: var(--text-3); margin-left: auto">间隔复习：首错<b>次日</b>到期 → 答对后<b>第 3 天</b> → <b>连对 2 次</b>标记掌握 · 答错回到次日</span>
    </div>

    <div class="pills mt16">
      <span class="pill" :class="{ on: pill === 'active' }" @click="pill = 'active'; load()">待复习</span>
      <span class="pill" :class="{ on: pill === 'mastered' }" @click="pill = 'mastered'; load()">已掌握</span>
    </div>

    <div v-if="!loading && !list.length" class="card mt16 empty">
      暂无{{ pill === 'active' ? '待复习' : '' }}错题
      <template v-if="pill === 'active'">：练习/模拟考答错的题会自动进来，连对 2 次后移入「已掌握」</template>
    </div>

    <div v-for="x in list" :key="x.id" class="card mt16" style="padding: 18px 22px">
      <div style="display: flex; gap: 8px; margin-bottom: 10px">
        <span class="tag" :style="{ background: clusterColor(x.cluster) + '18', color: clusterColor(x.cluster) }">{{ clusterName(x.cluster) }}</span>
        <span class="tag blue">{{ x.type }}</span>
        <span v-if="x.status === 'mastered'" class="tag green">已掌握 ✓</span>
        <span v-if="x.due && pill === 'active'" class="tag red">今日到期</span>
        <span class="tag">{{ x.review_count }} 次复习</span>
        <span style="margin-left: auto; font-size: 12px; color: var(--text-3)" class="mono">
          首错 {{ new Date(x.first_wrong_at * 1000).toLocaleDateString('zh-CN') }}
        </span>
      </div>
      <div style="font-size: 14.5px; line-height: 1.75">{{ x.stem }}</div>
      <div style="font-size: 13px; color: var(--text-2); margin-top: 10px; line-height: 1.9">
        <div v-for="(o, i) in x.options" :key="i">{{ 'ABCD'[i] }}. {{ o }}</div>
      </div>
      <div style="font-size: 12px; color: var(--text-3); margin-top: 10px">
        来源：<span class="mono">{{ shortSource(x.source_doc) }}</span>
        <span v-if="x.correct_answer" style="margin-left: 14px; color: var(--success); font-weight: 700">正确答案：{{ x.correct_answer }}</span>
      </div>
      <div style="display: flex; gap: 10px; margin-top: 14px">
        <button class="btn sm" @click="openRedo(x)">重答这道题</button>
        <button class="btn sm ghost" @click="openExplain(x)">看讲解</button>
        <button v-if="x.cluster" class="btn sm ghost" @click="router.push({ path: '/learn', query: { cluster: x.cluster } })">学这一簇</button>
      </div>
    </div>

    <!-- 讲解 -->
    <div v-if="modal && modal.mode === 'explain'" class="mask" @click.self="modal = null">
      <div class="modal" style="max-width: 560px">
        <div class="modal-h">📖 讲解 <span class="more" @click="modal = null">✕</span></div>
        <div style="font-size: 14.5px; line-height: 1.75">{{ modal.q.stem }}</div>
        <div style="margin-top: 14px; font-size: 14px">
          <div v-for="(o, i) in modal.q.options" :key="i"
            :style="{ padding: '8px 12px', borderRadius: 8, marginBottom: 6, fontSize: 13.5, border: '1.5px solid ' + (modal.q.answer.includes('ABCD'[i]) ? 'var(--success)' : 'var(--line)'), background: modal.q.answer.includes('ABCD'[i]) ? 'var(--success-light)' : '#fff' }">
            <b :style="{ color: modal.q.answer.includes('ABCD'[i]) ? 'var(--success)' : 'inherit' }">
              {{ 'ABCD'[i] }} {{ modal.q.answer.includes('ABCD'[i] ) ? '✓ ' : '' }}
            </b>{{ o }}
          </div>
        </div>
        <div style="font-size: 13px; color: var(--text-2); margin-top: 12px; line-height: 1.8">
          正确答案：<b style="color: var(--success)">{{ modal.q.answer }}</b><br>
          出处：<span class="mono" style="font-size: 12px">{{ shortSource(modal.q.source_doc) }}</span>
        </div>
        <div style="display: flex; gap: 10px; margin-top: 18px; justify-content: flex-end">
          <button class="btn sm ghost" @click="modal = null">关闭</button>
          <button class="btn sm" @click="openRedo(modal.q)">重答这道题</button>
        </div>
      </div>
    </div>

    <!-- 重答 -->
    <div v-if="modal && modal.mode === 'redo'" class="mask" @click.self="modal = null">
      <div class="modal" style="max-width: 560px">
        <div class="modal-h">✏ 重答 · {{ clusterName(modal.q.cluster) }} <span class="more" @click="modal = null">✕</span></div>
        <div v-if="reviewResult && reviewResult.correct" style="text-align: center; padding: 30px 0">
          <div style="font-size: 44px">🎉</div>
          <div style="font-size: 15px; font-weight: 700; margin-top: 8px">答对了 +10 积分</div>
          <div style="font-size: 12.5px; color: var(--text-3); margin-top: 6px">
            {{ reviewResult.status === 'mastered' ? '连对 2 次，已标记掌握 ✓' : '再答对 1 次即标记掌握（下次到期：第 3 天）' }}
          </div>
        </div>
        <template v-else-if="reviewResult">
          <div style="text-align: center; padding: 14px 0 4px">
            <div style="font-size: 36px">💪</div>
            <div style="font-size: 14px; font-weight: 700; margin-top: 6px">还差一点，回到次日再练</div>
            <div style="font-size: 13px; color: var(--text-2); margin-top: 8px">{{ reviewResult.feedback }}</div>
          </div>
          <div style="display: flex; justify-content: center; margin-top: 16px">
            <button class="btn sm" @click="picked = ''; reviewResult = null">再试一次</button>
          </div>
        </template>
        <template v-else>
          <div style="font-size: 14.5px; line-height: 1.75">{{ modal.q.stem }}</div>
          <div class="opt-list" style="margin-top: 14px">
            <div v-for="(o, i) in modal.q.options" :key="i"
              class="opt" :class="{ sel: (modal.q.type === '多选' ? picked.includes('ABCD'[i]) : picked === 'ABCD'[i]) }"
              @click="modal.q.type === '多选' ? (picked = (picked.includes('ABCD'[i]) ? picked.replace('ABCD'[i], '') : picked + 'ABCD'[i]).split('').sort().join('')) : (picked = picked === 'ABCD'[i] ? '' : 'ABCD'[i])">
              <b>{{ 'ABCD'[i] }}</b> {{ o }}
            </div>
          </div>
          <div style="display: flex; justify-content: flex-end; margin-top: 18px">
            <button class="btn sm" :disabled="!picked || busy" @click="doReview()">{{ busy ? '判分中…' : '提交' }}</button>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.opt {
  border: 1.5px solid var(--line); border-radius: 10px; padding: 11px 14px;
  font-size: 14px; cursor: pointer; transition: all .12s; display: flex; gap: 10px; margin-bottom: 8px;
}
.opt:hover { border-color: var(--primary); }
.opt.sel { border-color: var(--primary); background: var(--primary-light); font-weight: 600; }
.opt b { color: var(--primary); min-width: 18px; }
</style>