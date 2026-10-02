"""Fill REPORT_TEMPLATE.md: {{T:key}} from tables.json, {{X:key}} from xtext.md (sections '@@ key' ... ).
Writes CURRENT_CLARITY_STAGE11_REFLECTANCE_AND_SENSOR_AUDIT.md next to the template; fails on any unfilled key."""
import json, re, sys
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + "/stage11"
T = json.load(open(f"{S}/analysis/tables.json"))
X, cur = {}, None
for ln in open(f"{S}/analysis/xtext.md", encoding="utf-8").read().split("\n"):
    m = re.match(r"^@@ (\w+)\s*$", ln)
    if m: cur = m.group(1); X[cur] = []; continue
    if cur: X[cur].append(ln)
X = {k: "\n".join(v).strip("\n") for k, v in X.items()}
s = open(f"{S}/REPORT_TEMPLATE.md", encoding="utf-8").read()
s = re.sub(r"\{\{T:(\w+)\}\}", lambda m: T[m.group(1)], s)
s = re.sub(r"\{\{X:(\w+)\}\}", lambda m: X[m.group(1)], s)
left = re.findall(r"\{\{[TX]:\w+\}\}", s)
if left: sys.exit(f"unfilled: {left}")
open(f"{S}/CURRENT_CLARITY_STAGE11_REFLECTANCE_AND_SENSOR_AUDIT.md", "w", encoding="utf-8").write(s)
print("ok", len(s))
