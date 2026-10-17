# MH3U on Cemu: memory research notes

Notes from 2026-10-17. They cover how monster position and area were found in Monster Hunter 3 Ultimate running on Cemu, what this fork changes in the HP overlay, and what is still open.

## Setup this was found on

| | |
|---|---|
| Game | Monster Hunter 3 Ultimate, US, title `00050000-10118300`, update v32 |
| Game code module | `mh3g_cafe_us`, checksum `0x9d2f15e5` (a Cemu patch must match this) |
| Emulator | Cemu 2.6, Windows |
| Overlay | MH3U-MH3G-HP-Overlay v1.0.1 (this repo, branch `area-tracking`) |

## How addresses work

- Cemu reserves one memory region of size `0x4E000000` for the console's memory. The overlay finds it by that size (`scanmodule.get_regions`).
- The start of that region is Wii U address `0x02000000`. To convert:
  - `host = region_start + (wiiu_address - 0x02000000)`
  - `wiiu_address = host - region_start + 0x02000000`
- Pointers stored inside game memory are Wii U addresses, so convert them before following.
- All game values are big-endian.
- Game code starts at Wii U `0x02000000`. Fixed global data is around `0x10000000`. Objects such as monsters and the hunter live around `0x2F000000`.

## Monster data

The overlay finds each monster by the byte pattern `3C F5 C2 8F` followed by 12 zero bytes. The HP field sits `0x8A` after the match. Every offset below is relative to that HP field.

| Offset | Type | Meaning |
|---|---|---|
| `+0x000` | u16 | HP |
| `+0x004` | u16 | max HP |
| `+0x148` | u16 | `03 E8` while the monster is active |
| `-0x8B7` | u16, read little-endian | monster ID (see `Monsters` in `modules/mh3u_mh3g.py`) |
| `-0x816` | f32 | size multiplier |
| `-0x87A` | f32 ×3 | position x, y, z (y is up) |
| `-0x86A` | f32 ×3 | previous-frame position |
| `-0x83A` | f32 ×3 | spawn or home point |
| `+0x527` | u8 | the monster's area (game's internal number) |
| `+0x526` | u8 | the hunter's current area, as tracked by this monster (confirmed: follows every hunter area change) |

Behaviour observed:

- **Changing area:** when a large monster changes area, it flies up to y ≈ 10000 and waits there. `+0x527` switches to the destination area the moment it takes off.
- **Walking monsters** (e.g. Barroth) never rise; their position jumps straight into the new area's coordinates and `+0x527` switches at the same moment. Only flyers get the `→` marker.
- **Small monsters:** they exist only in the hunter's current area. Their entries are reused per area, and while an area loads they briefly hold junk: odd IDs (27, 33, 37, 16128), max HP 0, and position (0,0,0) or NaN. Filter those out.
- **Coordinates:** each area has its own coordinate space. A monster's position only means something relative to the hunter when both are in the same area.

The monster object starts `0x16EA` before HP. A fixed pointer table near Wii U `0x10547EC0` points to monster objects.

## Hunter data

| Where | Meaning |
|---|---|
| Wii U `0x10547BF0` | Pointer to the hunter object. It is **0 in the hub**, so fall back to searching memory. |
| object `+0x00` | Class identifier `0x1007F1A0`. Only one object in memory has it. |
| object `+0x40` | f32 ×3: position x, y, z |
| object `+0x50` | f32 ×3: rotation matrix row. Its x and z components give the facing direction. |
| object `+0xE95` | u8: location ID (which map) |
| object `+0xE96` | u8: the hunter's area (game's internal number). `+0xE97` usually holds the same value. |

Location IDs seen: Flooded Forest `3`, Misty Peaks `12`, Deserted Island `15`, Sandy Plains `16`, hub `26`.

## Game area numbers vs the in-game map

The game's internal area number is not always the number shown on the map. Translation tables (game → map), filled in by walking each area. These are also in `research/area_map.json`.

**Flooded Forest (location 3)**

| Game | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|
| Map | 1 | 3 | 4\* | 5 | 2 | 8 | 7 | 6 | 9 | 10 |

**Misty Peaks (location 12):** game number = map number for 1–9.

**Deserted Island (location 15)**

