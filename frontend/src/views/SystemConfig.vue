<template>
  <div class="page">
    <div class="toolbar">
      <span class="page-title">系统配置</span>
      <div class="actions">
        <el-button type="primary" :loading="saving" @click="doSave">
          <el-icon><Check /></el-icon> 保存配置
        </el-button>
      </div>
    </div>

    <div class="config-wrap" v-loading="loading">
      <!-- 认证配置 -->
      <el-card class="cfg-card">
        <template #header><span class="card-title">认证配置</span></template>
        <el-form :model="cfg.auth" label-width="140px" size="small">
          <el-form-item label="用户名">
            <el-input v-model="cfg.auth.username" />
          </el-form-item>
          <el-form-item label="密码">
            <SecretInput v-model="cfg.auth.password" config-path="auth.password" />
          </el-form-item>
          <el-form-item label="JWT 密钥">
            <SecretInput v-model="cfg.auth.jwt_secret" config-path="auth.jwt_secret" />
          </el-form-item>
          <el-form-item label="Token 有效期(小时)">
            <el-input-number v-model="cfg.auth.token_expire_hours" :min="1" :max="720" />
          </el-form-item>
          <el-form-item label="空闲超时(分钟)">
            <el-input-number v-model="cfg.auth.idle_timeout_minutes" :min="1" :max="1440" />
            <span class="field-tip">无操作超过此时间自动退出，0 表示不超时</span>
          </el-form-item>
        </el-form>
      </el-card>

      <!-- MongoDB（只读，从环境变量注入） -->
      <el-card class="cfg-card">
        <template #header>
          <span class="card-title">MongoDB 配置</span>
          <el-tag type="info" size="small" style="margin-left:8px">由环境变量配置，不可在此修改</el-tag>
        </template>
        <el-form :model="cfg.mongodb" label-width="140px" size="small">
          <el-form-item label="主机地址">
            <el-input :value="cfg.mongodb && cfg.mongodb.host" disabled />
          </el-form-item>
          <el-form-item label="端口">
            <el-input :value="cfg.mongodb && cfg.mongodb.port" disabled />
          </el-form-item>
          <el-form-item label="数据库名">
            <el-input :value="cfg.mongodb && cfg.mongodb.database" disabled />
          </el-form-item>
        </el-form>
        <p style="font-size:12px;color:#4a6080;padding:0 0 4px 140px">
          通过 <code>MONGO_HOST</code>、<code>MONGO_PORT</code>、<code>MONGO_DATABASE</code> 环境变量设置，修改需重启服务。
        </p>
      </el-card>

      <!-- 调度配置 -->
      <el-card class="cfg-card">
        <template #header><span class="card-title">采集调度 <el-tag type="warning" size="small" style="margin-left:8px">时间修改需重启</el-tag></span></template>
        <el-form :model="cfg.schedule" label-width="140px" size="small">
          <el-form-item label="定时采集时间">
            <el-input v-model="cfg.schedule.time" placeholder="如 01:30" style="width:120px" />
            <span class="field-tip">格式 HH:MM，修改后需重启服务生效</span>
          </el-form-item>
          <el-form-item label="采集时间窗口(小时)">
            <el-input-number v-model="cfg.schedule.hours" :min="1" :max="720" />
            <span class="field-tip">采集近 N 小时的监控均值</span>
          </el-form-item>
        </el-form>
      </el-card>

      <!-- 服务配置 -->
      <el-card class="cfg-card">
        <template #header><span class="card-title">服务配置 <el-tag type="warning" size="small" style="margin-left:8px">端口修改需重启</el-tag></span></template>
        <el-form :model="cfg.server" label-width="140px" size="small">
          <el-form-item label="监听端口">
            <el-input-number v-model="cfg.server.port" :min="1024" :max="65535" />
          </el-form-item>
          <el-form-item label="Debug 模式">
            <el-switch v-model="cfg.server.debug" />
          </el-form-item>
        </el-form>
        <el-form label-width="140px" size="small" style="margin-top:12px;">
          <el-form-item label="系统访问地址">
            <el-input v-model="cfg.system_url" placeholder="如 http://192.168.1.100:5002"
              style="width:300px" />
            <span class="field-tip" style="margin-left:8px">用于创建用户邮件中的系统链接，可不填</span>
          </el-form-item>
        </el-form>
      </el-card>

      <!-- 邮件服务器配置 -->
      <el-card class="cfg-card">
        <template #header><span class="card-title">邮件服务器配置</span></template>
        <el-form :model="cfg.email" label-width="140px" size="small">
          <el-form-item label="SMTP 服务器">
            <el-input v-model="cfg.email.host" placeholder="如 smtp.exmail.qq.com" />
          </el-form-item>
          <el-form-item label="端口">
            <el-input-number v-model="cfg.email.port" :min="1" :max="65535" />
            <el-switch v-model="cfg.email.ssl" active-text="SSL/TLS" inactive-text="STARTTLS" style="margin-left:16px" />
          </el-form-item>
          <el-form-item label="发件人账号">
            <el-input v-model="cfg.email.username" placeholder="如 monitor@company.com" />
          </el-form-item>
          <el-form-item label="发件人密码">
            <SecretInput v-model="cfg.email.password" config-path="email.password" />
          </el-form-item>
          <el-form-item label="发件人名称">
            <el-input v-model="cfg.email.from_name" placeholder="如 云监控系统" />
          </el-form-item>
        </el-form>
      </el-card>

      <!-- 告警阈值 -->
      <el-card class="cfg-card">
        <template #header>
          <div style="display:flex;align-items:center;justify-content:space-between">
            <span class="card-title">告警阈值配置</span>
            <el-button size="small" type="primary" :loading="savingAlert" @click="doSaveAlert">保存阈值</el-button>
          </div>
        </template>
        <el-form :model="alertCfg" label-width="140px" size="small">
          <el-form-item label="CPU 告警阈值(%)">
            <el-input-number v-model="alertCfg.cpu" :min="1" :max="100" />
            <span class="field-tip">CPU 均值超过此值则触发告警，默认 80%</span>
          </el-form-item>
          <el-form-item label="内存告警阈值(%)">
            <el-input-number v-model="alertCfg.mem" :min="1" :max="100" />
            <span class="field-tip">内存均值超过此值则触发告警，默认 85%</span>
          </el-form-item>
          <el-form-item label="磁盘告警阈值(%)">
            <el-input-number v-model="alertCfg.disk" :min="1" :max="100" />
            <span class="field-tip">磁盘最大使用率超过此值则触发告警，默认 90%</span>
          </el-form-item>
        </el-form>
      </el-card>

      <!-- 云账号配置 -->
      <el-card class="cfg-card">
        <template #header>
          <div style="display:flex;align-items:center;justify-content:space-between">
            <span class="card-title">云账号配置</span>
            <el-button size="small" type="primary" @click="addCloud">+ 添加账号</el-button>
          </div>
        </template>
        <div v-for="(cloud, idx) in cfg.clouds" :key="idx" class="cloud-item">
          <div class="cloud-header">
            <span class="cloud-name">{{ cloud.name || '未命名账号' }}</span>
            <el-button size="small" type="danger" text @click="removeCloud(idx)">删除</el-button>
          </div>
          <el-form :model="cloud" label-width="100px" size="small">
            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item label="账号名称">
                  <el-input v-model="cloud.name" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="云厂商">
                  <el-select v-model="cloud.provider" style="width:100%">
                    <el-option label="阿里云" value="aliyun" />
                    <el-option label="华为云" value="huawei" />
                    <el-option label="腾讯云" value="tencent" />
                    <el-option label="火山云" value="volcengine" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="Access Key">
                  <el-input v-model="cloud.ak" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="Secret Key">
                  <SecretInput v-model="cloud.sk" :config-path="`clouds.${idx}.sk`" />
                </el-form-item>
              </el-col>
              <el-col :span="24">
                <el-form-item label="Region 列表">
                  <el-select v-model="cloud.regions" multiple filterable allow-create
                    style="width:100%" placeholder="输入 region 后回车添加">
                    <el-option v-for="r in cloud.regions" :key="r" :label="r" :value="r" />
                  </el-select>
                </el-form-item>
              </el-col>
            </el-row>
          </el-form>
        </div>
        <el-empty v-if="!cfg.clouds || cfg.clouds.length === 0" description="暂无云账号" :image-size="60" />
      </el-card>

      <!-- 运维平台链接配置 -->
      <el-card class="cfg-card">
        <template #header>
          <div style="display:flex;align-items:center;justify-content:space-between">
            <span class="card-title">运维平台链接配置</span>
            <el-button size="small" type="primary" @click="openAddOpsLink">+ 添加链接</el-button>
          </div>
        </template>
        <el-table :data="opsLinks" size="small"
          :header-cell-style="{ background: 'rgba(21,65,128,0.6)', color: '#90caf9', fontSize: '12px' }"
          :cell-style="{ background: 'transparent', color: '#c8d8f0', fontSize: '12px' }"
          empty-text="暂无链接，请点击「添加链接」配置">
          <el-table-column label="图标" width="60">
            <template #default="{ row }">
              <el-icon><component :is="row.icon" /></el-icon>
            </template>
          </el-table-column>
          <el-table-column prop="name" label="名称" min-width="100" />
          <el-table-column prop="url" label="链接地址" min-width="160" show-overflow-tooltip />
          <el-table-column label="操作" width="120" fixed="right">
            <template #default="{ row }">
              <el-button size="small" type="primary" text @click="openEditOpsLink(row)">编辑</el-button>
              <el-button size="small" type="danger" text @click="doDeleteOpsLink(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <p style="font-size:11px;color:#4a6080;margin-top:8px;padding-left:4px">
          权限控制：在「用户管理 → 权限组」中为各权限组分配可见链接
        </p>
      </el-card>
    </div>
  </div>

  <!-- 运维链接 新增/编辑 弹窗 -->
  <el-dialog v-model="opsLinkDialogVisible" :title="editingOpsLink ? '编辑链接' : '添加链接'"
    width="480px" :close-on-click-modal="false" append-to-body>
    <el-form :model="opsLinkForm" label-width="90px" size="small">
      <el-form-item label="名称" required>
        <el-input v-model="opsLinkForm.name" placeholder="如：Jenkins、Grafana" />
      </el-form-item>
      <el-form-item label="链接地址" required>
        <el-input v-model="opsLinkForm.url" placeholder="http://..." />
      </el-form-item>
      <el-form-item label="图标">
        <div class="icon-grid">
          <div
            v-for="ic in OPS_ICONS"
            :key="ic.name"
            class="icon-item"
            :class="{ selected: opsLinkForm.icon === ic.name }"
            :title="ic.label"
            @click="opsLinkForm.icon = ic.name"
          >
            <el-icon><component :is="ic.name" /></el-icon>
            <span>{{ ic.label }}</span>
          </div>
        </div>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="opsLinkDialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="opsLinkSaving" @click="doSaveOpsLink">保存</el-button>
    </template>
  </el-dialog>

  <!-- 保存前密码验证弹窗 -->
  <el-dialog v-model="verifyVisible" title="操作验证" width="360px" :close-on-click-modal="false" append-to-body>
    <p style="font-size:13px;color:#8ba4d4;margin-bottom:12px">
      保存配置为高危操作，请输入管理员登录密码以确认：
    </p>
    <el-input
      v-model="verifyPwd"
      type="password"
      show-password
      placeholder="登录密码"
      @keyup.enter="confirmVerify"
    />
    <template #footer>
      <el-button @click="verifyVisible = false">取消</el-button>
      <el-button type="primary" :loading="verifying" @click="confirmVerify">确认保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import SecretInput from '../components/SecretInput.vue'
