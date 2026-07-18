import type { ChatChart } from '../api/client';

const COLORS = ['#2563eb', '#14b8a6', '#f59e0b', '#ef4444', '#8b5cf6', '#64748b'];

function number(value: number) {
  return new Intl.NumberFormat('vi-VN', { maximumFractionDigits: 2 }).format(value);
}

function BarOrLine({ chart }: { chart: ChatChart }) {
  const width = 640, height = 250, pad = { l: 70, r: 24, t: 24, b: 52 };
  const values = chart.values;
  const max = Math.max(...values, 1);
  const usableW = width - pad.l - pad.r, usableH = height - pad.t - pad.b;
  const point = (value: number, index: number) => ({
    x: pad.l + (values.length === 1 ? usableW / 2 : index * usableW / (values.length - 1)),
    y: pad.t + usableH - value / max * usableH,
  });
  const barCenter = (index: number) => pad.l + usableW * (index + .5) / values.length;
  const linePoints = values.map((value, index) => { const p = point(value, index); return `${p.x},${p.y}`; }).join(' ');
  return <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-auto" role="img" aria-label={chart.title}>
    {[0, .25, .5, .75, 1].map(t => <g key={t}>
      <line x1={pad.l} x2={width - pad.r} y1={pad.t + usableH * (1 - t)} y2={pad.t + usableH * (1 - t)} stroke="#e2e8f0" />
      <text x={pad.l - 7} y={pad.t + usableH * (1 - t) + 4} textAnchor="end" className="fill-slate-400 text-[10px]">{number(max * t)}</text>
    </g>)}
    {chart.chart_type === 'bar' ? values.map((value, index) => {
      const barWidth = Math.min(48, usableW / values.length * .64);
      const x = barCenter(index); const p = point(value, index);
      return <rect key={index} x={x - barWidth / 2} y={p.y} width={barWidth} height={pad.t + usableH - p.y} rx="4" fill={COLORS[index % COLORS.length]} />;
    }) : <><polyline points={linePoints} fill="none" stroke={COLORS[0]} strokeWidth="3" strokeLinejoin="round" />
      {values.map((value, index) => { const p = point(value, index); return <circle key={index} cx={p.x} cy={p.y} r="4" fill="white" stroke={COLORS[0]} strokeWidth="3" />; })}</>}
    {chart.labels.map((label, index) => {
      const x = chart.chart_type === 'bar' ? barCenter(index) : point(0, index).x;
      return <text key={index} x={x} y={height - 23} textAnchor="middle" className="fill-slate-500 text-[10px]">{label.length > 18 ? `${label.slice(0, 17)}…` : label}</text>;
    })}
    <text x={width / 2} y={height - 5} textAnchor="middle" className="fill-slate-400 text-[10px]">{chart.x_label || (chart.chart_type === 'line' ? 'Thời gian' : 'Hạng mục')}</text>
  </svg>;
}

function Pie({ chart }: { chart: ChatChart }) {
  const total = chart.values.reduce((sum, value) => sum + Math.max(value, 0), 0);
  let offset = 0;
  const radius = 44, circumference = 2 * Math.PI * radius;
  return <div className="flex flex-wrap items-center gap-5 px-2 py-3">
    <svg viewBox="0 0 120 120" className="w-32 h-32 -rotate-90" role="img" aria-label={chart.title}>
      <circle cx="60" cy="60" r={radius} fill="none" stroke="#e2e8f0" strokeWidth="20" />
      {chart.values.map((value, index) => { const length = total ? Math.max(value, 0) / total * circumference : 0; const dash = `${length} ${circumference - length}`; const current = offset; offset += length; return <circle key={index} cx="60" cy="60" r={radius} fill="none" stroke={COLORS[index % COLORS.length]} strokeWidth="20" strokeDasharray={dash} strokeDashoffset={-current} />; })}
    </svg>
    <div className="space-y-1.5 text-xs text-slate-600">{chart.labels.map((label, index) => <div key={index} className="flex items-center gap-2"><span className="w-2.5 h-2.5 rounded-full" style={{ background: COLORS[index % COLORS.length] }} /><span>{label}: <b>{number(chart.values[index])}</b></span></div>)}</div>
  </div>;
}

function Scatter({ chart }: { chart: ChatChart }) {
  const width = 640, height = 250, pad = 42;
  const minX = Math.min(...chart.x), maxX = Math.max(...chart.x), minY = Math.min(...chart.y), maxY = Math.max(...chart.y);
  const scale = (value: number, min: number, max: number, size: number) => pad + (value - min) / Math.max(max - min, 1) * (size - 2 * pad);
  return <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-auto" role="img" aria-label={chart.title}>
    <line x1={pad} x2={width - pad} y1={height - pad} y2={height - pad} stroke="#94a3b8" /><line x1={pad} x2={pad} y1={pad} y2={height - pad} stroke="#94a3b8" />
    {chart.x.map((value, index) => <g key={index}><circle cx={scale(value, minX, maxX, width)} cy={height - scale(chart.y[index], minY, maxY, height)} r="5" fill={COLORS[0]} /><title>{chart.labels[index] || `${value}, ${chart.y[index]}`}</title></g>)}
    <text x={width / 2} y={height - 8} textAnchor="middle" className="fill-slate-400 text-[10px]">{chart.x_label || 'X'}</text><text x="13" y={height / 2} textAnchor="middle" className="fill-slate-400 text-[10px]">{chart.y_label || 'Y'}</text>
  </svg>;
}

export function ChatCharts({ charts }: { charts: ChatChart[] }) {
  return <div className="space-y-3 mt-3">{charts.map((chart, index) => <section key={`${chart.title}-${index}`} className="rounded-xl border border-blue-100 bg-slate-50 p-3 overflow-hidden">
    <h4 className="font-semibold text-sm text-slate-800">{chart.title}</h4>
    {chart.description && <p className="text-xs text-slate-500 mt-0.5">{chart.description}</p>}
    {chart.chart_type === 'pie' ? <Pie chart={chart} /> : chart.chart_type === 'scatter' ? <Scatter chart={chart} /> : chart.chart_type === 'table' ? <div className="overflow-x-auto mt-3"><table className="w-full text-xs"><tbody>{chart.labels.map((label, row) => <tr key={row} className="border-t border-slate-200"><td className="py-1.5 text-slate-600">{label}</td><td className="py-1.5 text-right font-medium">{number(chart.values[row])}</td></tr>)}</tbody></table></div> : <BarOrLine chart={chart} />}
  </section>)}</div>;
}
