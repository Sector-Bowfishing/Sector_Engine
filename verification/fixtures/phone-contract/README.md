# Phone-contract goldens (Sector_Ops #53, Step 0)

Real `GET /conditions` responses from production, used to prove that released apps keep working through the
conditions consolidation. The contract is `contracts/phone/conditions-phone-contract-v1.json`. It lists what iOS
4.1.0 build 28 (tag `v4.1.0-28`) decodes. That build decodes strictly, so one missing key, wrong type or
fractional-second date fails the whole response and blanks every tile.

- `points-v1.json`: the 17 fixed points (15 directory lakes covering TVA, SWPA, Alabama Power, CWMS, west and north, plus
  one off-directory river point and one coastal point).
- `<date>/<slug>.json`: one capture. Free text (reasons, prose, alert text, gauge names, the spawn species name) is
  replaced with `"<redacted>"`, which keeps the type. This repository is public and must not carry per-lake species
  presence. The unredacted bodies are kept privately in `Sector Research/shared/conditions-golden/<date>/`.

Checks:
- `Tests/SectorEngineTests/PhoneContractTests.swift` (CI `swift test`): every golden meets the contract. Every golden
  also survives a decode into the Engine's `ConditionsResponse` and a re-encode with the server's encoder, with every
  contract value unchanged.
- `verification/test_phone_contract.py` (CI foundation job): the same validator in Python, against the same files.

Capture again (it changes nothing, it only reads):

    python3 tools/conditions_golden/capture.py capture --raw-dir "<Sector Research>/shared/conditions-golden/<date>"

Check production live against the contract (also the per-tile watch's contract probe):

    python3 tools/conditions_golden/capture.py check --live

The contract changes only by adding fields, or by a new version once no released build still needs the old one
(request logs by app version, rule 5 on #53).