import {
  getConfig, saveConfig, getAlertThresholds, saveAlertThresholds, verifyPassword,
  getOpsLinks, createOpsLink, updateOpsLink, deleteOpsLink
} from '../api/index.js'

const OPS_ICONS = [
  { name: 'Monitor',       label: '监控' },
  { name: 'Platform',      label: '平台' },
  { name: 'Link',          label: '链接' },
  { name: 'Tools',         label: '工具' },
  { name: 'Cpu',           label: '计算' },
  { name: 'DataLine',      label: '数据流' },
  { name: 'Compass',       label: '导航' },
  { name: 'List',          label: '列表' },
  { name: 'Operation',     label: '运维' },
  { name: 'Cloudy',        label: '云服务' },
  { name: 'Key',           label: '密钥' },
  { name: 'BellFilled',    label: '告警' },
  { name: 'Histogram',     label: '统计' },
  { name: 'Trophy',        label: '排行' },
  { name: 'MagicStick',    label: '魔法' },
  { name: 'OfficeBuilding',label: '企业' },
  { name: 'Briefcase',     label: '任务' },
  { name: 'Calendar',      label: '日历' },
  { name: 'Clock',         label: '计时' },
  { name: 'Search',        label: '搜索' },
  { name: 'Star',          label: '收藏' },
  { name: 'House',         label: '首页' },
  { name: 'Wallet',        label: '成本' },
  { name: 'Files',         label: '文件' },
  { name: 'PieChart',      label: '图表' },
  { name: 'Connection',    label: '连接' },
  { name: 'Setting',       label: '设置' },
  { name: 'Folder',        label: '目录' },
  { name: 'DataAnalysis',  label: '分析' },
  { name: 'TrendCharts',   label: '趋势' },
  { name: 'Grid',          label: '网格' },
]

