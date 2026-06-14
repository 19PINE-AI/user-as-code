import React from 'react'
import { motion } from 'framer-motion'

const LIMITS = [
  ['Write-time overhead', 'UaC runs two LLM passes where flat-fact systems run one; Phase-2 regeneration implies a scalability ceiling at hundreds of sessions.'],
  ['Neutral for pure recall', 'The typed state contributes only −1.3pp on LOCOMO QA (p=0.67). Its value concentrates in analytical inference and the constraint pipeline.'],
  ['Active service needs the pipeline', 'Without pre-computed alerts UaC drops to 52.5%; the 20-scenario hard set is underpowered against live Mem0 (p=0.69).'],
  ['Reimplementation fidelity', 'Same-backbone reproductions replace published retrieval stacks with one ChromaDB collection; published numbers are architecture ceilings, not direct competitors.'],
  ['Synthetic analytical data', 'Records are schema-clean and the single-query design is the worst case for UaC (structuring pays back after ~3 queries).'],
  ['Sandboxing required', 'Storing user state as executable code requires sandboxed execution and strict isolation against cross-user leakage or code injection.'],
]

export default function Footer() {
  return (
    <footer className="border-t border-white/5 bg-ink-950">
      <div className="container-page py-20">
        <div className="mx-auto max-w-3xl text-center">
          <span className="section-eyebrow">Honest accounting</span>
          <h2 className="mt-3 text-3xl font-bold tracking-tight text-white sm:text-4xl">Limitations</h2>
          <p className="mt-4 text-pretty text-slate-400">
            What the experiments do and do not establish — stated plainly.
          </p>
        </div>
        <div className="mt-10 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {LIMITS.map(([t, d], i) => (
            <motion.div
              key={t}
              initial={{ opacity: 0, y: 14 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-60px' }}
              transition={{ duration: 0.45, delay: i * 0.04 }}
              className="card p-5"
            >
              <div className="mb-2 h-1 w-8 rounded-full bg-gradient-to-r from-brand-400 to-accent-400" />
              <h4 className="font-semibold text-slate-100">{t}</h4>
              <p className="mt-1.5 text-sm leading-relaxed text-slate-400">{d}</p>
            </motion.div>
          ))}
        </div>

        <div className="mt-16 flex flex-col items-center gap-6 border-t border-white/10 pt-10 text-center">
          <div className="flex items-center gap-2.5">
            <span className="grid h-8 w-8 place-items-center rounded-lg bg-gradient-to-br from-brand-400 to-accent-500 font-mono text-sm font-bold text-ink-950">{'{}'}</span>
            <span className="font-mono text-sm font-semibold text-slate-100">User·as·Code</span>
          </div>
          <p className="max-w-xl text-sm text-slate-400">
            <span className="font-semibold text-slate-200">User as Code: Executable Memory for Personalized Agents</span>
            <br />Bojie Li · Pine AI · <a href="mailto:boj@19pine.ai" className="text-brand-300 hover:underline">boj@19pine.ai</a>
          </p>
          <div className="flex flex-wrap justify-center gap-3">
            <a href="https://github.com/bojieli/UserAsCode" target="_blank" rel="noreferrer" className="btn border border-white/10 bg-white/5 text-slate-200 hover:bg-white/10">
              Code &amp; data
            </a>
            <a href="#overview" className="btn border border-white/10 bg-white/5 text-slate-200 hover:bg-white/10">
              Back to top ↑
            </a>
          </div>
          <p className="font-mono text-[11px] text-slate-600">
            Interactive companion · 600 + 500 + 100 + 60 graded cases · cross-judged under Claude Opus 4.7
          </p>
        </div>
      </div>
    </footer>
  )
}
