<template>
  <div class="page">
    <div class="screen-title">
      <span>云资源监控大屏</span>
      <span class="datetime">{{ datetime }}</span>
    </div>

    <!-- KPI 卡片 -->
    <div class="kpi-row">
      <div class="kpi-card" v-for="k in kpis" :key="k.label">
        <div class="kpi-value">{{ k.value }}</div>
        <div class="kpi-label">{{ k.label }}</div>
      </div>
    </div>

    <!-- 图表区域 Row 1 -->
    <div class="chart-row">
      <div class="chart-box" style="flex:1">
        <div class="chart-title">各云账号主机分布</div>
        <v-chart :option="cloudPieOpt" autoresize style="height:220px" />
      </div>
      <div class="chart-box" style="flex:1">
        <div class="chart-title">各云厂商主机占比</div>
        <v-chart :option="providerPieOpt" autoresize style="height:220px" />
      </div>
      <div class="chart-box" style="flex:2">
        <div class="chart-title">项目主机数 Top 15</div>
        <v-chart :option="projectBarOpt" autoresize style="height:220px" />
      </div>
    </div>

    <!-- 图表区域 Row 2 -->
    <div class="chart-row">
      <div class="chart-box" style="flex:1">
        <div class="chart-title">CPU 使用率分布</div>
        <v-chart :option="cpuBucketOpt" autoresize style="height:220px" />
      </div>
      <div class="chart-box" style="flex:1">
        <div class="chart-title">内存使用率分布</div>
        <v-chart :option="memBucketOpt" autoresize style="height:220px" />
      </div>
      <div class="chart-box" style="flex:2">
        <div class="chart-title">选择查看天数</div>
        <div style="padding:24px 0">
          <el-radio-group v-model="days" @change="loadData" size="large">
            <el-radio-button :label="1">今日</el-radio-button>
            <el-radio-button :label="3">近3天</el-radio-button>
            <el-radio-button :label="7">近7天</el-radio-button>
            <el-radio-button :label="30">近30天</el-radio-button>
          </el-radio-group>
          <div class="stat-grid">
            <div class="stat-item" v-for="s in stats" :key="s.label">
              <span class="s-val">{{ s.value }}</span>
              <span class="s-lab">{{ s.label }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { PieChart, BarChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, LegendComponent, GridComponent } from 'echarts/components'
import { getSummary } from '../api/index.js'

use([CanvasRenderer, PieChart, BarChart, TitleComponent, TooltipComponent, LegendComponent, GridComponent])

const days = ref(1)
const summary = ref({})
const datetime = ref('')

setInterval(() => {
  const now = new Date()
  datetime.value = now.toLocaleString('zh-CN', { weekday: 'long', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' })
}, 1000)

const kpis = computed(() => [
  { label: '主机总数', value: summary.value.total_hosts ?? '-' },
  { label: '项目数量', value: summary.value.total_projects ?? '-' },
  { label: '接入云账号', value: (summary.value.cloud_dist ?? []).length },
  { label: '云厂商', value: (summary.value.provider_dist ?? []).length },
])

const stats = computed(() => {
  const cpu = summary.value.cpu_buckets ?? []
  const high = cpu.find(b => b.name === '80-100%')
  return [
    { label: 'CPU>80% 主机数', value: high?.value ?? 0 },
  ]
})

const COLORS = ['#4fc3f7','#29b6f6','#0288d1','#01579b','#81d4fa','#40c4ff','#80d8ff']

const pieOpt = (data) => ({
  backgroundColor: 'transparent',
  tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
  legend: { orient: 'vertical', right: 10, top: 'center', textStyle: { color: '#8ba4d4', fontSize: 11 } },
  series: [{
    type: 'pie', radius: ['45%', '70%'], center: ['38%', '50%'],
    data: data,
    itemStyle: { borderColor: '#060e1f', borderWidth: 2 },
    label: { show: false },
  }],
  color: COLORS,
})

const cloudPieOpt = computed(() => pieOpt(summary.value.cloud_dist ?? []))
const providerPieOpt = computed(() => pieOpt(summary.value.provider_dist ?? []))

const barOpt = (data, key) => ({
  backgroundColor: 'transparent',
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
  grid: { left: 8, right: 8, top: 8, bottom: 4, containLabel: true },
  xAxis: { type: 'value', splitLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } }, axisLabel: { color: '#5a7aac', fontSize: 10 } },
  yAxis: { type: 'category', data: (data ?? []).map(d => d.name), axisLabel: { color: '#8ba4d4', fontSize: 10, width: 90, overflow: 'truncate' } },
  series: [{ type: 'bar', data: (data ?? []).map(d => d.value), barMaxWidth: 18,
    itemStyle: { color: { type: 'linear', x: 0, y: 0, x2: 1, y2: 0,
      colorStops: [{ offset: 0, color: '#0d47a1' }, { offset: 1, color: '#4fc3f7' }] } },
    label: { show: true, position: 'right', color: '#8ba4d4', fontSize: 10 } }],
})

const projectBarOpt = computed(() => {
  const data = [...(summary.value.top_projects ?? [])].reverse()
  return barOpt(data, 'value')
})

const bucketBarOpt = (data) => ({
  backgroundColor: 'transparent',
  tooltip: { trigger: 'axis' },
  grid: { left: 8, right: 8, top: 8, bottom: 4, containLabel: true },
  xAxis: { type: 'category', data: (data ?? []).map(d => d.name), axisLabel: { color: '#8ba4d4', fontSize: 10 } },
  yAxis: { type: 'value', splitLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } }, axisLabel: { color: '#5a7aac' } },
  series: [{ type: 'bar', data: (data ?? []).map((d, i) => ({
    value: d.value,
    itemStyle: { color: ['#29b6f6','#66bb6a','#ffa726','#ef5350'][i] ?? '#4fc3f7' }
  })), barMaxWidth: 40 }],
})

