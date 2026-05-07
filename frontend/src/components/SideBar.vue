<template>
  <aside class="sidebar" :class="{ collapsed }">
    <!-- Logo 区域 -->
    <div class="sidebar-logo">
      <el-icon class="logo-icon"><Monitor /></el-icon>
      <transition name="fade">
        <span v-if="!collapsed" class="logo-text">云监控平台</span>
      </transition>
    </div>

    <!-- 导航菜单 -->
    <nav class="sidebar-nav">
      <!-- 普通导航项 -->
      <el-tooltip
        v-for="item in navItems"
        :key="item.path"
        :content="item.label"
        placement="right"
        :disabled="!collapsed"
      >
        <router-link
          :to="item.path"
          class="nav-item"
          :class="{ active: route.path === item.path }"
        >
          <el-icon class="nav-icon"><component :is="item.icon" /></el-icon>
          <transition name="fade">
            <span v-if="!collapsed" class="nav-label">{{ item.label }}</span>
          </transition>
        </router-link>
      </el-tooltip>

      <!-- 费用统计分组（需要 cost 权限） -->
      <el-tooltip v-if="hasMenu('cost')" content="费用统计" placement="right" :disabled="!collapsed">
        <div class="nav-item nav-group-header"
             :class="{ active: isCostActive }"
             @click="costOpen = !costOpen">
          <el-icon class="nav-icon"><TrendCharts /></el-icon>
          <transition name="fade">
            <span v-if="!collapsed" class="nav-label">费用统计</span>
          </transition>
          <transition name="fade">
            <el-icon v-if="!collapsed" class="group-arrow" :class="{ open: costOpen }">
              <ArrowDown />
            </el-icon>
          </transition>
        </div>
      </el-tooltip>

      <!-- 费用子菜单 -->
      <transition v-if="hasMenu('cost')" name="slide">
        <div v-if="costOpen && !collapsed" class="nav-sub">
          <template v-for="p in costProviders" :key="p.provider">
            <router-link
              v-if="p.implemented"
              :to="`/cost/${p.provider}`"
              class="nav-sub-item"
              :class="{ active: route.path === `/cost/${p.provider}` }"
            >
              <span class="sub-dot"></span>
              {{ p.display_name }}
            </router-link>
            <div v-else class="nav-sub-item disabled">
              <span class="sub-dot"></span>
              {{ p.display_name }}
              <span class="sub-tag">待接入</span>
            </div>
          </template>
        </div>
      </transition>

      <!-- 折叠态：费用子菜单（仅有数据的项） -->
      <template v-if="hasMenu('cost') && costOpen && collapsed">
        <el-tooltip
          v-for="p in costProviders.filter(x => x.implemented)"
          :key="p.provider"
          :content="p.display_name"
          placement="right"
        >
          <router-link
            :to="`/cost/${p.provider}`"
            class="nav-item nav-sub-collapsed"
            :class="{ active: route.path === `/cost/${p.provider}` }"
          >
            <el-icon class="nav-icon" style="font-size:13px"><Money /></el-icon>
          </router-link>
        </el-tooltip>
      </template>

      <!-- 运维平台（所有用户可见，子菜单按权限过滤） -->
      <el-tooltip content="运维平台" placement="right" :disabled="!collapsed">
        <div class="nav-item nav-group-header"
             :class="{ active: opsOpen }"
             @click="opsOpen = !opsOpen">
          <el-icon class="nav-icon"><Platform /></el-icon>
          <transition name="fade">
            <span v-if="!collapsed" class="nav-label">运维平台</span>
          </transition>
          <transition name="fade">
            <el-icon v-if="!collapsed" class="group-arrow" :class="{ open: opsOpen }">
              <ArrowDown />
            </el-icon>
          </transition>
        </div>
      </el-tooltip>

      <!-- 运维平台子菜单（展开态） -->
      <transition name="slide">
        <div v-if="opsOpen && !collapsed" class="nav-sub">
          <template v-if="opsLinks.length === 0">
            <div class="nav-sub-item disabled">
              <span class="sub-dot"></span>
              暂无链接
            </div>
          </template>
          <a
            v-for="lk in opsLinks"
            :key="lk._id"
            :href="lk.url"
            target="_blank"
            rel="noopener noreferrer"
            class="nav-sub-item"
          >
            <el-icon style="font-size:13px;flex-shrink:0"><component :is="resolveOpsIcon(lk.icon)" /></el-icon>
            <span style="margin-left:4px">{{ lk.name }}</span>
          </a>
        </div>
      </transition>

      <!-- 运维平台子菜单（折叠态） -->
      <template v-if="opsOpen && collapsed">
        <el-tooltip
          v-for="lk in opsLinks"
          :key="lk._id"
          :content="lk.name"
          placement="right"
        >
          <a
            :href="lk.url"
            target="_blank"
            rel="noopener noreferrer"
            class="nav-item nav-sub-collapsed"
          >
            <el-icon class="nav-icon" style="font-size:13px"><component :is="resolveOpsIcon(lk.icon)" /></el-icon>
          </a>
        </el-tooltip>
      </template>

      <!-- 系统配置（仅 admin） -->
      <el-tooltip v-if="isAdmin" content="系统配置" placement="right" :disabled="!collapsed">
        <router-link to="/config" class="nav-item" :class="{ active: route.path === '/config' }">
          <el-icon class="nav-icon"><Setting /></el-icon>
          <transition name="fade">
            <span v-if="!collapsed" class="nav-label">系统配置</span>
          </transition>
        </router-link>
      </el-tooltip>

      <!-- 系统审计（仅 admin） -->
      <el-tooltip v-if="isAdmin" content="系统审计" placement="right" :disabled="!collapsed">
        <router-link to="/audit" class="nav-item" :class="{ active: route.path === '/audit' }">
          <el-icon class="nav-icon"><DocumentChecked /></el-icon>
          <transition name="fade">
            <span v-if="!collapsed" class="nav-label">系统审计</span>
          </transition>
        </router-link>
      </el-tooltip>

      <!-- 用户管理（仅 admin） -->
      <el-tooltip v-if="isAdmin" content="用户管理" placement="right" :disabled="!collapsed">
        <router-link to="/users" class="nav-item" :class="{ active: route.path === '/users' }">
          <el-icon class="nav-icon"><UserFilled /></el-icon>
          <transition name="fade">
            <span v-if="!collapsed" class="nav-label">用户管理</span>
          </transition>
        </router-link>
      </el-tooltip>
    </nav>

    <!-- 底部区域 -->
    <div class="sidebar-bottom">
      <!-- 采集状态 & 用户 -->
      <div v-if="!collapsed" class="bottom-info">
        <span class="username clickable" @click="openUserDialog">{{ username }}</span>
        <span v-if="collectStatus.last_collect_time" class="last-time">
          上次: {{ collectStatus.last_collect_time }}
        </span>
        <span v-if="appVersion && appVersion !== 'dev'" class="version-tag">v{{ appVersion }}</span>
      </div>
      <div v-if="collapsed" class="version-collapsed" :title="`版本 v${appVersion}`">
        <span v-if="appVersion && appVersion !== 'dev'">{{ appVersion.slice(0, 6) }}</span>
      </div>

      <!-- 修改密码 -->
      <el-tooltip content="修改密码" placement="right" :disabled="!collapsed">
        <div class="action-btn" @click="changePwdVisible = true">
          <el-icon><Lock /></el-icon>
          <transition name="fade">
            <span v-if="!collapsed">修改密码</span>
          </transition>
        </div>
      </el-tooltip>

      <!-- 手动采集（有 collect 权限才显示） -->
      <el-tooltip v-if="canCollect" :content="'手动采集'" placement="right" :disabled="!collapsed">
        <div class="action-btn" @click="openDialog">
          <el-icon :class="{ 'is-loading': collectStatus.status === 'running' }">
            <Loading v-if="collectStatus.status === 'running'" />
            <VideoPlay v-else />
          </el-icon>
          <transition name="fade">
            <span v-if="!collapsed">手动采集</span>
          </transition>
        </div>
      </el-tooltip>

      <!-- 退出 -->
      <el-tooltip content="退出登录" placement="right" :disabled="!collapsed">
        <div class="action-btn logout" @click="logout">
          <el-icon><SwitchButton /></el-icon>
          <transition name="fade">
            <span v-if="!collapsed">退出登录</span>
          </transition>
        </div>
      </el-tooltip>

      <!-- 折叠 / 展开 按钮 -->
      <div class="toggle-btn" @click="$emit('update:collapsed', !collapsed)">
        <el-icon>
          <Expand v-if="collapsed" />
          <Fold v-else />
        </el-icon>
      </div>
    </div>
  </aside>

  <!-- 用户信息弹窗 -->
  <el-dialog v-model="userDialogVisible" title="登录信息" width="560px" class="user-dialog">
    <div class="user-info-header">
      <el-icon style="font-size:32px;color:#4fc3f7"><User /></el-icon>
      <div>
        <div class="user-name-big">{{ username }}</div>
        <div class="user-version" v-if="appVersion">当前版本：v{{ appVersion }}</div>
      </div>
    </div>
    <div class="login-history-title">最近登录记录</div>
    <el-table :data="loginHistory" size="small" stripe style="width:100%"
      :header-cell-style="{ background: 'rgba(21,65,128,0.7)', color: '#90caf9', fontSize: '12px' }"
      :cell-style="{ background: 'transparent', color: '#c8d8f0', fontSize: '12px' }"
      v-loading="historyLoading">
      <el-table-column prop="login_time" label="登录时间" width="160" />
      <el-table-column prop="ip" label="IP地址" width="140" />
      <el-table-column prop="user_agent" label="客户端" show-overflow-tooltip />
    </el-table>
    <template #footer>
      <el-button @click="userDialogVisible = false">关闭</el-button>
    </template>
  </el-dialog>

  <!-- 修改密码弹窗 -->
  <el-dialog v-model="changePwdVisible" title="修改密码" width="400px">
    <el-form :model="changePwdForm" label-width="100px">
      <el-form-item label="当前密码">
        <el-input v-model="changePwdForm.old_password" type="password" show-password
                  placeholder="请输入当前密码" />
      </el-form-item>
      <el-form-item label="新密码">
        <el-input v-model="changePwdForm.new_password" type="password" show-password
                  placeholder="不少于6位" />
      </el-form-item>
      <el-form-item label="确认新密码">
        <el-input v-model="changePwdForm.confirm_password" type="password" show-password
                  placeholder="再次输入新密码" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="changePwdVisible = false">取消</el-button>
      <el-button type="primary" :loading="changePwdLoading" @click="submitChangePwd">确认修改</el-button>
    </template>
  </el-dialog>

  <!-- 采集进度弹窗 -->
  <el-dialog v-model="dialogVisible" title="手动采集" width="640px"
    :close-on-click-modal="false" class="collect-dialog">
    <div class="dialog-body">
      <div class="status-row">
        <el-tag :type="statusTagType" effect="plain">
          <el-icon v-if="collectStatus.status === 'running'" class="is-loading"><Loading /></el-icon>
          {{ statusLabel }}
        </el-tag>
        <span v-if="collectStatus.status === 'running'" class="cloud-hint">
          {{ collectStatus.progress.current_cloud }}
        </span>
        <span v-if="collectStatus.error" class="err-hint">{{ collectStatus.error }}</span>
      </div>

      <el-progress
        v-if="collectStatus.progress.total > 0"
        :percentage="progressPct"
        :status="collectStatus.status === 'running' ? '' : (collectStatus.error ? 'exception' : 'success')"
        :striped="collectStatus.status === 'running'"
        :striped-flow="collectStatus.status === 'running'"
        :duration="5"
        style="margin:12px 0"
      />

      <div class="log-box" ref="logBoxRef">
        <div v-for="(line, i) in collectStatus.logs" :key="i" class="log-line">{{ line }}</div>
        <div v-if="!collectStatus.logs || collectStatus.logs.length === 0" class="log-empty">
          暂无日志，点击"开始采集"后将实时显示进度
        </div>
      </div>
    </div>

    <template #footer>
      <el-button @click="dialogVisible = false">关闭</el-button>
      <el-button type="primary" :loading="starting" :disabled="collectStatus.status === 'running'"
        @click="doCollect">
        {{ collectStatus.status === 'running' ? '采集中...' : '开始采集' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  Monitor, DataAnalysis, Grid, Warning, Bell,
  Folder, Coin, Setting, VideoPlay, Loading,
  SwitchButton, Expand, Fold, TrendCharts, ArrowDown, Money, User, DocumentChecked,
  UserFilled, Lock, Platform, Link, Tools, Cpu, DataLine, Compass, List, Operation,
  Cloudy, Key, BellFilled, Histogram, Trophy, MagicStick, OfficeBuilding,
  Briefcase, Calendar, Clock, Search, Star, House, Wallet, Files, PieChart, Connection
} from '@element-plus/icons-vue'
import {
  triggerCollect, getCollectStatus, getCostProviders, getLoginHistory, getVersion,
  changeOwnPassword, getOpsLinks
} from '../api/index.js'

const OPS_ICON_MAP = {
  Monitor, Platform, Link, Tools, Cpu, DataLine, Compass, List, Operation,
  Cloudy, Key, BellFilled, Histogram, Trophy, MagicStick, OfficeBuilding,
  Briefcase, Calendar, Clock, Search, Star, House, Wallet, Files, PieChart,
  Connection, Setting, Folder, DataAnalysis, TrendCharts, Grid
}

function resolveOpsIcon(name) {
  return OPS_ICON_MAP[name] || Link
}

defineProps({ collapsed: { type: Boolean, default: false } })
defineEmits(['update:collapsed'])

const route = useRoute()
const router = useRouter()
const username = localStorage.getItem('username') || ''
const role = localStorage.getItem('role') || 'user'
const isAdmin = role === 'admin'

function hasMenu(key) {
  if (isAdmin) return true
  const menus = JSON.parse(localStorage.getItem('menus') || '[]')
  return menus.includes('*') || menus.includes(key)
}

function hasAction(key) {
  if (isAdmin) return true
  const actions = JSON.parse(localStorage.getItem('actions') || '[]')
  return actions.includes('*') || actions.includes(key)
}

const canCollect = hasAction('collect')

// 运维平台分组状态
const opsOpen = ref(false)
const opsLinks = ref([])

async function loadOpsLinks() {
  try {
    const res = await getOpsLinks()
    if (res.code === 0) opsLinks.value = res.data
  } catch {}
}

// 费用统计分组状态
const costOpen = ref(false)
const costProviders = ref([])
const isCostActive = computed(() => route.path.startsWith('/cost'))

// 路由在费用页时自动展开
watch(isCostActive, (v) => { if (v) costOpen.value = true }, { immediate: true })

async function loadCostProviders() {
  try {
    const res = await getCostProviders()
    if (res.code === 0) costProviders.value = res.data
  } catch {}
}

const navItems = [
  { path: '/dashboard', label: '数据大屏', icon: DataAnalysis, menu: 'dashboard' },
  { path: '/table',     label: '明细列表', icon: Grid,         menu: 'table' },
  { path: '/expiry',    label: '资源到期', icon: Warning,      menu: 'expiry' },
  { path: '/alerts',    label: '告警中心', icon: Bell,         menu: 'alert' },
  { path: '/projects',  label: '项目维护', icon: Folder,       menu: 'project_mgmt' },
  { path: '/balance',   label: '账户余额', icon: Coin,         menu: 'balance' },
].filter(item => hasMenu(item.menu))

// 用户信息弹窗
const userDialogVisible = ref(false)
const loginHistory = ref([])
const historyLoading = ref(false)
const appVersion = ref('')

async function openUserDialog() {
  userDialogVisible.value = true
  historyLoading.value = true
  try {
    const res = await getLoginHistory()
    if (res.code === 0) loginHistory.value = res.data
  } catch {} finally {
    historyLoading.value = false
  }
}

async function loadVersion() {
  try {
    const res = await getVersion()
    if (res.code === 0) appVersion.value = res.version
  } catch {}
}

const dialogVisible = ref(false)
const starting = ref(false)
const collectStatus = ref({ status: 'idle', progress: {}, last_collect_time: null, error: null, logs: [] })
const logBoxRef = ref(null)

let bgTimer = null
let dlgTimer = null

const statusLabel = computed(() => {
  if (collectStatus.value.status === 'running') return '采集中'
  if (collectStatus.value.error) return '上次采集有错误'
  return '空闲'
})

const statusTagType = computed(() => {
  if (collectStatus.value.status === 'running') return 'warning'
  if (collectStatus.value.error) return 'danger'
  return 'success'
})

const progressPct = computed(() => {
  const p = collectStatus.value.progress || {}
  if (!p.total) return 0
  return Math.round((p.current / p.total) * 100)
})

async function pollStatus() {
  try {
    const res = await getCollectStatus()
    if (res.code === 0) collectStatus.value = res.data
  } catch {}
}

function scrollLogToBottom() {
  nextTick(() => {
    if (logBoxRef.value) logBoxRef.value.scrollTop = logBoxRef.value.scrollHeight
  })
}

watch(() => collectStatus.value.logs, scrollLogToBottom, { deep: true })

function openDialog() {
  dialogVisible.value = true
  pollStatus()
  startDialogPoll()
}

watch(dialogVisible, (v) => { if (!v) stopDialogPoll() })

function startDialogPoll() {
  stopDialogPoll()
  dlgTimer = setInterval(pollStatus, 2000)
}

function stopDialogPoll() {
  if (dlgTimer) { clearInterval(dlgTimer); dlgTimer = null }
}

async function doCollect() {
  starting.value = true
  try {
    await triggerCollect()
    await pollStatus()
    ElMessage.success('采集任务已启动')
  } catch {
    ElMessage.error('启动失败')
  } finally {
    starting.value = false
  }
}

function logout() {
  ['token', 'username', 'role', 'menus', 'actions'].forEach(k => localStorage.removeItem(k))
  router.push('/login')
}

// 修改密码
const changePwdVisible = ref(false)
const changePwdForm = ref({ old_password: '', new_password: '', confirm_password: '' })
const changePwdLoading = ref(false)

async function submitChangePwd() {
  if (!changePwdForm.value.old_password || !changePwdForm.value.new_password) {
    ElMessage.warning('请填写完整密码信息')
    return
  }
  if (changePwdForm.value.new_password !== changePwdForm.value.confirm_password) {
    ElMessage.error('两次输入的新密码不一致')
    return
  }
  if (changePwdForm.value.new_password.length < 6) {
    ElMessage.warning('新密码不能少于6位')
    return
  }
  changePwdLoading.value = true
  try {
    const res = await changeOwnPassword(changePwdForm.value.old_password, changePwdForm.value.new_password)
    if (res.code === 0) {
      ElMessage.success('密码修改成功，请重新登录')
      changePwdVisible.value = false
      changePwdForm.value = { old_password: '', new_password: '', confirm_password: '' }
      setTimeout(() => logout(), 1500)
    } else {
      ElMessage.error(res.msg || '修改失败')
    }
  } catch {
    ElMessage.error('修改失败')
  } finally {
    changePwdLoading.value = false
  }
}

onMounted(() => {
  pollStatus()
  bgTimer = setInterval(pollStatus, 5000)
  loadCostProviders()
  loadVersion()
  loadOpsLinks()
})

onUnmounted(() => {
  if (bgTimer) clearInterval(bgTimer)
  stopDialogPoll()
})
</script>

<style scoped>
.sidebar {
  position: fixed;
  left: 0;
  top: 0;
  bottom: 0;
  width: 220px;
  background: rgba(6, 14, 31, 0.97);
  border-right: 1px solid rgba(79, 195, 247, 0.15);
  display: flex;
  flex-direction: column;
  transition: width 0.25s ease;
  z-index: 100;
  overflow: hidden;
}

.sidebar.collapsed {
  width: 64px;
}

/* Logo */
.sidebar-logo {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 20px;
  height: 64px;
  border-bottom: 1px solid rgba(79, 195, 247, 0.1);
  flex-shrink: 0;
  overflow: hidden;
  white-space: nowrap;
}

.logo-icon {
  font-size: 22px;
  color: #4fc3f7;
  flex-shrink: 0;
}

.logo-text {
  font-size: 16px;
  font-weight: 700;
  color: #4fc3f7;
  text-shadow: 0 0 10px rgba(79, 195, 247, 0.5);
  white-space: nowrap;
}

/* Nav */
.sidebar-nav {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 12px 0;
}

.sidebar-nav::-webkit-scrollbar { width: 3px; }
.sidebar-nav::-webkit-scrollbar-thumb { background: rgba(79, 195, 247, 0.2); border-radius: 3px; }

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 20px;
  height: 48px;
  color: #8ba4d4;
  text-decoration: none;
  transition: color 0.2s, background 0.2s;
  white-space: nowrap;
  overflow: hidden;
  position: relative;
  cursor: pointer;
}

