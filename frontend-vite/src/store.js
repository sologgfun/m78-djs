
import { reactive } from 'vue';

const savedToken = localStorage.getItem('token');
const savedUser = (() => {
    try { return JSON.parse(localStorage.getItem('user')); } catch { return null; }
})();

export const store = reactive({
    systemReady: false,
    selectedList: [],

    // 用户状态
    token: savedToken || null,
    user: savedUser || null,
    isGuest: !savedToken,

    get isLoggedIn() {
        return !!this.token && !!this.user;
    },

    login(token, user) {
        this.token = token;
        this.user = user;
        this.isGuest = false;
        localStorage.setItem('token', token);
        localStorage.setItem('user', JSON.stringify(user));
    },

    logout() {
        this.token = null;
        this.user = null;
        this.isGuest = false;
        localStorage.removeItem('token');
        localStorage.removeItem('user');
    },

    enterAsGuest() {
        this.token = null;
        this.user = null;
        this.isGuest = true;
    },

    // 股票选择
    addSelected(stock) {
        if (!stock.code) return;
        if (this.selectedList.some(x => x.code === stock.code)) return;
        this.selectedList.push(stock);
    },

    removeSelected(code) {
        this.selectedList = this.selectedList.filter(x => x.code !== code);
    },

    clearSelected() {
        this.selectedList = [];
    },

    setSystemReady(status) {
        this.systemReady = status;
    }
});
