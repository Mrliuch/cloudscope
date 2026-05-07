<template>
  <div class="page">
    <!-- 筛选栏 -->
    <div class="toolbar">
      <span class="page-title">华为云 · 费用统计</span>

      <div class="filter-group">
        <span class="filter-label">账号</span>
        <el-select v-model="filters.cloud" style="width:200px" placeholder="选择账号"
          @change="loadData">
          <el-option v-for="c in cloudList" :key="c" :label="c" :value="c" />
        </el-select>
      </div>

      <div class="filter-group">
        <span class="filter-label">维度</span>
        <div class="period-tabs">
          <div v-for="t in periodOptions" :key="t.value"
               class="tab" :class="{ active: filters.period === t.value }"
               @click="switchPeriod(t.value)">
            {{ t.label }}
          </div>
        </div>
      </div>

      <!-- 按月 -->
      <div v-if="filters.period === 'month'" class="filter-group">
        <span class="filter-label">月份</span>
        <el-date-picker v-model="filters.monthDate" type="month" format="YYYY年MM月"
          value-format="YYYY-MM" style="width:150px" @change="loadData" />
      </div>

      <!-- 按季度 -->
      <template v-if="filters.period === 'quarter'">
        <div class="filter-group">
          <span class="filter-label">年份</span>
          <el-select v-model="filters.year" style="width:90px" @change="loadData">
            <el-option v-for="y in yearOptions" :key="y" :label="`${y}年`" :value="y" />
          </el-select>
        </div>
        <div class="filter-group">
          <span class="filter-label">季度</span>
          <el-select v-model="filters.quarter" style="width:90px" @change="loadData">
            <el-option label="Q1" :value="1" /><el-option label="Q2" :value="2" />
            <el-option label="Q3" :value="3" /><el-option label="Q4" :value="4" />
          </el-select>
        </div>
      </template>

      <!-- 按年 -->
      <div v-if="filters.period === 'year'" class="filter-group">
        <span class="filter-label">年份</span>
        <el-date-picker v-model="filters.yearDate" type="year" format="YYYY年"
          value-format="YYYY" style="width:120px" @change="loadData" />
      </div>
    </div>

    <div class="content">
      <!-- 无数据提示 -->
      <div v-if="!loading && !hasData" class="empty-tip">
        <el-empty description="暂无费用数据，请先触发手动采集" />
      </div>

      <template v-else>
        <!-- 汇总卡片 -->
        <div class="summary-cards">
          <div class="card" v-for="c in summaryCards" :key="c.key">
            <div class="card-label">{{ c.label }}</div>
            <div class="card-value">
              {{ fmtAmt(summary[c.key]) }}<span class="unit">元</span>
            </div>
            <div v-if="c.key === 'total' && summary.vs_last !== null" class="card-sub">
              较上期
              <span :class="summary.vs_last > 0 ? 'txt-up' : 'txt-down'">
                {{ summary.vs_last > 0 ? '↑' : '↓' }}
                {{ Math.abs(summary.vs_last) }}%
              </span>
            </div>
            <div v-else class="card-sub">
              占比 {{ pct(summary[c.key], summary.total) }}
            </div>
            <div class="card-bar">
              <div class="card-bar-fill"
                :style="{ width: pct(summary[c.key], summary.total), background: c.color }">
              </div>
            </div>
          </div>
        </div>

        <!-- 图表行 -->
        <div class="charts-row">
          <!-- 月度趋势 -->
          <div class="chart-box" style="flex:2">
            <div class="chart-title">月度费用趋势</div>
            <v-chart :option="trendOpt" autoresize style="height:220px" />
          </div>
          <!-- 费用构成 -->
          <div class="chart-box" style="flex:1">
            <div class="chart-title">费用构成</div>
            <v-chart :option="pieOpt" autoresize style="height:220px" />
          </div>
        </div>

        <!-- 项目明细表 -->
        <div class="table-box">
          <div class="table-header">
            <span class="table-title">项目费用明细</span>
            <span class="table-tip">共 {{ projects.length }} 个项目</span>
          </div>
          <div style="overflow-x:auto">
            <el-table :data="projects" v-loading="loading" stripe
              :header-cell-style="headerStyle" :cell-style="cellStyle"
              style="width:100%;background:transparent"
              :default-sort="{ prop: 'total', order: 'descending' }">
              <el-table-column type="index" label="排名" width="60" align="center" />
              <el-table-column prop="project" label="项目名称" min-width="140" show-overflow-tooltip>
                <template #default="{ row }">
                  <span style="color:#4fc3f7;font-weight:500">{{ row.project }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="compute"  label="计算（元）"  width="110" align="right" sortable>
                <template #default="{ row }">{{ fmtAmt(row.compute) }}</template>
              </el-table-column>
              <el-table-column prop="storage"  label="存储（元）"  width="110" align="right" sortable>
                <template #default="{ row }">{{ fmtAmt(row.storage) }}</template>
              </el-table-column>
              <el-table-column prop="network"  label="网络（元）"  width="110" align="right" sortable>
                <template #default="{ row }">{{ fmtAmt(row.network) }}</template>
              </el-table-column>
              <el-table-column prop="database" label="数据库（元）" width="115" align="right" sortable>
                <template #default="{ row }">{{ fmtAmt(row.database) }}</template>
              </el-table-column>
              <el-table-column prop="other"    label="其他（元）"  width="110" align="right" sortable>
                <template #default="{ row }">{{ fmtAmt(row.other) }}</template>
              </el-table-column>
              <el-table-column prop="total" label="合计（元）" width="120" align="right" sortable>
                <template #default="{ row }">
                  <span style="color:#4fc3f7;font-weight:700">{{ fmtAmt(row.total) }}</span>
                </template>
              </el-table-column>
              <el-table-column label="占比" width="130" align="right">
                <template #default="{ row }">
                  <div class="pct-bar-wrap">
                    <div class="pct-bar-fill"
                      :style="{ width: pct(row.total, summary.total) }"></div>
                  </div>
                  <span style="font-size:12px;color:#8ba4d4;margin-left:6px">
                    {{ pct(row.total, summary.total) }}
                  </span>
                </template>
              </el-table-column>
              <el-table-column prop="vs_last" label="环比" width="90" align="center" sortable>
                <template #default="{ row }">
                  <span v-if="row.vs_last === null" style="color:#4a6080">-</span>
                  <el-tag v-else-if="row.vs_last > 0" type="danger" size="small">
                    ↑ {{ row.vs_last }}%
                  </el-tag>
                  <el-tag v-else-if="row.vs_last < 0" type="success" size="small">
                    ↓ {{ Math.abs(row.vs_last) }}%
                  </el-tag>
                  <el-tag v-else type="info" size="small">持平</el-tag>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, PieChart, LineChart } from 'echarts/charts'
