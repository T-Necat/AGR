import React, { useState } from 'react';
import { Box, Button, TextField, CircularProgress, Typography, Card, CardContent, Grid } from '@mui/material';
import { apiService } from '../../services/api.service';
import { SandboxRequest, SandboxResponse } from '../../types/api.types';
import { EvaluationResult } from '../../types/evaluation.types';

const SandboxEvaluator: React.FC = () => {
    const [formData, setFormData] = useState<SandboxRequest>({
        agent_id: 'default-agent',
        query: '',
        agent_goal: 'Kullanıcının sorusunu, sağlanan bilgi tabanına dayanarak doğru ve eksiksiz bir şekilde yanıtlamak.',
        agent_persona: 'Yardımsever, profesyonel ve net bir yapay zeka asistanı.',
        save_to_db: true,
    });
    const [loading, setLoading] = useState(false);
    const [response, setResponse] = useState<SandboxResponse | null>(null);
    const [error, setError] = useState<string | null>(null);

    const handleChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        setFormData({
            ...formData,
            [event.target.name]: event.target.value,
        });
    };

    const handleEvaluate = async (event: React.FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        setLoading(true);
        setError(null);
        setResponse(null);
        try {
            const result = await apiService.evaluateSandbox(formData);
            setResponse(result);
        } catch (err: any) {
            setError(err.message || 'Değerlendirme sırasında bir hata oluştu.');
        } finally {
            setLoading(false);
        }
    };

    const renderMetrics = (metrics: EvaluationResult['metrics']) => {
        return (
            <Grid container spacing={2}>
                {Object.entries(metrics).map(([key, value]) => (
                    value && (
                        <Grid item xs={12} sm={6} md={4} key={key}>
                            <Card variant="outlined">
                                <CardContent>
                                    <Typography variant="h6" component="div" sx={{ textTransform: 'capitalize' }}>
                                        {key.replace(/_/g, ' ')}
                                    </Typography>
                                    <Typography variant="h5" color={value.score > 0.7 ? 'success.main' : value.score > 0.4 ? 'warning.main' : 'error.main'}>
                                        {(value.score * 100).toFixed(1)}%
                                    </Typography>
                                    <Typography variant="body2" color="text.secondary">
                                        {value.reasoning}
                                    </Typography>
                                </CardContent>
                            </Card>
                        </Grid>
                    )
                ))}
            </Grid>
        );
    };
    
    return (
        <Box sx={{ p: 2 }}>
            <Typography variant="h4" gutterBottom>
                Sandbox Değerlendirme
            </Typography>
            <Box component="form" onSubmit={handleEvaluate} sx={{ display: 'flex', flexDirection: 'column', gap: 2, mb: 4 }}>
                <TextField
                    name="query"
                    label="Kullanıcı Sorusu"
                    value={formData.query}
                    onChange={handleChange}
                    required
                    fullWidth
                />
                <TextField
                    name="agent_goal"
                    label="Agent Hedefi"
                    value={formData.agent_goal}
                    onChange={handleChange}
                    required
                    fullWidth
                    multiline
                    rows={2}
                />
                <TextField
                    name="agent_persona"
                    label="Agent Personası"
                    value={formData.agent_persona}
                    onChange={handleChange}
                    required
                    fullWidth
                    multiline
                    rows={2}
                />
                <Button type="submit" variant="contained" disabled={loading}>
                    {loading ? <CircularProgress size={24} /> : 'Değerlendir'}
                </Button>
            </Box>

            {error && (
                <Typography color="error" sx={{ mt: 2 }}>
                    Hata: {error}
                </Typography>
            )}

            {response && (
                <Box sx={{ mt: 4 }}>
                    <Typography variant="h5" gutterBottom>Değerlendirme Sonuçları</Typography>
                    <Card variant="outlined">
                        <CardContent>
                            <Typography variant="h6">Genel Değerlendirme</Typography>
                            <Typography variant="body1" sx={{ whiteSpace: 'pre-wrap' }}>{response.evaluation.reasoning}</Typography>
                            <Typography variant="h5" color="primary.main" sx={{ mt: 1 }}>
                                Genel Skor: {(response.evaluation.overall_score * 100).toFixed(1)}%
                            </Typography>
                        </CardContent>
                    </Card>
                    
                    <Typography variant="h5" gutterBottom sx={{ mt: 4 }}>Metrikler</Typography>
                    {renderMetrics(response.evaluation.metrics)}
                    
                    <Typography variant="h5" gutterBottom sx={{ mt: 4 }}>Agent Yanıtı</Typography>
                    <Card variant="outlined">
                        <CardContent>
                           <Typography variant="body1" sx={{ whiteSpace: 'pre-wrap' }}>{response.agent_response}</Typography>
                        </CardContent>
                    </Card>

                    <Typography variant="h5" gutterBottom sx={{ mt: 4 }}>RAG İçeriği</Typography>
                     <Card variant="outlined">
                        <CardContent>
                           <Typography variant="body1" sx={{ whiteSpace: 'pre-wrap', maxHeight: 200, overflow: 'auto' }}>{response.rag_context}</Typography>
                        </CardContent>
                    </Card>
                </Box>
            )}
        </Box>
    );
};

export default SandboxEvaluator; 