<script setup>
import { onMounted, ref } from 'vue'
import { api, auth, CLUSTERS } from '../api'

const me = ref({})
const pointsLog = ref([])
const badges = ref([])

function radarPoints() {
  // 画布 320×300（原 260×260）：原布局下右侧「环境防控 99」等标签超出画布被裁切（同事审核建议 3），
  // 现加大画布并把标签改为「名称 / 分值」两行居中，六簇标签全部完整可见。
  const n = CLUSTERS.length
  const cx = 160, cy = 146, R = 88, LR = R + 18
  const rings = []
  for (const f of [1, 0.66, 0.33]) {
    const pts = []
    for (let i = 0; i < n; i++) {
      const a = (Math.PI * 2 * i) / n - Math.PI / 2
      pts.push(`${cx + Math.cos(a) * R * f},${cy + Math.sin(a) * R * f}`)
    }
    rings.push(pts.join(' '))
  }
  const data = []
  const axes = []
  const labels = []
  for (let i = 0; i < n; i++) {
    const a = (Math.PI * 2 * i) / n - Math.PI / 2
    const lv = (me.value.mastery || {})[CLUSTERS[i].id] ?? 0
    data.push(`${cx + Math.cos(a) * R * (lv / 100)},${cy + Math.sin(a) * R * (lv / 100)}`)
    axes.push(`${cx},${cy} ${cx + Math.cos(a) * R},${cy + Math.sin(a) * R}`)
    labels.push({ x: cx + Math.cos(a) * LR, y: cy + Math.sin(a) * LR, name: CLUSTERS[i].name, lv: Math.round(lv) })
  }
  return { rings, data: data.join(' '), axes, labels }
}
const radar = ref(radarPoints())

const err = ref('')
async function load() {
  err.value = ''
  try {
    const [m, p, b] = await Promise.all([api.me(), api.points(), api.badges()])
    me.value = m
    radar.value = radarPoints()
    pointsLog.value = p.log.filter((x) => x.delta !== 0).slice(0, 20)
    badges.value = b
  } catch (e) {
    err.value = e.message // 原为静默：雷达/勋章/积分全空且无任何提示
  }
}
onMounted(load)
</script>

