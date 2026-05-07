<template>
  <div class="app-layout" :class="{ 'sidebar-collapsed': collapsed }">
    <SideBar v-model:collapsed="collapsed" />
    <main class="main-content">
      <router-view />
    </main>
  </div>

  <!-- 空闲超时警告 -->
  <el-dialog v-model="idleWarning" title="即将退出登录" width="360px"
    :close-on-click-modal="false" :close-on-press-escape="false" :show-close="false">
    <div style="text-align:center;padding:8px 0">
      <div style="font-size:15px;color:#c8d8f0;margin-bottom:12px">
        检测到长时间未操作，将在
        <span style="color:#ef5350;font-weight:700;font-size:18px">{{ countdown }}</span>
        秒后自动退出
      </div>
    </div>
    <template #footer>
      <el-button type="primary" @click="resetIdle">继续使用</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import SideBar from '../components/SideBar.vue'
import { getConfig } from '../api/index.js'

const collapsed = ref(false)
const router = useRouter()

// ── 空闲超时 ─────────────────────────────────────────────────────────────────
const idleWarning = ref(false)
const countdown = ref(60)

let timeoutMinutes = 30
let lastActivity = Date.now()
let checkTimer = null
let countdownTimer = null

const ACTIVITY_EVENTS = ['mousemove', 'keypress', 'click', 'scroll', 'touchstart']

function onActivity() {
  lastActivity = Date.now()
  if (idleWarning.value) {
    resetIdle()
  }
}

function resetIdle() {
  idleWarning.value = false
  lastActivity = Date.now()
  clearInterval(countdownTimer)
  countdownTimer = null
}

function startCountdown(secs) {
  countdown.value = secs
  idleWarning.value = true
  clearInterval(countdownTimer)
  countdownTimer = setInterval(() => {
    countdown.value -= 1
    if (countdown.value <= 0) {
      clearInterval(countdownTimer)
      countdownTimer = null
      localStorage.removeItem('token')
      localStorage.removeItem('username')
      router.push('/login')
    }
  }, 1000)
}

function startIdleCheck() {
  clearInterval(checkTimer)
  if (!timeoutMinutes || timeoutMinutes <= 0) return

  const timeoutMs = timeoutMinutes * 60 * 1000
  const warnMs = Math.min(60 * 1000, timeoutMs * 0.1)

  checkTimer = setInterval(() => {
    if (idleWarning.value) return
    const idleMs = Date.now() - lastActivity
    if (idleMs >= timeoutMs - warnMs) {
      const secsLeft = Math.max(1, Math.round((timeoutMs - idleMs) / 1000))
      startCountdown(secsLeft)
    }
  }, 5000)
}

async function loadIdleTimeout() {
  try {
    const res = await getConfig()
    if (res.code === 0) {
      timeoutMinutes = res.data?.auth?.idle_timeout_minutes ?? 30
    }
  } catch {}
  startIdleCheck()
}

onMounted(() => {
  ACTIVITY_EVENTS.forEach(e => window.addEventListener(e, onActivity, { passive: true }))
  loadIdleTimeout()
})

onUnmounted(() => {
  ACTIVITY_EVENTS.forEach(e => window.removeEventListener(e, onActivity))
  clearInterval(checkTimer)
  clearInterval(countdownTimer)
})
</script>

<style scoped>
.app-layout {
  display: flex;
  min-height: 100vh;
  background: #060e1f;
}

.main-content {
  flex: 1;
  margin-left: 220px;
  min-width: 0;
  transition: margin-left 0.25s ease;
  overflow: hidden;
}

.app-layout.sidebar-collapsed .main-content {
  margin-left: 64px;
}
</style>
