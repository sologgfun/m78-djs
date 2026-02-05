<script setup>
import { ref, computed } from 'vue';
import InputNumber from 'primevue/inputnumber';
import Divider from 'primevue/divider';
import Button from 'primevue/button';
import DataTable from 'primevue/datatable';
import Column from 'primevue/column';
import Tag from 'primevue/tag';
import Slider from 'primevue/slider';

const ma120 = ref(100);
const purchasePrice = ref(88);
const entryThreshold = ref(88);      // UI uses 88 for 88%
const singleProfit = ref(12);        // UI uses 12 for 12%
const fullClearThreshold = ref(112); // UI uses 112 for 112%

const ladderDown = ref([
    { ratio: 0.88, fund: 0.1 },
    { ratio: 0.80, fund: 0.2 },
    { ratio: 0.72, fund: 0.3 },
    { ratio: 0.64, fund: 0.4 }
]);

const entryPrice = computed(() => (ma120.value * (entryThreshold.value / 100)).toFixed(2));
const clearPrice = computed(() => (ma120.value * (fullClearThreshold.value / 100)).toFixed(2));
const takeProfitPrice = computed(() => (purchasePrice.value * (1 + (singleProfit.value / 100))).toFixed(2));

const ladderResults = computed(() => {
    return ladderDown.value.map((level, index) => {
        const buyPrice = (ma120.value * level.ratio).toFixed(2);
        const targetSell = (purchasePrice.value * (1 + (singleProfit.value / 100))).toFixed(2);
        
        return {
            index,
            ratio: level.ratio,
            fund: level.fund,
            buyPrice,
            targetSell: index === 0 ? targetSell : '跟随购买价计算' 
        };
    });
});
</script>

