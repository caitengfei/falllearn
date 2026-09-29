import { reactive } from 'vue'

const TOKEN_KEY = 'falllearn_token'
const USER_KEY = 'falllearn_user'

// auth 用 Vue 响应式对象：登录后 SPA 内 App 壳（顶栏用户名/教师 tab）立即刷新
export const auth = reactive({
  token: localStorage.getItem(TOKEN_KEY) || '',
  user: JSON.parse(localStorage.getItem(USER_KEY) || 'null'),
  save(token, user) {
    this.token = token
    this.user = user
    localStorage.setItem(TOKEN_KEY, token)
    localStorage.setItem(USER_KEY, JSON.stringify(user))
  },
  clear() {
    this.token = ''
    this.user = null
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
  },
  get ready() {
    return !!this.token
  }
})

async function request(path, { method = 'GET', body, headers = {}, timeout = 30000 } = {}) {
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), timeout)
  let res
  try {
    res = await fetch(path, {
      method,
      signal: ctrl.signal,
      headers: {
        'content-type': 'application/json',
        ...(auth.token ? { authorization: `Bearer ${auth.token}` } : {}),
        ...headers
      },
      body: body ? JSON.stringify(body) : undefined
    })
  } catch (e) {
    if (e.name === 'AbortError') throw new Error('请求超时，请稍后重试')
    throw new Error('网络异常，请检查连接')
  } finally {
    clearTimeout(timer)
  }
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    // 停用账号：清登录态回登录页（403 + 特定文案，与 401 同样处理）
    if (res.status === 403 && auth.ready && typeof data.detail === 'string' && data.detail.includes('账号已停用')) {
      auth.clear()
      location.href = '/login'
    }
    if (res.status === 401 && auth.ready) {
      auth.clear()
      location.href = '/login'
    }
    // FastAPI 422 的 detail 是数组：规范化成可读中文，避免弹 [object Object]
    let msg = data.detail || `HTTP ${res.status}`
    if (Array.isArray(msg)) {
      msg = msg.map((e) => {
        const loc = (e.loc || []).slice(1).join('.')
        const field = loc ? `${loc}：` : ''
        return field + (e.msg || '参数错误')
      }).join('；')
      msg = `参数错误（${msg}）`
    }
    throw new Error(msg)
  }
  return data
}

