<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue';
import { useRoute } from 'vue-router';
import { API } from '../api';
import { store } from '../store';

import Button from 'primevue/button';
import DataTable from 'primevue/datatable';
import Column from 'primevue/column';
import Tag from 'primevue/tag';
import ProgressBar from 'primevue/progressbar';
import Dialog from 'primevue/dialog';
import InputText from 'primevue/inputtext';
import Chart from 'primevue/chart';
import Select from 'primevue/select';
import { useToast } from 'primevue/usetoast';

const toast = useToast();
const route = useRoute();

const tasks = ref([]);
const activeTaskId = ref(null);
const activeResult = ref(null);
const activeDetails = ref(null);
const loadingTasks = ref(false);
const loadingResult = ref(false);
const loadingDetails = ref(false);
const filterText = ref('');
const hideNoTradeStocks = ref(false);

const activeTask = computed(() => tasks.value.find(t => t.task_id === activeTaskId.value) || null);

// Filter tasks by name or stock codes
const filteredTasks = computed(() => {
    if (!filterText.value.trim()) return tasks.value;
    const k = filterText.value.toLowerCase();
    return tasks.value.filter(t => 
        t.name.toLowerCase().includes(k) || 
        (t.stock_codes && t.stock_codes.some(code => code.toLowerCase().includes(k)))
    );
});

function fmtNum(val) {
    if (val === undefined || val === null || isNaN(parseFloat(val))) return '0.00';
    return parseFloat(val).toFixed(2);
}

function fmtTime(isoStr) {
    if (!isoStr) return '';
    try {
        const d = new Date(isoStr);
        const y = d.getFullYear();
        const m = (d.getMonth() + 1).toString().padStart(2, '0');
        const day = d.getDate().toString().padStart(2, '0');
        const h = d.getHours().toString().padStart(2, '0');
        const min = d.getMinutes().toString().padStart(2, '0');
        return `${y}-${m}-${day} ${h}:${min}`;
    } catch (e) {
        return isoStr;
    }
}

function fmtCapital(val) {
    if (val === undefined || val === null || isNaN(parseFloat(val))) return '¥0.00';
    const n = parseFloat(val);
    const absN = Math.abs(n);
    if (absN >= 10000) {
        return `¥${(n / 10000).toFixed(2)}万`;
    }
    return `¥${n.toFixed(2)}`;
}

// Stats & Results
const overallCards = computed(() => {
  const s = (activeResult.value && activeResult.value.overall_stats) || {};
  return [
    { label: '完成', value: (s['完成'] || '0'), icon: 'pi pi-check-circle', color: 'text-green-500' },
    { label: '未完成', value: (s['未完成'] || '0'), icon: 'pi pi-clock', color: 'text-blue-500' },
    { label: '完成率', value: (s['完成率'] || '0.00%'), icon: 'pi pi-percentage', color: 'text-purple-500' },
    { label: '平均收益率', value: (s['平均收益率'] || '0.00%'), icon: 'pi pi-chart-line', color: 'text-cyan-500' },
    { label: '平均回撤', value: (s['平均回撤'] || '0.00%'), icon: 'pi pi-arrow-down', color: 'text-orange-500' },
    { label: '平均耗时', value: (s['平均耗时'] || '0天'), icon: 'pi pi-calendar', color: 'text-indigo-500' },
  ];
});

const stockResults = computed(() => {
    let res = (activeResult.value && activeResult.value.stock_results) || [];
    if (hideNoTradeStocks.value) {
        // Filter out stocks with 0 completed AND 0 uncompleted trades
        res = res.filter(s => {
            const completed = parseInt(s['完成交易'] || 0);
            const uncompleted = parseInt(s['未完成交易'] || 0);
            return completed > 0 || uncompleted > 0;
        });
    }
    return res;
});

// Trade Dialog
const tradeDialogVisible = ref(false);
const tradeDialogStock = ref(null);
const tradeRows = ref([]);
const loadingTrades = ref(false);
const tradeActionFilter = ref(null);
const tradeSellReasonFilter = ref(null);

