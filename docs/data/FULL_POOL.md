# Full pool per lake

`full_pool.csv` gives each lake in the directory its **normal full pool**. The
generator (`scripts/generate-lake-directory.py`) writes it into every
`DirectoryLake`, and `GET /lakes` serves it to both apps. The engine compares
it with the live pool: above full pool, water is into the flood pool and the
shoreline brush is wet; below it, the lake is drawn down. Compiled 2026-09-26.

## What "full pool" means here

It is the level the operator fills to and holds in normal operations: for a
seasonal lake, the **normal summer pool**; for a lake held in a band, the top
of that band. It is never top of dam, top of gates, top of the flood pool,
maximum water surface or pool of record.

Some kinds of lake need a specific rule:

| Kind of lake | Full pool is |
|---|---|
| TVA mainstem | top of the summer operating zone (Guntersville 595) |
| TVA tributary | the June fill target, i.e. the top of the guide curve (Fontana 1703) |
| Corps multipurpose | top of conservation or normal pool in summer. The Mobile District's winter drawdown lakes use the summer maximum (Allatoona 840). The Little Rock District's seasonal raises use the base pool (Table Rock 915). Flood-control lakes on a guide curve use the top of that curve (Grenada 215). |
| Missouri mainstem (Fort Peck, Sakakawea, Oahe) | base of flood control, which the Corps uses for the full-reservoir shoreline |
| USBR | top of active conservation, or top of joint use where flood space is shared |
| Florida regulated lakes | the high of the regulation schedule |

## The datum rule

A full pool is only useful in the datum its lake's level is read in.

- **TVA and CWMS lakes:** the value is TVA's or the Corps' own figure, from the
  same system as the pool reading the engine gets.
- **Utilities on a local datum:** the utility's number, with the conversion in
  `note`. Examples: Ameren's Union Electric Datum, NIPSCO, Yadkin/Alcoa, Seattle
  City Light, MWRA and Pensacola.
- **Duke Energy:** MSL (NGVD29). Duke publishes it alongside its "100 = full
  pond" scale.

## Columns

- `basis`
  - `fullPool`: a managed reservoir.
  - `naturalSurface`: an unregulated lake's usual surface, a reference only.
    The engine never calls a natural lake flooded or drawn down.
- `conf`
  - `high`: the operator's or an agency's own figure with that meaning.
  - `med`: a secondary source, or an operator figure of unclear meaning.
  - `low`: unverified.

  Only `high` and `med` may produce a flooded or drawn-down statement.
- An empty `fullPoolFt` means the research found no figure. Nothing is kept,
  not even the sheet's value.
- `winterPoolFt`: where the source gives one. It is recorded for later use and
  the generator does not use it yet.

## Where the numbers came from

- **134 lakes:** TVA's operating guide (`/RestApi/operating-guide/{id}`) and
  CWMS location levels.
- **22 Northwestern Division lakes:** CWMS office `NWDM` or `NWDP`, not the
  district codes, which return nothing.
- **About 270 lakes:** researched one by one from operator pages (USBR, utility
  lake-level pages, FERC notices, state agencies, TWDB, USGS water-data reports).
  Each row's `source` is the page the number came from.
- **Natural lakes:** the sheet's natural-surface value, unverified.

## What the research found in the old sheet

The Aug 6 sheet's "Full Pool (ft)" column had 152 lakes off by more than half a
foot, including several marked "High":

- Several were top of gates: Guntersville 595.44, Fontana 1710, Douglas 1002.
- Some were the flood pool or maximum: Lake Mead 1229, Canyon Ferry 3800,
  Herrington 760.
- Many were plain wrong: Monksville 745 vs 400, Hamilton 300 vs 400, Box Butte
  17 ft low, Eleven Mile 33 ft low.
- Sherman Reservoir was a copy of Cedar Bluff's value.

## Refreshing

Operators do change these numbers:

- the 2020 Chatfield reallocation;
- the 2012 Pathfinder spillway;
- LCRA dropping Buchanan's seasonal pool in 2025;
- Anderson Ranch's planned 6-ft raise, around 2027.

Edit the row, keep `source` and `note` honest, and regenerate.
