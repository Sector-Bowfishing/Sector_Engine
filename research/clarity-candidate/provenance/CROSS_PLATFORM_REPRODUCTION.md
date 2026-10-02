# Cross-platform reproduction (2026-10-02)

**The reference environment is macOS arm64.** That is where the candidate was frozen, and where a freshly bootstrapped
environment reproduces every frozen output **bit for bit** (`GOLDEN_RESULT_macos.json`).

**On Linux x86-64**, the shadow job's Cloud Run image (`python:3.12.8-slim-bookworm`, the same pinned wheels, ACOLITE
f73cbe7, identical LUTs) passes `env/verify_env.py`. Its self-checks were run on 17 Cloud Run tasks (6 AMD, 11 Intel hosts) and 5
diagnostic tasks:

| Check | AMD EPYC 7B13 (AVX2) | Intel Xeon (AVX-512) |
|---|---|---|
| Environment, LUT and research hashes | identical | identical |
| Challenger port on 1,582 frozen fixtures | identical | identical |
| ACOLITE golden scene(s) | **identical** on 5 of 6 hosts; one host 4.7e-10 | max \|Δ\| 9.3e-10 (one float32 ulp); six scenes 1.9e-9 |
| engine14 on 1,574 certification rows | 11 rows differ, only `p`/`feet`, max relative 5.5e-16 | 100 rows differ, only `p`/`feet`, max relative 1.6e-15 |
| engine16 on 108 fresh rows | identical | 9 rows differ, only `p`/`feet_shown`, max relative 2.2e-16 |
| **Decisions** (tier, state, authority, display, hard class, evidence, algal, S2C) | **0 differences** | **0 differences** |

**Why it differs:** floating-point arithmetic, not method.
- The tier-3 prediction is `np.dot`: Accelerate on macOS, OpenBLAS on Linux.
- The gradient-boosted model sums leaf values in compiled code.
- NumPy picks SIMD kernels per CPU.

Bit-exact agreement between macOS arm64 and Linux x86-64 is not reachable for this frozen code.

**Consequence.**
- The shadow job fails closed on Linux: it writes nothing when any frozen output differs, and that is the rule
  Michael set.
- Running it in the cloud needs his decision on one of two things:
  1. **A declared tolerance.** Every decision identical; numeric fields within 1e-12 relative; ACOLITE within 1e-8
     reflectance. This would be recorded as an addendum before use.
  2. **An exact host.** Run on macOS arm64, where it is exact.
