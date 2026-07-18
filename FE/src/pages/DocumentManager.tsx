import { useState, useCallback, useEffect, useRef } from "react";
import { DocxEditor, type DocxEditorRef } from "@eigenpal/docx-editor-react";
import "@eigenpal/docx-editor-react/styles.css";
import { ApiClient, getStoredUser } from "../api/client";
import type { Repository, Document, RepositoryCategory } from "../api/client";
import { motion, AnimatePresence } from "framer-motion";
import {
  Database,
  Plus,
  Trash2,
  UploadCloud,
  File as FileIcon,
  ChevronRight,
  ChevronLeft,
  FolderOpen,
  X,
  Globe,
  Lock,
  Share2,
  Loader2,
  CheckCircle2,
  Folder,
  Pencil,
  Eye,
  Download,
  Save,
} from "lucide-react";

const DOCUMENT_FOLDERS = [
  { key: "draft", name: "Dự thảo" },
  { key: "feedback", name: "Văn bản góp ý" },
  { key: "summary", name: "Bảng tổng hợp ý kiến" },
  { key: "final", name: "Hoàn thiện dự thảo" },
] as const;

type DocumentFolderKey = (typeof DOCUMENT_FOLDERS)[number]["key"];
const UPLOAD_CONCURRENCY = 3;