<template>
    <div class="view-container" style="height: calc(100vh - 80px); overflow: hidden; padding: 1rem;">
        <div class="grid h-full" style="margin: 0; align-items: stretch;">
            <!-- Left: Inputs -->
            <div class="col-12 lg:col-4 h-full">
                <div class="gh-card h-full flex flex-column overflow-hidden">
                    <div class="gh-card-header shrink-0">
                        <i class="pi pi-sliders-h mr-2"></i>模拟参数输入
                    </div>
                    <div class="gh-card-body flex-1 overflow-auto">
                        <div class="flex flex-column gap-4 p-3">
                            <div class="flex flex-column gap-2 mb-1">
                                <label class="font-bold text-sm flex align-items-center">
                                    <i class="pi pi-chart-line mr-2 text-primary"></i>120日均线价格 (MA120)
                                </label>
                                <InputNumber v-model="ma120" mode="decimal" :minFractionDigits="2" class="w-full" inputClass="py-2 px-3 font-mono" prefix="¥ " />
                                <small class="text-400">行情软件中的 120 日移动平均价</small>
                            </div>

                            <div class="flex flex-column gap-2">
                                <label class="font-bold text-sm flex align-items-center">
                                    <i class="pi pi-shopping-cart mr-2 text-green-600"></i>实际买入价格
                                </label>
                                <InputNumber v-model="purchasePrice" mode="decimal" :minFractionDigits="2" class="w-full" inputClass="py-2 px-3 font-mono" prefix="¥ " />
                                <small class="text-400">您在账户中的实际成交均价</small>
                            </div>

                            <Divider class="my-2" />

                            <div class="flex flex-column gap-3">
                                <label class="font-bold text-sm text-primary flex align-items-center">
                                    <i class="pi pi-cog mr-2"></i>策略核心参数
                                </label>
                                
                                <!-- Entry Threshold -->
                                <div class="param-item">
                                    <div class="flex justify-content-between mb-2">
                                        <span class="text-xs font-semibold">入场信号 <span class="text-400 font-normal ml-1">价格 &le; MA120 &times;</span></span>
                                        <span class="text-primary font-bold">{{ entryThreshold }}%</span>
                                    </div>
                                    <Slider v-model="entryThreshold" :min="50" :max="100" />
                                </div>

                                <!-- Profit Rate -->
                                <div class="param-item">
                                    <div class="flex justify-content-between mb-2">
                                        <span class="text-xs font-semibold">单层止盈 <span class="text-400 font-normal ml-1">目标收益比</span></span>
                                        <span class="text-primary font-bold">{{ singleProfit }}%</span>
                                    </div>
                                    <Slider v-model="singleProfit" :min="1" :max="50" />
                                </div>

                                <!-- Clear Threshold -->
                                <div class="param-item">
                                    <div class="flex justify-content-between mb-2">
                                        <span class="text-xs font-semibold">全仓清仓 <span class="text-400 font-normal ml-1">价格 &ge; MA120 &times;</span></span>
                                        <span class="text-primary font-bold">{{ fullClearThreshold }}%</span>
                                    </div>
                                    <Slider v-model="fullClearThreshold" :min="100" :max="150" />
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Right: Results -->
            <div class="col-12 lg:col-8 h-full">
                <div class="gh-card h-full flex flex-column overflow-hidden">
                    <div class="gh-card-header shrink-0">
                        <i class="pi pi-bolt mr-2 text-warning"></i>量化价位建议
                    </div>
                    <div class="gh-card-body flex-1 overflow-auto">
                        <div class="p-3">
                            <!-- Quick Info -->
                            <div class="grid mb-4">
                                <div class="col-12 md:col-4">
                                    <div class="surface-card p-3 border-1 border-200 border-round">
                                        <div class="text-500 text-xs mb-1">建议入场价</div>
                                        <div class="text-xl font-bold text-primary">¥{{ entryPrice }}</div>
                                        <div class="text-xs text-400">MA120 * {{ entryThreshold }}%</div>
                                    </div>
                                </div>
                                <div class="col-12 md:col-4">
                                    <div class="surface-card p-3 border-1 border-200 border-round">
                                        <div class="text-500 text-xs mb-1">首层止盈价</div>
                                        <div class="text-xl font-bold text-green-600">¥{{ takeProfitPrice }}</div>
                                        <div class="text-xs text-400">买入价 * (1 + {{ singleProfit }}%)</div>
                                    </div>
                                </div>
                                <div class="col-12 md:col-4">
                                    <div class="surface-card p-3 border-1 border-200 border-round">
                                        <div class="text-500 text-xs mb-1">全仓清仓价</div>
                                        <div class="text-xl font-bold text-orange-600">¥{{ clearPrice }}</div>
                                        <div class="text-xs text-400">MA120 * {{ fullClearThreshold }}%</div>
                                    </div>
                                </div>
                            </div>

                            <div class="font-bold mb-3 text-800">补仓梯级表 (向下金字塔)</div>
                            <DataTable :value="ladderResults" size="small" stripedRows class="border-1 border-200 border-round overflow-hidden">
                                <Column field="index" header="层级">
                                    <template #body="{ data }">
                                        <Tag :value="'L' + data.index" :severity="data.index === 0 ? 'info' : 'warning'" />
                                    </template>
                                </Column>
                                <Column field="ratio" header="MA120比例">
                                    <template #body="{ data }">
                                        {{ (data.ratio * 100).toFixed(0) }}%
                                    </template>
                                </Column>
                                <Column field="buyPrice" header="目标买入价">
                                    <template #body="{ data }">
                                        <span class="font-bold text-primary">¥{{ data.buyPrice }}</span>
                                    </template>
                                </Column>
                                <Column field="targetSell" header="止盈价 (该层)">
                                    <template #body="{ data }">
                                        <span v-if="data.index === 0" class="text-green-600 font-bold">¥{{ data.targetSell }}</span>
                                        <span v-else class="text-400 italic">买入价 * (1+{{ singleProfit }})</span>
                                    </template>
                                </Column>
                                <Column field="fund" header="分配权重">
                                    <template #body="{ data }">
                                        {{ (data.fund * 100).toFixed(0) }}%
                                    </template>
                                </Column>
                            </DataTable>

                            <div class="mt-4 p-3 surface-50 border-round text-xs text-600 border-left-3 border-primary">
                                <div class="font-bold mb-1">使用说明：</div>
                                <p class="m-0">1. 输入当天的 MA120 价格，系统会计算理论入场点。</p>
                                <p class="m-0">2. 输入您的实际买入价，系统会计算对应的补仓位和第一层止盈位。</p>
                                <p class="m-0">3. 当股价回升触及 MA120 * {{ fullClearThreshold }} 时，建议不论盈亏全仓清出。</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped>
/* Inherit standard heights from RunsView */
.view-container {
    background-color: var(--gh-bg-secondary);
}
</style>
