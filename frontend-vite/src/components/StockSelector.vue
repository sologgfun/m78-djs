
<script setup>
import { ref, computed, onMounted } from 'vue';
import { API } from '../api';
import { store } from '../store';

import Button from 'primevue/button';
import InputText from 'primevue/inputtext';
import DataTable from 'primevue/datatable';
import Column from 'primevue/column';
import Tag from 'primevue/tag';
import { useToast } from 'primevue/usetoast';

const toast = useToast();
const keyword = ref('');
const searchResults = ref([]);
const djsStocks = ref([]);
const djsTotal = ref(0);
const loading = ref(false);
const loadingDjs = ref(false);

// 点金术特选 — 可配置筛选条件
const djsFilter = ref({
  peMax: 20,
  dividendMin: 3,
  priceRatio: 90,
});

const selectedCount = computed(() => store.selectedList.length);

function normalizeStock(s) {
  return {
    code: (s.code || s.stock_code || '').toString(),
    name: (s.name || s.stock_name || '').toString()
  };
}

/** 生成同花顺股票详情页 URL */
function thsUrl(code) {
  if (!code) return '#';
  // 同花顺股票首页格式: https://stockpage.10jqka.com.cn/600519/
  return `https://stockpage.10jqka.com.cn/${code}/`;
}

/** 搜索结果/收藏项：与 DJS 同结构，无数据时为 null 显示 — */
function normalizeSearchRow(s) {
  const base = normalizeStock(s);
  return {
    ...base,
    pe: s.pe != null && !isNaN(Number(s.pe)) ? Number(s.pe) : null,
    dividend: s.dividend != null && !isNaN(Number(s.dividend)) ? Number(s.dividend) : null,
    ratio: s.ratio != null && !isNaN(Number(s.ratio)) ? Number(s.ratio) : null,
    price: s.price != null ? Number(s.price) : null,
    ma120: s.ma120 != null ? Number(s.ma120) : null,
    industry: s.industry || null,
    stock5d: s.stock5d != null && !isNaN(Number(s.stock5d)) ? Number(s.stock5d) : null,
    industry5d: s.industry5d != null && !isNaN(Number(s.industry5d)) ? Number(s.industry5d) : null,
  };
}

/** 点金术列表项：保留 PE、股息、价/MA120 等用于展示 */
function normalizeDjsItem(s) {
  const code = (s.code || s.stock_code || '').toString();
  const name = (s.name || s.stock_name || '').toString();
  const pe = s.pe != null ? Number(s.pe) : null;
  const dividend = s.dividend != null ? Number(s.dividend) : null;
  const ratio = s.ratio != null ? Number(s.ratio) : null;
  const price = s.price != null ? Number(s.price) : null;
  const ma120 = s.ma120 != null ? Number(s.ma120) : null;
  const industry = s.industry || null;
  const stock5d = s.stock5d != null ? Number(s.stock5d) : null;
  const industry5d = s.industry5d != null ? Number(s.industry5d) : null;
  return {
    code,
    name,
    pe: pe != null && !isNaN(pe) ? pe : null,
    dividend: dividend != null && !isNaN(dividend) ? dividend : null,
    ratio: ratio != null && !isNaN(ratio) ? ratio : null,
    price,
    ma120,
    industry,
    stock5d: stock5d != null && !isNaN(stock5d) ? stock5d : null,
    industry5d: industry5d != null && !isNaN(industry5d) ? industry5d : null,
  };
}

async function doSearch() {
  const k = keyword.value.trim();
  loading.value = true;
  try {
      if (!k) {
          const resp = await API.favorites();
          searchResults.value = (resp.data || []).map(s => normalizeSearchRow(s));
      } else {
          const resp = await API.searchStocks(k);
          searchResults.value = (resp.data || []).map(s => normalizeSearchRow(s));
      }
  } catch (e) {
      toast.add({ severity: 'error', summary: '搜索失败', detail: e.message });
  } finally {
      loading.value = false;
  }
}

async function loadDjs() {
    loadingDjs.value = true;
    try {
        const f = djsFilter.value;
        const resp = await API.djsRecommend({
            peMax: f.peMax,
            dividendMin: f.dividendMin,
            priceRatio: f.priceRatio,
        });
        djsStocks.value = (resp.data || []).map(normalizeDjsItem);
        djsTotal.value = resp.total != null ? resp.total : djsStocks.value.length;
    } catch (e) {
        console.error('DJS Load Error:', e);
    } finally {
        loadingDjs.value = false;
    }
}

