"""Fill REPORT14_TEMPLATE.md from tables14.json, xtext14_dev.md and xtext14_cert.md; build the print copy."""
import json, re, sys
D = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + "/stage14"
T = json.load(open(f"{D}/analysis/tables14.json")); X = {}
for fn in ("xtext14_dev.md", "xtext14_cert.md"):
    cur = None
    for ln in open(f"{D}/analysis/{fn}", encoding="utf-8").read().split("\n"):
        m = re.match(r"^@@ (\w+)\s*$", ln)
        if m: cur = m.group(1); X[cur] = []; continue
        if cur: X[cur].append(ln)
X = {k: "\n".join(v).strip("\n") if isinstance(v, list) else v for k, v in X.items()}
s = open(f"{D}/REPORT14_TEMPLATE.md", encoding="utf-8").read()
for _ in range(2):
    s = re.sub(r"\{\{X:(\w+)\}\}", lambda m: X[m.group(1)], s)
    s = re.sub(r"\{\{T:(\w+)\}\}", lambda m: T[m.group(1)], s)
left = re.findall(r"\{\{[A-Za-z0-9_:]+\}\}", s)
if left: sys.exit(f"unfilled: {left}")
open(f"{D}/CURRENT_CLARITY_STAGE14_BLIND_CERTIFICATION.md", "w", encoding="utf-8").write(s)
head, sep, tail = s.rpartition("\n---\n")
tail = "\n\n".join(l for l in tail.strip().split("\n") if l.strip())
open(f"{D}/_print.md", "w", encoding="utf-8").write(head + sep + "\n" + tail + "\n"); print("ok", len(s))
