<template>
  <div class="page-wrap">
    <div class="page-header">
      <span class="page-title">用户管理</span>
    </div>

    <el-tabs v-model="activeTab" class="mgmt-tabs">
      <!-- ── 用户列表 ── -->
      <el-tab-pane label="用户列表" name="users">
        <div class="toolbar">
          <el-button type="primary" @click="openCreateUser">
            <el-icon><Plus /></el-icon>新建用户
          </el-button>
        </div>

        <el-table :data="users" stripe v-loading="usersLoading"
                  :header-cell-style="headerStyle" :cell-style="cellStyle">
          <el-table-column prop="username" label="用户名" width="140" />
          <el-table-column prop="email" label="邮箱" min-width="180" />
          <el-table-column label="权限组" width="160">
            <template #default="{ row }">
              <span>{{ groupName(row.group_id) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="90" align="center">
            <template #default="{ row }">
              <el-tag v-if="row.role === 'admin'" type="warning" size="small">管理员</el-tag>
              <el-tag v-else-if="row.is_active" type="success" size="small">启用</el-tag>
              <el-tag v-else type="danger" size="small">禁用</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="创建时间" width="160" />
          <el-table-column prop="last_login" label="最后登录" width="160" />
          <el-table-column label="操作" width="180" align="center" fixed="right">
            <template #default="{ row }">
              <div v-if="row.role !== 'admin'" class="table-actions">
                <el-button size="small" type="primary" link @click="openEditUser(row)">编辑</el-button>
                <el-button size="small" type="warning" link @click="doResetPassword(row)">重置密码</el-button>
                <el-button size="small" type="danger" link @click="doDeleteUser(row)">删除</el-button>
              </div>
              <span v-else class="readonly-text">不可编辑</span>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- ── 权限组 ── -->
      <el-tab-pane label="权限组管理" name="groups">
        <div class="toolbar">
          <el-button type="primary" @click="openCreateGroup">
            <el-icon><Plus /></el-icon>新建权限组
          </el-button>
        </div>

        <el-table :data="groups" stripe v-loading="groupsLoading"
                  :header-cell-style="headerStyle" :cell-style="cellStyle">
          <el-table-column prop="name" label="权限组名称" width="160" />
          <el-table-column prop="description" label="描述" min-width="180" />
          <el-table-column label="可访问菜单" min-width="240">
            <template #default="{ row }">
              <el-tag v-for="m in row.menus" :key="m" size="small" style="margin:2px;">
                {{ resolveMenuLabel(m) }}
              </el-tag>
              <span v-if="!row.menus.length" style="color:#5a7aac;font-size:12px;">无</span>
            </template>
          </el-table-column>
          <el-table-column label="操作权限" width="240">
            <template #default="{ row }">
              <el-tag v-for="a in row.actions" :key="a" size="small" type="warning" style="margin:2px;">
                {{ ACTION_LABELS[a] || a }}
              </el-tag>
              <span v-if="!row.actions.length" style="color:#5a7aac;font-size:12px;">无</span>
            </template>
          </el-table-column>
          <el-table-column label="类型" width="80" align="center">
            <template #default="{ row }">
              <el-tag :type="row.is_preset ? 'info' : 'success'" size="small">
                {{ row.is_preset ? '预设' : '自定义' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="140" align="center" fixed="right">
            <template #default="{ row }">
              <div class="table-actions compact">
                <el-button size="small" type="primary" link @click="openEditGroup(row)">编辑</el-button>
                <el-button size="small" type="danger" link @click="doDeleteGroup(row)">删除</el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <!-- ── 用户弹窗 ── -->
    <el-dialog v-model="userDialogVisible" :title="editingUser ? '编辑用户' : '新建用户'" width="480px">
      <el-form :model="userForm" label-width="90px">
        <el-form-item label="用户名" required>
          <el-input v-model="userForm.username" :disabled="!!editingUser" placeholder="登录用户名" />
        </el-form-item>
        <el-form-item label="邮箱" required>
          <el-input v-model="userForm.email" placeholder="用于接收初始密码" />
        </el-form-item>
        <el-form-item label="权限组">
          <el-select v-model="userForm.group_id" placeholder="请选择权限组" clearable style="width:100%">
            <el-option v-for="g in groups" :key="g._id" :label="g.name" :value="g._id" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="editingUser" label="状态">
          <el-switch v-model="userForm.is_active" active-text="启用" inactive-text="禁用" />
        </el-form-item>
      </el-form>
      <div v-if="!editingUser" style="margin:0 0 0 90px;font-size:12px;color:#5a7aac;">
        创建后系统将自动生成随机密码并发送至用户邮箱
      </div>
      <template #footer>
        <el-button @click="userDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="userSaving" @click="submitUser">确定</el-button>
      </template>
    </el-dialog>

    <!-- ── 权限组弹窗 ── -->
    <el-dialog v-model="groupDialogVisible" :title="editingGroup ? '编辑权限组' : '新建权限组'" width="560px">
      <el-form :model="groupForm" label-width="90px">
        <el-form-item label="名称" required>
          <el-input v-model="groupForm.name" placeholder="权限组名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="groupForm.description" placeholder="简要说明此权限组用途" />
        </el-form-item>
        <el-form-item label="菜单权限">
          <el-checkbox-group v-model="groupForm.menus">
            <el-checkbox v-for="(label, key) in MENU_LABELS" :key="key" :value="key"
                         style="margin:4px 8px 4px 0;">
              {{ label }}
            </el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item label="操作权限">
          <el-checkbox-group v-model="groupForm.actions">
            <el-checkbox v-for="(label, key) in ACTION_LABELS" :key="key" :value="key"
                         style="margin:4px 8px 4px 0;">
              {{ label }}
            </el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item v-if="allOpsLinks.length > 0" label="运维平台">
          <div style="font-size:11px;color:#5a7aac;margin-bottom:6px">选择该权限组可见的运维平台子菜单</div>
          <el-checkbox-group v-model="groupForm.menus">
            <el-checkbox
              v-for="lk in allOpsLinks"
              :key="`ops_link:${lk._id}`"
              :value="`ops_link:${lk._id}`"
              style="margin:4px 8px 4px 0;"
            >
              {{ lk.name }}
            </el-checkbox>
          </el-checkbox-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="groupDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="groupSaving" @click="submitGroup">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import {
  getUsers, createUser, updateUser, deleteUser, resetUserPassword,
  getPermissionGroups, createPermissionGroup, updatePermissionGroup, deletePermissionGroup,
  getOpsLinks,
} from '../api/index.js'

const MENU_LABELS = {
  dashboard: '数据大屏',
  table: '明细列表',
  expiry: '资源到期',
  alert: '告警中心',
  balance: '账户余额',
  cost: '费用统计',
  project_mgmt: '项目维护',
}

const ACTION_LABELS = {
  collect: '手动采集',
  refresh_expiry: '刷新实例',
  refresh_projects: '刷新项目信息',
  send_email: '发送邮件提醒',
}

function resolveMenuLabel(key) {
  if (MENU_LABELS[key]) return MENU_LABELS[key]
  if (key.startsWith('ops_link:')) {
    const id = key.slice(9)
    const lk = allOpsLinks.value.find(l => l._id === id)
    return lk ? `运维-${lk.name}` : key
  }
  return key
}

const headerStyle = { background: 'rgba(21,65,128,0.7)', color: '#90caf9', fontSize: '13px' }
const cellStyle = { background: 'transparent', color: '#c8d8f0', fontSize: '13px' }

const activeTab = ref('users')

// ── 用户 ──
const users = ref([])
const usersLoading = ref(false)
const userDialogVisible = ref(false)
const editingUser = ref(null)
const userSaving = ref(false)
const userForm = ref({ username: '', email: '', group_id: null, is_active: true })

async function loadUsers() {
  usersLoading.value = true
  try {
    const res = await getUsers()
    if (res.code === 0) users.value = res.data
  } catch {} finally { usersLoading.value = false }
}

function openCreateUser() {
  editingUser.value = null
  userForm.value = { username: '', email: '', group_id: null, is_active: true }
  userDialogVisible.value = true
}

function openEditUser(row) {
  editingUser.value = row
  userForm.value = { username: row.username, email: row.email,
                     group_id: row.group_id || null, is_active: row.is_active }
  userDialogVisible.value = true
}

async function submitUser() {
  if (!userForm.value.username) { ElMessage.warning('用户名不能为空'); return }
  if (!userForm.value.email) { ElMessage.warning('邮箱不能为空'); return }
  userSaving.value = true
  try {
    let res
    if (editingUser.value) {
      res = await updateUser(editingUser.value._id, {
        email: userForm.value.email,
        group_id: userForm.value.group_id || null,
        is_active: userForm.value.is_active,
      })
    } else {
      res = await createUser({
        username: userForm.value.username,
        email: userForm.value.email,
        group_id: userForm.value.group_id || null,
      })
    }
    if (res.code === 0) {
      ElMessage.success(editingUser.value ? '用户已更新' : '用户已创建，初始密码已发送至邮箱')
      userDialogVisible.value = false
      await loadUsers()
    } else {
      ElMessage.error(res.msg || '操作失败')
    }
  } catch { ElMessage.error('操作失败') } finally { userSaving.value = false }
}

async function doResetPassword(row) {
  try {
    await ElMessageBox.confirm(`确定要重置用户 "${row.username}" 的密码吗？新密码将发送至 ${row.email}`, '确认重置', {
      type: 'warning', confirmButtonText: '确定重置', cancelButtonText: '取消',
    })
    const res = await resetUserPassword(row._id)
    if (res.code === 0) ElMessage.success('密码已重置并发送邮件')
    else ElMessage.error(res.msg || '重置失败')
  } catch {}
}

async function doDeleteUser(row) {
  try {
    await ElMessageBox.confirm(`确定要删除用户 "${row.username}" 吗？此操作不可撤销`, '确认删除', {
      type: 'error', confirmButtonText: '确定删除', cancelButtonText: '取消',
    })
    const res = await deleteUser(row._id)
    if (res.code === 0) { ElMessage.success('用户已删除'); await loadUsers() }
    else ElMessage.error(res.msg || '删除失败')
  } catch {}
}

// ── 运维平台链接（用于权限组编辑器） ──
const allOpsLinks = ref([])

async function loadAllOpsLinks() {
  try {
    const res = await getOpsLinks()
    if (res.code === 0) allOpsLinks.value = res.data
  } catch {}
}

// ── 权限组 ──
const groups = ref([])
const groupsLoading = ref(false)
const groupDialogVisible = ref(false)
const editingGroup = ref(null)
const groupSaving = ref(false)
const groupForm = ref({ name: '', description: '', menus: [], actions: [] })

function groupName(groupId) {
  if (!groupId) return '—'
  const g = groups.value.find(g => g._id === groupId)
  return g ? g.name : '—'
}

async function loadGroups() {
  groupsLoading.value = true
  try {
    const res = await getPermissionGroups()
    if (res.code === 0) groups.value = res.data
  } catch {} finally { groupsLoading.value = false }
}

function openCreateGroup() {
  editingGroup.value = null
  groupForm.value = { name: '', description: '', menus: [], actions: [] }
  groupDialogVisible.value = true
}

function openEditGroup(row) {
  editingGroup.value = row
  groupForm.value = { name: row.name, description: row.description || '',
                      menus: [...(row.menus || [])], actions: [...(row.actions || [])] }
  groupDialogVisible.value = true
}

async function submitGroup() {
  if (!groupForm.value.name) { ElMessage.warning('权限组名称不能为空'); return }
  groupSaving.value = true
  try {
    let res
    if (editingGroup.value) {
      res = await updatePermissionGroup(editingGroup.value._id, groupForm.value)
    } else {
      res = await createPermissionGroup(groupForm.value)
    }
    if (res.code === 0) {
      ElMessage.success(editingGroup.value ? '权限组已更新' : '权限组已创建')
      groupDialogVisible.value = false
      await loadGroups()
    } else {
      ElMessage.error(res.msg || '操作失败')
    }
  } catch { ElMessage.error('操作失败') } finally { groupSaving.value = false }
}

async function doDeleteGroup(row) {
  try {
    await ElMessageBox.confirm(`确定要删除权限组 "${row.name}" 吗？`, '确认删除', {
      type: 'warning', confirmButtonText: '确定删除', cancelButtonText: '取消',
    })
    const res = await deletePermissionGroup(row._id)
    if (res.code === 0) { ElMessage.success('权限组已删除'); await loadGroups() }
    else ElMessage.error(res.msg || '删除失败（可能有用户正在使用此权限组）')
  } catch {}
}

onMounted(async () => {
  await Promise.all([loadUsers(), loadGroups(), loadAllOpsLinks()])
})
</script>

<style scoped>
.page-wrap {
  padding: 24px;
  min-height: 100%;
  background: rgba(6, 14, 31, 0.6);
}

.page-header {
  margin-bottom: 20px;
}

.page-title {
  font-size: 20px;
  font-weight: 700;
  color: #4fc3f7;
}

.mgmt-tabs {
  --el-tabs-header-height: 42px;
}

:deep(.el-tabs__nav-wrap::after) {
  background: rgba(79, 195, 247, 0.15);
}

:deep(.el-tabs__item) {
  color: #8ba4d4;
  font-size: 14px;
}

:deep(.el-tabs__item.is-active) {
  color: #4fc3f7;
}

:deep(.el-tabs__active-bar) {
  background: #4fc3f7;
}

.toolbar {
  margin-bottom: 16px;
}

:deep(.el-table) {
  background: transparent;
  --el-table-border-color: rgba(79, 195, 247, 0.12);
  --el-table-tr-bg-color: transparent;
  --el-table-row-hover-bg-color: rgba(79, 195, 247, 0.06);
  --el-table-header-bg-color: rgba(21, 65, 128, 0.5);
}

:deep(.el-table__inner-wrapper::before) {
  background: rgba(79, 195, 247, 0.12);
}

.table-actions {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  white-space: nowrap;
}

.table-actions.compact {
  gap: 16px;
}

.table-actions :deep(.el-button) {
  height: auto;
  min-height: 0;
  margin-left: 0;
  padding: 0;
  font-size: 12px;
  font-weight: 600;
  line-height: 1.4;
}

.table-actions :deep(.el-button.is-link:hover) {
  text-decoration: none;
  filter: brightness(1.18);
}

.readonly-text {
  color: #5a7aac;
  font-size: 12px;
}
</style>
