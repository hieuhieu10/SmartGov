import { useEffect, useState } from 'react';
import { CheckCircle2, Download, Eye, FileText, Loader2, Sparkles, Trash2, X } from 'lucide-react';
import { ApiClient } from '../api/client';
import type { Document, Repository } from '../api/client';

export function DraftingPage() {
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [draftRepoId, setDraftRepoId] = useState('');
  const [draftDocuments, setDraftDocuments] = useState<Document[]>([]);
  const [summaryDocuments, setSummaryDocuments] = useState<Document[]>([]);
  const [draftDocumentId, setDraftDocumentId] = useState('');
  const [feedbackRepoId, setFeedbackRepoId] = useState('');
  const [loadingDocuments, setLoadingDocuments] = useState(false);
  const [isDrafting, setIsDrafting] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [summaryDocument, setSummaryDocument] = useState<Document | null>(null);
  const [previewHtml, setPreviewHtml] = useState('');
  const [previewingId, setPreviewingId] = useState<string | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  useEffect(() => {
    ApiClient.getRepositories()
      .then(setRepositories)
      .catch(() => setError('Không tải được danh sách kho dữ liệu.'));
  }, []);

  useEffect(() => {
    if (!draftRepoId) {
      setDraftDocuments([]);
      setSummaryDocuments([]);
      setDraftDocumentId('');
      return;
    }
    setLoadingDocuments(true);
    setDraftDocumentId('');
    ApiClient.getDocuments(draftRepoId)
      .then((items) => {
        setDraftDocuments(items.filter((doc) => doc.processing_status === 'completed'));
        setSummaryDocuments(items.filter((doc) => doc.folder_key === 'summary'));
      })
      .catch(() => setError('Không tải được tài liệu trong kho đã chọn.'))
      .finally(() => setLoadingDocuments(false));
  }, [draftRepoId]);

  const canSubmit = Boolean(draftRepoId && draftDocumentId && feedbackRepoId && !isDrafting);
  const draftRepositories = repositories.filter((repo) => !repo.is_shared);

  const handleDraft = async () => {
    if (!canSubmit) return;
    setError('');
    setSuccess('');
    setSummaryDocument(null);
    setIsDrafting(true);
    try {
      const document = await ApiClient.consolidateDrafting(draftRepoId, draftDocumentId, feedbackRepoId);
      setSummaryDocument(document);
      setSummaryDocuments((items) => [document, ...items.filter((item) => item.id !== document.id)]);
      setSuccess(`Đã tạo ${document.filename} trong kho dự thảo.`);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Không thể soạn tài liệu. Vui lòng thử lại.');
    } finally {
      setIsDrafting(false);
    }
  };

  const handlePreview = async (document: Document) => {
    if (!draftRepoId) return;
    setPreviewingId(document.id);
    try {
      setPreviewHtml(await ApiClient.getDocumentPreview(draftRepoId, document.id));
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Không thể xem trước tài liệu.');
    } finally {
      setPreviewingId(null);
    }
  };

  const handleDownload = async (summaryDoc: Document) => {
    if (!draftRepoId) return;
    setDownloadingId(summaryDoc.id);
    try {
      const blob = await ApiClient.getDocumentFile(draftRepoId, summaryDoc.id);
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = summaryDoc.filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Không thể tải xuống tài liệu.');
    } finally {
      setDownloadingId(null);
    }
  };

  const handleDelete = async (document: Document) => {
    if (!draftRepoId || !window.confirm(`Xóa “${document.filename}”?`)) return;
    setDeletingId(document.id);
    try {
      await ApiClient.deleteDocument(draftRepoId, document.id);
      setSummaryDocuments((items) => items.filter((item) => item.id !== document.id));
      if (summaryDocument?.id === document.id) setSummaryDocument(null);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Không thể xóa tài liệu.');
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <header>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">Xây dựng dự thảo</h1>
        <p className="mt-1 text-sm text-slate-500">Chọn tài liệu dự thảo và kho chứa các văn bản góp ý để AI lập bảng tổng hợp.</p>
      </header>

      {error && <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div>}
      {success && <div className="flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700"><CheckCircle2 size={18}/>{success}</div>}

      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex items-start gap-3">
          <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-blue-600 text-sm font-bold text-white">1</span>
          <div className="min-w-0 flex-1">
            <h2 className="font-semibold text-slate-900">Chọn dự thảo</h2>
            <p className="mt-1 text-sm text-slate-500">Chọn một kho dữ liệu, sau đó chọn một tài liệu làm dự thảo.</p>
            <div className="mt-4 grid gap-4 md:grid-cols-2">
              <label className="block text-sm font-medium text-slate-700">Kho dữ liệu
                <select value={draftRepoId} onChange={(event) => setDraftRepoId(event.target.value)} className="mt-2 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-800">
                  <option value="">-- Chọn kho dữ liệu --</option>
                  {draftRepositories.map((repo) => <option key={repo.id} value={repo.id}>{repo.name}</option>)}
                </select>
              </label>
              <label className="block text-sm font-medium text-slate-700">Tài liệu dự thảo
                <select value={draftDocumentId} onChange={(event) => setDraftDocumentId(event.target.value)} disabled={!draftRepoId || loadingDocuments} className="mt-2 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-800 disabled:cursor-not-allowed disabled:bg-slate-100">
                  <option value="">{loadingDocuments ? 'Đang tải tài liệu...' : '-- Chọn một tài liệu --'}</option>
                  {draftDocuments.map((doc) => <option key={doc.id} value={doc.id}>{doc.filename}</option>)}
                </select>
              </label>
            </div>
          </div>
        </div>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex items-start gap-3">
          <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-violet-600 text-sm font-bold text-white">2</span>
          <div className="min-w-0 flex-1">
            <h2 className="font-semibold text-slate-900">Chọn kho văn bản góp ý</h2>
            <p className="mt-1 text-sm text-slate-500">Chọn một kho dữ liệu chứa các văn bản góp ý cần tổng hợp.</p>
            <label className="mt-4 block max-w-xl text-sm font-medium text-slate-700">Kho dữ liệu góp ý
              <select value={feedbackRepoId} onChange={(event) => setFeedbackRepoId(event.target.value)} className="mt-2 w-full rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-800">
                <option value="">-- Chọn kho văn bản góp ý --</option>
                {repositories.map((repo) => <option key={repo.id} value={repo.id}>{repo.name}</option>)}
              </select>
            </label>
          </div>
        </div>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex items-start gap-3">
          <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-emerald-600 text-sm font-bold text-white">3</span>
          <div className="min-w-0 flex-1">
            <h2 className="font-semibold text-slate-900">Tạo bảng tổng hợp</h2>
            <p className="mt-1 text-sm text-slate-500">AI đối chiếu dự thảo với các văn bản trong kho góp ý để tạo Bảng tổng hợp ý kiến.</p>
            <div className="mt-4 flex justify-end">
              <button type="button" onClick={handleDraft} disabled={!canSubmit} className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-5 py-3 text-sm font-semibold text-white shadow-lg shadow-blue-600/25 transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50">
                {isDrafting ? <Loader2 size={18} className="animate-spin"/> : <Sparkles size={18}/>} {isDrafting ? 'Đang tạo...' : 'Tạo bảng tổng hợp'}
              </button>
            </div>
            <div className="mt-5 border-t border-slate-100 pt-4">
              <h3 className="text-sm font-semibold text-slate-800">Bảng tổng hợp đã tạo</h3>
              {summaryDocuments.length ? (
                <div className="mt-3 space-y-2">
                  {summaryDocuments.map((document) => (
                    <div key={document.id} className="flex flex-wrap items-center gap-3 rounded-xl border border-slate-200 px-3 py-2.5">
                      <FileText size={18} className="shrink-0 text-emerald-600"/>
                      <p className="min-w-0 flex-1 truncate text-sm font-medium text-slate-700">{document.filename}</p>
                      <div className="flex items-center gap-1">
                        <button type="button" onClick={() => handlePreview(document)} disabled={previewingId === document.id} className="rounded-lg p-2 text-slate-500 hover:bg-blue-50 hover:text-blue-600 disabled:opacity-50" title="Xem trước" aria-label={`Xem trước ${document.filename}`}>
                          {previewingId === document.id ? <Loader2 size={17} className="animate-spin"/> : <Eye size={17}/>} 
                        </button>
                        <button type="button" onClick={() => handleDownload(document)} disabled={downloadingId === document.id} className="rounded-lg p-2 text-slate-500 hover:bg-emerald-50 hover:text-emerald-600 disabled:opacity-50" title="Tải xuống" aria-label={`Tải xuống ${document.filename}`}>
                          {downloadingId === document.id ? <Loader2 size={17} className="animate-spin"/> : <Download size={17}/>} 
                        </button>
                        <button type="button" onClick={() => handleDelete(document)} disabled={deletingId === document.id} className="rounded-lg p-2 text-slate-500 hover:bg-rose-50 hover:text-rose-600 disabled:opacity-50" title="Xóa" aria-label={`Xóa ${document.filename}`}>
                          {deletingId === document.id ? <Loader2 size={17} className="animate-spin"/> : <Trash2 size={17}/>} 
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : <p className="mt-2 text-sm text-slate-500">Chưa có bảng tổng hợp nào trong kho dự thảo đã chọn.</p>}
            </div>
          </div>
        </div>
      </section>

      <section className={`rounded-2xl border p-6 shadow-sm ${summaryDocument ? 'border-emerald-200 bg-emerald-50/40' : 'border-slate-200 bg-slate-50'}`}>
        <div className="flex items-start gap-3">
          <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-amber-500 text-sm font-bold text-white">4</span>
          <div className="min-w-0 flex-1">
            <h2 className="font-semibold text-slate-900">Hoàn thiện dự thảo từ các góp ý</h2>
            <p className="mt-1 text-sm text-slate-500">Dùng Bảng tổng hợp ý kiến ở bước 3 để rà soát, tiếp thu và hoàn thiện dự thảo.</p>
            {summaryDocument ? (
              <div className="mt-3 flex items-center gap-2 text-sm font-medium text-emerald-700"><CheckCircle2 size={18}/>Bảng tổng hợp đã sẵn sàng: {summaryDocument.filename}</div>
            ) : (
              <div className="mt-3 flex items-center gap-2 text-sm text-slate-500"><FileText size={18}/>Hoàn thành bước 3 trước khi thực hiện bước này.</div>
            )}
          </div>
        </div>
      </section>

      {previewHtml && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 p-4">
          <div className="flex h-[90vh] w-full max-w-6xl flex-col overflow-hidden rounded-2xl bg-white shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-200 px-5 py-3">
              <h2 className="text-sm font-semibold text-slate-800">Xem trước bảng tổng hợp</h2>
              <button type="button" onClick={() => setPreviewHtml('')} className="rounded-lg p-2 text-slate-500 hover:bg-slate-100" aria-label="Đóng xem trước"><X size={18}/></button>
            </div>
            <iframe title="Xem trước bảng tổng hợp" sandbox="allow-same-origin" srcDoc={previewHtml} className="min-h-0 flex-1 bg-white"/>
          </div>
        </div>
      )}
    </div>
  );
}
