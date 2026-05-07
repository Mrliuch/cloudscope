<template>
  <div class="page">
    <div class="toolbar">
      <span class="page-title">账户余额</span>
      <el-button size="small" :loading="loading" @click="loadData" style="margin-left:auto">
        <el-icon v-if="!loading"><Refresh /></el-icon>
        {{ loading ? '获取中...' : '刷新余额' }}
      </el-button>
    </div>

    <div v-loading="loading"
         element-loading-text="正在实时获取各云账号余额，请稍候..."
         element-loading-background="rgba(6,14,31,0.8)">

    <!-- KPI 汇总 -->
    <div class="kpi-row">
      <div class="kpi-card">
        <div class="kpi-value">{{ fmtMoney(totalAvailable) }}</div>
        <div class="kpi-label">实际可用合计（元）</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-value">{{ fmtMoney(totalCash) }}</div>
        <div class="kpi-label">现金余额合计（元）</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-value">{{ fmtMoney(totalCredit) }}</div>
        <div class="kpi-label">授信额度合计（元）</div>
      </div>
      <div class="kpi-card" v-if="totalOwe > 0">
        <div class="kpi-value owe">{{ fmtMoney(totalOwe) }}</div>
        <div class="kpi-label">欠费合计（元）</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-value">{{ fmtMoney(totalCoupon) }}</div>
        <div class="kpi-label">代金券合计（元）</div>
      </div>
    </div>

    <!-- 账号余额卡片 -->
    <div class="cards-row">
      <div class="balance-card" v-for="b in balances" :key="b.cloud"
        :style="{ borderColor: providerColor(b.provider) }">
        <div class="card-header">
          <span class="cloud-name">{{ b.cloud }}</span>
          <el-tag :color="providerColor(b.provider)" effect="dark" size="small">
            {{ providerLabel(b.provider) }}
          </el-tag>
        </div>
        <div class="card-body">
          <div class="balance-item available">
            <span class="balance-label">实际可用</span>
            <span class="balance-value">{{ fmtMoney(b.available_amount) }}</span>
          </div>
          <div class="balance-item cash">
            <span class="balance-label">现金余额</span>
            <span class="balance-value">{{ fmtMoney(b.cash_balance) }}</span>
          </div>
          <div class="balance-item credit">
            <span class="balance-label">授信额度</span>
            <span class="balance-value">{{ fmtMoney(b.credit_limit) }}</span>
          </div>
          <div class="balance-item owe" v-if="b.owe_amount > 0">
            <span class="balance-label">欠费金额</span>
            <span class="balance-value">{{ fmtMoney(b.owe_amount) }}</span>
          </div>
          <div class="balance-item coupon">
            <span class="balance-label">代金券</span>
            <span class="balance-value">{{ fmtMoney(b.coupon_amount) }}</span>
          </div>
        </div>
      </div>

      <div v-if="balances.length === 0 && !loading" class="empty-hint">
        暂无余额数据
      </div>
    </div>

    </div><!-- end v-loading wrapper -->
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { getBalance } from '../api/index.js'

const balances = ref([])
const loading = ref(false)

const totalCash = computed(() => balances.value.reduce((s, b) => s + b.cash_balance, 0))
const totalCredit = computed(() => balances.value.reduce((s, b) => s + b.credit_limit, 0))
const totalCoupon = computed(() => balances.value.reduce((s, b) => s + b.coupon_amount, 0))
const totalOwe = computed(() => balances.value.reduce((s, b) => s + (b.owe_amount || 0), 0))
const totalAvailable = computed(() => balances.value.reduce((s, b) => s + (b.available_amount || 0), 0))

const PROVIDER_MAP = { aliyun: '阿里云', huawei: '华为云', tencent: '腾讯云', volcengine: '火山云' }
const PROVIDER_COLORS = { aliyun: '#ff6a00', huawei: '#cf0a2c', tencent: '#006eff', volcengine: '#3370ff' }

function providerLabel(p) { return PROVIDER_MAP[p] || p }
function providerColor(p) { return PROVIDER_COLORS[p] || '#4fc3f7' }

function fmtMoney(v) {
  if (v == null) return '-'
  return Number(v).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

async function loadData() {
  loading.value = true
  try {
    const res = await getBalance()
    if (res.code === 0) balances.value = res.data || []
  } catch {} finally {
    loading.value = false
  }
}

onMounted(loadData)
</script>

<style scoped>
.page { min-height: 100vh; background: #060e1f; }
.toolbar {
  display: flex; align-items: center; padding: 14px 24px;
  background: rgba(10,22,40,0.8); border-bottom: 1px solid rgba(79,195,247,0.1);
}
.page-title { font-size: 16px; font-weight: 600; color: #4fc3f7; }

.kpi-row { display: flex; gap: 16px; padding: 16px 24px; }
.kpi-card {
  flex: 1; text-align: center; padding: 20px;
  background: linear-gradient(135deg, rgba(21,101,192,0.25), rgba(79,195,247,0.08));
  border: 1px solid rgba(79,195,247,0.2);
  border-radius: 10px;
}
.kpi-value { font-size: 36px; font-weight: 700; color: #4fc3f7; text-shadow: 0 0 12px rgba(79,195,247,0.4); }
.kpi-label { font-size: 13px; color: #8ba4d4; margin-top: 4px; }

.cards-row {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
  gap: 16px;
  padding: 0 24px 24px;
}

.balance-card {
  background: rgba(10,22,40,0.7);
  border: 1px solid rgba(79,195,247,0.15);
  border-left: 3px solid #4fc3f7;
  border-radius: 8px;
  padding: 20px;
  transition: border-color 0.2s;
}
.balance-card:hover { border-color: rgba(79,195,247,0.4); }

.card-header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 18px;
}
.cloud-name { font-size: 16px; font-weight: 600; color: #c8d8f0; }

.card-body { display: flex; gap: 24px; flex-wrap: wrap; }
.balance-item { display: flex; flex-direction: column; gap: 4px; }
.balance-label { font-size: 12px; color: #5a7aac; }
.balance-value { font-size: 20px; font-weight: 700; }
.balance-item.available .balance-value { color: #4fc3f7; }
.balance-item.cash .balance-value { color: #66bb6a; }
.balance-item.credit .balance-value { color: #29b6f6; }
.balance-item.coupon .balance-value { color: #ffa726; }
.balance-item.owe .balance-value { color: #ef5350; }

.kpi-value.owe { color: #ef5350; text-shadow: 0 0 12px rgba(239,83,80,0.4); }

.empty-hint {
  grid-column: 1 / -1;
  text-align: center;
  padding: 64px 0;
  color: #4a6080;
  font-size: 14px;
}
</style>
