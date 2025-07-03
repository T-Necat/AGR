import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Box, CircularProgress, Typography, Alert, Select, MenuItem, FormControl, InputLabel, Card, CardContent, Grid } from "@mui/material";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

// API'den gelen veri yapıları
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

const DashboardPage = () => {
  const { t } = useTranslation();
  const [agents, setAgents] = useState<string[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<string>("");
  const [stats, setStats] = useState<AgentStatsResponse | null>(null);
  const [loading, setLoading] = useState({ agents: true, stats: false });
  const [error, setError] = useState<string | null>(null);

  const API_KEY = "JotformSecretKey-123"; // GÜNCELLENDİ & TODO: Güvenli bir yerden al

  useEffect(() => {
    const fetchAgents = async () => {
      setLoading(prev => ({ ...prev, agents: true }));
      setError(null);
      try {
        const response = await fetch("http://localhost:8000/agents", {
          headers: { "X-API-Key": API_KEY }
        });
        if (!response.ok) throw new Error("Failed to fetch agents");
        const data: string[] = await response.json();
        setAgents(data);
        if (data.length > 0) {
          setSelectedAgent(data[0]);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "An unknown error occurred.");
      } finally {
        setLoading(prev => ({ ...prev, agents: false }));
      }
    };
    fetchAgents();
  }, []);

  useEffect(() => {
    if (!selectedAgent) return;

    const fetchAgentStats = async () => {
      setLoading(prev => ({ ...prev, stats: true }));
      setError(null);
      setStats(null);
      try {
        const response = await fetch(`http://localhost:8000/agent-stats/${selectedAgent}`, {
          headers: { "X-API-Key": API_KEY }
        });
        if (!response.ok) throw new Error(`Failed to fetch stats for agent ${selectedAgent}`);
        const data: AgentStatsResponse = await response.json();
        setStats(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "An unknown error occurred.");
      } finally {
        setLoading(prev => ({ ...prev, stats: false }));
      }
    };
    fetchAgentStats();
  }, [selectedAgent]);

  return (
    <Box sx={{ p: 3, flexGrow: 1 }}>
      <Typography variant="h4" gutterBottom>{t("dashboard_page_title")}</Typography>
      
      {loading.agents ? (
        <CircularProgress />
      ) : error ? (
        <Alert severity="error">{error}</Alert>
      ) : (
        <FormControl fullWidth sx={{ mb: 3 }}>
          <InputLabel id="agent-select-label">Select Agent</InputLabel>
          <Select
            labelId="agent-select-label"
            value={selectedAgent}
            label="Select Agent"
            onChange={(e) => setSelectedAgent(e.target.value as string)}
          >
            {agents.map(agent => (
              <MenuItem key={agent} value={agent}>{agent}</MenuItem>
            ))}
          </Select>
        </FormControl>
      )}

      {loading.stats && <CircularProgress sx={{ display: 'block', margin: 'auto', mt: 4 }} />}
      
      {stats && (
        <Grid container spacing={3}>
          <Grid item xs={12} md={4}>
            <Card>
              <CardContent>
                <Typography color="text.secondary" gutterBottom>Overall Average Score</Typography>
                <Typography variant="h3">{stats.overall_average_score}</Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} md={4}>
             <Card>
              <CardContent>
                <Typography color="text.secondary" gutterBottom>Total Evaluations</Typography>
                <Typography variant="h3">{stats.total_evaluations}</Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12}>
            <Card>
              <CardContent sx={{ height: 400 }}>
                 <Typography variant="h6" gutterBottom>Metrics Performance</Typography>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={stats.metrics} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="metric_name" />
                    <YAxis domain={[0, 1]} />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey="average_score" fill="#8884d8" />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}
    </Box>
  );
};

export default DashboardPage; 