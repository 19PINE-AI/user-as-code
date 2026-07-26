import React, { useState } from 'react'
import { motion } from 'framer-motion'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
  LineChart, Line, Legend, ComposedChart,
} from 'recharts'
import { useJson, Spinner, cx } from '../lib/ui.jsx'

const AXIS = { stroke: '#64748b', fontSize: 11 }
const GRID = 'rgba(148,163,184,0.1)'

function TooltipBox({ active, payload, label, fmt }) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-lg border border-white/10 bg-ink-950/95 px-3 py-2 text-xs shadow-xl backdrop-blur">
      {label !== undefined && <div className="mb-1 font-semibold text-slate-200">{label}</div>}
      {payload.map((p, i) => (
        <div key={i} className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full" style={{ background: p.color || p.fill }} />
          <span className="text-slate-400">{p.name}:</span>
          <span className="font-mono text-slate-100">{fmt ? fmt(p.value) : p.value}</span>
        </div>
      ))}
    </div>
  )
}

function ChartCard({ title, sub, children, className }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 18 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-60px' }}
      transition={{ duration: 0.5 }}
      className={cx('card p-5', className)}
    >
      <h3 className="text-base font-semibold text-white">{title}</h3>
      {sub && <p className="mt-1 text-xs text-slate-400">{sub}</p>}
      <div className="mt-4">{children}</div>
    </motion.div>
  )
}