.nav-item:hover {
  color: #c8d8f0;
  background: rgba(79, 195, 247, 0.06);
}

.nav-item.active {
  color: #4fc3f7;
  background: rgba(79, 195, 247, 0.12);
}

.nav-item.active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 24px;
  background: #4fc3f7;
  border-radius: 0 2px 2px 0;
}

.nav-icon {
  font-size: 18px;
  flex-shrink: 0;
}

.nav-label {
  font-size: 14px;
  white-space: nowrap;
}

/* 分组箭头 */
.nav-group-header { cursor: pointer; }
.group-arrow {
  margin-left: auto;
  font-size: 12px;
  transition: transform 0.25s ease;
  color: #4a6080;
}
.group-arrow.open { transform: rotate(180deg); }

/* 子菜单 */
.nav-sub { background: rgba(0,0,0,0.15); overflow: hidden; }
.nav-sub-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 20px 0 44px;
  height: 38px;
  color: #8ba4d4;
  text-decoration: none;
  font-size: 13px;
  transition: color 0.2s, background 0.2s;
  cursor: pointer;
}
.nav-sub-item:hover { color: #c8d8f0; background: rgba(79,195,247,0.05); }
.nav-sub-item.active { color: #4fc3f7; }
.nav-sub-item.disabled { color: #3d5070; cursor: default; }
.sub-dot {
  width: 4px; height: 4px; border-radius: 50%;
  background: currentColor; flex-shrink: 0;
}
.sub-tag {
  font-size: 10px; color: #3d5070;
  margin-left: auto;
}

/* 折叠态子菜单项 */
.nav-sub-collapsed { padding: 0 20px; }

/* 子菜单滑动动画 */
.slide-enter-active, .slide-leave-active { transition: max-height 0.25s ease, opacity 0.2s; overflow: hidden; }
.slide-enter-from, .slide-leave-to { max-height: 0; opacity: 0; }
.slide-enter-to, .slide-leave-from { max-height: 300px; opacity: 1; }

/* Bottom */
.sidebar-bottom {
  flex-shrink: 0;
  border-top: 1px solid rgba(79, 195, 247, 0.1);
  padding: 12px 0 8px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  overflow: hidden;
}

.bottom-info {
  padding: 0 20px 8px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  overflow: hidden;
}

.username {
  font-size: 13px;
  color: #8ba4d4;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.username.clickable {
  cursor: pointer;
}
.username.clickable:hover {
  color: #4fc3f7;
  text-decoration: underline dotted;
}
.version-tag {
  font-size: 10px;
  color: #2d4a70;
  font-family: monospace;
}
.version-collapsed {
  padding: 4px 0 0;
  text-align: center;
  font-size: 9px;
  color: #2d4a70;
  font-family: monospace;
  white-space: nowrap;
  overflow: hidden;
}

.last-time {
  font-size: 11px;
  color: #4a6080;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.action-btn {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 20px;
  height: 40px;
  color: #8ba4d4;
  cursor: pointer;
  transition: color 0.2s, background 0.2s;
  white-space: nowrap;
  overflow: hidden;
  font-size: 13px;
}

.action-btn:hover {
  color: #4fc3f7;
  background: rgba(79, 195, 247, 0.06);
}

.action-btn .el-icon {
  font-size: 16px;
  flex-shrink: 0;
}

.action-btn.logout:hover {
  color: #ef5350;
  background: rgba(239, 83, 80, 0.06);
}

.toggle-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 40px;
  color: #4a6080;
  cursor: pointer;
  transition: color 0.2s;
  margin-top: 4px;
}

.toggle-btn:hover { color: #4fc3f7; }
.toggle-btn .el-icon { font-size: 18px; }

/* Fade transition */
.fade-enter-active, .fade-leave-active {
  transition: opacity 0.15s ease;
}
.fade-enter-from, .fade-leave-to {
  opacity: 0;
}

/* User dialog */
.user-info-header { display: flex; align-items: center; gap: 16px; margin-bottom: 20px; }
.user-name-big { font-size: 18px; font-weight: 600; color: #4fc3f7; }
.user-version { font-size: 12px; color: #5a7aac; margin-top: 4px; font-family: monospace; }
.login-history-title { font-size: 13px; color: #8ba4d4; margin-bottom: 8px; }

/* Dialog styles */
.dialog-body { display: flex; flex-direction: column; gap: 8px; }
.status-row { display: flex; align-items: center; gap: 12px; }
.cloud-hint { font-size: 13px; color: #8ba4d4; }
.err-hint { font-size: 12px; color: #ef5350; }

.log-box {
  background: #0a0f1e;
  border: 1px solid rgba(79, 195, 247, 0.15);
  border-radius: 4px;
  padding: 10px 12px;
  height: 260px;
  overflow-y: auto;
  font-family: 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.6;
}
.log-line { color: #b0c4de; white-space: pre-wrap; word-break: break-all; }
.log-empty { color: #4a6080; font-style: italic; }
</style>