export const api = {
  login: (student_no, password) =>
    request('/api/auth/login', { method: 'POST', body: { student_no, password } }),
  me: () => request('/api/auth/me'),
  logout: () => request('/api/auth/logout', { method: 'POST' }),

  ask: (question) => request('/api/learn/ask', { method: 'POST', body: { question } }),
  answer: (log_id, option_index) =>
    request('/api/learn/answer', { method: 'POST', body: { log_id, option_index } }),
  status: (session_id, log_id) =>
    request(`/api/learn/status?session_id=${session_id}&log_id=${log_id}`),
  learnHistory: () => request('/api/learn/history'),

  quizStart: (kind = 'daily', exam_id = 0) => request('/api/quiz/start', { method: 'POST', body: { kind, exam_id } }),
quizWeak: () => request('/api/quiz/weak'),
  quizSubmit: (attempt_id, answers) =>
    request('/api/quiz/submit', { method: 'POST', body: { attempt_id, answers } }),
  quizSummary: () => request('/api/quiz/summary'),
  quizReport: () => request('/api/quiz/report'),
  quizReportAi: () => request('/api/quiz/report/ai', { method: 'POST', timeout: 90000 }),
  quizAssignments: () => request('/api/quiz/assignments'),
  quizResult: (attempt_id) => request(`/api/quiz/result/${attempt_id}`),

  wrongList: (status = 'active') => request(`/api/wrong?status=${status}`),
  wrongReview: (question_id, answer) =>
    request('/api/wrong/review', { method: 'POST', body: { question_id, answer } }),

  today: () => request('/api/game/today'),
  checkin: () => request('/api/game/checkin', { method: 'POST', body: {} }),
  points: () => request('/api/game/points'),
  badges: () => request('/api/game/badges'),
  leaderboard: () => request('/api/game/leaderboard'),

  adminDashboard: () => request('/api/admin/dashboard'),
  adminReset: () => request('/api/admin/reset-demo', { method: 'POST', body: {} }),

  // ---------- 管理后台 · 业务 ----------
  banners: () => request('/api/admin/banners'),
  bannerSave: (b) => request('/api/admin/banners', { method: 'POST', body: b }),
  bannerUpdate: (id, b) => request(`/api/admin/banners/${id}`, { method: 'PUT', body: b }),
  bannerDelete: (id) => request(`/api/admin/banners/${id}`, { method: 'DELETE' }),
  uploadImage: (file) => {
    const fd = new FormData()
    fd.append('file', file)
    return fetch('/api/admin/upload', { method: 'POST', headers: { authorization: `Bearer ${auth.token}` }, body: fd })
      .then((r) => r.json())
  },
  notices: () => request('/api/admin/announcements'),
  noticeSave: (n) => request('/api/admin/announcements', { method: 'POST', body: n }),
  noticeUpdate: (id, n) => request(`/api/admin/announcements/${id}`, { method: 'PUT', body: n }),
  noticeDelete: (id) => request(`/api/admin/announcements/${id}`, { method: 'DELETE' }),
  pubBanners: () => request('/api/content/banners'),
  pubNotices: () => request('/api/content/announcements'),

  adminExams: (status = '', student_id = 0) => {
    const qs = []
    if (status) qs.push(`status=${status}`)
    if (student_id) qs.push(`student_id=${student_id}`)
    return request(`/api/admin/exams${qs.length ? '?' + qs.join('&') : ''}`)
  },
  adminExamDetail: (id) => request(`/api/admin/exams/${id}`),
  adminExamsCsv: (status = '', student_id = 0) => {
    const qs = []
    if (status) qs.push(`status=${status}`)
    if (student_id) qs.push(`student_id=${student_id}`)
    return `/api/admin/exams/export${qs.length ? '?' + qs.join('&') : ''}`
  },
  adminAssignments: () => request('/api/admin/assignments'),
  adminAssign: (body) => request('/api/admin/assignments', { method: 'POST', body }),
  adminAssignDelete: (id) => request(`/api/admin/assignments/${id}`, { method: 'DELETE' }),
  metaClusters: () => request('/api/meta/clusters'),

  adminStudents: () => request('/api/admin/students'),
  studentCreate: (s) => request('/api/admin/students', { method: 'POST', body: s }),
  studentUpdate: (id, s) => request(`/api/admin/students/${id}`, { method: 'PUT', body: s }),
  accounts: () => request('/api/admin/accounts'),
  accountCreate: (a) => request('/api/admin/accounts', { method: 'POST', body: a }),
  accountUpdate: (id, a) => request(`/api/admin/accounts/${id}`, { method: 'PUT', body: a }),
  accountDelete: (id) => request(`/api/admin/accounts/${id}`, { method: 'DELETE' }),

  trainings: () => request('/api/admin/trainings'),
  trainingCreate: (t) => request('/api/admin/trainings', { method: 'POST', body: t }),
  trainingUpdate: (id, t) => request(`/api/admin/trainings/${id}`, { method: 'PUT', body: t }),
  trainingEnroll: (id, student_ids, status) =>
    request(`/api/admin/trainings/${id}/enroll`, { method: 'POST', body: { student_ids, status } }),
  trainingSetStatus: (tid, sid, status) =>
    request(`/api/admin/trainings/${tid}/students/${sid}/status`, { method: 'POST', body: { status } }),
  trainingDelete: (id) => request(`/api/admin/trainings/${id}`, { method: 'DELETE' }),

  statsOverview: () => request('/api/admin/stats/overview'),
  statsTrainings: () => request('/api/admin/stats/trainings'),
  statsWrong: () => request('/api/admin/stats/wrong'),

  kbSearch: (q, dim) => request(`/api/kb/search?q=${encodeURIComponent(q || '')}${dim ? `&dim=${encodeURIComponent(dim)}` : ''}`),
  kbDoc: (path) => request(`/api/kb/doc?path=${encodeURIComponent(path)}`),

  // ---------- 管理后台 · AI ----------
  aiModels: () => request('/api/admin/ai/models', { timeout: 300000 }),
  aiModel: (provider, model) => request('/api/admin/ai/model', { method: 'POST', body: { provider, model }, timeout: 300000 }),
  aiDirect: () => request('/api/admin/ai/direct'),
  aiDirectSave: (cfg) => request('/api/admin/ai/direct', { method: 'POST', body: cfg, timeout: 120000 }),
  aiDirectTest: () => request('/api/admin/ai/direct/test', { method: 'POST', body: {}, timeout: 120000 }),
  aiDirectClear: () => request('/api/admin/ai/direct', { method: 'DELETE' }),
  aiKb: () => request('/api/admin/ai/kb'),
  aiKbWrite: (path, content, force = false) => request('/api/admin/ai/kb', { method: 'POST', body: { path, content, force } }),
  aiKbDelete: (path) => request('/api/admin/ai/kb', { method: 'DELETE', body: { path } }),
  aiGenerate: (cluster_id, count, qtypes) =>
    request('/api/admin/ai/generate-questions', { method: 'POST', body: { cluster_id, count, qtypes }, timeout: 330000 }),
  aiQuestionsSave: (items) => request('/api/admin/ai/questions/save', { method: 'POST', body: { items } }),
  aiGrade: (attempt_id) =>
    request('/api/admin/ai/grade', { method: 'POST', body: { attempt_id }, timeout: 330000 }),
  aiGrades: (attempt_id = 0) => request(`/api/admin/ai/grades?attempt_id=${attempt_id}`)
}