function onAdd(row) {
    // 保存完整信息，包括PE、股息率、价/MA120
    store.addSelected({
        ...normalizeStock(row),
        pe: row.pe,
        dividend: row.dividend,
        ratio: row.ratio,
        price: row.price,
        ma120: row.ma120
    });
}

function onAddAll() {
    if (!djsStocks.value.length) return;
    djsStocks.value.forEach(row => {
        store.addSelected({
            ...normalizeStock(row),
            pe: row.pe,
            dividend: row.dividend,
            ratio: row.ratio,
            price: row.price,
            ma120: row.ma120
        });
    });
    toast.add({ severity: 'success', summary: '添加成功', detail: `已添加 ${djsStocks.value.length} 只股票`, life: 2000 });
}

function onRemove(code) {
    store.removeSelected(code);
}

onMounted(() => {
    loadDjs();
});
</script>

<template>
  <div class="grid overflow-hidden">
     <!-- Search Side -->
     <div class="col-12 md:col-7">
        <label class="block text-sm font-semibold mb-2">1. 查找股票</label>
        <div class="flex gap-2 mb-3">
            <InputText v-model="keyword" placeholder="代码/名称" class="flex-1 text-sm" style="min-width: 100px" @keydown.enter.prevent="doSearch" />
            <Button label="搜索" icon="pi pi-search" class="p-button-secondary text-sm shrink-0" @click="doSearch" :loading="loading" />
        </div>
        
        <div class="gh-card mb-3" v-if="searchResults.length || loading">
             <div class="gh-card-header py-2 flex align-items-center">
                 <span class="text-xs font-semibold">搜索结果</span>
             </div>
             <div class="p-0">
                 <DataTable :value="searchResults" :rows="5" paginator size="small" stripedRows tableStyle="min-width: 100%" class="stock-table">
                     <template #empty>
                         <div class="p-3 text-center text-500 text-sm">无搜索结果</div>
                     </template>
                     <Column field="code" header="代码" headerClass="col-code" bodyClass="col-code"></Column>
                     <Column header="名称" headerClass="col-name" bodyClass="col-name">
                         <template #body="{ data }">
                             <a :href="thsUrl(data.code)" target="_blank" class="stock-link">{{ data.name }}</a>
                         </template>
                     </Column>
                     <Column header="PE" headerClass="col-pe" bodyClass="col-pe">
                         <template #body="{ data }">
                             <span v-if="data.pe != null" class="stock-num">{{ data.pe }}</span>
                             <span v-else class="text-400">—</span>
                         </template>
                     </Column>
                     <Column header="股息%" headerClass="col-dividend" bodyClass="col-dividend">
                         <template #body="{ data }">
                             <span v-if="data.dividend != null" class="stock-num">{{ data.dividend }}%</span>
                             <span v-else class="text-400">—</span>
                         </template>
                     </Column>
                     <Column header="价/MA120" headerClass="col-ratio" bodyClass="col-ratio">
                         <template #body="{ data }">
                             <span v-if="data.ratio != null"
                                   :class="(data.ratio < 5 ? data.ratio * 100 : data.ratio) < 90 ? 'text-green-600 font-semibold' : ''"
                                   class="stock-num">
                                 {{ (data.ratio < 5 ? data.ratio * 100 : data.ratio).toFixed(1) }}%
                             </span>
                             <span v-else class="text-400">—</span>
                         </template>
                     </Column>
                     <Column header="" bodyClass="text-right col-action">
                         <template #body="{ data }">
                             <Button icon="pi pi-plus" size="small" text rounded severity="primary" @click="onAdd(data)" />
                         </template>
                     </Column>
                 </DataTable>
             </div>
        </div>

        <!-- DJS Recommendations -->
        <div class="gh-card">
             <div class="gh-card-header py-2 flex align-items-center justify-content-between">
                 <span class="text-xs font-semibold text-primary">
                    <i class="pi pi-star-fill text-yellow-500 mr-1"></i>点金术特选
                    <span class="text-500 font-normal ml-1">（共 {{ djsTotal }} 只）</span>
                 </span>
                 <Button v-if="!loadingDjs" icon="pi pi-refresh" text rounded size="small" @click="loadDjs" />
             </div>

             <!-- 可配置筛选条件 -->
             <div class="djs-filter-bar">
                 <div class="djs-filter-item">
                     <label>PE &lt;</label>
                     <input type="number" v-model.number="djsFilter.peMax" min="1" max="200" step="1" class="djs-filter-input" />
                 </div>
                 <div class="djs-filter-item">
                     <label>股息率 &gt;</label>
                     <input type="number" v-model.number="djsFilter.dividendMin" min="0" max="30" step="0.5" class="djs-filter-input" />
                     <span class="djs-filter-unit">%</span>
                 </div>
                 <div class="djs-filter-item">
                     <label>价格 &lt; 120MA &times;</label>
                     <input type="number" v-model.number="djsFilter.priceRatio" min="50" max="120" step="1" class="djs-filter-input" />
                     <span class="djs-filter-unit">%</span>
                 </div>
                 <div class="djs-filter-btn-group">
                     <Button label="筛选" icon="pi pi-filter" size="small" severity="primary" @click="loadDjs" :loading="loadingDjs" />
                     <Button v-if="djsStocks.length" label="一键添加所有" icon="pi pi-plus-circle" size="small" severity="primary" @click="onAddAll" />
                 </div>
             </div>

             <div class="p-0">
                 <DataTable :value="djsStocks" :rows="10" paginator size="small" :loading="loadingDjs" tableStyle="min-width: 100%"
                            :rowsPerPageOptions="[10, 20, 50]" class="stock-table">
                     <template #empty>
                         <div class="p-3 text-center text-500 text-sm">当前无符合条件的股票</div>
                     </template>
                     <Column field="code" header="代码" headerClass="col-code" bodyClass="col-code"></Column>
                     <Column header="名称" headerClass="col-name" bodyClass="col-name">
                         <template #body="{ data }">
                             <a :href="thsUrl(data.code)" target="_blank" class="stock-link">{{ data.name }}</a>
                         </template>
                     </Column>
                     <Column header="PE" headerClass="col-pe" bodyClass="col-pe" sortable dataType="numeric">
                         <template #body="{ data }">
                             <span v-if="data.pe != null" class="stock-num">{{ data.pe }}</span>
                             <span v-else class="text-400">—</span>
                         </template>
                     </Column>
                     <Column header="股息%" headerClass="col-dividend" bodyClass="col-dividend" sortable dataType="numeric">
                         <template #body="{ data }">
                             <span v-if="data.dividend != null" class="stock-num">{{ data.dividend }}%</span>
                             <span v-else class="text-400">—</span>
                         </template>
                     </Column>
                     <Column header="价/MA120" headerClass="col-ratio" bodyClass="col-ratio" sortable dataType="numeric">
                         <template #body="{ data }">
                             <span v-if="data.ratio != null"
                                   :class="(data.ratio < 5 ? data.ratio * 100 : data.ratio) < 90 ? 'text-green-600 font-semibold' : ''"
                                   class="stock-num">
                                 {{ (data.ratio < 5 ? data.ratio * 100 : data.ratio).toFixed(1) }}%
                             </span>
                             <span v-else class="text-400">—</span>
                         </template>
                     </Column>
                     <Column header="" bodyClass="text-right col-action">
                         <template #body="{ data }">
                             <Button icon="pi pi-plus" size="small" text rounded severity="primary" @click="onAdd(data)" />
                         </template>
                     </Column>
                 </DataTable>
             </div>
        </div>
     </div>

     <!-- Selected Side -->
     <div class="col-12 md:col-5">
        <label class="block text-sm font-semibold mb-2">
            已选股票 <Tag :value="selectedCount" severity="info" class="ml-2 text-xs"></Tag>
        </label>
        
        <div class="gh-card border-200 flex flex-column overflow-hidden" style="min-height: 400px; max-height: 600px;">
            <div v-if="!selectedCount" class="text-center text-500 py-8 text-sm flex-1 flex align-items-center justify-content-center">
                暂无已选股票
            </div>
            
            <div v-else class="p-0 flex-1 overflow-auto">
                <DataTable :value="store.selectedList" size="small" tableStyle="min-width: 100%" class="selected-table">
                     <Column field="code" header="代码" headerClass="sel-col-code" bodyClass="sel-col-code"></Column>
                     <Column field="name" header="名称" headerClass="sel-col-name" bodyClass="sel-col-name"></Column>
                     <Column header="PE" headerClass="sel-col-pe" bodyClass="sel-col-pe">
                         <template #body="{ data }">
                             <span v-if="data.pe != null" class="stock-num text-xs">{{ data.pe }}</span>
                             <span v-else class="text-400 text-xs">—</span>
                         </template>
                     </Column>
                     <Column header="股息%" headerClass="sel-col-div" bodyClass="sel-col-div">
                         <template #body="{ data }">
                             <span v-if="data.dividend != null" class="stock-num text-xs">{{ data.dividend }}%</span>
                             <span v-else class="text-400 text-xs">—</span>
                         </template>
                     </Column>
                     <Column header="价/MA120" headerClass="sel-col-ratio" bodyClass="sel-col-ratio">
                         <template #body="{ data }">
                             <span v-if="data.ratio != null"
                                   :class="(data.ratio < 5 ? data.ratio * 100 : data.ratio) < 90 ? 'text-green-600 font-semibold' : ''"
                                   class="stock-num text-xs">
                                 {{ (data.ratio < 5 ? data.ratio * 100 : data.ratio).toFixed(1) }}%
                             </span>
                             <span v-else class="text-400 text-xs">—</span>
                         </template>
                     </Column>
                     <Column header="" bodyClass="text-right sel-col-action">
                         <template #body="{ data }">
                             <Button icon="pi pi-times" size="small" text rounded severity="danger" @click="onRemove(data.code)" />
                         </template>
                     </Column>
                </DataTable>
            </div>
        </div>
     </div>
  </div>