<template>
  <div class="page" style="max-width: 1080px">
    <div v-if="err" class="card" style="border-color: #fca5a5; color: #b91c1c; margin-bottom: 12px">
      数据加载失败：{{ err }} <button class="btn sm" style="margin-left: 12px" @click="load">重试</button>
    </div>
    <div class="mine-grid">
      <div>
        <div class="card">
          <div class="card-title">📊 掌握度雷达（六簇 · 练习/复习/AI 问答共同驱动）</div>
          <div class="radar-box">
            <svg width="320" height="300" viewBox="0 0 320 300" class="radar-svg">
              <polygon v-for="(r, i) in radar.rings" :key="i" :points="r" fill="none" stroke="#eceef1" />
              <line v-for="(a, i) in radar.axes" :key="'a' + i" :x1="a.split(' ')[0].split(',')[0]" :y1="a.split(' ')[0].split(',')[1]" :x2="a.split(' ')[1].split(',')[0]" :y2="a.split(' ')[1].split(',')[1]" stroke="#eceef1" />
              <polygon :points="radar.data" fill="rgba(228,57,60,.18)" stroke="#e4393c" stroke-width="2" />
              <text v-for="(l, i) in radar.labels" :key="'l' + i" :x="l.x" :y="l.y" text-anchor="middle" font-size="11" fill="#6b7280">
                <tspan :x="l.x" dy="0">{{ l.name }}</tspan>
                <tspan :x="l.x" dy="13" font-size="11.5" font-weight="700" fill="#c62828">{{ l.lv }}</tspan>
              </text>
            </svg>
          </div>
        </div>

        <div class="card mt16">
          <div class="card-title">🏅 勋章墙（{{ badges.filter((b) => b.earned).length }} / {{ badges.length }}）</div>
          <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px">
            <div v-for="b in badges" :key="b.id" class="badge-cell" :class="{ earned: b.earned }">
              <div class="badge-ic">{{ b.icon }}</div>
              <div class="badge-name">{{ b.name }}</div>
              <div class="badge-rule">{{ b.rule || '—' }}</div>
              <div v-if="!b.earned && b.progress != null" class="badge-prog"><i :style="{ width: b.progress + '%' }"></i></div>
              <div class="badge-state">{{ b.earned ? '已获得 ✓' : (b.progress != null ? `进度 ${b.progress}/60` : '未解锁') }}</div>
            </div>
          </div>
        </div>
      </div>

      <div>
        <div class="card">
          <div class="card-title">{{ auth.user?.name }} · 概览</div>
          <div style="font-size: 12.5px; color: var(--text-3); margin-bottom: 10px">
            {{ auth.user?.student_no }} · {{ auth.user?.role === 'teacher' ? '教师' : '养老专业 2026 级' }}
          </div>
          <div class="stu-stats" style="grid-template-columns: 1fr 1fr">
            <div class="stat-item"><div class="v mono">{{ me.points || 0 }}</div><div class="k">积分</div></div>
            <div class="stat-item"><div class="v mono">{{ me.practice_count || 0 }}</div><div class="k">完成练习</div></div>
            <div class="stat-item"><div class="v mono">{{ me.hours || 0 }}</div><div class="k">学时</div></div>
            <div class="stat-item"><div class="v mono">{{ me.last_score ?? '—' }}</div><div class="k">上次得分</div></div>
            <div class="stat-item"><div class="v mono">{{ me.badge_count || 0 }}</div><div class="k">勋章</div></div>
          </div>
        </div>
        <div class="card mt16">
          <div class="card-title">积分明细</div>
          <div v-if="!pointsLog.length" class="empty">暂无积分记录</div>
          <div v-for="(p, i) in pointsLog" :key="i" class="row-item" style="padding: 7px 0">
            <div class="rmain">
              <div class="rtitle" style="font-weight: 500; font-size: 13px">{{ p.reason }}</div>
              <div style="font-size: 11px; color: var(--text-3)" class="mono">
                {{ new Date(p.at * 1000).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) }}
              </div>
            </div>
            <div class="mono" style="font-weight: 700" :style="{ color: p.delta > 0 ? '#15803d' : 'var(--text-3)' }">
              {{ p.delta > 0 ? '+' : '' }}{{ p.delta }}
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.mine-grid { display: grid; grid-template-columns: 1fr 380px; gap: 16px; }
/* 雷达画布 320×300：窄屏（360px）自适应缩放，避免 2px 横向溢出 */
.radar-box { display: flex; justify-content: center; }
.radar-svg { max-width: 100%; height: auto; }
@media (max-width: 900px) { .mine-grid { grid-template-columns: 1fr; } }
.badge-cell {
  border: 1px solid var(--line); border-radius: 10px; padding: 14px 8px; text-align: center;
  background: #fff; transition: all .15s;
}
.badge-cell.earned { border-color: #f5c8c8; background: linear-gradient(180deg, #fff, #fff5f5); }
.badge-cell:not(.earned) .badge-ic { filter: grayscale(1); opacity: .4; }
.badge-ic { font-size: 30px; }
.badge-name { font-size: 12.5px; font-weight: 600; margin-top: 6px; }
.badge-rule { font-size: 10.5px; color: var(--text-3); margin-top: 3px; line-height: 1.5; min-height: 30px; }
.badge-prog {
  height: 4px; background: var(--bg); border-radius: 2px; overflow: hidden; margin-top: 6px;
}
.badge-prog i { display: block; height: 100%; background: var(--primary-deep); border-radius: 2px; }
.badge-state { font-size: 11px; margin-top: 5px; color: var(--text-3); }
.badge-cell.earned .badge-state { color: var(--primary-text); font-weight: 600; }
</style>