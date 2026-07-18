import { useCallback, useEffect, useState } from 'react';
import type { ChangeEvent, DragEvent } from 'react';
import { ApiClient } from '../api/client';
import type { Document, Repository, RepositoryCategory } from '../api/client';
import { CheckCircle2, Database, FileText, Folder, FolderPlus, Globe2, Lock, Pencil, Plus, Share2, Trash2, UploadCloud } from 'lucide-react';

export function DataLibrary() {
  const [repos, setRepos] = useState<Repository[]>([]);
  const [categories, setCategories] = useState<RepositoryCategory[]>([]);
  const [selected, setSelected] = useState<Repository | null>(null);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [creating, setCreating] = useState(false);
  const [creatingCategory, setCreatingCategory] = useState(false);
  const [categoryName, setCategoryName] = useState('');
  const [editingRepo, setEditingRepo] = useState(false);
  const [editRepoName, setEditRepoName] = useState('');
  const [editRepoDescription, setEditRepoDescription] = useState('');
  const [editRepoCategoryId, setEditRepoCategoryId] = useState('');
  const [repoName, setRepoName] = useState('');
  const [repoDescription, setRepoDescription] = useState('');
  const [categoryId, setCategoryId] = useState('');
  const [newCategory, setNewCategory] = useState('');
  const [busy, setBusy] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState('');

  const loadRepos = useCallback(async () => setRepos(await ApiClient.getRepositories()), []);
  const loadCategories = useCallback(async () => setCategories(await ApiClient.getRepositoryCategories()), []);
  const loadDocs = useCallback(async (id: string) => setDocuments(await ApiClient.getDocuments(id)), []);
  useEffect(() => { Promise.all([loadRepos(), loadCategories()]).catch(() => setError('Không tải được dữ liệu.')); }, [loadRepos, loadCategories]);
  useEffect(() => { if (selected) loadDocs(selected.id).catch(() => setError('Không tải được tài liệu.')); else setDocuments([]); }, [selected, loadDocs]);

  const refresh = async () => { await Promise.all([loadRepos(), loadCategories()]); };
  const createRepo = async (event: React.FormEvent) => {
    event.preventDefault(); if (!repoName.trim()) return;
    setBusy(true); setError('');
    try {
      let nextCategory = categoryId;
      if (newCategory.trim()) { const category = await ApiClient.createRepositoryCategory(newCategory.trim()); nextCategory = category.id; }
      const repo = await ApiClient.createRepository(repoName.trim(), repoDescription.trim(), nextCategory || undefined);
      await refresh(); setSelected(repo); setCreating(false); setRepoName(''); setRepoDescription(''); setCategoryId(''); setNewCategory('');
    } catch (e: any) { setError(e.response?.data?.detail || 'Không thể tạo kho.'); } finally { setBusy(false); }
  };
  const createCategory = async (event: React.FormEvent) => {
    event.preventDefault(); if (!categoryName.trim()) return;
    setBusy(true); setError('');
    try { await ApiClient.createRepositoryCategory(categoryName.trim()); await refresh(); setCreatingCategory(false); setCategoryName(''); }
    catch (e: any) { setError(e.response?.data?.detail || 'Không thể tạo danh mục.'); } finally { setBusy(false); }
  };
  const openEditRepo = () => {
    if (!selected || selected.is_shared) return;
    setEditRepoName(selected.name); setEditRepoDescription(selected.description || ''); setEditRepoCategoryId(selected.category_id || ''); setEditingRepo(true);
  };
  const updateRepo = async (event: React.FormEvent) => {
    event.preventDefault(); if (!selected || !editRepoName.trim()) return;
    setBusy(true); setError('');
    try {
      const updated = await ApiClient.updateRepository(selected.id, { name: editRepoName.trim(), description: editRepoDescription.trim(), category_id: editRepoCategoryId || null });
      setSelected(updated); await refresh(); setEditingRepo(false);
    } catch (e: any) { setError(e.response?.data?.detail || 'Không thể cập nhật kho.'); } finally { setBusy(false); }
  };
  const uploadFiles = async (files: FileList | File[]) => {
    if (!selected || !files.length) return;
    setBusy(true); setError('');
    try { for (const file of Array.from(files)) await ApiClient.uploadDocument(selected.id, file); await loadDocs(selected.id); await loadRepos(); }
    catch (e: any) { setError(e.response?.data?.detail || 'Không thể tải tài liệu lên.'); } finally { setBusy(false); }
  };
  const onUpload = (event: ChangeEvent<HTMLInputElement>) => { if (event.target.files) uploadFiles(event.target.files); event.target.value = ''; };
  const onDrop = (event: DragEvent<HTMLLabelElement>) => { event.preventDefault(); setDragging(false); uploadFiles(event.dataTransfer.files); };
  const toggleShare = async () => {
    if (!selected || selected.is_shared) return;
    setBusy(true); try { const updated = await ApiClient.updateRepository(selected.id, { is_public: !selected.is_public }); setSelected(updated); await loadRepos(); }
    catch (e: any) { setError(e.response?.data?.detail || 'Không thể cập nhật chia sẻ.'); } finally { setBusy(false); }
  };
  const remove = async (doc: Document) => { if (!selected || !confirm(`Xóa “${doc.filename}”?`)) return; await ApiClient.deleteDocument(selected.id, doc.id); await loadDocs(selected.id); await loadRepos(); };
  const deleteRepo = async () => { if (!selected || selected.is_shared || !confirm(`Xóa kho “${selected.name}” và tất cả tài liệu?`)) return; await ApiClient.deleteRepository(selected.id); setSelected(null); await refresh(); };
  const ownRepos = repos.filter(repo => !repo.is_shared); const sharedRepos = repos.filter(repo => repo.is_shared);
  const ownCategories = categories.filter(category => !category.is_shared);
  const fileStatus = (doc: Document) => doc.processing_status === 'completed' ? 'Sẵn sàng AI' : doc.progress_message || 'Đang xử lý';

  return <div className="data-library max-w-[1400px] mx-auto space-y-7">
    <style>{`
      .data-library { font-size: 14px; }
      .data-library .text-4xl, .data-library .text-3xl, .data-library .text-2xl { font-size: 16px !important; line-height: 1.4; }
      .data-library .text-xl, .data-library .text-lg { font-size: 16px !important; line-height: 1.4; }
      .data-library .text-base { font-size: 14px !important; }
      .data-library .text-sm { font-size: 13px !important; }
      .data-library .text-xs { font-size: 12px !important; }
    `}</style>
    <header className="flex flex-wrap justify-between gap-4"><div><h1 className="text-3xl font-bold tracking-tight text-slate-900">Kho Dữ liệu</h1><p className="mt-1 text-base text-slate-500">Quản lý kho dữ liệu và tài liệu.</p></div><div className="flex gap-2"><button onClick={() => setCreatingCategory(true)} className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-3 text-base font-semibold text-slate-700 hover:bg-slate-50"><FolderPlus size={20}/>Tạo danh mục</button><button onClick={() => setCreating(true)} className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-5 py-3 text-base font-semibold text-white shadow-lg shadow-blue-600/25 hover:bg-blue-700"><Plus size={20}/>Tạo kho mới</button></div></header>
    {error && <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-rose-700">{error}</div>}
    <div className="grid gap-7 lg:grid-cols-[400px_minmax(0,1fr)]">
      <aside className="space-y-5"><div className="flex items-center justify-between px-1 text-sm font-bold uppercase tracking-wide text-slate-500"><span>{ownRepos.length} kho cá nhân</span><button onClick={() => setCreating(true)} className="p-1 text-slate-500 hover:text-blue-600"><FolderPlus size={21}/></button></div>
        {ownCategories.map(category => <div key={category.id}><div className="mb-2 flex items-center gap-2 px-1 font-bold uppercase tracking-wide text-slate-600"><Folder size={18}/>{category.name}</div>{ownRepos.filter(repo => repo.category_id === category.id).map(repo => <RepoCard key={repo.id} repo={repo} selected={selected?.id===repo.id} onClick={()=>setSelected(repo)}/>)}</div>)}
        {ownRepos.some(repo => !repo.category_id) && <div><div className="mb-2 flex items-center gap-2 px-1 font-bold uppercase tracking-wide text-slate-500"><Folder size={18}/>Chưa phân loại</div>{ownRepos.filter(repo => !repo.category_id).map(repo => <RepoCard key={repo.id} repo={repo} selected={selected?.id===repo.id} onClick={()=>setSelected(repo)}/>)}</div>}
        {sharedRepos.length > 0 && <><div className="pt-5 px-1 flex items-center gap-2 text-sm font-bold uppercase tracking-wide text-amber-600"><Share2 size={18}/>Kho chia sẻ từ đơn vị</div>{sharedRepos.map(repo => <RepoCard key={repo.id} repo={repo} shared selected={selected?.id===repo.id} onClick={()=>setSelected(repo)}/>)}</>}
      </aside>
      <section>{selected ? <div className="space-y-6"><div className="rounded-3xl border border-slate-200 bg-white p-7 shadow-sm"><div className="flex gap-5"><div className="grid h-20 w-20 shrink-0 place-items-center rounded-2xl bg-blue-600 text-white shadow-lg shadow-blue-500/20"><Database size={35}/></div><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-3"><h2 className="text-3xl font-bold text-slate-900">{selected.name}</h2>{!selected.is_shared && <button onClick={openEditRepo} className="text-slate-400 hover:text-blue-600" title="Sửa kho"><Pencil size={20}/></button>}</div><p className="mt-1 text-lg text-slate-500">{selected.description || 'Không có mô tả'}</p><div className="mt-5 flex flex-wrap items-center gap-x-5 gap-y-2 text-sm text-slate-500"><span>{documents.length} tài liệu</span><span className="text-emerald-600 font-medium">✓ Sẵn sàng AI</span>{selected.is_public ? <span className="inline-flex items-center gap-1 rounded-lg bg-emerald-50 px-3 py-1 font-medium text-emerald-700"><Globe2 size={15}/>Đang chia sẻ</span> : <span className="inline-flex items-center gap-1 rounded-lg bg-slate-100 px-3 py-1 font-medium"><Lock size={15}/>Riêng tư</span>}</div></div></div><div className="mt-6 flex justify-end gap-2">{!selected.is_shared && <><button onClick={openEditRepo} className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-4 py-2 font-medium text-slate-700 hover:bg-slate-50"><Pencil size={16}/>Sửa kho</button><button onClick={toggleShare} disabled={busy} className="rounded-xl border border-slate-200 px-4 py-2 font-medium text-slate-700 hover:bg-slate-50">{selected.is_public ? 'Dừng chia sẻ' : 'Chia sẻ cùng cơ quan'}</button><button onClick={deleteRepo} className="rounded-xl p-2 text-rose-500 hover:bg-rose-50"><Trash2 size={19}/></button></>}</div></div>
        {!selected.is_shared && <label onDragOver={e=>{e.preventDefault();setDragging(true)}} onDragLeave={()=>setDragging(false)} onDrop={onDrop} className={`flex cursor-pointer flex-col items-center justify-center rounded-3xl border-2 border-dashed px-8 py-16 transition-colors ${dragging?'border-blue-500 bg-blue-50':'border-slate-200 bg-white hover:border-blue-300'}`}><UploadCloud className="mb-5 text-blue-500" size={42}/><p className="text-xl font-semibold text-slate-700">Nhấn để chọn file hoặc kéo thả</p><p className="mt-2 text-slate-500">PDF, Word, Excel, ảnh, audio, video — tối đa 50MB</p><input type="file" multiple className="hidden" onChange={onUpload}/></label>}
        <div className="overflow-hidden rounded-3xl border border-slate-200 bg-white"><h3 className="flex items-center gap-3 border-b border-slate-200 px-7 py-5 text-2xl font-bold text-slate-800"><FileText className="text-blue-500"/>Tài liệu ({documents.length})</h3>{documents.map(doc=><div key={doc.id} className="flex items-center gap-4 border-b border-slate-100 px-7 py-4 last:border-0"><FileText className="text-blue-500" size={25}/><div className="min-w-0 flex-1"><p className="truncate text-lg font-medium text-slate-800">{doc.filename}</p><p className="mt-1 text-sm text-slate-400">{doc.file_size ? `${(doc.file_size/1024).toFixed(1)} KB · `:''}{fileStatus(doc)}</p></div><span className={`inline-flex items-center gap-1 rounded-lg px-3 py-2 text-sm font-medium ${doc.processing_status==='completed'?'bg-emerald-50 text-emerald-700':'bg-amber-50 text-amber-700'}`}><CheckCircle2 size={16}/>{fileStatus(doc)}</span>{!selected.is_shared&&<button onClick={()=>remove(doc)} className="rounded-lg p-2 text-slate-400 hover:bg-rose-50 hover:text-rose-500"><Trash2 size={18}/></button>}</div>)}{!documents.length&&<p className="p-10 text-center text-slate-400">Chưa có tài liệu trong kho.</p>}</div>
      </div> : <div className="grid min-h-96 place-items-center rounded-3xl border border-dashed border-slate-300 bg-white text-center text-slate-400"><div><Database className="mx-auto mb-4" size={46}/><p className="text-lg">Chọn hoặc tạo kho dữ liệu để bắt đầu.</p></div></div>}</section>
    </div>
    {creating && <div className="fixed inset-0 z-50 grid place-items-center bg-slate-900/35 p-4"><form onSubmit={createRepo} className="w-full max-w-md rounded-3xl bg-white p-7 shadow-2xl"><h2 className="text-2xl font-bold">Tạo kho mới</h2><div className="mt-5 space-y-3"><input autoFocus required value={repoName} onChange={e=>setRepoName(e.target.value)} placeholder="Tên kho" className="w-full rounded-xl border border-slate-300 px-4 py-3"/><input value={repoDescription} onChange={e=>setRepoDescription(e.target.value)} placeholder="Mô tả" className="w-full rounded-xl border border-slate-300 px-4 py-3"/><select value={categoryId} onChange={e=>setCategoryId(e.target.value)} className="w-full rounded-xl border border-slate-300 px-4 py-3"><option value="">Chưa phân loại</option>{ownCategories.map(category=><option key={category.id} value={category.id}>{category.name}</option>)}</select><input value={newCategory} onChange={e=>setNewCategory(e.target.value)} placeholder="Hoặc tạo danh mục mới" className="w-full rounded-xl border border-slate-300 px-4 py-3"/></div><div className="mt-6 flex justify-end gap-3"><button type="button" onClick={()=>setCreating(false)} className="px-4 py-2 text-slate-600">Hủy</button><button disabled={busy} className="rounded-xl bg-blue-600 px-5 py-2.5 font-medium text-white">{busy?'Đang tạo...':'Tạo kho'}</button></div></form></div>}
    {creatingCategory && <div className="fixed inset-0 z-50 grid place-items-center bg-slate-900/35 p-4"><form onSubmit={createCategory} className="w-full max-w-md rounded-3xl bg-white p-7 shadow-2xl"><h2 className="text-2xl font-bold">Tạo danh mục</h2><input autoFocus required value={categoryName} onChange={e=>setCategoryName(e.target.value)} placeholder="Tên danh mục" className="mt-5 w-full rounded-xl border border-slate-300 px-4 py-3"/><div className="mt-6 flex justify-end gap-3"><button type="button" onClick={()=>setCreatingCategory(false)} className="px-4 py-2 text-slate-600">Hủy</button><button disabled={busy} className="rounded-xl bg-blue-600 px-5 py-2.5 font-medium text-white">{busy?'Đang tạo...':'Tạo danh mục'}</button></div></form></div>}
    {editingRepo && <div className="fixed inset-0 z-50 grid place-items-center bg-slate-900/35 p-4"><form onSubmit={updateRepo} className="w-full max-w-md rounded-3xl bg-white p-7 shadow-2xl"><h2 className="text-2xl font-bold">Sửa kho dữ liệu</h2><div className="mt-5 space-y-3"><input autoFocus required value={editRepoName} onChange={e=>setEditRepoName(e.target.value)} placeholder="Tên kho" className="w-full rounded-xl border border-slate-300 px-4 py-3"/><input value={editRepoDescription} onChange={e=>setEditRepoDescription(e.target.value)} placeholder="Mô tả" className="w-full rounded-xl border border-slate-300 px-4 py-3"/><select value={editRepoCategoryId} onChange={e=>setEditRepoCategoryId(e.target.value)} className="w-full rounded-xl border border-slate-300 px-4 py-3"><option value="">Chưa phân loại</option>{ownCategories.map(category=><option key={category.id} value={category.id}>{category.name}</option>)}</select></div><div className="mt-6 flex justify-end gap-3"><button type="button" onClick={()=>setEditingRepo(false)} className="px-4 py-2 text-slate-600">Hủy</button><button disabled={busy} className="rounded-xl bg-blue-600 px-5 py-2.5 font-medium text-white">{busy?'Đang lưu...':'Lưu thay đổi'}</button></div></form></div>}
  </div>;
}

function RepoCard({ repo, selected, onClick, shared = false }: { repo: Repository; selected: boolean; onClick: () => void; shared?: boolean }) {
  return <button onClick={onClick} className={`mb-2 w-full rounded-2xl border p-4 text-left transition-all ${selected?'border-blue-500 bg-blue-50 shadow-sm':'border-slate-200 bg-white hover:border-blue-300 hover:shadow-sm'}`}><div className="flex gap-3"><div className={`grid h-11 w-11 place-items-center rounded-xl ${shared?'bg-amber-50 text-amber-500':'bg-slate-100 text-slate-500'}`}>{shared?<Share2 size={20}/>:<Database size={20}/>}</div><div className="min-w-0"><p className="truncate text-base font-semibold text-slate-800">{repo.name}</p><p className="text-xs text-slate-500">{shared&&repo.owner_name?`${repo.owner_name} · `:''}{repo.document_count} tài liệu</p></div></div></button>;
}
