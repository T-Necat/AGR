import { useTranslation } from "react-i18next";
import { Link as RouterLink } from "react-router-dom";
import { Box, Typography, Card, CardActionArea, CardContent } from "@mui/material";
import DashboardIcon from '@mui/icons-material/Dashboard';
import BarChartIcon from '@mui/icons-material/BarChart';
import CodeIcon from '@mui/icons-material/Code';
import type { ReactNode } from "react";

interface CardInfo {
    title: string;
    description: string;
    link: string;
    icon: ReactNode;
}

const cardInfo: CardInfo[] = [
    {
        title: "Jotform User Dashboard",
        description: "Analyze your own agent's performance with detailed metrics and insights.",
        link: "/dashboard",
        icon: <DashboardIcon sx={{ fontSize: 60 }} color="primary" />
    },
    {
        title: "Benchmark Agents",
        description: "Compare the performance of different test agents against various metrics.",
        link: "/benchmark",
        icon: <BarChartIcon sx={{ fontSize: 60 }} color="primary" />
    },
    {
        title: "Developer Raw Data",
        description: "Access raw evaluation data, logs, and detailed session traces.",
        link: "/dev",
        icon: <CodeIcon sx={{ fontSize: 60 }} color="primary" />
    }
];

const HomePage = () => {
  const { t } = useTranslation();

  return (
    <Box>
      <Typography variant="h3" component="h1" gutterBottom>
        {t("home_page_title")}
      </Typography>
      <Typography variant="h6" color="text.secondary" paragraph>
        This platform provides a comprehensive suite of tools to automatically evaluate AI agents based on real-world usage data. Explore the dashboards to gain deep insights into your agent's behavior, identify outliers, and compare performance benchmarks.
      </Typography>
      
      <Box display="flex" flexWrap="wrap" mt={4} mx={-2}>
        {cardInfo.map((card) => (
            <Box key={card.title} width={{ xs: 1, md: 1/3 }} p={2}>
                <Card sx={{ height: '100%' }}>
                    <CardActionArea component={RouterLink} to={card.link} sx={{ height: '100%' }}>
                        <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', p: 3 }}>
                           {card.icon}
                           <CardContent>
                                <Typography gutterBottom variant="h5" component="div" align="center">
                                    {card.title}
                                </Typography>
                                <Typography variant="body2" color="text.secondary" align="center">
                                    {card.description}
                                </Typography>
                           </CardContent>
                        </Box>
                    </CardActionArea>
                </Card>
            </Box>
        ))}
      </Box>
    </Box>
  );
};

export default HomePage; 