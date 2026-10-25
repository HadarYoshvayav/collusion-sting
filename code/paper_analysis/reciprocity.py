"""Reciprocity control: undercover keeps its offers (main run) vs does not (free run). Game-level."""
import json, glob, random
rng = random.Random(0)
def load(d): return [json.load(open(f)) for f in sorted(glob.glob(f"{d}/sting_records/*.json"))]
import sys
MAIN = load("/home/claude/data/llama_main")
FREE = load(sys.argv[1] if len(sys.argv) > 1 else "/home/claude/data/llama_free")
def mean(x): x=[v for v in x if v is not None]; return sum(x)/len(x) if x else float('nan')
def ci(x,n=5000):
    x=[v for v in x if v is not None]; b=sorted(mean([x[rng.randrange(len(x))] for _ in x]) for _ in range(n)); return round(b[int(.025*n)],2), round(b[int(.975*n)-1],2)
def perm(a,b,n=20000):
    a=[v for v in a if v is not None]; b=[v for v in b if v is not None]; o=mean(a)-mean(b); pool=a+b; k=0
    for _ in range(n):
        rng.shuffle(pool); k += abs(mean(pool[:len(a)])-mean(pool[len(a):]))>=abs(o)-1e-12
    return round(o,2), round((k+1)/(n+1),4)
def signflip(d,n=20000):
    d=[v for v in d if v is not None]; o=mean(d); k=0
    for _ in range(n): k += abs(mean([v if rng.random()<.5 else -v for v in d]))>=abs(o)-1e-12
    return round((k+1)/(n+1),4)
def r(g,f):
    v=[c["was_challenged"] for c in g["challenges"] if c["phase"]=="post" and f(c)]; return sum(v)/len(v) if v else None
UC=lambda c: c["challenged_is_undercover"]
OT=lambda c: not c["challenged_is_undercover"] and not c["challenger_is_undercover"]
BY=lambda c: c["challenger_is_undercover"]
def row(gs):
    uc=[r(g,UC) for g in gs]; ot=[r(g,OT) for g in gs]; by=[r(g,BY) for g in gs]
    gap=[(o-u) if (o is not None and u is not None) else None for u,o in zip(uc,ot)]
    return uc,ot,by,gap
none_uc = row([g for g in MAIN if g["condition"]=="none"])[0]
print(f"baseline none (main): vsUC={mean(none_uc):.2f} {ci(none_uc)}")
for c in ["direct","assigned"]:
    K=row([g for g in MAIN if g["condition"]==c]); F=row([g for g in FREE if g["condition"]==c])
    print(f"\n== {c}")
    for name,(uc,ot,by,gap) in [("keep",K),("new",F)]:
        print(f" {name}: games={len(uc)} withUC={sum(v is not None for v in uc)} vsUC={mean(uc):.2f} {ci(uc)} vsOthers={mean(ot):.2f} {ci(ot)} "
              f"gap={mean(gap):+.2f} {ci(gap)} p_gap={signflip(gap)} | UC's own rate={mean(by):.2f} {ci(by)}")
    print(f" UC own rate free-keep: {perm(F[2],K[2])}  (manipulation check)")
    print(f" targets vsUC free-keep: {perm(F[0],K[0])}")
    print(f" targets vsUC free vs NONE baseline: {perm(F[0],none_uc)}")
    print(f" gap free-keep: {perm(F[3],K[3])}")
    print(" decisions:", sorted({o['decision'] for g in FREE if g['condition']==c for o in g['offers']}),
          "n targets", sum(len(g['offers']) for g in FREE if g['condition']==c))
