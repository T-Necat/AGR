import React from 'react';
import { Box, Typography, Divider } from '@mui/material';
import SandboxEvaluator from '../components/evaluation/SandboxEvaluator';
import BatchEvaluator from '../components/evaluation/BatchEvaluator';

const EvaluationPage: React.FC = () => {
    return (
        <Box>
            <Typography variant="h3" component="h1" gutterBottom>
                Değerlendirme Araçları
            </Typography>
            <Typography variant="h6" color="text.secondary" paragraph>
                Bu sayfada, AI ajanlarını manuel olarak test edebilir veya toplu halde değerlendirebilirsiniz.
            </Typography>
            <SandboxEvaluator />
            <Divider sx={{ my: 5 }} />
            <BatchEvaluator />
        </Box>
    );
};

export default EvaluationPage; 