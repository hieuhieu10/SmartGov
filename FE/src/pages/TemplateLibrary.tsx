import { useState, useEffect, useRef } from 'react';
import { ApiClient } from '../api/client';
import type { Repository, RepositoryCategory, Document, DraftTypeInfo, DraftTaskStatus, TemplateInfo } from '../api/client';
import { FileCode, Loader2, Play, Database, Download, RotateCcw, CheckCircle, AlertCircle, Upload, Trash2, FileUp, Sparkles, Clock, Pencil, Check, X, FileText, Folder, Eye } from 'lucide-react';
import { useSearchParams } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';

const FIELD_LABELS: Record<string, string> = {
  co_quan_ban_hanh: 'Cơ quan ban hành',
  co_quan_chu_quan: 'Cơ quan chủ quản',
  noi_nhan: 'Kính gửi / Nơi nhận',
  trich_yeu: 'Trích yếu nội dung',
  noi_dung_chinh: 'Yêu cầu nội dung chính',
  nguoi_ky: 'Họ tên người ký',
  chuc_vu_nguoi_ky: 'Chức vụ người ký',
  so_van_ban: 'Số văn bản',
  can_cu: 'Căn cứ pháp lý',
  muc_dich: 'Mục đích',
  yeu_cau: 'Yêu cầu',
  ly_do: 'Lý do trình',
  kien_nghi: 'Kiến nghị',
  ky_bao_cao: 'Kỳ báo cáo',
  danh_gia: 'Đánh giá chung',
};

const DOC_TYPE_NAMES: Record<string, string> = {
  cong_van: 'Công văn',
  quyet_dinh: 'Quyết định',
  ke_hoach: 'Kế hoạch',
  thong_bao: 'Thông báo',
  to_trinh: 'Tờ trình',
  bao_cao: 'Báo cáo',
};

type TabType = 'standard' | 'custom';

