import { useState, useCallback, useEffect } from 'react';
import { ApiClient } from '../api/client';
import type { Repository, Document, RepositoryCategory } from '../api/client';
import { motion, AnimatePresence } from 'framer-motion';
import { Database, Plus, Trash2, UploadCloud, File, ChevronRight, ChevronLeft, FileText, X, Globe, Lock, Share2, Loader2, CheckCircle2, Folder, FolderPlus, Pencil, Eye } from 'lucide-react';

export function RepositoryManager() {
  const [repos, setRepos] = useState<Repository[]>([]);
  const [categories, setCategories] = useState<RepositoryCategory[]>([]);
  const [selectedRepo, setSelectedRepo] = useState<Repository | null>(null);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [newRepoName, setNewRepoName] = useState('');
  const [newRepoDesc, setNewRepoDesc] = useState('');
  const [newRepoCategoryId, setNewRepoCategoryId] = useState('');
  const [newCategoryName, setNewCategoryName] = useState('');
  const [showCategoryForm, setShowCategoryForm] = useState(false);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [renameTarget, setRenameTarget] = useState<{ type: 'repo'; item: Repository } | { type: 'category'; item: RepositoryCategory } | null>(null);
  const [renameValue, setRenameValue] = useState('');
  const [renameError, setRenameError] = useState('');
  const [isRenaming, setIsRenaming] = useState(false);
  const [error, setError] = useState('');
  const [isCreating, setIsCreating] = useState(false);
  const [createSuccess, setCreateSuccess] = useState(false);
  const [previewHtml, setPreviewHtml] = useState('');
  const [previewTitle, setPreviewTitle] = useState('');
  const [isPreviewLoading, setIsPreviewLoading] = useState(false);

  const fetchRepos = useCallback(async () => {
    try {
      const data = await ApiClient.getRepositories();
      setRepos(data);
    } catch (err) { console.error(err); }
  }, []);

  const fetchCategories = useCallback(async () => {
    try {
      const data = await ApiClient.getRepositoryCategories();
      setCategories(data);
    } catch (err) { console.error(err); }
  }, []);

  const fetchDocs = useCallback(async (repoId: string) => {
    try {
      const data = await ApiClient.getDocuments(repoId);
      setDocuments(data);
    } catch (err) { console.error(err); }
  }, []);

  useEffect(() => { fetchRepos(); fetchCategories(); }, [fetchRepos, fetchCategories]);

  useEffect(() => {
    if (selectedRepo) fetchDocs(selectedRepo.id);
  }, [selectedRepo, fetchDocs]);

  useEffect(() => {
    if (!selectedRepo) return;
    const hasActiveDocs = documents.some(doc =>
      ['queued', 'processing'].includes(doc.processing_status)
    );
    if (!hasActiveDocs) return;

    const timer = window.setInterval(() => {
      fetchDocs(selectedRepo.id);
      fetchRepos();
    }, 3000);

    return () => window.clearInterval(timer);
  }, [selectedRepo, documents, fetchDocs, fetchRepos]);

  const handleCreateRepo = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newRepoName.trim() || isCreating) return;
    setError('');
    setIsCreating(true);
    setCreateSuccess(false);
    try {
      const repo = await ApiClient.createRepository(newRepoName, newRepoDesc, newRepoCategoryId || undefined);
      setCreateSuccess(true);
      await fetchRepos();
      // Show success briefly before closing
      setTimeout(() => {
        setNewRepoName(''); setNewRepoDesc(''); setNewRepoCategoryId('');
        setShowCreateForm(false);
        setCreateSuccess(false);
        setIsCreating(false);
        setSelectedRepo(repo);
      }, 1200);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Lỗi khi tạo kho');
      setIsCreating(false);
    }
  };

  const openRenameRepoModal = (repo: Repository) => {
    if (repo.is_shared) return;
    setRenameTarget({ type: 'repo', item: repo });
    setRenameValue(repo.name);
    setRenameError('');
  };

  const handleDeleteRepo = async (id: string) => {
    if (!confirm('Xóa kho này? Toàn bộ tài liệu và lịch sử chat sẽ bị xóa.')) return;
    try {
      await ApiClient.deleteRepository(id);
      if (selectedRepo?.id === id) { setSelectedRepo(null); setDocuments([]); }
      fetchRepos();
    } catch (err) { console.error(err); }
  };

  const handleCreateCategory = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newCategoryName.trim()) return;
    try {
      await ApiClient.createRepositoryCategory(newCategoryName.trim());
      setNewCategoryName('');
      setShowCategoryForm(false);
      fetchCategories();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Lỗi tạo danh mục');
    }
  };

  const openRenameCategoryModal = (category: RepositoryCategory) => {
    if (category.is_shared) return;
    setRenameTarget({ type: 'category', item: category });
    setRenameValue(category.name);
    setRenameError('');
  };

  const closeRenameModal = () => {
    if (isRenaming) return;
    setRenameTarget(null);
    setRenameValue('');
    setRenameError('');
  };

  const submitRename = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!renameTarget || isRenaming) return;
    const name = renameValue.trim();
    if (!name) {
      setRenameError('Vui lòng nhập tên mới');
      return;
    }
    if (name === renameTarget.item.name) {
      closeRenameModal();
      return;
    }

    setIsRenaming(true);
    setRenameError('');
    try {
      if (renameTarget.type === 'repo') {
        const updated = await ApiClient.updateRepository(renameTarget.item.id, { name });
        if (selectedRepo?.id === renameTarget.item.id) setSelectedRepo(updated);
      } else {
        await ApiClient.updateRepositoryCategory(renameTarget.item.id, { name });
        if (selectedRepo?.category_id === renameTarget.item.id) {
          setSelectedRepo({ ...selectedRepo, category_name: name });
        }
      }
      await fetchCategories();
      await fetchRepos();
      setRenameTarget(null);
      setRenameValue('');
    } catch (err: any) {
      setRenameError(err.response?.data?.detail || (renameTarget.type === 'repo' ? 'Lỗi đổi tên kho' : 'Lỗi đổi tên danh mục'));
    } finally {
      setIsRenaming(false);
    }
  };

  const handleToggleCategoryShare = async (category: RepositoryCategory) => {
    try {
      await ApiClient.updateRepositoryCategory(category.id, { is_public: !category.is_public });
      fetchCategories();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Lỗi cập nhật danh mục');
    }
  };

  const handleDeleteCategory = async (category: RepositoryCategory) => {
    if (!confirm('Xóa danh mục này? Các kho trong danh mục sẽ chuyển về chưa phân loại.')) return;
    try {
      await ApiClient.deleteRepositoryCategory(category.id);
      if (selectedRepo?.category_id === category.id) {
        setSelectedRepo({ ...selectedRepo, category_id: null, category_name: null });
      }
      await fetchCategories();
      await fetchRepos();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Lỗi xóa danh mục');
    }
  };

  const handleUpdateRepoCategory = async (categoryId: string) => {
    if (!selectedRepo || selectedRepo.is_shared) return;
    try {
      const updated = await ApiClient.updateRepository(selectedRepo.id, { category_id: categoryId || null });
      setSelectedRepo(updated);
      await fetchRepos();
      await fetchCategories();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Lỗi cập nhật danh mục kho');
    }
  };

  const uploadFiles = async (fileList: FileList | File[]) => {
    if (!selectedRepo || isUploading) return;
    const files = Array.from(fileList).filter(file => file.size > 0);
    if (files.length === 0) return;

    setIsUploading(true);
    try {
      for (const file of files) {
        await ApiClient.uploadDocument(selectedRepo.id, file);
      }
      await fetchDocs(selectedRepo.id);
      await fetchRepos();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Lỗi upload');
    } finally {
      setIsUploading(false);
    }
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) await uploadFiles(e.target.files);
    e.target.value = '';
  };

  const handleDragOver = (e: React.DragEvent<HTMLLabelElement>) => {
    e.preventDefault();
    e.stopPropagation();
    if (!isUploading) setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent<HTMLLabelElement>) => {
    e.preventDefault();
    e.stopPropagation();
    const nextTarget = e.relatedTarget as Node | null;
    if (nextTarget && e.currentTarget.contains(nextTarget)) return;
    setIsDragging(false);
  };

  const handleDrop = async (e: React.DragEvent<HTMLLabelElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    if (e.dataTransfer.files.length > 0) {
      await uploadFiles(e.dataTransfer.files);
    }
  };

  const handleDeleteDoc = async (docId: string) => {
    if (!selectedRepo || !confirm('Xóa tài liệu này?')) return;
    try {
      await ApiClient.deleteDocument(selectedRepo.id, docId);
      fetchDocs(selectedRepo.id);
      fetchRepos();
    } catch (err) { console.error(err); }
  };

  const openDocumentPreview = async (doc: Document) => {
    if (!selectedRepo) return;
    setPreviewTitle(doc.filename);
    setPreviewHtml('');
    setIsPreviewLoading(true);
    try {
      const html = await ApiClient.getDocumentPreview(selectedRepo.id, doc.id);
      setPreviewHtml(html);
    } catch (err: any) {
      const detail = err.response?.data?.detail || 'Không thể tải bản xem trước';
      setPreviewHtml(`<div style="font-family:system-ui;padding:24px;color:#b91c1c">${detail}</div>`);
    } finally {
      setIsPreviewLoading(false);
    }
  };

  const closeDocumentPreview = () => {
    setPreviewHtml('');
    setPreviewTitle('');
    setIsPreviewLoading(false);
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const getDocStatus = (doc: Document) => {
    switch (doc.processing_status) {
      case 'queued':
        return {
          label: 'Đang chờ',
          className: 'bg-amber-50 text-amber-700 border-amber-200',
          icon: <Loader2 size={12} className="animate-spin" />,
        };
      case 'processing':
        return {
          label: 'Đang xử lý',
          className: 'bg-blue-50 text-blue-700 border-blue-200',
          icon: <Loader2 size={12} className="animate-spin" />,
        };
      case 'failed':
        return {
          label: 'Lỗi',
          className: 'bg-rose-50 text-rose-700 border-rose-200',
          icon: <X size={12} />,
        };
      case 'completed':
      default:
        return {
          label: 'Sẵn sàng',
          className: 'bg-emerald-50 text-emerald-700 border-emerald-200',
          icon: <CheckCircle2 size={12} />,
        };
    }
  };


  const ownCategories = categories.filter(c => !c.is_shared);
  const sharedCategories = categories.filter(c => c.is_shared);
  const ownRepos = repos.filter(r => !r.is_shared);
  const sharedRepos = repos.filter(r => r.is_shared);
  const uncategorizedOwnRepos = ownRepos.filter(r => !r.category_id);
  const uncategorizedSharedRepos = sharedRepos.filter(r => !r.category_id || !sharedCategories.some(c => c.id === r.category_id));

  const renderRepoCard = (repo: Repository, shared = false) => (
    <div
      key={repo.id}
      onClick={() => setSelectedRepo(repo)}
      className={`p-4 rounded-2xl cursor-pointer transition-all border group ${
        selectedRepo?.id === repo.id
          ? shared
            ? 'bg-amber-50 border-amber-400 shadow-md ring-2 ring-amber-400/20'
            : 'bg-blue-50 border-blue-500 shadow-md ring-2 ring-blue-500/20'
          : shared
            ? 'bg-white border-slate-200 hover:border-amber-300 hover:shadow-sm'
            : 'bg-white border-slate-200 hover:border-blue-300 hover:shadow-sm'
      }`}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3 flex-1 min-w-0">
          <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${
            selectedRepo?.id === repo.id
              ? shared ? 'bg-amber-500 text-white' : 'bg-blue-600 text-white'
              : shared ? 'bg-amber-50 text-amber-500' : 'bg-slate-100 text-slate-500'
          }`}>
            {shared ? <Share2 size={18} /> : <Database size={18} />}
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h3 className="font-semibold text-slate-800 truncate">{repo.name}</h3>
              {!shared && repo.is_public && <Globe size={12} className="text-emerald-500 shrink-0" />}
            </div>
            <p className="text-xs text-slate-500 truncate">
              {shared && repo.owner_name ? `Từ ${repo.owner_name} · ` : ''}{repo.document_count} tài liệu
            </p>
          </div>
        </div>
        <div className="flex items-center gap-1">
          {!shared && (
            <>
              <button
                onClick={(e) => { e.stopPropagation(); openRenameRepoModal(repo); }}
                className="p-2 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors opacity-0 group-hover:opacity-100"
                title="Đổi tên kho"
              >
                <Pencil size={14} />
              </button>
              <button
                onClick={(e) => { e.stopPropagation(); handleDeleteRepo(repo.id); }}
                className="p-2 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors opacity-0 group-hover:opacity-100"
                title="Xóa kho"
              >
                <Trash2 size={14} />
              </button>
            </>
          )}
          <ChevronRight size={16} className="text-slate-400" />
        </div>
      </div>
      {repo.description && (
        <p className="text-xs text-slate-500 mt-2 pl-13 truncate">{repo.description}</p>
      )}
    </div>
  );

  const renderCategoryBlock = (category: RepositoryCategory, categoryRepos: Repository[], shared = false) => (
    <div key={category.id} className="space-y-2">
      <div className={`flex items-center justify-between text-xs font-semibold uppercase tracking-wider px-1 pt-3 ${shared ? 'text-amber-600' : 'text-slate-600'}`}>
        <div className="flex items-center gap-1 min-w-0">
          <Folder size={13} />
          <span className="truncate">{category.name}</span>
          {shared && category.owner_name && <span className="normal-case font-normal text-slate-400 truncate">· {category.owner_name}</span>}
        </div>
        {!shared && (
          <div className="flex items-center gap-1 shrink-0">
            <button
              onClick={() => openRenameCategoryModal(category)}
              className="p-1.5 rounded-lg text-slate-400 hover:text-blue-600 hover:bg-blue-50 transition-colors"
              title="Đổi tên danh mục"
            >
              <Pencil size={13} />
            </button>
            <button
              onClick={() => handleToggleCategoryShare(category)}
              className={`p-1.5 rounded-lg transition-colors ${category.is_public ? 'text-emerald-600 hover:bg-emerald-50' : 'text-slate-400 hover:bg-slate-100'}`}
              title={category.is_public ? 'Đang chia sẻ danh mục' : 'Chia sẻ danh mục'}
            >
              {category.is_public ? <Globe size={13} /> : <Lock size={13} />}
            </button>
            <button
              onClick={() => handleDeleteCategory(category)}
              className="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors"
              title="Xóa danh mục"
            >
              <Trash2 size={13} />
            </button>
          </div>
        )}
      </div>
      {categoryRepos.map(repo => renderRepoCard(repo, shared))}
    </div>
  );

  return (
    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="max-w-6xl mx-auto space-y-6">
      <header className="flex justify-between items-start">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 tracking-tight">Kho Dữ liệu</h1>
          <p className="text-slate-500 mt-2">Quản lý kho dữ liệu và tài liệu.</p>
        </div>
        <button
          onClick={() => setShowCreateForm(true)}
          className="px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-medium flex items-center gap-2 shadow-lg shadow-blue-600/20 transition-colors"
        >
          <Plus size={18} /> Tạo kho mới
        </button>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Repo List */}
        <div className="lg:col-span-4 space-y-3">
          <div className="flex items-center justify-between px-1">
            <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              {ownRepos.length} kho cá nhân
            </div>
            <button
              onClick={() => setShowCategoryForm(v => !v)}
              className="p-2 rounded-lg text-slate-500 hover:text-blue-600 hover:bg-blue-50 transition-colors"
              title="Tạo danh mục"
            >
              <FolderPlus size={16} />
            </button>
          </div>

          {showCategoryForm && (
            <form onSubmit={handleCreateCategory} className="bg-white border border-slate-200 rounded-2xl p-3 flex gap-2">
              <input
                type="text"
                value={newCategoryName}
                onChange={(e) => setNewCategoryName(e.target.value)}
                placeholder="Tên danh mục"
                className="min-w-0 flex-1 bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
              />
              <button type="submit" className="p-2 bg-blue-600 text-white rounded-xl hover:bg-blue-700 transition-colors">
                <Plus size={16} />
              </button>
            </form>
          )}

          {ownRepos.length === 0 && sharedRepos.length === 0 ? (
            <div className="p-8 text-center bg-white rounded-2xl border border-dashed border-slate-300 text-slate-400">
              <Database size={40} className="mx-auto mb-3 text-slate-300" />
              <p className="font-medium">Chưa có kho nào</p>
              <p className="text-sm mt-1">Tạo kho đầu tiên để bắt đầu</p>
            </div>
          ) : (
            <>
              {ownCategories.map(category => {
                const categoryRepos = ownRepos.filter(repo => repo.category_id === category.id);
                return renderCategoryBlock(category, categoryRepos, false);
              })}

              {uncategorizedOwnRepos.length > 0 && (
                <div className="space-y-2">
                  <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider px-1 pt-3 flex items-center gap-1">
                    <Database size={13} />
                    Chưa phân loại
                  </div>
                  {uncategorizedOwnRepos.map(repo => renderRepoCard(repo, false))}
                </div>
              )}

              {sharedRepos.length > 0 && (
                <>
                  <div className="text-xs font-semibold text-amber-600 uppercase tracking-wider px-1 pt-4 flex items-center gap-1">
                    <Share2 size={12} />
                    Kho chia sẻ từ đơn vị
                  </div>
                  {sharedCategories.map(category => {
                    const categoryRepos = sharedRepos.filter(repo => repo.category_id === category.id);
                    return categoryRepos.length > 0 ? renderCategoryBlock(category, categoryRepos, true) : null;
                  })}
                  {uncategorizedSharedRepos.map(repo => renderRepoCard(repo, true))}
                </>
              )}
            </>
          )}
        </div>

        {/* Repo Detail + Docs */}
        <div className="lg:col-span-8">
          {selectedRepo ? (
            <div className="space-y-6">
              {/* Header */}
              <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
                <div className="flex items-center gap-4 mb-2">
                  <button onClick={() => setSelectedRepo(null)} className="lg:hidden p-2 text-slate-400 hover:text-slate-600 rounded-lg">
                    <ChevronLeft size={20} />
                  </button>
                  <div className="w-12 h-12 rounded-xl bg-gradient-to-tr from-blue-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-blue-500/20">
                    <Database size={22} className="text-white" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <h2 className="text-xl font-bold text-slate-900 truncate">{selectedRepo.name}</h2>
                      {!selectedRepo.is_shared && (
                        <button
                          onClick={() => openRenameRepoModal(selectedRepo)}
                          className="p-1.5 rounded-lg text-slate-400 hover:text-blue-600 hover:bg-blue-50 transition-colors"
                          title="Đổi tên kho"
                        >
                          <Pencil size={15} />
                        </button>
                      )}
                    </div>
                    <p className="text-sm text-slate-500">{selectedRepo.description || 'Không có mô tả'}</p>
                  </div>
                </div>
                <div className="flex flex-wrap gap-4 mt-4 text-xs text-slate-500 items-center">
                  <span>Tạo: {new Date(selectedRepo.created_at).toLocaleDateString('vi-VN')}</span>
                  <span>·</span>
                  <span>{selectedRepo.document_count} tài liệu</span>
                  {selectedRepo.notebook_id && (
                    <>
                      <span>·</span>
                      <span className="text-emerald-600 font-medium">✓ Sẵn sàng AI</span>
                    </>
                  )}
                  {selectedRepo.is_shared && (
                    <span className="px-2 py-0.5 bg-amber-100 text-amber-700 rounded-md font-medium">Kho chia sẻ</span>
                  )}
                  {!selectedRepo.is_shared && (
                    <button
                      onClick={async () => {
                        try {
                          await ApiClient.updateRepository(selectedRepo.id, { is_public: !selectedRepo.is_public });
                          const updated = { ...selectedRepo, is_public: !selectedRepo.is_public };
                          setSelectedRepo(updated);
                          fetchRepos();
                          fetchCategories();
                        } catch { /* ignore */ }
                      }}
                      className={`flex items-center gap-1 px-2 py-0.5 rounded-md font-medium transition-colors ${
                        selectedRepo.is_public
                          ? 'bg-emerald-100 text-emerald-700 hover:bg-emerald-200'
                          : 'bg-slate-100 text-slate-500 hover:bg-slate-200'
                      }`}
                    >
                      {selectedRepo.is_public ? <><Globe size={11} /> Công khai</> : <><Lock size={11} /> Riêng tư</>}
                    </button>
                  )}
                </div>
                <div className="mt-4 pt-4 border-t border-slate-100 flex flex-wrap items-center gap-2 text-sm">
                  <div className="flex items-center gap-2 text-slate-600">
                    <Folder size={16} className="text-slate-400" />
                    <span className="font-medium">Danh mục</span>
                  </div>
                  {selectedRepo.is_shared ? (
                    <span className="px-3 py-1.5 bg-slate-100 text-slate-600 rounded-lg">
                      {selectedRepo.category_name || 'Chưa phân loại'}
                    </span>
                  ) : (
                    <select
                      value={selectedRepo.category_id || ''}
                      onChange={(e) => handleUpdateRepoCategory(e.target.value)}
                      className="bg-slate-50 border border-slate-200 rounded-lg px-3 py-1.5 text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                    >
                      <option value="">Chưa phân loại</option>
                      {ownCategories.map(category => (
                        <option key={category.id} value={category.id}>{category.name}</option>
                      ))}
                    </select>
                  )}
                </div>
              </div>

              {/* Upload — only for own repos */}
              {!selectedRepo.is_shared && (
              <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
                <h3 className="font-bold text-slate-800 flex items-center gap-2 mb-4">
                  <UploadCloud className="text-blue-600" size={18} /> Upload tài liệu
                </h3>
                <div className="relative">
                  <label
                    onDragEnter={handleDragOver}
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                    onDrop={handleDrop}
                    className={`border-2 border-dashed rounded-2xl py-8 flex flex-col items-center justify-center cursor-pointer transition-all ${
                      isUploading
                        ? 'border-blue-400 bg-blue-50/50'
                        : isDragging
                          ? 'border-blue-500 bg-blue-50 ring-4 ring-blue-100'
                          : 'border-slate-300 hover:border-blue-400 hover:bg-blue-50/30'
                    }`}
                  >
                    <UploadCloud size={28} className="text-blue-500 mb-2" />
                    <p className="font-medium text-slate-700">
                      {isUploading ? 'Đang upload...' : 'Nhấn để chọn file hoặc kéo thả'}
                    </p>
                    <p className="text-xs text-slate-500 mt-1">PDF, Word, Excel, ảnh, audio, video — tối đa 50MB</p>
                    <input
                      type="file"
                      className="hidden"
                      onChange={handleUpload}
                      disabled={isUploading}
                    />
                  </label>
                  {isUploading && (
                    <div className="absolute inset-0 bg-white/80 backdrop-blur flex items-center justify-center rounded-2xl">
                      <div className="w-10 h-10 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
                    </div>
                  )}
                </div>
              </div>
              )}

              {/* Doc List */}
              <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
                <div className="p-4 border-b border-slate-200 bg-slate-50/50">
                  <h3 className="font-bold text-slate-800 flex items-center gap-2">
                    <FileText className="text-blue-600" size={18} />
                    Tài liệu ({documents.length})
                  </h3>
                </div>
                {documents.length === 0 ? (
                  <div className="p-8 text-center text-slate-400 text-sm">
                    Chưa có tài liệu nào. Upload tài liệu đầu tiên!
                  </div>
                ) : (
                  <div className="divide-y divide-slate-100">
                    {documents.map(doc => {
                      const status = getDocStatus(doc);
                    
                      return (
                      <div key={doc.id} className="px-6 py-3 flex items-center justify-between hover:bg-slate-50 transition-colors group gap-4">
                        <div className="flex items-center gap-3 min-w-0">
                          <File size={16} className="text-blue-500 shrink-0" />
                          <div className="min-w-0">
                            <p className="font-medium text-slate-800 text-sm truncate">{doc.filename}</p>
                            <p className="text-xs text-slate-400 truncate">
                              {formatSize(doc.file_size)} · {new Date(doc.uploaded_at).toLocaleDateString('vi-VN')}
                              {doc.chunk_count > 0 && ` · ${doc.chunk_count} đoạn`}
                              {doc.progress_message && ` · ${doc.progress_message}`}
                              {doc.error_message && ` · ${doc.error_message}`}
                            </p>
                          </div>
                        </div>
                        <div className="flex items-center gap-2 shrink-0">
                          <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-md border text-xs font-medium ${status.className}`}>
                            {status.icon}
                            {status.label}
                          </span>
                        <button
                          onClick={() => openDocumentPreview(doc)}
                          className="p-2 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors opacity-0 group-hover:opacity-100"
                          title="Xem file"
                        >
                          <Eye size={14} />
                        </button>
                        {!selectedRepo.is_shared && (
                        <button
                          onClick={() => handleDeleteDoc(doc.id)}
                          className="p-2 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors opacity-0 group-hover:opacity-100"
                        >
                          <Trash2 size={14} />
                        </button>
                        )}
                        </div>
                      </div>
                    )})}
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="h-full flex flex-col items-center justify-center text-slate-400 bg-slate-50/50 rounded-2xl border border-dashed border-slate-300 min-h-[400px]">
              <Database size={48} className="text-slate-300 mb-4" />
              <p className="font-medium">Chọn một kho dữ liệu từ danh sách bên trái</p>
              <p className="text-sm mt-1">hoặc tạo kho mới để bắt đầu</p>
            </div>
          )}
        </div>
      </div>

      {/* Rename Modal */}
      <AnimatePresence>
        {renameTarget && (
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4"
            onClick={closeRenameModal}
          >
            <motion.div
              initial={{ scale: 0.94, opacity: 0, y: 12 }} animate={{ scale: 1, opacity: 1, y: 0 }} exit={{ scale: 0.94, opacity: 0, y: 12 }}
              onClick={(e) => e.stopPropagation()}
              className="bg-white rounded-3xl p-7 w-full max-w-md shadow-2xl border border-slate-200"
            >
              <div className="flex items-start justify-between gap-4 mb-6">
                <div>
                  <h2 className="text-xl font-bold text-slate-900">
                    {renameTarget.type === 'repo' ? 'Đổi tên kho' : 'Đổi tên danh mục'}
                  </h2>
                  <p className="text-sm text-slate-500 mt-1">
                    Cập nhật tên hiển thị để dễ quản lý và tìm kiếm.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={closeRenameModal}
                  disabled={isRenaming}
                  className="p-2 hover:bg-slate-100 rounded-lg transition-colors disabled:opacity-50"
                >
                  <X size={20} className="text-slate-400" />
                </button>
              </div>

              <form onSubmit={submitRename} className="space-y-4">
                <div>
                  <label className="block text-sm font-semibold text-slate-700 mb-2">Tên mới</label>
                  <input
                    type="text"
                    autoFocus
                    required
                    value={renameValue}
                    onChange={(e) => setRenameValue(e.target.value)}
                    disabled={isRenaming}
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all disabled:opacity-60"
                  />
                </div>

                {renameError && (
                  <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-rose-600 text-sm">{renameError}</div>
                )}

                <div className="flex gap-3 pt-2">
                  <button
                    type="button"
                    onClick={closeRenameModal}
                    disabled={isRenaming}
                    className="flex-1 py-3 bg-slate-100 text-slate-700 rounded-xl font-medium hover:bg-slate-200 transition-colors disabled:opacity-50"
                  >
                    Hủy
                  </button>
                  <button
                    type="submit"
                    disabled={isRenaming || !renameValue.trim()}
                    className="flex-1 py-3 bg-blue-600 text-white rounded-xl font-medium hover:bg-blue-700 transition-colors flex items-center justify-center gap-2 shadow-lg shadow-blue-600/20 disabled:opacity-70"
                  >
                    {isRenaming ? <><Loader2 size={18} className="animate-spin" /> Đang lưu...</> : <><Pencil size={18} /> Lưu</>}
                  </button>
                </div>
              </form>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Create Repo Modal */}
      <AnimatePresence>
        {showCreateForm && (
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4"
            onClick={() => setShowCreateForm(false)}
          >
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.9, opacity: 0 }}
              onClick={(e) => e.stopPropagation()}
              className="bg-white rounded-3xl p-8 w-full max-w-md shadow-2xl"
            >
              <div className="flex justify-between items-center mb-6">
                <h2 className="text-xl font-bold text-slate-900">Tạo kho dữ liệu mới</h2>
                <button onClick={() => !isCreating && setShowCreateForm(false)} className={`p-2 hover:bg-slate-100 rounded-lg transition-colors ${isCreating ? 'opacity-50 cursor-not-allowed' : ''}`}>
                  <X size={20} className="text-slate-400" />
                </button>
              </div>

              {createSuccess ? (
                <motion.div
                  initial={{ scale: 0.8, opacity: 0 }} animate={{ scale: 1, opacity: 1 }}
                  className="py-8 flex flex-col items-center gap-3"
                >
                  <div className="w-16 h-16 rounded-full bg-emerald-100 flex items-center justify-center">
                    <CheckCircle2 size={32} className="text-emerald-600" />
                  </div>
                  <p className="text-lg font-bold text-slate-900">Tạo kho thành công!</p>
                  <p className="text-sm text-slate-500">Đang chuyển hướng...</p>
                </motion.div>
              ) : (
              <form onSubmit={handleCreateRepo} className="space-y-4">
                <div>
                  <label className="block text-sm font-semibold text-slate-700 mb-2">Tên kho *</label>
                  <input
                    type="text" required
                    value={newRepoName} onChange={(e) => setNewRepoName(e.target.value)}
                    placeholder="VD: Kho Khoa học Công nghệ"
                    disabled={isCreating}
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all disabled:opacity-60"
                  />
                </div>
                <div>
                  <label className="block text-sm font-semibold text-slate-700 mb-2">Mô tả</label>
                  <textarea
                    value={newRepoDesc} onChange={(e) => setNewRepoDesc(e.target.value)}
                    placeholder="Mô tả ngắn về nội dung kho..."
                    rows={3}
                    disabled={isCreating}
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all disabled:opacity-60"
                  />
                </div>
                <div>
                  <label className="block text-sm font-semibold text-slate-700 mb-2">Danh mục</label>
                  <select
                    value={newRepoCategoryId}
                    onChange={(e) => setNewRepoCategoryId(e.target.value)}
                    disabled={isCreating}
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all disabled:opacity-60"
                  >
                    <option value="">Chưa phân loại</option>
                    {ownCategories.map(category => (
                      <option key={category.id} value={category.id}>{category.name}</option>
                    ))}
                  </select>
                </div>
                {error && (
                  <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-rose-600 text-sm">{error}</div>
                )}
                <div className="flex gap-3 pt-2">
                  <button type="button" onClick={() => !isCreating && setShowCreateForm(false)}
                    disabled={isCreating}
                    className="flex-1 py-3 bg-slate-100 text-slate-700 rounded-xl font-medium hover:bg-slate-200 transition-colors disabled:opacity-50 disabled:cursor-not-allowed">
                    Hủy
                  </button>
                  <button type="submit"
                    disabled={isCreating}
                    className="flex-1 py-3 bg-blue-600 text-white rounded-xl font-medium hover:bg-blue-700 transition-colors flex items-center justify-center gap-2 shadow-lg shadow-blue-600/20 disabled:opacity-70 disabled:cursor-not-allowed">
                    {isCreating ? (
                      <><Loader2 size={18} className="animate-spin" /> Đang tạo...
                      </>
                    ) : (
                      <><Plus size={18} /> Tạo kho</>
                    )}
                  </button>
                </div>
              </form>
              )}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Document Preview Modal */}
      <AnimatePresence>
        {(previewHtml || isPreviewLoading) && (
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4"
            onClick={closeDocumentPreview}
          >
            <motion.div
              initial={{ scale: 0.96, opacity: 0, y: 12 }} animate={{ scale: 1, opacity: 1, y: 0 }} exit={{ scale: 0.96, opacity: 0, y: 12 }}
              onClick={(e) => e.stopPropagation()}
              className="bg-white rounded-3xl w-full max-w-6xl h-[90vh] shadow-2xl border border-slate-200 overflow-hidden flex flex-col"
            >
              <div className="px-5 py-4 border-b border-slate-200 flex items-center justify-between gap-4">
                <div className="min-w-0">
                  <h2 className="font-bold text-slate-900 truncate">Xem file</h2>
                  <p className="text-sm text-slate-500 truncate">{previewTitle}</p>
                </div>
                <button
                  onClick={closeDocumentPreview}
                  className="p-2 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
                  title="Đóng"
                >
                  <X size={20} />
                </button>
              </div>
              <div className="flex-1 bg-slate-100">
                {isPreviewLoading ? (
                  <div className="h-full flex items-center justify-center text-slate-500">
                    <Loader2 size={24} className="animate-spin mr-2" />
                    Đang tải bản xem trước...
                  </div>
                ) : (
                  <iframe
                    title={previewTitle || 'Xem file'}
                    srcDoc={previewHtml}
                    className="w-full h-full border-0 bg-white"
                  />
                )}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
