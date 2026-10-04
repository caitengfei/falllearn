<script setup>
import { useRouter } from 'vue-router'
const router = useRouter()
</script>

<template>
  <div class="page" style="max-width: 640px">
    <div class="card center" style="padding: 60px 24px">
      <div style="font-size: 52px">🧭</div>
      <div style="font-size: 20px; font-weight: 700; margin-top: 12px">404 · 页面不存在</div>
      <div style="font-size: 13px; color: var(--text-2); margin-top: 8px">你访问的地址不在康养智行里，回首页看看吧</div>
      <button class="btn mt16" style="margin-top: 20px" @click="router.push('/')">返回首页</button>
    </div>
  </div>
</template>