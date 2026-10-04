<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, auth } from '../api'

const route = useRoute()
const router = useRouter()
const code = ref('')
const name = ref('')
const pwd = ref('')
const pwd2 = ref('')
const busy = ref(false)
const err = ref('')

onMounted(() => {
  code.value = String(route.query.code || '').toUpperCase()
  // 邀请码链接进入时，焦点直接落在昵称（减少一步点击）
  if (code.value) setTimeout(() => document.getElementById('name')?.focus(), 120)
})

async function submit() {
  err.value = ''
  if (!code.value.trim()) { err.value = '请填写老师发给你的邀请码'; return }
  if (!name.value.trim()) { err.value = '请填写昵称（可用姓名或昵称）'; return }
  if (pwd.value.length < 6) { err.value = '密码至少 6 位'; return }
  if (pwd.value !== pwd2.value) { err.value = '两次输入的密码不一致'; return }
  busy.value = true
  try {
    const r = await api.register(code.value.trim(), name.value.trim(), pwd.value)
    auth.save(r.token, r.user)
    router.push('/')
  } catch (e) {
    err.value = e.message
  }
  busy.value = false
}
</script>

<template>
  <div class="reg-wrap">
    <div class="reg-card">
      <div class="reg-head">
        <span class="logo-mark">康</span>
        <div>
          <div class="t1">加入康养智行</div>
          <div class="t2">用老师发的邀请码注册 · 30 秒完成</div>
        </div>
      </div>

      <form class="reg-body" @submit.prevent="submit">
        <div class="field">
          <label for="code">邀请码</label>
          <input id="code" v-model="code" placeholder="如 FD-7K2M9Q" autocomplete="off" />
        </div>
        <div class="field">
          <label for="name">昵称</label>
          <input id="name" v-model="name" placeholder="可用姓名或昵称（不必填真名）" autocomplete="nickname" />
        </div>
        <div class="field">
          <label for="pwd">设置密码</label>
          <input id="pwd" v-model="pwd" type="password" placeholder="至少 6 位" autocomplete="new-password" />
        </div>
        <div class="field">
          <label for="pwd2">确认密码</label>
          <input id="pwd2" v-model="pwd2" type="password" placeholder="再输一次" autocomplete="new-password" />
        </div>
        <div v-if="err" class="err">{{ err }}</div>
        <button type="submit" class="btn" style="width: 100%; padding: 11px" :disabled="busy">
          <span v-if="busy" class="spinner"></span>
          {{ busy ? '注册中…' : '注册并进入' }}
        </button>
      </form>

      <div class="privacy">
        <b>隐私说明</b>：注册只需昵称与自设密码——不采集手机号、邮箱、身份证或学籍号；
        学号由平台自动分配（如 S2026004）；答题与成绩数据仅保存在本平台服务器，用于个人学习分析。
      </div>

      <div class="reg-foot">已有账号？<router-link to="/login">返回登录</router-link></div>
    </div>
  </div>
</template>

<style scoped>
.reg-wrap {
  min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 24px;
  background: linear-gradient(120deg, #7f1d1d, #b91c1c 55%, #e4393c);
}
.reg-card {
  width: 100%; max-width: 430px; background: #fff; border-radius: 16px; padding: 26px 26px 20px;
  box-shadow: 0 18px 50px rgba(0, 0, 0, .25);
}
.reg-head { display: flex; gap: 10px; align-items: center; margin-bottom: 18px; }
.reg-head .logo-mark {
  width: 42px; height: 42px; border-radius: 12px; background: #e4393c; color: #fff;
  display: flex; align-items: center; justify-content: center; font-size: 22px; font-weight: 800;
}
.t1 { font-size: 18px; font-weight: 800; }
.t2 { font-size: 12px; color: var(--text-3); margin-top: 2px; }
.reg-body .field { margin-bottom: 12px; }
.reg-body .field label { display: block; font-size: 12.5px; color: var(--text-2); margin-bottom: 5px; }
.reg-body .field input {
  width: 100%; padding: 10px 12px; border: 1px solid var(--line); border-radius: 8px; font-size: 14px;
}
.reg-body .field input:focus { outline: none; border-color: var(--primary); }
.err { color: var(--primary-text); font-size: 12.5px; margin: 6px 0 10px; }
.privacy {
  margin-top: 14px; font-size: 11.5px; color: var(--text-3); line-height: 1.7;
  background: var(--bg); border-radius: 8px; padding: 10px 12px;
}
.privacy b { color: var(--text-2); }
.reg-foot { margin-top: 14px; font-size: 12.5px; color: var(--text-2); text-align: center; }
.reg-foot a { color: var(--primary-text); font-weight: 600; }
</style>