const tradeActionOptions = [
    { label: '全部', value: null },
    { label: '买入', value: 'BUY' },
    { label: '卖出', value: 'SELL' },
];

const tradeSellReasonOptions = computed(() => {
    const reasons = new Set();
    tradeRows.value.forEach(t => {
        if (t.sell_reason) reasons.add(t.sell_reason);
    });
    return [
        { label: '全部', value: null },
        ...Array.from(reasons).sort().map(r => ({ label: r, value: r })),
    ];
});

const filteredTradeRows = computed(() => {
    let rows = tradeRows.value;
    if (tradeActionFilter.value === 'BUY') {
        rows = rows.filter(t => t.action === 'BUY');
    } else if (tradeActionFilter.value === 'SELL') {
        rows = rows.filter(t => t.action !== 'BUY');
    }
    if (tradeSellReasonFilter.value) {
        rows = rows.filter(t => t.sell_reason === tradeSellReasonFilter.value);
    }
    return rows;
});

// Chart Data
const chartData = computed(() => {
    if (!activeDetails.value || !activeDetails.value.daily_stats) return null;
    const stats = activeDetails.value.daily_stats;
    if (stats.length === 0) return null;

    const labels = stats.map(s => (s.date && s.date.includes('T')) ? s.date.split('T')[0] : s.date);
    
    // 获取本次回测涉及的所有股票
    const allStocks = new Set();
    stats.forEach(s => {
        if (s.stock_layers) {
            Object.keys(s.stock_layers).forEach(code => allStocks.add(code));
        }
    });

    const datasets = Array.from(allStocks).map((code, index) => {
        const stockInfo = activeResult.value?.stock_results?.find(r => r['代码'] === code);
        const name = stockInfo ? stockInfo['股票'] : code;
        
        const colors = [
            '#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', 
            '#EC4899', '#06B6D4', '#6366F1', '#14B8A6', '#F97316'
        ];
        const color = colors[index % colors.length];

        return {
            label: name,
            data: stats.map(s => (s.stock_layers && s.stock_layers[code]) || 0),
            borderColor: color,
            borderWidth: 2,
            pointRadius: 0,
            pointHoverRadius: 4,
            fill: false,
            tension: 0.1,
            stepped: true
        };
    });

    return { labels, datasets };
});

const chartOptions = ref({
    maintainAspectRatio: false,
    plugins: {
        legend: {
            position: 'top',
            labels: { boxWidth: 10, fontSize: 10, color: '#666' }
        },
        tooltip: {
            mode: 'index',
            intersect: false,
            padding: 10,
            bodyFont: { size: 11 }
        }
    },
    scales: {
        x: {
            grid: { display: false },
            ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 10, font: { size: 10 } }
        },
        y: {
            title: { display: true, text: '持仓层数', font: { size: 11 } },
            min: 0,
            ticks: {
                stepSize: 1,
                font: { size: 10 }
            },
            grid: { color: '#f0f0f0' }
        }
    },
    interaction: {
        mode: 'index',
        intersect: false
    }
});

// Edit Task Name Dialog
const editDialogVisible = ref(false);
const editTaskId = ref(null);
const editTaskName = ref('');

let refreshInterval = null;

function isOwner(task) {
    return store.isLoggedIn && store.user && task.user_id === store.user.id;
}

function statusSeverity(status) {
    if (status === 'completed') return 'success';
    if (status === 'running') return 'info';
    if (status === 'failed') return 'danger';
    return 'secondary';
}

function statusLabel(status) {
    const map = { completed: '完成', running: '运行中', pending: '等待中', failed: '失败' };
    return map[status] || status;
}

async function refreshTasks() {
  loadingTasks.value = true;
  try {
      const resp = await API.tasks();
      tasks.value = resp.data || [];
      
      // Auto-select: prefer URL query ?id=, otherwise first task
      if (!activeTaskId.value && tasks.value.length) {
          const queryId = route.query.id;
          const match = queryId && tasks.value.find(t => t.task_id === queryId);
          activeTaskId.value = match ? match.task_id : tasks.value[0].task_id;
      }
  } catch (e) {
      console.error(e);
  } finally {
      loadingTasks.value = false;
  }
}

