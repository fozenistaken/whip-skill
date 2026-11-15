# The Director

Covers the Director (in-game, no-code builder of missions, heists and stories from cards): concepts, the scenario document, start modes, every built-in card and task step with its fields, the server/client Director API (exports, events), custom cards, tasks, buttons, weapons and Object Viewer options, packs/templates, testing from scripts, Dungeon Mode and gotchas. Built from doc anchors `#director`, `#director-api`, `#director-items`, `#director-live`, `#director-runs`, `#director-cards`, `#director-tasks-buttons`, plus `whip_core/docs/director-architecture.md`, `whip_core/server/director/*.lua`, `shared/director/{kit,steps,things}.lua`, `client/director*.lua`, `types/director.lua`, `types/satellite.lua`, `types/server.lua`, `types/events.lua`, `lib/satellite.lua` (Director parts), `tools/ov_panel.lua`, `shared/weapon_catalog.lua`, `dev/director/*`. The card and step catalogue below was dumped from the live registries (98 cards, 54 steps) by loading the Director offline.

## Contents
- Concepts and vocabulary
- Permissions
- Architecture (where each concept lives)
- The scenario document (format 2)
- Settings keys and start modes
- Run lifecycle, limits and outcomes
- What a run hands out (items, money, tags)
- Built-in cards
- Built-in task steps
- Placed-thing kinds and field kinds
- Server exports: starting runs
- Server exports: reading runs and scenarios
- Server exports: steering runs
- Server exports: checking and testing
- Events (server and client)
- Custom cards: Whip.card
- The card object (WhipDirectorCard)
- Whip.answerCard, Whip.removeCard
- Custom tasks: Whip.task / Whip.removeTask
- Buttons and thing data: Whip.directorButton, GetDirectorThingData
- Weapons: Whip.weapons / Whip.removeWeapons
- Object Viewer options: Whip.objectViewerOption
- Packs, Whip.scenario, Whip.template, export
- Cards other WHIP resources add
- Dungeon Mode (live mode)
- In /whip, the editor, dev commands, DB tables
- Gotchas
- Docs vs code

## Concepts and vocabulary