import { TooltipComponent, LegendComponent, GridComponent } from 'echarts/components'
import { getCostProviders, getCostData } from '../api/index.js'

use([CanvasRenderer, BarChart, PieChart, LineChart, TooltipComponent, LegendComponent, GridComponent])

const now = new Date()
const loading = ref(false)
const cloudList = ref([])
const summary  = ref({ total: 0, compute: 0, storage: 0, network: 0, database: 0, other: 0, vs_last: null })
const trend    = ref([])
const cmpTrend = ref([])
const projects = ref([])
const hasData  = computed(() => summary.value.total > 0 || projects.value.length > 0)

const filters = ref({
  cloud:     '',
  period:    'month',
  monthDate: `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`,
  year:      now.getFullYear(),
  quarter:   Math.ceil((now.getMonth() + 1) / 3),
  yearDate:  String(now.getFullYear()),
})

const periodOptions = [
  { value: 'month',   label: '按月'   },
  { value: 'quarter', label: '按季度' },
  { value: 'year',    label: '按年'   },
]

const yearOptions = Array.from({ length: 4 }, (_, i) => now.getFullYear() - i)

const summaryCards = [
  { key: 'total',    label: '本期总费用',        color: '#4fc3f7' },
  { key: 'compute',  label: '计算费用（ECS）',    color: '#42a5f5' },
  { key: 'storage',  label: '存储费用（OBS/EVS）',color: '#66bb6a' },
  { key: 'network',  label: '网络费用（EIP/带宽）',color: '#ffa726'},
  { key: 'database', label: '数据库费用',          color: '#ab47bc' },
  { key: 'other',    label: '其他费用',            color: '#ef5350' },
]

