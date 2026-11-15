# fivem-whip: a Claude skill for the WHIP FiveM framework

WHIP (whipfx.net, github.com/WHIPFX) is a FiveM framework released in November 2026. It replaces QBCore, Qbox,
ESX and ox_core. This skill gives Claude the framework's complete API surface and its rules, so it can:

- **port** QBCore, Qbox, ESX and ox scripts to WHIP, fully integrated (world prompts, bank and business
  accounts, `/whip` admin pages, the Monitor, the activity log, phone apps, Director cards), not translated
  call for call;
- **build** new WHIP resources;
- **review and debug** WHIP resources, and install and run WHIP servers.

## Install

```bash
git clone https://github.com/fozenistaken/whip-skill ~/.claude/skills/fivem-whip
```

Or copy this folder so that `~/.claude/skills/fivem-whip/SKILL.md` exists. Then restart Claude Code. The scripts
need Python 3.9+ (standard library only).

Not affiliated with WHIP or WHIPFX. MIT licence (see `LICENSE`).

## Inside

```
SKILL.md                         entry point (short): never-invent rules, core rules, workflows, reference map
AGENTS.md                        setup for Codex, Cursor and other agents (points to SKILL.md)
references/
  export-index.md                all 580 whip_core exports (generated from whip_core/types)
  whip-names.json                every real export, helper, event and option key (generated; used by the scanner)
  sources.md                     official links, every repo pinned to its commit, how to check a citation
  core-concepts.md               ids, Whip.register, return values, registration rule, satellite helper, examples
  porting-to-whip.md             QBCore / Qbox / ESX / ox mapping tables, rewrites, procedure, checklist
  porting-playbooks.md           per script type (shops, jobs, police, EMS, housing, heists, ...) + worked case
  server-setup.md                field-tested server setup: scan, ask, set up; both routes; troubleshooting
  integration.md                 every WHIP surface a resource should plug into, integration review
  security.md                    SecureEvent / SecureCallback, Sentinel, permissions
  players-stats-hud.md           player sheet, lifecycle, stats, HUD, death, escort
  money-banks.md                 ChargePlayer / PayPlayer, receipts, bank accounts, ATMs
  inventory-items.md             items, use handlers, inventory exports
  stores-containers-panels.md    store addresses, StoreMove, containers, store kinds, panels
  vehicles-garages.md            vehicles, keys, vehicle data and stats, garages
  jobs-shops-properties-doors.md jobs, shops, properties, doors
  interactions.md                AddAction prompts, wheel, car parts, points
  world-zones-time-npcs.md       zones, time/weather, NPCs, blips
  ui-nui-camera.md               UI library, screens, controller, camera, theming, own NUI, DUI
  server-ops-devtools.md         config.lua, settings pages, dev tools, commands, setup report
  events-and-data.md             every event and data structure, state bags
  director.md                    the Director: cards, tasks, scenarios
  gunny-weapons.md, rope.md, autos-fuel-dealership.md, voice.md, phone-chat-loadingscreen.md,
  install-packs-testing.md       the WHIP satellite resources, install and packs
scripts/
  whip_scan.py                   port finder (--mode port, --plan) and WHIP-way reviewer (--mode review);
                                 flags invented exports, events and option keys (W070-W072)
  whip_names.py                  regenerates references/whip-names.json from whip_core
  whip_host.py                   server setup step 1 (scan the machine) and install check
  install_whip.py                install WHIP without txAdmin from the live recipe (--create-db, --game enhanced)
  export_index.py                regenerates export-index.md from whip_core/types
  selftest/                      fixtures + run.py for whip_scan.py
assets/
  whip-resource-template/        starter resource
  examples/                      WHIP's MIT example resources (cafe, delivery)
  luarc.template.json            LuaLS config for WHIP's types
evals/evals.json                 test prompts
```

## Scanner

```bash
python -I scripts/whip_scan.py path/to/resource --plan              # port plan grouped by WHIP surface
python -I scripts/whip_scan.py path/to/resource --mode port         # every foreign-framework call, with the WHIP replacement
python -I scripts/whip_scan.py path/to/resource                     # review a WHIP resource (exit 1 on HIGH)
python -I scripts/whip_scan.py --selfcheck references/export-index.md
python -I scripts/selftest/run.py
```

## Sources and currency

Built from https://whipfx.net/docs/ and every https://github.com/WHIPFX repository as of 2026-11-15 (whip_core
commit `d12235f`), with facts checked against the source code. `references/sources.md` links every repository at
the exact commit used, explains how to open any `repo/path:line` citation on GitHub, and lists every docs anchor. Where docs and code differ, the references say so ("Docs vs code").
WHIP's code is LGPL-3.0. The example resources under `assets/examples` are MIT and unchanged. The starter
template is original. Regenerate `export-index.md` after a WHIP update.