async function loadResult(taskId) {
  if (!taskId) return;
  loadingResult.value = true;
  try {
      const resp = await API.result(taskId);
      activeResult.value = resp.data;
  } catch (e) {
      activeResult.value = null;
      toast.add({ severity: 'error', summary: '加载结果失败', detail: e.message });
  } finally {
      loadingResult.value = false;
  }
}

async function loadDetails(taskId) {
  if (!taskId) return;
  loadingDetails.value = true;
  try {
      const resp = await API.resultDetails(taskId);
      activeDetails.value = resp.data;
  } catch (e) {
      activeDetails.value = null;
      console.error('Failed to load chart details:', e);
  } finally {
      loadingDetails.value = false;
  }
}

async function onTaskSelect(row) {
    if (activeTaskId.value === row.task_id) return;
    activeTaskId.value = row.task_id;
}

async function deleteTask(data, event) {
    event?.stopPropagation?.();
    const id = data?.task_id;
    if (!id) return;
    try {
        await API.deleteTask(id);
        if (activeTaskId.value === id) activeTaskId.value = null;
        await refreshTasks();
        toast.add({ severity: 'success', summary: '已删除', detail: '任务已删除。' });
    } catch (e) {
        toast.add({ severity: 'error', summary: '删除失败', detail: e.message });
    }
}

function openEditDialog(data, event) {
    event?.stopPropagation?.();
    editTaskId.value = data.task_id;
    editTaskName.value = data.name || '';
    editDialogVisible.value = true;
}

async function saveTaskName() {
    if (!editTaskId.value || !editTaskName.value.trim()) return;
    try {
        await API.updateTask(editTaskId.value, { name: editTaskName.value.trim() });
        editDialogVisible.value = false;
        await refreshTasks();
        toast.add({ severity: 'success', summary: '已保存', detail: '任务名称已更新。' });
    } catch (e) {
        toast.add({ severity: 'error', summary: '保存失败', detail: e.message });
    }
}

// Watch active task to load results if completed
watch(activeTaskId, async (newId) => {
    activeResult.value = null;
    activeDetails.value = null;
    const t = tasks.value.find(x => x.task_id === newId);
    if (t && (t.status === 'completed' || t.status === 'failed')) {
        await loadResult(newId);
        if (t.status === 'completed') {
            await loadDetails(newId);
        }
    }
});

// Watch tasks update to auto-reload result if status changes to completed
watch(tasks, (newTasks) => {
    if (!activeTaskId.value) return;
    const t = newTasks.find(x => x.task_id === activeTaskId.value);
    if (t && t.status === 'completed' && !activeResult.value && !loadingResult.value) {
        loadResult(activeTaskId.value);
        loadDetails(activeTaskId.value);
    }
}, { deep: true });

function getTradeDialogHeader() {
    if (!tradeDialogStock.value) return '交易明细';
    const stock = tradeDialogStock.value;
    const total = tradeRows.value.length;
    const shown = filteredTradeRows.value.length;
    const countStr = shown < total ? `${shown}/${total}笔` : `${total}笔`;
    
    let dateRange = '';
    if (total > 0) {
        const dates = tradeRows.value.map(t => t.date).filter(d => d);
        if (dates.length > 0) {
            const sortedDates = [...dates].sort();
            dateRange = ` (${sortedDates[0]} ~ ${sortedDates[sortedDates.length - 1]})`;
        }
    }
    
    return `${stock['股票'] || stock.stock_name || ''} (${stock['代码'] || stock.code || ''}) - 交易明细 [${countStr}]${dateRange}`;
}

// 判断买入交易是否未完成（即没有对应的卖出）
function isUncompletedBuy(trade, allTrades) {
    if (trade.action !== 'BUY') return false;
    
    // 查找是否有对应层级的卖出
    const buyDate = trade.date;
    const layerIndex = trade.layer_index;
    
    const hasSell = allTrades.some(t => 
        (t.action === 'SELL_LAYER' || t.action === 'SELL_ALL') &&
        t.buy_date === buyDate &&
        t.layer_index === layerIndex
    );
    
    return !hasSell;
}