| Game | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Map | 1 | 3 | 2 | 7 | 5 | 9 | 11 | 12 | 6 | 8\* | 4 | 10 |

Map 11 and 12 are the underwater areas.

**Sandy Plains (location 16)**

| Game | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Map | 1 | 2 | 3 | 4 | 5 | 8 | 9 | 10 | 7 | 11 | 6 |

\* Deduced as the only remaining number, not visited.

Not mapped yet: Tundra, Volcano and any other maps.

## What this fork changes in the overlay

`modules/mh3u_mh3g.py`:

- **Monster data:** large monster results now also carry the area label (a string) and an `is_flying` flag (true when y > 800).
- **`get_location`:** finds the hunter's location ID through the pointer at `0x10547BF0`. When that pointer is empty, it uses the hunter object found while scanning the memory chunks the overlay already reads (`find_hunter_in_chunk`).
- **`area_label`:** translates a game area number through `AREA_LABELS[location]`. Locations without a table show the raw game number with a `?`.

`overlay.py`:

- Large monster lines end with ` | Area N`, or ` | → Area N` while the monster is flying to it.

Small monsters and the overlay's layout are unchanged.

### How the installed copy was patched (without rebuilding the exe)

The released overlay is a packaged Python 3.12 app (cx_Freeze). Its code is compiled `.pyc` files inside `lib\library.zip`:

1. Confirm the v1.0.1 source compiles to code identical to the bundled `.pyc` files. It did, for both files.
2. Compile the modified `overlay.py` → `__main__mh3u_mh3g_hp_overlay.pyc` and `modules/mh3u_mh3g.py` → `modules/mh3u_mh3g.pyc` with Python **3.12**. The standalone embeddable 3.12.7 works; no install is needed.
3. Rebuild `library.zip` from the original with those two entries replaced.
4. Stop the overlay, replace `lib\library.zip`, start it again.

The original archive is kept as `lib\library.zip.orig` in the installed overlay folder. To revert, rename it back to `library.zip`.

## Research scripts (`research/`)

They only read memory; none of them write to the game. Run them with Python 3.13 or later while Cemu is running the game.

| Script | What it does |
|---|---|
| `mh3u_mem.py` | Shared reader: finds Cemu and the memory region, converts addresses, finds monsters and the hunter. |
| `names.py` | Monster ID → name tables, taken from the overlay. |
| `myarea.py` | Prints the hunter's area and location ID, and the area the small monsters report. |
| `areaid.py` | Small always-on-top window showing the game's area number live. |
| `radar.py` | Top-down radar: centered on the hunter with a facing arrow, monsters in other areas listed by area. |
| `huntercheck.py` | The "stand still / walk" memory comparison used to find the hunter's position. |
| `poslog.py`, `analyze.py` | 2-minute position logger and its summary. |
| `ppcdis.py` | Disassembles game code from live memory (`pip install capstone`). |
| `area_map.json` | The area translation tables. |

## Open: 2.5× damage multiplier (for playing scaled quests solo)

Goal: multiply the hunter's damage by 2.5 as a Cemu patch tied to module checksum `0x9d2f15e5`, which can be switched on or off in Cemu.

Done so far:

- Game code reaches monster HP through a smaller block inside the monster object, at offset `0x8A`.
- All 16-bit stores to `0x8A` in the game code were disassembled. None of them is the hit-damage path:
  - `0x02b112ec`: changes HP by ±1 at a time, like regeneration.
  - `0x02b18ccc`, `0x02b18d44`, `0x02b18d64`: recompute HP proportionally.
  - `0x02b1924c`: saves HP and restores the same value.
  - `0x02d3df2c`, `0x02d3df5c`: a different structure that happens to use the same offset.
  - `0x02a2a398`: a stack variable.

Next step: in Cemu, open **Debug → View PPC debugger → Breakpoints → Create memory breakpoint (write)** on a monster's HP address (the 4-byte-aligned address). Hit the monster once. The instruction that wrote HP leads back to where damage is calculated.

Fallback idea: per-monster "damage taken" multipliers in the quest data, which would be a data change instead of a code patch. Not located yet.

## Open items

- Confirm Flooded Forest game 3 → map 4.
- Map the remaining locations.
- Damage multiplier, as above.