const loading = ref(false)
const saving = ref(false)
const savingAlert = ref(false)
const alertCfg = reactive({ cpu: 80, mem: 85, disk: 90 })
const cfg = ref({
  auth: { username: '', password: '', jwt_secret: '', token_expire_hours: 24 },
  mongodb: { host: '', port: 27017, database: '' },
  schedule: { time: '01:30', hours: 24 },
  server: { port: 5002, debug: false },
  email: { host: '', port: 465, username: '', password: '', from_name: '云监控系统', ssl: true },
  clouds: [],
})

// ── 密码二次验证弹窗 ──────────────────────────────────────────────────────────
const verifyVisible = ref(false)
const verifyPwd = ref('')
const verifying = ref(false)
let pendingAction = null

function requireVerify(action) {
  pendingAction = action
  verifyPwd.value = ''
  verifyVisible.value = true
}

async function confirmVerify() {
  if (!verifyPwd.value) { ElMessage.warning('请输入密码'); return }
  verifying.value = true
  try {
    const res = await verifyPassword(verifyPwd.value)
    if (res.code === 0) {
      verifyVisible.value = false
      verifyPwd.value = ''
      if (pendingAction) await pendingAction()
    } else {
      ElMessage.error(res.msg || '密码错误')
    }
  } catch (e) {
    ElMessage.error(e?.response?.data?.msg || '验证失败')
  } finally {
    verifying.value = false
  }
}

