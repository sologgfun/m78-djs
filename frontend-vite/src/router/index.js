
import { createRouter, createWebHistory } from 'vue-router';
import AppLayout from '../layout/AppLayout.vue';

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
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
          component: () => import('../views/CreateTaskView.vue')
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

export default router;
