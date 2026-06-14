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
  const rows = summary[bench]
  const data = rows.map((r) => ({ name: r.system, acc: r.acc, ci: r.ci, ours: r.ours, upper: r.upper }))
  return (
    <ChartCard
      title="Standard benchmarks"
      sub="LLM-as-Judge accuracy on a shared Gemini 3 Flash backbone. UaC ties the full-context upper bound and leads every memory system."
    >
      <div className="mb-3 inline-flex rounded-lg border border-white/10 bg-ink-900/60 p-1">
        {[['locomo', 'LOCOMO · 600'], ['lme', 'LongMemEval · 500']].map(([k, l]) => (
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
          <YAxis type="category" dataKey="name" tick={{ ...AXIS, fontSize: 11 }} width={108} />
          <Tooltip content={<TooltipBox fmt={(v) => `${v}%`} />} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
          <Bar dataKey="acc" radius={[0, 6, 6, 0]} barSize={20} label={{ position: 'right', fill: '#cbd5e1', fontSize: 11, formatter: (v) => `${v}%` }}>
            {data.map((d, i) => (
              <Cell key={i} fill={d.ours ? '#22d3ee' : d.upper ? '#a78bfa' : '#475569'} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
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
      sub="Code-executable representations stay ≥95%; retrieval collapses as more records become relevant than top-k can return."
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

/* Active service grouped bars */
function ActiveService({ summary }) {
  const map = {}
  summary.active_standard.forEach((r) => {
    map[r.system] = { name: r.system, standard: r.rate, ours: r.ours }
  })
  summary.active_hard.forEach((r) => {
    map[r.system] = { ...(map[r.system] || { name: r.system, ours: r.ours }), hard: r.rate }
  })
  const data = Object.values(map)
  return (
    <ChartCard
      title="Active service — proactive alerts"
      sub="The first benchmark for memory-triggered alerts initiated without a user query. UaC's constraint pipeline leads on standard and hard arithmetic scenarios."
    >
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={data} margin={{ left: -8, right: 8 }}>
          <CartesianGrid vertical={false} stroke={GRID} />
          <XAxis dataKey="name" tick={{ ...AXIS, fontSize: 9.5 }} interval={0} angle={-12} textAnchor="end" height={64} />
          <YAxis domain={[0, 100]} tick={AXIS} unit="%" />
          <Tooltip content={<TooltipBox fmt={(v) => `${v}%`} />} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <Bar dataKey="standard" name="Standard (n=40)" fill="#22d3ee" radius={[4, 4, 0, 0]} barSize={16} />
          <Bar dataKey="hard" name="Hard (n=20)" fill="#7c3aed" radius={[4, 4, 0, 0]} barSize={16} />
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  )
}

/* Ablation combined chart */
function Ablation({ summary }) {
  const data = summary.ablation.map((r) => ({ name: r.version.split(' ')[0], locomo: r.locomo, active: r.active }))
  return (
    <ChartCard title="Architecture ablation" sub="Append-only extraction is the single biggest recall gain (+19pp); two-phase separation solves the overwrite problem; the pipeline drives active service.">
      <ResponsiveContainer width="100%" height={300}>
        <ComposedChart data={data} margin={{ left: -8, right: 8 }}>
          <CartesianGrid vertical={false} stroke={GRID} />
          <XAxis dataKey="name" tick={AXIS} />
          <YAxis domain={[0, 100]} tick={AXIS} unit="%" />
          <Tooltip content={<TooltipBox fmt={(v) => `${v}%`} />} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <Bar dataKey="locomo" name="LOCOMO (300)" fill="#22d3ee" radius={[4, 4, 0, 0]} barSize={22} />
          <Line dataKey="active" name="Active service" stroke="#7c3aed" strokeWidth={2.5} dot={{ r: 4 }} />
        </ComposedChart>
      </ResponsiveContainer>
    </ChartCard>
  )
}

/* Cost amortization */
function Amortization({ summary }) {
  // build cumulative cost curves at N=500 across K queries
  const N500 = summary.amortization.find((r) => r.n === 500)
  const data = []
  for (let k = 0; k <= 12; k++) {
    data.push({
      k,
      UaC: +(N500.structuring + k * N500.uacQuery).toFixed(1),
      'FC+REPL': +(k * N500.fcQuery).toFixed(1),
    })
  }
  return (
    <ChartCard title="Cost amortization (N=500)" sub="UaC pays a one-time structuring cost, then ~1.4 m$/query. It repays after ~3 queries and is ~15× cheaper over 100 queries.">
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={data} margin={{ left: 4, right: 12 }}>
          <CartesianGrid stroke={GRID} />
          <XAxis dataKey="k" tick={AXIS} label={{ value: 'queries (K)', position: 'insideBottom', offset: -2, fill: '#64748b', fontSize: 11 }} />
          <YAxis tick={AXIS} label={{ value: 'm$', angle: -90, position: 'insideLeft', fill: '#64748b', fontSize: 11 }} />
          <Tooltip content={<TooltipBox fmt={(v) => `${v} m$`} />} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <Line type="monotone" dataKey="UaC" stroke="#22d3ee" strokeWidth={3} dot={false} />
          <Line type="monotone" dataKey="FC+REPL" stroke="#a78bfa" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </ChartCard>
  )
}

/* Cross-judge kappa scatter as table-ish bars */
function JudgeKappa({ summary }) {
  const [ds, setDs] = useState('LOCOMO')
  const rows = summary.judge.filter((r) => r.dataset === ds)
  return (
    <ChartCard title="Cross-family judge agreement" sub="Re-judging all 7,700 predictions under Claude Opus 4.7. Rankings are preserved; every κ is substantial-to-almost-perfect.">
      <div className="mb-3 inline-flex rounded-lg border border-white/10 bg-ink-900/60 p-1">
        {['LOCOMO', 'LME-500'].map((k) => (
          <button key={k} onClick={() => setDs(k)} className={cx('rounded-md px-3 py-1 text-xs font-medium transition', ds === k ? 'bg-brand-400/15 text-brand-200' : 'text-slate-400 hover:text-slate-100')}>{k}</button>
        ))}
      </div>
      <div className="space-y-2">
        {rows.map((r) => (
          <div key={r.system} className="grid grid-cols-[100px_1fr_auto] items-center gap-3 text-xs">
            <span className={cx('truncate font-medium', r.ours ? 'text-brand-300' : 'text-slate-300')}>{r.system}</span>
            <div className="h-3 overflow-hidden rounded-full bg-ink-700">
              <div className="h-full rounded-full bg-gradient-to-r from-accent-500 to-brand-400" style={{ width: `${r.kappa * 100}%` }} />
            </div>
            <span className="font-mono text-slate-200">κ {r.kappa.toFixed(2)}</span>
          </div>
        ))}
      </div>
      <div className="mt-3 text-[11px] text-slate-500">Gemini vs. Claude accuracy delta stays under ~6pp; UaC's lead over lower systems widens under the stricter judge.</div>
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
            Five evaluation axes, one shared backbone. UaC matches the full-context upper bound on recall and pulls
            decisively ahead exactly where retrieval is structurally lossy — aggregation and proactive alerting.
          </p>
        </div>

        {error && <p className="mt-10 text-center text-bad">Failed to load summary data.</p>}
        {!summary && !error && <Spinner />}

        {summary && (
          <div className="mt-12 grid gap-5 lg:grid-cols-2">
            <BenchmarkBars summary={summary} />
            <AnalyticalScaling summary={summary} />
            <ActiveService summary={summary} />
            <Ablation summary={summary} />
            <Amortization summary={summary} />
            <Modularity summary={summary} />
            <JudgeKappa summary={summary} />
            <ChartCard title="Answer-time latency (LOCOMO)" sub="UaC trades ~1.4s of latency for a 49.5pp accuracy gain over Mem0; its median stays under conversational pacing.">
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={summary.latency.map((r) => ({ name: r.system, median: r.median, p95: r.p95, ours: r.ours }))} margin={{ left: -8, right: 8 }}>
                  <CartesianGrid vertical={false} stroke={GRID} />
                  <XAxis dataKey="name" tick={{ ...AXIS, fontSize: 9.5 }} interval={0} angle={-12} textAnchor="end" height={64} />
                  <YAxis tick={AXIS} unit="s" />
                  <Tooltip content={<TooltipBox fmt={(v) => `${v}s`} />} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  <Bar dataKey="median" name="Median" fill="#22d3ee" radius={[4, 4, 0, 0]} barSize={16} />
                  <Bar dataKey="p95" name="p95" fill="#475569" radius={[4, 4, 0, 0]} barSize={16} />
                </BarChart>
              </ResponsiveContainer>
            </ChartCard>
          </div>
        )}
      </div>
    </section>
  )
}
