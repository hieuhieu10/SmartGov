import { useState, useEffect } from 'react';
import { ApiClient, getStoredUser } from '../api/client';
import type { OrgInfo, DeptInfo, AdminUser } from '../api/client';
import { motion, AnimatePresence } from 'framer-motion';
import { Building2, Users, FolderTree, Plus, Trash2, Edit3, Save, X, Shield, UserPlus, Loader2, ChevronRight, Cpu } from 'lucide-react';

type Tab = 'orgs' | 'depts' | 'users';

export function AdminPanel() {
  const currentUser = getStoredUser();
  const isSystemAdmin = currentUser?.role === 'system_admin';

  const [activeTab, setActiveTab] = useState<Tab>('orgs');
  const [orgs, setOrgs] = useState<OrgInfo[]>([]);
  const [depts, setDepts] = useState<DeptInfo[]>([]);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [selectedOrg, setSelectedOrg] = useState<OrgInfo | null>(null);
  const [loading, setLoading] = useState(false);

  // Forms
  const [showOrgForm, setShowOrgForm] = useState(false);
  const [orgForm, setOrgForm] = useState({ name: '', description: '', max_accounts: 0 });
  const [editingOrgId, setEditingOrgId] = useState<string | null>(null);

  const [showDeptForm, setShowDeptForm] = useState(false);
  const [deptForm, setDeptForm] = useState({ name: '', description: '' });
  const [editingDeptId, setEditingDeptId] = useState<string | null>(null);

  const [showUserForm, setShowUserForm] = useState(false);
  const [userForm, setUserForm] = useState({
    username: '', password: '', full_name: '', role: 'user', org_id: '', dept_id: '', ai_engine: '',
  });
  const [editingUserId, setEditingUserId] = useState<string | null>(null);

  useEffect(() => {
    loadOrgs();
    loadUsers();
  }, []);

  useEffect(() => {
    if (selectedOrg) loadDepts(selectedOrg.id);
  }, [selectedOrg]);

  const loadOrgs = async () => {
    try {
      const data = await ApiClient.getOrganizations();
      setOrgs(data);
      if (!selectedOrg && data.length > 0) setSelectedOrg(data[0]);
    } catch { /* ignore */ }
  };

  const loadDepts = async (orgId: string) => {
    try {
      const data = await ApiClient.getDepartments(orgId);
      setDepts(data);
    } catch { /* ignore */ }
  };

  const loadUsers = async () => {
    try {
      const data = await ApiClient.getUsers();
      setUsers(data);
    } catch { /* ignore */ }
  };

  // ── Org CRUD ──
  const handleSaveOrg = async () => {
    setLoading(true);
    try {
      if (editingOrgId) {
        await ApiClient.updateOrganization(editingOrgId, {
          name: orgForm.name,
          description: orgForm.description,
          ...(isSystemAdmin ? { max_accounts: orgForm.max_accounts } : {}),
        });
      } else {
        await ApiClient.createOrganization(orgForm.name, orgForm.description, orgForm.max_accounts);
      }
      await loadOrgs();
      setShowOrgForm(false);
      setOrgForm({ name: '', description: '', max_accounts: 0 });
      setEditingOrgId(null);
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Lỗi');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteOrg = async (id: string) => {
    if (!confirm('Xóa đơn vị này? Tất cả phòng ban sẽ bị xóa, user sẽ mất liên kết.')) return;
    try {
      await ApiClient.deleteOrganization(id);
      await loadOrgs();
      if (selectedOrg?.id === id) setSelectedOrg(null);
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Lỗi');
    }
  };

  // ── Dept CRUD ──
  const handleSaveDept = async () => {
    if (!selectedOrg) return;
    setLoading(true);
    try {
      if (editingDeptId) {
        await ApiClient.updateDepartment(editingDeptId, deptForm);
      } else {
        await ApiClient.createDepartment(selectedOrg.id, deptForm.name, deptForm.description);
      }
      await loadDepts(selectedOrg.id);
      await loadOrgs();
      setShowDeptForm(false);
      setDeptForm({ name: '', description: '' });
      setEditingDeptId(null);
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Lỗi');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteDept = async (id: string) => {
    if (!confirm('Xóa phòng ban này?')) return;
    try {
      await ApiClient.deleteDepartment(id);
      if (selectedOrg) await loadDepts(selectedOrg.id);
      await loadOrgs();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Lỗi');
    }
  };

  // ── User CRUD ──
  const handleSaveUser = async () => {
    setLoading(true);
    try {
      if (editingUserId) {
        const { username, ...updateData } = userForm;
        await ApiClient.updateUser(editingUserId, {
          full_name: updateData.full_name || undefined,
          password: updateData.password || undefined,
          role: updateData.role || undefined,
          org_id: updateData.org_id || undefined,
          dept_id: updateData.dept_id || undefined,
          ...(isSystemAdmin ? { ai_engine: updateData.ai_engine || undefined } : {}),
        });
      } else {
        await ApiClient.createUser({
          username: userForm.username,
          password: userForm.password,
          full_name: userForm.full_name,
          role: userForm.role,
          org_id: userForm.org_id || undefined,
          dept_id: userForm.dept_id || undefined,
          ...(isSystemAdmin ? { ai_engine: userForm.ai_engine || undefined } : {}),
        });
      }
      await loadUsers();
      setShowUserForm(false);
      setUserForm({ username: '', password: '', full_name: '', role: 'user', org_id: '', dept_id: '', ai_engine: '' });
      setEditingUserId(null);
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Lỗi');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteUser = async (id: string) => {
    if (!confirm('Xóa tài khoản này?')) return;
    try {
      await ApiClient.deleteAdminUser(id);
      await loadUsers();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Lỗi');
    }
  };

  const ROLE_LABELS: Record<string, string> = {
    system_admin: 'Admin HT',
    org_admin: 'Admin ĐV',
    user: 'Người dùng',
  };

  const ROLE_COLORS: Record<string, string> = {
    system_admin: 'bg-rose-500/10 text-rose-400',
    org_admin: 'bg-amber-500/10 text-amber-400',
    user: 'bg-slate-500/10 text-slate-400',
  };

  const ENGINE_LABELS: Record<string, string> = {
    notebooklm: 'Server 1',
    self_hosted: 'Server 2',
  };

  const ENGINE_COLORS: Record<string, string> = {
    notebooklm: 'bg-violet-500/10 text-violet-500',
    self_hosted: 'bg-teal-500/10 text-teal-500',
  };

  const tabs = [
    { key: 'orgs' as Tab, label: 'Đơn vị', icon: Building2, count: orgs.length },
    { key: 'depts' as Tab, label: 'Phòng ban', icon: FolderTree, count: depts.length },
    { key: 'users' as Tab, label: 'Tài khoản', icon: Users, count: users.length },
  ];

  // Deps for selected org
  const [orgDepts, setOrgDepts] = useState<DeptInfo[]>([]);
  useEffect(() => {
    if (userForm.org_id) {
      ApiClient.getDepartments(userForm.org_id).then(setOrgDepts).catch(() => setOrgDepts([]));
    } else {
      setOrgDepts([]);
    }
  }, [userForm.org_id]);

  return (
    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="max-w-6xl mx-auto space-y-6">
      <header>
        <h1 className="text-3xl font-bold text-slate-900 tracking-tight flex items-center gap-3">
          <Shield className="text-amber-500" size={28} />
          Quản trị hệ thống
        </h1>
        <p className="text-slate-500 mt-2">Quản lý đơn vị, phòng ban và tài khoản người dùng.</p>
      </header>

      {/* Tabs */}
      <div className="flex gap-1 bg-slate-100 p-1 rounded-2xl w-fit">
        {tabs.map(t => (
          <button
            key={t.key}
            onClick={() => setActiveTab(t.key)}
            className={`px-5 py-2.5 rounded-xl text-sm font-semibold transition-all flex items-center gap-2 ${
              activeTab === t.key ? 'bg-white text-slate-800 shadow-sm' : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            <t.icon size={16} />
            {t.label}
            <span className="px-2 py-0.5 bg-slate-200 text-slate-600 rounded-full text-xs">{t.count}</span>
          </button>
        ))}
      </div>

      {/* ═══════ Organizations Tab ═══════ */}
      {activeTab === 'orgs' && (
        <div className="space-y-4">
          {isSystemAdmin && (
            <button onClick={() => { setShowOrgForm(true); setEditingOrgId(null); setOrgForm({ name: '', description: '', max_accounts: 0 }); }}
              className="px-4 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-medium flex items-center gap-2 transition-colors">
              <Plus size={16} /> Thêm đơn vị
            </button>
          )}

          {showOrgForm && (
            <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}
              className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm space-y-4">
              <h3 className="font-bold text-slate-800">{editingOrgId ? 'Sửa' : 'Thêm'} đơn vị</h3>
              <input value={orgForm.name} onChange={e => setOrgForm({ ...orgForm, name: e.target.value })}
                placeholder="Tên đơn vị" className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500/20" />
              <textarea value={orgForm.description} onChange={e => setOrgForm({ ...orgForm, description: e.target.value })}
                placeholder="Mô tả chức năng nhiệm vụ..." rows={3} className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500/20" />
              <div className="space-y-2">
                <label className="block text-sm font-semibold text-slate-700">
                  Giới hạn tài khoản của đơn vị
                </label>
                <input type="number" min={0} value={orgForm.max_accounts}
                  onChange={e => setOrgForm({ ...orgForm, max_accounts: Math.max(0, Number(e.target.value) || 0) })}
                  disabled={!isSystemAdmin}
                  placeholder="0 = không giới hạn"
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500/20 disabled:bg-slate-100 disabled:text-slate-400 disabled:cursor-not-allowed" />
                <p className="text-xs text-slate-500">
                  Nhập 0 nếu không giới hạn. Chỉ admin hệ thống được thay đổi giá trị này.
                </p>
              </div>
              <div className="flex gap-2">
                <button onClick={handleSaveOrg} disabled={loading || !orgForm.name}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg font-medium flex items-center gap-2 disabled:opacity-50">
                  {loading ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />} Lưu
                </button>
                <button onClick={() => setShowOrgForm(false)} className="px-4 py-2 bg-slate-100 text-slate-600 rounded-lg font-medium flex items-center gap-2">
                  <X size={16} /> Hủy
                </button>
              </div>
            </motion.div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {orgs.map(org => (
              <div key={org.id} onClick={() => { setSelectedOrg(org); setActiveTab('depts'); }}
                className={`p-6 rounded-2xl border bg-white cursor-pointer transition-all hover:shadow-md ${
                  selectedOrg?.id === org.id ? 'border-blue-500 ring-2 ring-blue-500/20' : 'border-slate-200 hover:border-blue-300'
                }`}>
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div className="p-2.5 rounded-xl bg-blue-100 text-blue-600"><Building2 size={20} /></div>
                    <div>
                      <h3 className="font-bold text-slate-800">{org.name}</h3>
                      <p className="text-xs text-slate-500">
                        {org.dept_count} phòng ban · {org.user_count}/{org.max_accounts || '∞'} tài khoản
                      </p>
                    </div>
                  </div>
                  <div className="flex gap-1">
                    <button onClick={e => { e.stopPropagation(); setEditingOrgId(org.id); setOrgForm({ name: org.name, description: org.description, max_accounts: org.max_accounts || 0 }); setShowOrgForm(true); }}
                      className="p-1.5 text-slate-400 hover:text-blue-500 hover:bg-blue-50 rounded-lg"><Edit3 size={14} /></button>
                    {isSystemAdmin && (
                      <button onClick={e => { e.stopPropagation(); handleDeleteOrg(org.id); }}
                        className="p-1.5 text-slate-400 hover:text-rose-500 hover:bg-rose-50 rounded-lg"><Trash2 size={14} /></button>
                    )}
                  </div>
                </div>
                {org.description && <p className="text-sm text-slate-500 mt-3 line-clamp-2">{org.description}</p>}
                <div className="flex items-center text-xs text-blue-500 mt-3 font-medium">
                  Xem phòng ban <ChevronRight size={14} />
                </div>
              </div>
            ))}
          </div>

          {orgs.length === 0 && (
            <div className="p-12 text-center bg-white rounded-2xl border border-dashed border-slate-300 text-slate-400">
              <Building2 size={40} className="mx-auto mb-3 text-slate-300" />
              <p className="font-medium">Chưa có đơn vị nào</p>
            </div>
          )}
        </div>
      )}

      {/* ═══════ Departments Tab ═══════ */}
      {activeTab === 'depts' && (
        <div className="space-y-4">
          {selectedOrg ? (
            <>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-blue-100 text-blue-600"><Building2 size={18} /></div>
                  <div>
                    <h2 className="font-bold text-slate-800">{selectedOrg.name}</h2>
                    <p className="text-xs text-slate-500">Phòng ban</p>
                  </div>
                </div>
                <button onClick={() => { setShowDeptForm(true); setEditingDeptId(null); setDeptForm({ name: '', description: '' }); }}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-medium flex items-center gap-2 text-sm">
                  <Plus size={14} /> Thêm phòng ban
                </button>
              </div>

              {showDeptForm && (
                <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}
                  className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm space-y-4">
                  <h3 className="font-bold text-slate-800">{editingDeptId ? 'Sửa' : 'Thêm'} phòng ban</h3>
                  <input value={deptForm.name} onChange={e => setDeptForm({ ...deptForm, name: e.target.value })}
                    placeholder="Tên phòng ban" className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500/20" />
                  <textarea value={deptForm.description} onChange={e => setDeptForm({ ...deptForm, description: e.target.value })}
                    placeholder="Mô tả chức năng nhiệm vụ phòng ban..." rows={3} className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500/20" />
                  <div className="flex gap-2">
                    <button onClick={handleSaveDept} disabled={loading || !deptForm.name}
                      className="px-4 py-2 bg-blue-600 text-white rounded-lg font-medium flex items-center gap-2 disabled:opacity-50">
                      {loading ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />} Lưu
                    </button>
                    <button onClick={() => setShowDeptForm(false)} className="px-4 py-2 bg-slate-100 text-slate-600 rounded-lg font-medium flex items-center gap-2">
                      <X size={16} /> Hủy
                    </button>
                  </div>
                </motion.div>
              )}

              <div className="space-y-3">
                <AnimatePresence>
                  {depts.map(dept => (
                    <motion.div key={dept.id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                      className="p-5 bg-white rounded-2xl border border-slate-200">
                      <div className="flex items-start justify-between">
                        <div className="flex items-center gap-3">
                          <div className="p-2 rounded-lg bg-emerald-100 text-emerald-600"><FolderTree size={18} /></div>
                          <div>
                            <h3 className="font-bold text-slate-800">{dept.name}</h3>
                            <p className="text-xs text-slate-500">{dept.user_count} tài khoản</p>
                          </div>
                        </div>
                        <div className="flex gap-1">
                          <button onClick={() => { setEditingDeptId(dept.id); setDeptForm({ name: dept.name, description: dept.description }); setShowDeptForm(true); }}
                            className="p-1.5 text-slate-400 hover:text-blue-500 hover:bg-blue-50 rounded-lg"><Edit3 size={14} /></button>
                          <button onClick={() => handleDeleteDept(dept.id)}
                            className="p-1.5 text-slate-400 hover:text-rose-500 hover:bg-rose-50 rounded-lg"><Trash2 size={14} /></button>
                        </div>
                      </div>
                      {dept.description && <p className="text-sm text-slate-500 mt-2">{dept.description}</p>}
                    </motion.div>
                  ))}
                </AnimatePresence>
              </div>

              {depts.length === 0 && (
                <div className="p-8 text-center bg-white rounded-2xl border border-dashed border-slate-300 text-slate-400">
                  <FolderTree size={32} className="mx-auto mb-2 text-slate-300" />
                  <p className="text-sm font-medium">Chưa có phòng ban</p>
                </div>
              )}
            </>
          ) : (
            <div className="p-12 text-center bg-white rounded-2xl border border-dashed border-slate-300 text-slate-400">
              <Building2 size={40} className="mx-auto mb-3 text-slate-300" />
              <p className="font-medium">Chọn một đơn vị trong tab "Đơn vị"</p>
            </div>
          )}
        </div>
      )}

      {/* ═══════ Users Tab ═══════ */}
      {activeTab === 'users' && (
        <div className="space-y-4">
          <button onClick={() => {
            setShowUserForm(true); setEditingUserId(null);
            setUserForm({ username: '', password: '', full_name: '', role: 'user', org_id: '', dept_id: '', ai_engine: '' });
          }}
            className="px-4 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-medium flex items-center gap-2 transition-colors">
            <UserPlus size={16} /> Thêm tài khoản
          </button>

          {showUserForm && (
            <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}
              className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm space-y-4">
              <h3 className="font-bold text-slate-800">{editingUserId ? 'Sửa' : 'Thêm'} tài khoản</h3>
              <div className="grid grid-cols-2 gap-4">
                {!editingUserId && (
                  <input value={userForm.username} onChange={e => setUserForm({ ...userForm, username: e.target.value })}
                    placeholder="Tên đăng nhập" className="bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500/20" />
                )}
                <input value={userForm.full_name} onChange={e => setUserForm({ ...userForm, full_name: e.target.value })}
                  placeholder="Họ tên" className="bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500/20" />
                <input type="password" value={userForm.password} onChange={e => setUserForm({ ...userForm, password: e.target.value })}
                  placeholder={editingUserId ? "Mật khẩu mới (để trống giữ nguyên)" : "Mật khẩu"}
                  className="bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500/20" />
                <select value={userForm.role} onChange={e => setUserForm({ ...userForm, role: e.target.value })}
                  className="bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500/20">
                  <option value="user">Người dùng</option>
                  <option value="org_admin">Admin đơn vị</option>
                  {isSystemAdmin && <option value="system_admin">Admin hệ thống</option>}
                </select>
                <select value={userForm.org_id} onChange={e => setUserForm({ ...userForm, org_id: e.target.value, dept_id: '' })}
                  className="bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500/20">
                  <option value="">-- Chọn đơn vị --</option>
                  {orgs.map(o => <option key={o.id} value={o.id}>{o.name}</option>)}
                </select>
                <select value={userForm.dept_id} onChange={e => setUserForm({ ...userForm, dept_id: e.target.value })}
                  className="bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500/20">
                  <option value="">-- Chọn phòng ban --</option>
                  {orgDepts.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}
                </select>
                {isSystemAdmin ? (
                  <select value={userForm.ai_engine} onChange={e => setUserForm({ ...userForm, ai_engine: e.target.value })}
                    className="bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500/20">
                    <option value="">-- Máy chủ xử lý: Mặc định hệ thống --</option>
                    <option value="notebooklm">Server 1</option>
                    <option value="self_hosted">Server 2</option>
                  </select>
                ) : (
                  <div className="bg-slate-100 border border-slate-200 rounded-xl px-4 py-3 text-slate-600 flex items-center gap-2">
                    <Cpu size={16} className="text-violet-500" />
                    <span className="text-sm font-medium">Máy chủ xử lý: Server 1</span>
                  </div>
                )}
              </div>
              <div className="flex gap-2">
                <button onClick={handleSaveUser} disabled={loading || (!editingUserId && (!userForm.username || !userForm.password))}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg font-medium flex items-center gap-2 disabled:opacity-50">
                  {loading ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />} Lưu
                </button>
                <button onClick={() => setShowUserForm(false)} className="px-4 py-2 bg-slate-100 text-slate-600 rounded-lg font-medium flex items-center gap-2">
                  <X size={16} /> Hủy
                </button>
              </div>
            </motion.div>
          )}

          {/* User list */}
          <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
            <table className="w-full">
              <thead className="bg-slate-50 border-b border-slate-200">
                <tr>
                  <th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase">Tài khoản</th>
                  <th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase">Vai trò</th>
                  <th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase">Máy chủ xử lý</th>
                  <th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase">Đơn vị</th>
                  <th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase">Phòng ban</th>
                  <th className="text-right px-5 py-3 text-xs font-semibold text-slate-500 uppercase">Thao tác</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {users.map(u => (
                  <tr key={u.id} className="hover:bg-slate-50/50">
                    <td className="px-5 py-3">
                      <p className="text-sm font-semibold text-slate-800">{u.full_name || u.username}</p>
                      <p className="text-xs text-slate-400">@{u.username}</p>
                    </td>
                    <td className="px-5 py-3">
                      <span className={`px-2 py-1 text-[11px] font-bold rounded-md ${ROLE_COLORS[u.role] || ROLE_COLORS.user}`}>
                        {ROLE_LABELS[u.role] || u.role}
                      </span>
                    </td>
                    <td className="px-5 py-3">
                      {u.ai_engine ? (
                        <span className={`inline-flex items-center gap-1 px-2 py-1 text-[11px] font-bold rounded-md ${ENGINE_COLORS[u.ai_engine] || 'bg-slate-100 text-slate-500'}`}>
                          <Cpu size={11} />
                          {ENGINE_LABELS[u.ai_engine] || u.ai_engine}
                        </span>
                      ) : (
                        <span className="text-xs text-slate-400 italic">Mặc định</span>
                      )}
                    </td>
                    <td className="px-5 py-3 text-sm text-slate-600">{u.org_name || '-'}</td>
                    <td className="px-5 py-3 text-sm text-slate-600">{u.dept_name || '-'}</td>
                    <td className="px-5 py-3 text-right">
                      <div className="flex justify-end gap-1">
                        <button onClick={() => {
                          setEditingUserId(u.id);
                          setUserForm({
                            username: u.username, password: '', full_name: u.full_name,
                            role: u.role, org_id: u.org_id || '', dept_id: u.dept_id || '',
                            ai_engine: u.ai_engine || '',
                          });
                          setShowUserForm(true);
                        }} className="p-1.5 text-slate-400 hover:text-blue-500 hover:bg-blue-50 rounded-lg">
                          <Edit3 size={14} />
                        </button>
                        {u.id !== currentUser?.id && (
                          <button onClick={() => handleDeleteUser(u.id)}
                            className="p-1.5 text-slate-400 hover:text-rose-500 hover:bg-rose-50 rounded-lg">
                            <Trash2 size={14} />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {users.length === 0 && (
            <div className="p-8 text-center text-slate-400">
              <Users size={32} className="mx-auto mb-2 text-slate-300" />
              <p className="text-sm font-medium">Chưa có tài khoản nào</p>
            </div>
          )}
        </div>
      )}
    </motion.div>
  );
}
