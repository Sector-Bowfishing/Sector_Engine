"""Fill REPORT13_TEMPLATE.md from tables13.json and xtext13.md (nested {{T:}} inside X text resolved too)."""
import json, re, sys
D = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + "/stage13"
T = json.load(open(f"{D}/analysis/tables13.json")); X, cur = {}, None
for ln in open(f"{D}/analysis/xtext13.md", encoding="utf-8").read().split("\n"):
    m = re.match(r"^@@ (\w+)\s*$", ln)
    if m: cur = m.group(1); X[cur] = []; continue
    if cur: X[cur].append(ln)
X = {k: "\n".join(v).strip("\n") for k, v in X.items()}
s = open(f"{D}/REPORT13_TEMPLATE.md", encoding="utf-8").read()
for _ in range(2):
    s = re.sub(r"\{\{X:(\w+)\}\}", lambda m: X[m.group(1)], s)
    s = re.sub(r"\{\{T:(\w+)\}\}", lambda m: T[m.group(1)], s)
left = re.findall(r"\{\{[A-Z0-9_:a-z]+\}\}", s)
if left: sys.exit(f"unfilled: {left}")
open(f"{D}/CURRENT_CLARITY_STAGE13_LOW_VISIBILITY_ENGINE.md", "w", encoding="utf-8").write(s); print("ok", len(s))