function getTradeRowClass(data) {
    if (data.action === 'BUY') {
        // 检查是否未完成
        if (isUncompletedBuy(data, tradeRows.value)) {
            return 'uncompleted-buy-row';
        }
    }
    return '';
}

async function openTrades(row) {
  const code = (row['代码'] || row.code || '').toString();
  tradeDialogStock.value = row;
  tradeRows.value = [];
  tradeActionFilter.value = null;
  tradeSellReasonFilter.value = null;
  tradeDialogVisible.value = true;
  loadingTrades.value = true;
  
  if (!activeTaskId.value || !code) return;
  
  try {
      const resp = await API.trades(activeTaskId.value, code);
      // 按日期倒序排序，最新交易在最前面
      const trades = resp.data || [];
      tradeRows.value = trades.sort((a, b) => {
          const dateA = new Date(a.date);
          const dateB = new Date(b.date);
          return dateB - dateA; // 倒序
      });
  } catch (e) {
      toast.add({ severity: 'error', summary: '加载交易明细失败', detail: e.message });
  } finally {
      loadingTrades.value = false;
  }
}

onMounted(() => {
    refreshTasks();
    refreshInterval = setInterval(refreshTasks, 3000);
});

onUnmounted(() => {
    if (refreshInterval) clearInterval(refreshInterval);
});
</script>