| Term | Meaning |
|---|---|
| Scenario | A job/story: its placed things (World tab) and its cards (Blueprint), wired. Keyed by `key` (2-64 chars `[%w_-]`). Every revision is kept (`rev`, `draftRev`); the revision switched on never changes under its players. Edits made while on go live only when switched off and on. |
| Card | One step of a scenario (node). Leaves through one of its outcomes (output pins) along wires. Type ids are `'<namespace>.<name>'` (`flow.wait`, `police.notify`). |
| Wire | Link `from = {node, pin}` → `to = {node, pin}`. An outcome may have several wires: every card they lead to starts at the same moment, first-drawn first. |
| Run | One playing of a scenario revision for its players. Scripts see it as a `DirectorRunView` (a copy). Max 64 runs on the server at once (`DirectorRuntime.LIMITS.runs`). |
| Test | A builder's private run from the editor. Sends no public events, excluded from every export unless `{ tests = true }`, changes nothing that lasts. |
| Placed thing (thing, world) | An entry of the World tab: npc, vehicle, prop, spot, groundItem, container, door, route. Has `id`, `kind`, `layer`, `label`, `def`. |
| Layer | `'standing'` (Always present: made when the scenario is switched on, before any run; cars/containers/doors cannot be standing) or `'run'` (made by a run's cards). |
| Place | Where a placed thing is: its `def.coords`, or per-run override (`StartScenarioRun` `opts.places`, `card:place(id)`). `"coords": "spot"` in a shipped file = "place me" (left unplaced). |
| Variable | Scenario-declared `{ id, type, default }`, `type` `'number' | 'text' | 'bool'`; text at most 200 chars when set by script. |
| Lead-in | The part of a run before Scenario Started By Player (`scenario.begin`): nothing fails or counts; ends quietly as called off if it does not reach `scenario.begin` within 300 s (`LIMITS.preSec`). |
| Variant | Multi Run Variants: up to 8 versions of the job in one scenario (`doc.variants`), sharing settings, vars and shared things; a run plays one. |
| Template | A starting point in the editor's New list (`Whip.template`). |
| Pack | A resource shipping scenarios as data (`whip_director_scenario` manifest lines, or `Whip.scenario`). Accepted packs are read-only. |
| Live mode / Dungeon Mode | The world builder with no scenario: what a Dungeon Master makes goes straight into the live world until restart. |
| Lore character | A named NPC identity stories reuse (portrait, bank/pay name, voice lines). Lore exports and Phone Call / Lore Says belong to the voice reference. |

## Permissions

| Level | Permission | May |
|---|---|---|
| Builder | `director.build` | See every scenario; make, edit, test, switch on/off; restore a revision; stop a run; `/director` (opens editor) and `/director send` |
| Director admin | `director.admin` | All a builder may, plus delete scenarios, accept shipped packs, trust a pack resource, export packs, give/take Director access |
| Dungeon Master | `director.live` | Dungeon Mode only. Neither of the other two includes it, nor does it include them |
| Full admin | `whip.devtools` | All three, always, and the `/director <sub>` dev commands (also needs developer mode on: `DevTools.isAllowed`) |

Access is given per account in `/whip` → Director → Access (pick a character; every character on that account has it). Builders see through walls and the camera goes anywhere: trust them.

## Architecture (where each concept lives)

One registry per concept; a new card/step/field kind/thing kind is one entry, never edits spread across files (`dev/director/lint.lua` fails on unknown names).

| What | Where |
|---|---|
| Card types | `server/director/nodes.lua` (`DirectorNodes`) + `nodes_*.lua`, `guards.lua`, `lore.lua`, `lore_voice.lua`, `speakers.lua`; other resources' via `cards_api.lua` |
| Task steps | `shared/director/steps.lua` (`DirectorSteps`), both sides; other resources' via `satellite_api.lua` + `server/director/tasks.lua` + `client/director_tasks.lua` |
| Field kinds | `server/director/fields.lua` (`DirectorFields`), plus the `when` language (twin: `html/js/director/when.js`) |
| Placed things | `shared/director/things.lua` (`DirectorThings`); `dev/director/export_data.lua` regenerates `html/js/director/things-data.js`, `refs-data.js` |
| References/renames | `server/director/refs.lua`, `html/js/director/refs.js` |
| What a run hands out | `server/director/effects.lua` (`DirectorEffects`) |
| Conversations | `server/director/talk.lua` (`DirectorTalk`) |
| A run | `server/director/runtime.lua` (`DirectorRuntime`): one scheduler pass (`Every('director', ...)`), cards never run threads; anything that waits goes in `ctx:call` |
| Document reading | `server/director/doc.lua` (`DirectorDoc.load`: format, renames, `upgrade(props, fromV)`) |
| Check/compile | `server/director/graph.lua` (`DirectorGraph`) |
| Public API | `server/director/api.lua`, `main.lua` (`StartScenarioRun`, events), `cards_api.lua`, `satellite_api.lua`, `testing.lua`, `packs.lua` |
| Offline regression | `dev/director/golden.lua` (`lua54 golden.lua [--accept]`), `harness.lua` (real Director under a fake scheduler) |

Scheduler hard limits (`runtime.lua:23`): chain 500 cards without a real pause faults the run; burst 2000; 100 cards per run per pass; 1000 per pass; ~2 ms per pass; a run woken more than 100 times/s is a loop; trace 200.

## The scenario document (format 2)

`{ format = 2, key?, name, description?, settings = {...}, vars = { {id, type, default} }, world = { {id, kind, layer, label, def} }, nodes = { {id, type, v, x, y, props} }, links = { {id, from = {node, pin}, to = {node, pin}} }, comments, variants = { {id, name, nodes, links, world, comments} }, taskTimes = 2, requires? }`

- `format` must be `2` (`DirectorDoc.FORMAT`). Format 1 is refused ("made before the Director was rebuilt"). Shipped files: at most 512 KB.
- `taskTimes = 2`: a task time of 0 is no end and a give-up of 0 is never. A document without it has every task `sec`/`giveUp` ≤ 0 read as 0.1 s (old behaviour), then is marked 2.
- Ids: 1-64 chars `[%w_-]`. Unknown prop keys on a saved card are kept.
- Limits (Check refuses past them, `graph.lua:13`): 400 cards, 1200 wires, 1000 placed things, 200 variables, 8 variants.
- Each card stores its version `v`; a card whose `v` rose upgrades the saved props once at load (`upgrade(props, fromV)`).
- Renamed card types (`renamed` on a custom card) are applied at read time; nothing else reads an old shape.
- Check (`CheckDirectorScenario`) returns problems `{ severity = 'error'|'warning', node?, pin?, message, world?, nodes?, tab? }`. Errors block switching on; warnings do not.

## Settings keys and start modes

`doc.settings`:

| Key | Meaning |
|---|---|
| `start = { mode, world?, label?, icon?, radius?, every?, item?, consume? }` | How a run begins (below). `world` the placed thing; `label` prompt text (default `Talk`/`Use`); `radius` 1-500 m (area/timer); `every` 1-1440 minutes (timer); `item` an item key; `consume = true` (item used up) |
| `maxConcurrentRuns` | Runs at once (default 1). With variants: min(variant count, this) |
| `teamSize` | Players per run including starter, 1-16 (empty: 16 = `Director.MAX_CREW`) |
| `maxRunSec` | Run deadline seconds (default 3600; 0 = none) |
| `cooldownMin` | Per-character wait after a job, 0-10080 minutes |
| `cooldownWho` | `'everyone'` (default) or `'starter'` |
| `kinds` | "Kind" for scripts: comma text or list; lower-cased; at most 6 words, each ≤24 chars `[%w][%w -]*` |
| `where` | "Where it happens": a placed thing id (for scripts' `run.where`) |
| `scriptSwitch` | `true`: "Scripts may switch it on and off" (`SwitchScenario`) |
| `variantPick` / `variantOrder` | `'sequential'` (first free, default), `'random'`, `'order'` (in turn) |

Start modes (`settings.start.mode`; Scenario Enabled card's "It starts"):

| mode | How | `run:started` `startedBy.mode` |
|---|---|---|
| `enabled` | When it's switched on (default for a new scenario). One run at a time starts at once with nobody in it; Scenario Enabled's cards play and what they make is out for everyone. First player to talk (Dialog Line), press (Wait for Press, Interaction Menu) or come near (Player Arrives) joins and becomes starter (claim). After the run ends, a fresh one starts 2 s later (`REOPEN_MS`); a run that ended before anyone joined waits until switched off and on | `enabled` |
| `interaction` | Talk on a standing (Always present) NPC. While its runs are full others see "They're busy right now." | `interaction` |
| `press` | An E prompt with your label on a standing prop or a spot | `press` |
| `area` | Within `radius` of a placed thing. Once per visit (must leave and come back after a run). One turned away by full runs gets one as soon as a place frees | `area` |
| `item` | Using an item; kept unless `consume`. Item must be `usable` and have no other use handler; two scenarios can't share an item | `item` |
| `timer` | Every `every` minutes (first one that long after switching on): one run for every player near the thing | `timer` |
| `script` | `exports.whip_core:StartScenarioRun(key, who, opts)` | `script` (`by` = resource) |
| `admin` | By hand only (editor's Start a run, `/director start <key>`) | `hand` |
| `always` | Engine-internal (started by hand, never ended by players leaving) | - |

- The job begins at Scenario Started By Player (`scenario.begin`); before it, nothing fails or counts. With no such card it begins at the run's start (or, for `enabled`, as the first player joins).
- A player is never in two runs of the same scenario (checked in `Director.startRun` for every start).
- Eligibility (`Director.eligible`): on a character, not closing, not in the character creator, not dead/down, not in an Isolate world, not already in a run of this scenario.
- Test starts a run for the builder whatever the mode; anyone with Director access can press Start a run in `/whip`.

## Run lifecycle, limits and outcomes

- A run ends on Succeed, Fail, Call Off, a fault, an abort, the last player leaving, its deadline (`maxRunSec`), or having nothing left to wait for (event cards count as waiting; Fail Conditions do not).
- Activate After Failure / After Success chains get at most 120 s (`afterSec`) after the run's result.
- Public outcomes: `succeeded`, `failed`, `calledOff` (Call Off card, or a quiet abort), `aborted` (an admin, the last player leaving, whip_core stopping), `faulted` (runaway, a card error, an unwired custom Didn't Work).
- At the end: everything made under the run's tag (`run:<id>`) is released by every resource (blips, points, NPCs, cars, skill checks); later creates under that tag are refused. Test-stamped items are taken back; ground items stamped by the run deleted; players told (`'Done.'`, `'Failed.'`, `'Called off.'`, `'Something went wrong with this job.'`).
- Cooldown starts only for a live run whose job began, not faulted, not Call Off, not cut short from outside (admin Abort, scenario switched off/replaced/deleted, `SwitchScenario`). Stored per character in KVP `director:cd:<scenario>` (survives restarts).
- Logout/disconnect takes a player out (`why` `'logout'` / `'left'`); items stamped by a run still on them are taken back at next character load.
- Only once: a switch (`onlyOnce`, "Only once", group "Played again") added to every card that does something and goes on; the first visit acts, later visits skip through `onceOut`. Not on events, flow cards, goals, or cards the run waits at for a player. To stop a run the second time, use First Time Only (`flow.once`).
- Several things on one card: most cards naming placed things take several or a group (`group:<name>`: every NPC/prop whose page has that Group name). Talking cards, goals and one-car cards name one.

## What a run hands out (items, money, tags)

- Live run: items from Give Item, Drop Item, Put in Car, Create Container, loot, a run car's keys are the player's to keep, never taken back.
- Only items a run's own card looks for (`runItem` fields: Collect, Bring Item To; item-spot piles; Item Picked Up, Take Item) carry a plain run tag in metadata `fromRun = <runId>` (plus where made). Nothing else reads it; it stays on the item. Others carry nothing and stack normally.
- Test: everything handed out is stamped `metadata.director = <runId>`, listed before it goes, and taken back from whoever holds it (and from the ground) when the test ends. Costs, sales, Charge Player, Claim Car, Give Car are only said; flags it sets live on the test run only; Send Signal sends nothing.
- Money: a Test pays and charges nothing (says what it would). Live pays add to `run.payout` (reported in `run:ended.payout`). Money arriving after its card gave up: a payment stays the player's, a charge is refunded.
- An item with per-item generated metadata (serial) is handed one at a time, at most 10 (`MAX_SERIALS`).

## Built-in cards

Notation: `key:kind=default (min..max) [options]`, `req` = required. Every "does and goes on" card also has `onlyOnce:bool=false`. Outcome labels in parentheses. "giveUp N" = built-in Took too long after N s. Inputs are `in` unless noted; event cards have no inputs; Fail Conditions have no pins.

### Scenario and flow

| Type | Title | Outcomes | Fields / notes |
|---|---|---|---|
| `scenario.started` | Scenario Enabled | out | Event card. Fires when the start conditions are met. Cards between it and `scenario.begin` are a lead-in (no failures, no cooldowns) |
| `scenario.begin` | Scenario Started By Player | started (Started), notnow (Not now, bad) | The job starts here. Not now: all its runs are going, or someone is cooling down |
| `scenario.succeed` | Succeed | none | `reason:text` (≤120) |
| `scenario.fail` | Fail | none | `reason:text` (≤120) |
| `scenario.calloff` | Call Off | none | `reason:text` (≤120). No result, nobody told |
| `flow.if` | If | yes, no | `var:var req`, `op:select=is [is, is not, more than, less than, at least, at most, is set, is empty]`, `value:text` (≤100) |
| `flow.sequence` | Do in Order | then1..then4 | Starts everything wired at the same moment, top first; does not wait |
| `flow.reroute` | Reroute | out | Wire bend |
| `flow.once` | First Time Only | out | Goes on the first time; later visits stop there |
| `flow.random` | Random Chance | yes, no | `chance:number=50 (1..99)` |
| `flow.wait` | Wait | done | `seconds:duration=5 (0..86400)` |
| `flow.waitAll` | Wait for All | done | Inputs `a,b,c,d`: goes on once every wired input was reached |
| `flow.countdown` | Countdown | done (Time's up), stopped | Inputs `start`, `stop`. `seconds:duration=300 (1..86400)`, `label:text=Time left`, `show:bool=true`, `who:players=everyone in the run` |
| `var.set` | Set Variable | out | `var:var req`, `value:text` (≤100) |
| `var.add` | Add to Variable | out | `var:var req`, `amount:number=1` (negative subtracts) |
| `flag.set` | Set Player Flag | out | `flag:text req` (≤64), `to:select=on [on, off, to a value, add a number]`, `value:text`, `who:players=this player`. Permanent per character (Player flags) |
| `flag.if` | If Player Flag | yes, no | `flag:text req`, `op:select=is set [is set, is not set, is, at least, less than]`, `value:text` |
| `player.hasItem` | Player Has Item? | yes, no | `item:item req`, `count:number=1 (1..1000)`, `who:select=this player [this player, anyone in the run, everyone in the run]` |
| `player.hasMoney` | Player Has Money? | yes, no, timeout | giveUp 15. `amount:number=100 (1..10000000)`, `where:select=cash or bank [cash or bank, cash, bank]` |
| `script.signal` | Send Signal | out | `name:text req` (≤40, one word `[%w_%-.]+`), `value:text` (≤120), `var:var` (sends that variable's value instead). Fires `whip_core:run:signalled` (not in a Test) |
| `script.wait` | Wait for Script Event | heard (Heard it), timeout (Not in time) | `event:text req` (≤64, `ns.name`), `who:select=About a player in this run [About a player in this run, Sent for this run, Any run waiting for it]`, `seconds:duration=0 (0..86400; 0 never)`. Hears `SendDirectorEvent` |

### Fail conditions and after-cards (category `fail`)

Wired to nothing; watch the whole run every 1000 ms.

| Type | Title | Fields |
|---|---|---|
| `fail.playerDown` | Fail If a Player Goes Down | `who:select=any [any, all]`, `ends:select=everyone [everyone, them]`, `reason:text=Someone went down` |
| `fail.strays` | Fail If a Player Strays | `at:world req`, `radius:number=200 (10..5000)`, `grace:number=10 (0..300 s)`, `ends:select=them`, `reason:text=You left the area` |
| `fail.npcDies` | Fail If an NPC Dies | `npc:worlds req (npc)`, `who:select=any [any, all]`, `reason:text=They were killed` |
| `fail.carLost` | Fail If the Car Is Lost | `car:worlds req (vehicle)`, `reason:text=The car was lost` |
| `fail.carDamaged` | Fail If the Car Is Damaged | `car:worlds req`, `percent:number=25 (1..100)`, `reason:text=The car was too badly damaged` |
| `fail.variable` | Fail If a Variable | `var:var req`, `op:select=at least` (If's ops), `value:text`, `reason:text=It went wrong` |
| `run.afterFail` | Activate After Failure | Outcome `out`, no input: plays when the run fails, 2 min at most |
| `run.afterSuccess` | Activate After Success | Same, on success |

`ends`: `everyone` = fail the run; `them` = take only that player out.

### Event cards (category `events`, no inputs)

| Type | Title | Internal event | Fields |
|---|---|---|---|
| `npc.killed` | NPC Killed | `npc.killed` | `npc:worlds req` |
| `npc.allKilled` | All Killed | `npc.down` | `npc:worlds req` |
| `npc.damaged` | NPC Hurt | `npc.damaged` | `npc:worlds req`, `damage:number (1..2000)` |
| `npc.spotted` | Guard Spots You | `npc.spotted` | `npc:worlds req` (guards: NPCs with Sees players on). The spotted player is the trigger |
| `item.picked` | Item Picked Up | `item.added` | `item:worlds req (groundItem)` |
| `container.opened` | Container Opened | `container.opened` | `container:worlds req` |
| `vehicle.entered` | Car Entered | `vehicle.entered` | `car:worlds req`, `driver:bool=true` |
| `player.downed` | Player has died | `player.died` | `who:select=any [any, all]` |

### Goals (category `goals`)

Each shows objective + blip + waits + clears. Common: `text:text` objective (≤120), `mark:bool=true`, `seconds:duration` time limit (5..86400; empty none; `timeout` "Out of time" only when set).

| Type | Title | Outcomes | Own fields |
|---|---|---|---|
| `goal.goTo` | Goal: Go To | done (Arrived), timeout | `at:world req`, `radius=10 (1..500)`, `who:select=any [any, all]` |
| `goal.deliverCar` | Goal: Deliver the Car | done (Delivered), lost (Car lost), timeout | `car:world req (vehicle)`, `at:world req`, `radius=8 (1..100)`, `driven:bool=true` (only a run player completes) |
| `goal.killAll` | Goal: Kill Them All | done (All down), timeout | `npc:worlds req` (each marked red) |
| `goal.collect` | Goal: Collect | done (Collected), timeout | `item:runItem req`, `count=5 (1..1000)` team total, `at:world` optional area, `radius=50 (5..2000)` |
| `goal.bring` | Goal: Bring Item To | done (Brought), timeout | `item:runItem req`, `count=1`, `at:world req` (thing or NPC), `radius=3 (1..50)`, `take:bool=true` |
| `goal.stealCar` | Goal: Steal the Car | done (In the car), lost, timeout | `car:world req`, `driver:bool=true` |
| `goal.search` | Goal: Search | done (Opened), timeout | `container:world req` (Create Container first) |
| `goal.speakTo` | Goal: Speak To | done (Spoke), lost (NPC lost), timeout | `npc:world req` (wire its Dialog Line beside it) |
| `goal.survive` | Goal: Survive | done (Survived), failed | `length:duration=120 (5..86400)`, `at:world` optional, `radius=50`, `mark` (area). Failed: all down or all left |

`runItem` = one of the items the scenario itself places or gives.

### Dialog and NPC talk (category `dialog`)

Talking cards share: `nameShown:select=yes [yes, no, other]`, `speaker:text` (≤40, shown when `other`), `talk:text=Talk` prompt (≤40). In an `enabled` run with nobody in it they wait for anyone (Talk point).

| Type | Title | Outcomes | Fields |
|---|---|---|---|
| `dialog.line` | Dialog Line | opt1..opt4, fail1..fail4 (Answer N failed, bad), left (Walked away), timeout (No answer) | `npc:world req`, `line:text req` (≤440), `opt1:text req`/`opt2..4` (≤60), `optNRule:rule`, `away:select=wait [wait, out]`, `seconds:duration (5..3600)`, `goal:text` (objective while waiting), `goalMark:bool=true`. An answer wired straight to another Dialog Line for the same NPC continues the conversation |
| `dialog.team` | Pick Team | ready, left, timeout | `npc:world req`, `line:text=Who are you doing this with?`, `radius:number=15 (2..100)`, `byId:bool=true`, `seconds=300 (30..3600)`. Player picks crew up to Team size; each is asked |
| `npc.sell` | Sell to NPC | sold, nothing (Had none), cancelled (Said no), timeout | `npc:world req`, `item:item req`, `price:number=100 (0..1000000)` each, `most:number (1..1000)`, `line:text=I'll give you {total} for {count} {item}.`, `yes:text=Deal`, `no:text=No thanks`, `method:select=auto [auto, cash, bank]`, `soldVar:var`, `paidVar:var`, `seconds=120` |
| `npc.haggle` | Haggle | deal, bad (Bad deal), walked, angry, timeout | `npc:world req`, `forCard:card [player.pay, npc.sell, player.giveItem, player.charge, lore.pay]`, `side:select`, `base=1000`, `floor=700`, `ceiling=1500` (0..100000000), `rounds=3 (1..5)`, `patience:select=normal [short, normal, long]`, `priceVar:var`, `what:text=it`, `seconds=180`, `byeDeal/byeBad/byeWalked/byeAngry:text`. Agrees a price, moves no money: wire Deal to Sell/Pay/Take Item |
| `npc.me` | NPC /me | out | `npc:worlds req`, `text:text req` + `text2..text4` alternatives (≤120), `pick:select=random [random, order]`, `count=1 (1..4)`, `gap:duration=4 (1..30)`, `range=20 (5..250)` |

Dialog Line answer rules (`optNRule`, kind `rule`): `only` = `always | has an item | carries cash | a flag is set | a flag is not set | a variable is` (+ `item`, `count` 1-1000, `cash`, `flag`, `onlyVar`, `value`); `cost` = `nothing | an item | money` (+ `costItem`, `costCount`, `costCash` ≤10,000,000); `offer` = `every time | once a run | once ever`; `chance` 1-99 (server-rolled; a miss leaves by `failN`). Not met = not offered; can't pay = refused.

### Player cards (category `player`)

| Type | Title | Outcomes | Fields |
|---|---|---|---|
| `player.message` | Message | out | `text:text req` (≤200), `kind:select=info [info, success, warning, error]`, `who:players=everyone in the run` |
| `player.objective` | Show Objective | out | `text:text req` (≤200), `who:players`, `subShown:select=name [name, none, other]`, `sub:text`, `icon:glyph=objective` |
| `player.clearObjective` | Clear Objective | out | `who:players` (goals' own and a Countdown stay) |
| `player.giveItem` | Give Item | given, failed, timeout | giveUp 15. `item:item req`, `amount=1 (1..100)`, `who:players=this player`. At their feet if it doesn't fit |
| `item.take` | Take Item | taken, missing, timeout | giveUp 15. `item:worlds req (groundItem)`: takes this scenario's placed items back |
| `player.pay` | Pay | paid, failed, timeout | giveUp 15. `amount=100 (0..1000000)`, `method:select=auto [auto, cash, bank]`, `reason:text=Job done` |
| `player.charge` | Charge Player | paid, short (Could not pay), timeout | giveUp 15. `amount=100 (1..1000000)`, `method=auto`, `reason=Payment` |
| `player.progress` | Progress | done, stopped, timeout (No answer) | Server-timed bar. `label=Working...`, `seconds=8 (1..120)`, `at:world`, `range=3 (1..25)`, `emote:emote`, `canCancel:bool=true` |
| `player.skillCheck` | Skill Check | passed, failed (Missed), timeout, notStarted (Couldn't start) | `game:select=ring` (plus registered skill-check games), `difficulty:select=hard [easy, medium, hard]`, `at:world`, `range=3`. Wire Couldn't start back to a Wait for Press |
| `map.blip` | Show Blip | out | `at:worlds req`, `label:text` (≤40), `color:select=yellow [yellow, red, green, blue, white]`, `route:bool=true`, `radius:number (1..5000)` area, `who:players` |
| `map.blipRemove` | Remove Blip | out | `at:worlds req` |
| `map.waypoint` | Set Waypoint | out | `at:world req`, `who:players` |
| `vehicle.give` | Give Car | given, failed, timeout | `model:text req`, `plate:text` (≤8), `where:select=their garage [their garage, at a placed thing]`, `at:world`, `key:bool=true` |

### World cards (category `world`)

| Type | Title | Outcomes | Fields |
|---|---|---|---|
| `npc.spawn` | Spawn NPC | out, failed | `npcs:worlds (≤24)`, `together:bool=true`, `hostile:bool=false`, `range:number (1..500)`, `tasks:bool=true` |
| `npc.hostile` | NPC Attacks | out | `npc:worlds req`, `hostile:bool=true`, `target:select=the run's players [the run's players, players not in the run, a director entity]`, `thing:world`, `range (1..500)`, `accuracy=30 (0..100)`, `rate=40 (10..100)`, `pattern=full auto [single shots, bursts, full auto]`, `skill=a pro [a rookie, a pro, a killer]` |
| `npc.flee` | NPC Runs Away | out | `npc:worlds req`, `from:select=this player [this player, the nearest of the run's players]` |
| `npc.follow` | NPC Follows Player | out | `npc:worlds req`, `do:select=follow the player [follow the player, stop following]`, `pace=walk [walk, run]` |
| `npc.walkTo` | NPC Walks To | arrived, failed (Did not get there), timeout | `npc:worlds req`, `at:world req`, `pace=walk`, `seconds (5..3600)` |
| `npc.emote` | NPC Plays Emote | out | `npc:worlds req`, `emote:text` (/e name; empty stops) |
| `vehicle.spawn` | Spawn Car | out (Made), failed, timeout | `cars:worlds (≤12)`, `tasks:bool=true` |
| `vehicle.claim` | Claim Car | claimed (Theirs), failed, timeout | `car:world req`, `plate:text` (≤8), `keep:select=where it is [where it is, in their garage]`, `key:bool=true` (ClaimVehicle) |
| `vehicle.dropKey` | Give Car Key | placed (Given), failed, timeout | giveUp 15. `car:world req`, `to:select=on the ground [on the ground, the player who set it off, everyone in the run]`, `at:world` |
| `vehicle.plate` | Change Plate | out, failed, timeout | giveUp 15. `car:world req`, `plate:text req` (≤8) |
| `vehicle.putIn` | Put in Car | placed, failed, timeout | giveUp 15. `car:world req`, `item:item req`, `amount=1 (1..100)`, `into:select=trunk [trunk, glovebox]` |
| `vehicle.reached` | Car Delivered | reached, lost, timeout | `car:world req`, `at:world req`, `radius=8 (1..100)`, `driven:bool=true`, `seconds (10..86400)` |
| `vehicle.damaged` | Car Damaged | damaged | `car:worlds req`, `percent=5 (1..100)`, from when the card starts |
| `vehicle.destroyed` | Car Destroyed | destroyed | `car:worlds req` |
| `vehicle.playTake` | Play Scripted Driving Event | done (Finished), failed, timeout | `car:world req`, `take:take req`, `riders:bool=true`, `ride:bool=false` (player at wheel), `ending:select [it stops, the driver brakes / everyone gets out / their tasks start / it drives on]` |
| `prop.show` | Show Prop | out | `prop:worlds req`, `withGroup:bool=false`, `tasks:bool=true` |
| `prop.hide` | Hide Prop | out | `prop:worlds req`, `withGroup:bool=false` |
| `item.place` | Place Item | placed, failed, timeout | giveUp 15. `item:worlds req (groundItem)` |
| `item.drop` | Drop Item | placed, failed, timeout | giveUp 15. `item:item req`, `amount=1 (1..100)`, `at:world req` (NPC: where it fell) |
| `container.create` | Create Container | made, failed, timeout | giveUp 15. `container:world req`, `loot:loot` (slots `{slot, item, min, max, chance}`; a slot's chances ≤100%) |
| `door.set` | Lock / Unlock Door | out (Done), failed | `door:worlds req`, `action:select=unlock [unlock, lock]`, `who:select=nobody (only the cards) [.., the run's players]`. Restored at run end |
| `point.press` | Wait for Press | used (Pressed), timeout | `at:world req`, `label:text=Use`, `icon:glyph`, `reach=2 (1..5)`, `seconds (5..86400)` |
| `point.menu` | Interaction Menu | item1..item8 (Choice N), timeout | `at:world req`, `label=Use`, `item1:text req`..`item8`, `itemNUnder:select=top [top,1..8]` (nest 3 deep), `reach=2`, `seconds` |
| `area.entered` | Player Arrives | entered, timeout (Too late) | `at:world req`, `radius=15 (1..500)`, `who=any [any, all]`, `seconds (5..86400)` |
| `area.left` | Player Leaves | left, timeout | `at:world req`, `radius=25`, `who`, `seconds` |
| `tasks.start` | Start Tasks | out (Started), done (Finished), failed, stopped | `things:worlds (≤24)`, `from:select=the first task [the first task, where they stopped]`. `out` goes at once |
| `tasks.stop` | Stop Tasks | out | `what:worlds req (≤24)`, `then:select=goes back to its idle [.., stays where it is]` |
| `world.remove` | Remove | out (Done), timeout | giveUp 15. `what:worlds req`: removes what the run made for them |
| `weapon.fire` | Fire Weapon | fired, failed, timeout (No answer) | `weapon:world req (prop: a Fixed Weapon)`, `shots=1 (1..20)`, `gap=0.5 (0.05..5)`, `at:select=where it points [.., a placed thing]`, `thing:world`. Real shots, in a Test too |
| `speakers.play` | Play on Speakers | done, failed, timeout | `speakers:worlds req (prop, ≤32)`, `url:text req` (Fivemanage link), `loop=true`, `volume=100 (0..200)`, `range=40 (5..300)`, `full=4`, `sound=35`, `tone:bool` + `bass/mid/treble (-12..12)`, `fadeIn (0..30)`, `wait:bool=false` |
| `speakers.stop` | Stop Speakers | done (Stopped), timeout | `speakers:worlds req`, `fadeOut=2 (0..30)` |

### Lore (category `lore`; details in the voice reference)

`lore.pay` Send Money (paid, failed, timeout; giveUp 15; `lore:lore`, `amount=500 (1..1000000)`, `message=For the job`; a Test pays nothing), `lore.say` Lore Says (done, failed, timeout; `lore`, `line:select=Hello [Hello, Goodbye, React positive, React negative, Bumped into, Hit by a car, Gun aimed at it, Gunfire nearby, Its car stolen]`, `wait=true`, `bonus (0..250)`, `megaphone`, `radio [No, On the player's frequency, On a frequency]`, `freq (100..999)`), `lore.voiceLine` Play Custom Voice Line (done (Said), failed, timeout; `url req`, `text` subtitle, `busy=say it after [say it after, cut in, skip it]`, plus Lore Says' device fields). A `lore` field left empty = the scenario's own lore character.

## Built-in task steps

A thing's Tasks list (NPC, car, prop; at most 40 steps, `DirectorSteps.MAX_STEPS`) plays top to bottom. Spawn cards start them (Start its tasks, default on) or Start Tasks later. Times are seconds to 0.1, at most 86399.

Timing: `instant` (done once applied), `timed` (lasts `sec`), `until` (waits to be done, gives up after `giveUp`), `either` (builder picks; `next`). A time of 0 = no end (goes on until the list is stopped or the run ends); new "can go on" steps are added at 0. Steps that do one thing (`length`: Throw, Turn To Face, Horn, Flash the Lights, Brake, Speed Up To, prop Slide To/Turn To/Fade) keep a time and 0 means at once. A give-up of 0 = never. 0 is sent as a week (`NO_END_MS`).

Target field (`target`): `nearest` (nearest run player), `trigger` (who set the card off), `thing` (placed thing), `point`.

| Group | Steps (`t` "label" kinds: fields; timing defaults) |
|---|---|
| move | `goTo` "Go To" npc: `at`, `pace [walk, run, sprint]`, `straight` (either, 10 s / give-up 30) · `walkRoute` "Walk a Route" npc: `route:world(route)`, `loose` · `wander` "Wander Nearby" npc: `radius=8 (2..60)` (timed 20, new=0) · `teleport` "Teleport" all: `at` · `face` "Turn To Face" npc: `target` (2 s) · `follow` "Follow" npc: `target [nearest, trigger, thing]`, `pace` · `flee` "Run Away From" npc: `target` · `cover` "Take Cover" npc: `at`, `height [something low, something tall]`, `side [left, right]` (either 10/20) · `slideTo` "Slide To" prop: `at` (3 s) · `turnTo` "Turn To" prop: `heading (0..360)` |
| look | `lookAt` "Look At" npc: `target`, `eyes` · `aimAt` "Aim At" npc: `target` · `shootAt` "Shoot At" npc: `target`, `accuracy=30`, `rate=40`, `pattern`, `skill` (standing NPC never shoots) · `throw` "Throw" npc: `item [grenade, molotov, smoke grenade, flare, snowball, ball]`, `target=point` |
| fight | `fightPlayers` "Fight the Scenario's Players" npc · `fightNpc` "Fight an NPC" npc: `npc:world(npc)` |
| act | `emote` "Play Emote" npc: `by [emote, animation]`, `emote`, `dict`, `clip`, `loop=true` · `speech` "GTA Speech" npc: `voice`, `line` (once) · internal: `anim`, `scenario` |
| car | NPC driving: `getIn` "Get In" `car`, `seat [driver, front passenger, back left, back right, any free seat]` (until 20) · `getOut` "Get Out" · `warpIn` "Sit In (at once)" · `driveTo` "Drive To" `at`, `speed=60 km/h (5..300)`, `style [normal, careful, rushed]` (either 30/120) · `cruise` "Cruise Around" `speed=50`, `style` · `followCar` "Follow in a Car" `target`, `speed=80`. Vehicle: `take` "Play a Scripted Driving Event" `take` (until 60) · `brake` · `speedTo` `speed` · `everyoneOut` · `siren` `on` · `blowUp` · `door` `door [front left .. bonnet, boot, all of them]`, `how [open, shut]` · `windows` `how [down, up, smashed]` · `lights` `lights [on, off, as GTA has them]`, `beam`, `inside` · `flashLights` · `indicators` `side [left, right, hazards, off]` · `horn` · `alarm` · `engine` `how [on, off, smoking, stalled]` · `tyres` `how [burst, fixed]` · `roof` `how [down, up]` · `fire` · `dirt` `pct` · `lock` `on` |
| body | `setHealth` npc/vehicle `pct (1..100)` · `die` · `revive` · `writhe` · `freeze` npc/vehicle `on` · `weapon` "Hold a Weapon" npc `weapon` · `fade` prop `pct` · `look` "Change Look" prop `variant (0..15)` |
| wait | `wait` "Wait" all: `by [time, card]`, `card`, `outs` (wait for a run card's outcome) (timed 3, give-up 3600) |

Standing (Always present) NPCs skip steps that need a run (fight players, shoot, throw, get in a run car, writhe). Lasting steps (wander, drive, emote...) keep going after their slot; once steps (speech, throw, blowUp, fire) are never replayed by a new owner. `/npcdebug` shows each NPC's and car's task. `Config.ExperimentalDriveSync` (off by default): every game plays recorded drives itself.

## Placed-thing kinds and field kinds

Things (`DirectorThings.KINDS`): `npc` (needs `model`; tasks), `vehicle` (needs `model`; run only, made by Spawn Car; tasks; random vehicle: `def.random = true`, `def.models = { {model, chance} }`), `prop` (needs `model`; tasks; Physics on unless static), `spot` (a place only), `groundItem` "Item spot" (needs `item`), `container` (run only), `door` (run only), `route` (points for Walk a Route). Ids default to base + number (`npc3`, `car2`, `item1`).

Field kinds a card may use (`fields.lua`): `text`, `number`, `duration`, `bool`, `select`, `players`, `world`, `worlds`, `var`, `item`, `runItem`, `rule`, `job`, `card`, `take`, `glyph`, `emote`, `loot`, `lore`, `entries`. Step-only: `cardOuts`, `point`, `target`, `weapon`, `voice`, `speechLine`.
- Another resource's card (`satCard`): `text`, `number`, `duration`, `bool`, `select`, `players`, `world`, `var`, `item`, `job`, `lore`, `entries`.
- Another resource's task (`satStep`): `text`, `number`, `bool`, `select`, `world`, `point`, `target`.
- `players` values: `'this player'`, `'everyone in the run'`, `'the starter'` (resolved to server ids for your code).

## Server exports: starting runs

All `exports.whip_core:<Name>`; server scripts are trusted (any may steer any run; the history names the resource).

### StartScenarioRun(key, who, opts?) — SERVER
Start a run of a switched-on scenario whose start mode is `script`, or join the waiting run of an `enabled` one.
- `key` string; `who` server id or `{ charId }` (online). The player becomes starter; Team size applies.
- `opts.with` list of players (server id or `{charId}`) as crew; total ≤ Team size (16 max). One who is down, in the character screen, already in a run of it, or cooling down is silently left out (the starter cooling down is refused).
- `opts.vars` `{ name = value }` typed as declared (number finite; bool boolean; text ≤200).
- `opts.places` `{ [placedThingId] = {x, y, z, heading?, interior?} | vector3 | vector4 | { coords = ... } }`: NPCs, cars, ground items, containers, spots only. Refused for a Standing thing, a door, a prop; |x|,|y| ≤ 20000, z −500..3000; ≤64 places; `interior = true` inside an MLO.
- `enabled` scenario: the player (and `with`, added like `AddPlayerToScenarioRun`) join its waiting run; `vars`/`places` refused.
- Returns: `runId` (number), or `false, reason`: `'that scenario is not switched on'`, `'that scenario does not start from a script (its Settings: A run starts)'`, `'that player is not online (a server id, or { charId = n })'`, `'You are already doing this'`, `'this scenario is already running'`, `'You can do this job again in N min'`, `'This is not available right now: it needs ...'`, a var/place error.
```lua
local runId, why = exports.whip_core:StartScenarioRun('turf_war', source, {
    with = { partner }, vars = { reward = 2500, rival = 'Ballas' },
    places = { stash = { x = 102.4, y = -1940.2, z = 20.8, heading = 90 }, boss = vector4(-1150.2, -1520.6, 10.6, 35.0) },
})
if not runId then exports.whip_core:NotifyPlayer(source, why, 'error') end
```

### CanStartScenarioRun(key, who) — SERVER
Same checks, nothing started: Director on, switched on, mode `script`/`enabled`, eligible, not cooling down (when no `scenario.begin`), cards present, for `enabled` its waiting run not taken (`'Someone is doing this already'`), runs not full, < 64 runs server-wide (`'too many scenarios are running'`). Returns `true` or `false, reason` (worded "They ...").

## Server exports: reading runs and scenarios

Tests are left out unless `opts.tests` / `filter.tests` is true. Never waits unless said.

### GetScenarioRun(runId, opts?) — SERVER
Returns `DirectorRunView` or `false, 'No run with that id is going'`.

`DirectorRunView` = `{ id, tag, scenario (key), name, rev, test, kinds (string[]), where = { world, label, coords = {x,y,z} } | nil, players = { {source, charId, name} }, starter, startedAt (epoch s), seconds, endsIn (s | nil), vars, objectives = { {source, text, countdown} }, things = { [placedThingId] = { kind, netId, npcId, vehicleId, containerId, groundId, doorId, npcs } }, variant = { id, name } | nil }`. `where` is moved to the run's own place when started with `places`. Give `run.tag` to anything you make for the run (`ShowBlip`, `AddPoint`, `SpawnNpc` opts): it goes when the run ends.

### GetScenarioRuns(filter?) — SERVER
`filter = { scenario?, player? (id | {charId}), kind? (lower-cased match), tests? }`. Returns a list (empty when none, or when `player` is offline).

### GetPlayerScenarioRuns(who, opts?) · IsPlayerInScenarioRun(who, key?, opts?) — SERVER
List of views; `true|false` (of that scenario, or any).
```lua
if exports.whip_core:IsPlayerInScenarioRun(source, 'bank_job') then return false, 'Finish the job you are on first' end
```

### GetScenarioRunOf(ref, opts?) — SERVER
`ref` = `{ netId }` | `{ vehicleId }` | `{ npcId }` | `{ tag }`. A `netId` must exist now (resolved to whip's NPC/car). Returns view or `false, 'That is not part of a run going now'`.

### GetScenario(key) · GetScenarios(filter?) — SERVER
`DirectorScenarioView` = `{ key, name, description, kinds, where, on, rev (on revision | nil), draftRev, startMode ('enabled'|'interaction'|'press'|'area'|'item'|'timer'|'script'|'admin'), source ('db' | 'pack:<resource>' | 'file'), runs (live, tests excluded), variants? }`; `GetScenario` adds `cards` (types used), `world` (`{ id, kind, layer, label, coords }`), `vars` (`{ id, type, default }`). Describes the switched-on revision, else the draft. `filter = { on?, kind?, startMode? }`. Returns `false, 'No scenario called <key>'` / list.

### GetScenarioStats(key) — SERVER, WAITS
`{ runs, succeeded, stopped, lastAt (epoch s | nil) }` (`stopped` = called off/aborted/cut short), tests excluded; stored scenarios only (`false, 'No stored scenario called ...'`).

### GetDirectorCards(filter?) — SERVER
Every card type as the editor gets it: `{ type, title, desc, category, inputs, outputs, labels, props, owner, ... }`. `filter = { category?, owner? }`.

## Server exports: steering runs

Refused for a builder's Test (`'That run is a builder\'s Test'`) except `EndScenarioRun`.

### EndScenarioRun(runId, outcome, reason?) — SERVER
`outcome` `'succeeded' | 'failed' | 'calledOff'` (no result, nobody told). `reason` cut to 120; recorded as `'<reason> (by <resource>)'` in `run:ended.reason` and the history. Returns `true` or `false, reason`.

### AddPlayerToScenarioRun(runId, who) — SERVER
Crew: the run's doors, containers, payouts, items, and what its cards gave "the run's players" (prompts, goals, objective, guards' targets, blips). Refused: Test, down/no character/creator/isolated, already in a run of it, cooling down (job begun), full (`'That run is full (N players)'`, N = Team size). On an `enabled` run nobody has joined yet it claims the run (they become starter). Announces `run:playerJoined` with `by`. Returns `true` / `false, reason`. Police responding to a heist are not crew: reach them with blips.

### RemovePlayerFromScenarioRun(runId, who, why?) — SERVER, WAITS
Takes back test-stamped items first, then takes them out (`why` ≤120, default `'taken out'`); announces `run:playerLeft` with `by`. Call from a thread.

### GetScenarioRunVar(runId, name, opts?) · SetScenarioRunVar(runId, name, value) — SERVER
Get returns `true, value` (true first: a variable may hold false/nil) or `false, reason`. Set checks the declared type (`'<name> is a number'`, `'... is true or false'`, `'... is text'`, `'... at most 200 characters'`); the next card reading it sees the value; not written to history.

### SendDirectorEvent(name, payload?, opts?) — SERVER
Every Wait for Script Event card (and custom event/fail card) waiting for `name` reacts.
- `name` `'<ns>.<name>'` (≤64, `^[%a][%w_]*%.[%a][%w_.]*$`) in your namespace: first running resource to use a namespace owns it (shared with cards/tasks); whip_core's are nobody's.
- `payload.source` = player it is about (what follows acts for them when they are one of the run's players). Payload copied 4 deep, 50 keys, text 500.
- `opts.runId`: only that run.
- Rate: 20 of one name/s per sender, 60/s per sender in total (`'too often: ...'`).
- Returns `true, heardBy` or `false, reason`. A Test never hears real events: `/director send <event> [value]` injects one into your own Test.
```lua
exports.whip_core:SendDirectorEvent('police.backupArrived', { source = robber, unit = 'Adam-12' })
```

### SwitchScenario(key, on, why?) — SERVER, WAITS
Only when the revision a person switched on has `settings.scriptSwitch = true`; never while a builder tests it; on only at that person-switched revision (never a draft, never one a person switched off: `'a builder must switch it on first ...'`); `on` must be a boolean. Off calls off its runs with `'<why> (switched off by <resource>)'` (cut short: no cooldown). In memory only: a reboot restores the person's choice; a person switching it forgets the script's. Off while its pack restarts or the server boots is remembered. Never with a card provider other than the one a person accepted. Events show `by = { resource }`.
```lua
CreateThread(function()
    local wasNight
    while true do
        local hour = exports.whip_core:GetTime()
        local night = hour >= 22 or hour < 5
        if night ~= wasNight then exports.whip_core:SwitchScenario('bank_job', night, 'night only') wasNight = night end
        Wait(60000)
    end
end)
```

### GetDirectorThingData(where, worldId) — SERVER
What YOUR resource's buttons saved on a placed thing. `where` = run id (that run's revision) or scenario key (the switched-on revision; off → `false, 'That scenario is not on'`). Returns a copy, `nil` (nothing saved), or `false, reason`.

## Server exports: checking and testing

### CheckDirectorScenario(doc) — SERVER
Returns `ok, problems` (`{ { severity, node?, pin?, message } }`).

### TestDirectorCard(type, props?, opts) — SERVER, WAITS
Runs one of YOUR cards once as a Test in a scenario of its own (Scenario Enabled → card → each outcome ends it). Real code runs with `card.test = true` (Give taken back, Pay only says, Charge nothing, no events).
- `props`: fields; a `world` field takes `{x, y, z, heading?}` / vector (only `spot` world kinds).
- `opts.player` (required, on a character, not testing in the editor); `opts.seconds` 1-120 (default min(120, Give up after + 5); a longer Give up after is shortened to fit); `opts.event` an event card's payload (`source` defaults to the player).
- At most 2 card tests of yours at once.
- Returns `{ outcome, data }` or `false, reason` (Check's first error `'Check: ...'`, Didn't work's reason, `'it had not answered after N seconds'`).

### TestDirectorScenario(doc, opts) · SteerDirectorTest(runId, op, ...) · GetDirectorTestResult(runId) — SERVER
- Runs a document as a Test for `opts.player` (required). Check must pass (a run that can never succeed is tested anyway). One per player; 3 of yours at once.
- `opts.seconds` 1-600 (60): still going → aborted, `late = true`. `opts.vars` set before the first card. `opts.wait = false` returns at once (`status 'running'`).
- `opts.steer` (≤200), done in order: `{ op='take', node, pin }` and `{ op='say', node, option, amount? }` once their card waits; `{ op='event'|'emit', name, payload?, when? }`, `{ op='var', name, value, when? }` at once or when the `when` card waits; `{ op='end', outcome?, reason? }`; `{ op='wait', ms }`.
- `say` options: Dialog Line `opt1..opt4`; Haggle `ask` (with amount), `take`, `leave`; Sell to NPC `yes`/`no`; Pick Team `go`.
- `emit` = one of the Director's internal events to this run alone (`npc.killed`, `npc.down`, `npc.damaged`, `npc.spotted`, `item.added`, `container.opened`, `vehicle.entered`, `player.died`, `player.left`, `point.used`, `conversation.choice`, `conversation.ended`, `scenario.started`, `script.event` ...); `payload.source` defaults to the tester, `runId` to the run.
- Result: `{ runId, status ('running'|'succeeded'|'failed'|'aborted'|'faulted'), reason, faultNode, late, vars, steps = { {n, node, kind, pin, text, ms} } (≤4000; `dropped` counts more), fired = { [node] = { [pin] = n } }, entered = { [node] = n }, waiting, things, made, players, steered, steerFailed?, left, done }`.
- `SteerDirectorTest(runId, 'take'|'say'|'event'|'emit'|'var'|'end', ...)`: `true[, extra]` or `false, reason`; `'end'` with `'succeeded'`/`'failed'`, anything else aborts.
- `GetDirectorTestResult(runId)`: yours only; kept 10 minutes after the end (20 per resource max); `nil` otherwise.
```lua
CreateThread(function()
    local r = exports.whip_core:TestDirectorScenario(doc, { player = source,
        steer = { { op = 'say', node = 'offer', option = 'opt1' } } })
    print(r and r.status, r and r.reason)
end)
```

### Other Director-related server exports (documented elsewhere)
`RemoveDirectorScenario(key)`, `RemoveDirectorTemplate(name)` (packs, below). Lore: `GetLoreCharacter`, `GetLoreCharacters`, `CheckPicture`, `PayAsLore` (WAITS), `LoreSay` (WAITS) — see the voice reference. Internal (`__`-prefixed) exports are used only by `lib/satellite.lua`.

## Events (server and client)

Server events (`whip_core:*`) go out after the scheduler pass (never inside a run's cards), never for a builder's Test (except `run:thingMade`). Any resource can fire them: check `GetInvokingResource() == 'whip_core'` before paying anything.

| Event | Payload |
|---|---|
| `whip_core:run:started` | `{ run, startedBy = { mode, by } }`. `mode`: `interaction`, `press`, `area`, `item`, `timer`, `script` (`by` = resource), `hand` (admin/editor), `enabled` (nobody in it yet: wait for `run:playerJoined`) |
| `whip_core:run:ended` | `{ run, outcome, reason, vars, payout, faultCard = { id, type } | nil, stopping }`. `outcome`: `succeeded`, `failed`, `calledOff`, `aborted`, `faulted`. `stopping` = whip_core stopping. The run is gone afterwards |
| `whip_core:run:playerJoined` | `{ run (with them), source, charId, by }` (`by` = resource that added them, else nil) |
| `whip_core:run:playerLeft` | `{ run (without them), source, charId, why ('logout'|'left'|script reason|...), by, runEnds }`; sent before its `run:ended` |
| `whip_core:run:signalled` | `{ run, name, data = { value }, source }` (Send Signal) |
| `whip_core:run:thingMade` | `{ run, world, kind, label, netId, npcId, vehicleId, containerId, groundId, doorId, model, data }`; `data[resource]` = what each resource keeps on the thing (yours at `data[GetCurrentResourceName()]`); `model` = car model as made. Sent in Tests too (`run.test`). Standing layer: `{ scenario, standing = true, test?, world, kind, ... }` with no run, as the scenario switches on or a Test starts. `netId` may be nil briefly after a car is made |
| `whip_core:scenario:switchedOn` | `{ scenario, name, rev, replaced (boolean), by }` |
| `whip_core:scenario:switchedOff` | `{ scenario, name, rev, why, by }`. `by`: `{ source, name }` (person), `{ resource }` (`SwitchScenario`), nil (server) |
| `whip_core:lore:changed` | `{ key, character, retired }` (voice reference) |

Client (local, this player's own runs, never a Test; `client/director_runs.lua`):

| Event | Payload |
|---|---|
| `whip_core:run:joined` / `whip_core:run:updated` | `{ runId, scenario, name, objective, countdown }` (`updated`: objective or clock changed; an update for an unknown run arrives as `joined`) |
| `whip_core:run:left` | `{ runId, scenario, name, why }` |
| `whip_core:run:ended` | `{ runId, scenario, name, outcome, payout }` |
| `whip_core:director:builderCopy` | world builder (local): `{ id, kind, model, entity, data, driven }` the builder made its own copy of a car/NPC/prop a resource keeps data on: dress it as a run would. `driven = true` on the car recorded in a take |

Client export `GetPlayerScenarioRuns()` — CLIENT: `{ { runId, scenario, name, objective, countdown } }` newest first (countdown counted down locally).

```lua
AddEventHandler('whip_core:run:started', function(e)
    if GetInvokingResource() ~= 'whip_core' then return end
    for _, k in ipairs(e.run.kinds) do
        if k == 'heist' and e.run.where then
            local people = {}
            for _, o in ipairs(exports.whip_core:GetClockedOnEmployees('police') or {}) do people[#people + 1] = { charId = o.charId } end
            if #people > 0 then
                exports.whip_core:ShowBlip({ people = people }, 'heist:' .. e.run.id, { coords = e.run.where.coords,
                    label = 'Alarm: ' .. e.run.where.label, sprite = 161, color = 1, tag = e.run.tag })
            end
        end
    end
end)
```

## Custom cards: Whip.card

Load `@whip_core/lib/satellite.lua`. Your functions stay in your resource: whip_core receives the card as data plus one entry function that runs your `run`/filter/`check`/`onEnd` in a pcall on your side, so errors come back in your own words.

### Whip.card(type, def) — SERVER
- `type` `'<namespace>.<name>'` (≤64, `^[%a][%w_]*%.[%a][%w_]*$`). First running resource to use a namespace owns it (cards, tasks, buttons, events). whip_core's namespaces are refused: `flow scenario player world npc item vehicle goal dialog map point door container area prop flag var script run job zone conversation whip whip_core` plus every built-in prefix (`fail`, `lore`, `speakers`, `tasks`, `weapon`, ...).
- Call at file scope or in `Whip.register`: re-sent whenever whip_core restarts; calling again changes it. Refusals are printed (`[res] Director card X refused: why`).
- Needs `run`, or `event`, or `fail`. Returns `true`, or `false` (printed) when `def` isn't a card.

| def key | Type / default | Notes |
|---|---|---|
| `title` | string, required | ≤40 |
| `desc`, `help` | string? | ≤200, ≤600 |
| `category`, `categoryTitle` | string? | palette group (≤24, one word; default your namespace; fail conditions default `fail`), group name ≤24 |
| `color` | `blue teal green amber red violet slate` | |
| `icon` | string? | ≤24 `[%w_-]` |
| `outputs` | string[] | 1-8 outcomes, one word ≤24; not `timeout`/`didntWork` |
| `labels` | `{ [outcome] = text }` | ≤30 |
| `bad` | string[] | outcomes drawn red |
| `props` | table[] ≤40 | fields (below) |
| `run` | `function(card) -> outcome?, data?` | may wait; return nothing and answer later with `Whip.answerCard`; an error = Didn't work |
| `instant` | boolean | answered inside the pass; must not wait (`card:give/pay/charge` refused) |
| `timeout` | number 1-3600, default 30 | becomes a `giveUpAfter` field "Give up after (seconds)" the builder can change |
| `event` | `{ name, match?, once?, filter? }` | instead of `run`; `name` in your namespace; `match` `'player'` (default; payload.source is a run player) / `'run'` (payload sent with `opts.runId`) / `'any'`; `once` default true (fires once per run); `filter(card, event) -> outcome|nil, data?` (must not wait) |
| `fail` | `{ event, match?, ends?, reason?, filter? }` | a Fail Condition instead of `run`+`outputs`; gets fields `ends` (`player` match only; default `fail.ends` or `'everyone'`) and `reason` (default `fail.reason` or `'A rule of the job was broken'`); `filter(card, event)` → `true` or text breaks (text is told), false/nil not this time |
| `check` | `function(props, doc) -> message?, 'warning'?` | must answer at once; `doc = { vars = {{id,type}}, world = {{id, kind, label, model, models}}, data = { [worldId] = your button data } }` |
| `onEnd` | `function(callId, why)` | ended without your answer; `why` `'timeout'`, `'didntWork'`, `'run ended'`, `'restarted'` |
| `testSays` | string ≤200 | what a Test says instead of running; `{field}` placeholders |
| `test` | `'run'` | runs in a builder's Test too (`card.test` true: act only on `card.player`/`card.starter`) |
| `permission` | string | only holders may add/change it (3-64 `[%w_.-]`); checked on save, copy, restore, Test |
| `v`, `renamed` | int ≥1; `{ ['ns.old'] = { pins = { old = 'new' } } }` | ≤8 renames, own namespace |
| `once`, `onceOut` | boolean; outcome | `once = false` removes the Only once switch (cards the run waits at for a player) |

Inputs are not settable: thread/instant cards have `in`, event/fail cards none.

Field (`props[n]`): `{ key, kind, label, default?, required?, hint? (≤160), unit? (≤12), group? (≤30), showIf? }`. `key` one word ≤24, not `giveUpAfter`. `showIf` = key of a `bool` field of the same card. Per kind:
- `text`: `maxLength` (default 200, ≤500), `lines` 1-6.
- `number` / `duration`: `min`, `max`, default within.
- `bool`; `select`: 1-200 `options` (text ≤40, or `{ value, label }`), default must be an option.
- `world`: `worldKind` (`spot`, `npc`, `vehicle`, ...). Your code gets `{ id, kind, label, coords = {x,y,z}, heading }` (at the run's own place) or nil.
- `item` (default an item key ≤60), `job` (default a job key ≤64), `var`, `lore` (no default; empty = scenario's lore; your code gets `{ key, name, payName, model }`), `players` (default `this player`; your code gets server ids).
- `entries`: `button` (one of your Director buttons with kind `'card'`), `add` (≤30 words), `max` 1-12 (default 8), no default; a list of plain-data entries each showing its `text`.

Three behaviours:
- Thread (default): runs in its own thread outside the pass; outcomes plus `didntWork` ("Didn't work": resource stopped, code threw, unknown outcome) and `timeout` ("Took too long"). Unwired Didn't work faults the run. Pulsed again while running: dropped.
- Instant: outcomes + `didntWork`. Returning nil means no outcome: nothing follows from it (`cards_api.lua:690`).
- Event: listens for the whole run; goes on through the first outcome (or the filter's). In a builder's Test it hears only `/director send` and its filter runs only with `test = 'run'`.

In a builder's Test (no `test = 'run'`): the card is a stand-in; the tester is told `testSays` and the test strip offers its outcomes, taking the first after 15 s.

```lua
Whip.card('mycafe.callStaff', {
    title = 'Call Staff', color = 'teal', desc = 'Tells the café staff on duty, with a message.',
    outputs = { 'sent', 'nobody' }, labels = { sent = 'Sent', nobody = 'Nobody on duty' }, bad = { 'nobody' },
    props = { { key = 'message', kind = 'text', label = 'Message', default = 'A customer is waiting', maxLength = 120 } },
    testSays = 'Would send "{message}" to the staff on duty',
    run = function(card)
        local staff = Whip.core:GetClockedOnEmployees('mycafe')
        if type(staff) ~= 'table' or #staff == 0 then return 'nobody' end
        for _, s in ipairs(staff) do if s.source then Whip.core:NotifyPlayer(s.source, card.props.message, 'info') end end
        card:record('called', { detail = card.props.message })
        return 'sent'
    end,
})
```

Fail condition example:
```lua
Whip.card('police.failArrested', {
    title = 'Fail If a Player Is Arrested',
    fail = { event = 'police.arrested', match = 'player', ends = 'them', reason = 'You were arrested',
             filter = function(card, event) return event.data.felony and 'Arrested for a felony' end },
})
-- elsewhere: exports.whip_core:SendDirectorEvent('police.arrested', { source = src, felony = true })
```

Card providers: when a person switches a scenario on (or accepts its pack), the resource providing each custom card is recorded; the server re-enabling it (boot, card returning) only accepts the same providers. A card's resource stopping: its scenarios start no new runs (`'This is not available right now: it needs <res>, which is not running'`), running runs take Didn't work when they reach it, a Test holding it ends. Scenarios waiting for cards come back on by themselves once all are present. `/director cards` lists every custom card's stats (at work, didn't work, tested, items/money handed out).

## The card object (WhipDirectorCard)

A copy handed to `run`/filters; methods call back into whip_core and are refused (`'that card is no longer running'`) once the card finished or for another resource.

Fields: `callId` (never send to a client), `type`, `runId`, `cardId`, `scenario`, `name`, `rev`, `tag`, `test`, `player` (who the run acts for now), `starter`, `players` (server ids), `trigger`, `props`.

| Method | Returns | Notes |
|---|---|---|
| `card:var(name)` | value, or `nil, why` | `'"x" is not one of this scenario's variables'` |
| `card:setVar(name, value)` | `true` / `false, why` | typed as declared |
| `card:state()` / `card:setState(t)` | table / `true` | per-card memory kept between calls in the run (copied 4 deep, 50 keys, text 500) |
| `card:place(id)` | `{ id, kind, label, coords, heading }` / `nil, why` | at the run's own place |
| `card:made(id)` | `{ kind, netId, npcId, vehicleId, containerId, groundId, doorId, model, data }` / `nil, why` | `'the run has not made it (yet)'`; `data` = your button data on it |
| `card:record(kind, { source?, detail? })` | `true` / `false, why` | history line; `kind` ≤30, `detail` ≤120; 50 per card per run; `source` must be a run player |
| `card:objective(text, { who? })` | `true` / `false, why` | ≤200; whole crew (follows joiners) or one run player |
| `card:clearObjective()` | `true` | take it down before answering; auto-removed if the card ends without your answer |
| `card:clock(seconds, label)` | `true` / `false, why` | 0-86400 (0 stops); label default `Time left` (≤60) |
| `card:give(src, item, n, metadata?)` | `true, given` / `false, why` | WAITS; run player; item exists; n 1-100; as Give Item (Test takes back); not from instant cards |
| `card:pay(src, amount, { method?, reason? })` | `true` / `false, why` | WAITS; whole $1-1,000,000; `method` `cash`/`bank`/auto; Test only says |
| `card:charge(src, amount, { method?, reason? })` | `true` / `false, why` | WAITS; Test charges nothing |
| `card:finish(outcome, reason?)` | `true` / `false, why` | `'succeeded'|'failed'|'calledOff'`; reason ≤120 |
| `card:log(fmt, ...)` | `true` | server console line naming run and card |

## Whip.answerCard, Whip.removeCard

### Whip.answerCard(callId, outcome, data?) — SERVER
Answers a waiting thread card later. Only the card's own resource. `outcome` must be one of its own; `data.source` = which run player what follows acts for. Returns `true` or `false, reason` (`'that card is no longer waiting'`, `'"x" is not one of this card's outcomes'`). A wrong outcome does not retry: the card ends as Didn't work (faults the run if unwired).
```lua
Whip.answerCard(callId, 'responded', { source = officer })
```

### Whip.removeCard(type) — SERVER
Takes one of your cards away (all go when your resource stops). Returns `true` / `false, reason`. A scenario using a removed card keeps it, drawn as unknown until it is back.

## Custom tasks: Whip.task / Whip.removeTask

### Whip.task(type, def) — SERVER CLIENT (one call in a file both sides load)
Server sends the type as data; each game keeps `run`/`done` and plays the step on the game that owns the NPC/car (in its own thread). The world builder's Play here runs it on its copy with `info.preview`.

| def key | Notes |
|---|---|
| `label` | ≤40, required |
| `desc` | ≤160 |
| `group` | `move look fight act car body wait` or your own (one word ≤24; default your namespace) with `groupTitle` (≤24) |
| `kinds` | `{ 'npc' }`, `{ 'vehicle' }` or both; `'prop'` refused |
| `timing` | `instant`, `timed` (default), `until`, `either` |
| `sec` | timed/either seconds, default 3; 0 (no end) or 0.1-86399 |
| `giveUp` | until/either, default 30; 0 (never) or 1-86399 |
| `next` | either's default `'done'` or `'time'` |
| `lasting`, `once` | booleans; `standing = false`: standing NPCs skip it |
| `fields` | ≤8: `{ key, kind, label (≤40), hint (≤80), unit (≤8), default?, required? }`; keys not `k t sec giveUp next thing` |
| `run(entity, args, info)` | required. `args`: world field → entity on this game (nil if not here); target → `{ kind, entity, coords }`; point → `{ x, y, z, heading }`. `info = { type, kind, timing, ms, preview }` (`ms` a week for no end). Returning `false` or throwing = failed |
| `done(entity, args)` | until steps: asked every 0.25 s; `true` done, `'failed'` failed, else not yet. Without it, the step is done when `run` returns |

Field kinds: `number` (`min`, `max`; `slider = true` needs min+max, `step` > 0, default = min), `bool`, `select` (1-200 options ≤30 chars; `look = 'seg'` 2-4 buttons; default first option), `text` (`max` ≤128, default 64), `world` (`worldKind`), `point` (key must be `'at'`), `target` (key must be `'target'`; options subset of `nearest trigger thing point`, default first). A `point` field and a target allowing `point` cannot coexist.

The game that owns the thing can change mid-step: the new owner runs a timed or lasting step again from its start; keep `run` to what the entity itself does. Returns `true`, or `false` (printed). `Whip.removeTask(type)` removes it on the side it's called on.
```lua
-- shared file
Whip.task('mycafe.flash', {
    label = 'Flash the Lights', group = 'car', kinds = { 'vehicle' }, timing = 'timed', sec = 4,
    fields = { { key = 'times', kind = 'number', label = 'Times', min = 1, max = 20, default = 5 } },
    run = function(car, args)
        for _ = 1, args.times do SetVehicleLights(car, 2) Wait(200) SetVehicleLights(car, 1) Wait(200) end
        SetVehicleLights(car, 0)
    end,
})
```

## Buttons and thing data: Whip.directorButton, GetDirectorThingData

### Whip.directorButton(id, def) — CLIENT
A button for a kind of placed thing on its page (Tools), in the world builder's bubble, or both. `id` `'<ns>.<name>'`.

| def key | Notes |
|---|---|
| `label` | ≤24, required |
| `kinds` | `npc vehicle prop spot groundItem container door route`, or `card` (fills a card's `entries` field) |
| `where` | `'page'`, `'bubble'`, `'both'` (default) |
| `takesOver` | Director steps aside (page hidden, mouse released) until `thing:back()`, your code throws, or your resource stops |
| `icon` | WHIP icon key ≤24 (as `AddAction`'s: `'turbo'`, `'lock'`) |
| `hint` | tooltip ≤120 |
| `press(thing)` | required; runs in its own thread |

`thing` = `{ id, kind, label, model, models, coords = {x,y,z,heading}, scenario, data, entity, builder }`: `data` = what you keep on it; `entity` the builder's copy while open (never for `takesOver`); `models` every model of a random vehicle (pressed for one: `model`). A thing not in the scenario yet is added first. For kind `'card'`: `thing.card = { type, field, entry (nil = new), value, props, world }`, and `thing:save(t)` keeps `t` as that entry (nil removes it).
- `thing:save(t)`: plain data, ≤4096 bytes of JSON (nil removes); an edit of the open scenario (Save keeps it, Ctrl+Z undoes). Saved under `world.def.ext[<resource>]`.
- `thing:back(t?)`: only for `takesOver`; saves `t` first, hands the screen back.
- Both return `true` / `false, reason` (`'that press is over'`, `'the Director is closed'`, `'data is 4096 bytes of JSON at most'`).
Returns `true`, or `false` (printed). `Whip.removeDirectorButton(id)`.

Your data comes back: `whip_core:run:thingMade` `data[GetCurrentResourceName()]`, `card:made(id).data`, `GetDirectorThingData(runIdOrKey, worldId)`, `check`'s `doc.data`, `whip_core:director:builderCopy` (client).
```lua
Whip.directorButton('mycafe.customise', { label = 'Customise', icon = 'turbo', kinds = { 'vehicle' }, takesOver = true,
    press = function(thing)
        local paint = OpenMyTuningScreen(thing.model, thing.coords, thing.data)   -- yours; waits
        thing:back(paint and { paint = paint } or nil)
    end })
-- server
AddEventHandler('whip_core:run:thingMade', function(e)
    if GetInvokingResource() ~= 'whip_core' then return end
    local mine = e.data[GetCurrentResourceName()]
    if e.kind == 'vehicle' and mine and mine.paint then PaintRunCar(e.vehicleId, mine.paint) end
end)
```

## Weapons: Whip.weapons / Whip.removeWeapons

### Whip.weapons(list, opts?) — SERVER CLIENT (one call in a file both sides load)
Add-on weapons beside GTA's in every WHIP weapon list (NPC Weapon, Hold a Weapon step, Fixed Weapons, Dungeon Mode, Object Viewer Give a weapon), shown as "Label (tag)". Server list decides what Check/runs accept; each game's what its editor offers.
- `list[n] = { name, label, group, model? }`: `name` `WEAPON_` + capitals/digits/`_` (≤64), never GTA's; `label` ≤40; `group` exactly one of `'pistol'`, `'smg'`, `'rifle'`, `'machine gun'`, `'shotgun'`, `'sniper'`, `'heavy'`, `'thrown'`, `'stun gun'`, `'melee'` (spaces as written); `model` a firearm's world model (never GTA's, unique) so it can be a Fixed Weapon.
- `opts.tag` ≤16 (default resource name). ≤200 weapons per resource.
- Calling again replaces your list. One bad entry refuses the whole list (printed). Returns `true` / `false`.
- An NPC given one carries the gun itself, never your item (your ammo/reload code is not on it). A scenario using one waits at server start until your resource adds it.
- `Whip.removeWeapons()` removes yours on that side.

## Object Viewer options: Whip.objectViewerOption

### Whip.objectViewerOption(id, def) — CLIENT
An option in the `/w` Object Viewer list (G on the picked target). `id` `'<ns>.<name>'`.
- `label` (≤48, required), `group` (heading ≤24, default resource), `tint` (`blue teal green amber red violet slate`, default slate), `hint` (≤160), `kinds` (`vehicle player npc object`), `whip` (`true` WHIP's own only: saved car, player; `false` game's only; nil both), `select(target)` (own thread; list closed).
- `target` = `{ kind, entity, netId, whip, vehicleId, serverId, model, name, coords = {x,y,z,heading} }`.
- Shown to people with dev tools on and to Dungeon Masters in Dungeon Mode: anything `select` asks of your server must check permission itself (`HasDevTools`).
- Returns `true` / `false` (printed). `Whip.removeObjectViewerOption(id)`; goes when your resource stops.

## Packs, Whip.scenario, Whip.template, export

### Shipping scenario files
```lua
-- fxmanifest.lua of your pack
whip_director_scenario 'scenarios/bank_job.json'
```
- Each file: a scenario document (`"format": 2`, ≤512 KB, `.json` inside the resource, no `..`), with `"key"` (2-64 `[%w_-]`; else `<resource>_<file>`) and `"requires": { "items": [...], "models": [...], "resources": [...], "cards": [...], "format": 2 }`. Items named in its world/cards count as required anyway; models are listed for the admin, not checked.
- Things with `"coords": "spot"` are placed by each server in a copy.
- Life: read when the resource starts (never run), checked, offered as pending to a Director admin (`/whip` → Director → Shipped). Accepted: a read-only scenario (Duplicate to change). Off while its resource is stopped, back on with it. Deleted (tombstoned): never offered again. A changed file (FNV-1a hash) is pending again; what was accepted stays until then.
- Trust: a Director admin may trust a resource once; its new/changed scenarios are accepted automatically when they pass Check and have what they need.
- DB: `director_packs` (`resource`, `file`, `scenarioKey`, `hash`, `status` pending/accepted/refused/deleted, `acceptedHash`, ...), `director_pack_trust`.

### Export (pack_exports folder)
Export as a pack (Director admin, on a scenario in `/whip`): writes `whip_core/pack_exports/<key>.director.json` (the active revision, else draft; `key` and `requires` filled; ≤512 KB; read back to verify) and `whip_core/pack_exports/<key>.fxmanifest.lua` (`fx_version 'cerulean'`, `game 'gta5'`, description, `whip_director_scenario 'scenarios/<key>.json'`). To ship: make a resource with that manifest and put the JSON at `scenarios/<key>.json`.

### Whip.scenario(key, doc) — SERVER
A scenario built in code, offered like a shipped file (pending until accepted or trusted), then read-only. Sent again on every whip_core restart; same scenario again changes nothing (canonical hash). `doc` copied 24 deep, ≤512 KB as JSON. Returns nothing (refusal printed). `RemoveDirectorScenario(key)` — SERVER: takes yours off the Shipped list (accepted stays stored); `true` / `false, reason`.

### Whip.template(name, doc) — SERVER
Adds a starting point to the editor's New list (`name` ≤60). `doc` must load as a format-2 document; `id`, `rev`, `key` are stripped. A builder's copy is theirs; a permission-gated card is refused in the copy. Returns nothing (printed). `RemoveDirectorTemplate(name)` — SERVER.

## Cards other WHIP resources add

| Resource | Cards / tasks / buttons |
|---|---|
| whip_phone | `phone.giveContact` Give Contact, `phone.sendText` Send Text, `phone.call` Phone Call (outcomes answered/hungup/declined/missed/busy/nophone; `timeout = 300`; `test = 'run'` rings only the tester; recording `@resource/file.ogg` or https link, mp3/ogg/wav) |
| whip_rope | `rope.make`, `rope.moveEnd`, `rope.rules`, `rope.remove`, `rope.goalTie`, `rope.goalHang`, `rope.whenPulled` |
| whip_autos | cards `autos.customise` (Goal: Customise Vehicle), `autos.forceOpen`; task `autos.openWhiplash`; buttons `autos.look` (Whiplash), `autos.exactWay`; Object Viewer option `autos.whiplash` |
| whip_gunny | `Whip.weapons(list, { tag = 'gunny' })` |

A minigame needs no card: register a skill check game (`Whip.skillCheckGame`) and it is a choice in the Skill Check card's Game field.

## Dungeon Mode (live mode)

- Permission `director.live` (full admins too). Open from `/whip` → Director → Dungeon Mode → Start Dungeon Mode, or `/w` Panels row (full admins).
- Put down props, NPCs, cars, Fixed Weapons; click yours to move, open Options (NPC attacks/follows/guards; Fixed Weapon fires) or Remove. Click a player: Spawn a car for them (key in their pocket), Send NPCs after them; anything else: Object Viewer options.
- Cars are made unlocked with no key; Dungeon car options set key location, Locked, Only its key opens it. Changed map props are hidden on every game until restart (Put back).
- Everything lasts until restart or removal, owned by account (only owner or full admin removes). Limits: 150 things and 20 effects per account, 600 and 80 for everyone (`live.lua:25`, `:650`). Logged as `dungeon_mode`.
- Refused for a Dungeon Master (greyed "Admins only"): making a car someone's, changing saved cars, player stats/movement/character editor, kick/ban, inventories/trunks/gloveboxes, entering a locked player car, changing ground items. Restore health/armour stay open.

## In /whip, the editor, dev commands, DB tables

- `/whip` → Director pages: Overview (7/14/30/90 days, tests left out), Scenarios (Active, Previous Versions + Restore, Duplicate, Open Editor, Start a run, Delete), Lore characters, Shipped, Live runs (Stop; file-loaded scenarios), Access, Dungeon Mode. A builder who isn't a full admin sees only the Director in `/whip`.
- Editor: world builder (Place, Configure, Blueprint); Fullscreen editor tabs Cards, World, Variables, Settings; Save, Test, Check. Auto-save every 5 minutes unless off (World tab). Exit discards unsaved placements (asks). Keys: R move/turn, G snapping, Ctrl+click multi-select; grid right-click add card, drag pin to wire, C comment box, Ctrl copy/paste/undo/save. During a Test the test map's Free camera (H for mouse), G hides the map; live runs light cards on the grid.
- Thing pages: Outfit (freemode NPCs can use the character editor), Tasks, Takes (recorded drives ≤3 min, trailers included; Ride along), Eye sight (guards: meter 2 s close, 8 s at full distance; sneaking halves the distance; server-computed), Routes, Physics.
- `/director` opens the editor (builders). `whip.devtools` + dev mode: `/director spot <worldId>`, `load <name>` (from `server/director/examples/<name>.json`: courier, steal_car, vault; not saved), `save <name>`, `on <key> [rev]`, `stop <key>`, `start <key>`, `list`, `scenarios`, `history <key>`, `abort <runId>`, `npctest <1-6|stop>`, `cards`, `events` (print every `SendDirectorEvent`). Builders: `send <event> [value]` into their own Test.
- Tables: `director_scenarios`, `director_revisions`, `director_runs`, `director_run_players`, `director_run_events`, `director_takes`, `director_lore`, `director_lore_portraits`, `director_packs`, `director_pack_trust`. If the store can't be built/read the Director switches off (`Director.off`; exports answer `'The Director is off: ...'`) and the rest of WHIP runs.

## Gotchas

1. A builder's Test sends no public events and is invisible to every export unless `{ tests = true }`; `whip_core:run:thingMade` is the exception (check `run.test`). `EndScenarioRun` is the only control export that accepts a Test.
2. Always check `GetInvokingResource() == 'whip_core'` in `run:*` handlers before paying; an ended run can't be confirmed with `GetScenarioRun`.
3. An `enabled` run starts with nobody in it: wait for `run:playerJoined` before treating it as a job in progress.
4. `StartScenarioRun` only works for modes `script` and `enabled`; for `enabled`, `opts.vars`/`opts.places` are refused.
5. `opts.with` silently drops ineligible or cooling-down crew (no error), and everyone beyond Team size.
6. `GetScenarioRunVar` returns `true, value` first: do not treat a `false` variable as failure.
7. `RemovePlayerFromScenarioRun`, `SwitchScenario`, `GetScenarioStats`, `TestDirectorCard`, `TestDirectorScenario` (unless `wait = false`) and `card:give/pay/charge` wait: call from a thread.
8. Event names and card/task/button ids share your namespace; the first running resource to use it owns it until it stops. Never use whip_core's (`npc.`, `player.`, `script.`, ...).
9. `SendDirectorEvent` is rate-limited (20/s per name, 60/s per resource); a Test never hears real events (use `/director send`).
10. Custom event cards fire once per run unless `event.once = false`; event cards keep a run alive (it won't end "with nothing left to wait for").
11. An outcome your `run` returns that the card doesn't have becomes Didn't work, and an unwired Didn't work faults the whole run. Answer only with your own outcomes; never `'timeout'`.
12. An instant card must not wait: `card:give/pay/charge` are refused; any other wait faults the run.
13. Take down `card:objective`/`card:clock` before you answer; they are removed automatically only when the card ends without your answer.
14. Never send `card.callId` to a client; only your resource can answer it anyway.
15. In a builder's Test your card is a stand-in (first outcome after 15 s) unless `test = 'run'`; with it, act only on `card.player`/`card.starter` (never page real police).
16. Tag anything you make for a run with `run.tag`/`card.tag`: it is removed at run end, and creates under a closed tag are refused.
17. Live-run items are the player's to keep; only test-stamped items (`metadata.director`) are ever taken back. Items a run's goal tracks carry `metadata.fromRun = runId`.
18. Whip.task's `run` may be replayed from its start when ownership of the entity changes: keep it idempotent and limited to the entity.
19. A `point` task field must have key `at`, a `target` field key `target`; props can't have custom tasks.
20. `thing:save` data is limited to 4096 bytes of JSON and is saved only when the builder saves the scenario.
21. `GetDirectorThingData(key, id)` only works while the scenario is switched on; use a run id otherwise.
22. Format 1 documents are refused: `Whip.scenario`/`Whip.template`/packs need `format = 2` (despite comments saying 1).
23. A scenario switched on by `SwitchScenario` reverts to the person's choice on reboot; a person switching it forgets the script's state.
24. Weapons: one bad entry refuses the whole `Whip.weapons` list; NPCs get the gun, not your item.
25. Exported packs land flat in `whip_core/pack_exports/` but the manifest line points at `scenarios/<key>.json`: move the file when building the pack resource.
26. Object Viewer options and Dungeon Mode actions reach the server from Dungeon Masters too: always re-check permissions server-side.
27. A scenario's runs stop starting while a custom card's resource is stopped; when it comes back with a different provider, a person must switch the scenario on again.

## Docs vs code

1. Scenario document format for `Whip.scenario`: `types/satellite.lua:256`, `lib/satellite.lua:1396` and `server/director/packs.lua:3` say "format 1"; `server/director/doc.lua:13` sets `DirectorDoc.FORMAT = 2` and refuses format 1. Docs (format 2) are right.
2. Run full size: docs say "a full run (16)"; code uses the scenario's Team size (`settings.teamSize`, 1-16, default 16) (`main.lua:1575`, `main.lua:1694`).
3. `RemovePlayerFromScenarioRun` "takes back what the run handed them": `effects.lua:304` only takes back test-stamped (`metadata.director`) items, and the export refuses Tests, so on live runs nothing is taken back (consistent with "live items are kept").
4. `GetDirectorCards` filter: docs list `{ category }`; code also accepts `owner` (`api.lua:556`).
5. `DirectorRunView` also has `variant = { id, name }` and `DirectorScenarioView` `variants` when a scenario has variants (`api.lua:63`, `api.lua:110`); undocumented.
6. `AddPlayerToScenarioRun` on an `enabled` run nobody has joined claims it (player becomes starter; `run:playerJoined.by` is nil) (`api.lua:416`, `main.lua:777`); undocumented.
7. `event.once` for custom event cards defaults to true (`cards_api.lua:299`); docs mark it optional without a default.
8. `TestDirectorCard`: at most 2 tests of your cards at once (`cards_api.lua:1379`); undocumented.
9. `TestDirectorScenario` result also carries `faultNode`, `made`, `players`, `steered`, `left`, `steerFailed`, `dropped` (`testing.lua:15`).
10. `Whip.objectViewerOption` label limit is 48 characters (`tools/ov_panel.lua:334`); docs give none.
