import { useState } from 'react';
import { NavLink } from 'react-router-dom';
import {
  MessageSquare,
  Files,
  LogOut,
  User,
  Shield,
  Building2,
  Key,
  X,
  ChevronLeft,
  ChevronRight,
  Database,
  FilePenLine,
} from 'lucide-react';
import clsx from 'clsx';
import { motion, AnimatePresence } from 'framer-motion';
import { getStoredUser, clearAuth, ApiClient } from '../api/client';

interface SidebarProps {
  onLogout: () => void;
}

export function Sidebar({ onLogout }: SidebarProps) {
  const user = getStoredUser();
  const isAdmin = user?.role === 'system_admin' || user?.role === 'org_admin';

  const [showPasswordModal, setShowPasswordModal] = useState(false);
  const [oldPassword, setOldPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [passwordError, setPasswordError] = useState('');
  const [passwordSuccess, setPasswordSuccess] = useState('');
  const [isSubmittingPassword, setIsSubmittingPassword] = useState(false);
  const [isCollapsed, setIsCollapsed] = useState(false);

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!oldPassword || !newPassword) return;
    if (newPassword.length < 6) {
      setPasswordError('Mật khẩu mới phải từ 6 ký tự trở lên');
      return;
    }
    setIsSubmittingPassword(true);
    setPasswordError('');
    setPasswordSuccess('');
    try {
      await ApiClient.changePassword({ old_password: oldPassword, new_password: newPassword });
      setPasswordSuccess('Đổi mật khẩu thành công!');
      setTimeout(() => {
        setShowPasswordModal(false);
        setOldPassword('');
        setNewPassword('');
        setPasswordSuccess('');
      }, 1500);
    } catch (err: any) {
      setPasswordError(err.response?.data?.detail || 'Lỗi khi đổi mật khẩu');
    } finally {
      setIsSubmittingPassword(false);
    }
  };

  const navItems = [
    { name: 'Trang chủ', path: '/', icon: Files },
    { name: 'Kho dữ liệu', path: '/data', icon: Database },
    { name: 'Xây dựng dự thảo', path: '/drafting', icon: FilePenLine },
    { name: 'Trợ lý Chat', path: '/chat', icon: MessageSquare },
  ];

  const handleLogout = () => {
    clearAuth();
    onLogout();
  };

  const roleLabel = user?.role === 'system_admin' ? 'Admin HT'
    : user?.role === 'org_admin' ? 'Admin ĐV' : null;

  return (
    <div
      className={clsx(
        "h-screen bg-slate-900 border-r border-slate-800 flex flex-col items-start py-6 text-slate-300 transition-all duration-300 ease-out shrink-0",
        isCollapsed ? "w-20 px-3" : "w-64 px-4"
      )}
    >
      <div
        className={clsx(
          "flex items-center gap-3 mb-10 w-full",
          isCollapsed ? "justify-center px-0" : "px-2"
        )}
      >
        <div className="w-10 h-10 rounded-xl overflow-hidden bg-slate-950 flex items-center justify-center shadow-lg shadow-slate-950/20">
          <img src="/icon.png" alt="TKO" className="w-full h-full object-contain" />
        </div>
        {!isCollapsed && (
          <div>
            <h1 className="text-lg font-bold text-white tracking-tight">Trợ lý Ơi</h1>
            <p className="text-xs text-slate-400 font-medium tracking-wide">HỖ TRỢ SOẠN THẢO VB</p>
          </div>
        )}
      </div>

      <nav className="flex-1 w-full space-y-2">
        {navItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) =>
              clsx(
                "relative flex items-center gap-3 px-3 py-3 rounded-xl transition-all duration-300 ease-out group font-medium",
                isCollapsed && "justify-center",
                isActive ? "text-white bg-blue-600/10" : "hover:bg-slate-800 hover:text-slate-100"
              )
            }
            title={isCollapsed ? item.name : undefined}
          >
            {({ isActive }) => (
              <>
                {isActive && (
                  <motion.div
                    layoutId="active-nav-indicator"
                    className="absolute left-0 w-1 h-6 bg-blue-500 rounded-r-full"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                  />
                )}
                <item.icon className={clsx("w-5 h-5", isActive ? "text-blue-500" : "text-slate-400 group-hover:text-blue-400")} />
                {!isCollapsed && item.name}
              </>
            )}
          </NavLink>
        ))}

        {/* Admin Section */}
        {isAdmin && (
          <>
            <div className={clsx("pt-4 pb-1 px-3", isCollapsed && "sr-only")}>
              <div className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Quản trị</div>
            </div>
            <NavLink
              to="/admin"
              className={({ isActive }) =>
                clsx(
                  "relative flex items-center gap-3 px-3 py-3 rounded-xl transition-all duration-300 ease-out group font-medium",
                  isCollapsed && "justify-center",
                  isActive ? "text-white bg-amber-600/10" : "hover:bg-slate-800 hover:text-slate-100"
                )
              }
              title={isCollapsed ? "Quản trị hệ thống" : undefined}
            >
              {({ isActive }) => (
                <>
                  {isActive && (
                    <motion.div
                      layoutId="active-nav-indicator"
                      className="absolute left-0 w-1 h-6 bg-amber-500 rounded-r-full"
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                    />
                  )}
                  <Shield className={clsx("w-5 h-5", isActive ? "text-amber-500" : "text-slate-400 group-hover:text-amber-400")} />
                  {!isCollapsed && "Quản trị hệ thống"}
                </>
              )}
            </NavLink>
          </>
        )}
      </nav>

      {/* User info + Logout */}
      <div className="w-full mt-auto space-y-2">
        {user && (
          <div
            className={clsx(
              "flex items-center gap-3 px-3 py-3 bg-slate-800/50 rounded-xl",
              isCollapsed && "justify-center"
            )}
          >
            <div className="w-8 h-8 rounded-full bg-blue-600/20 flex items-center justify-center">
              <User size={16} className="text-blue-400" />
            </div>
            {!isCollapsed && (
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <p className="text-sm font-semibold text-white truncate">{user.full_name || user.username}</p>
                  {roleLabel && (
                    <span className="px-1.5 py-0.5 text-[9px] font-bold bg-amber-500/20 text-amber-400 rounded-md uppercase shrink-0">
                      {roleLabel}
                    </span>
                  )}
                </div>
                {user.org_name ? (
                  <div className="flex items-center gap-1 text-[10px] text-slate-500 truncate">
                    <Building2 size={10} className="shrink-0" />
                    {user.org_name}
                  </div>
                ) : (
                  <p className="text-xs text-slate-500 truncate">@{user.username}</p>
                )}
              </div>
            )}
          </div>
        )}
        <button
          onClick={() => setIsCollapsed((current) => !current)}
          className={clsx(
            "flex items-center gap-3 px-3 py-3 w-full rounded-xl hover:bg-slate-800 text-slate-400 hover:text-white transition-colors text-sm font-medium",
            isCollapsed && "justify-center"
          )}
          title={isCollapsed ? "Mở rộng menu" : "Thu gọn menu"}
        >
          {isCollapsed ? (
            <ChevronRight className="w-5 h-5" />
          ) : (
            <ChevronLeft className="w-5 h-5" />
          )}
          {!isCollapsed && "Thu gọn menu"}
        </button>
        <button
          onClick={() => setShowPasswordModal(true)}
          className={clsx(
            "flex items-center gap-3 px-3 py-3 w-full rounded-xl hover:bg-slate-800 text-slate-400 hover:text-white transition-colors text-sm font-medium",
            isCollapsed && "justify-center"
          )}
          title={isCollapsed ? "Đổi mật khẩu" : undefined}
        >
          <Key className="w-5 h-5" />
          {!isCollapsed && "Đổi mật khẩu"}
        </button>
        <button
          onClick={handleLogout}
          className={clsx(
            "flex items-center gap-3 px-3 py-3 w-full rounded-xl hover:bg-rose-500/10 text-slate-400 hover:text-rose-400 transition-colors text-sm font-medium",
            isCollapsed && "justify-center"
          )}
          title={isCollapsed ? "Đăng xuất" : undefined}
        >
          <LogOut className="w-5 h-5" />
          {!isCollapsed && "Đăng xuất"}
        </button>
      </div>

      {/* Change Password Modal */}
      <AnimatePresence>
        {showPasswordModal && (
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4"
            onClick={() => setShowPasswordModal(false)}
          >
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.9, opacity: 0 }}
              onClick={(e) => e.stopPropagation()}
              className="bg-white rounded-3xl p-8 w-full max-w-sm shadow-2xl"
            >
              <div className="flex justify-between items-center mb-6">
                <h2 className="text-xl font-bold text-slate-900">Đổi mật khẩu</h2>
                <button onClick={() => setShowPasswordModal(false)} className="p-2 hover:bg-slate-100 rounded-lg transition-colors">
                  <X size={20} className="text-slate-400" />
                </button>
              </div>
              <form onSubmit={handleChangePassword} className="space-y-4">
                <div>
                  <label className="block text-sm font-semibold text-slate-700 mb-2">Mật khẩu hiện tại</label>
                  <input
                    type="password" required
                    value={oldPassword} onChange={(e) => setOldPassword(e.target.value)}
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all"
                  />
                </div>
                <div>
                  <label className="block text-sm font-semibold text-slate-700 mb-2">Mật khẩu mới</label>
                  <input
                    type="password" required
                    value={newPassword} onChange={(e) => setNewPassword(e.target.value)}
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all"
                  />
                </div>
                {passwordError && (
                  <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-rose-600 text-sm">{passwordError}</div>
                )}
                {passwordSuccess && (
                  <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl text-emerald-600 text-sm">{passwordSuccess}</div>
                )}
                <div className="pt-2">
                  <button type="submit" disabled={isSubmittingPassword}
                    className="w-full py-3 bg-blue-600 outline-none border-none text-white rounded-xl font-medium hover:bg-blue-700 transition-colors flex items-center justify-center gap-2 shadow-lg shadow-blue-600/20 cursor-pointer">
                    {isSubmittingPassword ? 'Đang cập nhật...' : 'Cập nhật mật khẩu'}
                  </button>
                </div>
              </form>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
