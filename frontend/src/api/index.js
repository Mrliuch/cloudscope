import axios from 'axios'
import router from '../router/index.js'

const http = axios.create({ baseURL: '/api', timeout: 30000 })

http.interceptors.request.use(cfg => {
  const token = localStorage.getItem('token')
  if (token) cfg.headers.Authorization = `Bearer ${token}`
  return cfg
})

http.interceptors.response.use(
  res => res.data,
  err => {
    const status = err.response?.status
    // 401 且 token_version < 2 说明是旧 token，直接清缓存跳转登录
    if (status === 401 && localStorage.getItem('token_version') < 2) {
      ;['token', 'username', 'role', 'menus', 'actions', 'token_version'].forEach(k =>
        localStorage.removeItem(k)
      )
      router.push('/login')
      return Promise.reject(err)
    }
    if (status === 401) {
      localStorage.removeItem('token')
      router.push('/login')
    }
    return Promise.reject(err)
  }
)

export const login = (data) => http.post('/login', data)
export const getSummary = (days) => http.get('/summary', { params: { days } })
export const getMetrics = (params) => http.get('/metrics', { params })
export const getFilterOptions = () => http.get('/filter-options')
export const triggerCollect = () => http.post('/collect')
export const getCollectStatus = () => http.get('/collect/status')
export const refreshProjects = () => http.post('/refresh-projects')
export const getRefreshProjectsStatus = () => http.get('/refresh-projects/status')

// 项目维护
export const getProjects = () => http.get('/projects')
export const createProject = (data) => http.post('/projects', data)
export const updateProject = (id, data) => http.put(`/projects/${id}`, data)
export const deleteProject = (id) => http.delete(`/projects/${id}`)

// 系统配置
export const getConfig = () => http.get('/config')
export const saveConfig = (data) => http.post('/config', data)

export const exportExcel = (params) => {
  const token = localStorage.getItem('token')
  const query = new URLSearchParams(params).toString()
  window.open(`/api/export?${query}&_t=${token}`)
}

// 到期资源
export const getExpiryList = (params) => http.get('/expiry', { params })
export const getExpiryFilterOptions = () => http.get('/expiry/filter-options')
export const refreshExpiry = () => http.post('/expiry/refresh')
export const getExpiryStatus = () => http.get('/expiry/status')
export const exportExpiryExcel = (params) => {
  const token = localStorage.getItem('token')
  const query = new URLSearchParams(params).toString()
  window.open(`/api/expiry/export?${query}&_t=${token}`)
}
export const sendExpiryEmail = (resources) => http.post('/expiry/send-email', { resources })
export const saveExpiryEmailOverride = (cloud, resource_id, email) =>
  http.patch('/expiry/email-override', { cloud, resource_id, email })

// 告警
export const getAlerts = () => http.get('/alerts')
export const getAlertThresholds = () => http.get('/alert-thresholds')
export const saveAlertThresholds = (data) => http.post('/alert-thresholds', data)
export const sendAlertEmail = (alerts, extraEmail = '', extraEmailMode = 'append') =>
  http.post('/alert/send-email', { alerts, extra_email: extraEmail, extra_email_mode: extraEmailMode })

// 账户余额
export const getBalance = () => http.get('/balance')

// 费用统计
export const getCostProviders = () => http.get('/cost/providers')
export const getCostData = (providerType, params) => http.get(`/cost/${providerType}`, { params })

// 用户
export const getLoginHistory = () => http.get('/login-history')
export const getVersion = () => http.get('/version')

// 审计
export const verifyAndRevealSecret = (configPath, password) =>
  http.post('/audit/verify-secret', { config_path: configPath, password })
export const getAuditLogs = (params) => http.get('/audit/logs', { params })
export const verifyPassword = (password) => http.post('/auth/verify-password', { password })

// 用户管理
export const getUsers = () => http.get('/users')
export const createUser = (data) => http.post('/users', data)
export const updateUser = (id, data) => http.put(`/users/${id}`, data)
export const deleteUser = (id) => http.delete(`/users/${id}`)
export const resetUserPassword = (id) => http.post(`/users/${id}/reset-password`)
export const changeOwnPassword = (oldPw, newPw) =>
  http.put('/profile/password', { old_password: oldPw, new_password: newPw })

// 权限组
export const getPermissionGroups = () => http.get('/permission-groups')
export const createPermissionGroup = (data) => http.post('/permission-groups', data)
export const updatePermissionGroup = (id, data) => http.put(`/permission-groups/${id}`, data)
export const deletePermissionGroup = (id) => http.delete(`/permission-groups/${id}`)

// 运维平台链接
export const getOpsLinks = () => http.get('/ops-links')
export const createOpsLink = (data) => http.post('/ops-links', data)
export const updateOpsLink = (id, data) => http.put(`/ops-links/${id}`, data)
export const deleteOpsLink = (id) => http.delete(`/ops-links/${id}`)
