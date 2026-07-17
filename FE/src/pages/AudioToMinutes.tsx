import React, { useState, useEffect, useRef } from 'react';
import { ApiClient } from '../api/client';
import type { AudioTaskResponse } from '../api/client';
import { Mic, UploadCloud, FileText, Download, Loader2, AlertCircle, Clock, RefreshCw, Trash2 } from 'lucide-react';
import { motion } from 'framer-motion';

export function AudioToMinutes() {
  const [tasks, setTasks] = useState<AudioTaskResponse[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchTasks = async () => {
    try {
      const data = await ApiClient.getAudioTasks();
      setTasks(data);
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    fetchTasks();
    const interval = setInterval(fetchTasks, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      setIsUploading(true);
      await ApiClient.uploadAudio(file);
      await fetchTasks();
    } catch (error: any) {
      alert(error.message || 'Lỗi khi upload file');
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleDeleteTask = async (taskId: string) => {
    if (!confirm('Bạn có chắc chắn muốn xóa lịch sử này?')) return;
    try {
      await ApiClient.deleteAudioTask(taskId);
      setTasks(prev => prev.filter(t => t.id !== taskId));
    } catch { /* ignore */ }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-indigo-400 flex items-center gap-3">
          <Mic className="w-8 h-8 text-blue-400" />
          Ghi âm thành Biên bản
        </h1>
        <p className="text-gray-400 mt-2 text-lg">
          Upload file ghi âm cuộc họp (MP3, WAV, M4A) để AI tự động chuyển đổi thành file Word biên bản theo đúng thể thức hành chính NĐ 30/2020.
        </p>
      </div>

      {/* Upload Zone */}
      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="relative bg-white/5 border border-white/10 rounded-2xl p-8 hover:bg-white/10 transition-colors border-dashed text-center cursor-pointer group"
      >
        <input 
          type="file" 
          accept="audio/*" 
          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-10"
          onChange={handleFileUpload}
          ref={fileInputRef}
          disabled={isUploading}
        />
        <div className="flex flex-col items-center justify-center space-y-4 relative z-0">
          <div className="p-4 bg-blue-500/20 rounded-full group-hover:scale-110 transition-transform">
            {isUploading ? (
              <Loader2 className="w-10 h-10 text-blue-400 animate-spin" />
            ) : (
              <UploadCloud className="w-10 h-10 text-blue-400" />
            )}
          </div>
          <div>
            <p className="text-xl font-medium text-white mb-2">
              {isUploading ? 'Đang tải lên và khai báo tác vụ...' : 'Kéo thả hoặc Nhấn để chọn file Ghi Âm'}
            </p>
            <p className="text-gray-400 text-sm max-w-lg mx-auto">
              Hỗ trợ MP3, WAV, M4A, OGG... dung lượng tối đa 100MB. Hệ thống sẽ tự động phân tích nội dung cuộc họp thành biên bản chuẩn tắc bằng công nghệ AI.
            </p>
          </div>
        </div>
      </motion.div>

      {/* Task List */}
      <div className="bg-white/5 border border-white/10 rounded-2xl overflow-hidden shadow-xl">
        <div className="p-4 border-b border-white/10 flex justify-between items-center bg-white/5 backdrop-blur-sm">
          <h2 className="text-xl font-semibold flex items-center gap-2">
            <Clock className="w-5 h-5 text-indigo-400" />
            Lịch sử xử lý
          </h2>
          <button 
            onClick={fetchTasks}
            className="flex items-center gap-2 px-3 py-1.5 text-sm bg-white/5 hover:bg-white/10 rounded-lg transition"
          >
            <RefreshCw className="w-4 h-4 text-gray-300" /> Làm mới
          </button>
        </div>

        {tasks.length === 0 ? (
          <div className="p-12 text-center text-gray-400 flex flex-col items-center justify-center">
            <Mic className="w-12 h-12 text-gray-600 mb-4 opacity-50" />
            Tài khoản của bạn chưa có lịch sử xử lý file ghi âm nào.
          </div>
        ) : (
          <div className="divide-y divide-white/5">
            {tasks.map(task => (
              <div key={task.id} className="p-5 flex flex-col md:flex-row gap-4 items-start md:items-center justify-between hover:bg-white-[0.02] transition-colors relative group">
                <div className="flex items-center gap-4 overflow-hidden w-full">
                  <div className={`p-3 rounded-2xl flex-shrink-0 shadow-lg ${
                    task.status === 'completed' ? 'bg-green-500/10 text-green-400 shadow-green-500/5' :
                    task.status === 'error' ? 'bg-red-500/10 text-red-400 shadow-red-500/5' :
                    'bg-blue-500/10 text-blue-400 shadow-blue-500/5'
                  }`}>
                    {task.status === 'completed' ? <FileText className="w-6 h-6" /> :
                     task.status === 'error' ? <AlertCircle className="w-6 h-6" /> :
                     <Loader2 className="w-6 h-6 animate-spin" />}
                  </div>
                  <div className="min-w-0 pr-4">
                    <h3 className="text-white font-medium truncate text-lg">{task.filename}</h3>
                    <div className="text-sm text-gray-400 mt-1.5 flex items-center gap-3 flex-wrap">
                      <span className="flex items-center gap-1.5">
                        <Clock className="w-3.5 h-3.5 opacity-70" />
                        {new Date(task.created_at).toLocaleString('vi-VN')}
                      </span>
                      <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold border ${
                        task.status === 'completed' ? 'border-green-500/30 text-green-300 bg-green-500/10' :
                        task.status === 'error' ? 'border-red-500/30 text-red-300 bg-red-500/10' :
                        'border-blue-500/30 text-blue-300 bg-blue-500/10'
                      }`}>
                        {task.progress_message || task.status}
                      </span>
                    </div>
                    {task.error_message && (
                      <div className="text-xs text-red-400 mt-2 line-clamp-2 bg-red-500/10 p-2 rounded-lg border border-red-500/20">
                        <span className="font-semibold mr-1">Lỗi:</span>{task.error_message}
                      </div>
                    )}
                  </div>
                </div>

                <div className="flex-shrink-0 flex items-center gap-2">
                  {task.output_ready && (
                    <a 
                      href={ApiClient.getAudioDownloadUrl(task.id)}
                      download
                      className="flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white rounded-xl font-medium shadow-lg shadow-blue-500/20 transition-all hover:scale-105 active:scale-95"
                    >
                      <Download className="w-4 h-4" />
                      Tải Tệp Word
                    </a>
                  )}
                  <button
                    onClick={(e) => { e.stopPropagation(); handleDeleteTask(task.id); }}
                    title="Xóa lịch sử"
                    className="p-2.5 text-red-400 hover:text-red-300 hover:bg-red-500/10 rounded-xl transition"
                  >
                    <Trash2 className="w-5 h-5" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
