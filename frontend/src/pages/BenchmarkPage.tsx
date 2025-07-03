import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Box, CircularProgress, Typography, Alert, Select, MenuItem, FormControl, InputLabel, OutlinedInput, Checkbox, ListItemText, Grid, Paper } from "@mui/material";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { DataGrid, GridColDef } from '@mui/x-data-grid';

// Data structures from the API
interface AgentStat {
  metric_name: string;
  average_score: number;
}

interface AgentStatsResponse {
  agent_id: string;
  total_evaluations: number;
  overall_average_score: number;
  metrics: AgentStat[];
}

const COLORS = ['#8884d8', '#82ca9d', '#ffc658', '#ff8042', '#0088FE', '#00C49F'];

const BenchmarkPage = () => {
  const { t } = useTranslation();
  const [allAgents, setAllAgents] = useState<string[]>([]);
  const [selectedAgents, setSelectedAgents] = useState<string[]>([]);
  const [benchmarkData, setBenchmarkData] = useState<any[]>([]);
  const [loading, setLoading] = useState({ agents: true, stats: false });
  const [error, setError] = useState<string | null>(null);

  const API_KEY = "JotformSecretKey-123"; // GÜNCELLENDİ & TODO: Use secure storage

  useEffect(() => {
    const fetchAgents = async () => {
      setLoading(prev => ({ ...prev, agents: true }));
      try {
        const response = await fetch("http://localhost:8000/agents", { headers: { "X-API-Key": API_KEY } });
        if (!response.ok) throw new Error("Failed to fetch agents list");
        const data: string[] = await response.json();
        setAllAgents(data);
        if (data.length > 1) {
          setSelectedAgents(data.slice(0, 2)); // Select first two by default
        } else {
          setSelectedAgents(data);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setLoading(prev => ({ ...prev, agents: false }));
      }
    };
    fetchAgents();
  }, []);

  useEffect(() => {
    if (selectedAgents.length === 0) {
      setBenchmarkData([]);
      return;
    }

    const fetchAllStats = async () => {
      setLoading(prev => ({ ...prev, stats: true }));
      setError(null);
      try {
        const promises = selectedAgents.map(agentId =>
          fetch(`http://localhost:8000/agent-stats/${agentId}`, { headers: { "X-API-Key": API_KEY } })
            .then(res => res.ok ? res.json() : Promise.reject(`Failed for ${agentId}`))
        );
        const results: AgentStatsResponse[] = await Promise.all(promises);
        transformDataForChart(results);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to fetch benchmark data");
      } finally {
        setLoading(prev => ({ ...prev, stats: false }));
      }
    };

    fetchAllStats();
  }, [selectedAgents]);
  
  const transformDataForChart = (data: AgentStatsResponse[]) => {
    const transformed: { [key: string]: any } = {};
    data.forEach(agentStats => {
        agentStats.metrics.forEach(metric => {
            if (!transformed[metric.metric_name]) {
                transformed[metric.metric_name] = { metric_name: metric.metric_name };
            }
            transformed[metric.metric_name][agentStats.agent_id] = metric.average_score.toFixed(3);
        });
    });
    setBenchmarkData(Object.values(transformed));
  };
  
  const columns: GridColDef[] = [
      { field: 'metric_name', headerName: 'Metric', flex: 1, sortable: false },
      ...selectedAgents.map(agentId => ({
          field: agentId,
          headerName: agentId,
          flex: 1,
          type: 'number',
      }))
  ];

  return (
    <Box sx={{ p: 3, flexGrow: 1 }}>
      <Typography variant="h4" gutterBottom>{t("benchmark_page_title")}</Typography>
      
      {loading.agents ? <CircularProgress /> : (
        <FormControl sx={{ mb: 3, width: '100%' }}>
          <InputLabel id="multiple-agent-checkbox-label">Compare Agents</InputLabel>
          <Select
            labelId="multiple-agent-checkbox-label"
            multiple
            value={selectedAgents}
            onChange={(e) => setSelectedAgents(e.target.value as string[])}
            input={<OutlinedInput label="Compare Agents" />}
            renderValue={(selected) => (selected as string[]).join(', ')}
          >
            {allAgents.map((agent) => (
              <MenuItem key={agent} value={agent}>
                <Checkbox checked={selectedAgents.indexOf(agent) > -1} />
                <ListItemText primary={agent} />
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      )}

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      {loading.stats && <CircularProgress sx={{ display: 'block', margin: 'auto', mt: 4 }} />}

      {benchmarkData.length > 0 && (
          <Grid container spacing={3}>
              <Grid item xs={12}>
                  <Paper sx={{ p: 2, height: 400 }}>
                      <Typography variant="h6">Metrics Comparison</Typography>
                      <ResponsiveContainer width="100%" height="100%">
                          <BarChart data={benchmarkData} margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
                              <CartesianGrid strokeDasharray="3 3" />
                              <XAxis dataKey="metric_name" angle={-15} textAnchor="end" height={60} />
                              <YAxis domain={[0, 1]} />
                              <Tooltip />
                              <Legend />
                              {selectedAgents.map((agentId, index) => (
                                  <Bar key={agentId} dataKey={agentId} fill={COLORS[index % COLORS.length]} />
                              ))}
                          </BarChart>
                      </ResponsiveContainer>
                  </Paper>
              </Grid>
              <Grid item xs={12}>
                   <Paper sx={{ p: 2, height: 400, width: '100%' }}>
                        <Typography variant="h6">Comparison Table</Typography>
                         <DataGrid
                            rows={benchmarkData.map((d, i) => ({ id: i, ...d }))}
                            columns={columns}
                            hideFooter
                            autoHeight
                          />
                   </Paper>
              </Grid>
          </Grid>
      )}
    </Box>
  );
};

export default BenchmarkPage; 