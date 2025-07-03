import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { DataGrid, GridColDef, GridRowParams } from '@mui/x-data-grid';
import { Box, CircularProgress, Typography, Alert, Drawer, List, ListItem, ListItemText, Divider, Card, CardContent, CardHeader } from "@mui/material";

// API'den gelen veri yapısını tanımla
interface MetricResult {
  metric_name: string;
  score: number;
  reasoning: string;
}

interface EvaluationSession {
  id: number;
  session_id: string;
  created_at: string;
  user_query: string;
  agent_response: string;
  rag_context: string;
  agent_goal: string;
  agent_persona: string;
  metric_results: MetricResult[];
}

const DevPage = () => {
  const { t } = useTranslation();
  const [evaluations, setEvaluations] = useState<EvaluationSession[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedRow, setSelectedRow] = useState<EvaluationSession | null>(null);

  useEffect(() => {
    const fetchEvaluations = async () => {
      setLoading(true);
      setError(null);
      try {
        // TODO: API anahtarını güvenli bir yerden al (örneğin, ortam değişkeni)
        const response = await fetch("http://localhost:8000/evaluations", {
          headers: {
            "X-API-Key": "JotformSecretKey-123"
          }
        });
        if (!response.ok) {
          throw new Error(`API call failed with status: ${response.status}`);
        }
        const data: EvaluationSession[] = await response.json();
        setEvaluations(data);
      } catch (err) {
        if (err instanceof Error) {
            setError(`Failed to fetch evaluations: ${err.message}`);
        } else {
            setError("An unknown error occurred.");
        }
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    fetchEvaluations();
  }, []);

  const handleRowClick = (params: GridRowParams) => {
    setSelectedRow(params.row as EvaluationSession);
  };

  const handleDrawerClose = () => {
    setSelectedRow(null);
  };

  const columns: GridColDef[] = [
    { field: 'id', headerName: 'ID', width: 90 },
    { field: 'session_id', headerName: 'Session ID', width: 150 },
    {
      field: 'created_at',
      headerName: 'Timestamp',
      width: 200,
      valueFormatter: (params) => new Date(params.value).toLocaleString(),
    },
    { field: 'user_query', headerName: 'User Query', flex: 1 },
    { field: 'agent_response', headerName: 'Agent Response', flex: 1 },
  ];

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '80vh' }}>
        <CircularProgress />
        <Typography ml={2}>Loading evaluations...</Typography>
      </Box>
    );
  }

  if (error) {
    return <Alert severity="error">{error}</Alert>;
  }
  
  return (
    <Box sx={{ display: 'flex', height: '95vh' }}>
      <Box sx={{ flexGrow: 1, height: '100%', padding: 2 }}>
        <Typography variant="h4" gutterBottom>{t("dev_page_title")}</Typography>
        <Link to="/">Go to Home</Link>
        <Box sx={{ height: 'calc(100% - 100px)', width: '100%', mt: 2 }}>
          <DataGrid
            rows={evaluations}
            columns={columns}
            onRowClick={handleRowClick}
            initialState={{
              pagination: {
                paginationModel: {
                  pageSize: 15,
                },
              },
            }}
            pageSizeOptions={[5, 10, 15, 25]}
            checkboxSelection
            disableRowSelectionOnClick
          />
        </Box>
      </Box>
      <Drawer
        anchor="right"
        open={selectedRow !== null}
        onClose={handleDrawerClose}
      >
        <Box
          sx={{ width: 500, padding: 2 }}
          role="presentation"
        >
          {selectedRow && (
            <>
              <Typography variant="h5" gutterBottom>Session Details</Typography>
              <Typography variant="subtitle1" color="text.secondary">{selectedRow.session_id}</Typography>
              <Divider sx={{ my: 2 }} />
              
              <Card variant="outlined" sx={{ mb: 2 }}>
                <CardHeader title="Metrics" />
                <CardContent>
                  <DataGrid
                    rows={selectedRow.metric_results.map((m, i) => ({ id: i, ...m }))}
                    columns={[
                      { field: 'metric_name', headerName: 'Metric', flex: 1 },
                      { field: 'score', headerName: 'Score', width: 80 },
                    ]}
                    autoHeight
                    density="compact"
                    hideFooter
                  />
                </CardContent>
              </Card>

              <List dense>
                <ListItem>
                  <ListItemText primary="User Query" secondary={selectedRow.user_query} />
                </ListItem>
                <Divider component="li" />
                <ListItem>
                  <ListItemText primary="Agent Response" secondary={selectedRow.agent_response} />
                </ListItem>
                <Divider component="li" />
                <ListItem>
                  <ListItemText primary="RAG Context" secondary={selectedRow.rag_context} />
                </ListItem>
                 <Divider component="li" />
                <ListItem>
                  <ListItemText primary="Agent Goal" secondary={selectedRow.agent_goal} />
                </ListItem>
                 <Divider component="li" />
                <ListItem>
                  <ListItemText primary="Agent Persona" secondary={selectedRow.agent_persona} />
                </ListItem>
              </List>
            </>
          )}
        </Box>
      </Drawer>
    </Box>
  );
};

export default DevPage; 