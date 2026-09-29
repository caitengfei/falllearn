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
  <div class="login-page">
    <div class="login-card">
      <div class="login-head">
        <div class="lh-logo">跌</div>
        <h1>防跌学堂</h1>
        <p>老年人跌倒预防与应急处置 · 岗课赛证融通</p>
        <div class="lh-tags">
          <span>世赛对标</span><span>省赛 GZ063</span><span>三证贯通</span>
        </div>
      </div>
      <form class="login-body" @submit.prevent="doLogin">
        <div class="field">
          <label for="sno">学号 / 工号</label>
          <input id="sno" v-model="sno" name="username" autocomplete="username" placeholder="如 S2026001" />
        </div>
        <div class="field">
          <label for="pwd">密码</label>
          <input id="pwd" v-model="pwd" type="password" name="password" autocomplete="current-password" placeholder="密码" />
        </div>
        <button type="submit" class="btn" style="width: 100%; padding: 11px" :disabled="busy">
          <span v-if="busy" class="spinner"></span>
          {{ busy ? '登录中…' : '登 录' }}
        </button>
        <div v-if="err" class="err">{{ err }}</div>

        <div class="demo-hint">
          <div class="dh-title">一键体验（密码 123456）</div>
          <div class="dh-row">
            <button v-for="d in demos" :key="d.sno" type="button" class="dh-btn" :disabled="busy" @click="fill(d); doLogin()">
              <span class="dh-tag" :class="{ t: d.tag === '教师' }">{{ d.tag }}</span>
              {{ d.sno }}<span class="dh-name">{{ d.name }}</span>
            </button>
          </div>
        </div>
      </form>
    </div>
  </div>
</template>

<style scoped>
.lh-logo {
  width: 46px; height: 46px; border-radius: 12px; background: rgba(255,255,255,.2);
  display: flex; align-items: center; justify-content: center; font-size: 24px; font-weight: 800; margin-bottom: 10px;
}
.lh-tags { display: flex; gap: 6px; margin-top: 10px; }
.lh-tags span {
  font-size: 10.5px; background: rgba(255,255,255,.16); padding: 2px 9px; border-radius: 9px;
}
.dh-title { font-size: 11px; color: var(--text-3); margin-bottom: 8px; letter-spacing: 1px; }
.dh-row { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.dh-btn {
  border: 1px solid var(--line); background: #fff; border-radius: 8px; padding: 8px 10px;
  font-size: 12.5px; text-align: left; transition: all .15s; display: flex; align-items: center; gap: 7px;
}
.dh-btn:hover { border-color: var(--primary); background: var(--primary-light); }
.dh-tag {
  font-size: 10px; padding: 1px 6px; border-radius: 4px; background: var(--primary-light); color: var(--primary-text);
}
.dh-tag.t { background: var(--gold-light); color: #b45309; }
.dh-name { color: var(--text-3); font-size: 11.5px; margin-left: auto; white-space: nowrap; }
</style>