// ── 云账号操作 ─────────────────────────────────────────────────────────────────
function addCloud() {
  cfg.value.clouds.push({ name: '', provider: 'aliyun', ak: '', sk: '', regions: [] })
}

function removeCloud(idx) {
  cfg.value.clouds.splice(idx, 1)
}

// ── 保存系统配置 ───────────────────────────────────────────────────────────────
function doSave() {
  requireVerify(execSave)
}

async function execSave() {
  saving.value = true
  try {
    const res = await saveConfig(cfg.value)
    if (res.code === 0) {
      if (res.restart_needed && res.restart_needed.length > 0) {
        await ElMessageBox.alert(
          `配置已保存。以下变更需重启服务生效：<br><b>${res.restart_needed.join('、')}</b>`,
          '保存成功',
          { dangerouslyUseHTMLString: true, confirmButtonText: '知道了', type: 'warning' }
        )
      } else {
        ElMessage.success('配置已保存，立即生效')
      }
    } else {
      ElMessage.error(res.msg || '保存失败')
    }
  } catch {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

// ── 保存告警阈值 ───────────────────────────────────────────────────────────────
function doSaveAlert() {
  requireVerify(execSaveAlert)
}

async function execSaveAlert() {
  savingAlert.value = true
  try {
    const res = await saveAlertThresholds(alertCfg)
    if (res.code === 0) {
      ElMessage.success('告警阈值已保存')
    } else {
      ElMessage.error(res.msg || '保存失败')
    }
  } catch {
    ElMessage.error('保存失败')
  } finally {
    savingAlert.value = false
  }
}

// ── 运维平台链接管理 ───────────────────────────────────────────────────────────
const opsLinks = ref([])
const opsLinkDialogVisible = ref(false)
const opsLinkSaving = ref(false)
const editingOpsLink = ref(null)
const opsLinkForm = ref({ name: '', url: '', icon: 'Link' })

async function loadOpsLinks() {
  try {
    const res = await getOpsLinks()
    if (res.code === 0) opsLinks.value = res.data
  } catch {}
}

function openAddOpsLink() {
  editingOpsLink.value = null
  opsLinkForm.value = { name: '', url: '', icon: 'Link' }
  opsLinkDialogVisible.value = true
}

function openEditOpsLink(row) {
  editingOpsLink.value = row
  opsLinkForm.value = { name: row.name, url: row.url, icon: row.icon || 'Link' }
  opsLinkDialogVisible.value = true
}

async function doSaveOpsLink() {
  if (!opsLinkForm.value.name || !opsLinkForm.value.url) {
    ElMessage.warning('名称和链接地址不能为空')
    return
  }
  opsLinkSaving.value = true
  try {
    let res
    if (editingOpsLink.value) {
      res = await updateOpsLink(editingOpsLink.value._id, opsLinkForm.value)
    } else {
      res = await createOpsLink(opsLinkForm.value)
    }
    if (res.code === 0) {
      ElMessage.success(editingOpsLink.value ? '更新成功' : '添加成功')
      opsLinkDialogVisible.value = false
      await loadOpsLinks()
    } else {
      ElMessage.error(res.msg || '操作失败')
    }
  } catch {
    ElMessage.error('操作失败')
  } finally {
    opsLinkSaving.value = false
  }
}

async function doDeleteOpsLink(row) {
  await ElMessageBox.confirm(`确定删除链接「${row.name}」？`, '确认删除', {
    type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消'
  })
  try {
    const res = await deleteOpsLink(row._id)
    if (res.code === 0) {
      ElMessage.success('已删除')
      await loadOpsLinks()
    } else {
      ElMessage.error(res.msg || '删除失败')
    }
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

onMounted(async () => {
  loading.value = true
  try {
    const [cfgRes, alertRes] = await Promise.all([getConfig(), getAlertThresholds()])
    if (cfgRes.code === 0) {
      cfg.value = Object.assign(cfg.value, cfgRes.data)
      if (!cfg.value.clouds) cfg.value.clouds = []
    }
    if (alertRes.code === 0) {
      Object.assign(alertCfg, alertRes.data)
    }
  } catch {} finally {
    loading.value = false
  }
  loadOpsLinks()
})
</script>

<style scoped>
.page { min-height: 100vh; background: #060e1f; }
.toolbar {
  display: flex; align-items: center; gap: 12px; padding: 14px 24px;
  background: rgba(10,22,40,0.8); border-bottom: 1px solid rgba(79,195,247,0.1);
}
.page-title { font-size: 16px; font-weight: 600; color: #4fc3f7; }
.actions { margin-left: auto; }
.config-wrap { padding: 20px 24px; display: grid; grid-template-columns: repeat(auto-fit, minmax(480px, 1fr)); gap: 16px; }
.cfg-card { background: rgba(10,22,40,0.7); border: 1px solid rgba(79,195,247,0.15); }
.card-title { font-size: 14px; font-weight: 600; color: #4fc3f7; }
.field-tip { font-size: 11px; color: #5a7aac; margin-left: 8px; }
.cloud-item { border: 1px solid rgba(79,195,247,0.1); border-radius: 6px; padding: 12px 16px; margin-bottom: 12px; background: rgba(21,65,128,0.1); }
.cloud-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.cloud-name { font-size: 13px; color: #4fc3f7; font-weight: 500; }
:deep(.el-card__header) { padding: 10px 16px; border-bottom-color: rgba(79,195,247,0.1); }
:deep(.el-card__body) { padding: 14px 16px; }
:deep(.el-form-item__label) { color: #8ba4d4; }
:deep(.el-input__wrapper) { background: rgba(21,65,128,0.3) !important; box-shadow: 0 0 0 1px rgba(79,195,247,0.2) !important; }
:deep(.el-input__inner) { color: #c8d8f0 !important; }
:deep(.el-input-number .el-input__wrapper) { background: rgba(21,65,128,0.3) !important; }
:deep(.el-select .el-input__wrapper) { background: rgba(21,65,128,0.3) !important; }
.icon-grid {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 6px;
  max-height: 280px;
  overflow-y: auto;
  padding: 4px;
}
.icon-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 6px 4px;
  border-radius: 6px;
  border: 1px solid rgba(79,195,247,0.12);
  cursor: pointer;
  font-size: 10px;
  color: #8ba4d4;
  transition: all 0.15s;
}
.icon-item:hover { border-color: rgba(79,195,247,0.5); color: #c8d8f0; background: rgba(79,195,247,0.06); }
.icon-item.selected { border-color: #4fc3f7; color: #4fc3f7; background: rgba(79,195,247,0.12); }
.icon-item .el-icon { font-size: 18px; }
</style>
