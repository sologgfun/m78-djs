<script setup>
import { ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { API } from '../api';
import { store } from '../store';
import StockSelector from '../components/StockSelector.vue';

import Button from 'primevue/button';
import InputText from 'primevue/inputtext';
import InputNumber from 'primevue/inputnumber';
import DatePicker from 'primevue/datepicker';
import SelectButton from 'primevue/selectbutton';
import Slider from 'primevue/slider';
import ToggleSwitch from 'primevue/toggleswitch';
import { useToast } from 'primevue/usetoast';

const router = useRouter();
const toast = useToast();
const loading = ref(false);
const isPublic = ref(false);

const modeOptions = ref([
    { label: '自选股回测', value: 'manual' },
    { label: '条件选股回测', value: 'auto_screen' }
]);
const mode = ref('manual');

// ---- 条件选股：股票 / ETF 切换 ----
const screenType = ref('stock'); // 'stock' | 'etf'
const screenTypeOptions = ref([
    { label: '股票筛选', value: 'stock' },
    { label: 'ETF 筛选', value: 'etf' }
]);

const screenParams = ref({
    pe_max: 20,
    dividend_min: 3,
    market_cap_min: 0,
    etf_keyword: ''
});

// ETF 领域快捷标签
const etfQuickTags = [
    '沪深300', '中证500', '中证1000', '创业板', '科创50', '上证50',
    '半导体', '芯片', '医药', '新能源', '光伏', '军工',
    '银行', '证券', '白酒', '消费', '红利', '煤炭',
    '黄金', '纳斯达克', '恒生科技', '标普500', '日经',
    '债券', '国债',
];

const form = ref({
  name: '我的回测任务',
  startDate: new Date('2015-01-01'),
  endDate: new Date('2025-12-31'),
  initialCapital: 10, // 默认 10万 (每只独立)
  maxPositions: 5,
});

// Auto-adjust capital when mode changes
watch(mode, (newMode) => {
    // 无论是手选还是自动，默认都给 10 万单股资金
    form.value.initialCapital = 10;
});

// ---- 策略参数 ----
const positionUnit = ref('percent'); // 'percent' | 'amount'
const unitOptions = ref([
    { label: '%', value: 'percent' },
    { label: '¥', value: 'amount' }
]);

const strategy = ref({
  entryThreshold: 88,
  ladders: [
    { price: 88, fund: 10 },
    { price: 80, fund: 20 },
    { price: 70, fund: 30 },
    { price: 60, fund: 40 },
  ],
  singleLayerProfit: 12,
  fullClearThreshold: 112,
});

// Watch unit change to convert values approximately (optional user convenience)
watch(positionUnit, (newUnit) => {
    const cap = form.value.initialCapital || 100; // in Wan
    if (newUnit === 'amount') {
        // % -> ¥ (Wan)
        strategy.value.ladders.forEach(l => l.fund = parseFloat((l.fund / 100 * cap).toFixed(2)));
    } else {
        // ¥ (Wan) -> %
        strategy.value.ladders.forEach(l => l.fund = parseFloat((l.fund / cap * 100).toFixed(1)));
    }
});

const addLadder = () => {
    strategy.value.ladders.push({ price: 70, fund: positionUnit.value === 'percent' ? 10 : 1 }); // Default 1万 in amount mode
};

const removeLadder = (idx) => {
  strategy.value.ladders.splice(idx, 1);
};

const fmt = (d) => {
    if (!d) return '';
    if (typeof d === 'string') return d;
    return d.toISOString().split('T')[0];
};

async function createTask() {
    if (mode.value === 'manual' && store.selectedList.length === 0) {
        toast.add({ severity: 'error', summary: '未选择股票', detail: '请至少添加一只股票进行回测。', life: 3000 });
        return;
    }
    // ETF 条件选股：关键词为空时提示
    if (mode.value === 'auto_screen' && screenType.value === 'etf' && !screenParams.value.etf_keyword.trim()) {
        toast.add({ severity: 'warn', summary: '未输入关键词', detail: '将返回全部 ETF，数量可能较多。如需缩小范围请输入领域关键词。', life: 4000 });
    }

    loading.value = true;
    try {
        const s = strategy.value;
        const cap = form.value.initialCapital;

        const ladders = s.ladders.map(l => {
            let fundRatio = 0;
            if (positionUnit.value === 'percent') {
                fundRatio = l.fund / 100;
            } else {
                // l.fund is in "万", cap is in "万", so ratio is correct
                fundRatio = l.fund / cap;
            }
            return [l.price / 100, fundRatio];
        });

        const payload = {
            name: form.value.name,
            start_date: fmt(form.value.startDate),
            end_date: fmt(form.value.endDate),
            max_positions: form.value.maxPositions,
            
            mode: mode.value,
            screen_params: mode.value === 'auto_screen'
                ? { ...screenParams.value, screen_type: screenType.value }
                : {},
            stock_codes: mode.value === 'manual' ? store.selectedList.map(s => s.code) : [],

            strategy: {
                entry_threshold: s.entryThreshold / 100,
                ladder_down: ladders,
                single_layer_profit: s.singleLayerProfit / 100,
                full_clear_threshold: s.fullClearThreshold / 100,
            },
            is_public: isPublic.value,
        };

        const resp = await API.createBacktest(payload);
        toast.add({ severity: 'success', summary: '创建成功', detail: '回测任务已开始。' });
        router.push(`/?id=${resp.task_id}`);
    } catch (e) {
        toast.add({ severity: 'error', summary: '创建失败', detail: e.message });
    } finally {
        loading.value = false;
    }
}
</script>

<template>
  <div class="container-narrow">
      <!-- Header -->
      <div class="mb-4 pb-3 border-bottom-1 border-200">
          <h2 class="text-xl font-normal m-0 mb-1">新建回测任务</h2>
          <div class="text-500 text-sm">创建一个新的回测策略，包含股票池选择与参数配置。</div>
      </div>

      <div class="grid">
          <div class="col-12">
              <!-- Mode Selection -->
              <div class="mb-4 text-center">
                  <SelectButton v-model="mode" :options="modeOptions" optionLabel="label" optionValue="value" />
              </div>

              <!-- Step 1: Stocks (Manual) -->
               <div class="gh-card mb-4" v-if="mode === 'manual'">
                   <div class="gh-card-header">1. 选择股票</div>
                   <div class="gh-card-body">
                       <StockSelector />
                   </div>
               </div>

               <!-- Step 1: Screening (Auto) -->
               <div class="gh-card mb-4" v-if="mode === 'auto_screen'">
                   <div class="gh-card-header flex align-items-center justify-content-between">
                       <span>1. 筛选条件</span>
                       <SelectButton v-model="screenType" :options="screenTypeOptions"
                                     optionLabel="label" optionValue="value" class="tiny-select" />
                   </div>
                   <div class="gh-card-body">
                       <!-- 股票筛选 -->
                       <div v-if="screenType === 'stock'" class="config-grid">
                           <div class="config-item">
                               <label class="config-label">最大市盈率 (PE TTM)</label>
                               <InputNumber v-model="screenParams.pe_max" :min="0" :max="200" showButtons suffix=" 倍" class="w-full" />
                           </div>
                           <div class="config-item">
                               <label class="config-label">最小股息率</label>
                               <InputNumber v-model="screenParams.dividend_min" :min="0" :max="20" showButtons suffix="%" :step="0.5" class="w-full" />
                           </div>
                           <div class="config-item">
                               <label class="config-label">最小市值 (亿)</label>
                               <InputNumber v-model="screenParams.market_cap_min" :min="0" showButtons suffix=" 亿" class="w-full" />
                           </div>
                       </div>

                       <!-- ETF 筛选 -->
                       <div v-if="screenType === 'etf'">
                           <div class="config-item mb-3">
                               <label class="config-label">领域关键词</label>
                               <InputText v-model="screenParams.etf_keyword"
                                          placeholder="输入关键词，如：半导体、医药、沪深300、黄金"
                                          class="w-full text-sm" />
                               <small class="text-xs text-500 mt-1 block">
                                   按名称 / 跟踪指数 / 行业主题 搜索场内 ETF，留空则返回全部 ETF
                               </small>
                           </div>
                           <div class="etf-tags">
                               <span v-for="tag in etfQuickTags" :key="tag"
                                     class="etf-tag"
                                     :class="{ active: screenParams.etf_keyword === tag }"
                                     @click="screenParams.etf_keyword = screenParams.etf_keyword === tag ? '' : tag">
                                   {{ tag }}
                               </span>
                           </div>
                       </div>
                   </div>
               </div>

               <!-- Step 2: Config -->
               <div class="gh-card mb-4">
                   <div class="gh-card-header">2. 参数配置</div>
                   <div class="gh-card-body">
                       <div class="config-grid">
                            <div class="config-item">
                                <label class="config-label">任务名称</label>
                                <InputText v-model="form.name" class="text-sm w-full" />
                            </div>
                             <div class="config-item">
                                 <label class="config-label">单股资金 (万)</label>
                                 <InputNumber v-model="form.initialCapital" suffix=" 万" :min="1" :minFractionDigits="0" :maxFractionDigits="0" class="w-full" />
                                 <small class="text-xs text-500 mt-1 block">
                                     每只股票独立分配的资金，默认 10 万。
                                 </small>
                             </div>
                            <div class="config-item">
                                <label class="config-label">开始日期</label>
                                <DatePicker v-model="form.startDate" dateFormat="yy-mm-dd" showIcon class="w-full" />
                            </div>
                            <div class="config-item">
                                <label class="config-label">结束日期</label>
                                <DatePicker v-model="form.endDate" dateFormat="yy-mm-dd" showIcon class="w-full" />
                            </div>
                       </div>
                   </div>
               </div>

               <!-- Step 3: Strategy -->
               <div class="gh-card mb-4">
                   <div class="gh-card-header">3. 策略配置</div>
                   <div class="gh-card-body">
                       <!-- 参数面板 -->
                       <div class="param-panel">
                           <!-- 入场信号 -->
                           <div class="param-row">
                               <div class="param-left">
                                   <div class="param-label">入场信号</div>
                                   <div class="param-hint">价格 &le; MA120 &times;</div>
                               </div>
                               <div class="param-slider">
                                   <Slider v-model="strategy.entryThreshold" :min="50" :max="100" :step="1" />
                               </div>
                               <div class="param-value">{{ strategy.entryThreshold }}%</div>
                           </div>


                           <!-- 单层止盈 -->
                           <div class="param-row">
                               <div class="param-left">
                                   <div class="param-label">单层止盈</div>
                                   <div class="param-hint">每层收益目标</div>
                               </div>
                               <div class="param-slider">
                                   <Slider v-model="strategy.singleLayerProfit" :min="1" :max="50" :step="1" />
                               </div>
                               <div class="param-value">{{ strategy.singleLayerProfit }}%</div>
                           </div>

                           <!-- 全仓清空 -->
                           <div class="param-row">
                               <div class="param-left">
                                   <div class="param-label">全仓清空</div>
                                   <div class="param-hint">价格 &ge; MA120 &times;</div>
                               </div>
                               <div class="param-slider">
                                   <Slider v-model="strategy.fullClearThreshold" :min="100" :max="150" :step="1" />
                               </div>
                               <div class="param-value">{{ strategy.fullClearThreshold }}%</div>
                           </div>
                       </div>

                       <!-- 梯级加仓 -->
                       <div class="mt-4">
                           <div class="flex align-items-center justify-content-between mb-2">
                               <div class="flex align-items-center gap-2">
                                   <span class="font-bold text-sm">梯级加仓</span>
                                   <SelectButton v-model="positionUnit" :options="unitOptions" optionLabel="label" optionValue="value" class="tiny-select" />
                               </div>
                               <Button label="添加" icon="pi pi-plus" text size="small" @click="addLadder" />
                           </div>
                           <div class="ladder-table">
                               <div class="ladder-header">
                                   <span class="ladder-col-idx">#</span>
                                   <span class="ladder-col-main">触发价位 <span class="font-normal text-400">MA120 &times;</span></span>
                                   <span class="ladder-col-main">加仓金额 <span class="text-xs font-normal">({{ positionUnit === 'percent' ? '%' : '¥' }})</span></span>
                                   <span class="ladder-col-act"></span>
                               </div>
                               <div v-for="(lad, idx) in strategy.ladders" :key="idx" class="ladder-row">
                                   <span class="ladder-col-idx text-500">{{ idx + 1 }}</span>
                                   <div class="ladder-col-main">
                                       <InputNumber v-model="lad.price" suffix="%" :min="10" :max="100" inputClass="ladder-input-prime" class="w-full ladder-prime" />
                                   </div>
                                   <div class="ladder-col-main">
                                       <InputNumber v-if="positionUnit === 'percent'" v-model="lad.fund" suffix="%" :min="0" :max="100" inputClass="ladder-input-prime" class="w-full ladder-prime" />
                                        <InputNumber v-else v-model="lad.fund" suffix=" 万" :min="0.01" :step="0.1" :minFractionDigits="1" :maxFractionDigits="2" inputClass="ladder-input-prime" class="w-full ladder-prime" />
                                   </div>
                                   <div class="ladder-col-act">
                                       <button class="ladder-del" @click="removeLadder(idx)"
                                               :disabled="strategy.ladders.length <= 1" title="删除">
                                           <i class="pi pi-minus-circle"></i>
                                       </button>
                                   </div>
                               </div>
                           </div>
                       </div>
                   </div>
               </div>

               <div class="flex gap-3 pt-2 border-top-1 border-200 align-items-center justify-content-between">
                   <div class="flex gap-3 align-items-center">
                       <Button label="创建回测" icon="pi pi-check" severity="success" @click="createTask" />
                       <Button label="取消" severity="secondary" text @click="router.back()" />
                   </div>
                   <div class="flex align-items-center gap-2">
                       <ToggleSwitch v-model="isPublic" />
                       <span class="text-sm text-500">{{ isPublic ? '公开结果' : '仅自己可见' }}</span>
                   </div>
               </div>
          </div>
      </div>
  </div>
</template>

<style scoped>
.container-narrow {
    max-width: 1012px;
    margin: 0 auto;
    padding: 0 16px;
}

/* ---- 参数配置网格 ---- */
.config-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
}
@media (max-width: 768px) {
    .config-grid {
        grid-template-columns: repeat(2, 1fr);
    }
}
@media (max-width: 480px) {
    .config-grid {
        grid-template-columns: 1fr;
    }
}
.config-item {
    display: flex;
    flex-direction: column;
    gap: 6px;
}
.config-label {
    font-size: 0.8rem;
    font-weight: 600;
    color: var(--p-text-muted-color, #6c757d);
}
.param-panel {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 16px 24px;
}
@media (max-width: 768px) {
    .param-panel {
        grid-template-columns: 1fr;
        gap: 20px;
    }
}

.param-row {
    display: flex;
    align-items: center;
    gap: 12px;
}
.param-left {
    width: 80px;
    flex-shrink: 0;
}
.param-label {
    font-size: 0.875rem;
    font-weight: 600;
    color: var(--p-text-color, #212529);
    line-height: 1.2;
}
.param-hint {
    font-size: 0.75rem;
    color: var(--p-text-muted-color, #6c757d);
    margin-top: 2px;
}
.param-slider {
    flex: 1;
    min-width: 0;
    padding: 0 4px;
}
.param-value {
    width: 40px;
    flex-shrink: 0;
    text-align: right;
    font-size: 1.1rem;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
    color: var(--p-primary-color, #3b82f6);
}

/* ---- 梯级表格 ---- */
.ladder-table {
    border: 1px solid var(--p-content-border-color, #dee2e6);
    border-radius: 6px;
    overflow: hidden;
}
.ladder-header {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 7px 12px;
    background: var(--p-surface-100, #f8f9fa);
    font-size: 0.78rem;
    font-weight: 600;
    color: var(--p-text-muted-color, #6c757d);
    border-bottom: 1px solid var(--p-content-border-color, #dee2e6);
}
.ladder-row {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 5px 12px;
    border-bottom: 1px solid var(--p-content-border-color, #dee2e6);
    transition: background 0.15s;
}
.ladder-row:last-child { border-bottom: none; }
.ladder-row:hover { background: var(--p-surface-50, #f8f9fa); }

.ladder-col-idx {
    width: 22px;
    flex-shrink: 0;
    text-align: center;
    font-size: 0.78rem;
}
.ladder-col-main {
    flex: 1;
    min-width: 0;
}

/* 原生 number input 美化 */
.ladder-input {
    width: 100%;
    padding: 6px 10px;
    border: 1px solid var(--p-content-border-color, #dee2e6);
    border-radius: 4px;
    font-size: 0.85rem;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
    text-align: center;
    color: var(--p-text-color, #212529);
    background: var(--p-surface-0, #fff);
    outline: none;
    transition: border-color 0.15s, box-shadow 0.15s;
    -moz-appearance: textfield;
    box-sizing: border-box;
}
.ladder-input::-webkit-inner-spin-button,
.ladder-input::-webkit-outer-spin-button {
    -webkit-appearance: none;
    margin: 0;
}
.ladder-input:focus {
    border-color: var(--p-primary-color, #3b82f6);
    box-shadow: 0 0 0 2px color-mix(in srgb, var(--p-primary-color, #3b82f6) 16%, transparent);
}

.ladder-col-act {
    width: 32px;
    flex-shrink: 0;
    display: flex;
    justify-content: center;
}
.ladder-del {
    background: none;
    border: none;
    color: var(--p-text-muted-color, #6c757d);
    cursor: pointer;
    padding: 4px;
    border-radius: 4px;
    font-size: 0.9rem;
    transition: color 0.15s, background 0.15s;
    line-height: 1;
}
.ladder-del:hover:not(:disabled) {
    color: var(--p-red-500, #ef4444);
    background: var(--p-red-50, #fef2f2);
}
.ladder-del:disabled {
    opacity: 0.3;
    cursor: not-allowed;
}

/* New Styles for PrimeVue Inputs in Ladder */
:deep(.ladder-prime) {
    width: 100%;
}
:deep(.ladder-input-prime) {
    text-align: center;
    padding: 0.25rem 0.5rem;
    font-size: 0.85rem;
    height: 30px;
}
:deep(.tiny-select) .p-button {
    padding: 2px 8px;
    font-size: 0.75rem;
}

/* ---- ETF 快捷标签 ---- */
.etf-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
}
.etf-tag {
    display: inline-block;
    padding: 4px 12px;
    border: 1px solid var(--p-content-border-color, #dee2e6);
    border-radius: 16px;
    font-size: 0.78rem;
    color: var(--p-text-color, #495057);
    background: var(--p-surface-0, #fff);
    cursor: pointer;
    user-select: none;
    transition: all 0.15s;
}
.etf-tag:hover {
    border-color: var(--p-primary-color, #3b82f6);
    color: var(--p-primary-color, #3b82f6);
    background: color-mix(in srgb, var(--p-primary-color, #3b82f6) 6%, transparent);
}
.etf-tag.active {
    border-color: var(--p-primary-color, #3b82f6);
    color: #fff;
    background: var(--p-primary-color, #3b82f6);
    font-weight: 600;
}
</style>