const cpuBucketOpt = computed(() => bucketBarOpt(summary.value.cpu_buckets ?? []))
const memBucketOpt = computed(() => bucketBarOpt(summary.value.mem_buckets ?? []))

async function loadData() {
  try {
    const res = await getSummary(days.value)
    if (res.code === 0) summary.value = res.data
  } catch {}
}

onMounted(loadData)
</script>

<style scoped>
.page { min-height: 100vh; background: #060e1f; }
.screen-title {
  text-align: center; padding: 20px 24px 4px;
  font-size: 28px; font-weight: 700; color: #4fc3f7;
  text-shadow: 0 0 20px rgba(79,195,247,0.5);
  display: flex; justify-content: space-between; align-items: center;
}
.datetime { font-size: 13px; color: #5a7aac; font-weight: normal; }
.kpi-row { display: flex; gap: 16px; padding: 16px 24px; }
.kpi-card {
  flex: 1; text-align: center; padding: 20px;
  background: linear-gradient(135deg, rgba(21,101,192,0.25), rgba(79,195,247,0.08));
  border: 1px solid rgba(79,195,247,0.2);
  border-radius: 10px;
}
.kpi-value { font-size: 36px; font-weight: 700; color: #4fc3f7; text-shadow: 0 0 12px rgba(79,195,247,0.4); }
.kpi-label { font-size: 13px; color: #8ba4d4; margin-top: 4px; }
.chart-row { display: flex; gap: 16px; padding: 0 24px 16px; }
.chart-box {
  padding: 16px;
  background: rgba(10,22,40,0.7);
  border: 1px solid rgba(79,195,247,0.12);
  border-radius: 10px;
}
.chart-title { font-size: 13px; color: #4fc3f7; margin-bottom: 8px; font-weight: 600; }
.stat-grid { display: flex; gap: 24px; margin-top: 20px; }
.stat-item { display: flex; flex-direction: column; align-items: center; }
.s-val { font-size: 28px; font-weight: 700; color: #ef5350; }
.s-lab { font-size: 12px; color: #8ba4d4; }
:deep(.el-radio-button__inner) { background: rgba(21,65,128,0.3); border-color: rgba(79,195,247,0.2); color: #8ba4d4; }
:deep(.el-radio-button__original-radio:checked + .el-radio-button__inner) { background: #1565c0; border-color: #4fc3f7; color: #fff; }
</style>
