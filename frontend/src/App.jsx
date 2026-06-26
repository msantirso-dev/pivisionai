import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import Layout from './components/Layout';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import CamerasPage from './pages/Cameras';
import EventsPage from './pages/Events';
import RulesPage from './pages/Rules';
import HealthPage from './pages/Health';
import LiveViewPage from './pages/LiveView';
import AIConfigPage from './pages/AIConfig';
import IntegrationsPage from './pages/Integrations';

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route element={<Layout />}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/cameras" element={<CamerasPage />} />
            <Route path="/events" element={<EventsPage />} />
            <Route path="/rules" element={<RulesPage />} />
            <Route path="/health" element={<HealthPage />} />
            <Route path="/live" element={<LiveViewPage />} />
            <Route path="/ai-config" element={<AIConfigPage />} />
            <Route path="/integrations" element={<IntegrationsPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