</template>

<style scoped>
/* ---- 点金术特选筛选条件栏 ---- */
.djs-filter-bar {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 12px;
    padding: 12px 14px;
    background: var(--p-surface-50, #f8f9fa);
    border-bottom: 1px solid var(--p-content-border-color, #dee2e6);
}
.djs-filter-item {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: flex-start;
    gap: 6px;
    font-size: 0.78rem;
    color: var(--p-text-color, #212529);
    white-space: nowrap;
}
.djs-filter-btn-group {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-left: auto;
}
.djs-filter-item label {
    font-weight: 600;
    color: var(--p-text-muted-color, #6c757d);
}
.djs-filter-input {
    width: 56px;
    padding: 4px 6px;
    border: 1px solid var(--p-content-border-color, #dee2e6);
    border-radius: 4px;
    font-size: 0.8rem;
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
.djs-filter-input::-webkit-inner-spin-button,
.djs-filter-input::-webkit-outer-spin-button {
    -webkit-appearance: none;
    margin: 0;
}
.djs-filter-input:focus {
    border-color: var(--p-primary-color, #3b82f6);
    box-shadow: 0 0 0 2px color-mix(in srgb, var(--p-primary-color, #3b82f6) 16%, transparent);
}
.djs-filter-unit {
    font-size: 0.75rem;
    color: var(--p-text-muted-color, #6c757d);
}

/* ---- 股票表格列宽与对齐 ---- */
.stock-table :deep(.col-code) {
    width: 18%;
}
.stock-table :deep(.col-name) {
    width: 20%;
}
.stock-table :deep(.col-pe) {
    width: 15%;
    text-align: left;
}
.stock-table :deep(.col-dividend) {
    width: 17%;
    text-align: left;
}
.stock-table :deep(.col-ratio) {
    width: 20%;
    text-align: left;
}
.stock-table :deep(.col-action) {
    width: 10%;
    text-align: center;
}
.stock-num {
    font-variant-numeric: tabular-nums;
}
.stock-link {
    color: var(--p-primary-color, #3b82f6);
    text-decoration: none;
    transition: color 0.15s;
}
.stock-link:hover {
    color: var(--p-primary-600, #2563eb);
    text-decoration: underline;
}

/* ---- 已选股票表格列宽 ---- */
.selected-table :deep(.sel-col-code) {
    width: 16%;
    font-size: 0.8rem;
}
.selected-table :deep(.sel-col-name) {
    width: 22%;
    font-size: 0.8rem;
}
.selected-table :deep(.sel-col-pe) {
    width: 13%;
    text-align: left;
}
.selected-table :deep(.sel-col-div) {
    width: 15%;
    text-align: left;
}
.selected-table :deep(.sel-col-ratio) {
    width: 20%;
    text-align: left;
}
.selected-table :deep(.sel-col-action) {
    width: 14%;
    text-align: center;
}
</style>