<template>
  <!-- Main View Container: fixed height to allow internal scrolling -->
  <div class="view-container" style="height: calc(100vh - 120px); overflow: hidden; padding: 0.5rem 1rem;">
      <div class="grid h-full" style="margin: 0; align-items: stretch;">
          <!-- Left: Task List -->
          <div class="col-12 lg:col-4 h-full">
              <div class="gh-card h-full flex flex-column overflow-hidden">
                  <div class="gh-card-header flex align-items-center justify-content-between shrink-0">
                      <span class="font-bold">回测任务列表</span>
                      <Button icon="pi pi-refresh" text rounded size="small" @click="refreshTasks" :loading="loadingTasks" />
                  </div>
                  
                  <!-- Filter Search -->
                  <div class="p-2 border-bottom-1 border-200 bg-50 shrink-0">
                      <span class="p-input-icon-left w-full">
                          <i class="pi pi-search text-xs" />
                          <InputText v-model="filterText" placeholder="搜索股票代码或任务名..." class="w-full text-xs p-2" />
                      </span>
                  </div>

                  <div class="gh-card-body flex-1 overflow-auto p-0">
                      <div v-if="!filteredTasks.length" class="p-4 text-center text-500 text-xs">暂无符合条件的任务</div>
                      <div v-for="t in filteredTasks" :key="t.task_id" 
                           class="task-item" :class="{ 'active': activeTaskId === t.task_id }"
                           @click="onTaskSelect(t)">
                          <div class="task-item-indicator"></div>
                          <div class="task-item-content">
                              <div class="flex align-items-center justify-content-between mb-1">
                                  <div class="task-item-name">{{ t.name }}</div>
                                  <div class="task-item-actions" v-if="isOwner(t)">
                                      <Button icon="pi pi-pencil" text rounded size="small" severity="secondary" @click.stop="openEditDialog(t, $event)" />
                                      <Button icon="pi pi-trash" text rounded size="small" severity="danger" @click.stop="deleteTask(t, $event)" />
                                  </div>
                              </div>
                              <div class="flex align-items-center gap-2 mb-1">
                                  <Tag :value="statusLabel(t.status)" :severity="statusSeverity(t.status)" class="text-xs px-1" />
                                  <Tag v-if="t.is_public" value="公开" severity="info" class="text-xs px-1" />
                                  <Tag v-else-if="isOwner(t)" value="私有" severity="secondary" class="text-xs px-1" />
                                  <span class="text-xs text-400 font-mono">{{ fmtTime(t.created_at) }}</span>
                              </div>
                              <div class="flex align-items-center justify-content-between text-xs">
                                  <span class="text-500">{{ t.start_date }} ~ {{ t.end_date }}</span>
                                  <span class="text-400 font-mono">{{ t.stock_codes?.length || 0 }} 股</span>
                              </div>
                          </div>
                      </div>
                  </div>
              </div>
          </div>
          
          <!-- Right: Results Area -->
          <div class="col-12 lg:col-8 h-full">
               <div class="gh-card h-full flex flex-column overflow-hidden">
                   <div class="gh-card-header shrink-0">回测统计结果详情</div>
                   <div class="gh-card-body flex-1 overflow-auto p-0">
                       <!-- Empty State: no task selected -->
                       <div v-if="!activeTask" class="flex flex-column align-items-center justify-content-center py-8 text-500">
                           <i class="pi pi-chart-bar text-4xl mb-3"></i>
                           <div class="text-lg">请从左侧选择一个回测任务</div>
                       </div>
                       
                       <!-- Failed State (before results check so it always shows) -->
                       <div v-else-if="activeTask.status === 'failed'" class="flex flex-column align-items-center justify-content-center py-8 text-red-500">
                           <i class="pi pi-exclamation-triangle text-4xl mb-3"></i>
                           <div class="text-xl font-bold">回测执行失败</div>
                           <div class="mt-2">{{ activeTask.message || '未知错误' }}</div>
                       </div>

                       <!-- Pending / Running State -->
                       <div v-else-if="activeTask.status !== 'completed'" class="flex flex-column align-items-center justify-content-center py-8">
                            <i v-if="activeTask.status === 'running'" class="pi pi-spin pi-spinner text-4xl mb-3 text-primary"></i>
                            <i v-else class="pi pi-clock text-4xl mb-3 text-500"></i>
                            <div class="text-xl font-medium mb-3">{{ statusLabel(activeTask.status) }}...</div>
                            <ProgressBar v-if="activeTask.status === 'running'" :value="activeTask.progress || 0" style="width: 300px; height: 10px" />
                            <div class="text-sm text-500 mt-3">{{ activeTask.message || '正在准备计算数据' }}</div>
                       </div>

                       <!-- Loading Result (completed but result not fetched yet) -->
                       <div v-else-if="loadingResult || !activeResult" class="flex flex-column align-items-center justify-content-center py-8">
                            <i class="pi pi-spin pi-spinner text-4xl mb-3 text-primary"></i>
                            <div class="text-lg text-500">正在加载回测结果...</div>
                       </div>
                       
                       <!-- Results Display -->
                       <div v-else>
                            <!-- Strategy Details Fallback for old tasks -->
                            <div class="p-3 border-bottom-1 border-200" v-if="!activeTask.strategy">
                                <div class="font-bold text-sm mb-1 text-800">策略信息</div>
                                <div class="text-sm text-600 italic">
                                    历史任务，未记录详细策略参数。
                                </div>
                            </div>
                            <!-- Summary Cards -->
                            <div class="p-3">
                                <div class="grid mb-4">
                               <div class="col-6 md:col-3" v-for="item in overallCards" :key="item.label">
                                   <div class="surface-card p-3 border-1 border-200 border-round h-full flex flex-column justify-content-between overflow-hidden">
                                       <div class="text-500 font-medium text-xs mb-2 white-space-nowrap">{{ item.label }}</div>
                                       <div class="text-lg font-bold flex align-items-center gap-2 text-overflow-ellipsis overflow-hidden white-space-nowrap" :title="item.value">
                                            <i :class="item.icon + ' ' + item.color" class="text-sm"></i>
                                            {{ item.value }}
                                   </div>
                                   </div>
                               </div>
                           </div>

                           <!-- Equity Curve Chart -->
                           <div v-if="stockResults.length <= 5" class="surface-card p-3 border-round mb-4 border-1 border-200">
                               <div class="flex align-items-center justify-content-between mb-3">
                                   <div class="font-bold text-sm text-800 flex align-items-center">
                                       <i class="pi pi-chart-line mr-2 text-primary"></i>资产净值曲线 (含交易点)
                                   </div>
                               </div>
                               <div style="height: 300px">
                                   <div v-if="loadingDetails" class="flex flex-column align-items-center justify-content-center h-full text-500">
                                       <i class="pi pi-spin pi-spinner text-2xl mb-2"></i>
                                       <span class="text-xs">加载曲线数据...</span>
                                   </div>
                                   <Chart v-else-if="chartData" type="line" :data="chartData" :options="chartOptions" style="height: 100%" />
                                   <div v-else class="flex align-items-center justify-content-center h-full text-400 text-xs">
                                       无曲线数据
                                   </div>
                               </div>
                           </div>
                                <!-- Stock Table -->
                                <DataTable :value="stockResults" dataKey="代码" paginator :rows="10" :rowsPerPageOptions="[10, 20, 50, 100]" size="small" stripedRows tableStyle="min-width: 50rem"
                                           selectionMode="single" @row-select="e => openTrades(e.data)">
                                    <template #header>
                                        <div class="flex align-items-center justify-content-between">
                                            <span class="text-xs text-500">点击行查看交易明细</span>
                                            <Button :icon="hideNoTradeStocks ? 'pi pi-filter-fill' : 'pi pi-filter'" 
                                                    :label="hideNoTradeStocks ? '显示全部' : '过滤无交易股'"
                                                    size="small" text :severity="hideNoTradeStocks ? 'primary' : 'secondary'"
                                                    class="text-xs py-1"
                                                    @click="hideNoTradeStocks = !hideNoTradeStocks" />
                                        </div>
                                    </template>
                                    <Column field="股票" header="股票" frozen>
                                        <template #body="{ data }">
                                            <div class="font-medium text-sm">{{ data['股票'] }}</div>
                                            <div class="text-xs text-500 font-mono">{{ data['代码'] }}</div>
                                        </template>
                                    </Column>
                                    <Column field="总收益率" header="收益率" sortable>
                                         <template #body="{ data }">
                                            <span :class="parseFloat(data['总收益率']) >= 0 ? 'text-green-500' : 'text-red-500'" class="font-bold">
                                                {{ data['总收益率'] || '0.00%' }}
                                            </span>
                                        </template>
                                    </Column>
                                    <Column field="最大回撤" header="最大回撤" sortable>
                                        <template #body="{ data }">
                                            <span class="text-orange-500 font-bold">{{ data['最大回撤'] || '0.00%' }}</span>
                                        </template>
                                    </Column>
                                    <Column field="回测胜率" header="胜率" sortable></Column>
                                    <Column field="完成交易" header="完成交易" sortable></Column>
                                    <Column field="未完成交易" header="未完成交易" sortable></Column>
                                    <Column field="单笔均益" header="单笔均益" sortable></Column>
                                    <Column field="平均时间" header="平均耗时" sortable></Column>
                                </DataTable>
                            </div>
                       </div>
                   </div>
               </div>
          </div>
      </div>
      
      <!-- Trade Dialog -->
      <Dialog v-model:visible="tradeDialogVisible" 
              :header="getTradeDialogHeader()" 
              modal :style="{ width: '1300px', maxWidth: '95vw' }" class="p-fluid">
          <ProgressBar v-if="loadingTrades" mode="indeterminate" style="height: 4px" class="mb-3" />
          <DataTable v-else :value="filteredTradeRows" paginator :rows="15" size="small" stripedRows scrollable scrollHeight="60vh"
                     :rowClass="getTradeRowClass"
                     sortField="date" :sortOrder="-1">
             <template #empty>暂无交易记录</template>
             <template #header>
                 <div class="flex align-items-center justify-content-between flex-wrap gap-2">
                     <span class="text-xs text-500">最新交易在最前 (点击列标题可排序)</span>
                     <div class="flex align-items-center gap-2">
                         <Select v-model="tradeActionFilter" :options="tradeActionOptions" optionLabel="label" optionValue="value"
                                 placeholder="方向" class="text-xs" style="min-width: 90px; height: 28px;" />
                         <Select v-model="tradeSellReasonFilter" :options="tradeSellReasonOptions" optionLabel="label" optionValue="value"
                                 placeholder="卖出条件" class="text-xs" style="min-width: 160px; height: 28px;" />
                     </div>
                 </div>
             </template>

             <!-- ===== 基础交易信息 ===== -->
             <Column field="date" header="日期" sortable style="min-width: 95px" frozen></Column>
             <Column field="action" header="方向" style="min-width: 60px">
                 <template #body="{ data }">
                     <Tag :value="data.action === 'BUY' ? '买入' : (data.action.includes('SELL') ? '卖出' : data.action)" 
                          :severity="data.action === 'BUY' ? 'success' : 'danger'" class="text-xs" />
                 </template>
             </Column>
             <Column field="sell_reason" header="卖出条件" style="min-width: 130px">
                 <template #body="{ data }">
                     <span v-if="data.sell_reason" class="text-xs font-medium">
                         <Tag :value="data.sell_reason" severity="warn" class="text-xs" style="white-space: nowrap;" />
                     </span>
                     <span v-else class="text-400">-</span>
                 </template>
             </Column>
             <Column field="price" header="成交价" style="min-width: 75px">
                 <template #body="{ data }">{{ fmtNum(data.price) }}</template>
             </Column>
             <Column field="target_price" header="目标价" style="min-width: 75px">
                 <template #body="{ data }">
                     <span v-if="data.action === 'BUY' && data.target_price" class="text-green-600 font-semibold">
                         {{ fmtNum(data.target_price) }}
                     </span>
                     <span v-else class="text-400">-</span>
                 </template>
             </Column>
             <Column field="shares" header="数量" style="min-width: 65px"></Column>

             <!-- ===== 策略参考指标 ===== -->
             <Column field="ma120" header="120线" style="min-width: 75px">
                 <template #body="{ data }">
                     <span v-if="data.ma120">{{ fmtNum(data.ma120) }}</span>
                     <span v-else class="text-400">-</span>
                 </template>
             </Column>
             <Column field="price_ma120_pct" header="价/120线%" style="min-width: 80px">
                 <template #body="{ data }">
                     <span v-if="data.price_ma120_pct" :class="data.price_ma120_pct < 90 ? 'text-green-500 font-bold' : (data.price_ma120_pct > 110 ? 'text-red-500 font-bold' : '')">
                         {{ fmtNum(data.price_ma120_pct) }}%
                     </span>
                     <span v-else class="text-400">-</span>
                 </template>
             </Column>
             <Column field="discount_ma120" header="折价率" style="min-width: 70px">
                 <template #body="{ data }">
                     <span v-if="data.discount_ma120 !== undefined && data.discount_ma120 !== null && data.discount_ma120 !== 0"
                           :class="data.discount_ma120 < 0 ? 'text-green-500 font-bold' : 'text-red-500 font-bold'">
                         {{ data.discount_ma120 > 0 ? '+' : '' }}{{ fmtNum(data.discount_ma120) }}%
                     </span>
                     <span v-else class="text-400">-</span>
                 </template>
             </Column>
             <Column field="atr_pct" header="ATR%" style="min-width: 65px">
                 <template #body="{ data }">
                     <span v-if="data.atr_pct">{{ fmtNum(data.atr_pct) }}%</span>
                     <span v-else class="text-400">-</span>
                 </template>
             </Column>
             <Column field="volume_ratio" header="量比" style="min-width: 55px">
                 <template #body="{ data }">
                     <span v-if="data.volume_ratio" :class="data.volume_ratio > 2 ? 'text-orange-500 font-bold' : ''">
                         {{ fmtNum(data.volume_ratio) }}
                     </span>
                     <span v-else class="text-400">-</span>
                 </template>
             </Column>

             <!-- ===== 环境参考 ===== -->
             <Column field="index_price" header="上证指数" style="min-width: 85px">
                 <template #body="{ data }">
                     <span v-if="data.index_price">{{ fmtNum(data.index_price) }}</span>
                     <span v-else class="text-400">-</span>
                 </template>
             </Column>
             <!-- ===== 盈亏结果 ===== -->
             <Column field="profit_amount" header="本笔盈亏" style="min-width: 85px">
                 <template #body="{ data }">
                     <!-- 已完成交易的盈亏 -->
                     <span v-if="data.profit_amount !== undefined && data.profit_amount !== null" :class="data.profit_amount > 0 ? 'text-green-500' : (data.profit_amount < 0 ? 'text-red-500' : '')" class="font-bold">
                         {{ fmtNum(data.profit_amount) }}
                     </span>
                     <!-- 未完成买入的浮动盈亏 -->
                     <span v-else-if="data.action === 'BUY' && data.uncompleted_profit !== undefined && data.uncompleted_profit !== null" 
                           :class="data.uncompleted_profit > 0 ? 'text-orange-500' : 'text-orange-600'" 
                           class="font-semibold"
                           :title="`回测结束时价格: ${fmtNum(data.uncompleted_price || 0)}`">
                         {{ fmtNum(data.uncompleted_profit) }}
                     </span>
                     <span v-else class="text-400">-</span>
                 </template>
             </Column>
             <Column field="profit_rate" header="收益率" style="min-width: 70px">
                 <template #body="{ data }">
                     <!-- 已完成交易的收益率 -->
                     <span v-if="data.profit_rate !== undefined && data.profit_rate !== null" :class="data.profit_rate > 0 ? 'text-green-500' : (data.profit_rate < 0 ? 'text-red-500' : '')" class="font-bold">
                        {{ (data.profit_rate * 100).toFixed(2) }}%
                     </span>
                     <!-- 未完成买入的浮动收益率 -->
                     <span v-else-if="data.action === 'BUY' && data.uncompleted_profit_rate !== undefined && data.uncompleted_profit_rate !== null" 
                           :class="data.uncompleted_profit_rate > 0 ? 'text-orange-500' : 'text-orange-600'" 
                           class="font-semibold">
                        {{ (data.uncompleted_profit_rate * 100).toFixed(2) }}%
                     </span>
                     <span v-else class="text-400">-</span>
                 </template>
             </Column>
             <Column field="holding_days" header="耗时" style="min-width: 60px">
                 <template #body="{ data }">
                     <span v-if="data.holding_days !== undefined && data.holding_days !== null">{{ data.holding_days }}天</span>
                     <span v-else class="text-400">-</span>
                 </template>
             </Column>
          </DataTable>
      </Dialog>
      
      <!-- Edit Task Name Dialog -->
      <Dialog v-model:visible="editDialogVisible" header="编辑任务名称" modal :style="{ width: '400px' }">
          <div class="p-fluid">
              <InputText v-model="editTaskName" placeholder="请输入任务名称" class="w-full" autofocus />
          </div>
          <template #footer>
              <Button label="取消" severity="secondary" text @click="editDialogVisible = false" />
              <Button label="保存" @click="saveTaskName" />
          </template>
      </Dialog>
  </div>
