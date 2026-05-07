<template>
  <div class="page">
    <div class="toolbar">
      <span class="page-title">主机明细列表</span>
      <div class="filters">
        <el-input v-model="filters.name" placeholder="名称搜索" clearable style="width:150px"
          @input="debouncedLoad" @clear="loadData">
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-input v-model="filters.ip" placeholder="IP搜索" clearable style="width:140px"
          @input="debouncedLoad" @clear="loadData">
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-select v-model="filters.cloud" placeholder="云账号" clearable style="width:160px"
          :filterable="opts.clouds.length > 10" @change="loadData">
          <el-option v-for="o in opts.clouds" :key="o" :label="o" :value="o" />
        </el-select>
        <el-select v-model="filters.provider" placeholder="云厂商" clearable style="width:120px" @change="loadData">
          <el-option v-for="o in opts.providers" :key="o" :label="o" :value="o" />
        </el-select>
        <el-select v-model="filters.region" placeholder="区域" clearable style="width:160px"
          :filterable="opts.regions.length > 10" @change="loadData">
          <el-option v-for="o in opts.regions" :key="o" :label="o" :value="o" />
        </el-select>
        <el-select v-model="filters.project" placeholder="项目" clearable style="width:160px"
          :filterable="opts.projects.length > 10" @change="loadData">
          <el-option v-for="o in opts.projects" :key="o" :label="o" :value="o" />
        </el-select>
        <el-select v-model="filters.group" placeholder="部门" clearable style="width:130px"
          :filterable="opts.groups.length > 10" @change="loadData">
          <el-option v-for="o in opts.groups" :key="o" :label="o" :value="o" />
        </el-select>
        <el-select v-model="days" placeholder="时间范围" style="width:120px" @change="loadData">
          <el-option label="今日" :value="1" />
          <el-option label="近3天" :value="3" />
          <el-option label="近7天" :value="7" />
          <el-option label="近30天" :value="30" />
        </el-select>
        <el-button type="warning" v-if="canRefreshProjects" :loading="refreshing" @click="doRefreshProjects">
          <el-icon><Refresh /></el-icon> 刷新项目信息
        </el-button>
        <el-button type="primary" @click="doExport">
          <el-icon><Download /></el-icon> 导出 Excel
        </el-button>
      </div>
    </div>

    <div class="table-wrap">
      <el-table :data="tableData" v-loading="loading" stripe
        :header-cell-style="headerStyle" :cell-style="cellStyle"
        style="width:100%;background:transparent"
        :row-class-name="rowClass"
        height="calc(100vh - 180px)"
        @sort-change="handleSortChange">
        <el-table-column type="index" label="序号" width="60" align="center" fixed />
        <el-table-column prop="name" label="名称" min-width="140" show-overflow-tooltip fixed sortable="custom" />
        <el-table-column prop="cloud" label="云账号" min-width="140" show-overflow-tooltip sortable="custom" />
        <el-table-column prop="provider" label="厂商" width="80" sortable="custom" />
        <el-table-column prop="region" label="区域" min-width="120" show-overflow-tooltip sortable="custom" />
        <el-table-column prop="project" label="项目" min-width="120" show-overflow-tooltip sortable="custom" />
        <el-table-column prop="group" label="部门" min-width="100" show-overflow-tooltip sortable="custom" />
        <el-table-column prop="last_group" label="二级部门" min-width="100" show-overflow-tooltip />
        <el-table-column prop="manager" label="负责人" width="80" />
        <el-table-column prop="n_ip" label="内网IP" width="130" />
        <el-table-column prop="w_ip" label="外网IP" width="130" />
        <el-table-column prop="cpus" label="CPU核" width="70" align="center" sortable="custom" />
        <el-table-column prop="ram" label="内存GB" width="75" align="center" sortable="custom" />
        <el-table-column prop="cpu_avg" label="CPU均值%" width="90" align="center" sortable="custom">
          <template #default="{row}">
            <span :class="valueClass(row.cpu_avg)">{{ fmt(row.cpu_avg) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="cpu_max" label="CPU峰值%" width="90" align="center" sortable="custom">
          <template #default="{row}">
            <span :class="valueClass(row.cpu_max)">{{ fmt(row.cpu_max) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="mem_avg" label="内存均值%" width="95" align="center" sortable="custom">
          <template #default="{row}">
            <span :class="valueClass(row.mem_avg)">{{ fmt(row.mem_avg) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="mem_max" label="内存峰值%" width="95" align="center" sortable="custom">
          <template #default="{row}">
            <span :class="valueClass(row.mem_max)">{{ fmt(row.mem_max) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="disk_avg" label="磁盘%" width="90" align="center" sortable="custom">
          <template #default="{row}">
            <el-popover v-if="row.disk_details && row.disk_details.length >= 1"
              placement="left" width="220" trigger="hover">
              <template #reference>
                <span :class="valueClass(row.disk_avg)" style="cursor:pointer;text-decoration:underline dotted">
                  {{ fmt(row.disk_avg) }}
                </span>
              </template>
              <div class="disk-pop">
                <div v-for="d in row.disk_details" :key="d.device" class="disk-row">
                  <span class="disk-dev">{{ d.device }}</span>
                  <span :class="valueClass(d.usage)" class="disk-val">{{ d.usage }}%</span>
                </div>
              </div>
            </el-popover>
            <span v-else :class="row.disk_avg ? valueClass(row.disk_avg) : 'val-normal'" style="color:#aaa">{{ row.disk_avg ? fmt(row.disk_avg) : '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="out_avg" label="出带宽Mbps" width="105" align="center" sortable="custom">
          <template #default="{row}">{{ fmt(row.out_avg) }}</template>
        </el-table-column>
        <el-table-column prop="in_avg" label="入带宽Mbps" width="105" align="center" sortable="custom">
          <template #default="{row}">{{ fmt(row.in_avg) }}</template>
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
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import { getMetrics, getFilterOptions, exportExcel, refreshProjects, getRefreshProjectsStatus } from '../api/index.js'

const loading = ref(false)
const refreshing = ref(false)
const tableData = ref([])

const isAdmin = localStorage.getItem('role') === 'admin'
function hasAction(key) {
  if (isAdmin) return true
  const actions = JSON.parse(localStorage.getItem('actions') || '[]')
  return actions.includes('*') || actions.includes(key)
}
const canRefreshProjects = hasAction('refresh_projects')
const total = ref(0)
const page = ref(1)
const pageSize = ref(50)
const days = ref(7)
const sortField = ref('cpu_avg')
const sortOrder = ref('desc')
const opts = reactive({ clouds: [], providers: [], regions: [], projects: [] })
const filters = reactive({ cloud: '', provider: '', region: '', project: '', group: '', name: '', ip: '' })

let _debounceTimer = null
function debouncedLoad() {
  clearTimeout(_debounceTimer)
  _debounceTimer = setTimeout(() => { page.value = 1; loadData() }, 400)
}

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

const rowClass = ({ rowIndex }) => rowIndex % 2 === 1 ? 'alt-row' : ''

const fmt = (v) => v == null ? '-' : typeof v === 'number' ? v.toFixed(2) : v

const valueClass = (v) => {
  if (v >= 80) return 'val-danger'
  if (v >= 60) return 'val-warn'
  return ''
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
    const res = await getMetrics({
      ...filters, days: days.value, page: page.value, page_size: pageSize.value,
      sort_field: sortField.value, sort_order: sortOrder.value,
    })
    if (res.code === 0) {
      tableData.value = res.data
      total.value = res.total
    }
  } catch {} finally {
    loading.value = false
  }
}

async function loadOpts() {
  try {
    const res = await getFilterOptions()
    if (res.code === 0) Object.assign(opts, res.data)
  } catch {}
}

function doExport() {
  exportExcel({ ...filters, days: days.value, sort_field: sortField.value, sort_order: sortOrder.value })
}

async function doRefreshProjects() {
  refreshing.value = true
  try {
    await refreshProjects()
    await pollRefreshProjects()
  } catch {
    ElMessage.error('刷新失败')
    refreshing.value = false
  }
}

async function pollRefreshProjects() {
  const timer = setInterval(async () => {
    try {
      const res = await getRefreshProjectsStatus()
      const s = res.data
      if (s.status === 'done') {
        clearInterval(timer)
        refreshing.value = false
        ElMessage.success(`刷新完成：实例 ${s.result.instances_updated} 条，监控数据 ${s.result.metrics_updated} 条`)
        loadData()
      } else if (s.status === 'error') {
        clearInterval(timer)
        refreshing.value = false
        ElMessage.error(s.error || '刷新失败')
      }
    } catch {
      clearInterval(timer)
      refreshing.value = false
      ElMessage.error('刷新状态查询失败')
    }
  }, 2000)
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
.page-title { font-size: 16px; font-weight: 600; color: #4fc3f7; min-width: 120px; }
.filters { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; margin-left: auto; }
.table-wrap { padding: 16px 24px; }
.pagination { display: flex; justify-content: flex-end; align-items: center; gap: 16px; margin-top: 12px; }
.total-tip { font-size: 13px; color: #5a7aac; }
.val-danger { color: #ef5350; font-weight: 600; }
.val-warn { color: #ffa726; font-weight: 600; }
:deep(.el-table) { --el-table-bg-color: transparent; --el-table-tr-bg-color: transparent; }
:deep(.el-table__row.alt-row td) { background: rgba(21,65,128,0.15) !important; }
:deep(.el-table__row:hover td) { background: rgba(79,195,247,0.08) !important; }
:deep(.el-select .el-input__wrapper) { background: rgba(21,65,128,0.3); box-shadow: 0 0 0 1px rgba(79,195,247,0.2) !important; }
:deep(.el-select .el-input__inner) { color: #c8d8f0; }
:deep(.el-pagination) { --el-pagination-bg-color: rgba(21,65,128,0.3); --el-pagination-text-color: #8ba4d4; }
:deep(.el-loading-mask) { background: rgba(6,14,31,0.7); }
:deep(.el-scrollbar__bar.is-horizontal) { height: 8px; opacity: 1 !important; }
:deep(.el-scrollbar__bar.is-horizontal .el-scrollbar__thumb) { background: rgba(79,195,247,0.45); border-radius: 4px; }
:deep(.el-scrollbar__bar.is-horizontal:hover .el-scrollbar__thumb) { background: rgba(79,195,247,0.75); }
.disk-pop { font-size: 12px; }
.disk-row { display: flex; justify-content: space-between; padding: 3px 0; border-bottom: 1px solid #eee; }
.disk-dev { color: #555; max-width: 140px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.disk-val { font-weight: 600; margin-left: 8px; }
</style>
