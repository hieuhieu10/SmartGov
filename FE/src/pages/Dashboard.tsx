import { useEffect, useState } from 'react';
import { ApiClient } from '../api/client';
import type { Repository, StorageUsage } from '../api/client';
import { motion } from 'framer-motion';
import { Database, FileText, MessageSquare, Server, FolderOpen, Activity } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

export function Dashboard() {
  const [health, setHealth] = useState<any>(null);
  const [repos, setRepos] = useState<Repository[]>([]);
  const [storageUsage, setStorageUsage] = useState<StorageUsage | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    ApiClient.getHealth().then(setHealth).catch(console.error);
    ApiClient.getRepositories().then(setRepos).catch(console.error);
    ApiClient.getStorageUsage().then(setStorageUsage).catch(console.error);
  }, []);

  const totalDocs = repos.reduce((sum, r) => sum + (r.document_count || 0), 0);

  const statCards = [
    { title: 'Kho Dữ liệu', value: repos.filter(r => !r.is_shared).length, icon: Database, color: 'text-indigo-500', bg: 'bg-indigo-500/10', gradient: 'from-indigo-500 to-blue-500' },
    { title: 'Tài liệu', value: totalDocs, icon: FileText, color: 'text-emerald-500', bg: 'bg-emerald-500/10', gradient: 'from-emerald-500 to-teal-500', detail: storageUsage ? `${storageUsage.used_label}/${storageUsage.limit_label}` : 'Đang tải dung lượng' },
    { title: 'Trạng thái', value: health?.status === 'ok' ? 'Hoạt động' : 'Đang tải', icon: Server, color: 'text-blue-500', bg: 'bg-blue-500/10', gradient: 'from-blue-500 to-cyan-500' },
    { title: 'Dịch vụ AI', value: (health?.ai_service === 'authenticated' || health?.ai_service === 'ok') ? 'Sẵn sàng' : 'Lỗi/Chưa xác thực', icon: Activity, color: 'text-amber-500', bg: 'bg-amber-500/10', gradient: 'from-amber-500 to-orange-500' },
  ];

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="max-w-6xl mx-auto space-y-8"
    >
      <header className="mb-8">
        <h1 className="text-3xl font-bold font-sans text-slate-900 tracking-tight">Trang chủ</h1>
        <p className="text-slate-500 mt-2">Theo dõi tình trạng hoạt động và dữ liệu của Office AI.</p>
      </header>

      {/* Stat Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {statCards.map((item, idx) => (
          <motion.div
            key={item.title}
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: idx * 0.1 }}
            className="p-6 rounded-2xl bg-white border border-slate-200 shadow-sm hover:shadow-md transition-shadow group relative overflow-hidden"
          >
            <div className={`absolute -right-6 -top-6 w-24 h-24 rounded-full ${item.bg} blur-2xl group-hover:scale-150 transition-transform duration-700`} />
            <div className="flex items-center justify-between mb-4 relative">
              <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wider">{item.title}</h3>
              <div className={`p-2 rounded-xl ${item.bg}`}>
                <item.icon className={`w-5 h-5 ${item.color}`} />
              </div>
            </div>
            <p className="text-3xl font-bold text-slate-900 relative">
              {item.value}
            </p>
            {'detail' in item && (
              <div className="mt-3 relative">
                <div className="flex items-center justify-between text-xs text-slate-500 mb-1">
                  <span>Dung lượng</span>
                  <span className="font-semibold text-slate-600">{item.detail}</span>
                </div>
                <div className="h-2 rounded-full bg-slate-100 overflow-hidden">
                  <div
                    className="h-full bg-emerald-500 rounded-full"
                    style={{ width: `${Math.min(storageUsage?.percent || 0, 100)}%` }}
                  />
                </div>
              </div>
            )}
          </motion.div>
        ))}
      </div>

      {/* Repository Quick Access */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="p-6 border-b border-slate-200 flex justify-between items-center">
            <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
              <FolderOpen className="text-blue-600" size={20} /> Kho dữ liệu gần đây
            </h3>
            <button
              onClick={() => navigate('/repositories')}
              className="text-sm text-blue-600 hover:text-blue-700 font-medium"
            >
              Xem tất cả →
            </button>
          </div>

          {repos.length === 0 ? (
            <div className="p-12 text-center text-slate-400">
              <Database size={40} className="mx-auto mb-3 text-slate-300" />
              <p>Chưa có kho dữ liệu nào.</p>
              <button
                onClick={() => navigate('/repositories')}
                className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-xl text-sm font-medium hover:bg-blue-700 transition-colors"
              >
                Tạo kho đầu tiên
              </button>
            </div>
          ) : (
            <div className="divide-y divide-slate-100">
              {repos.slice(0, 5).map(repo => (
                <div key={repo.id} className="px-6 py-4 flex items-center justify-between hover:bg-slate-50 transition-colors">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-blue-50 flex items-center justify-center">
                      <Database size={18} className="text-blue-600" />
                    </div>
                    <div>
                      <p className="font-semibold text-slate-800">{repo.name}</p>
                      <p className="text-xs text-slate-500">{repo.document_count} tài liệu</p>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => navigate(`/chat?repo=${repo.id}`)}
                      className="px-3 py-1.5 text-xs font-medium bg-blue-50 text-blue-700 rounded-lg hover:bg-blue-100 transition-colors flex items-center gap-1"
                    >
                      <MessageSquare size={12} /> Chat
                    </button>
                    <button
                      onClick={() => navigate(`/drafting?repo=${repo.id}`)}
                      className="px-3 py-1.5 text-xs font-medium bg-indigo-50 text-indigo-700 rounded-lg hover:bg-indigo-100 transition-colors flex items-center gap-1"
                    >
                      <FileText size={12} /> Soạn VB
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Backend Status */}
        <div className="p-6 rounded-2xl bg-gradient-to-br from-slate-900 to-indigo-900 shadow-xl text-white">
          <h3 className="text-lg font-bold mb-4 flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full ${health?.status === 'ok' ? 'bg-emerald-400 animate-pulse' : 'bg-amber-400'}`} />
            Kết nối hệ thống
          </h3>
          <ul className="space-y-4">
            <li className="flex justify-between items-center text-sm border-b border-white/10 pb-3">
              <span className="text-slate-300 font-medium">Phiên bản</span>
              <span className="px-2 py-1 bg-blue-500/20 text-blue-300 rounded-md text-xs font-bold">{health?.version || '...'}</span>
            </li>
            <li className="flex justify-between items-center text-sm border-b border-white/10 pb-3">
              <span className="text-slate-300 font-medium">Dịch vụ AI</span>
              <span className={`px-2 py-1 rounded-md text-xs font-bold ${
                (health?.ai_service === 'authenticated' || health?.ai_service === 'ok')
                  ? 'bg-emerald-500/20 text-emerald-300'
                  : 'bg-rose-500/20 text-rose-300'
              }`}>
                {(health?.ai_service === 'authenticated' || health?.ai_service === 'ok') ? 'OK' : 'Error'}
              </span>
            </li>
            <li className="flex justify-between items-center text-sm">
              <span className="text-slate-300 font-medium">API Status</span>
              <span className={`px-2 py-1 rounded-md text-xs font-bold ${
                health?.status === 'ok'
                  ? 'bg-emerald-500/20 text-emerald-300'
                  : 'bg-amber-500/20 text-amber-300'
              }`}>
                {health?.status || '...'}
              </span>
            </li>
          </ul>
        </div>
      </div>
    </motion.div>
  );
}
