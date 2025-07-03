import { Routes, Route } from 'react-router-dom';
import HomePage from './pages/HomePage';
import DashboardPage from './pages/DashboardPage';
import BenchmarkPage from './pages/BenchmarkPage';
import DevPage from './pages/DevPage';
import Layout from './components/Layout';
import EvaluationPage from './pages/EvaluationPage';

function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<HomePage />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="benchmark" element={<BenchmarkPage />} />
        <Route path="dev" element={<DevPage />} />
        <Route path="evaluation" element={<EvaluationPage />} />
      </Route>
    </Routes>
  );
}

export default App;