const COLORS = ['#4fc3f7', '#42a5f5', '#66bb6a', '#ffa726', '#ab47bc', '#ef5350']

function fmtAmt(v) {
  if (!v) return '0.00'
  return Number(v).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function pct(part, total) {
  if (!total || !part) return '0%'
  return (part / total * 100).toFixed(1) + '%'
}

function switchPeriod(p) {
  filters.value.period = p
  loadData()
}

function buildParams() {
  const f = filters.value
  const p = { cloud: f.cloud, period: f.period }
  if (f.period === 'month' && f.monthDate) {
    const [y, m] = f.monthDate.split('-')
    p.year = y; p.month = m
  } else if (f.period === 'quarter') {
    p.year = f.year; p.quarter = f.quarter
  } else if (f.period === 'year' && f.yearDate) {
    p.year = f.yearDate
  }
  return p
}

async function loadData() {
  if (!filters.value.cloud) return
  loading.value = true
  try {
    const res = await getCostData('huawei', buildParams())
    if (res.code === 0) {
      summary.value  = res.data.summary
      trend.value    = res.data.trend
      cmpTrend.value = res.data.cmp_trend
      projects.value = res.data.projects
    }
  } catch {} finally {
    loading.value = false
  }
}

const trendOpt = computed(() => ({
  backgroundColor: 'transparent',
  tooltip: { trigger: 'axis', formatter: (p) => {
    return p.map(item => `${item.seriesName}: ¥${Number(item.value).toLocaleString('zh-CN', { minimumFractionDigits: 2 })}`).join('<br/>')
  }},
  legend: { data: ['本期', '上期（对比）'], textStyle: { color: '#8ba4d4' }, top: 0 },
  grid: { left: 60, right: 20, top: 36, bottom: 28 },
  xAxis: {
    type: 'category',
    data: trend.value.map(t => t.month),
    axisLine: { lineStyle: { color: 'rgba(79,195,247,0.2)' } },
    axisLabel: { color: '#5a7aac', fontSize: 11 },
  },
  yAxis: {
    type: 'value',
    axisLabel: { color: '#5a7aac', fontSize: 11, formatter: v => v >= 10000 ? (v/10000).toFixed(1)+'万' : v },
    splitLine: { lineStyle: { color: 'rgba(79,195,247,0.08)' } },
  },
  series: [
    {
      name: '本期', type: 'bar', barMaxWidth: 40,
      data: trend.value.map(t => t.amount),
      itemStyle: { color: { type: 'linear', x: 0, y: 1, x2: 0, y2: 0, colorStops: [
        { offset: 0, color: 'rgba(79,195,247,0.4)' },
        { offset: 1, color: 'rgba(79,195,247,0.9)' },
      ]}},
    },
    {
      name: '上期（对比）', type: 'bar', barMaxWidth: 40,
      data: cmpTrend.value.map(t => t.amount),
      itemStyle: { color: 'rgba(79,195,247,0.18)' },
    },
  ],
}))

const pieOpt = computed(() => {
  const cats = [
    { name: '计算',   value: summary.value.compute  },
    { name: '存储',   value: summary.value.storage  },
    { name: '网络',   value: summary.value.network  },
    { name: '数据库', value: summary.value.database },
    { name: '其他',   value: summary.value.other    },
  ].filter(c => c.value > 0)

  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'item', formatter: '{b}: ¥{c} ({d}%)' },
    legend: {
      orient: 'vertical', right: 10, top: 'middle',
      textStyle: { color: '#8ba4d4', fontSize: 12 },
    },
    series: [{
      type: 'pie', radius: ['45%', '70%'],
      center: ['38%', '50%'],
      label: { show: false },
      data: cats.map((c, i) => ({ ...c, itemStyle: { color: COLORS[i] } })),
    }],
  }
})

const headerStyle = () => ({
  background: 'rgba(21,65,128,0.8)', color: '#90caf9',
  fontSize: '12px', borderBottom: '1px solid rgba(79,195,247,0.15)',
})
const cellStyle = () => ({
  background: 'transparent', color: '#c8d8f0',
  borderBottom: '1px solid rgba(79,195,247,0.06)', fontSize: '12px',
})

onMounted(async () => {
  try {
    const res = await getCostProviders()
    if (res.code === 0) {
      const hw = res.data.find(p => p.provider === 'huawei')
      if (hw && hw.clouds.length) {
        cloudList.value = hw.clouds
        filters.value.cloud = hw.clouds[0]
        loadData()
      }
    }
  } catch {}
})
</script>

