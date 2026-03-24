import ReactECharts from 'echarts-for-react';
import type { ActivityEvent } from '../types';

interface Props {
  events: ActivityEvent[];
}

const TEXT_COLOR = '#cbd5e1';
const GRID_COLOR = 'rgba(148,163,184,0.1)';
const TOOLTIP_BG = '#1e293b';

function makeGradient(color1: string, color2: string) {
  return {
    type: 'linear' as const,
    x: 0, y: 0, x2: 1, y2: 0,
    colorStops: [
      { offset: 0, color: color1 },
      { offset: 1, color: color2 },
    ],
  };
}

export default function Charts({ events }: Props) {
  // 1. Activity by Project
  const projectCounts: Record<string, number> = {};
  for (const e of events) {
    projectCounts[e.project_key] = (projectCounts[e.project_key] ?? 0) + 1;
  }
  const projectEntries = Object.entries(projectCounts).sort((a, b) => b[1] - a[1]);

  const projectOption = {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', backgroundColor: TOOLTIP_BG, borderColor: '#334155', textStyle: { color: TEXT_COLOR } },
    grid: { left: '3%', right: '6%', containLabel: true },
    xAxis: { type: 'value', axisLabel: { color: TEXT_COLOR }, splitLine: { lineStyle: { color: GRID_COLOR } } },
    yAxis: { type: 'category', data: projectEntries.map(([k]) => k).reverse(), axisLabel: { color: TEXT_COLOR } },
    series: [{
      type: 'bar',
      data: projectEntries.map(([, v]) => v).reverse(),
      itemStyle: { color: makeGradient('#0ea5e9', '#8b5cf6') },
    }],
  };

  // 2. Top Repos
  const repoCounts: Record<string, number> = {};
  for (const e of events) {
    repoCounts[e.repo] = (repoCounts[e.repo] ?? 0) + 1;
  }
  const topRepos = Object.entries(repoCounts).sort((a, b) => b[1] - a[1]).slice(0, 10);

  const repoOption = {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', backgroundColor: TOOLTIP_BG, borderColor: '#334155', textStyle: { color: TEXT_COLOR } },
    grid: { left: '3%', right: '6%', containLabel: true },
    xAxis: { type: 'value', axisLabel: { color: TEXT_COLOR }, splitLine: { lineStyle: { color: GRID_COLOR } } },
    yAxis: { type: 'category', data: topRepos.map(([k]) => k).reverse(), axisLabel: { color: TEXT_COLOR } },
    series: [{
      type: 'bar',
      data: topRepos.map(([, v]) => v).reverse(),
      itemStyle: { color: makeGradient('#8b5cf6', '#0ea5e9') },
    }],
  };

  // 3. Activity Over Time (monthly)
  const monthCounts: Record<string, number> = {};
  for (const e of events) {
    const month = e.created_at.slice(0, 7); // YYYY-MM
    monthCounts[month] = (monthCounts[month] ?? 0) + 1;
  }
  const months = Object.keys(monthCounts).sort();
  const monthValues = months.map(m => monthCounts[m]);

  const timeOption = {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', backgroundColor: TOOLTIP_BG, borderColor: '#334155', textStyle: { color: TEXT_COLOR } },
    grid: { left: '3%', right: '4%', containLabel: true },
    xAxis: { type: 'category', data: months, axisLabel: { color: TEXT_COLOR, rotate: 30 }, axisLine: { lineStyle: { color: GRID_COLOR } } },
    yAxis: { type: 'value', axisLabel: { color: TEXT_COLOR }, splitLine: { lineStyle: { color: GRID_COLOR } } },
    series: [{
      type: 'line',
      data: monthValues,
      smooth: true,
      lineStyle: { color: '#0ea5e9', width: 2 },
      areaStyle: {
        color: {
          type: 'linear' as const,
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(14,165,233,0.3)' },
            { offset: 1, color: 'rgba(14,165,233,0.02)' },
          ],
        },
      },
      symbol: 'circle',
      symbolSize: 5,
      itemStyle: { color: '#0ea5e9' },
    }],
  };

  if (events.length === 0) {
    return (
      <div className="text-slate-400 text-sm text-center py-8">No data to display charts.</div>
    );
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4 mb-6">
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
        <h3 className="text-slate-300 font-semibold text-sm mb-3">Activity by Project</h3>
        <ReactECharts option={projectOption} style={{ height: 260 }} />
      </div>
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
        <h3 className="text-slate-300 font-semibold text-sm mb-3">Top 10 Repos</h3>
        <ReactECharts option={repoOption} style={{ height: 260 }} />
      </div>
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 lg:col-span-2 xl:col-span-1">
        <h3 className="text-slate-300 font-semibold text-sm mb-3">Activity Over Time</h3>
        <ReactECharts option={timeOption} style={{ height: 260 }} />
      </div>
    </div>
  );
}
