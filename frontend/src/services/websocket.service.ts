type MessageCallback = (data: any) => void;

class WebSocketService {
    private socket: WebSocket | null = null;
    private listeners: Map<string, MessageCallback[]> = new Map();

    connect(clientId: string): WebSocket {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            console.warn('WebSocket is already connected.');
            return this.socket;
        }

        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const url = `${wsProtocol}//${window.location.host}/ws/evaluation/${clientId}`;
        this.socket = new WebSocket(url);

        this.socket.onopen = () => {
            console.log(`WebSocket connected for client: ${clientId}`);
        };

        this.socket.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (this.listeners.has('message')) {
                    this.listeners.get('message')?.forEach(callback => callback(data));
                }
            } catch (error) {
                console.error('Error parsing WebSocket message:', error);
            }
        };

        this.socket.onerror = (error) => {
            console.error('WebSocket error:', error);
            if (this.listeners.has('error')) {
                this.listeners.get('error')?.forEach(callback => callback(error));
            }
        };

        this.socket.onclose = (event) => {
            console.log('WebSocket disconnected:', event.reason);
            if (this.listeners.has('close')) {
                this.listeners.get('close')?.forEach(callback => callback(event));
            }
            this.socket = null;
        };

        return this.socket;
    }

    disconnect() {
        if (this.socket) {
            this.socket.close();
        }
    }

    on(event: 'message' | 'error' | 'close', callback: MessageCallback) {
        if (!this.listeners.has(event)) {
            this.listeners.set(event, []);
        }
        this.listeners.get(event)?.push(callback);
    }

    off(event: 'message' | 'error' | 'close', callback: MessageCallback) {
        if (this.listeners.has(event)) {
            const newListeners = this.listeners.get(event)?.filter(cb => cb !== callback);
            this.listeners.set(event, newListeners || []);
        }
    }
}

export const webSocketService = new WebSocketService(); 