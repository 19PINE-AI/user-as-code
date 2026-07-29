#!/usr/bin/env python3
"""Item-level Wilson intervals and exact paired tests for paper results."""
from __future__ import annotations
import json, math
from pathlib import Path

R = Path(__file__).resolve().parent / "results"

def load(path):
    return json.loads((R / path).read_text(encoding="utf-8-sig"))

def rows(data):
    out = []
    for conv, values in data["details"].items():
        for value in values:
            out.append({"conversation": conv, **value})
    return out

def wilson(k, n, z=1.959963984540054):
    p = k / n; d = 1 + z*z/n
    c = (p + z*z/(2*n)) / d
    h = z * math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / d
    return c-h, c+h

def mcnemar(b, c):
    n = b + c
    if not n: return 1.0
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(min(b, c)+1)) / 2**n)

def holm(values):
    order = sorted(range(len(values)), key=values.__getitem__)
    adjusted = [0.0] * len(values); running = 0.0; m = len(values)
    for rank, index in enumerate(order):
        running = max(running, min(1.0, (m-rank) * values[index]))
        adjusted[index] = running
    return adjusted

def keyed_channel(path):
    return {(r["conversation"], int(r["qa_idx"])): bool(r["judge_correct"])
            for r in rows(load(path))}

def keyed_full(directory, system):
    return {r["qa_id"]: bool(r["judge_correct"])
            for r in rows(load(f"{directory}/{system}.json")) if int(r["category"]) != 5}

def show_interval(label, values):
    k, n = sum(values), len(values); lo, hi = wilson(k, n)
    print(f"{label}: {100*k/n:.1f}% (95% Wilson {100*lo:.1f}--{100*hi:.1f}; {k}/{n})")

def main():
    print("Intervals are over benchmark items, not independent model reruns.\n")
    for panel, directory in [("Luna", "full_locomo_gpt56_luna"),
                             ("Gemini", "full_locomo_gemini3_flash_preview")]:
        u = keyed_full(directory, "uac_v5")
        m = keyed_full(directory, "memmachine")
        show_interval(f"{panel} UaC judge", list(u.values()))
        b = sum(u[k] and not m[k] for k in u); c = sum(m[k] and not u[k] for k in u)
        print(f"{panel} UaC vs MemMachine: discordant {b}/{c}; exact two-sided McNemar p={mcnemar(b,c):.8g}")
    print()
    for system in ("full_context", "uac_v5", "memmachine"):
        values = [bool(x["judge_correct"]) for x in load(f"lme500_{system}.json")["by_question"].values()]
        show_interval(f"LongMemEval {system}", values)
    print()
    files = {"full":"locomo5_uac_v5.json", "no_state":"locomo5_uac_v5_ablate_no_state.json",
             "no_facts":"locomo5_uac_v5_ablate_no_facts.json", "no_archive":"locomo5_uac_v5_ablate_no_archive.json"}
    outcomes = {name:keyed_channel(path) for name,path in files.items()}
    for name, result in outcomes.items(): show_interval(f"Channel {name}", list(result.values()))
    raw=[]; discord=[]
    for name in ("no_state", "no_facts", "no_archive"):
        f, x = outcomes["full"], outcomes[name]
        b=sum(f[k] and not x[k] for k in f); c=sum(x[k] and not f[k] for k in f)
        discord.append((name,b,c)); raw.append(mcnemar(b,c))
    for (name,b,c),p,adj in zip(discord,raw,holm(raw)):
        print(f"Channel {name}: discordant {b}/{c}; exact two-sided McNemar p={p:.8g}; Holm p={adj:.8g}")
    print()
    for strategy in ("monolithic", "modular", "manifest"):
        values=[bool(x["correct"]) for x in load(f"modularity_{strategy}.json")["by_case"].values()]
        show_interval(f"Modularity {strategy}", values)

if __name__ == "__main__": main()
