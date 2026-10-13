# Bowfisher trip log: what a tester writes down

The point is **shootable fish per hour in the places the Brain favoured vs the places it did not**, including the hours with nothing. It takes about a minute per stop. Nothing here needs a biology degree; an observation is **one spot (zone) on one trip**.

## One line per spot you fished
| Question | Answer | Required? |
|---|---|---|
| Which lake, which night (date/time)? | `lakeId`, `observedAt` | yes |
| How long did you work this spot? | minutes (`effortMinutes`, 1-720) | **yes, even if you saw nothing** |
| What kind of spot? | backwater / creek or river mouth / tailwater / channel edge / flooded vegetation / shallow vegetation / wood / deep pool / open water (`zone`) | yes |
| What did you see? | **fish seen: yes/no** (`encountered`) and how many (`count`) | yes |
| How many could you actually shoot at? | `shootableCount` (0 is a real answer) | strongly asked |
| What fish? | the species and **how sure you are** (`CONFIRMED` / `LIKELY` / `GROUP_ONLY` e.g. "a gar", "a buffalo" / `UNCERTAIN`) | yes |
| Anything else you know | depth band, vegetation (none / submerged / emergent / flooded), water temp, water clarity, level rising/steady/falling, wind, "spawning behaviour seen?", a short note (≤ 280 characters) | optional |
| Who you are | a code the Engine team gives you (`observerId`): never a name, email or phone number | yes |
| Same outing | the same `tripId` for every spot on one night | yes |

## Rules that keep it honest
* **Log the empty spots.** A spot with no fish is data. Skipping them makes any rule look good.
* **"A gar" or "a buffalo" is fine.** Do not guess the species: buffalo and gar cannot be told apart reliably at night, so group-level answers are scored at group level.
* One night = one `tripId`. Ten fish at one spot are one observation, not ten.
* Nothing is edited afterwards: the store is append-only and hash-chained. If you made a mistake, send a corrected entry with a new id and a note.
* Predictions are logged **before** your trip. You will never be asked to adjust a prediction to match what you saw.

## Tooling (local, no cloud)
```
python3 tools/observations.py validate trips.json
python3 tools/observations.py append   store.jsonl trips.json     # all-or-nothing
python3 tools/observations.py summary  store.jsonl
python3 tools/observations.py evaluate predictions.jsonl store.jsonl   # descriptive only
```
Fields and allowed values: `schemas/observation.schema.json`. The evaluation reports shootable encounters per effort-hour for favoured vs other habitat classes and **never issues a verdict below 30 independent trips**; the success criterion must be preregistered before any outcome is examined (`BIOLOGICAL_VALIDATION_FLEET_DESIGN.md`).
