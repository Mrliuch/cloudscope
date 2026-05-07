import { createRouter, createWebHistory } from 'vue-router'

// 菜单 key → 路由 path 映射
const MENU_ROUTE_MAP = {
  dashboard: 'dashboard',
  table: 'table',
  expiry: 'expiry',
  alert: 'alerts',
  balance: 'balance',
  cost: 'cost',
  project_mgmt: 'projects',
  system_config: 'config',
  audit: 'audit',
  user_mgmt: 'users',
}

function hasMenuAccess(routePath) {
  const menus = JSON.parse(localStorage.getItem('menus') || '[]')
  if (menus.includes('*')) return true
  // cost 子路由特殊处理
  if (routePath.startsWith('cost')) return menus.includes('cost')
  const entry = Object.entries(MENU_ROUTE_MAP).find(([, p]) => p === routePath)
  if (!entry) return true
  return menus.includes(entry[0])
}

const routes = [
  { path: '/login', component: () => import('../views/Login.vue') },
  {
    path: '/',
    component: () => import('../layouts/MainLayout.vue'),
    meta: { auth: true },
    children: [
      { path: '', redirect: '/dashboard' },
      { path: 'dashboard', component: () => import('../views/Dashboard.vue') },
      { path: 'table',     component: () => import('../views/Table.vue') },
      { path: 'expiry',    component: () => import('../views/Expiry.vue') },
      { path: 'alerts',    component: () => import('../views/Alert.vue') },
      { path: 'projects',  component: () => import('../views/ProjectMgmt.vue') },
      { path: 'config',    component: () => import('../views/SystemConfig.vue'), meta: { adminOnly: true } },
      { path: 'balance',   component: () => import('../views/Balance.vue') },
      { path: 'cost/:provider', component: () => import('../views/CostPage.vue') },
      { path: 'audit',     component: () => import('../views/Audit.vue'), meta: { adminOnly: true } },
      { path: 'users',     component: () => import('../views/UserMgmt.vue'), meta: { adminOnly: true } },
    ],
  },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach((to, from, next) => {
  const needsAuth = to.matched.some(r => r.meta.auth)
  if (needsAuth && !localStorage.getItem('token')) {
    return next('/login')
  }
  const role = localStorage.getItem('role') || 'user'
  if (to.meta.adminOnly && role !== 'admin') {
    return next('/dashboard')
  }
  // 非 admin 检查菜单权限
  if (needsAuth && role !== 'admin') {
    const routePath = to.path.replace(/^\//, '')
    if (!hasMenuAccess(routePath)) {
      return next('/dashboard')
    }
  }
  next()
})

export default router
