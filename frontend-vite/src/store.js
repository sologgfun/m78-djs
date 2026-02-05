
import { reactive } from 'vue';

export const store = reactive({
    systemReady: false,
    selectedList: [],

    // Actions
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
