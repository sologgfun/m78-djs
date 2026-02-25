<script setup>
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { useToast } from 'primevue/usetoast';
import { API } from '../api';
import { store } from '../store';
import InputText from 'primevue/inputtext';
import Button from 'primevue/button';

const router = useRouter();
const toast = useToast();

const tab = ref('login');
const username = ref('');
const password = ref('');
const loading = ref(false);

async function handleLogin() {
  if (!username.value.trim() || !password.value) return;
  loading.value = true;
  try {
    const res = await API.login(username.value.trim(), password.value);
    store.login(res.token, res.user);
    toast.add({ severity: 'success', summary: '登录成功', life: 2000 });
    router.push('/');
  } catch (e) {
    toast.add({ severity: 'error', summary: '登录失败', detail: e.message, life: 3000 });
  } finally {
    loading.value = false;
  }
}

async function handleRegister() {
  if (!username.value.trim() || !password.value) return;
  loading.value = true;
  try {
    const res = await API.register(username.value.trim(), password.value);
    store.login(res.token, res.user);
    toast.add({ severity: 'success', summary: '注册成功', life: 2000 });
    router.push('/');
  } catch (e) {
    toast.add({ severity: 'error', summary: '注册失败', detail: e.message, life: 3000 });
  } finally {
    loading.value = false;
  }
}

function enterAsGuest() {
  store.enterAsGuest();
  router.push('/');
}

function onSubmit() {
  if (tab.value === 'login') handleLogin();
  else handleRegister();
}
</script>

<template>
  <div class="login-wrapper">
    <div class="login-card gh-card">
      <div class="login-header">
        <svg width="48" height="48" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
          <circle cx="16" cy="16" r="15" fill="#C0C0C0" stroke="#888" stroke-width="2"/>
          <path d="M16 4C12 4 11 9 11 14H21C21 9 20 4 16 4Z" fill="#D32F2F"/>
          <ellipse cx="13" cy="18" rx="3" ry="5" fill="#FFEB3B" />
          <ellipse cx="19" cy="18" rx="3" ry="5" fill="#FFEB3B" />
          <path d="M15 24L16 22L17 24H15Z" fill="#D32F2F"/>
        </svg>
        <h2>白马梯级轮动回测系统</h2>
      </div>

      <div class="login-tabs">
        <button :class="['tab-btn', { active: tab === 'login' }]" @click="tab = 'login'">登录</button>
        <button :class="['tab-btn', { active: tab === 'register' }]" @click="tab = 'register'">注册</button>
      </div>

      <form class="login-form" @submit.prevent="onSubmit">
        <div class="field">
          <label>用户名</label>
          <InputText v-model="username" placeholder="请输入用户名" class="w-full" />
        </div>
        <div class="field">
          <label>密码</label>
          <InputText v-model="password" type="password" placeholder="请输入密码" class="w-full" />
        </div>
        <Button
          :label="tab === 'login' ? '登录' : '注册'"
          type="submit"
          class="w-full p-button-success"
          :loading="loading"
        />
      </form>

      <div class="guest-divider">
        <span>或</span>
      </div>

      <Button
        label="访客进入（仅查看公开结果）"
        class="w-full p-button-secondary"
        @click="enterAsGuest"
      />
    </div>
  </div>
</template>

<style scoped>
.login-wrapper {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: var(--gh-bg-secondary);
}

.login-card {
  width: 360px;
  padding: 32px;
}

.login-header {
  text-align: center;
  margin-bottom: 24px;
}

.login-header h2 {
  margin-top: 12px;
  font-size: 1.25rem;
}

.login-tabs {
  display: flex;
  border-bottom: 1px solid var(--gh-border);
  margin-bottom: 20px;
}

.tab-btn {
  flex: 1;
  background: none;
  border: none;
  padding: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  color: var(--gh-text-secondary);
  border-bottom: 2px solid transparent;
  transition: all 0.2s;
}

.tab-btn.active {
  color: var(--gh-text-primary);
  border-bottom-color: var(--gh-link);
}

.tab-btn:hover {
  color: var(--gh-text-primary);
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.field label {
  display: block;
  font-weight: 600;
  margin-bottom: 4px;
  font-size: 14px;
}

.guest-divider {
  text-align: center;
  margin: 16px 0;
  position: relative;
  color: var(--gh-text-secondary);
  font-size: 13px;
}

.guest-divider::before,
.guest-divider::after {
  content: '';
  position: absolute;
  top: 50%;
  width: 40%;
  height: 1px;
  background: var(--gh-border);
}

.guest-divider::before { left: 0; }
.guest-divider::after { right: 0; }
</style>