export function RepositoryManager() {
  const [repos, setRepos] = useState<Repository[]>([]);
  const [categories, setCategories] = useState<RepositoryCategory[]>([]);
  const [selectedRepo, setSelectedRepo] = useState<Repository | null>(null);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [selectedFolderKey, setSelectedFolderKey] =
    useState<DocumentFolderKey>("draft");
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<{
    completed: number;
    total: number;
  } | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [newRepoName, setNewRepoName] = useState("");
  const [newRepoDesc, setNewRepoDesc] = useState("");
  const [newRepoCategoryId, setNewRepoCategoryId] = useState("");
  const [newCategoryName, setNewCategoryName] = useState("");
  const [categoryError, setCategoryError] = useState("");
  const [isCreatingCategory, setIsCreatingCategory] = useState(false);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [renameTarget, setRenameTarget] = useState<
    | { type: "repo"; item: Repository }
    | { type: "category"; item: RepositoryCategory }
    | null
  >(null);
  const [renameValue, setRenameValue] = useState("");
  const [renameCategoryId, setRenameCategoryId] = useState("");
  const [renameError, setRenameError] = useState("");
  const [isRenaming, setIsRenaming] = useState(false);
  const [error, setError] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const [createSuccess, setCreateSuccess] = useState(false);
  const [isRepoListCollapsed, setIsRepoListCollapsed] = useState(false);
  const [viewingDocId, setViewingDocId] = useState<string | null>(null);
  const [downloadingDocId, setDownloadingDocId] = useState<string | null>(null);
  const [updatingDocId, setUpdatingDocId] = useState<string | null>(null);
  const [editTargetDoc, setEditTargetDoc] = useState<Document | null>(null);
  const [docxEditorDoc, setDocxEditorDoc] = useState<Document | null>(null);
  const [docxEditorBuffer, setDocxEditorBuffer] = useState<ArrayBuffer | null>(
    null
  );
  const [docxEditorError, setDocxEditorError] = useState("");
  const [docxEditorDirty, setDocxEditorDirty] = useState(false);
  const [loadingDocxEditorId, setLoadingDocxEditorId] = useState<string | null>(
    null
  );
  const [isDocxEditorSaving, setIsDocxEditorSaving] = useState(false);
  const editFileInputRef = useRef<HTMLInputElement | null>(null);
  const docxEditorRef = useRef<DocxEditorRef | null>(null);
  const docxEditorSavingRef = useRef(false);

  const fetchRepos = useCallback(async () => {
    try {
      const data = await ApiClient.getRepositories();
      setRepos(data);
    } catch (err) {
      console.error(err);
    }
  }, []);

  const fetchCategories = useCallback(async () => {
    try {
      const data = await ApiClient.getRepositoryCategories();
      setCategories(data);
    } catch (err) {
      console.error(err);
    }
  }, []);

  const fetchDocs = useCallback(async (repoId: string) => {
    try {
      const data = await ApiClient.getDocuments(repoId);
      setDocuments(data);
    } catch (err) {
      console.error(err);
    }
  }, []);

  useEffect(() => {
    fetchRepos();
    fetchCategories();
  }, [fetchRepos, fetchCategories]);

  useEffect(() => {
    if (selectedRepo) fetchDocs(selectedRepo.id);
  }, [selectedRepo, fetchDocs]);

  useEffect(() => {
    if (!selectedRepo) return;
    const hasActiveDocs = documents.some((doc) =>
      ["queued", "processing"].includes(doc.processing_status)
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
    if (newRepoCategoryId === "__new__") {
      setCategoryError("Vui lòng tạo danh mục mới trước khi tạo kho");
      return;
    }
    setError("");
    setIsCreating(true);
    setCreateSuccess(false);
    try {
      const repo = await ApiClient.createRepository(
        newRepoName,
        newRepoDesc,
        newRepoCategoryId || undefined
      );
      setCreateSuccess(true);
      await fetchRepos();
      // Show success briefly before closing
      setTimeout(() => {
        setNewRepoName("");
        setNewRepoDesc("");
        setNewRepoCategoryId("");
        setNewCategoryName("");
        setCategoryError("");
        setShowCreateForm(false);
        setCreateSuccess(false);
        setIsCreating(false);
        handleSelectRepo(repo);
      }, 1200);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Lỗi khi tạo kho");
      setIsCreating(false);
    }
  };

  const handleSelectRepo = (repo: Repository) => {
    setSelectedRepo(repo);
    setSelectedFolderKey("draft");
  };

  const handleViewDoc = async (doc: Document) => {
    if (!selectedRepo || viewingDocId) return;

    const popup = window.open("", "_blank");
    setViewingDocId(doc.id);
    try {
      const blob = await ApiClient.getDocumentFile(selectedRepo.id, doc.id);
      const url = URL.createObjectURL(blob);
      if (popup) {
        popup.location.href = url;
      } else {
        window.open(url, "_blank");
      }
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (err: any) {
      popup?.close();
      alert(err.response?.data?.detail || "Không thể mở file");
    } finally {
      setViewingDocId(null);
    }
  };

  const handleDownloadDoc = async (doc: Document) => {
    if (!selectedRepo || downloadingDocId) return;

    setDownloadingDocId(doc.id);
    try {
      const blob = await ApiClient.getDocumentFile(selectedRepo.id, doc.id);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = doc.filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (err: any) {
      alert(err.response?.data?.detail || "Không thể tải file");
    } finally {
      setDownloadingDocId(null);
    }
  };

  const isWordDocument = (filename: string) =>
    /\.(doc|docx)$/i.test(filename.trim());

  const isDocxDocument = (filename: string) => /\.docx$/i.test(filename.trim());

  const closeDocxEditor = () => {
    if (isDocxEditorSaving) return;
    if (
      docxEditorDirty &&
      !confirm("Đóng trình soạn thảo? Các thay đổi chưa lưu sẽ bị mất.")
    ) {
      return;
    }
    setDocxEditorDoc(null);
    setDocxEditorBuffer(null);
    setDocxEditorError("");
    setDocxEditorDirty(false);
  };

  const openDocxEditor = async (doc: Document) => {
    if (!selectedRepo || selectedRepo.is_shared || loadingDocxEditorId) return;
    if (!isDocxDocument(doc.filename)) {
      alert("Trình soạn thảo trực tiếp hiện chỉ hỗ trợ file .docx.");
      return;
    }

    setDocxEditorDoc(doc);
    setDocxEditorBuffer(null);
    setDocxEditorError("");
    setDocxEditorDirty(false);
    setLoadingDocxEditorId(doc.id);
    try {
      const blob = await ApiClient.getDocumentFile(selectedRepo.id, doc.id);
      setDocxEditorBuffer(await blob.arrayBuffer());
    } catch (err: any) {
      setDocxEditorError(err.response?.data?.detail || "Không thể mở file DOCX");
    } finally {
      setLoadingDocxEditorId(null);
    }
  };

  const saveDocxEditorBuffer = async (buffer: ArrayBuffer) => {
    if (!selectedRepo || !docxEditorDoc || docxEditorSavingRef.current) return;

    docxEditorSavingRef.current = true;
    setIsDocxEditorSaving(true);
    setDocxEditorError("");
    try {
      const file = new File([buffer], docxEditorDoc.filename, {
        type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      });
      await ApiClient.replaceDocument(selectedRepo.id, docxEditorDoc.id, file);
      await fetchDocs(selectedRepo.id);
      await fetchRepos();
      setDocxEditorDirty(false);
      setDocxEditorDoc(null);
      setDocxEditorBuffer(null);
    } catch (err: any) {
      setDocxEditorError(err.response?.data?.detail || "Không thể lưu file DOCX");
    } finally {
      docxEditorSavingRef.current = false;
      setIsDocxEditorSaving(false);
    }
  };

  const saveDocxEditor = async () => {
    const buffer = await docxEditorRef.current?.save({ selective: false });
    if (!buffer) {
      setDocxEditorError("Không thể xuất nội dung DOCX để lưu.");
      return;
    }
    await saveDocxEditorBuffer(buffer);
  };

  const openReplaceDocPicker = (doc: Document) => {
    if (!selectedRepo || selectedRepo.is_shared || updatingDocId) return;
    setEditTargetDoc(doc);
    editFileInputRef.current?.click();
  };

  const handleReplaceDoc = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file || !selectedRepo || !editTargetDoc) return;

    if (!isWordDocument(file.name)) {
      alert("Vui lòng chọn file Word (.doc hoặc .docx) để thay thế.");
      setEditTargetDoc(null);
      return;
    }

    setUpdatingDocId(editTargetDoc.id);
    try {
      await ApiClient.replaceDocument(selectedRepo.id, editTargetDoc.id, file);
      await fetchDocs(selectedRepo.id);
      await fetchRepos();
    } catch (err: any) {
      alert(err.response?.data?.detail || "Không thể cập nhật file");
    } finally {
      setUpdatingDocId(null);
      setEditTargetDoc(null);
    }
  };

  const openRenameRepoModal = (repo: Repository) => {
    if (repo.is_shared) return;
    setRenameTarget({ type: "repo", item: repo });
    setRenameValue(repo.name);
    setRenameCategoryId(repo.category_id || "");
    setRenameError("");
  };

  const handleDeleteRepo = async (id: string) => {
    if (!confirm("Xóa kho này? Toàn bộ tài liệu và lịch sử chat sẽ bị xóa."))
      return;
    try {
      await ApiClient.deleteRepository(id);
      if (selectedRepo?.id === id) {
        setSelectedRepo(null);
        setDocuments([]);
      }
      fetchRepos();
    } catch (err) {
      console.error(err);
    }
  };

  const handleCreateCategory = async () => {
    if (!newCategoryName.trim() || isCreatingCategory) return;
    setCategoryError("");
    setIsCreatingCategory(true);
    try {
      const category = await ApiClient.createRepositoryCategory(
        newCategoryName.trim()
      );
      setNewRepoCategoryId(category.id);
      setNewCategoryName("");
      await fetchCategories();
    } catch (err: any) {
      setCategoryError(err.response?.data?.detail || "Lỗi tạo danh mục");
    } finally {
      setIsCreatingCategory(false);
    }
  };

  const openRenameCategoryModal = (category: RepositoryCategory) => {
    if (category.is_shared) return;
    setRenameTarget({ type: "category", item: category });
    setRenameValue(category.name);
    setRenameCategoryId("");
    setRenameError("");
  };

  const closeRenameModal = () => {
    if (isRenaming) return;
    setRenameTarget(null);
    setRenameValue("");
    setRenameCategoryId("");
    setRenameError("");
  };

  const submitRename = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!renameTarget || isRenaming) return;
    const name = renameValue.trim();
    if (!name) {
      setRenameError("Vui lòng nhập tên mới");
      return;
    }
    const categoryChanged =
      renameTarget.type === "repo" &&
      renameCategoryId !== (renameTarget.item.category_id || "");
    if (name === renameTarget.item.name && !categoryChanged) {
      closeRenameModal();
      return;
    }

    setIsRenaming(true);
    setRenameError("");
    try {
      if (renameTarget.type === "repo") {
        const updated = await ApiClient.updateRepository(renameTarget.item.id, {
          name,
          category_id: renameCategoryId || null,
        });
        if (selectedRepo?.id === renameTarget.item.id) setSelectedRepo(updated);
      } else {
        await ApiClient.updateRepositoryCategory(renameTarget.item.id, {
          name,
        });
        if (selectedRepo?.category_id === renameTarget.item.id) {
          setSelectedRepo({ ...selectedRepo, category_name: name });
        }
      }
      await fetchCategories();
      await fetchRepos();
      setRenameTarget(null);
      setRenameValue("");
      setRenameCategoryId("");
    } catch (err: any) {
      setRenameError(
        err.response?.data?.detail ||
          (renameTarget.type === "repo"
            ? "Lỗi đổi tên kho"
            : "Lỗi đổi tên danh mục")
      );
    } finally {
      setIsRenaming(false);
    }
  };

  const handleToggleCategoryShare = async (category: RepositoryCategory) => {
    try {
      await ApiClient.updateRepositoryCategory(category.id, {
        is_public: !category.is_public,
      });
      fetchCategories();
    } catch (err: any) {
      alert(err.response?.data?.detail || "Lỗi cập nhật danh mục");
    }
  };

  const handleDeleteCategory = async (category: RepositoryCategory) => {
    if (
      !confirm(
        "Xóa danh mục này? Các kho trong danh mục sẽ chuyển về chưa phân loại."
      )
    )
      return;
    try {
      await ApiClient.deleteRepositoryCategory(category.id);
      if (selectedRepo?.category_id === category.id) {
        setSelectedRepo({
          ...selectedRepo,
          category_id: null,
          category_name: null,
        });
      }
      await fetchCategories();
      await fetchRepos();
    } catch (err: any) {
      alert(err.response?.data?.detail || "Lỗi xóa danh mục");
    }
  };

  const uploadFiles = async (fileList: FileList | File[]) => {
    if (!selectedRepo || isUploading) return;
    const files = Array.from(fileList).filter((file) => file.size > 0);
    if (files.length === 0) return;

    const repoId = selectedRepo.id;
    const folderKey = selectedFolderKey;
    const errors: string[] = [];
    let completed = 0;

    setIsUploading(true);
    setUploadProgress({ completed: 0, total: files.length });

    const uploadOne = async (file: File) => {
      try {
        await ApiClient.uploadDocument(repoId, file, folderKey);
      } catch (err: any) {
        errors.push(
          `${file.name}: ${err.response?.data?.detail || "Lỗi upload"}`
        );
      } finally {
        completed += 1;
        setUploadProgress({ completed, total: files.length });
      }
    };

    try {
      const workerCount = Math.min(UPLOAD_CONCURRENCY, files.length);
      await Promise.all(
        Array.from({ length: workerCount }, async (_, workerIndex) => {
          for (let index = workerIndex; index < files.length; index += workerCount) {
            await uploadOne(files[index]);
          }
        })
      );
      await fetchDocs(repoId);
      await fetchRepos();
      if (errors.length > 0) {
        const preview = errors.slice(0, 5).join("\n");
        const suffix =
          errors.length > 5 ? `\n...và ${errors.length - 5} file khác` : "";
        alert(`Một số file upload thất bại:\n${preview}${suffix}`);
      }
    } finally {
      setIsUploading(false);
      setUploadProgress(null);
    }
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) await uploadFiles(e.target.files);
    e.target.value = "";
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
    if (!selectedRepo || !confirm("Xóa tài liệu này?")) return;
    try {
      await ApiClient.deleteDocument(selectedRepo.id, docId);
      fetchDocs(selectedRepo.id);
      fetchRepos();
    } catch (err) {
      console.error(err);
    }
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const selectedFolder =
    DOCUMENT_FOLDERS.find((folder) => folder.key === selectedFolderKey) ||
    DOCUMENT_FOLDERS[0];
  const visibleDocuments = documents.filter(
    (doc) => (doc.folder_key || "draft") === selectedFolderKey
  );
  const folderDocumentCount = (folderKey: DocumentFolderKey) =>
    documents.filter((doc) => (doc.folder_key || "draft") === folderKey).length;

  const ownCategories = categories.filter((c) => !c.is_shared);
  const sharedCategories = categories.filter((c) => c.is_shared);
  const ownRepos = repos.filter((r) => !r.is_shared);
  const sharedRepos = repos.filter((r) => r.is_shared);
  const uncategorizedOwnRepos = ownRepos.filter((r) => !r.category_id);
  const uncategorizedSharedRepos = sharedRepos.filter(
    (r) =>
      !r.category_id || !sharedCategories.some((c) => c.id === r.category_id)
  );

  const renderRepoCard = (repo: Repository, shared = false) => (
    <div
      key={repo.id}
      onClick={() => handleSelectRepo(repo)}
      className={`p-3 rounded-xl cursor-pointer transition-all border ${
        selectedRepo?.id === repo.id
          ? shared
            ? "bg-amber-50 border-amber-300 shadow-sm"
            : "bg-white border-blue-500 shadow-sm"
          : shared
          ? "bg-white border-slate-200 hover:border-amber-300 hover:shadow-sm"
          : "bg-white border-slate-200 hover:border-blue-300 hover:shadow-sm"
      }`}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center flex-1 min-w-0">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h3 className="font-semibold text-slate-800 truncate">
                {repo.name}
              </h3>
              {!shared && repo.is_public && (
                <Globe size={12} className="text-emerald-500 shrink-0" />
              )}
            </div>
            <p className="text-xs text-slate-500 truncate">
              {shared && repo.owner_name ? `Từ ${repo.owner_name} · ` : ""}
              {repo.document_count} tài liệu
            </p>
          </div>
        </div>
        <div className="flex items-center gap-1">
          {selectedRepo?.id === repo.id ? (
            <span className="h-2 w-2 rounded-full bg-blue-600" />
          ) : (
            <ChevronRight size={16} className="text-slate-400" />
          )}
        </div>
      </div>
    </div>
  );

  const renderCategoryBlock = (
    category: RepositoryCategory,
    categoryRepos: Repository[],
    shared = false
  ) => (
    <div key={category.id} className="space-y-2">
      <div
        className={`flex items-center justify-between text-xs font-semibold uppercase tracking-wider px-1 pt-3 ${
          shared ? "text-amber-600" : "text-slate-600"
        }`}
      >
        <div className="flex items-center gap-1 min-w-0">
          <Folder size={13} />
          <span className="truncate">{category.name}</span>
          {shared && category.owner_name && (
            <span className="normal-case font-normal text-slate-400 truncate">
              · {category.owner_name}
            </span>
          )}
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
              className={`p-1.5 rounded-lg transition-colors ${
                category.is_public
                  ? "text-emerald-600 hover:bg-emerald-50"
                  : "text-slate-400 hover:bg-slate-100"
              }`}
              title={
                category.is_public
                  ? "Đang chia sẻ danh mục"
                  : "Chia sẻ danh mục"
              }
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
      {categoryRepos.map((repo) => renderRepoCard(repo, shared))}
    </div>
  );

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="max-w-7xl mx-auto space-y-6"
    >
      <input
        ref={editFileInputRef}
        type="file"
        accept=".doc,.docx,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        className="hidden"
        onChange={handleReplaceDoc}
      />

      <header className="flex justify-between items-start">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 tracking-tight">
            Kho dữ liệu
          </h1>
        </div>
        <button
          onClick={() => setShowCreateForm(true)}
          className="px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-medium flex items-center gap-2 shadow-lg shadow-blue-600/20 transition-colors"
        >
          <Plus size={18} /> Tạo kho mới
        </button>
      </header>

      <div
        className={`grid grid-cols-1 gap-6 transition-all duration-300 ${
          isRepoListCollapsed
            ? "lg:grid-cols-[56px_minmax(0,1fr)]"
            : "lg:grid-cols-[minmax(160px,190px)_minmax(0,1fr)]"
        }`}
      >
        {/* Repo List */}
        <aside className="space-y-3 transition-all duration-300">
          {isRepoListCollapsed ? (
            <button
              type="button"
              onClick={() => setIsRepoListCollapsed(false)}
              className="w-full min-h-16 rounded-xl border border-slate-200 bg-white text-slate-500 hover:text-blue-600 hover:border-blue-300 hover:bg-blue-50/50 transition-colors flex flex-col items-center justify-center gap-1 shadow-sm"
              title="Mở danh sách kho"
            >
              <Database size={20} />
              <ChevronRight size={16} />
            </button>
          ) : (
            <>
              <div className="flex items-center justify-between px-1">
                <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                  Kho cá nhân · {ownRepos.length}
                </div>
                <button
                  type="button"
                  onClick={() => setIsRepoListCollapsed(true)}
                  className="p-1.5 rounded-lg text-slate-400 hover:text-blue-600 hover:bg-blue-50 transition-colors"
                  title="Thu gọn danh sách kho"
                >
                  <ChevronLeft size={16} />
                </button>
              </div>

              {ownRepos.length === 0 && sharedRepos.length === 0 ? (
                <div className="p-6 text-center bg-white rounded-xl border border-dashed border-slate-300 text-slate-400">
                  <Database size={34} className="mx-auto mb-3 text-slate-300" />
                  <p className="font-medium">Chưa có kho nào</p>
                  <p className="text-sm mt-1">Tạo kho đầu tiên để bắt đầu</p>
                </div>
              ) : (
                <>
                  {ownCategories.map((category) => {
                    const categoryRepos = ownRepos.filter(
                      (repo) => repo.category_id === category.id
                    );
                    return renderCategoryBlock(category, categoryRepos, false);
                  })}

                  {uncategorizedOwnRepos.length > 0 && (
                    <div className="space-y-2">
                      <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider px-1 pt-3 flex items-center gap-1">
                        <Database size={13} />
                        Chưa phân loại
                      </div>
                      {uncategorizedOwnRepos.map((repo) =>
                        renderRepoCard(repo, false)
                      )}
                    </div>
                  )}

                  {sharedRepos.length > 0 && (
                    <>
                      <div className="text-xs font-semibold text-amber-600 uppercase tracking-wider px-1 pt-4 flex items-center gap-1">
                        <Share2 size={12} />
                        Kho chia sẻ từ đơn vị
                      </div>
                      {sharedCategories.map((category) => {
                        const categoryRepos = sharedRepos.filter(
                          (repo) => repo.category_id === category.id
                        );
                        return categoryRepos.length > 0
                          ? renderCategoryBlock(category, categoryRepos, true)
                          : null;
                      })}
                      {uncategorizedSharedRepos.map((repo) =>
                        renderRepoCard(repo, true)
                      )}
                    </>
                  )}
                </>
              )}
            </>
          )}
        </aside>

        {/* Repo Detail + Docs */}
        <section className="min-w-0 transition-all duration-300">
          {selectedRepo ? (
            <div className="space-y-5">
              {/* Header */}
              <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
                <div className="flex items-start gap-4">
                  <button
                    onClick={() => setSelectedRepo(null)}
                    className="lg:hidden p-2 text-slate-400 hover:text-slate-600 rounded-lg"
                  >
                    <ChevronLeft size={20} />
                  </button>
                  <div className="w-11 h-11 rounded-lg bg-blue-600 flex items-center justify-center shadow-sm shrink-0">
                    <Database size={21} className="text-white" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <h2 className="text-xl font-bold text-slate-900 truncate max-w-full">
                        {selectedRepo.name}
                      </h2>
                      {selectedRepo.is_shared && (
                        <span className="px-2 py-1 bg-amber-100 text-amber-700 rounded-md text-xs font-semibold">
                          Kho chia sẻ
                        </span>
                      )}
                      {!selectedRepo.is_shared && selectedRepo.is_public && (
                        <span className="px-2 py-1 bg-emerald-100 text-emerald-700 rounded-md text-xs font-semibold">
                          Công khai
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-slate-500">
                      {selectedRepo.description || "Không có mô tả"}
                    </p>
                  </div>
                  <div className="flex items-center gap-1 shrink-0">
                    {!selectedRepo.is_shared && (
                      <>
                        <button
                          onClick={() => openRenameRepoModal(selectedRepo)}
                          className="p-2 rounded-lg text-slate-400 hover:text-blue-600 hover:bg-blue-50 transition-colors"
                          title="Đổi tên kho"
                        >
                          <Pencil size={16} />
                        </button>
                        <button
                          onClick={async () => {
                            try {
                              await ApiClient.updateRepository(
                                selectedRepo.id,
                                {
                                  is_public: !selectedRepo.is_public,
                                }
                              );
                              const updated = {
                                ...selectedRepo,
                                is_public: !selectedRepo.is_public,
                              };
                              setSelectedRepo(updated);
                              fetchRepos();
                              fetchCategories();
                            } catch {
                              /* ignore */
                            }
                          }}
                          className="p-2 rounded-lg text-slate-400 hover:text-emerald-600 hover:bg-emerald-50 transition-colors"
                          title={
                            selectedRepo.is_public
                              ? "Chuyển về riêng tư"
                              : "Chia sẻ kho"
                          }
                        >
                          {selectedRepo.is_public ? (
                            <Globe size={16} />
                          ) : (
                            <Lock size={16} />
                          )}
                        </button>
                        <button
                          onClick={() => handleDeleteRepo(selectedRepo.id)}
                          className="p-2 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors"
                          title="Xóa kho"
                        >
                          <Trash2 size={16} />
                        </button>
                      </>
                    )}
                  </div>
                </div>
                <div className="mt-5 -mx-5 px-5 py-4 border-y border-slate-100 bg-slate-50/60">
                  <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
                    {DOCUMENT_FOLDERS.map((folder, index) => {
                      const count = folderDocumentCount(folder.key);
                      const active = selectedFolderKey === folder.key;
                      const showArrow = index < DOCUMENT_FOLDERS.length - 1;

                      return (
                        <div key={folder.key} className="relative">
                          <button
                            type="button"
                            onClick={() => setSelectedFolderKey(folder.key)}
                            className={`min-h-20 w-full rounded-lg border px-3 py-3 text-left transition-all ${
                              active
                                ? "bg-white border-blue-500 shadow-sm"
                                : "bg-slate-50 border-slate-200 hover:bg-blue-50/60 hover:border-blue-200"
                            }`}
                          >
                            <div className="flex items-start justify-between gap-3">
                              <div className="flex items-start gap-2 min-w-0">
                                <FolderOpen
                                  size={18}
                                  className={`mt-0.5 shrink-0 ${
                                    active ? "text-blue-600" : "text-slate-500"
                                  }`}
                                />
                                <span className="font-semibold text-sm text-slate-800 leading-snug whitespace-normal break-words">
                                  {folder.name}
                                </span>
                              </div>
                              <span
                                className={`text-xs rounded-md px-2 py-0.5 shrink-0 ${
                                  active
                                    ? "bg-blue-100 text-blue-700"
                                    : "bg-white text-slate-500 border border-slate-200"
                                }`}
                              >
                                {count}
                              </span>
                            </div>
                          </button>
                          {showArrow && (
                            <div
                              className="hidden xl:flex absolute -right-3 top-1/2 z-10 -translate-y-1/2 items-center justify-center text-slate-300 pointer-events-none"
                              aria-hidden="true"
                            >
                              <ChevronRight size={18} strokeWidth={2.25} />
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>

                {visibleDocuments.length === 0 && !selectedRepo.is_shared && (
                  <div className="pt-5">
                    <label
                      onDragEnter={handleDragOver}
                      onDragOver={handleDragOver}
                      onDragLeave={handleDragLeave}
                      onDrop={handleDrop}
                      className={`min-h-32 rounded-xl border border-dashed px-4 py-6 flex flex-col items-center justify-center gap-2 cursor-pointer transition-all ${
                        isUploading
                          ? "border-blue-300 bg-blue-50"
                          : isDragging
                          ? "border-blue-500 bg-blue-50 ring-4 ring-blue-100"
                          : "border-slate-300 bg-slate-50 hover:border-blue-300 hover:bg-blue-50/40"
                      }`}
                    >
                      {isUploading ? (
                        <Loader2
                          size={22}
                          className="animate-spin text-blue-600"
                        />
                      ) : (
                        <UploadCloud size={22} className="text-blue-600" />
                      )}
                      <span className="text-sm font-semibold text-slate-700 text-center">
                        Kéo thả file vào {selectedFolder.name}
                      </span>
                      <span className="text-xs text-slate-500 text-center">
                        {isUploading && uploadProgress
                          ? `Đang upload ${uploadProgress.completed}/${uploadProgress.total} file...`
                          : "hoặc bấm để chọn nhiều file"}
                      </span>
                      <input
                        type="file"
                        multiple
                        className="hidden"
                        onChange={handleUpload}
                        disabled={isUploading}
                      />
                    </label>
                  </div>
                )}

                {!selectedRepo.is_shared && visibleDocuments.length > 0 && (
                  <label
                    onDragEnter={handleDragOver}
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                    onDrop={handleDrop}
                    className={`mt-5 min-h-16 rounded-lg border border-dashed px-4 py-4 flex items-center justify-center gap-3 cursor-pointer transition-all ${
                      isUploading
                        ? "border-blue-300 bg-blue-50"
                        : isDragging
                        ? "border-blue-500 bg-blue-50 ring-4 ring-blue-100"
                        : "border-slate-300 bg-slate-50 hover:border-blue-300 hover:bg-blue-50/40"
                    }`}
                  >
                    {isUploading ? (
                      <Loader2
                        size={18}
                        className="animate-spin text-blue-600"
                      />
                    ) : (
                      <UploadCloud size={18} className="text-blue-600" />
                    )}
                    <span className="text-sm font-medium text-slate-700">
                      {isUploading && uploadProgress
                        ? `Đang upload ${uploadProgress.completed}/${uploadProgress.total} file...`
                        : `Kéo thả nhiều file vào ${selectedFolder.name}`}
                    </span>
                    <input
                      type="file"
                      multiple
                      className="hidden"
                      onChange={handleUpload}
                      disabled={isUploading}
                    />
                  </label>
                )}

                {visibleDocuments.length === 0 ? (
                  <div className="p-8 text-center text-slate-400 text-sm">
                    Thư mục này chưa có file nào.
                  </div>
                ) : (
                  <div className="divide-y divide-slate-100 mt-5">
                    {visibleDocuments.map((doc) => (
                      <div
                        key={doc.id}
                        className="py-3 flex items-center justify-between hover:bg-slate-50 transition-colors group gap-4"
                      >
                        <div className="flex items-center gap-3 min-w-0">
                          <FileIcon size={16} className="text-blue-500 shrink-0" />
                          <div className="min-w-0">
                            <p className="font-medium text-slate-800 text-sm truncate">
                              {doc.filename}
                            </p>
                            <p className="text-xs text-slate-400 truncate">
                              {formatSize(doc.file_size)} ·{" "}
                              {new Date(doc.uploaded_at).toLocaleDateString(
                                "vi-VN"
                              )}
                              {doc.processing_status === "processing" &&
                                " · Đang xử lý"}
                              {doc.processing_status === "queued" &&
                                " · Đang chờ"}
                              {doc.processing_status === "failed" &&
                                " · Lỗi xử lý"}
                            </p>
                          </div>
                        </div>
                        <div className="flex items-center gap-1 shrink-0">
                          <button
                            type="button"
                            onClick={() => handleViewDoc(doc)}
                            disabled={viewingDocId === doc.id}
                            className="p-2 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors opacity-100 md:opacity-0 md:group-hover:opacity-100 disabled:opacity-60 disabled:cursor-wait"
                            title="Xem file"
                            aria-label={`Xem file ${doc.filename}`}
                          >
                            {viewingDocId === doc.id ? (
                              <Loader2 size={14} className="animate-spin" />
                            ) : (
                              <Eye size={14} />
                            )}
                          </button>
                          <button
                            type="button"
                            onClick={() => handleDownloadDoc(doc)}
                            disabled={downloadingDocId === doc.id}
                            className="p-2 text-slate-400 hover:text-emerald-600 hover:bg-emerald-50 rounded-lg transition-colors opacity-100 md:opacity-0 md:group-hover:opacity-100 disabled:opacity-60 disabled:cursor-wait"
                            title="Tải xuống"
                            aria-label={`Tải xuống ${doc.filename}`}
                          >
                            {downloadingDocId === doc.id ? (
                              <Loader2 size={14} className="animate-spin" />
                            ) : (
                              <Download size={14} />
                            )}
                          </button>
                          {!selectedRepo.is_shared && isDocxDocument(doc.filename) && (
                            <button
                              type="button"
                              onClick={() => openDocxEditor(doc)}
                              disabled={loadingDocxEditorId === doc.id}
                              className="p-2 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors opacity-100 md:opacity-0 md:group-hover:opacity-100 disabled:opacity-60 disabled:cursor-wait"
                              title="Soạn thảo DOCX"
                              aria-label={`Soạn thảo DOCX ${doc.filename}`}
                            >
                              {loadingDocxEditorId === doc.id ? (
                                <Loader2 size={14} className="animate-spin" />
                              ) : (
                                <Pencil size={14} />
                              )}
                            </button>
                          )}
                          {!selectedRepo.is_shared && isWordDocument(doc.filename) && (
                            <button
                              type="button"
                              onClick={() => openReplaceDocPicker(doc)}
                              disabled={updatingDocId === doc.id}
                              className="p-2 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors opacity-100 md:opacity-0 md:group-hover:opacity-100 disabled:opacity-60 disabled:cursor-wait"
                              title="Thay thế file Word"
                              aria-label={`Thay thế file Word ${doc.filename}`}
                            >
                              {updatingDocId === doc.id ? (
                                <Loader2 size={14} className="animate-spin" />
                              ) : (
                                <UploadCloud size={14} />
                              )}
                            </button>
                          )}
                          {!selectedRepo.is_shared && (
                            <button
                              type="button"
                              onClick={() => handleDeleteDoc(doc.id)}
                              className="p-2 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors opacity-100 md:opacity-0 md:group-hover:opacity-100"
                              title="Xóa tài liệu"
                              aria-label={`Xóa tài liệu ${doc.filename}`}
                            >
                              <Trash2 size={14} />
                            </button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="h-full flex flex-col items-center justify-center text-slate-400 bg-slate-50/50 rounded-2xl border border-dashed border-slate-300 min-h-[400px]">
              <Database size={48} className="text-slate-300 mb-4" />
              <p className="font-medium">
                Chọn một kho dữ liệu từ danh sách bên trái
              </p>
              <p className="text-sm mt-1">hoặc tạo kho mới để bắt đầu</p>
            </div>
          )}
        </section>
      </div>

      {/* DOCX Editor Modal */}
      <AnimatePresence>
        {docxEditorDoc && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[60] bg-slate-950/70 backdrop-blur-sm p-2 sm:p-4"
          >
            <motion.div
              initial={{ scale: 0.98, opacity: 0, y: 10 }}
              animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={{ scale: 0.98, opacity: 0, y: 10 }}
              className="h-full min-h-0 bg-white rounded-2xl shadow-2xl border border-slate-200 overflow-hidden flex flex-col"
            >
              <div className="h-16 px-4 sm:px-5 border-b border-slate-200 flex items-center justify-between gap-3 bg-white shrink-0">
                <div className="min-w-0">
                  <h2 className="font-bold text-slate-900 truncate">
                    {docxEditorDoc.filename}
                  </h2>
                  <p className="text-xs text-slate-500 truncate">
                    {docxEditorDirty
                      ? "Có thay đổi chưa lưu"
                      : "Đang soạn thảo DOCX"}
                  </p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <button
                    type="button"
                    onClick={saveDocxEditor}
                    disabled={
                      isDocxEditorSaving ||
                      !docxEditorBuffer ||
                      Boolean(docxEditorError)
                    }
                    className="px-3 sm:px-4 py-2 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 transition-colors flex items-center gap-2 disabled:opacity-60 disabled:cursor-not-allowed"
                    title="Lưu DOCX"
                  >
                    {isDocxEditorSaving ? (
                      <Loader2 size={16} className="animate-spin" />
                    ) : (
                      <Save size={16} />
                    )}
                    <span className="hidden sm:inline">
                      {isDocxEditorSaving ? "Đang lưu" : "Lưu"}
                    </span>
                  </button>
                  <button
                    type="button"
                    onClick={closeDocxEditor}
                    disabled={isDocxEditorSaving}
                    className="p-2 rounded-lg text-slate-500 hover:text-slate-800 hover:bg-slate-100 transition-colors disabled:opacity-50"
                    title="Đóng"
                  >
                    <X size={20} />
                  </button>
                </div>
              </div>

              {docxEditorError ? (
                <div className="flex-1 min-h-0 flex items-center justify-center p-6 bg-slate-50">
                  <div className="max-w-md rounded-xl border border-rose-200 bg-white p-5 text-center shadow-sm">
                    <p className="font-semibold text-rose-700">
                      Không thể mở trình soạn thảo
                    </p>
                    <p className="text-sm text-slate-500 mt-2">
                      {docxEditorError}
                    </p>
                  </div>
                </div>
              ) : !docxEditorBuffer ? (
                <div className="flex-1 min-h-0 flex flex-col items-center justify-center gap-3 bg-slate-50 text-slate-500">
                  <Loader2 size={26} className="animate-spin text-blue-600" />
                  <p className="text-sm font-medium">Đang tải file DOCX...</p>
                </div>
              ) : (
                <div className="flex-1 min-h-0 overflow-hidden bg-slate-100">
                  <DocxEditor
                    ref={docxEditorRef}
                    documentBuffer={docxEditorBuffer}
                    documentName={docxEditorDoc.filename}
                    documentNameEditable={false}
                    author={getStoredUser()?.full_name || "User"}
                    mode="editing"
                    showFileOpen={false}
                    showRuler
                    rulerUnit="cm"
                    initialZoom={0.9}
                    className="h-full"
                    onChange={() => setDocxEditorDirty(true)}
                    onSave={(buffer) => void saveDocxEditorBuffer(buffer)}
                    onError={(err) =>
                      setDocxEditorError(
                        err.message || "Trình soạn thảo DOCX gặp lỗi"
                      )
                    }
                  />
                </div>
              )}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Rename Modal */}
      <AnimatePresence>
        {renameTarget && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4"
            onClick={closeRenameModal}
          >
            <motion.div
              initial={{ scale: 0.94, opacity: 0, y: 12 }}
              animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={{ scale: 0.94, opacity: 0, y: 12 }}
              onClick={(e) => e.stopPropagation()}
              className="bg-white rounded-3xl p-7 w-full max-w-md shadow-2xl border border-slate-200"
            >
              <div className="flex items-start justify-between gap-4 mb-6">
                <div>
                  <h2 className="text-xl font-bold text-slate-900">
                    {renameTarget.type === "repo"
                      ? "Đổi tên kho"
                      : "Đổi tên danh mục"}
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
                  <label className="block text-sm font-semibold text-slate-700 mb-2">
                    Tên mới
                  </label>
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

                {renameTarget.type === "repo" && (
                  <div>
                    <label className="block text-sm font-semibold text-slate-700 mb-2">
                      Chuyển danh mục
                    </label>
                    <select
                      value={renameCategoryId}
                      onChange={(e) => setRenameCategoryId(e.target.value)}
                      disabled={isRenaming}
                      className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all disabled:opacity-60"
                    >
                      <option value="">Chưa phân loại</option>
                      {ownCategories.map((category) => (
                        <option key={category.id} value={category.id}>
                          {category.name}
                        </option>
                      ))}
                    </select>
                  </div>
                )}

                {renameError && (
                  <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-rose-600 text-sm">
                    {renameError}
                  </div>
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
                    {isRenaming ? (
                      <>
                        <Loader2 size={18} className="animate-spin" /> Đang
                        lưu...
                      </>
                    ) : (
                      <>
                        <Pencil size={18} /> Lưu
                      </>
                    )}
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
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4"
            onClick={() =>
              !isCreating && !isCreatingCategory && setShowCreateForm(false)
            }
          >
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              onClick={(e) => e.stopPropagation()}
              className="bg-white rounded-3xl p-8 w-full max-w-md shadow-2xl"
            >
              <div className="flex justify-between items-center mb-6">
                <h2 className="text-xl font-bold text-slate-900">
                  Tạo kho dữ liệu mới
                </h2>
                <button
                  onClick={() =>
                    !isCreating &&
                    !isCreatingCategory &&
                    setShowCreateForm(false)
                  }
                  disabled={isCreating || isCreatingCategory}
                  className={`p-2 hover:bg-slate-100 rounded-lg transition-colors ${
                    isCreating || isCreatingCategory
                      ? "opacity-50 cursor-not-allowed"
                      : ""
                  }`}
                >
                  <X size={20} className="text-slate-400" />
                </button>
              </div>

              {createSuccess ? (
                <motion.div
                  initial={{ scale: 0.8, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  className="py-8 flex flex-col items-center gap-3"
                >
                  <div className="w-16 h-16 rounded-full bg-emerald-100 flex items-center justify-center">
                    <CheckCircle2 size={32} className="text-emerald-600" />
                  </div>
                  <p className="text-lg font-bold text-slate-900">
                    Tạo kho thành công!
                  </p>
                  <p className="text-sm text-slate-500">Đang chuyển hướng...</p>
                </motion.div>
              ) : (
                <form onSubmit={handleCreateRepo} className="space-y-4">
                  <div>
                    <label className="block text-sm font-semibold text-slate-700 mb-2">
                      Tên kho *
                    </label>
                    <input
                      type="text"
                      required
                      value={newRepoName}
                      onChange={(e) => setNewRepoName(e.target.value)}
                      placeholder="VD: Kho Khoa học Công nghệ"
                      disabled={isCreating}
                      className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all disabled:opacity-60"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-semibold text-slate-700 mb-2">
                      Mô tả
                    </label>
                    <textarea
                      value={newRepoDesc}
                      onChange={(e) => setNewRepoDesc(e.target.value)}
                      placeholder="Mô tả ngắn về nội dung kho..."
                      rows={3}
                      disabled={isCreating}
                      className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all disabled:opacity-60"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-semibold text-slate-700 mb-2">
                      Danh mục
                    </label>
                    <select
                      value={newRepoCategoryId}
                      onChange={(e) => {
                        setNewRepoCategoryId(e.target.value);
                        setCategoryError("");
                      }}
                      disabled={isCreating || isCreatingCategory}
                      className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all disabled:opacity-60"
                    >
                      <option value="">Chưa phân loại</option>
                      {ownCategories.map((category) => (
                        <option key={category.id} value={category.id}>
                          {category.name}
                        </option>
                      ))}
                      <option value="__new__">+ Thêm danh mục mới</option>
                    </select>
                    {newRepoCategoryId === "__new__" && (
                      <div className="mt-2 flex gap-2">
                        <input
                          type="text"
                          autoFocus
                          value={newCategoryName}
                          onChange={(e) => {
                            setNewCategoryName(e.target.value);
                            setCategoryError("");
                          }}
                          onKeyDown={(e) => {
                            if (e.key !== "Enter") return;
                            e.preventDefault();
                            handleCreateCategory();
                          }}
                          placeholder="Tên danh mục mới"
                          disabled={isCreating || isCreatingCategory}
                          className="min-w-0 flex-1 bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all disabled:opacity-60"
                        />
                        <button
                          type="button"
                          onClick={handleCreateCategory}
                          disabled={
                            isCreating ||
                            isCreatingCategory ||
                            !newCategoryName.trim()
                          }
                          className="px-4 py-3 bg-blue-600 text-white rounded-xl hover:bg-blue-700 transition-colors flex items-center justify-center gap-2 disabled:opacity-60 disabled:cursor-not-allowed"
                        >
                          {isCreatingCategory ? (
                            <Loader2 size={18} className="animate-spin" />
                          ) : (
                            <Plus size={18} />
                          )}
                          <span className="sr-only">Tạo danh mục</span>
                        </button>
                      </div>
                    )}
                    {categoryError && (
                      <div className="mt-2 p-3 bg-rose-50 border border-rose-200 rounded-xl text-rose-600 text-sm">
                        {categoryError}
                      </div>
                    )}
                  </div>
                  {error && (
                    <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-rose-600 text-sm">
                      {error}
                    </div>
                  )}
                  <div className="flex gap-3 pt-2">
                    <button
                      type="button"
                      onClick={() =>
                        !isCreating &&
                        !isCreatingCategory &&
                        setShowCreateForm(false)
                      }
                      disabled={isCreating || isCreatingCategory}
                      className="flex-1 py-3 bg-slate-100 text-slate-700 rounded-xl font-medium hover:bg-slate-200 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      Hủy
                    </button>
                    <button
                      type="submit"
                      disabled={
                        isCreating ||
                        isCreatingCategory ||
                        newRepoCategoryId === "__new__"
                      }
                      className="flex-1 py-3 bg-blue-600 text-white rounded-xl font-medium hover:bg-blue-700 transition-colors flex items-center justify-center gap-2 shadow-lg shadow-blue-600/20 disabled:opacity-70 disabled:cursor-not-allowed"
                    >
                      {isCreating ? (
                        <>
                          <Loader2 size={18} className="animate-spin" /> Đang
                          tạo...
                        </>
                      ) : (
                        <>
                          <Plus size={18} /> Tạo kho
                        </>
                      )}
                    </button>
                  </div>
                </form>
              )}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
