<template>
  <div class="page">
    <div class="toolbar">
      <span class="page-title">项目维护</span>
      <div class="actions">
        <el-input v-model="search" placeholder="搜索项目/部门/负责人" clearable style="width:240px"
          prefix-icon="Search" @input="onSearch" />
        <el-button type="primary" @click="openDialog()">
          <el-icon><Plus /></el-icon> 新增项目
        </el-button>
        <el-button type="warning" v-if="canRefresh" :loading="refreshing" @click="doRefresh">
          <el-icon><Refresh /></el-icon> 刷新实例数据
        </el-button>
      </div>
    </div>

    <div class="table-wrap">
      <el-table :data="filtered" v-loading="loading" stripe
        :header-cell-style="headerStyle" :cell-style="cellStyle"
        style="width:100%" height="calc(100vh - 180px)">
        <el-table-column type="index" label="序号" width="60" align="center" />
        <el-table-column prop="project" label="项目名称" min-width="160" show-overflow-tooltip />
        <el-table-column prop="group" label="部门" min-width="120" show-overflow-tooltip />
        <el-table-column prop="last_group" label="二级部门" min-width="120" show-overflow-tooltip />
        <el-table-column prop="manager" label="负责人" width="100" />
        <el-table-column prop="pms" label="PMS" min-width="160" show-overflow-tooltip />
        <el-table-column prop="cloud" label="云厂商" width="100" />
        <el-table-column prop="notify_email" label="通知人邮箱" min-width="200" show-overflow-tooltip />
        <el-table-column label="操作" width="130" align="center" fixed="right">
          <template #default="{row}">
            <el-button size="small" type="primary" text @click="openDialog(row)">编辑</el-button>
            <el-popconfirm title="确认删除该项目？" @confirm="doDelete(row._id)">
              <template #reference>
                <el-button size="small" type="danger" text>删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>

      <div class="footer-tip">共 {{ filtered.length }} 条</div>
    </div>

    <!-- 新增/编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="form._id ? '编辑项目' : '新增项目'"
      width="480px" :close-on-click-modal="false">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="90px">
        <el-form-item label="项目名称" prop="project">
          <el-input v-model="form.project" :disabled="!!form._id" />
        </el-form-item>
        <el-form-item label="部门">
          <el-input v-model="form.group" />
        </el-form-item>
        <el-form-item label="二级部门">
          <el-input v-model="form.last_group" />
        </el-form-item>
        <el-form-item label="负责人">
          <el-input v-model="form.manager" />
        </el-form-item>
        <el-form-item label="PMS">
          <el-input v-model="form.pms" />
        </el-form-item>
        <el-form-item label="云厂商">
          <el-input v-model="form.cloud" />
        </el-form-item>
        <el-form-item label="通知邮箱">
          <el-input v-model="form.notify_email" placeholder="多个邮箱用逗号分隔" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="doSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getProjects, createProject, updateProject, deleteProject, refreshProjects, getRefreshProjectsStatus } from '../api/index.js'

const loading = ref(false)
const saving = ref(false)
const refreshing = ref(false)
const projects = ref([])

const isAdmin = localStorage.getItem('role') === 'admin'
function hasAction(key) {
  if (isAdmin) return true
  const actions = JSON.parse(localStorage.getItem('actions') || '[]')
  return actions.includes('*') || actions.includes(key)
}
const canRefresh = hasAction('refresh_projects')
const search = ref('')
const dialogVisible = ref(false)
const formRef = ref(null)

const emptyForm = () => ({ _id: '', project: '', group: '', last_group: '', manager: '', pms: '', cloud: '', notify_email: '' })
const form = ref(emptyForm())
const rules = { project: [{ required: true, message: '项目名称不能为空', trigger: 'blur' }] }

const filtered = computed(() => {
  const q = search.value.toLowerCase()
  if (!q) return projects.value
  return projects.value.filter(r =>
    [r.project, r.group, r.last_group, r.manager].some(v => v && v.toLowerCase().includes(q))
  )
})

const headerStyle = () => ({
  background: 'rgba(21,65,128,0.8)', color: '#90caf9',
  fontSize: '12px', borderBottom: '1px solid rgba(79,195,247,0.15)',
})
const cellStyle = () => ({
  background: 'transparent', color: '#c8d8f0',
  borderBottom: '1px solid rgba(79,195,247,0.06)', fontSize: '12px',
})

function onSearch() {}

function openDialog(row = null) {
  form.value = row ? { ...row } : emptyForm()
  dialogVisible.value = true
}

async function doSave() {
  await formRef.value.validate()
  saving.value = true
  try {
    const { _id, ...data } = form.value
    if (_id) {
      await updateProject(_id, data)
    } else {
      await createProject(data)
    }
    ElMessage.success('保存成功')
    dialogVisible.value = false
    await loadData()
  } catch {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

async function doDelete(id) {
  try {
    await deleteProject(id)
    ElMessage.success('已删除')
    await loadData()
  } catch {
    ElMessage.error('删除失败')
  }
}

async function doRefresh() {
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
        ElMessage.success(`刷新完成：${s.result.instances_updated} 条实例，${s.result.metrics_updated} 条监控记录`)
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

async function loadData() {
  loading.value = true
  try {
    const res = await getProjects()
    if (res.code === 0) projects.value = res.data
  } catch {} finally {
    loading.value = false
  }
}

onMounted(loadData)
</script>

<style scoped>
.page { min-height: 100vh; background: #060e1f; }
.toolbar {
  display: flex; align-items: center; flex-wrap: wrap; gap: 12px;
  padding: 14px 24px;
  background: rgba(10,22,40,0.8);
  border-bottom: 1px solid rgba(79,195,247,0.1);
}
.page-title { font-size: 16px; font-weight: 600; color: #4fc3f7; min-width: 100px; }
.actions { display: flex; gap: 10px; align-items: center; margin-left: auto; flex-wrap: wrap; }
.table-wrap { padding: 16px 24px; }
.footer-tip { font-size: 13px; color: #5a7aac; margin-top: 10px; text-align: right; }
:deep(.el-table) { --el-table-bg-color: transparent; --el-table-tr-bg-color: transparent; }
:deep(.el-table__row:hover td) { background: rgba(79,195,247,0.08) !important; }
:deep(.el-table__row:nth-child(even) td) { background: rgba(21,65,128,0.12) !important; }
:deep(.el-select .el-input__wrapper),
:deep(.el-input__wrapper) { background: rgba(21,65,128,0.3); box-shadow: 0 0 0 1px rgba(79,195,247,0.2) !important; }
:deep(.el-input__inner) { color: #c8d8f0; }
:deep(.el-dialog) { background: #0d1b33; border: 1px solid rgba(79,195,247,0.2); }
:deep(.el-dialog__title) { color: #4fc3f7; }
:deep(.el-form-item__label) { color: #8ba4d4; }
</style>