/* Standard benchmark bars (LOCOMO / LME toggle) */
function BenchmarkBars({ summary }) {
  const [bench, setBench] = useState('locomo')
  const [noteOpen, setNoteOpen] = useState(false)
  const rows = summary[bench]
  const data = rows.map((r) => ({
    name: r.lite ? `${r.system} (lite)` : r.system,
    acc: r.acc, ours: r.ours, reference: r.reference, lite: r.lite,
  }))
  return (
    <ChartCard
      title="Standard benchmarks"
      sub="Gemini 3 Flash judge accuracy. Full LOCOMO uses 1,540 answer-bearing questions; LongMemEval uses all 500 questions. Full Context is a reference, not an upper bound."
    >
      <div className="mb-3 inline-flex rounded-lg border border-white/10 bg-ink-900/60 p-1">
        {[['locomo', 'LOCOMO · 1,986'], ['lme', 'LongMemEval · 500']].map(([k, l]) => (
          <button
            key={k}
            onClick={() => setBench(k)}
            className={cx('rounded-md px-3 py-1 text-xs font-medium transition', bench === k ? 'bg-brand-400/15 text-brand-200' : 'text-slate-400 hover:text-slate-100')}
          >
            {l}
          </button>
        ))}
      </div>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={data} layout="vertical" margin={{ left: 12, right: 28 }}>
          <CartesianGrid horizontal={false} stroke={GRID} />
          <XAxis type="number" domain={[0, 100]} tick={AXIS} unit="%" />
          <YAxis type="category" dataKey="name" tick={{ ...AXIS, fontSize: 10.5 }} width={120} />
          <Tooltip content={<TooltipBox fmt={(v) => `${v}%`} />} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
          <Bar dataKey="acc" radius={[0, 6, 6, 0]} barSize={20} label={{ position: 'right', fill: '#cbd5e1', fontSize: 11, formatter: (v) => `${v}%` }}>
            {data.map((d, i) => (
              <Cell key={i} fill={d.ours ? '#22d3ee' : d.reference ? '#a78bfa' : d.lite ? '#3f4a63' : '#475569'} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <button onClick={() => setNoteOpen((v) => !v)} className="mt-2 inline-flex items-center gap-1 text-[11px] font-medium text-amber-300/90 hover:text-amber-200">
        <svg className={cx('h-3 w-3 transition', noteOpen && 'rotate-90')} viewBox="0 0 20 20" fill="currentColor"><path d="M7 5l6 5-6 5V5z" /></svg>
        Implementation context
      </button>
      {noteOpen && (
        <p className="mt-2 rounded-lg border border-amber-400/20 bg-amber-500/[0.06] px-3 py-2.5 text-[11.5px] leading-relaxed text-slate-300">
          {summary.notes.baseline}
        </p>
      )}
    </ChartCard>
  )
}

/* LongMemEval per question-type breakdown (heatmap-style grid) */
function LmeByType({ summary }) {
  const types = ['KU', 'MS', 'SA', 'SP', 'SU', 'TR']
  const legend = summary.lme_type_legend
  const nmap = summary.lme_type_n
  const cell = (v) => {
    // green→amber→red gradient by accuracy
    const h = Math.round((v / 100) * 140) // 0=red .. 140=green
    return `hsl(${h}, 65%, ${22 + (v / 100) * 16}%)`
  }
  return (
    <ChartCard
      title="LongMemEval by question type"
      sub="Per-type differences are descriptive; the artifacts do not isolate the components or error mechanisms that cause them."
    >
      <div className="overflow-x-auto">
        <table className="w-full border-separate border-spacing-1 text-center text-xs">
          <thead>
            <tr>
              <th className="px-2 py-1 text-left font-medium text-slate-500">System</th>
              {types.map((t) => (
                <th key={t} className="px-1 py-1 font-mono text-[10px] text-slate-400" title={`${legend[t]} (n=${nmap[t]})`}>{t}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {summary.lme.map((r) => (
              <tr key={r.system}>
                <td className={cx('px-2 py-1 text-left text-[11px] font-medium', r.ours ? 'text-brand-200' : 'text-slate-300')}>
                  {r.lite ? `${r.system}*` : r.system}
                </td>
                {types.map((t) => (
                  <td
                    key={t}
                    className="rounded-md px-1 py-1.5 font-mono text-[11px] font-semibold text-white/90"
                    style={{ background: cell(r.types[t]) }}
                    title={`${r.system} · ${legend[t]}: ${r.types[t]}%`}
                  >
                    {r.types[t]}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 font-mono text-[10px] text-slate-500">
        {types.map((t) => (
          <span key={t}>{t} = {legend[t]}</span>
        ))}
        <span className="text-slate-600">· * = same-backbone lite reimpl.</span>
      </div>
    </ChartCard>
  )
}

/* Analytical scaling line chart */
function AnalyticalScaling({ summary }) {
  const Ns = ['20', '50', '100', '200', '500']
  const data = Ns.map((n) => {
    const row = { n }
    summary.analytical.forEach((s) => {
      row[s.system] = s.byN[n]
    })
    return row
  })
  const colorFor = (name) =>
    /UaC/i.test(name) ? '#22d3ee' : /REPL/i.test(name) ? '#a78bfa' : /Full/i.test(name) ? '#34d399' : /MemMachine/i.test(name) ? '#f472b6' : '#f87171'
  return (
    <ChartCard
      title="Analytical inference vs. record count"
      sub="UaC and raw-record FC+REPL both score 100% after rerunning the corrected year-qualified item; retrieval-only systems decline as N grows in this harness."
    >
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={data} margin={{ left: -8, right: 12 }}>
          <CartesianGrid stroke={GRID} />
          <XAxis dataKey="n" tick={AXIS} label={{ value: 'N records', position: 'insideBottom', offset: -2, fill: '#64748b', fontSize: 11 }} />
          <YAxis domain={[0, 100]} tick={AXIS} unit="%" />
          <Tooltip content={<TooltipBox fmt={(v) => `${v}%`} />} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          {summary.analytical.map((s) => (
            <Line
              key={s.system}
              type="monotone"
              dataKey={s.system}
              stroke={colorFor(s.system)}
              strokeWidth={/UaC/i.test(s.system) ? 3 : 2}
              dot={{ r: 3 }}
              activeDot={{ r: 5 }}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </ChartCard>
  )
}

/* Modularity */
function Modularity({ summary }) {
  const data = summary.modularity.map((r) => ({ name: r.strategy.split(' ')[0], acc: r.acc, perCase: r.perCase }))
  return (
    <ChartCard title="Modularity & progressive disclosure" sub="Loading only the query-relevant domain matches monolithic accuracy at 14.9× lower prompt cost on a 500-record state.">
      <ResponsiveContainer width="100%" height={300}>
        <ComposedChart data={data} margin={{ left: -6, right: 6 }}>
          <CartesianGrid vertical={false} stroke={GRID} />
          <XAxis dataKey="name" tick={AXIS} />
          <YAxis yAxisId="l" domain={[0, 100]} tick={AXIS} unit="%" />
          <YAxis yAxisId="r" orientation="right" tick={AXIS} unit=" m$" />
          <Tooltip content={<TooltipBox />} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <Bar yAxisId="l" dataKey="acc" name="Accuracy %" fill="#22d3ee" radius={[4, 4, 0, 0]} barSize={28} />
          <Line yAxisId="r" dataKey="perCase" name="Cost m$/case" stroke="#fbbf24" strokeWidth={2.5} dot={{ r: 4 }} />
        </ComposedChart>
      </ResponsiveContainer>
    </ChartCard>
  )
}

export default function Results() {
  const { data: summary, error } = useJson('summary.json')

  return (
    <section id="results" className="border-t border-white/5 bg-ink-900/30 py-20 sm:py-28">
      <div className="container-page">
        <div className="mx-auto max-w-3xl text-center">
          <span className="section-eyebrow">Evaluation</span>
          <h2 className="mt-3 text-3xl font-bold tracking-tight text-white sm:text-4xl">Results at a glance</h2>
          <p className="mt-4 text-pretty text-slate-400">
            Current publication results cover full LOCOMO, LongMemEval, the corrected analytical benchmark,
            and the modular-loading study. Metric-specific recall tradeoffs are reported separately.
          </p>
        </div>

        {error && <p className="mt-10 text-center text-bad">Failed to load summary data.</p>}
        {!summary && !error && <Spinner />}

        {summary && (
          <div className="mt-12 grid gap-5 lg:grid-cols-2">
            <BenchmarkBars summary={summary} />
            <LmeByType summary={summary} />
            <AnalyticalScaling summary={summary} />
            <Modularity summary={summary} />
          </div>
        )}
      </div>
    </section>
  )
}
