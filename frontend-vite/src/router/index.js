
import { createRouter, createWebHistory } from 'vue-router';
import { store } from '../store';
import AppLayout from '../layout/AppLayout.vue';

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('../views/LoginView.vue')
    },
    {
      path: '/',
      component: AppLayout,
      children: [
        {
          path: '',
          name: 'dashboard',
          component: () => import('../views/RunsView.vue')
        },
        {
          path: '/new',
          name: 'create-task',
          component: () => import('../views/CreateTaskView.vue'),
          meta: { requiresAuth: true }
        },
        {
          path: '/simulator',
          name: 'simulator',
          component: () => import('../views/SimulatorView.vue')
        }
      ]
    }
  ]
});

router.beforeEach((to) => {
  const hasAccess = store.isLoggedIn || store.isGuest;
  if (to.name !== 'login' && !hasAccess) {
    return { name: 'login' };
  }
  if (to.meta.requiresAuth && !store.isLoggedIn) {
    return { name: 'login' };
  }
});

export default router;
