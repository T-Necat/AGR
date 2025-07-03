import React, { useState, useEffect } from 'react';
import { Box, LinearProgress, Typography, Alert } from '@mui/material';
import { webSocketService } from '../../services/websocket.service';
import { TaskStatusResponse, TaskStatus } from '../../types/api.types';

interface TaskProgressProps {
    taskId: string;
    onComplete?: (result: any) => void;
}

const TaskProgress: React.FC<TaskProgressProps> = ({ taskId, onComplete }) => {
    const [status, setStatus] = useState<TaskStatus>('PENDING');
    const [progress, setProgress] = useState(0);
    const [result, setResult] = useState<any>(null);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!taskId) return;

        webSocketService.connect(taskId);

        const handleMessage = (data: TaskStatusResponse) => {
            if (data.task_id === taskId) {
                setStatus(data.status);
                if (data.status === 'PROGRESS' && data.progress) {
                    setProgress(data.progress);
                }
                if (data.status === 'SUCCESS') {
                    setResult(data.result);
                    if(onComplete) onComplete(data.result);
                    webSocketService.disconnect();
                }
                if (data.status === 'FAILURE') {
                    setError('Görev başarısız oldu.');
                    setResult(data.result);
                    webSocketService.disconnect();
                }
            }
        };

        const handleError = (err: any) => {
            setError(`WebSocket bağlantı hatası: ${err.message || 'Bilinmeyen hata'}`);
        };

        webSocketService.on('message', handleMessage);
        webSocketService.on('error', handleError);

        return () => {
            webSocketService.off('message', handleMessage);
            webSocketService.off('error', handleError);
            webSocketService.disconnect();
        };
    }, [taskId, onComplete]);

    const getProgressText = () => {
        switch (status) {
            case 'PENDING':
                return 'Görev bekleniyor...';
            case 'PROGRESS':
                return `Değerlendirme sürüyor... ${progress.toFixed(0)}%`;
            case 'SUCCESS':
                return 'Değerlendirme tamamlandı!';
            case 'FAILURE':
                return 'Görev başarısız oldu.';
            default:
                return `Görev durumu: ${status}`;
        }
    }

    return (
        <Box sx={{ width: '100%', my: 2 }}>
            <Typography variant="body1" gutterBottom>{getProgressText()}</Typography>
            {(status === 'PROGRESS' || status === 'PENDING') && (
                 <LinearProgress variant="determinate" value={progress} />
            )}
            {status === 'SUCCESS' && (
                <Alert severity="success">Sonuçlar başarıyla alındı.</Alert>
            )}
            {error && (
                <Alert severity="error">{error}</Alert>
            )}
            {result && status === 'FAILURE' && (
                <pre>{JSON.stringify(result, null, 2)}</pre>
            )}
        </Box>
    );
};

export default TaskProgress; 