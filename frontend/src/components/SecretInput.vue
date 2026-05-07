<template>
  <div class="secret-wrap">
    <el-input
      :value="displayValue"
      readonly
      autocomplete="off"
      :class="{ 'is-revealed': mode === 'view' }"
    >
      <template #suffix>
        <span v-if="mode === 'view'" class="countdown">{{ countdown }}s</span>
        <el-icon class="icon-btn" :title="mode === 'view' ? '隐藏' : '查看'" @click="handleToggleView">
          <Hide v-if="mode === 'view'" />
          <View v-else />
        </el-icon>
        <el-icon class="icon-btn" title="修改" style="margin-left:6px" @click="openEdit">
          <EditPen />
        </el-icon>
      </template>
    </el-input>

    <!-- 身份验证弹窗 -->
    <el-dialog v-model="authVisible" title="查看敏感配置" width="360px" append-to-body :close-on-click-modal="false">
      <p class="dlg-tip">需要输入管理员登录密码以查看此配置项。</p>
      <el-input
        ref="authInputRef"
        v-model="authPwd"
        type="password"
        show-password
        placeholder="登录密码"
        @keyup.enter="doVerify"
      />
      <template #footer>
        <el-button @click="authVisible = false">取消</el-button>
        <el-button type="primary" :loading="verifying" @click="doVerify">验证并查看</el-button>
      </template>
    </el-dialog>

    <!-- 修改值弹窗 -->
    <el-dialog v-model="editVisible" title="修改配置值" width="400px" append-to-body>
      <p class="dlg-tip">输入新值后点击确认，然后点击页面"保存配置"生效。</p>
      <el-input
        v-model="editVal"
        type="password"
        show-password
        placeholder="请输入新值"
        @keyup.enter="confirmEdit"
      />
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmEdit">确认修改</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { View, Hide, EditPen } from '@element-plus/icons-vue'
import { verifyAndRevealSecret } from '../api/index.js'

const props = defineProps({
  modelValue: { type: String, default: '' },
  configPath: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue'])

const mode = ref('hidden')
const actualValue = ref('')
const countdown = ref(0)
let timer = null

const displayValue = computed(() =>
  mode.value === 'view' ? actualValue.value : (props.modelValue || '****')
)

// ── 查看 ──
const authVisible = ref(false)
const authPwd = ref('')
const verifying = ref(false)

function handleToggleView() {
  if (mode.value === 'view') {
    hideValue()
  } else {
    authPwd.value = ''
    authVisible.value = true
  }
}

async function doVerify() {
  if (!authPwd.value) { ElMessage.warning('请输入密码'); return }
  if (!props.configPath) { ElMessage.error('未指定配置路径，无法验证'); return }
  verifying.value = true
  try {
    const res = await verifyAndRevealSecret(props.configPath, authPwd.value)
    if (res.code === 0) {
      actualValue.value = res.value
      mode.value = 'view'
      authVisible.value = false
      authPwd.value = ''
      startCountdown()
    } else {
      ElMessage.error(res.msg || '验证失败')
    }
  } catch (e) {
    ElMessage.error(e?.response?.data?.msg || e?.message || '验证失败')
  } finally {
    verifying.value = false
  }
}

function startCountdown() {
  clearTimer()
  countdown.value = 30
  timer = setInterval(() => {
    countdown.value--
    if (countdown.value <= 0) hideValue()
  }, 1000)
}

function hideValue() {
  clearTimer()
  mode.value = 'hidden'
  actualValue.value = ''
  countdown.value = 0
}

function clearTimer() {
  if (timer) { clearInterval(timer); timer = null }
}

// ── 修改 ──
const editVisible = ref(false)
const editVal = ref('')

function openEdit() {
  editVal.value = ''
  editVisible.value = true
}

function confirmEdit() {
  if (editVal.value.trim()) {
    emit('update:modelValue', editVal.value.trim())
    ElMessage.success('已更新，请点击"保存配置"使其生效')
  }
  editVisible.value = false
}

onUnmounted(clearTimer)
</script>

<style scoped>
.secret-wrap {
  display: flex;
  align-items: center;
  width: 100%;
}
.secret-wrap .el-input {
  flex: 1;
}
.icon-btn {
  cursor: pointer;
  color: #5a7aac;
  font-size: 15px;
  transition: color 0.2s;
}
.icon-btn:hover {
  color: #4fc3f7;
}
.countdown {
  font-size: 11px;
  color: #ff9800;
  margin-right: 4px;
  font-family: monospace;
  min-width: 24px;
  text-align: right;
}
.dlg-tip {
  font-size: 13px;
  color: #8ba4d4;
  margin-bottom: 12px;
}
</style>
