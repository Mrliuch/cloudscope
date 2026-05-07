<template>
  <div class="page">
    <div class="toolbar">
      <span class="page-title">告警中心</span>
      <div class="toolbar-right">
        <span class="collect-time" v-if="collectTime">数据时间：{{ collectTime }}</span>
        <el-button size="small" :loading="loading" @click="loadAlerts">
          <el-icon><Refresh /></el-icon> 刷新
        </el-button>
        <el-button
          v-if="canSendEmail"
          type="danger"
          size="small"
          :disabled="totalAlerts === 0"
          @click="openSendDialog">
          <el-icon><Message /></el-icon>
          发送告警邮件{{ totalAlerts ? `（${totalAlerts}条）` : '' }}
        </el-button>
      </div>
    </div>

    <!-- 发送告警邮件确认框 -->
    <el-dialog v-model="sendDialogVisible" title="发送告警邮件" width="460px" :close-on-click-modal="false">
      <div style="margin-bottom:16px;font-size:13px;color:#8ba4d4;">
        将向各项目配置的通知邮箱发送当前 <strong style="color:#ef5350">{{ totalAlerts }}</strong> 条告警提醒。
      </div>
      <el-form label-width="110px" size="small">
        <el-form-item label="统一收件邮箱">
          <el-input
            v-model="extraEmail"
            placeholder="可选，多个邮箱用逗号分隔，留空则按项目邮箱发送"
            clearable
            style="width:100%"
          />
        </el-form-item>
        <el-form-item label="发送模式" v-if="extraEmail">
          <el-radio-group v-model="extraEmailMode">
            <el-radio value="append" style="display:block;margin-bottom:6px;color:#c8d8f0">
              追加：同时发送给项目邮箱 + 此邮箱
            </el-radio>
            <el-radio value="replace" style="display:block;color:#c8d8f0">
              替换：仅发送给此邮箱（忽略项目邮箱）
            </el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="sendDialogVisible = false">取消</el-button>
        <el-button type="danger" :loading="sending" @click="doSendEmail">确认发送</el-button>
      </template>
    </el-dialog>

    <div class="content" v-loading="loading">
      <!-- 统计卡片 -->
      <div class="stat-cards">
        <div class="stat-card" :class="alerts.cpu.length ? 'card-danger' : 'card-ok'">
          <div class="card-icon"><el-icon><Cpu /></el-icon></div>
          <div class="card-info">
            <div class="card-count">{{ alerts.cpu.length }}</div>
            <div class="card-label">CPU 告警（≥ {{ thresholds.cpu }}%）</div>
          </div>
        </div>
        <div class="stat-card" :class="alerts.mem.length ? 'card-warn' : 'card-ok'">
          <div class="card-icon"><el-icon><DataLine /></el-icon></div>
          <div class="card-info">
            <div class="card-count">{{ alerts.mem.length }}</div>
            <div class="card-label">内存告警（≥ {{ thresholds.mem }}%）</div>
          </div>
        </div>
        <div class="stat-card" :class="alerts.disk.length ? 'card-warn' : 'card-ok'">
          <div class="card-icon"><el-icon><Files /></el-icon></div>
          <div class="card-info">
            <div class="card-count">{{ alerts.disk.length }}</div>
            <div class="card-label">磁盘告警（≥ {{ thresholds.disk }}%）</div>
          </div>
        </div>
        <div class="stat-card" :class="alerts.down.length ? 'card-danger' : 'card-ok'">
          <div class="card-icon"><el-icon><Warning /></el-icon></div>
          <div class="card-info">
            <div class="card-count">{{ alerts.down.length }}</div>
            <div class="card-label">实例离线</div>
          </div>
        </div>
      </div>

      <!-- CPU 告警 -->
      <div class="alert-section" v-if="alerts.cpu.length">
        <div class="section-header danger">
          <el-icon><Cpu /></el-icon>
          <span>CPU 使用率过高（≥ {{ thresholds.cpu }}%）</span>
          <el-tag type="danger" size="small" style="margin-left:8px">{{ alerts.cpu.length }} 台</el-tag>
        </div>
        <el-table :data="alerts.cpu" :header-cell-style="headerStyle" :cell-style="cellStyle"
          size="small" style="width:100%" :max-height="300">
          <el-table-column prop="name" label="实例名称" min-width="140" show-overflow-tooltip />
          <el-table-column prop="n_ip" label="内网IP" width="130" />
          <el-table-column prop="cloud" label="云账号" min-width="120" show-overflow-tooltip />
          <el-table-column prop="region" label="区域" min-width="110" show-overflow-tooltip />
          <el-table-column prop="project" label="项目" min-width="110" show-overflow-tooltip />
          <el-table-column prop="group" label="部门" min-width="100" show-overflow-tooltip />
          <el-table-column prop="manager" label="负责人" width="80" />
          <el-table-column prop="cpu_avg" label="CPU均值%" width="100" align="center">
            <template #default="{row}">
              <span class="val-danger">{{ row.cpu_avg?.toFixed(2) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="cpu_max" label="CPU峰值%" width="100" align="center">
            <template #default="{row}">
              <span class="val-danger">{{ row.cpu_max?.toFixed(2) }}</span>
            </template>
          </el-table-column>
        </el-table>
      </div>
      <div class="alert-empty" v-else>
        <el-icon style="color:#4fc3f7"><CircleCheck /></el-icon>
        <span>CPU 使用率正常（阈值 {{ thresholds.cpu }}%）</span>
      </div>

      <!-- 内存告警 -->
      <div class="alert-section" v-if="alerts.mem.length">
        <div class="section-header warn">
          <el-icon><DataLine /></el-icon>
          <span>内存使用率过高（≥ {{ thresholds.mem }}%）</span>
          <el-tag type="warning" size="small" style="margin-left:8px">{{ alerts.mem.length }} 台</el-tag>
        </div>
        <el-table :data="alerts.mem" :header-cell-style="headerStyle" :cell-style="cellStyle"
          size="small" style="width:100%" :max-height="300">
          <el-table-column prop="name" label="实例名称" min-width="140" show-overflow-tooltip />
          <el-table-column prop="n_ip" label="内网IP" width="130" />
          <el-table-column prop="cloud" label="云账号" min-width="120" show-overflow-tooltip />
          <el-table-column prop="region" label="区域" min-width="110" show-overflow-tooltip />
          <el-table-column prop="project" label="项目" min-width="110" show-overflow-tooltip />
          <el-table-column prop="group" label="部门" min-width="100" show-overflow-tooltip />
          <el-table-column prop="manager" label="负责人" width="80" />
          <el-table-column prop="mem_avg" label="内存均值%" width="105" align="center">
            <template #default="{row}">
              <span class="val-warn">{{ row.mem_avg?.toFixed(2) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="mem_max" label="内存峰值%" width="105" align="center">
            <template #default="{row}">
              <span class="val-warn">{{ row.mem_max?.toFixed(2) }}</span>
            </template>
          </el-table-column>
        </el-table>
      </div>
      <div class="alert-empty" v-else>
        <el-icon style="color:#4fc3f7"><CircleCheck /></el-icon>
        <span>内存使用率正常（阈值 {{ thresholds.mem }}%）</span>
      </div>

      <!-- 磁盘告警 -->
      <div class="alert-section" v-if="alerts.disk.length">
        <div class="section-header warn">
          <el-icon><Files /></el-icon>
          <span>磁盘使用率过高（≥ {{ thresholds.disk }}%）</span>
          <el-tag type="warning" size="small" style="margin-left:8px">{{ alerts.disk.length }} 台</el-tag>
        </div>
        <el-table :data="alerts.disk" :header-cell-style="headerStyle" :cell-style="cellStyle"
          size="small" style="width:100%" :max-height="300">
          <el-table-column prop="name" label="实例名称" min-width="140" show-overflow-tooltip />
          <el-table-column prop="n_ip" label="内网IP" width="130" />
          <el-table-column prop="cloud" label="云账号" min-width="120" show-overflow-tooltip />
          <el-table-column prop="region" label="区域" min-width="110" show-overflow-tooltip />
          <el-table-column prop="project" label="项目" min-width="110" show-overflow-tooltip />
          <el-table-column prop="group" label="部门" min-width="100" show-overflow-tooltip />
          <el-table-column prop="manager" label="负责人" width="80" />
          <el-table-column prop="disk_avg" label="磁盘最大%" width="105" align="center">
            <template #default="{row}">
              <el-popover v-if="row.disk_details && row.disk_details.length"
                placement="left" width="220" trigger="hover">
                <template #reference>
                  <span class="val-warn" style="cursor:pointer;text-decoration:underline dotted">
                    {{ row.disk_avg?.toFixed(2) }}
                  </span>
                </template>
                <div style="font-size:12px">
                  <div v-for="d in row.disk_details" :key="d.device"
                    style="display:flex;justify-content:space-between;padding:3px 0;border-bottom:1px solid #eee">
                    <span style="color:#555">{{ d.device }}</span>
                    <span :style="{color: d.usage>=90?'#ef5350':d.usage>=80?'#ffa726':'#555', fontWeight:600}">
                      {{ d.usage }}%
                    </span>
                  </div>
                </div>
              </el-popover>
              <span v-else class="val-warn">{{ row.disk_avg?.toFixed(2) }}</span>
            </template>
          </el-table-column>
        </el-table>
      </div>
      <div class="alert-empty" v-else>
        <el-icon style="color:#4fc3f7"><CircleCheck /></el-icon>
        <span>磁盘使用率正常（阈值 {{ thresholds.disk }}%）</span>
      </div>

      <!-- 离线告警 -->
      <div class="alert-section" v-if="alerts.down.length">
        <div class="section-header danger">
          <el-icon><Warning /></el-icon>
          <span>实例离线</span>
          <el-tag type="danger" size="small" style="margin-left:8px">{{ alerts.down.length }} 台</el-tag>
        </div>
        <el-table :data="alerts.down" :header-cell-style="headerStyle" :cell-style="cellStyle"
          size="small" style="width:100%" :max-height="300">
          <el-table-column prop="name" label="实例名称" min-width="140" show-overflow-tooltip />
          <el-table-column prop="n_ip" label="内网IP" width="130" />
          <el-table-column prop="cloud" label="云账号" min-width="120" show-overflow-tooltip />
          <el-table-column prop="region" label="区域" min-width="110" show-overflow-tooltip />
          <el-table-column prop="project" label="项目" min-width="110" show-overflow-tooltip />
          <el-table-column prop="group" label="部门" min-width="100" show-overflow-tooltip />
          <el-table-column prop="manager" label="负责人" width="80" />
          <el-table-column prop="status" label="状态" width="80" align="center">
            <template #default="{row}">
              <el-tag type="danger" size="small" effect="plain">{{ row.status || 'DOWN' }}</el-tag>
            </template>
          </el-table-column>
        </el-table>
      </div>
      <div class="alert-empty" v-else>
        <el-icon style="color:#4fc3f7"><CircleCheck /></el-icon>
        <span>所有实例运行正常</span>
      </div>

      <div class="no-data" v-if="!loading && !collectTime">
        <el-empty description="暂无采集数据，请先执行手动采集" :image-size="80" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getAlerts, sendAlertEmail } from '../api/index.js'
import { Cpu, DataLine, Files, Warning, CircleCheck, Refresh, Message } from '@element-plus/icons-vue'

const loading = ref(false)
const sending = ref(false)
const collectTime = ref('')
const thresholds = reactive({ cpu: 80, mem: 85, disk: 90 })
const alerts = reactive({ cpu: [], mem: [], disk: [], down: [] })
const sendDialogVisible = ref(false)
const extraEmail = ref('')
const extraEmailMode = ref('append')

function hasAction(key) {
  const actions = JSON.parse(localStorage.getItem('actions') || '[]')
  return actions.includes('*') || actions.includes(key)
}
const canSendEmail = hasAction('send_email')
const totalAlerts = computed(() =>
  alerts.cpu.length + alerts.mem.length + alerts.disk.length + alerts.down.length
)

const headerStyle = () => ({
  background: 'rgba(21,65,128,0.8)',
  color: '#90caf9',
  fontSize: '12px',
  borderBottom: '1px solid rgba(79,195,247,0.15)',
})

const cellStyle = () => ({
  background: 'transparent',
  color: '#c8d8f0',
  borderBottom: '1px solid rgba(79,195,247,0.06)',
  fontSize: '12px',
})

async function loadAlerts() {
  loading.value = true
  try {
    const res = await getAlerts()
    if (res.code === 0) {
      const d = res.data
      alerts.cpu = d.cpu || []
      alerts.mem = d.mem || []
      alerts.disk = d.disk || []
      alerts.down = d.down || []
      collectTime.value = d.collect_time || ''
      if (d.thresholds) {
        thresholds.cpu = d.thresholds.cpu
        thresholds.mem = d.thresholds.mem
        thresholds.disk = d.thresholds.disk
      }
    }
  } catch {} finally {
    loading.value = false
  }
}

function openSendDialog() {
  extraEmail.value = ''
  extraEmailMode.value = 'append'
  sendDialogVisible.value = true
}

async function doSendEmail() {
  if (totalAlerts.value === 0) return
  sending.value = true
  try {
    const res = await sendAlertEmail(
      { cpu: alerts.cpu, mem: alerts.mem, disk: alerts.disk, down: alerts.down },
      extraEmail.value,
      extraEmailMode.value,
    )
    if (res.code === 0) {
      ElMessage.success(res.msg)
      sendDialogVisible.value = false
    } else {
      ElMessage.error(res.msg || '发送失败')
    }
  } catch (e) {
    ElMessage.error('发送失败：' + (e?.response?.data?.msg || e.message || '网络错误'))
  } finally {
    sending.value = false
  }
}

onMounted(loadAlerts)
</script>

<style scoped>
.page { min-height: 100vh; background: #060e1f; }
.toolbar {
  display: flex; align-items: center; padding: 14px 24px;
  background: rgba(10,22,40,0.8); border-bottom: 1px solid rgba(79,195,247,0.1);
}
.page-title { font-size: 16px; font-weight: 600; color: #4fc3f7; }
.toolbar-right { margin-left: auto; display: flex; align-items: center; gap: 12px; }
.collect-time { font-size: 12px; color: #5a7aac; }

.content { padding: 20px 24px; }

.stat-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}
.stat-card {
  display: flex; align-items: center; gap: 16px;
  padding: 16px 20px;
  border-radius: 8px;
  border: 1px solid rgba(79,195,247,0.15);
  background: rgba(10,22,40,0.7);
}
.card-danger { border-color: rgba(239,83,80,0.4); background: rgba(239,83,80,0.06); }
.card-warn { border-color: rgba(255,167,38,0.4); background: rgba(255,167,38,0.06); }
.card-ok { border-color: rgba(79,195,247,0.15); }
.card-icon { font-size: 28px; color: #4fc3f7; }
.card-danger .card-icon { color: #ef5350; }
.card-warn .card-icon { color: #ffa726; }
.card-count { font-size: 28px; font-weight: 700; color: #c8d8f0; line-height: 1; }
.card-danger .card-count { color: #ef5350; }
.card-warn .card-count { color: #ffa726; }
.card-label { font-size: 12px; color: #5a7aac; margin-top: 4px; }

.alert-section {
  margin-bottom: 16px;
  border: 1px solid rgba(79,195,247,0.15);
  border-radius: 8px;
  overflow: hidden;
  background: rgba(10,22,40,0.5);
}
.section-header {
  display: flex; align-items: center; gap: 8px;
  padding: 10px 16px;
  font-size: 14px; font-weight: 600; color: #c8d8f0;
  background: rgba(21,65,128,0.4);
}
.section-header.danger { background: rgba(239,83,80,0.12); color: #ef9a9a; }
.section-header.warn { background: rgba(255,167,38,0.1); color: #ffcc80; }

.alert-empty {
  display: flex; align-items: center; gap: 8px;
  padding: 12px 16px; margin-bottom: 16px;
  background: rgba(10,22,40,0.4);
  border: 1px solid rgba(79,195,247,0.1);
  border-radius: 8px;
  font-size: 13px; color: #5a7aac;
}

.no-data { padding: 60px 0; }

.val-danger { color: #ef5350; font-weight: 600; }
.val-warn { color: #ffa726; font-weight: 600; }

:deep(.el-table) { --el-table-bg-color: transparent; --el-table-tr-bg-color: transparent; }
:deep(.el-table__row:hover td) { background: rgba(79,195,247,0.06) !important; }
:deep(.el-empty__description p) { color: #5a7aac; }
:deep(.el-dialog) { background: #0d1b33; border: 1px solid rgba(79,195,247,0.2); }
:deep(.el-dialog__title) { color: #4fc3f7; }
:deep(.el-form-item__label) { color: #8ba4d4; }
:deep(.el-radio__label) { color: #c8d8f0; }
:deep(.el-radio__input.is-checked .el-radio__inner) { background: #ef5350; border-color: #ef5350; }
</style>
