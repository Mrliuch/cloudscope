<template>
  <div class="page">
    <div class="toolbar">
      <span class="page-title">资源到期</span>
      <div class="filters">
        <el-select v-model="filters.cloud" placeholder="云账号" clearable style="width:160px"
          :filterable="opts.clouds.length > 10" @change="loadData">
          <el-option v-for="o in opts.clouds" :key="o" :label="o" :value="o" />
        </el-select>
        <el-select v-model="filters.provider" placeholder="云厂商" clearable style="width:120px" @change="loadData">
          <el-option v-for="o in opts.providers" :key="o" :label="o" :value="o" />
        </el-select>
        <el-select v-model="filters.resource_type" placeholder="资源类型" clearable style="width:120px" @change="loadData">
          <el-option v-for="o in opts.resource_types" :key="o" :label="o" :value="o" />
        </el-select>
        <el-select v-model="filters.group" placeholder="部门" clearable style="width:130px"
          :filterable="opts.groups.length > 10" @change="loadData">
          <el-option v-for="o in opts.groups" :key="o" :label="o" :value="o" />
        </el-select>
        <el-select v-model="filters.project" placeholder="项目" clearable style="width:160px"
          :filterable="opts.projects.length > 10" @change="loadData">
          <el-option v-for="o in opts.projects" :key="o" :label="o" :value="o" />
        </el-select>
        <el-select v-model="filters.auto_renew" placeholder="自动续费" clearable style="width:110px" @change="loadData">
          <el-option label="是" value="是" />
          <el-option label="否" value="否" />
          <el-option label="未知" value="未知" />
        </el-select>
        <el-select v-model="days" placeholder="到期范围" style="width:120px" @change="loadData">
          <el-option label="7天内" :value="7" />
          <el-option label="15天内" :value="15" />
          <el-option label="30天内" :value="30" />
          <el-option label="60天内" :value="60" />
          <el-option label="90天内" :value="90" />
        </el-select>
        <el-button type="warning" v-if="canRefresh" :loading="refreshing" @click="doRefresh">
          <el-icon><Refresh /></el-icon> 刷新数据
        </el-button>
        <el-button type="primary" @click="doExport">
          <el-icon><Download /></el-icon> 导出 Excel
        </el-button>
        <el-button
          v-if="canSendEmail"
          type="danger"
          :disabled="selectedRows.length === 0"
          :loading="sending"
          @click="doSendEmail">
          <el-icon><Message /></el-icon>
          发送邮件提醒{{ selectedRows.length ? `（${selectedRows.length}条）` : '' }}
        </el-button>
      </div>
    </div>

    <div class="table-wrap">
      <div class="stat-bar" v-if="!loading">
        <span class="stat-item danger">
          <el-icon><Warning /></el-icon>
          7天内到期：{{ urgentCount }} 条
        </span>
        <span class="stat-item warn">15天内到期：{{ soonCount }} 条</span>
        <span class="stat-item normal">共 {{ total }} 条</span>
        <span v-if="selectedRows.length" class="stat-item selected">
          已选 {{ selectedRows.length }} 条
        </span>
      </div>

      <el-table
        ref="tableRef"
        :data="tableData"
        v-loading="loading"
        stripe
        :header-cell-style="headerStyle"
        :cell-style="cellStyle"
        style="width:100%;background:transparent"
        :row-class-name="rowClass"
        height="calc(100vh - 210px)"
        @selection-change="onSelectionChange"
        @sort-change="handleSortChange">
        <el-table-column type="selection" width="46" align="center" fixed />
        <el-table-column type="index" label="序号" width="55" align="center" fixed />
        <el-table-column prop="name" label="资源名称" min-width="160" show-overflow-tooltip fixed sortable="custom" />
        <el-table-column prop="resource_type" label="类型" width="70" align="center" sortable="custom">
          <template #default="{row}">
            <el-tag size="small" :type="typeTagType(row.resource_type)" effect="plain">{{ row.resource_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="cloud" label="云账号" min-width="140" show-overflow-tooltip />
        <el-table-column prop="provider" label="厂商" width="80" />
        <el-table-column prop="region" label="区域" min-width="120" show-overflow-tooltip />
        <el-table-column prop="n_ip" label="内网IP" width="130" show-overflow-tooltip />
        <el-table-column prop="project" label="项目" min-width="120" show-overflow-tooltip />
        <el-table-column prop="group" label="部门" min-width="100" show-overflow-tooltip />
        <el-table-column prop="last_group" label="二级部门" min-width="100" show-overflow-tooltip />
        <el-table-column prop="manager" label="负责人" width="80" />
        <el-table-column prop="charging_mode" label="计费方式" width="90" align="center" />
        <el-table-column prop="status" label="状态" width="80" align="center" />
        <el-table-column prop="auto_renew" label="自动续费" width="90" align="center">
          <template #default="{row}">
            <el-tag
              size="small"
              :type="row.auto_renew === '是' ? 'success' : row.auto_renew === '否' ? 'danger' : 'info'"
              effect="plain">
              {{ row.auto_renew || '未知' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="expire_time" label="到期时间" width="155" align="center" sortable="custom" />
        <el-table-column label="通知邮箱" min-width="200">
          <template #default="{row}">
            <div class="email-cell">
              <template v-if="editingEmailKey === rowKey(row)">
                <el-input
                  v-model="editingEmailVal"
                  size="small"
                  placeholder="输入邮箱后回车确认"
                  style="width:100%"
                  @keyup.enter="confirmEmail(row)"
                  @blur="confirmEmail(row)"
                  @keyup.esc="cancelEmail"
                  autofocus
                />
              </template>
              <template v-else>
                <span class="email-text" :class="{'email-override': !!emailOverrides[rowKey(row)]}">
                  {{ emailOverrides[rowKey(row)] || row.notify_email || '-' }}
                </span>
                <el-icon class="email-edit-icon" @click="startEditEmail(row)"><Edit /></el-icon>
                <el-icon
                  v-if="emailOverrides[rowKey(row)]"
                  class="email-reset-icon"
                  title="恢复项目默认邮箱"
                  @click="resetEmail(row)">
                  <RefreshLeft />
                </el-icon>
              </template>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="days_left" label="剩余天数" width="90" align="center" fixed="right" sortable="custom">
          <template #default="{row}">
            <span :class="daysClass(row.days_left)" class="days-badge">
              {{ row.days_left }} 天
            </span>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination">
        <span class="total-tip">共 {{ total }} 条</span>
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[50, 100, 200]"
          layout="sizes, prev, pager, next"
          background
          @change="loadData"
        />
      </div>
    </div>
  </div>

  <!-- 发送邮件确认对话框 -->
  <el-dialog
    v-model="sendDialog.visible"
    title="发送邮件确认"
    width="480px"
    :close-on-click-modal="false"
    class="send-email-dialog"
    :style="{
      '--el-dialog-bg-color': '#0d1f3a',
      '--el-dialog-border-radius': '8px',
      '--el-text-color-primary': '#c8d8f0',
      '--el-text-color-regular': '#8ba4d4',
      '--el-border-color-light': 'rgba(79,195,247,0.15)',
      '--el-color-primary': '#4fc3f7',
    }">
    <div class="send-confirm-body">
      <p class="send-confirm-count">
        确认向所选 <strong>{{ sendDialog.toSend.length }}</strong> 条资源发送到期提醒？
      </p>
      <div class="send-recipient-block" v-if="sendDialog.emailList.length">
        <span class="sr-label">收件人：</span>
        <span class="sr-emails">
          {{ sendDialog.emailList.slice(0, 3).join('、') }}{{ sendDialog.emailList.length > 3 ? ` 等 ${sendDialog.emailList.length} 个` : '' }}
        </span>
      </div>
      <div class="send-noemail-block" v-if="sendDialog.noEmailCount > 0">
        <el-icon style="color:#ffa726"><Warning /></el-icon>
        <span class="ne-text">{{ sendDialog.noEmailCount }} 条资源未配置邮箱，</span>
        <template v-if="!sendDialog.showFallback">
          <span class="ne-link" @click="sendDialog.showFallback = true">在此配置邮箱发送</span>
        </template>
        <template v-else>
          <span class="ne-hint">将统一发送至：</span>
        </template>
      </div>
      <div class="send-fallback-input" v-if="sendDialog.showFallback">
        <el-input
          v-model="sendDialog.fallbackEmail"
          placeholder="输入兜底收件邮箱"
          size="small"
          clearable
          autofocus
          :style="{
            '--el-input-bg-color': 'rgba(21,65,128,0.5)',
            '--el-input-text-color': '#c8d8f0',
            '--el-input-placeholder-color': '#5a7aac',
            '--el-input-border-color': 'rgba(79,195,247,0.3)',
            '--el-input-hover-border-color': 'rgba(79,195,247,0.6)',
            '--el-input-focus-border-color': '#4fc3f7',
            '--el-fill-color-blank': 'rgba(21,65,128,0.5)',
          }"
        />
        <span class="ne-skip-tip" v-if="!sendDialog.fallbackEmail">不填则跳过</span>
      </div>
    </div>
    <template #footer>
      <el-button @click="sendDialog.visible = false">取消</el-button>
      <el-button type="primary" :loading="sending" @click="confirmSendEmail">发送</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Message, Edit, RefreshLeft } from '@element-plus/icons-vue'
import { getExpiryList, getExpiryFilterOptions, refreshExpiry, exportExpiryExcel, sendExpiryEmail, saveExpiryEmailOverride } from '../api/index.js'

const loading = ref(false)
const refreshing = ref(false)
const sending = ref(false)
const tableRef = ref(null)

const isAdmin = localStorage.getItem('role') === 'admin'

function hasAction(key) {
  if (isAdmin) return true
  const actions = JSON.parse(localStorage.getItem('actions') || '[]')
  return actions.includes('*') || actions.includes(key)
}

const canRefresh = hasAction('refresh_expiry')
const canSendEmail = hasAction('send_email')
const tableData = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(50)
const days = ref(30)
const sortField = ref('expire_time')
const sortOrder = ref('asc')
const opts = reactive({ clouds: [], providers: [], resource_types: [], groups: [], projects: [], auto_renews: [] })
const filters = reactive({ cloud: '', provider: '', resource_type: '', group: '', project: '', auto_renew: '' })
const selectedRows = ref([])

// 行内邮箱编辑状态（不持久化到项目表）
const emailOverrides = reactive({})       // { rowKey: email }
const editingEmailKey = ref(null)         // 当前正在编辑的行 key
const editingEmailVal = ref('')

const rowKey = (row) => `${row.resource_id || row.name}_${row.cloud}`

function startEditEmail(row) {
  editingEmailKey.value = rowKey(row)
  editingEmailVal.value = emailOverrides[rowKey(row)] ?? row.notify_email ?? ''
}

async function confirmEmail(row) {
  const key = rowKey(row)
  const val = editingEmailVal.value.trim()
  editingEmailKey.value = null
  editingEmailVal.value = ''
  // 若与原始项目邮箱相同则视为"清除覆盖"
  if (val === (row.notify_email || '')) {
    delete emailOverrides[key]
  } else {
    emailOverrides[key] = val
  }
  // 持久化到数据库（resource_id 优先，name 作为降级 key）
  try {
    await saveExpiryEmailOverride(row.cloud, row.resource_id || row.name, val)
  } catch (e) {
    ElMessage.warning('邮箱已在本页更新，但写入数据库失败：' + (e?.response?.data?.msg || e.message || ''))
  }
}

function cancelEmail() {
  editingEmailKey.value = null
  editingEmailVal.value = ''
}

function resetEmail(row) {
  delete emailOverrides[rowKey(row)]
}

const urgentCount = computed(() => tableData.value.filter(r => r.days_left <= 7).length)
const soonCount = computed(() => tableData.value.filter(r => r.days_left <= 15).length)

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

const rowClass = ({ row }) => {
  if (row.days_left <= 7) return 'row-danger'
  if (row.days_left <= 15) return 'row-warn'
  return ''
}

const daysClass = (d) => {
  if (d <= 7) return 'days-danger'
  if (d <= 15) return 'days-warn'
  if (d <= 30) return 'days-notice'
  return 'days-ok'
}

const typeTagType = (t) => {
  const map = { ECS: 'primary', CVM: 'primary', RDS: 'success', CBS: 'warning', SLB: 'info' }
  return map[t] || ''
}

function onSelectionChange(rows) {
  selectedRows.value = rows
}

function handleSortChange({ prop, order }) {
  if (!prop || !order) return
  sortField.value = prop
  sortOrder.value = order === 'ascending' ? 'asc' : 'desc'
  page.value = 1
  loadData()
}

async function loadData() {
  loading.value = true
  try {
    const res = await getExpiryList({
      ...filters, days: days.value, page: page.value, page_size: pageSize.value,
      sort_field: sortField.value, sort_order: sortOrder.value,
    })
    if (res.code === 0) {
      tableData.value = res.data
      total.value = res.total
      // 从后端 notify_email_is_override 标记还原已保存的覆盖邮箱
      res.data.forEach(row => {
        const k = rowKey(row)
        if (row.notify_email_is_override && row.notify_email) {
          emailOverrides[k] = row.notify_email
        } else {
          delete emailOverrides[k]
        }
      })
    }
  } catch {} finally {
    loading.value = false
  }
}

async function loadOpts() {
  try {
    const res = await getExpiryFilterOptions()
    if (res.code === 0) Object.assign(opts, res.data)
  } catch {}
}

async function doRefresh() {
  refreshing.value = true
  try {
    const res = await refreshExpiry()
    if (res.code === 0) {
      ElMessage.success('到期资源采集已启动，请稍后刷新页面')
    } else {
      ElMessage.error(res.msg || '启动失败')
    }
  } catch {
    ElMessage.error('启动失败')
  } finally {
    refreshing.value = false
  }
}

function doExport() {
  exportExpiryExcel({ ...filters, days: days.value })
}

const sendDialog = reactive({
  visible: false,
  toSend: [],
  emailList: [],
  noEmailCount: 0,
  fallbackEmail: '',
  showFallback: false,
})

function doSendEmail() {
  if (!selectedRows.value.length) return
  const toSend = selectedRows.value.map(row => ({
    ...row,
    notify_email: emailOverrides[rowKey(row)] ?? row.notify_email ?? '',
  }))
  const emailList = [...new Set(toSend.map(r => r.notify_email).filter(Boolean))]
  const noEmailCount = toSend.filter(r => !r.notify_email).length
  sendDialog.toSend = toSend
  sendDialog.emailList = emailList
  sendDialog.noEmailCount = noEmailCount
  sendDialog.fallbackEmail = ''
  // 全部无邮箱时直接展开输入框；部分无邮箱时先显示提示链接
  sendDialog.showFallback = emailList.length === 0 && noEmailCount > 0
  sendDialog.visible = true
}

async function confirmSendEmail() {
  const fallback = sendDialog.fallbackEmail.trim()
  const toSend = sendDialog.toSend.map(r => ({
    ...r,
    notify_email: r.notify_email || fallback,
  }))
  sendDialog.visible = false
  sending.value = true
  try {
    const res = await sendExpiryEmail(toSend)
    if (res.code === 0) {
      ElMessage.success(res.msg)
    } else {
      ElMessage.error(res.msg || '发送失败')
    }
  } catch (e) {
    ElMessage.error('发送失败：' + (e?.response?.data?.msg || e.message || '网络错误'))
  } finally {
    sending.value = false
  }
}

onMounted(() => {
  loadOpts()
  loadData()
})
</script>

<style scoped>
.page { min-height: 100vh; background: #060e1f; }
.toolbar {
  display: flex; align-items: center; flex-wrap: wrap; gap: 12px;
  padding: 14px 24px;
  background: rgba(10,22,40,0.8);
  border-bottom: 1px solid rgba(79,195,247,0.1);
}
.page-title { font-size: 16px; font-weight: 600; color: #ff7043; min-width: 80px; }
.filters { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; margin-left: auto; }
.stat-bar {
  display: flex; gap: 20px; align-items: center;
  padding: 10px 0 8px;
  font-size: 13px;
}
.stat-item { display: flex; align-items: center; gap: 4px; }
.stat-item.danger { color: #ef5350; font-weight: 600; }
.stat-item.warn { color: #ffa726; }
.stat-item.normal { color: #5a7aac; }
.stat-item.selected { color: #4fc3f7; font-weight: 600; }
.table-wrap { padding: 8px 24px 16px; }
.pagination { display: flex; justify-content: flex-end; align-items: center; gap: 16px; margin-top: 12px; }
.total-tip { font-size: 13px; color: #5a7aac; }

.email-cell { display: flex; align-items: center; gap: 6px; }
.email-text { font-size: 12px; color: #8ba4d4; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.email-text.email-override { color: #4fc3f7; font-weight: 600; }
.email-edit-icon { color: #5a7aac; cursor: pointer; font-size: 13px; flex-shrink: 0; }
.email-edit-icon:hover { color: #4fc3f7; }
.email-reset-icon { color: #ff9800; cursor: pointer; font-size: 13px; flex-shrink: 0; }
.email-reset-icon:hover { color: #ffb74d; }

.days-badge { padding: 2px 8px; border-radius: 10px; font-size: 12px; font-weight: 600; }
.days-danger { color: #fff; background: rgba(239,83,80,0.85); }
.days-warn { color: #fff; background: rgba(255,167,38,0.85); }
.days-notice { color: #333; background: rgba(253,216,53,0.85); }
.days-ok { color: #81c784; background: rgba(129,199,132,0.15); }

:deep(.el-table) { --el-table-bg-color: transparent; --el-table-tr-bg-color: transparent; }
:deep(.el-table__row.row-danger td) { background: rgba(239,83,80,0.08) !important; }
:deep(.el-table__row.row-warn td) { background: rgba(255,167,38,0.08) !important; }
:deep(.el-table__row:hover td) { background: rgba(79,195,247,0.08) !important; }
:deep(.el-select .el-input__wrapper) { background: rgba(21,65,128,0.3); box-shadow: 0 0 0 1px rgba(79,195,247,0.2) !important; }
:deep(.el-select .el-input__inner) { color: #c8d8f0; }
:deep(.el-pagination) { --el-pagination-bg-color: rgba(21,65,128,0.3); --el-pagination-text-color: #8ba4d4; }
:deep(.el-loading-mask) { background: rgba(6,14,31,0.7); }
:deep(.el-table__header .el-checkbox) { --el-checkbox-border-color: rgba(79,195,247,0.4); }
:deep(.el-scrollbar__bar.is-horizontal) { height: 8px; opacity: 1 !important; }
:deep(.el-scrollbar__bar.is-horizontal .el-scrollbar__thumb) { background: rgba(79,195,247,0.45); border-radius: 4px; }
:deep(.el-scrollbar__bar.is-horizontal:hover .el-scrollbar__thumb) { background: rgba(79,195,247,0.75); }

.send-confirm-body { display: flex; flex-direction: column; gap: 12px; }
.send-confirm-count { font-size: 14px; color: #c8d8f0; margin: 0; }
.send-confirm-count strong { color: #4fc3f7; font-size: 16px; }
.send-recipient-block { display: flex; align-items: flex-start; gap: 6px; font-size: 13px; }
.sr-label { color: #5a7aac; white-space: nowrap; }
.sr-emails { color: #90caf9; line-height: 1.6; }
.send-noemail-block { display: flex; align-items: center; gap: 5px; font-size: 13px; flex-wrap: wrap; }
.ne-text { color: #ffa726; }
.ne-hint { color: #8ba4d4; }
.ne-link {
  color: #4fc3f7; cursor: pointer; text-decoration: underline; text-underline-offset: 2px;
}
.ne-link:hover { color: #81d4fa; }
.send-fallback-input { display: flex; align-items: center; gap: 8px; }
.ne-skip-tip { font-size: 12px; color: #5a7aac; white-space: nowrap; }
</style>