// 知识簇元信息（6 簇；general=护理通识仅用于题目展示映射）
export const CLUSTERS = [
  { id: 'morse', name: 'Morse评估', color: '#3B82F6' },
  { id: 'env', name: '环境防控', color: '#22C55E' },
  { id: 'five', name: '五步处置', color: '#E4393C' },
  { id: 'fracture', name: '骨折识别', color: '#F5A623' },
  { id: 'record', name: '记录上报', color: '#8B5CF6' },
  { id: 'cpr', name: 'CPR启动', color: '#0EA5E9' }
]
export const clusterColor = (id) => (CLUSTERS.find((c) => c.id === id) || {}).color || '#9CA3AF'
export const clusterName = (id) => {
  if (id === 'general') return '护理通识'
  return (CLUSTERS.find((c) => c.id === id) || {}).name || id
}

// 簇题库规模（真实入库数，用于知识卡信息量）
export const CLUSTER_QCOUNT = { morse: 20, env: 58, five: 79, fracture: 9, record: 35, cpr: 2, general: 1150 }

// 簇知识点（02-课/知识点梳理.md 摘编；首页知识卡 + 学习中心抽屉共用）
export const CLUSTER_KNOWLEDGE = {
  morse: ['Morse 量表 6 条目，总分 0–125', '低危 <25 / 中危 25–44 / 高危 ≥45', '再评估时点：入住、每年≥1次、跌倒后、住院后、病情或用药变化'],
  env: ['「五查」：查光线/地面/设施/用具/个人因素', 'MZ/T 185—2021 机构环境排查 10 项', '风险因素三分类：环境 / 个人 / 药物（备赛按六因素口径）'],
  five: ['五步法：①评估意识与伤情 ②不急于搬动 ③呼叫支援 ④按预案处置 ⑤记录上报', '「不要急于扶起、分情况处理」是核心理念', '五步顺序与细节是赛项评分主线'],
  fracture: ['疑诊线索：畸形、异常活动、骨擦感、剧痛、不能负重', '就地制动：不搬动、不牵引、固定后转运', '「未制动即搬动」是重扣分/一票否决点'],
  record: ['记录单 12 要素（时间/地点/情境/主诉/评估…）', '上报时限与对象要明确', '「低危也要报」：全量数据支撑趋势分析'],
  cpr: ['意识不清/呼吸心跳骤停 → 立即启动心肺复苏', '先确认环境与意识，呼叫支援再按压', '理论高频考点：CPR 启动条件']
}

// 评委演示引导（学生端首页卡 + 顶栏 ? 弹窗共用；教师端数据总览卡）
export const DEMO_GUIDE = {
  student: [
    { ic: '🤖', t: 'AI 老师 · 逐字流式作答', d: '提问后四栏答案逐字生成，不再等 30 秒', to: '/learn', ask: '老人摔倒了怎么办？完整讲讲' },
    { ic: '📚', t: '知识库 · 全文检索', d: '26 份岗课赛证文档搜原文，一键问 AI 划重点', to: '/kb' },
    { ic: '📝', t: '教师布置 · 完成即判分', d: '「五步处置专项」5 题 10 分钟，交卷秒出成绩', to: '/practice?menu=teacher' },
    { ic: '📊', t: '学习报告 · AI 分析', d: '得分趋势 / 错题分布 / 14 天活跃 + AI 学习诊断', to: '/report' },
    { ic: '📕', t: '错题本 · 间隔复习', d: '次日到期 → 第 3 天，连对 2 次标记掌握', to: '/wrong' },
    { ic: '👨‍🏫', t: '教师视角', d: '登录页切陈老师（T2026 / 123456）看布置闭环与班级错题', to: '/login' }
  ],
  teacher: [
    { ic: '📝', t: '布置练习', d: '按知识点出全班练习（自动标题 / 截止 / 积分）', to: '/admin/exams' },
    { ic: '📈', t: '班级错题分析', d: '高频错题 TOP10 + 知识点正确率，精准教学', to: '/admin/stats?tab=wrong' },
    { ic: '📊', t: '数据总览', d: '全班活跃 / 学时 / AI 问答 / 掌握度，卡片下钻', to: '/admin' },
    { ic: '🤖', t: 'AI 管理', d: '直连通道模型选择 · AI 出题判卷', to: '/admin/ai' }
  ]
}