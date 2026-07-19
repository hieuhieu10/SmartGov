import { useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Sidebar } from './components/Sidebar';
import { ChatAssistant } from './pages/ChatAssistant';
import { DraftingPage } from './pages/DraftingPage';
import { AdminPanel } from './pages/AdminPanel';
import { LoginPage } from './pages/LoginPage';
import { HomePage } from './pages/HomePage';
import { DataLibrary } from './pages/DataLibrary';
import { getStoredToken, getStoredUser } from './api/client';
import { Menu } from 'lucide-react';

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(!!getStoredToken());
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  const handleLoginSuccess = () => {
    setIsAuthenticated(true);
  };

  const handleLogout = () => {
    setIsMobileMenuOpen(false);
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
        <Sidebar
          onLogout={handleLogout}
          isMobileOpen={isMobileMenuOpen}
          onClose={() => setIsMobileMenuOpen(false)}
        />
        {isMobileMenuOpen && (
          <button
            type="button"
            aria-label="Đóng menu"
            className="fixed inset-0 z-40 bg-slate-950/50 backdrop-blur-sm md:hidden"
            onClick={() => setIsMobileMenuOpen(false)}
          />
        )}
        <main className="flex-1 overflow-auto bg-slate-50 p-4 md:p-6">
          <header className="mb-4 flex items-center justify-between rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm md:hidden">
            <div className="flex items-center gap-2">
              <img src="/icon.png" alt="TKO" className="h-8 w-8 rounded-lg bg-slate-950 object-contain" />
              <span className="font-bold text-slate-800">Trợ lý Ơi</span>
            </div>
            <button
              type="button"
              aria-label="Mở menu"
              className="rounded-lg p-2 text-slate-600 transition-colors hover:bg-slate-100 hover:text-blue-600"
              onClick={() => setIsMobileMenuOpen(true)}
            >
              <Menu size={22} />
            </button>
          </header>
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/data" element={<DataLibrary />} />
            <Route path="/chat" element={<ChatAssistant />} />
            {isAdmin && <Route path="/admin" element={<AdminPanel />} />}
            {/* Legacy routes redirect */}
            <Route path="/repositories" element={<Navigate to="/data" />} />
            <Route path="/documents" element={<Navigate to="/data" />} />
            <Route path="/templates" element={<Navigate to="/" />} />
            <Route path="/drafting" element={<DraftingPage />} />
            <Route path="/audio-to-minutes" element={<Navigate to="/" />} />
            <Route path="/login" element={<Navigate to="/" />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

export default App;
