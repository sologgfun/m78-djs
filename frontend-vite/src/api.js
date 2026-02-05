async function request(path, options = {}) {
  const res = await fetch(path, {
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {})
    },
    ...options
  });

  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) {
    throw new Error((data && data.error) || `请求失败(${res.status})`);
  }
  return data;
}

export const API = {
  healthCheck: () => request('/api/system/health'),

  searchStocks: (keyword) => request(`/api/stocks/search?keyword=${encodeURIComponent(keyword)}`),
  favorites: () => request('/api/stocks/favorites'),
  djsRecommend: (params = {}) => {
    const qs = new URLSearchParams();
    if (params.peMax != null) qs.set('pe_max', params.peMax);
    if (params.dividendMin != null) qs.set('dividend_min', params.dividendMin);
    if (params.priceRatio != null) qs.set('price_ratio', params.priceRatio);
    const q = qs.toString();
    return request(`/api/stocks/djs${q ? '?' + q : ''}`);
  },

  createBacktest: (payload) =>
    request('/api/backtest/create', { method: 'POST', body: JSON.stringify(payload) }),

  tasks: () => request('/api/backtest/tasks'),
  result: (taskId) => request(`/api/backtest/result/${taskId}`),
  resultDetails: (taskId) => request(`/api/backtest/result/${taskId}/details`),
  trades: (taskId, stockCode) =>
    request(`/api/backtest/result/${taskId}/trades?stock_code=${encodeURIComponent(stockCode)}`),
  deleteTask: (taskId) =>
    request(`/api/backtest/delete/${taskId}`, { method: 'DELETE' }),
  updateTask: (taskId, data) =>
    request(`/api/backtest/update/${taskId}`, { method: 'PUT', body: JSON.stringify(data) }),
};

