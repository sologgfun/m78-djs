
<script setup>
import { ref, onMounted } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { API } from '../api';
import Toast from 'primevue/toast';

const router = useRouter();
const route = useRoute();
const systemReady = ref(false);

const menuItems = [
  { label: '回测大厅', route: '/' },
  { label: '模拟器', route: '/simulator' },
  { label: '新建回测', route: '/new', highlight: true }
];

function navigate(path) {
  router.push(path);
}

onMounted(async () => {
    try {
        await API.healthCheck();
        systemReady.value = true;
    } catch {
        systemReady.value = false;
    }
});
</script>

<template>
  <div class="layout-wrapper">
    <!-- Header -->
    <header class="gh-header">
        <div class="gh-header-container">
            <div class="flex align-items-center gap-3">
                <a @click="navigate('/')" class="gh-logo" title="Backtest Ultra">
                    <!-- Simple Ultraman-inspired SVG Logo -->
                    <svg width="32" height="32" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <circle cx="16" cy="16" r="15" fill="#C0C0C0" stroke="#888" stroke-width="2"/>
                        <path d="M16 4C12 4 11 9 11 14H21C21 9 20 4 16 4Z" fill="#D32F2F"/>
                        <ellipse cx="13" cy="18" rx="3" ry="5" fill="#FFEB3B" />
                        <ellipse cx="19" cy="18" rx="3" ry="5" fill="#FFEB3B" />
                        <path d="M15 24L16 22L17 24H15Z" fill="#D32F2F"/>
                    </svg>
                </a>
                
                <nav class="gh-nav">
                    <a v-for="item in menuItems" :key="item.route"
                        class="gh-nav-item"
                        :class="{ 'active': route.path === item.route, 'btn-highlight': item.highlight }"
                        v-ripple
                        @click="navigate(item.route)">
                        {{ item.label }}
                    </a>
                </nav>
            </div>
            
            <div class="gh-header-actions">
                <span class="text-xs text-white-alpha-70 mr-2 flex align-items-center gap-1">
                    <i class="pi pi-circle-fill" style="font-size: 8px" :class="systemReady ? 'text-green-500' : 'text-red-500'"></i>
                    {{ systemReady ? '服务正常' : '离线' }}
                </span>
            </div>
        </div>
    </header>

    <main class="layout-content">
        <div class="container py-4">
            <router-view />
        </div>
    </main>
    
    <Toast />
  </div>
</template>

<style scoped>
.layout-wrapper {
    min-height: 100vh;
    background-color: var(--gh-bg-secondary);
}

/* Header Styles */
.gh-header {
    background-color: var(--primary-color);
    padding: 12px 0;
    color: white;
}

.gh-header-container {
    max-width: 1012px;
    margin: 0 auto;
    padding: 0 16px;
    display: flex;
    align-items: center;
    justify-content: space-between;
}

.gh-logo {
    cursor: pointer;
    display: flex;
    align-items: center;
    transition: transform 0.2s;
}
.gh-logo:hover {
    transform: scale(1.05);
}

.gh-nav {
    display: flex;
    gap: 8px;
}

.gh-nav-item {
    color: rgba(255, 255, 255, 0.75);
    font-weight: 500;
    padding: 6px 12px;
    border-radius: 6px;
    font-size: 14px;
    cursor: pointer;
    transition: all 0.2s;
}

.gh-nav-item:hover {
    color: #fff;
    background-color: rgba(255, 255, 255, 0.1);
    text-decoration: none;
}

.gh-nav-item.active {
    color: #fff;
    font-weight: 600;
}
</style>
