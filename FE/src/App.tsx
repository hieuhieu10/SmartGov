import { useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Sidebar } from './components/Sidebar';
import { ChatAssistant } from './pages/ChatAssistant';
import { RepositoryManager } from './pages/DocumentManager';
import { AdminPanel } from './pages/AdminPanel';
import { LoginPage } from './pages/LoginPage';
import { getStoredToken, getStoredUser } from './api/client';

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(!!getStoredToken());

  const handleLoginSuccess = () => {
    setIsAuthenticated(true);
  };

  const handleLogout = () => {
    setIsAuthenticated(false);
  };

  if (!isAuthenticated) {
    return (
      <BrowserRouter>
        <Routes>
          <Route path="*" element={<LoginPage onLoginSuccess={handleLoginSuccess} />} />
        </Routes>
      </BrowserRouter>
    );
  }

  const user = getStoredUser();
  const isAdmin = user?.role === 'system_admin' || user?.role === 'org_admin';

  return (
    <BrowserRouter>
      <div className="flex h-screen w-full bg-slate-50/50">
        <Sidebar onLogout={handleLogout} />
        <main className="flex-1 overflow-auto bg-slate-50 p-6">
          <Routes>
            <Route path="/" element={<RepositoryManager />} />
            <Route path="/chat" element={<ChatAssistant />} />
            {isAdmin && <Route path="/admin" element={<AdminPanel />} />}
            {/* Legacy routes redirect */}
            <Route path="/repositories" element={<Navigate to="/" />} />
            <Route path="/documents" element={<Navigate to="/" />} />
            <Route path="/templates" element={<Navigate to="/" />} />
            <Route path="/drafting" element={<Navigate to="/" />} />
            <Route path="/audio-to-minutes" element={<Navigate to="/" />} />
            <Route path="/login" element={<Navigate to="/" />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

export default App;
