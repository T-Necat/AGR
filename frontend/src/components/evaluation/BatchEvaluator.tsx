import React, { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { Box, Button, Typography, Alert, Paper } from '@mui/material';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import { apiService } from '../../services/api.service';
import TaskProgress from '../common/TaskProgress';

const BatchEvaluator: React.FC = () => {
    const [file, setFile] = useState<File | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);
    const [taskId, setTaskId] = useState<string | null>(null);
    const [finalResult, setFinalResult] = useState<any>(null);

    const onDrop = useCallback((acceptedFiles: File[], fileRejections: any[]) => {
        setError(null);
        setTaskId(null);
        setFinalResult(null);

        if (fileRejections.length > 0) {
            setError('Geçersiz dosya türü. Lütfen sadece .csv uzantılı bir dosya yükleyin.');
            return;
        }
        if (acceptedFiles.length > 0) {
            setFile(acceptedFiles[0]);
        }
    }, []);

    const { getRootProps, getInputProps, isDragActive } = useDropzone({
        onDrop,
        accept: { 'text/csv': ['.csv'] },
        maxFiles: 1,
    });

    const handleUpload = async () => {
        if (!file) {
            setError('Lütfen bir dosya seçin.');
            return;
        }
        setLoading(true);
        setError(null);
        try {
            const response = await apiService.uploadBatchFile(file);
            setTaskId(response.task_id);
        } catch (err: any) {
            setError(err.message || 'Dosya yüklenirken bir hata oluştu.');
        } finally {
            setLoading(false);
        }
    };
    
    const handleTaskComplete = (result: any) => {
        setFinalResult(result);
    };

    return (
        <Box sx={{ p: 2, mt: 4 }}>
            <Typography variant="h4" gutterBottom>
                Toplu Değerlendirme (CSV)
            </Typography>
            <Paper
                {...getRootProps()}
                sx={{
                    p: 4,
                    border: '2px dashed',
                    borderColor: isDragActive ? 'primary.main' : 'grey.500',
                    textAlign: 'center',
                    cursor: 'pointer',
                    mb: 2
                }}
            >
                <input {...getInputProps()} />
                <UploadFileIcon sx={{ fontSize: 60, color: 'grey.500' }} />
                {isDragActive ? (
                    <Typography>Dosyayı buraya bırakın...</Typography>
                ) : (
                    <Typography>Değerlendirme için CSV dosyasını buraya sürükleyin veya tıklayarak seçin.</Typography>
                )}
            </Paper>

            {file && <Typography sx={{ mb: 2 }}>Seçilen dosya: {file.name}</Typography>}
            
            <Button
                variant="contained"
                onClick={handleUpload}
                disabled={!file || loading}
            >
                {loading ? 'Yükleniyor...' : 'Yükle ve Değerlendirmeyi Başlat'}
            </Button>

            {error && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>}
            
            {taskId && <TaskProgress taskId={taskId} onComplete={handleTaskComplete} />}

            {finalResult && (
                 <Box sx={{ mt: 4 }}>
                    <Typography variant="h5">Değerlendirme Sonuçları</Typography>
                    <Paper sx={{ p: 2, maxHeight: 400, overflow: 'auto' }}>
                        <pre>{JSON.stringify(finalResult, null, 2)}</pre>
                    </Paper>
                </Box>
            )}
        </Box>
    );
};

export default BatchEvaluator; 