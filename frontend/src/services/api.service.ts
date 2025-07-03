import { EvaluationSession } from '../types/evaluation.types';
import { 
    SandboxRequest, 
    SandboxResponse, 
    BatchEvaluationResponse,
    TaskStatusResponse,
    FeedbackRequest,
    MetricStatistics
} from '../types/api.types';

const API_BASE_URL = ''; // Proxy'den gelen istekler için temel URL boş olmalı
// In a real app, this should be handled more securely (e.g., via an auth flow)
const API_KEY = import.meta.env.VITE_API_KEY || 'JotformSecretKey-123';

class ApiService {
    private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
        const url = `${API_BASE_URL}${endpoint}`;
        
        const headers = {
            ...options.headers,
            'X-API-Key': API_KEY,
        };

        if (!(options.body instanceof FormData)) {
            headers['Content-Type'] = 'application/json';
        }

        const config: RequestInit = {
            ...options,
            headers,
        };

        try {
            const response = await fetch(url, config);
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ detail: response.statusText }));
                throw new Error(`API Error: ${response.status} ${errorData.detail || 'Unknown error'}`);
            }
            if (response.status === 204) { // No Content
                return null as T;
            }
            return response.json();
        } catch (error) {
            console.error(`Request to ${endpoint} failed:`, error);
            throw error;
        }
    }

    // --- Evaluation Endpoints ---

    async evaluateSandbox(data: SandboxRequest): Promise<SandboxResponse> {
        return this.request('/api/evaluate/sandbox', {
            method: 'POST',
            body: JSON.stringify(data),
        });
    }

    async uploadBatchFile(file: File): Promise<BatchEvaluationResponse> {
        const formData = new FormData();
        formData.append('file', file);

        return this.request('/api/evaluate/batch', {
            method: 'POST',
            body: formData,
        });
    }

    // --- Task Status ---

    async getTaskStatus(taskId: string): Promise<TaskStatusResponse> {
        return this.request(`/api/tasks/${taskId}`);
    }

    // --- Data Retrieval Endpoints ---

    async getAllEvaluations(): Promise<EvaluationSession[]> {
        return this.request('/api/evaluations');
    }
    
    async getSession(sessionId: string): Promise<EvaluationSession> {
        return this.request(`/api/sessions/${sessionId}`);
    }

    async getAgents(): Promise<string[]> {
        return this.request('/api/agents');
    }

    async getMetricStats(agentId?: string): Promise<MetricStatistics> {
        const endpoint = agentId ? `/api/metrics/stats?agent_id=${agentId}` : '/api/metrics/stats';
        return this.request(endpoint);
    }

    // --- Feedback ---

    async saveFeedback(data: FeedbackRequest): Promise<void> {
        return this.request<void>('/api/feedback', {
            method: 'POST',
            body: JSON.stringify(data),
        });
    }
}

export const apiService = new ApiService(); 