<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, auth } from '../api'

const route = useRoute()
const router = useRouter()
const sno = ref('')
const pwd = ref('')
const err = ref('')
const busy = ref(false)

const demos = [
  { tag: '学生', sno: 'S2026001', name: '张小明' },
  { tag: '学生', sno: 'S2026002', name: '李小红' },
  { tag: '学生', sno: 'S2026003', name: '王大锤' },
  { tag: '教师', sno: 'T2026', name: '陈老师' }
]
function fill(s) {
  sno.value = s.sno
  pwd.value = '123456'
}

async function doLogin() {
  if (!sno.value.trim() || !pwd.value) {
    err.value = '请输入学号/工号与密码（或点下方「一键体验」）'
    return
  }
  err.value = ''
  busy.value = true
  try {
    const r = await api.login(sno.value.trim(), pwd.value)
    auth.save(r.token, r.user)
    // 教师默认进管理后台，学生进首页
    router.push(route.query.next || (r.user.role === 'teacher' ? '/admin' : '/'))
  } catch (e) {
    err.value = e.message
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="lp-page">
    <div class="lp-shell login-card">
      <!-- 左：品牌区 -->
      <div class="lp-brand">
        <div class="lp-glow g1"></div>
        <div class="lp-glow g2"></div>
        <div class="lp-gridlines"></div>
        <div class="lp-brand-in login-head">
          <div class="lp-logo-row">
            <div class="lp-logo">康</div>
            <div class="lp-logo-name">康养智行</div>
          </div>
          <h1 class="lp-title">智慧养老<br />“岗课赛证”融通智能体</h1>
          <div class="lp-slogan">智护银龄 · 行稳致远</div>
          <div class="lp-divider"></div>
          <ul class="lp-feats">
            <li><span class="fi">🎯</span><span>首发场景：<b>跌倒预防与应急处置</b></span></li>
            <li><span class="fi">📚</span><span>四维编目：<b>岗 · 课 · 赛 · 证</b></span></li>
            <li><span class="fi">🚀</span><span>架构支持向<b>全技能照护赛训</b>扩展</span></li>
          </ul>
          <div class="lp-foot">46 份真实文档 · 1781 题结构化题库 · 六簇知识体系</div>
        </div>
      </div>

      <!-- 右：表单区 -->
      <div class="lp-form-wrap">
        <div class="lp-form-in">
          <div class="lp-f-head">
            <div class="lp-f-title">账号登录</div>
            <div class="lp-f-sub">学生 / 教师 · 均可一键体验</div>
          </div>
          <form class="lp-form login-body" @submit.prevent="doLogin">
            <div class="lp-field field">
              <label for="sno">学号 / 工号</label>
              <input id="sno" v-model="sno" name="username" autocomplete="username" placeholder="如 S2026001" />
            </div>
            <div class="lp-field field">
              <label for="pwd">密码</label>
              <input id="pwd" v-model="pwd" type="password" name="password" autocomplete="current-password" placeholder="请输入密码" />
            </div>
            <button type="submit" class="lp-btn btn" style="width: 100%; padding: 11px" :disabled="busy">
              <span v-if="busy" class="lp-spin"></span>
              {{ busy ? '登录中…' : '登 录' }}
            </button>
            <div v-if="err" class="lp-err err">{{ err }}</div>
          </form>
          <div class="lp-reg">
            老师发了邀请码？<router-link to="/register">用邀请码加入 →</router-link>
          </div>
          <div class="lp-demo">
            <div class="lp-demo-title">一键体验（密码 123456）</div>
            <div class="lp-demo-row">
              <button v-for="d in demos" :key="d.sno" type="button" class="lp-demo-btn dh-btn" :disabled="busy" @click="fill(d); doLogin()">
                <span class="lp-demo-tag dh-tag" :class="{ t: d.tag === '教师' }">{{ d.tag }}</span>
                <span class="lp-demo-sno">{{ d.sno }}</span>
                <span class="lp-demo-name">{{ d.name }}</span>
              </button>
            </div>
          </div>
          <div class="lp-privacy">不收集手机号 / 身份证号 · 演示账号均为虚构</div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.lp-page {
  min-height: 100vh; display: flex; align-items: center; justify-content: center;
  padding: 28px 16px;
  background:
    radial-gradient(1000px 520px at 12% -10%, rgba(228, 57, 60, .16), transparent 60%),
    radial-gradient(900px 500px at 105% 110%, rgba(29, 78, 216, .14), transparent 60%),
    linear-gradient(160deg, #0c1220, #111a2e 55%, #0c1220);
}
.lp-shell {
  width: min(1000px, 96vw); min-height: 600px; border-radius: 20px; overflow: hidden;
  display: grid; grid-template-columns: 46% 1fr;
  box-shadow: 0 30px 80px rgba(2, 6, 23, .55), 0 0 0 1px rgba(255, 255, 255, .06);
}

/* —— 左：品牌区 —— */
.lp-brand {
  position: relative; overflow: hidden; color: #fff;
  background:
    radial-gradient(420px 300px at -10% 0%, rgba(228, 57, 60, .35), transparent 65%),
    radial-gradient(380px 320px at 115% 110%, rgba(59, 130, 246, .22), transparent 60%),
    linear-gradient(165deg, #131c30, #0d1526 60%, #0a1120);
  display: flex;
}
.lp-glow { position: absolute; border-radius: 50%; filter: blur(2px); pointer-events: none; }
.lp-glow.g1 { width: 240px; height: 240px; right: -70px; top: -60px; background: radial-gradient(circle, rgba(228,57,60,.35), transparent 70%); }
.lp-glow.g2 { width: 200px; height: 200px; left: -60px; bottom: -70px; background: radial-gradient(circle, rgba(59,130,246,.28), transparent 70%); }
.lp-gridlines {
  position: absolute; inset: 0; pointer-events: none; opacity: .5;
  background-image: linear-gradient(rgba(255,255,255,.045) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,255,255,.045) 1px, transparent 1px);
  background-size: 44px 44px;
  mask-image: radial-gradient(420px 340px at 70% 30%, #000 30%, transparent 75%);
  -webkit-mask-image: radial-gradient(420px 340px at 70% 30%, #000 30%, transparent 75%);
}
.lp-brand-in {
  position: relative; z-index: 1; padding: 44px 38px 34px;
  display: flex; flex-direction: column;
}
.lp-logo-row { display: flex; align-items: center; gap: 12px; }
.lp-logo {
  width: 44px; height: 44px; border-radius: 12px; flex-shrink: 0;
  background: linear-gradient(135deg, #e4393c, #b91c1c);
  display: flex; align-items: center; justify-content: center;
  font-size: 22px; font-weight: 800; color: #fff;
  box-shadow: 0 8px 22px rgba(228, 57, 60, .4);
}
.lp-logo-name { font-size: 17px; font-weight: 700; letter-spacing: 2px; }
.lp-title {
  font-size: 23px; line-height: 1.55; font-weight: 800; margin: 30px 0 0;
  letter-spacing: .5px;
}
.lp-slogan {
  margin-top: 14px; font-size: 13px; letter-spacing: 4px; color: rgba(255, 255, 255, .8);
}
.lp-divider { height: 1px; background: linear-gradient(90deg, rgba(255,255,255,.28), transparent); margin: 26px 0 20px; }
.lp-feats { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 14px; }
.lp-feats li {
  display: flex; align-items: flex-start; gap: 10px;
  font-size: 12.5px; color: rgba(255, 255, 255, .82); line-height: 1.6;
}
.lp-feats .fi { flex-shrink: 0; width: 26px; height: 26px; border-radius: 8px; background: rgba(255,255,255,.1); border: 1px solid rgba(255,255,255,.16); display: flex; align-items: center; justify-content: center; font-size: 13px; }
.lp-feats b { color: #fff; font-weight: 600; }
.lp-foot {
  margin-top: auto; padding-top: 26px;
  font-size: 11px; color: rgba(255, 255, 255, .5); letter-spacing: .5px;
}

/* —— 右：表单区 —— */
.lp-form-wrap { background: #fff; display: flex; }
.lp-form-in { width: 100%; max-width: 400px; margin: auto; padding: 48px 44px 34px; }
.lp-f-title { font-size: 21px; font-weight: 800; color: #111827; }
.lp-f-sub { font-size: 12.5px; color: #6b7280; margin-top: 5px; }
.lp-form { margin-top: 26px; display: flex; flex-direction: column; gap: 16px; }
.lp-field { display: flex; flex-direction: column; gap: 7px; }
.lp-field label { font-size: 12.5px; font-weight: 600; color: #374151; }
.lp-field input {
  height: 44px; border: 1.5px solid #e5e7eb; border-radius: 10px; padding: 0 14px;
  font-size: 14px; transition: border-color .15s, box-shadow .15s; background: #fafbfc;
}
.lp-field input:focus {
  outline: none; border-color: #e4393c; background: #fff;
  box-shadow: 0 0 0 3px rgba(228, 57, 60, .12);
}
.lp-btn {
  height: 46px; border: none; border-radius: 10px; cursor: pointer;
  background: linear-gradient(135deg, #e4393c, #c02626);
  color: #fff; font-size: 15px; font-weight: 700; letter-spacing: 4px;
  display: flex; align-items: center; justify-content: center; gap: 8px;
  box-shadow: 0 8px 20px rgba(228, 57, 60, .32);
  transition: transform .15s, box-shadow .15s;
}
.lp-btn:hover:not(:disabled) { transform: translateY(-1px); box-shadow: 0 10px 26px rgba(228, 57, 60, .4); }
.lp-btn:disabled { opacity: .7; cursor: default; }
.lp-spin { width: 15px; height: 15px; border: 2px solid rgba(255,255,255,.4); border-top-color: #fff; border-radius: 50%; animation: lp-rot .8s linear infinite; }
@keyframes lp-rot { to { transform: rotate(360deg); } }
.lp-err {
  background: #fef2f2; border: 1px solid #fecaca; color: #b91c1c;
  font-size: 12.5px; border-radius: 8px; padding: 9px 12px;
}
.lp-reg { margin-top: 16px; font-size: 12.5px; color: #6b7280; text-align: center; }
.lp-reg a { color: #e4393c; font-weight: 700; text-decoration: none; }
.lp-reg a:hover { text-decoration: underline; }
.lp-demo { margin-top: 22px; border-top: 1px dashed #e5e7eb; padding-top: 18px; }
.lp-demo-title { font-size: 11px; color: #9ca3af; margin-bottom: 9px; letter-spacing: 1px; }
.lp-demo-row { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.lp-demo-btn {
  border: 1px solid #e5e7eb; background: #fff; border-radius: 9px; padding: 9px 11px;
  font-size: 12.5px; text-align: left; cursor: pointer; transition: all .15s;
  display: flex; align-items: center; gap: 7px; color: #374151;
}
.lp-demo-btn:hover { border-color: #e4393c; background: #fef5f5; transform: translateY(-1px); }
.lp-demo-btn:disabled { opacity: .6; cursor: default; }
.lp-demo-tag { font-size: 10px; padding: 1px 6px; border-radius: 4px; background: #fdeaea; color: #b91c1c; font-weight: 700; }
.lp-demo-tag.t { background: #fef3c7; color: #b45309; }
.lp-demo-sno { font-weight: 600; }
.lp-demo-name { color: #9ca3af; font-size: 11.5px; margin-left: auto; white-space: nowrap; }
.lp-privacy { margin-top: 20px; font-size: 11px; color: #c0c6d0; text-align: center; }

/* —— 移动端 —— */
@media (max-width: 860px) {
  .lp-page { padding: 0; align-items: stretch; }
  .lp-shell { grid-template-columns: 1fr; width: 100%; min-height: 100vh; border-radius: 0; }
  .lp-brand { padding: 0; }
  .lp-brand-in { padding: 26px 22px 22px; }
  .lp-title { font-size: 18px; margin-top: 18px; }
  .lp-slogan { margin-top: 8px; }
  .lp-divider { margin: 16px 0 14px; }
  .lp-foot { display: none; }
  .lp-form-in { padding: 26px 22px 30px; }
  .lp-feats li { font-size: 11.5px; }
}
@media (max-width: 420px) {
  .lp-demo-row { grid-template-columns: 1fr; }
}
</style>