<style scoped>
.page { min-height: 100vh; background: #060e1f; }

.toolbar {
  display: flex; align-items: center; flex-wrap: wrap; gap: 12px;
  padding: 14px 24px; background: rgba(10,22,40,0.8);
  border-bottom: 1px solid rgba(79,195,247,0.1);
}
.page-title { font-size: 17px; font-weight: 600; color: #4fc3f7; margin-right: 8px; }
.filter-group { display: flex; align-items: center; gap: 8px; }
.filter-label { font-size: 13px; color: #5a7aac; }
.period-tabs { display: flex; gap: 4px; }
.tab { height: 32px; padding: 0 12px; border-radius: 4px;
  border: 1px solid rgba(79,195,247,0.2); color: #8ba4d4;
  font-size: 13px; cursor: pointer; display: flex; align-items: center; }
.tab.active { background: rgba(79,195,247,0.15); color: #4fc3f7; border-color: #4fc3f7; }
.tab:hover:not(.active) { color: #c8d8f0; }

.content { padding: 20px 24px; display: flex; flex-direction: column; gap: 16px; }
.empty-tip { padding: 80px 0; text-align: center; }

/* 汇总卡片 */
.summary-cards { display: flex; gap: 12px; flex-wrap: wrap; }
.card {
  flex: 1; min-width: 160px; background: rgba(10,22,40,0.8);
  border: 1px solid rgba(79,195,247,0.12); border-radius: 8px; padding: 14px 16px;
}
.card-label { font-size: 12px; color: #5a7aac; margin-bottom: 6px; }
.card-value { font-size: 22px; font-weight: 700; color: #4fc3f7; line-height: 1.2; }
.unit { font-size: 12px; font-weight: 400; color: #8ba4d4; margin-left: 3px; }
.card-sub { font-size: 12px; color: #5a7aac; margin-top: 4px; }
.txt-up { color: #ef5350; font-weight: 600; }
.txt-down { color: #66bb6a; font-weight: 600; }
.card-bar { height: 3px; background: rgba(79,195,247,0.1); border-radius: 2px; margin-top: 8px; overflow: hidden; }
.card-bar-fill { height: 100%; border-radius: 2px; }

/* 图表 */
.charts-row { display: flex; gap: 16px; }
.chart-box {
  background: rgba(10,22,40,0.8); border: 1px solid rgba(79,195,247,0.12);
  border-radius: 8px; padding: 16px 20px;
}
.chart-title { font-size: 14px; color: #8ba4d4; margin-bottom: 8px; }

/* 明细表 */
.table-box {
  background: rgba(10,22,40,0.8); border: 1px solid rgba(79,195,247,0.12);
  border-radius: 8px; overflow: hidden;
}
.table-header {
  padding: 12px 20px; border-bottom: 1px solid rgba(79,195,247,0.1);
  display: flex; align-items: center; justify-content: space-between;
}
.table-title { font-size: 14px; color: #8ba4d4; }
.table-tip { font-size: 12px; color: #4a6080; }

.pct-bar-wrap { display: inline-block; width: 60px; height: 5px; background: rgba(79,195,247,0.1); border-radius: 3px; vertical-align: middle; overflow: hidden; }
.pct-bar-fill { height: 100%; background: rgba(79,195,247,0.5); border-radius: 3px; }

:deep(.el-table) { --el-table-bg-color: transparent; --el-table-tr-bg-color: transparent; }
:deep(.el-table__row:nth-child(even) td) { background: rgba(21,65,128,0.1) !important; }
:deep(.el-table__row:hover td) { background: rgba(79,195,247,0.06) !important; }
:deep(.el-select .el-input__wrapper) { background: rgba(21,65,128,0.3); box-shadow: 0 0 0 1px rgba(79,195,247,0.2) !important; }
:deep(.el-select .el-input__inner) { color: #c8d8f0; }
:deep(.el-scrollbar__bar.is-horizontal) { height: 8px; opacity: 1 !important; }
:deep(.el-scrollbar__bar.is-horizontal .el-scrollbar__thumb) { background: rgba(79,195,247,0.45); border-radius: 4px; }
</style>
