import { Link } from 'react-router-dom';
import { Database, FilePenLine, ArrowRight } from 'lucide-react';
import { motion } from 'framer-motion';

const actions = [
  { to: '/data', title: 'Kho dữ liệu', text: 'Quản lý kho, danh mục và tài liệu nguồn.', icon: Database, color: 'bg-blue-600' },
  { to: '/drafting', title: 'Xây dựng dự thảo', text: 'Tổng hợp góp ý và hoàn thiện bản dự thảo.', icon: FilePenLine, color: 'bg-violet-600' },
];

export function HomePage() {
  return <div className="max-w-5xl mx-auto py-12">
    <h1 className="text-3xl font-bold text-slate-900">Trợ lý Ơi</h1>
    <p className="mt-2 text-slate-500">Chọn chức năng để bắt đầu công việc.</p>
    <div className="grid md:grid-cols-2 gap-6 mt-10">
      {actions.map(({ to, title, text, icon: Icon, color }) => <motion.div key={to} whileHover={{ y: -4 }}>
        <Link to={to} className="block p-7 rounded-2xl bg-white border border-slate-200 shadow-sm hover:shadow-lg transition-shadow">
          <div className={`w-12 h-12 ${color} rounded-xl grid place-items-center text-white`}><Icon size={24}/></div>
          <h2 className="mt-5 text-xl font-bold text-slate-900">{title}</h2>
          <p className="mt-2 text-slate-500">{text}</p>
          <span className="mt-6 inline-flex items-center gap-2 font-medium text-blue-600">Mở chức năng <ArrowRight size={17}/></span>
        </Link>
      </motion.div>)}
    </div>
  </div>;
}
