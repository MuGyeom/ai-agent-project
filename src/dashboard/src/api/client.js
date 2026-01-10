import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000';

const api = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        'Content-Type': 'application/json',
    },
});

export const fetchRequests = async (status = null, limit = 20, offset = 0) => {
    const params = { limit, offset };
    if (status && status !== 'all') params.status = status;
    const response = await api.get('/api/requests', { params });
    return response.data;
};

export const fetchRequestDetail = async (requestId) => {
    const response = await api.get(`/api/requests/${requestId}`);
    return response.data;
};

export const fetchMetrics = async () => {
    const response = await api.get('/api/metrics');
    return response.data;
};

export const createRequest = async (topic) => {
    const response = await api.post('/analyze', { topic });
    return response.data;
};

export default api;
