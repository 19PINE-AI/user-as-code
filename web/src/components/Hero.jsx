import React from 'react'
import { motion } from 'framer-motion'
import { CodeBlock, StatPill } from '../lib/ui.jsx'

const HERO_CODE = `# Two facts arrive ten months apart, in different sessions:
#   "I'm DEATHLY allergic to penicillin" (2024-03-01)
#   "Dr. Chen prescribed amoxicillin 500mg" (2025-01-10)

# Phase 2 structures them into one typed state:
medical = MedicalProfile(
    allergies=[Allergy(allergen="Penicillin", drug_class="penicillin")],
    medications=[Medication(name="Amoxicillin", drug_class="penicillin")],
)

# A 1-line boolean check the interpreter runs on every update:
>>> med.drug_class == allergy.drug_class
True   # CRITICAL alert surfaced before the user asks anything`

const fade = {
  hidden: { opacity: 0, y: 16 },
  show: (i = 0) => ({ opacity: 1, y: 0, transition: { delay: 0.06 * i, duration: 0.5 } }),
}

export default function Hero() {
  return (
    <section id="overview" className="relative overflow-hidden pt-28 pb-16 sm:pt-36">
      {/* animated grid backdrop */}
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.25]"
        style={{
          backgroundImage:
            'linear-gradient(to right, rgba(148,163,184,0.08) 1px, transparent 1px), linear-gradient(to bottom, rgba(148,163,184,0.08) 1px, transparent 1px)',
          backgroundSize: '44px 44px',
          maskImage: 'radial-gradient(60% 60% at 50% 30%, black, transparent)',
        }}
      />
      <div className="container-page relative grid items-center gap-12 lg:grid-cols-[1.05fr_0.95fr]">
        <div>
          <motion.div variants={fade} initial="hidden" animate="show" custom={0}>
            <span className="chip border-brand-400/30 bg-brand-400/10 text-brand-200">
              <span className="h-1.5 w-1.5 rounded-full bg-brand-300" />
              Paper companion · Pine AI
            </span>
          </motion.div>

          <motion.h1
            variants={fade}
            initial="hidden"
            animate="show"
            custom={1}
            className="mt-5 text-balance text-4xl font-extrabold leading-[1.05] tracking-tight text-white sm:text-5xl lg:text-6xl"
          >
            User as Code
            <span className="mt-2 block bg-gradient-to-r from-brand-300 via-brand-200 to-accent-300 bg-clip-text text-transparent">
              Executable memory for personalized agents
            </span>
          </motion.h1>

          <motion.p
            variants={fade}
            initial="hidden"
            animate="show"
            custom={2}
            className="mt-6 max-w-xl text-pretty text-base leading-relaxed text-slate-300 sm:text-lg"
          >
            Instead of a “bag of facts,” UaC models a user as a version-controlled software
            project of <span className="font-semibold text-slate-100">typed Python dataclasses</span> and{' '}
            <span className="font-semibold text-slate-100">executable constraints</span>. A two-phase
            pipeline — append-only extraction, then periodic structuring into code — lets an interpreter
            answer, aggregate, and <em>proactively alert</em>, deterministically.
          </motion.p>

          <motion.div
            variants={fade}
            initial="hidden"
            animate="show"
            custom={3}
            className="mt-8 flex flex-wrap gap-3"
          >
            <a href="#explorer" className="btn bg-gradient-to-r from-brand-400 to-accent-400 text-ink-950 hover:opacity-90">
              Explore every test case
              <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor"><path d="M7 5l6 5-6 5V5z" /></svg>
            </a>
            <a href="#mechanism" className="btn border border-white/10 bg-white/5 text-slate-200 hover:bg-white/10">
              How it works
            </a>
            <a href={`${import.meta.env.BASE_URL}paper.pdf`} target="_blank" rel="noreferrer" className="btn border border-white/10 bg-white/5 text-slate-200 hover:bg-white/10">
              <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor"><path d="M4 2h7l5 5v11a1 1 0 01-1 1H4a1 1 0 01-1-1V3a1 1 0 011-1zm7 1.5V7h3.5L11 3.5z" /></svg>
              Read the paper
            </a>
          </motion.div>

          <motion.div
            variants={fade}
            initial="hidden"
            animate="show"
            custom={4}
            className="mt-10 grid grid-cols-2 gap-3 sm:grid-cols-4"
          >
            <StatPill value="78.8%" label="LOCOMO (600 QAs)" />
            <StatPill value="83.0%" label="LongMemEval (500)" accent="accent" />
            <StatPill value="99%" label="Analytical inference" accent="ok" />
            <StatPill value="100%" label="Active-Service alerts" />
          </motion.div>
        </div>

        <motion.div
          variants={fade}
          initial="hidden"
          animate="show"
          custom={3}
          className="relative"
        >
          <div className="absolute -inset-4 -z-10 rounded-3xl bg-gradient-to-br from-brand-500/20 to-accent-500/20 blur-2xl" />
          <CodeBlock code={HERO_CODE} caption="cross-session drug-allergy check" />
          <div className="mt-3 flex items-center gap-2 text-xs text-slate-500">
            <span className="h-1.5 w-1.5 rounded-full bg-ok" />
            The two utterances never co-occur in any retrieval window — only the typed schema joins them.
          </div>
        </motion.div>
      </div>

      <div className="container-page relative mt-16">
        <div className="card flex flex-wrap items-center justify-center gap-x-8 gap-y-2 px-6 py-4 text-center text-sm text-slate-400">
          <span>Evaluated against <strong className="text-slate-200">5 memory systems</strong> + a full-context upper bound on one shared Gemini&nbsp;3&nbsp;Flash backbone</span>
          <span className="hidden h-4 w-px bg-white/10 sm:block" />
          <span>Mem0 · A-MEM · MemMachine · EverMemOS · Hindsight · Full&nbsp;Context</span>
          <span className="hidden h-4 w-px bg-white/10 sm:block" />
          <span>Cross-judged under <strong className="text-slate-200">Claude Opus 4.7</strong> (κ ≥ 0.74)</span>
        </div>
      </div>
    </section>
  )
}
