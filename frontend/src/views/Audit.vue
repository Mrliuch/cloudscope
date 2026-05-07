<template>
  <div class="page">
    <div class="toolbar">
      <span class="page-title">系统审计</span>
      <div class="filter-group">
        <el-radio-group v-model="eventFilter" size="small" @change="() => loadLogs(1)">
          <el-radio-button value="">全部</el-radio-button>
          <el-radio-button value="login_success">登录成功</el-radio-button>
          <el-radio-button value="login_fail">登录失败</el-radio-button>
          <el-radio-button value="view_secret">查看密码</el-radio-button>
        </el-radio-group>
        <el-button size="small" :loading="loading" @click="() => loadLogs(page)">
          <el-icon><Refresh /></el-icon>
        </el-button>
      </div>
    </div>

    <div class="content" v-loading="loading">
      <el-table
        :data="logs"
        stripe
        size="small"
        style="width:100%"
        :header-cell-style="{ background: 'rgba(21,65,128,0.7)', color: '#90caf9', fontSize: '13px' }"
        :cell-style="{ background: 'transparent', color: '#c8d8f0', fontSize: '13px' }"
      >
        <el-table-column prop="ts" label="时间" width="180" />
        <el-table-column label="事件" width="120">
          <template #default="{ row }">
            <el-tag :type="tagType(row.event)" size="small" effect="plain">
              {{ eventLabel(row.event) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="username" label="用户" width="120" />
        <el-table-column prop="ip" label="IP 地址" width="150" />
        <el-table-column prop="detail" label="详情" show-overflow-tooltip />
        <el-table-column prop="user_agent" label="客户端" show-overflow-tooltip />
      </el-table>

      <div class="pagination-bar">
        <el-pagination
          v-model:current-page="page"
          :page-size="pageSize"
          :total="total"
          background
          layout="total, prev, pager, next"
          @current-change="loadLogs"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { getAuditLogs } from '../api/index.js'

const loading = ref(false)
const logs = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 50
const eventFilter = ref('')

const EVENT_LABELS = {
  login_success: '登录成功',
  login_fail:    '登录失败',
  view_secret:   '查看密码',
}

const EVENT_TAG = {
  login_success: 'success',
  login_fail:    'danger',
  view_secret:   'warning',
}

function eventLabel(event) {
  return EVENT_LABELS[event] || event
}

function tagType(event) {
  return EVENT_TAG[event] || 'info'
}

async function loadLogs(p = 1) {
  page.value = p
  loading.value = true
  try {
    const res = await getAuditLogs({
      event: eventFilter.value,
      page: page.value,
      page_size: pageSize,
    })
    if (res.code === 0) {
      logs.value = res.data.items || []
      total.value = res.data.total || 0
    }
  } catch {} finally {
    loading.value = false
  }
}

onMounted(() => loadLogs(1))
</script>

<style scoped>
.page {
  min-height: 100vh;
  background: #060e1f;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 14px 24px;
  background: rgba(10, 22, 40, 0.8);
  border-bottom: 1px solid rgba(79, 195, 247, 0.1);
}

.page-title {
  font-size: 16px;
  font-weight: 600;
  color: #4fc3f7;
  flex-shrink: 0;
}

.filter-group {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
}

.content {
  padding: 20px 24px;
}

.pagination-bar {
  display: flex;
  justify-content: flex-end;
  padding: 16px 0 4px;
}
</style>
