import { useState, useRef, useEffect } from 'react';
import { ApiClient } from '../api/client';
import type { Repository, RepositoryCategory, ChatMessage } from '../api/client';
import { motion, AnimatePresence } from 'framer-motion';
import { Send, Bot, User, Loader2, Database, Trash2, MessageSquare, X, AlertTriangle, Folder } from 'lucide-react';
import { useSearchParams } from 'react-router-dom';
import clsx from 'clsx';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export function ChatAssistant() {
  const [searchParams] = useSearchParams();
  const [messages, setMessages] = useState<{ role: string; content: string }[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [streamingText, setStreamingText] = useState('');
  const scrollRef = useRef<HTMLDivElement>(null);

  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [categories, setCategories] = useState<RepositoryCategory[]>([]);
  const [selectedCategoryId, setSelectedCategoryId] = useState<string>('');
  const [selectedRepoId, setSelectedRepoId] = useState<string>('');
  const [showClearConfirm, setShowClearConfirm] = useState(false);

  useEffect(() => {
    Promise.all([ApiClient.getRepositories(), ApiClient.getRepositoryCategories()])
      .then(([repos, cats]) => {
        setRepositories(repos);
        setCategories(cats);
        const urlRepo = searchParams.get('repo');
        const initialRepo = (urlRepo && repos.find(r => r.id === urlRepo)) || repos[0];
        if (initialRepo) {
          setSelectedRepoId(initialRepo.id);
          setSelectedCategoryId(initialRepo.category_id || '__uncategorized');
        }
      })
      .catch(console.error);
  }, [searchParams]);

  // Load history when repo changes
  useEffect(() => {
    if (selectedRepoId) {
      ApiClient.getChatHistory(selectedRepoId).then(data => {
        const history = (data.messages || []).map((m: ChatMessage) => ({
          role: m.role, content: m.content,
        }));
        setMessages(history);
      }).catch(console.error);
    } else {
      setMessages([]);
    }
  }, [selectedRepoId]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, streamingText, isLoading]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading || !selectedRepoId) return;

    const userQuery = input.trim();
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: userQuery }]);
    setIsLoading(true);
    setStreamingText('');

    try {
      let fullResponse = '';
      for await (const chunk of ApiClient.chatStream(selectedRepoId, userQuery)) {
        fullResponse += chunk;
        setStreamingText(fullResponse);
      }
      setMessages(prev => [...prev, { role: 'assistant', content: fullResponse }]);
      setStreamingText('');
    } catch (error: any) {
      console.error(error);
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: `Lỗi: ${error.message || 'Không thể kết nối đến server.'}`
      }]);
      setStreamingText('');
    } finally {
      setIsLoading(false);
    }
  };

  const handleClearHistory = async () => {
    if (!selectedRepoId) return;
    try {
      await ApiClient.clearChatHistory(selectedRepoId);
      setMessages([]);
      setShowClearConfirm(false);
    } catch (err) { console.error(err); }
  };

  const selectedRepo = repositories.find(r => r.id === selectedRepoId);
  const filteredRepositories = selectedCategoryId === ''
    ? repositories
    : selectedCategoryId === '__uncategorized'
      ? repositories.filter(r => !r.category_id)
      : repositories.filter(r => r.category_id === selectedCategoryId);

  const handleCategoryChange = (categoryId: string) => {
    setSelectedCategoryId(categoryId);
    const nextRepos = categoryId === ''
      ? repositories
      : categoryId === '__uncategorized'
        ? repositories.filter(r => !r.category_id)
        : repositories.filter(r => r.category_id === categoryId);
    setSelectedRepoId(nextRepos[0]?.id || '');
  };

  const handleRepoChange = (repoId: string) => {
    setSelectedRepoId(repoId);
    const repo = repositories.find(r => r.id === repoId);
    if (repo) setSelectedCategoryId(repo.category_id || '__uncategorized');
  };

  return (
    <div className="flex h-[calc(100vh-3rem)] rounded-2xl overflow-hidden bg-white border border-slate-200 shadow-sm max-w-5xl mx-auto">
      <div className="flex-1 flex flex-col bg-slate-50 relative">
        {/* Header */}
        <div className="h-16 border-b border-slate-200 bg-white/80 backdrop-blur flex items-center px-6 gap-3">
          <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center text-blue-600">
            <Bot size={18} />
          </div>
          <div className="flex-1">
            <h2 className="font-bold text-slate-800">Office AI</h2>
            <p className="text-xs text-slate-500">
              {selectedRepo ? `Kho: ${selectedRepo.name}` : 'Vui lòng chọn kho dữ liệu'}
            </p>
          </div>

          {/* Category + repo selectors */}
          <div className="flex items-center gap-2">
            <div className="relative">
              <Folder size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
              <select
                value={selectedCategoryId}
                onChange={(e) => handleCategoryChange(e.target.value)}
                className="w-44 bg-slate-100 hover:bg-slate-200 border border-slate-200 rounded-lg pl-8 pr-3 py-1.5 text-sm font-medium text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
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
                onChange={(e) => handleRepoChange(e.target.value)}
                className="w-52 bg-slate-100 hover:bg-slate-200 border border-slate-200 rounded-lg pl-8 pr-3 py-1.5 text-sm font-medium text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
              >
                <option value="">Chọn kho</option>
                {filteredRepositories.map(repo => (
                  <option key={repo.id} value={repo.id}>
                    {repo.is_shared ? 'Chia sẻ: ' : ''}{repo.name} ({repo.document_count})
                  </option>
                ))}
              </select>
            </div>
          </div>

          {messages.length > 0 && (
            <button
              onClick={() => setShowClearConfirm(true)}
              className="p-2 text-slate-400 hover:text-rose-500 hover:bg-rose-50 rounded-lg transition-colors"
              title="Xóa lịch sử"
            >
              <Trash2 size={16} />
            </button>
          )}
        </div>

        {/* Messages */}
        <div ref={scrollRef} className="flex-1 p-6 overflow-y-auto space-y-6">
          {messages.length === 0 && !streamingText && (
            <div className="h-full flex flex-col items-center justify-center text-slate-400 space-y-4">
              <div className="w-20 h-20 rounded-full bg-blue-50 flex items-center justify-center">
                <MessageSquare size={32} className="text-blue-300" />
              </div>
              <div className="text-center">
                <p className="font-medium text-slate-500">Hỏi đáp với dữ liệu trong kho</p>
                <p className="text-sm mt-1">Chọn kho dữ liệu và đặt câu hỏi!</p>
              </div>
            </div>
          )}

          <AnimatePresence>
            {messages.map((msg, idx) => (
              <motion.div
                key={idx}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className={clsx("flex gap-4 w-full", msg.role === 'user' ? "justify-end" : "justify-start")}
              >
                {msg.role === 'assistant' && (
                  <div className="w-8 h-8 rounded-full bg-blue-100 flex-shrink-0 flex items-center justify-center text-blue-600 mt-1">
                    <Bot size={18} />
                  </div>
                )}
                <div className={clsx(
                  "max-w-[75%] px-5 py-4 rounded-2xl shadow-sm text-[15px] leading-relaxed",
                  msg.role === 'user'
                    ? "bg-blue-600 text-white rounded-tr-none whitespace-pre-wrap"
                    : "bg-white text-slate-800 border border-slate-100 rounded-tl-none [&>p:not(:last-child)]:mb-2 [&_ul]:list-disc [&_ul]:ml-5 [&_ul]:mb-2 [&_ol]:list-decimal [&_ol]:ml-5 [&_ol]:mb-2 [&_strong]:font-bold [&_em]:italic [&_a]:text-blue-600 [&_a]:underline [&_h1]:text-xl [&_h1]:font-bold [&_h2]:text-lg [&_h2]:font-bold [&_h3]:font-bold"
                )}>
                  {msg.role === 'user' ? msg.content : (
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {msg.content}
                    </ReactMarkdown>
                  )}
                </div>
                {msg.role === 'user' && (
                  <div className="w-8 h-8 rounded-full bg-slate-800 flex-shrink-0 flex items-center justify-center text-white mt-1">
                    <User size={18} />
                  </div>
                )}
              </motion.div>
            ))}
          </AnimatePresence>

          {/* Streaming message */}
          {streamingText && (
            <div className="flex gap-4 w-full justify-start">
              <div className="w-8 h-8 rounded-full bg-blue-100 flex-shrink-0 flex items-center justify-center text-blue-600 mt-1">
                <Bot size={18} />
              </div>
              <div className="max-w-[75%] px-5 py-4 rounded-2xl rounded-tl-none bg-white text-slate-800 border border-slate-100 shadow-sm text-[15px] leading-relaxed [&>p:not(:last-child)]:mb-2 [&_ul]:list-disc [&_ul]:ml-5 [&_ul]:mb-2 [&_ol]:list-decimal [&_ol]:ml-5 [&_ol]:mb-2 [&_strong]:font-bold [&_em]:italic [&_a]:text-blue-600 [&_a]:underline [&_h1]:text-xl [&_h1]:font-bold [&_h2]:text-lg [&_h2]:font-bold [&_h3]:font-bold">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {streamingText}
                </ReactMarkdown>
                <span className="inline-block w-2 h-4 bg-blue-500 ml-0.5 animate-pulse rounded-sm" />
              </div>
            </div>
          )}

          {isLoading && !streamingText && (
            <div className="flex gap-4 w-full">
              <div className="w-8 h-8 rounded-full bg-blue-100 flex-shrink-0 flex items-center justify-center text-blue-600">
                <Loader2 size={18} className="animate-spin" />
              </div>
              <div className="bg-white px-5 py-4 border border-slate-100 rounded-2xl rounded-tl-none flex items-center gap-2">
                <span className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" />
                <span className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '75ms' }} />
                <span className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
              </div>
            </div>
          )}
        </div>

        {/* Input */}
        <div className="p-4 bg-white border-t border-slate-200">
          <form onSubmit={handleSubmit} className="relative flex items-end gap-2 bg-slate-50 border border-slate-300 focus-within:border-blue-500 focus-within:ring-2 focus-within:ring-blue-500/20 rounded-2xl p-2 transition-all">
            <textarea
              className="flex-1 bg-transparent resize-none outline-none py-2 px-3 text-slate-800 min-h-[44px] max-h-32"
              placeholder={selectedRepoId ? "Nhập câu hỏi về dữ liệu trong kho..." : "Vui lòng chọn kho dữ liệu trước..."}
              rows={1}
              value={input}
              disabled={!selectedRepoId}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSubmit(e as any);
                }
              }}
            />
            <button
              type="submit"
              disabled={!input.trim() || isLoading || !selectedRepoId}
              className="p-3 bg-blue-600 text-white rounded-xl hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <Send size={18} />
            </button>
          </form>
          <div className="text-center mt-2">
            <span className="text-[10px] text-slate-400 uppercase tracking-widest font-semibold">
              Phản hồi dựa trên dữ liệu trong kho qua AI. Hãy kiểm tra lại thông tin.
            </span>
          </div>
        </div>

        {/* Clear History Confirmation Modal */}
        <AnimatePresence>
          {showClearConfirm && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="absolute inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center z-50"
              onClick={() => setShowClearConfirm(false)}
            >
              <motion.div
                initial={{ scale: 0.9, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                exit={{ scale: 0.9, opacity: 0 }}
                onClick={(e) => e.stopPropagation()}
                className="bg-white rounded-2xl p-6 w-full max-w-sm shadow-2xl mx-4"
              >
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-10 h-10 rounded-full bg-rose-100 flex items-center justify-center">
                    <AlertTriangle size={20} className="text-rose-500" />
                  </div>
                  <div>
                    <h3 className="font-bold text-slate-800">Xóa lịch sử chat</h3>
                    <p className="text-sm text-slate-500">Hành động này không thể hoàn tác</p>
                  </div>
                </div>
                <p className="text-sm text-slate-600 mb-5">
                  Bạn có chắc muốn xóa toàn bộ <strong>{messages.length}</strong> tin nhắn trong cuộc trò chuyện này?
                </p>
                <div className="flex gap-3">
                  <button
                    onClick={() => setShowClearConfirm(false)}
                    className="flex-1 py-2.5 bg-slate-100 text-slate-700 rounded-xl font-medium hover:bg-slate-200 transition-colors flex items-center justify-center gap-2"
                  >
                    <X size={16} /> Hủy
                  </button>
                  <button
                    onClick={handleClearHistory}
                    className="flex-1 py-2.5 bg-rose-600 text-white rounded-xl font-medium hover:bg-rose-700 transition-colors flex items-center justify-center gap-2"
                  >
                    <Trash2 size={16} /> Xóa
                  </button>
                </div>
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
