<template>
  <div class="login-wrap">
    <div class="login-box">
      <div class="title">
        <span class="title-main">云监控平台</span>
        <span class="title-sub">Cloud Metrics Dashboard</span>
      </div>
      <el-form :model="form" @keyup.enter="doLogin">
        <el-form-item>
          <el-input v-model="form.username" placeholder="用户名" size="large" prefix-icon="User" />
        </el-form-item>
        <el-form-item>
          <el-input v-model="form.password" type="password" placeholder="密码" size="large"
                    prefix-icon="Lock" show-password />
        </el-form-item>
        <el-button type="primary" size="large" :loading="loading" @click="doLogin" style="width:100%">
          登 录
        </el-button>
      </el-form>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { login } from '../api/index.js'

const router = useRouter()
const loading = ref(false)
const form = ref({ username: '', password: '' })

async function doLogin() {
  if (!form.value.username || !form.value.password) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  loading.value = true
  try {
    const res = await login(form.value)
    if (res.code === 0) {
      localStorage.setItem('token', res.token)
      localStorage.setItem('username', res.username)
      localStorage.setItem('role', res.role || 'user')
      localStorage.setItem('menus', JSON.stringify(res.menus || []))
      localStorage.setItem('actions', JSON.stringify(res.actions || []))
      localStorage.setItem('token_version', res.v || 1)
      router.push('/dashboard')
    } else {
      ElMessage.error(res.msg || '登录失败')
    }
  } catch (e) {
    ElMessage.error('登录失败，请检查用户名密码')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-wrap {
  min-height: 100vh;
  background: radial-gradient(ellipse at 50% 30%, #0d2657 0%, #060e1f 70%);
  display: flex;
  align-items: center;
  justify-content: center;
}
.login-box {
  width: 420px;
  padding: 48px 40px;
  background: rgba(10, 22, 40, 0.85);
  border: 1px solid rgba(79,195,247,0.25);
  border-radius: 12px;
  box-shadow: 0 0 40px rgba(79,195,247,0.12);
}
.title { text-align: center; margin-bottom: 36px; }
.title-main { display: block; font-size: 26px; font-weight: 700; color: #4fc3f7;
  text-shadow: 0 0 20px rgba(79,195,247,0.6); }
.title-sub { display: block; font-size: 13px; color: #5a7aac; margin-top: 6px; letter-spacing: 2px; }
:deep(.el-input__wrapper) {
  background: rgba(255,255,255,0.05) !important;
  box-shadow: 0 0 0 1px rgba(79,195,247,0.2) !important;
  color: #e0e8ff;
}
:deep(.el-input__inner) { color: #e0e8ff !important; }
:deep(.el-button--primary) { background: #1565c0; border-color: #1e88e5; font-size: 16px; }
:deep(.el-button--primary:hover) { background: #1e88e5; }
</style>
