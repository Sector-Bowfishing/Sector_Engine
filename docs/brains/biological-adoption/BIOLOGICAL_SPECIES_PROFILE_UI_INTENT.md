# Species study guide: UX intent for Sector Ops (Biological-owned; Ops owns the design)

Open **Biological, then a fish**. The page should answer, without another Claude session: how does this fish move from January to December, when is it shallow, when does it spawn, what temperature matters, what rising and falling water do, where to look at night, what habitat it uses, how strong the evidence is, whether it applies to the Southeast, whether it has been reviewed or field-validated, and what is missing that would help a bowfisher.

Suggested hierarchy (all fields come from one profile payload):
1. **Header**: sector label, scientific name, role (Target / Secondary / Knowledge only), knowledge diagnostics (Species-v2, Bowfisher Knowledge), **General confidence** and **Southeast confidence** side by side, review badge, field-validation badge.
2. **Yearly movement**: a 12-cell track. Colour by `shallowLikelihood`; mark `precision` visibly (solid = MONTH, hatched = SEASONAL estimate, faint = INFERRED, empty = UNKNOWN). Click a month for movement states, favored habitat, temperature/water-level/night context, the bowfisher meaning, and its claims. Show condition modifiers underneath as chips (rising water, cold, night, turbid), flagging any that do not fire for lack of a season.
3. **How to find this fish**: Spring / Summer / Fall / Winter / Night / Best shallow window, in the plain sentences the profile supplies.
4. **Knowledge areas**: Spawn, Temperature, Depth, Water level, Vegetation, Clarity, Day/Night, Current, each with coverage chip, statements, and the *open questions* in a muted "we don't know" list.
5. **What Sector knows well / What Sector is missing**: strongest and weakest areas; for each gap show the priority and the "if we learn this" sentence. Show `RESEARCH_NOT_AUTHORIZED` as plain text; the page never starts research.
6. **Rules**: WHEN / SECTOR EXPECTS / BOWFISHER MEANING with status, review and field badges; sort rules awaiting review first.
7. **Evidence**: counts and strongest source up front; drill-down to the claim and its sources. Never load every citation on the first screen.
8. **Review / field validation**: counts and last observation. Keep these visually separate from the knowledge areas.

Separate tab: **Current outlook** (per lake) with a **Why?** control that opens the trace: current inputs, matched knowledge, season check (e.g. "October: outside spawn window: spawn rule not applicable"), result.
**Fleet overview**: the coverage matrix (targets first) so weak areas across all fish are visible at once.