</template>

<style scoped>
.task-list-wrapper {
    background: #fff;
}
.task-item {
    display: flex;
    padding: 12px 16px;
    border-bottom: 1px solid #f0f0f0;
    cursor: pointer;
    transition: all 0.2s;
    position: relative;
    user-select: none;
}
.task-item:hover {
    background-color: #f8fafc;
}
.task-item.active {
    background-color: #f1f5f9;
}
.task-item-indicator {
    position: absolute;
    left: 0;
    top: 0;
    bottom: 0;
    width: 3px;
    background-color: transparent;
}
.task-item.active .task-item-indicator {
    background-color: #2563eb;
}
.task-item-content {
    flex: 1;
    min-width: 0;
}
.task-item-name {
    font-weight: 600;
    font-size: 0.875rem;
    color: #1e293b;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.task-item-actions {
    display: flex;
    gap: 4px;
    opacity: 0;
    transition: opacity 0.2s;
}
.task-item:hover .task-item-actions {
    opacity: 1;
}
.task-delete-btn, .task-edit-btn {
    opacity: 0.7;
}
.task-delete-btn:hover, .task-edit-btn:hover {
    opacity: 1;
}

/* 交易明细表格行样式 - 未完成的买入 */
:deep(.uncompleted-buy-row) {
    background-color: rgba(251, 146, 60, 0.08) !important;
    border-left: 3px solid #f97316;
}

:deep(.uncompleted-buy-row:hover) {
    background-color: rgba(251, 146, 60, 0.12) !important;
}
</style>