function formatFileSize(size: number): string {
  if (!Number.isFinite(size) || size <= 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  let value = size;
  let idx = 0;
  while (value >= 1024 && idx < units.length - 1) {
    value /= 1024;
    idx += 1;
  }
  return `${value.toFixed(idx === 0 ? 0 : 1)} ${units[idx]}`;
}

interface HistoryTask {
  task_id: string;
  document_type?: string;
  status: string;
  progress_message: string;
  error_message: string;
  output_ready: boolean;
  created_at: string;
}

export function TemplateLibrary() {
  const [searchParams] = useSearchParams();
  const [activeTab, setActiveTab] = useState<TabType>('standard');

  // ── Standard drafting state ──
  const [draftTypes, setDraftTypes] = useState<DraftTypeInfo[]>([]);
  const [selectedType, setSelectedType] = useState<DraftTypeInfo | null>(null);
  const [formData, setFormData] = useState<Record<string, string>>({});
  const [isGenerating, setIsGenerating] = useState(false);
  const [taskStatus, setTaskStatus] = useState<DraftTaskStatus | null>(null);
  const [draftHistory, setDraftHistory] = useState<HistoryTask[]>([]);

  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [categories, setCategories] = useState<RepositoryCategory[]>([]);
  const [selectedDraftCategoryId, setSelectedDraftCategoryId] = useState<string>('');
  const [selectedRepoId, setSelectedRepoId] = useState<string>('');
  const [repoDocuments, setRepoDocuments] = useState<Document[]>([]);
  const [selectedDocumentIds, setSelectedDocumentIds] = useState<string[]>([]);

  // ── Custom template state ──
  const [templates, setTemplates] = useState<TemplateInfo[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<TemplateInfo | null>(null);
  const [templateFormData, setTemplateFormData] = useState<Record<string, string>>({});
  const [isUploading, setIsUploading] = useState(false);
  const [isTemplateGenerating, setIsTemplateGenerating] = useState(false);
  const [templateTaskStatus, setTemplateTaskStatus] = useState<any>(null);
  const [selectedTemplateCategoryId, setSelectedTemplateCategoryId] = useState<string>('');
  const [templateRepoId, setTemplateRepoId] = useState<string>('');
  const [templateRepoDocuments, setTemplateRepoDocuments] = useState<Document[]>([]);
  const [selectedTemplateDocumentIds, setSelectedTemplateDocumentIds] = useState<string[]>([]);
  const [history, setHistory] = useState<HistoryTask[]>([]);
  const [editingNameId, setEditingNameId] = useState<string | null>(null);
  const [editNameValue, setEditNameValue] = useState('');
  const [editDraftTaskId, setEditDraftTaskId] = useState<string | null>(null);
  const [editInstruction, setEditInstruction] = useState('');
  const [previewHtml, setPreviewHtml] = useState('');
  const [previewTitle, setPreviewTitle] = useState('');
  const [isPreviewLoading, setIsPreviewLoading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadDraftHistory = async () => {
    try {
      const list = await ApiClient.getDraftHistory();
      setDraftHistory(list);
    } catch { /* ignore */ }
  };

  useEffect(() => {
    ApiClient.getDraftTypes().then(types => {
      setDraftTypes(types);
      if (types.length > 0) setSelectedType(prev => prev || types[0]);
    }).catch(console.error);

    Promise.all([ApiClient.getRepositories(), ApiClient.getRepositoryCategories()])
      .then(([repos, cats]) => {
        setRepositories(repos);
        setCategories(cats);
        const urlRepo = searchParams.get('repo');
        const initialRepo = (urlRepo && repos.find(r => r.id === urlRepo)) || repos[0];
        if (initialRepo) {
          setSelectedRepoId(initialRepo.id);
          setSelectedDraftCategoryId(initialRepo.category_id || '__uncategorized');
        }
      })
      .catch(console.error);

    loadTemplates();
    loadDraftHistory();
  }, [searchParams]);

  useEffect(() => {
    setSelectedDocumentIds([]);
    if (!selectedRepoId) {
      setRepoDocuments([]);
      return;
    }
    ApiClient.getDocuments(selectedRepoId)
      .then(setRepoDocuments)
      .catch(() => setRepoDocuments([]));
  }, [selectedRepoId]);

  useEffect(() => {
    setSelectedTemplateDocumentIds([]);
    if (!templateRepoId) {
      setTemplateRepoDocuments([]);
      return;
    }
    ApiClient.getDocuments(templateRepoId)
      .then(setTemplateRepoDocuments)
      .catch(() => setTemplateRepoDocuments([]));
  }, [templateRepoId]);

  const loadTemplates = async () => {
    try {
      const list = await ApiClient.getTemplates();
      setTemplates(list);
    } catch { /* ignore */ }
  };

  // Refresh templates that are still analyzing
  useEffect(() => {
    const analyzing = templates.filter(t => t.status === 'analyzing');
    if (analyzing.length === 0) return;

    const interval = setInterval(async () => {
      await loadTemplates();
    }, 3000);
    return () => clearInterval(interval);
  }, [templates]);

  // Load history when selecting a template
  useEffect(() => {
    if (!selectedTemplate) {
      setHistory([]);
      return;
    }
    ApiClient.getTemplateHistory(selectedTemplate.id)
      .then(setHistory)
      .catch(() => setHistory([]));
  }, [selectedTemplate?.id]);

  // ── Standard drafting handlers ──
  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedType || !selectedRepoId) return;
    setIsGenerating(true);
    setTaskStatus(null);

    try {
      const res = await ApiClient.createDraft(
        selectedRepoId,
        selectedType.type_code,
        formData,
        selectedDocumentIds,
      );
      const taskId = res.task_id;

      const poll = async () => {
        const status = await ApiClient.getDraftStatus(taskId);
        setTaskStatus(status);
        if (status.status === 'completed' || status.status === 'error') {
          setIsGenerating(false);
          loadDraftHistory();
          return;
        }
        setTimeout(poll, 2000);
      };
      poll();
    } catch (err: any) {
      const detail = err.response?.data?.detail || 'Lỗi khi tạo văn bản';
      setTaskStatus({
        task_id: '', status: 'error', document_type: selectedType.type_code,
        progress_message: '', error_message: detail, output_ready: false,
      });
      setIsGenerating(false);
    }
  };

  const handleReset = () => {
    setTaskStatus(null);
    setFormData({});
  };

  const openEditDraftModal = (taskId: string) => {
    setEditDraftTaskId(taskId);
    setEditInstruction('');
  };

  const closeEditDraftModal = () => {
    if (isGenerating) return;
    setEditDraftTaskId(null);
    setEditInstruction('');
  };

  const openPreview = async (kind: 'draft' | 'template', taskId: string) => {
    setPreviewTitle(kind === 'draft' ? 'Xem trước văn bản' : 'Xem trước văn bản theo mẫu');
    setPreviewHtml('');
    setIsPreviewLoading(true);
    try {
      const html = kind === 'draft'
        ? await ApiClient.getDraftPreview(taskId)
        : await ApiClient.getTemplatePreview(taskId);
      setPreviewHtml(html);
    } catch (err: any) {
      const detail = err.response?.data?.detail || 'Không thể tải bản xem trước';
      setPreviewHtml(`<div style="font-family:system-ui;padding:24px;color:#b91c1c">${detail}</div>`);
    } finally {
      setIsPreviewLoading(false);
    }
  };

  const closePreview = () => {
    setPreviewHtml('');
    setPreviewTitle('');
    setIsPreviewLoading(false);
  };

  const submitEditDraft = async () => {
    if (!editDraftTaskId || !editInstruction.trim()) return;
    setIsGenerating(true);
    setTaskStatus(null);
    try {
      const res = await ApiClient.editDraft(editDraftTaskId, editInstruction.trim());
      const editTaskId = res.task_id;
      setEditDraftTaskId(null);
      setEditInstruction('');
      const poll = async () => {
        const status = await ApiClient.getDraftStatus(editTaskId);
        setTaskStatus(status);
        if (status.status === 'completed' || status.status === 'error') {
          setIsGenerating(false);
          loadDraftHistory();
          return;
        }
        setTimeout(poll, 2000);
      };
      poll();
    } catch (err: any) {
      setTaskStatus({
        task_id: '',
        status: 'error',
        document_type: selectedType?.type_code || '',
        progress_message: '',
        error_message: err.response?.data?.detail || 'Lỗi khi chỉnh sửa file Word',
        output_ready: false,
      });
      setIsGenerating(false);
    }
  };

  // ── Custom template handlers ──
  const handleTemplateUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setIsUploading(true);
    try {
      await ApiClient.uploadTemplate(file);
      await loadTemplates();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Lỗi khi upload mẫu');
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleDeleteTemplate = async (id: string) => {
    if (!confirm('Xóa mẫu này?')) return;
    try {
      await ApiClient.deleteTemplate(id);
      setTemplates(prev => prev.filter(t => t.id !== id));
      if (selectedTemplate?.id === id) {
        setSelectedTemplate(null);
        setTemplateFormData({});
      }
    } catch { /* ignore */ }
  };

  const handleRenameTemplate = async (id: string, newName: string) => {
    if (!newName.trim()) return;
    try {
      const updated = await ApiClient.renameTemplate(id, newName.trim());
      setTemplates(prev => prev.map(t => t.id === id ? updated : t));
      if (selectedTemplate?.id === id) setSelectedTemplate(updated);
    } catch { /* ignore */ }
    setEditingNameId(null);
  };

  const handleTemplateGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedTemplate || !templateRepoId) return;
    setIsTemplateGenerating(true);
    setTemplateTaskStatus(null);

    try {
      const res = await ApiClient.generateFromTemplate(
        selectedTemplate.id,
        templateFormData,
        templateRepoId,
        selectedTemplateDocumentIds,
      );
      const taskId = res.task_id;

      const poll = async () => {
        const status = await ApiClient.getTemplateGenStatus(taskId);
        setTemplateTaskStatus(status);
        if (status.status === 'completed' || status.status === 'error') {
          setIsTemplateGenerating(false);
          // Refresh history
          if (selectedTemplate) {
            ApiClient.getTemplateHistory(selectedTemplate.id)
              .then(setHistory).catch(() => {});
          }
          return;
        }
        setTimeout(poll, 2000);
      };
      poll();
    } catch (err: any) {
      setTemplateTaskStatus({
        task_id: '', status: 'error', progress_message: '',
        error_message: err.response?.data?.detail || 'Lỗi khi tạo văn bản',
        output_ready: false,
      });
      setIsTemplateGenerating(false);
    }
  };

  const handleDeleteHistoryTask = async (taskId: string) => {
    if (!confirm('Bạn có chắc chắn muốn xóa lịch sử này?')) return;
    try {
      // Assuming this is custom template history
      await ApiClient.deleteTemplateTask(taskId);
      setHistory(prev => prev.filter(t => t.task_id !== taskId));
    } catch { /* ignore */ }
  };

  const handleTemplateReset = () => {
    setTemplateTaskStatus(null);
    setTemplateFormData({});
  };

  const allFields = selectedType
    ? [...selectedType.required_fields, ...selectedType.optional_fields]
    : [];
  const filteredDraftRepositories = selectedDraftCategoryId === ''
    ? repositories
    : selectedDraftCategoryId === '__uncategorized'
      ? repositories.filter(r => !r.category_id)
      : repositories.filter(r => r.category_id === selectedDraftCategoryId);
  const filteredTemplateRepositories = selectedTemplateCategoryId === ''
    ? repositories
    : selectedTemplateCategoryId === '__uncategorized'
      ? repositories.filter(r => !r.category_id)
      : repositories.filter(r => r.category_id === selectedTemplateCategoryId);
  const availableDraftDocuments = repoDocuments.filter(d => d.processing_status === 'completed');
  const availableTemplateDocuments = templateRepoDocuments.filter(d => d.processing_status === 'completed');

  const handleDraftCategoryChange = (categoryId: string) => {
    setSelectedDraftCategoryId(categoryId);
    const nextRepos = categoryId === ''
      ? repositories
      : categoryId === '__uncategorized'
        ? repositories.filter(r => !r.category_id)
        : repositories.filter(r => r.category_id === categoryId);
    setSelectedRepoId(nextRepos[0]?.id || '');
  };

  const handleDraftRepoChange = (repoId: string) => {
    setSelectedRepoId(repoId);
    const repo = repositories.find(r => r.id === repoId);
    if (repo) setSelectedDraftCategoryId(repo.category_id || '__uncategorized');
  };

  const handleTemplateCategoryChange = (categoryId: string) => {
    setSelectedTemplateCategoryId(categoryId);
    const nextRepos = categoryId === ''
      ? repositories
      : categoryId === '__uncategorized'
        ? repositories.filter(r => !r.category_id)
        : repositories.filter(r => r.category_id === categoryId);
    setTemplateRepoId(nextRepos[0]?.id || '');
  };

  const handleTemplateRepoChange = (repoId: string) => {
    setTemplateRepoId(repoId);
    const repo = repositories.find(r => r.id === repoId);
    if (repo) setSelectedTemplateCategoryId(repo.category_id || '__uncategorized');
  };

  return (
    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="max-w-6xl mx-auto space-y-6">
      <header className="mb-4">
        <h1 className="text-3xl font-bold text-slate-900 tracking-tight">Soạn Văn bản Hành chính</h1>
        <p className="text-slate-500 mt-2">Tự động soạn thảo văn bản từ mẫu chuẩn hoặc mẫu tùy chỉnh của bạn.</p>
      </header>

      {/* Tab Switcher */}
      <div className="flex gap-1 bg-slate-100 p-1 rounded-2xl w-fit">
        <button
          onClick={() => setActiveTab('standard')}
          className={`px-5 py-2.5 rounded-xl text-sm font-semibold transition-all ${
            activeTab === 'standard'
              ? 'bg-white text-blue-700 shadow-sm'
              : 'text-slate-500 hover:text-slate-700'
          }`}
        >
          <FileCode size={16} className="inline mr-2" />
          Mẫu chuẩn (NĐ 30)
        </button>
        <button
          onClick={() => setActiveTab('custom')}
          className={`px-5 py-2.5 rounded-xl text-sm font-semibold transition-all ${
            activeTab === 'custom'
              ? 'bg-white text-purple-700 shadow-sm'
              : 'text-slate-500 hover:text-slate-700'
          }`}
        >
          <Sparkles size={16} className="inline mr-2" />
          Mẫu tùy chỉnh
          {templates.length > 0 && (
            <span className="ml-2 px-2 py-0.5 bg-purple-100 text-purple-700 rounded-full text-xs">{templates.length}</span>
          )}
        </button>
      </div>

      {/* ═══════ Standard Templates Tab ═══════ */}
      {activeTab === 'standard' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Type List */}
          <div className="lg:col-span-1 space-y-3">
            <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider px-1">Chọn loại văn bản</div>
            {draftTypes.map((tpl) => (
              <div
                key={tpl.type_code}
                onClick={() => { setSelectedType(tpl); setFormData({}); setTaskStatus(null); }}
                className={`p-5 rounded-2xl cursor-pointer transition-all border ${
                  selectedType?.type_code === tpl.type_code
                    ? 'bg-blue-50 border-blue-500 shadow-md ring-2 ring-blue-500/20'
                    : 'bg-white border-slate-200 hover:border-blue-300 hover:shadow-sm'
                }`}
              >
                <div className="flex items-start gap-4">
                  <div className={`p-2.5 rounded-xl shrink-0 ${
                    selectedType?.type_code === tpl.type_code
                      ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/30'
                      : 'bg-slate-100 text-slate-500'
                  }`}>
                    <FileCode size={20} />
                  </div>
                  <div>
                    <h3 className={`font-bold ${selectedType?.type_code === tpl.type_code ? 'text-blue-900' : 'text-slate-800'}`}>
                      {tpl.name}
                    </h3>
                    <p className="text-xs text-slate-500 mt-1 line-clamp-2 leading-relaxed">{tpl.description}</p>
                  </div>
                </div>
              </div>
            ))}

            {draftTypes.length === 0 && (
              <div className="p-8 text-center bg-white rounded-2xl border border-dashed border-slate-300 text-slate-400">
                <Loader2 className="animate-spin mx-auto mb-2" />
                Đang tải...
              </div>
            )}
          </div>

          {/* Form / Result */}
          <div className="lg:col-span-2">
            {selectedType ? (
              <div className="bg-white rounded-3xl p-8 border border-slate-200 shadow-sm">
                <div className="flex items-center justify-between mb-6">
                  <h2 className="text-xl font-bold text-slate-800">
                    Soạn: {selectedType.name}
                  </h2>
                  <div className="flex flex-wrap items-center gap-2">
                    <div className="relative">
                      <Folder size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
                      <select
                        value={selectedDraftCategoryId}
                        onChange={(e) => handleDraftCategoryChange(e.target.value)}
                        className="w-44 bg-slate-50 border border-slate-200 rounded-lg pl-8 pr-3 py-1.5 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                      >
                        <option value="">Tất cả danh mục</option>
                        {categories.map(category => (
                          <option key={category.id} value={category.id}>
                            {category.is_shared ? 'Chia sẻ: ' : ''}{category.name}
                          </option>
                        ))}
                        <option value="__uncategorized">Chưa phân loại</option>
                      </select>
                    </div>
                    <div className="relative">
                      <Database size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-blue-600 pointer-events-none" />
                      <select
                        value={selectedRepoId}
                        onChange={(e) => handleDraftRepoChange(e.target.value)}
                        className="w-56 bg-slate-50 border border-slate-200 rounded-lg pl-8 pr-3 py-1.5 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
                      >
                        <option value="">-- Chọn kho dữ liệu --</option>
                        {filteredDraftRepositories.map(r => (
                          <option key={r.id} value={r.id}>{r.is_shared ? 'Chia sẻ: ' : ''}{r.name} ({r.document_count} tài liệu)</option>
                        ))}
                      </select>
                    </div>
                  </div>
                </div>

                {taskStatus ? (
                  <div className="space-y-6">
                    <div className={`p-6 rounded-2xl border ${
                      taskStatus.status === 'completed' ? 'bg-emerald-50 border-emerald-200' :
                      taskStatus.status === 'error' ? 'bg-rose-50 border-rose-200' :
                      'bg-blue-50 border-blue-200'
                    }`}>
                      <div className="flex items-center gap-3 mb-2">
                        {taskStatus.status === 'completed' && <CheckCircle className="text-emerald-600" size={24} />}
                        {taskStatus.status === 'error' && <AlertCircle className="text-rose-600" size={24} />}
                        {!['completed','error'].includes(taskStatus.status) && <Loader2 className="text-blue-600 animate-spin" size={24} />}
                        <span className="font-semibold text-lg">
                          {taskStatus.status === 'completed' ? 'Hoàn thành!' :
                           taskStatus.status === 'error' ? 'Lỗi' : 'Đang xử lý...'}
                        </span>
                      </div>
                      <p className="text-sm text-slate-600">{taskStatus.progress_message || taskStatus.error_message}</p>
                    </div>
                    <div className="flex gap-4">
                      <button onClick={handleReset}
                        className="flex-1 px-6 py-3 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl font-medium transition-colors flex items-center justify-center gap-2">
                        <RotateCcw size={18} /> Soạn văn bản khác
                      </button>
                      {taskStatus.output_ready && (
                        <>
                          <button onClick={() => openPreview('draft', taskStatus.task_id)}
                            className="flex-1 px-6 py-3 bg-slate-700 hover:bg-slate-800 text-white rounded-xl font-medium transition-colors flex items-center justify-center gap-2 shadow-lg shadow-slate-500/20">
                            <Eye size={18} /> Xem trước
                          </button>
                          <button onClick={() => openEditDraftModal(taskStatus.task_id)}
                            className="flex-1 px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-medium transition-colors flex items-center justify-center gap-2 shadow-lg shadow-blue-500/20">
                            <Pencil size={18} /> Chỉnh sửa
                          </button>
                          <a href={ApiClient.getDraftDownloadUrl(taskStatus.task_id)}
                            className="flex-1 px-6 py-3 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl font-medium transition-colors flex items-center justify-center gap-2 shadow-lg shadow-emerald-500/20">
                            <Download size={18} /> Tải xuống .docx
                          </a>
                        </>
                      )}
                    </div>
                  </div>
                ) : (
                  <form onSubmit={handleGenerate} className="space-y-5">
                    {selectedRepoId && (
                      <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                        <div className="flex items-start justify-between gap-4 mb-3">
                          <div>
                            <h3 className="text-sm font-bold text-slate-700 flex items-center gap-2">
                              <FileText size={16} className="text-blue-600" />
                              Tài liệu nguồn
                            </h3>
                            <p className="text-xs text-slate-500 mt-1">
                              {selectedDocumentIds.length > 0
                                ? `Chỉ dùng ${selectedDocumentIds.length} tài liệu đã chọn để soạn.`
                                : 'Không chọn tài liệu: hệ thống dùng toàn bộ tài liệu trong kho.'}
                            </p>
                          </div>
                          {availableDraftDocuments.length > 0 && (
                            <button
                              type="button"
                              onClick={() => {
                                if (selectedDocumentIds.length === availableDraftDocuments.length) {
                                  setSelectedDocumentIds([]);
                                } else {
                                  setSelectedDocumentIds(availableDraftDocuments.map(d => d.id));
                                }
                              }}
                              className="text-xs font-semibold text-blue-700 hover:text-blue-800"
                            >
                              {selectedDocumentIds.length === availableDraftDocuments.length ? 'Bỏ chọn tất cả' : 'Chọn tất cả'}
                            </button>
                          )}
                        </div>

                        {availableDraftDocuments.length === 0 ? (
                          <div className="text-sm text-slate-500 bg-white border border-dashed border-slate-200 rounded-xl p-3">
                            Kho này chưa có tài liệu đã xử lý xong để chọn.
                          </div>
                        ) : (
                          <div className="max-h-52 overflow-y-auto rounded-xl border border-slate-200 bg-white divide-y divide-slate-100">
                            {availableDraftDocuments.map(doc => {
                              const checked = selectedDocumentIds.includes(doc.id);
                              return (
                                <label key={doc.id} className="flex items-center gap-3 px-3 py-2.5 hover:bg-blue-50/50 cursor-pointer">
                                  <input
                                    type="checkbox"
                                    checked={checked}
                                    onChange={(e) => {
                                      setSelectedDocumentIds(prev =>
                                        e.target.checked
                                          ? [...prev, doc.id]
                                          : prev.filter(id => id !== doc.id)
                                      );
                                    }}
                                    className="h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                                  />
                                  <div className="min-w-0 flex-1">
                                    <p className="text-sm font-medium text-slate-700 truncate">{doc.filename}</p>
                                    <p className="text-xs text-slate-400">{formatFileSize(doc.file_size)}</p>
                                  </div>
                                </label>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    )}

                    {allFields.map((field) => {
                      const isRequired = selectedType.required_fields.includes(field);
                      const label = FIELD_LABELS[field] || field;
                      const isTextarea = ['noi_dung_chinh', 'can_cu', 'ly_do', 'kien_nghi', 'muc_dich', 'yeu_cau', 'danh_gia'].includes(field);
                      return (
                        <div key={field}>
                          <label className="block text-sm font-semibold text-slate-700 mb-2">
                            {label} {isRequired && <span className="text-rose-500">*</span>}
                          </label>
                          {isTextarea ? (
                            <textarea required={isRequired} rows={3}
                              value={formData[field] || ''}
                              onChange={e => setFormData({...formData, [field]: e.target.value})}
                              placeholder={`Nhập ${label.toLowerCase()}...`}
                              className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all placeholder:text-slate-400" />
                          ) : (
                            <input type="text" required={isRequired}
                              value={formData[field] || ''}
                              onChange={e => setFormData({...formData, [field]: e.target.value})}
                              placeholder={`Nhập ${label.toLowerCase()}...`}
                              className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all placeholder:text-slate-400" />
                          )}
                        </div>
                      );
                    })}
                    {!selectedRepoId && (
                      <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl text-amber-700 text-sm font-medium flex items-center gap-2">
                        <Database size={16} /> Vui lòng chọn kho dữ liệu trước khi soạn.
                      </div>
                    )}
                    <div className="pt-4 flex justify-end">
                      <button type="submit" disabled={isGenerating || !selectedRepoId}
                        className="px-8 py-3 bg-blue-600 hover:bg-blue-700 disabled:opacity-60 disabled:cursor-not-allowed text-white rounded-xl font-semibold flex items-center gap-2 transition-colors shadow-lg shadow-blue-600/20">
                        {isGenerating ? (
                          <><Loader2 size={18} className="animate-spin" /> Đang soạn...</>
                        ) : (
                          <><Play size={18} fill="currentColor" /> Soạn văn bản</>
                        )}
                      </button>
                    </div>
                  </form>
                )}

                {/* ── Draft Export History ── */}
                {draftHistory.length > 0 && (
                  <div className="mt-8 border-t border-slate-100 pt-6">
                    <h3 className="text-sm font-bold text-slate-600 flex items-center gap-2 mb-3">
                      <Clock size={16} className="text-slate-400" />
                      Lịch sử xuất file
                    </h3>
                    <div className="space-y-2">
                      {draftHistory.map((task) => (
                        <div key={task.task_id} className="flex items-center justify-between p-3 bg-slate-50 rounded-xl">
                          <div className="flex items-center gap-3">
                            {task.status === 'completed' ? (
                              <CheckCircle size={16} className="text-emerald-500 shrink-0" />
                            ) : task.status === 'error' ? (
                              <AlertCircle size={16} className="text-rose-500 shrink-0" />
                            ) : (
                              <Loader2 size={16} className="text-blue-500 animate-spin shrink-0" />
                            )}
                            <div>
                              <p className="text-xs font-medium text-slate-700">
                                {DOC_TYPE_NAMES[task.document_type || ''] || task.document_type || 'Văn bản'}
                                {' — '}
                                {task.status === 'completed' ? 'Hoàn thành' : task.status === 'error' ? 'Lỗi' : 'Đang xử lý'}
                              </p>
                              <p className="text-[10px] text-slate-400">
                                {new Date(task.created_at).toLocaleString('vi-VN')}
                              </p>
                            </div>
                          </div>
                          <div className="flex-shrink-0 flex items-center gap-2">
                            {task.output_ready && (
                              <>
                                <button onClick={() => openPreview('draft', task.task_id)}
                                  className="px-3 py-1.5 bg-slate-100 text-slate-700 rounded-lg text-xs font-semibold hover:bg-slate-200 transition-colors flex items-center gap-1.5">
                                  <Eye size={12} /> Xem
                                </button>
                                <button onClick={() => openEditDraftModal(task.task_id)}
                                  className="px-3 py-1.5 bg-blue-100 text-blue-700 rounded-lg text-xs font-semibold hover:bg-blue-200 transition-colors flex items-center gap-1.5">
                                  <Pencil size={12} /> Sửa
                                </button>
                                <a href={ApiClient.getDraftDownloadUrl(task.task_id)}
                                  className="px-3 py-1.5 bg-emerald-100 text-emerald-700 rounded-lg text-xs font-semibold hover:bg-emerald-200 transition-colors flex items-center gap-1.5">
                                  <Download size={12} /> Tải xuống
                                </a>
                              </>
                            )}
                            <button
                              onClick={async (e) => {
                                e.stopPropagation();
                                if (!confirm('Bạn có chắc chắn muốn xóa lịch sử này?')) return;
                                try {
                                  await ApiClient.deleteDraftHistoryTask(task.task_id);
                                  setDraftHistory(prev => prev.filter(t => t.task_id !== task.task_id));
                                } catch { /* ignore */ }
                              }}
                              title="Xóa lịch sử"
                              className="p-1.5 text-rose-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors"
                            >
                              <Trash2 size={14} />
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="h-full flex flex-col items-center justify-center text-slate-400 bg-slate-50/50 rounded-3xl border border-dashed border-slate-300 min-h-[400px]">
                <FileCode size={48} className="text-slate-300 mb-4" />
                <p className="font-medium">Chọn một loại văn bản từ danh sách bên trái</p>
                <p className="text-sm mt-1">để bắt đầu soạn thảo</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ═══════ Custom Templates Tab ═══════ */}
      {activeTab === 'custom' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left: Template List + Upload */}
          <div className="lg:col-span-1 space-y-3">
            <input ref={fileInputRef} type="file" accept=".docx,.pdf,.jpg,.jpeg,.png" className="hidden" onChange={handleTemplateUpload} />
            <button onClick={() => fileInputRef.current?.click()} disabled={isUploading}
              className="w-full p-4 rounded-2xl border-2 border-dashed border-purple-300 bg-purple-50/50 hover:bg-purple-50 text-purple-700 font-semibold transition-all flex items-center justify-center gap-3">
              {isUploading ? (
                <><Loader2 size={20} className="animate-spin" /> Đang upload...</>
              ) : (
                <><FileUp size={20} /> Upload mẫu (Word, PDF, Ảnh)</>
              )}
            </button>

            <div className="text-[10px] text-slate-400 px-2 leading-relaxed">
              Upload file mẫu (.docx, .pdf, .jpg, .png). AI tự phân tích cấu trúc và trích xuất đầu mục.
            </div>

            <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider px-1 pt-2">
              Mẫu đã upload ({templates.length})
            </div>

            <AnimatePresence>
              {templates.map(tpl => (
                <motion.div
                  key={tpl.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, x: -20 }}
                  onClick={() => {
                    if (tpl.status === 'ready') {
                      setSelectedTemplate(tpl);
                      setTemplateFormData({});
                      setTemplateTaskStatus(null);
                    }
                  }}
                  className={`p-4 rounded-2xl cursor-pointer transition-all border ${
                    selectedTemplate?.id === tpl.id
                      ? 'bg-purple-50 border-purple-500 shadow-md ring-2 ring-purple-500/20'
                      : tpl.status === 'error'
                        ? 'bg-rose-50/50 border-rose-200'
                        : tpl.status === 'analyzing'
                          ? 'bg-amber-50/50 border-amber-200'
                          : 'bg-white border-slate-200 hover:border-purple-300'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3 min-w-0 flex-1">
                      <div className={`p-2 rounded-lg shrink-0 ${
                        tpl.status === 'ready' ? 'bg-purple-100 text-purple-600'
                        : tpl.status === 'analyzing' ? 'bg-amber-100 text-amber-600'
                        : 'bg-rose-100 text-rose-600'
                      }`}>
                        {tpl.status === 'analyzing' ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
                      </div>
                      <div className="min-w-0 flex-1">
                        {editingNameId === tpl.id ? (
                          <div className="flex items-center gap-1" onClick={e => e.stopPropagation()}>
                            <input
                              autoFocus
                              value={editNameValue}
                              onChange={e => setEditNameValue(e.target.value)}
                              onKeyDown={e => {
                                if (e.key === 'Enter') handleRenameTemplate(tpl.id, editNameValue);
                                if (e.key === 'Escape') setEditingNameId(null);
                              }}
                              className="text-sm font-bold text-slate-800 bg-white border border-purple-300 rounded px-2 py-0.5 w-full focus:outline-none focus:ring-1 focus:ring-purple-400"
                            />
                            <button onClick={() => handleRenameTemplate(tpl.id, editNameValue)} className="p-1 text-emerald-500 hover:text-emerald-700"><Check size={14} /></button>
                            <button onClick={() => setEditingNameId(null)} className="p-1 text-slate-400 hover:text-slate-600"><X size={14} /></button>
                          </div>
                        ) : (
                          <p className="text-sm font-bold text-slate-800 truncate">{tpl.name}</p>
                        )}
                        <p className="text-[11px] text-slate-400 truncate">
                          {tpl.status === 'analyzing' ? 'AI đang phân tích cấu trúc...'
                            : tpl.status === 'error' ? tpl.error_message
                            : `${tpl.doc_type_label || ''} — ${tpl.headings.length} đầu mục`}
                        </p>
                      </div>
                    </div>
                    <div className="flex gap-1 shrink-0">
                      {tpl.status === 'ready' && (
                        <button
                          title="Đổi tên"
                          onClick={(e) => { e.stopPropagation(); setEditingNameId(tpl.id); setEditNameValue(tpl.name); }}
                          className="p-1.5 text-slate-300 hover:text-purple-500 hover:bg-purple-50 rounded-lg transition-colors"
                        >
                          <Pencil size={13} />
                        </button>
                      )}
                      <button
                        title="Xoá mẫu"
                        onClick={(e) => { e.stopPropagation(); handleDeleteTemplate(tpl.id); }}
                        className="p-1.5 text-slate-300 hover:text-rose-500 hover:bg-rose-50 rounded-lg transition-colors"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>

            {templates.length === 0 && (
              <div className="p-8 text-center bg-white rounded-2xl border border-dashed border-slate-300 text-slate-400">
                <Upload size={32} className="mx-auto mb-3 text-slate-300" />
                <p className="text-sm font-medium">Chưa có mẫu nào</p>
                <p className="text-xs mt-1">Upload file Word, PDF hoặc ảnh mẫu văn bản</p>
              </div>
            )}
          </div>

          {/* Right: Template Detail / Form / Status */}
          <div className="lg:col-span-2">
            {selectedTemplate ? (
              <div className="bg-white rounded-3xl p-8 border border-slate-200 shadow-sm">
                <div className="mb-6">
                  <h2 className="text-xl font-bold text-slate-800 flex items-center gap-2">
                    <Sparkles size={20} className="text-purple-500" />
                    {selectedTemplate.name}
                  </h2>
                  {selectedTemplate.description && (
                    <p className="text-sm text-slate-500 mt-1">{selectedTemplate.description}</p>
                  )}
                  <div className="flex items-center gap-3 mt-2">
                    {selectedTemplate.doc_type_label && (
                      <span className="px-2.5 py-1 bg-purple-100 text-purple-700 rounded-lg text-xs font-bold">
                        {selectedTemplate.doc_type_label}
                      </span>
                    )}
                    <span className="text-xs text-slate-400">
                      {selectedTemplate.headings.length} đầu mục — Xuất NĐ 30/2020
                    </span>
                  </div>

                  {/* Headings list */}
                  <div className="mt-4 space-y-2">
                    <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Đầu mục trích xuất</p>
                    {selectedTemplate.headings.map((h, idx) => (
                      <div key={h.key} className="flex items-start gap-2 p-2.5 bg-slate-50 rounded-xl">
                        <span className="text-xs font-bold text-purple-500 mt-0.5 shrink-0">{idx + 1}.</span>
                        <div>
                          <p className="text-sm font-semibold text-slate-700">{h.title}</p>
                          {h.description && <p className="text-xs text-slate-400 mt-0.5">{h.description}</p>}
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* Repo selector (required) */}
                  <div className="mt-5">
                    <label className="block text-sm font-semibold text-slate-700 mb-1.5">
                      <Database size={14} className="inline mr-1" />
                      Kho dữ liệu nguồn <span className="text-rose-500">*</span>
                    </label>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                      <div className="relative">
                        <Folder size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
                        <select
                          value={selectedTemplateCategoryId}
                          onChange={(e) => handleTemplateCategoryChange(e.target.value)}
                          className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-9 pr-4 py-2.5 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 transition-all"
                        >
                          <option value="">Tất cả danh mục</option>
                          {categories.map(category => (
                            <option key={category.id} value={category.id}>
                              {category.is_shared ? 'Chia sẻ: ' : ''}{category.name}
                            </option>
                          ))}
                          <option value="__uncategorized">Chưa phân loại</option>
                        </select>
                      </div>
                      <div className="relative">
                        <Database size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-purple-600 pointer-events-none" />
                        <select
                          value={templateRepoId}
                          onChange={(e) => handleTemplateRepoChange(e.target.value)}
                          className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-9 pr-4 py-2.5 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 transition-all"
                        >
                          <option value="">-- Chọn kho dữ liệu --</option>
                          {filteredTemplateRepositories.map(r => (
                            <option key={r.id} value={r.id}>{r.is_shared ? 'Chia sẻ: ' : ''}{r.name} ({r.document_count} tài liệu)</option>
                          ))}
                        </select>
                      </div>
                    </div>
                    <p className="text-[10px] text-slate-400 mt-1">AI sẽ tổng hợp nội dung từ tài liệu trong kho để viết cho từng đầu mục.</p>
                  </div>

                  {templateRepoId && (
                    <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 p-4">
                      <div className="flex items-start justify-between gap-4 mb-3">
                        <div>
                          <h3 className="text-sm font-bold text-slate-700 flex items-center gap-2">
                            <FileText size={16} className="text-purple-600" />
                            Tài liệu nguồn
                          </h3>
                          <p className="text-xs text-slate-500 mt-1">
                            {selectedTemplateDocumentIds.length > 0
                              ? `Chỉ dùng ${selectedTemplateDocumentIds.length} tài liệu đã chọn để tạo văn bản.`
                              : 'Không chọn tài liệu: hệ thống dùng toàn bộ tài liệu trong kho.'}
                          </p>
                        </div>
                        {availableTemplateDocuments.length > 0 && (
                          <button
                            type="button"
                            onClick={() => {
                              if (selectedTemplateDocumentIds.length === availableTemplateDocuments.length) {
                                setSelectedTemplateDocumentIds([]);
                              } else {
                                setSelectedTemplateDocumentIds(availableTemplateDocuments.map(d => d.id));
                              }
                            }}
                            className="text-xs font-semibold text-purple-700 hover:text-purple-800"
                          >
                            {selectedTemplateDocumentIds.length === availableTemplateDocuments.length ? 'Bỏ chọn tất cả' : 'Chọn tất cả'}
                          </button>
                        )}
                      </div>

                      {availableTemplateDocuments.length === 0 ? (
                        <div className="text-sm text-slate-500 bg-white border border-dashed border-slate-200 rounded-xl p-3">
                          Kho này chưa có tài liệu đã xử lý xong để chọn.
                        </div>
                      ) : (
                        <div className="max-h-52 overflow-y-auto rounded-xl border border-slate-200 bg-white divide-y divide-slate-100">
                          {availableTemplateDocuments.map(doc => {
                            const checked = selectedTemplateDocumentIds.includes(doc.id);
                            return (
                              <label key={doc.id} className="flex items-center gap-3 px-3 py-2.5 hover:bg-purple-50/50 cursor-pointer">
                                <input
                                  type="checkbox"
                                  checked={checked}
                                  onChange={(e) => {
                                    setSelectedTemplateDocumentIds(prev =>
                                      e.target.checked
                                        ? [...prev, doc.id]
                                        : prev.filter(id => id !== doc.id)
                                    );
                                  }}
                                  className="h-4 w-4 rounded border-slate-300 text-purple-600 focus:ring-purple-500"
                                />
                                <div className="min-w-0 flex-1">
                                  <p className="text-sm font-medium text-slate-700 truncate">{doc.filename}</p>
                                  <p className="text-xs text-slate-400">{formatFileSize(doc.file_size)}</p>
                                </div>
                              </label>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* Template Status Display */}
                {templateTaskStatus ? (
                  <div className="space-y-6">
                    <div className={`p-6 rounded-2xl border ${
                      templateTaskStatus.status === 'completed' ? 'bg-emerald-50 border-emerald-200' :
                      templateTaskStatus.status === 'error' ? 'bg-rose-50 border-rose-200' :
                      'bg-purple-50 border-purple-200'
                    }`}>
                      <div className="flex items-center gap-3 mb-2">
                        {templateTaskStatus.status === 'completed' && <CheckCircle className="text-emerald-600" size={24} />}
                        {templateTaskStatus.status === 'error' && <AlertCircle className="text-rose-600" size={24} />}
                        {!['completed','error'].includes(templateTaskStatus.status) && <Loader2 className="text-purple-600 animate-spin" size={24} />}
                        <span className="font-semibold text-lg">
                           {templateTaskStatus.status === 'completed' ? 'Hoàn thành!' :
                           templateTaskStatus.status === 'error' ? 'Lỗi' : 'AI đang sinh nội dung...'}
                        </span>
                      </div>
                      <p className="text-sm text-slate-600">{templateTaskStatus.progress_message || templateTaskStatus.error_message}</p>
                    </div>

                    <div className="flex gap-4">
                      <button onClick={handleTemplateReset}
                        className="flex-1 px-6 py-3 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl font-medium transition-colors flex items-center justify-center gap-2">
                        <RotateCcw size={18} /> Tạo văn bản khác
                      </button>
                      {templateTaskStatus.output_ready && (
                        <>
                          <button onClick={() => openPreview('template', templateTaskStatus.task_id)}
                            className="flex-1 px-6 py-3 bg-slate-700 hover:bg-slate-800 text-white rounded-xl font-medium transition-colors flex items-center justify-center gap-2 shadow-lg shadow-slate-500/20">
                            <Eye size={18} /> Xem trước
                          </button>
                          <a href={ApiClient.getTemplateDownloadUrl(templateTaskStatus.task_id)}
                            className="flex-1 px-6 py-3 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl font-medium transition-colors flex items-center justify-center gap-2 shadow-lg shadow-emerald-500/20">
                            <Download size={18} /> Tải xuống .docx
                          </a>
                        </>
                      )}
                    </div>
                  </div>
                ) : (
                  <form onSubmit={handleTemplateGenerate} className="space-y-5">
                    {/* Common fields */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      {[
                        { key: 'co_quan_chu_quan', label: 'Cơ quan chủ quản', ph: 'VD: UBND TỈNH TÂY NINH' },
                        { key: 'co_quan_ban_hanh', label: 'Cơ quan ban hành', ph: 'VD: SỞ KHOA HỌC VÀ CÔNG NGHỆ' },
                        { key: 'nguoi_ky', label: 'Người ký', ph: 'Họ tên' },
                        { key: 'chuc_vu_nguoi_ky', label: 'Chức vụ người ký', ph: 'VD: GIÁM ĐỐC' },
                      ].map(f => (
                        <div key={f.key}>
                          <label className="block text-xs font-semibold text-slate-500 mb-1">{f.label}</label>
                          <input type="text"
                            value={templateFormData[f.key] || ''}
                            onChange={e => setTemplateFormData({...templateFormData, [f.key]: e.target.value})}
                            placeholder={f.ph}
                            className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 transition-all placeholder:text-slate-400" />
                        </div>
                      ))}
                    </div>

                    {/* Heading hints */}
                    <div className="border-t border-slate-100 pt-4 mt-2">
                      <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">
                        Gợi ý nội dung (tùy chọn)
                      </p>
                      {selectedTemplate.headings.map((h) => (
                        <div key={h.key} className="mb-3">
                          <label className="block text-sm font-semibold text-slate-700 mb-1">{h.title}</label>
                          <textarea rows={2}
                            value={templateFormData[h.key] || ''}
                            onChange={e => setTemplateFormData({...templateFormData, [h.key]: e.target.value})}
                            placeholder={h.description || `Gợi ý cho mục "${h.title}" — để trống để AI tự viết`}
                            className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 transition-all placeholder:text-slate-400" />
                        </div>
                      ))}
                    </div>

                    {!templateRepoId && (
                      <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl text-amber-700 text-sm font-medium flex items-center gap-2">
                        <Database size={16} /> Vui lòng chọn kho dữ liệu trước khi tạo văn bản.
                      </div>
                    )}

                    <div className="pt-4 flex justify-end">
                      <button type="submit" disabled={isTemplateGenerating || !templateRepoId}
                        className="px-8 py-3 bg-purple-600 hover:bg-purple-700 disabled:opacity-60 disabled:cursor-not-allowed text-white rounded-xl font-semibold flex items-center gap-2 transition-colors shadow-lg shadow-purple-600/20">
                        {isTemplateGenerating ? (
                          <><Loader2 size={18} className="animate-spin" /> Đang sinh...</>
                        ) : (
                          <><Sparkles size={18} /> Tạo văn bản NĐ 30</>
                        )}
                      </button>
                    </div>
                  </form>
                )}

                {/* ── Generation History ── */}
                {history.length > 0 && (
                  <div className="mt-8 border-t border-slate-100 pt-6">
                    <h3 className="text-sm font-bold text-slate-600 flex items-center gap-2 mb-3">
                      <Clock size={16} className="text-slate-400" />
                      Lịch sử tạo văn bản
                    </h3>
                    <div className="space-y-2">
                      {history.map((task) => (
                        <div key={task.task_id} className="flex items-center justify-between p-3 bg-slate-50 rounded-xl">
                          <div className="flex items-center gap-3">
                            {task.status === 'completed' ? (
                              <CheckCircle size={16} className="text-emerald-500 shrink-0" />
                            ) : task.status === 'error' ? (
                              <AlertCircle size={16} className="text-rose-500 shrink-0" />
                            ) : (
                              <Loader2 size={16} className="text-purple-500 animate-spin shrink-0" />
                            )}
                            <div>
                              <p className="text-xs font-medium text-slate-700">
                                {task.status === 'completed' ? 'Hoàn thành' : task.status === 'error' ? 'Lỗi' : 'Đang xử lý'}
                              </p>
                              <p className="text-[10px] text-slate-400">
                                {new Date(task.created_at).toLocaleString('vi-VN')}
                              </p>
                            </div>
                          </div>
                          <div className="flex-shrink-0 flex items-center gap-2">
                            {task.output_ready && (
                              <>
                                <button onClick={() => openPreview('template', task.task_id)}
                                  className="px-3 py-1.5 bg-slate-100 text-slate-700 rounded-lg text-xs font-semibold hover:bg-slate-200 transition-colors flex items-center gap-1.5">
                                  <Eye size={12} /> Xem
                                </button>
                                <a href={ApiClient.getTemplateDownloadUrl(task.task_id)}
                                  className="px-3 py-1.5 bg-emerald-100 text-emerald-700 rounded-lg text-xs font-semibold hover:bg-emerald-200 transition-colors flex items-center gap-1.5">
                                  <Download size={12} /> Tải xuống
                                </a>
                              </>
                            )}
                            <button
                              onClick={(e) => { e.stopPropagation(); handleDeleteHistoryTask(task.task_id); }}
                              title="Xóa lịch sử"
                              className="p-1.5 text-rose-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors"
                            >
                              <Trash2 size={14} />
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="h-full flex flex-col items-center justify-center text-slate-400 bg-purple-50/30 rounded-3xl border border-dashed border-purple-200 min-h-[400px]">
                <Sparkles size={48} className="text-purple-200 mb-4" />
                <p className="font-medium text-slate-500">Chọn mẫu từ danh sách hoặc upload mẫu mới</p>
                <p className="text-sm mt-1">Upload file Word, PDF hoặc ảnh mẫu văn bản — AI tự trích xuất đầu mục</p>
              </div>
            )}
          </div>
        </div>
      )}

      <AnimatePresence>
        {(previewHtml || isPreviewLoading) && (
          <motion.div
            className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/55 px-4 py-6 backdrop-blur-sm"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <motion.div
              initial={{ opacity: 0, y: 18, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 12, scale: 0.98 }}
              transition={{ duration: 0.18 }}
              className="flex h-[90vh] w-full max-w-6xl flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl"
            >
              <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
                <h3 className="text-lg font-bold text-slate-900">{previewTitle}</h3>
                <button
                  type="button"
                  onClick={closePreview}
                  className="rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
                  aria-label="Đóng"
                >
                  <X size={18} />
                </button>
              </div>
              <div className="min-h-0 flex-1 bg-slate-100">
                {isPreviewLoading ? (
                  <div className="flex h-full items-center justify-center text-slate-500">
                    <Loader2 size={22} className="mr-2 animate-spin" /> Đang tải bản xem trước...
                  </div>
                ) : (
                  <iframe
                    title={previewTitle}
                    srcDoc={previewHtml}
                    className="h-full w-full border-0"
                    sandbox=""
                  />
                )}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {editDraftTaskId && (
          <motion.div
            className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/45 px-4 backdrop-blur-sm"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <motion.div
              initial={{ opacity: 0, y: 18, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 12, scale: 0.98 }}
              transition={{ duration: 0.18 }}
              className="w-full max-w-xl overflow-hidden rounded-2xl bg-white shadow-2xl border border-slate-200"
            >
              <div className="flex items-start justify-between border-b border-slate-100 px-6 py-5">
                <div>
                  <h3 className="text-lg font-bold text-slate-900">Chỉnh sửa file Word đã xuất</h3>
                  <p className="mt-1 text-sm text-slate-500">
                    AI sẽ sửa trực tiếp nội dung trong file hiện có, không soạn văn bản mới.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={closeEditDraftModal}
                  disabled={isGenerating}
                  className="rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-700 disabled:opacity-50"
                  aria-label="Đóng"
                >
                  <X size={18} />
                </button>
              </div>

              <div className="px-6 py-5 space-y-3">
                <label className="block text-sm font-semibold text-slate-700">
                  Yêu cầu chỉnh sửa
                </label>
                <textarea
                  autoFocus
                  rows={6}
                  value={editInstruction}
                  onChange={(e) => setEditInstruction(e.target.value)}
                  placeholder="Ví dụ: Rút gọn phần II, bổ sung thời gian thực hiện cho nhiệm vụ 3, đổi cơ quan phối hợp thành Văn phòng UBND tỉnh..."
                  className="w-full resize-none rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-800 outline-none transition-all placeholder:text-slate-400 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
                />
                <div className="rounded-xl border border-blue-100 bg-blue-50 px-4 py-3 text-sm text-blue-800">
                  Nên nêu rõ mục, đoạn hoặc cụm từ cần sửa để AI thay đúng phần trong file.
                </div>
              </div>

              <div className="flex items-center justify-end gap-3 border-t border-slate-100 bg-slate-50 px-6 py-4">
                <button
                  type="button"
                  onClick={closeEditDraftModal}
                  disabled={isGenerating}
                  className="rounded-xl px-5 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-200 disabled:opacity-50"
                >
                  Hủy
                </button>
                <button
                  type="button"
                  onClick={submitEditDraft}
                  disabled={isGenerating || !editInstruction.trim()}
                  className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white shadow-lg shadow-blue-600/20 hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {isGenerating ? <Loader2 size={16} className="animate-spin" /> : <Pencil size={16} />}
                  Chỉnh sửa file
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
