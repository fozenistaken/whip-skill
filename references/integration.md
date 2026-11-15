# Full WHIP integration: every surface a resource should plug into

A resource that only swaps framework calls still feels like a foreign script on a WHIP server. A resource
that is *integrated* shows up where WHIP's players and admins already look: its prompts look like WHIP's
prompts, its money appears on bank statements and ATMs, its settings sit in `/whip` → Settings, its staff are a
WHIP job, its events are in the Monitor, its actions are on each character's activity timeline, its doors are in
the Door Manager, its app is on the phone. This file is the checklist for that, for new resources and ports
alike. Each row names the surface, what the player or admin sees, and the call; details live in the topic
reference named in brackets.

Built from every topic reference in this skill and checked against `export-index.md`.

## Contents
- How to use this checklist
- 1. Lifecycle and identity
- 2. Security and the Monitor
- 3. Admin panel (/whip) and staff permissions
- 4. Developer tools (/w)
- 5. Economy: money, banks, business accounts, prices
- 6. Items, inventory and storage
- 7. The 3D world: prompts, wheel, props, doors, blips, zones, NPCs
- 8. Screens and UI
- 9. HUD, stats and vehicle gauges
- 10. Vehicles and garages
- 11. Jobs and duty
- 12. Phone, voice, chat
- 13. Director: missions and admin scripting
- 14. Persistence and data
- 15. Settings each player chooses
- Integration review: questions to ask of a finished resource

## How to use this checklist

1. List every feature of the resource (for a port: every file, event, command, table, UI and config block).
2. For each feature, walk the sections below and pick the WHIP surface it belongs on. A feature that has a
   WHIP surface and does not use it is a defect, not a style choice.
3. Delete what WHIP already does (anti-exploit distance checks, cooldown tables, key scripts, duty toggles,
   stash registration, webhooks used as audit logs, framework bridges).
4. What WHIP genuinely lacks stays your own code, built on WHIP primitives (SecureEvent, stores, prompts,
   `EnsureTable`) and exposed back through WHIP surfaces (configPage, dev page, phone module, Director card).
5. Run `scripts/whip_scan.py` and walk "Integration review" at the end.

## 1. Lifecycle and identity  [core-concepts.md, players-stats-hud.md]

| Need | Surface | Call |
|---|---|---|
| Start with WHIP, restart with it | manifest | `dependency 'whip_core'`, `whip_requires '1.0'`, `'@whip_core/lib/satellite.lua'` first in shared_scripts |
| Update notices for owners | setup report | `whip_updates 'you/repo'` |
| Declarations that survive a whip_core restart | — | `Whip.register(function() Whip.core:… end)` |
| One clean console line | console | `Whip.sayStarted()`, problems via `Whip.startProblem` |
| Who is this | — | `GetPlayer(source)`; store `player.charId`, never a server id |
| Names for offline people | — | `GetCharacterNames(charIds)`, `GetPlayerFullName(source)` |
| Facts about a character | — | `SetPlayerFlag` / `GetPlayerFlag` (online), `SetPlayerMetadata` / `GetPlayerMetadata` |
| Player ready / leaving | events | `whip_core:player:loaded`, `whip_core:player:logout` (events-and-data.md) |
| Still the same character after a wait | — | `IsSessionCurrent(source, player.session)` |
| Send them to the character screen | — | `LogoutPlayer(source)` |

## 2. Security and the Monitor  [security.md]

Every message from a game is a `SecureEvent` or `SecureCallback` with `params`, `rateLimit`, `near` (and
`ace`/`permission` where staff-only). Each call then appears in `/whip` → System → Monitor, accepted or refused
with the reason, with no extra code. Commands are `Whip.command(name, { ace | dev | whileDead | rateLimit }, fn)`.
Client asks with `TriggerServerEvent` (no values the server should decide) or `Callback(name, …)`.

## 3. Admin panel (/whip) and staff permissions  [server-ops-devtools.md, security.md]

Using WHIP's primitives is what puts your data in the admin panel. Hand-made tables do not appear there.

| What admins should manage | Lands in | Call |
|---|---|---|
| Your settings (prices, distances, toggles, positions, lists) | `/whip` → Settings → your page | `Whip.configPage({ label, settings | groups })` in a shared file; `sides = 'server'` for secrets; `Whip.onConfigChanged(path, fn)` |
| Staff roles that are not jobs (realtor admin, moderator) | Player Manager → Permissions | `RegisterPermission('myres.admin', { label, grantedBy })`, check `HasPermission(source, name)` or schema `permission = …` |
| Your items | Economy → Items (owner shown) | `RegisterItem` |
| Your stashes | Economy → Containers | `EnsureContainer` |
| Your shops | Economy → Shops | `EnsureShop` |
| Your staff | Economy → Jobs | `EnsureJob` |
| Your doors | Doors (in your folder) | `EnsureDoors` / `EnsureDoor` (managed) |
| Your areas | World → Zones | `EnsureZone` |
| Who did what | each character's activity timeline | `LogActivity(source, event, opts)` |
| Your errors | Monitor / `GetErrorLog` | automatic through the satellite's error tap |

## 4. Developer tools (/w)  [server-ops-devtools.md]

| Need | Call |
|---|---|
| Admin/setup tools (calibrate, photograph, clear, teleport to X) | `RegisterDevPage(id, def)` (client) + `RefreshDevPage`; check `HasDevTools(source)` on the server for each action |
| A debug overlay switch | `RegisterDebugTool` |
| An option on a prop in the Object Viewer | `Whip.objectViewerOption(id, def)` |
| Measure a per-frame loop | `WhipCost` (`@whip_core/lib/cost.lua`) |

Replace admin chat commands (`/myadmintool`) with dev-page rows where they are tools rather than gameplay.

## 5. Economy: money, banks, business accounts, prices  [money-banks.md]

| Need | Call | Shows up as |
|---|---|---|
| Charge a player | `ChargePlayer(source, amount, { method, reason })` → receipt | cash taken / bank statement line with your `reason` |
| Undo after failure | `RefundPlayer(receipt)` (30 min) | statement line |
| Pay a wage, reward, refund later | `PayPlayer(who, amount, { method = 'bank', reason })`; `{ charId = n }` reaches offline players | statement line |
| Takings belong to a business | the job's business account: `GetJobBankAccounts(job)`, then `BankSystemDeposit` / `BankSystemTransfer` | business statement, owners see it at ATMs and in the bank |
| Recurring billing while offline (rent, loans) | `GetDefaultBankAccount({ charId = n })` + `BankSystemWithdraw` (no overdraft: balance can never go below 0) | statement line |
| Deposits held, then settled | `HoldMoney` / `SettleMoneyHold` | held money |
| Your own ledger rows with a money/item change | `CommitWithAction` | one transaction |

Cash is the `cash` item: never keep a cash number of your own. Do not run a second economy (own accounts,
own balances); put money in WHIP's bank and read it from there.

## 6. Items, inventory and storage  [inventory-items.md, stores-containers-panels.md]

| Need | Call |
|---|---|
| An item with a picture | `RegisterItem(key, def)` + `html/img/items/<key>.webp` listed in `files {}` |
| Using it (bar, anim, prop, server-timed) | `RegisterUseHandler(key, { label, duration, anim, prop, disable, onComplete })` |
| Extra right-click option on an item | `AddItemOption` / `RegisterContextAction` |
| Storage anywhere (furniture, mailbox, locker) | `EnsureContainer` + `OpenStore(source, addr)` |
| Storage with your own rules | `RegisterStoreKind(kindId, def)` |
| Items inside an item (wallet, case) | `RegisterPanelItem` |
| Move items anywhere | `StoreMove(from, to)` (one transaction) |
| Give to someone offline | `GiveOnLogin({ charId = n }, item, n, meta, { reason })` |

## 7. The 3D world  [interactions.md, world-zones-time-npcs.md, jobs-shops-properties-doors.md, ui-nui-camera.md]

| Need | Call |
|---|---|
| Something to press at a spot, on an entity, on every prop of a model, on a car part | `AddAction({ at = { coords | entity | model | vehiclePart | aimBox }, label, icon, options, require, canInteract, reach, holdMs, style })` |
| An entry on the F1 wheel | `AddAction` with a wheel `at` (interactions.md) |
| Server-placed points everyone sees | `AddPoint` (server) |
| A map marker or route | `ShowBlip(audience, id, { coords, label, sprite, color, route })`. WHIP's own pause map and radar show any native blip, but only `ShowBlip` blips keep their name, and radius circles show on neither (porting-playbooks.md → blips) |
| An area that reacts | `EnsureZone` (server, `trackPlayers`) / client zones |
| A person standing there, talking | `SpawnNpc`, `StartConversation` |
| Props placed for a scene | `ShowPropSet` / `HidePropSet` |
| A real door that locks | `EnsureDoors` (permanent, managed) or `HoldDoor` + `SetHeldDoorAccess` (temporary) |
| Something held in the hands | `HoldProps` (server) |
| Text over a spot | `ShowPlayerText` |
| A screen in the world | DUI (ui-nui-camera.md) |
| Weather/time per player (indoors, a vision) | `SetPlayerWeatherLayer` / `ClearPlayerWeatherLayer` |

Use WHIP's glyph names for `icon` and its prompt styles, so your prompts are indistinguishable from WHIP's.

## 8. Screens and UI  [ui-nui-camera.md]

| Need | Call |
|---|---|
| Toasts | `NotifyPlayer` (server) / `Notify` (client), or `return false, 'why'` from a SecureEvent |
| A bar that gives something at the end | server `Progress(source, opts)` (never a client bar) |
| A skill check | `SkillCheck` (server or client); custom game `Whip.skillCheckGame` |
| A form, a yes/no | `Input`, `Confirm`, `Alert` |
| Your own NUI page | `SetScreenOpen(true, key)` instead of `SetNuiFocus`; `BlockControls`; `FreeHands`; WHIP's `--ui-*` tokens and `caps.js` so it matches the theme |
| React before WHIP acts on the player | `RegisterClientHook` |
| Gamepad | `Whip.padScreen` for your screen |
| A camera shot | the camera API (`PlayCamera`, sequences) |

Only one screen is open at a time; WHIP's dialogs know about yours only if you asked for the screen.

## 9. HUD, stats and vehicle gauges  [players-stats-hud.md, vehicles-garages.md]

| Need | Call |
|---|---|
| A need/meter on the HUD (stress, drunk) | `RegisterStat` + `AddStat` / `SetStat`; listen `OnStatChanged` |
| A gauge on a car (charge, oil) | `RegisterVehicleStat`, `OnVehicleStatChanged`, `WatchVehicleStat` |
| Health / revive | `RevivePlayer`, death events |

## 10. Vehicles and garages  [vehicles-garages.md]

Job and rental cars: `SpawnTempVehicle(model, coords, { forSource, despawnAfter, tag })` (key included, goes
with your resource). Owned cars: `CreateOwnedVehicle`, keys `GiveVehicleKey`, data `SetVehicleData`, looks
`SetVehicleAppearance`. Boot and glovebox are stores (`{ kind = 'vehicle', id, sub = 'trunk' }`).

## 11. Jobs and duty  [jobs-shops-properties-doors.md]

Staff = `EnsureJob(key, { name, roles })`; per-action rules = role permissions checked with
`HasJobPermission`; on duty = `IsPlayerClockedOn` / client `LocalPlayer.state.whipJob`; players clock on in the
phone's Business app or your `ClockOn` prompt. The job's business account is where its money goes (§5).

## 12. Phone, voice, chat  [phone-chat-loadingscreen.md, voice.md]

| Need | Call |
|---|---|
| An app on the Duo phone | `exports.whip_phone:RegisterModule({ id, script })` + `SecureCallback('<res>:<action>', { params = { { 'args', 'any' } } }, fn)` |
| Calls, radios, speakers | `Whip.voice(name, …)` after `Whip.voiceSystem()` |

## 13. Director  [director.md]

Expose your feature to admins' no-code missions: `Whip.card` (a card that does your thing), `Whip.task`,
`Whip.directorButton`, `Whip.scenario`. Tag what a run creates (`{ tag = … }`) and `ReleaseTag` it.

## 14. Persistence and data  [core-concepts.md]

`EnsureTable(name, createSql, migrations)` instead of shipping `.sql`; `CommitWithAction` for rows that go with
an item or money change; keys are `charId`, never citizenid/identifier/server id.

## 15. Settings each player chooses  [server-ops-devtools.md]

`Whip.playerSetting({ key, … })` puts a row on the pause menu's Server Settings page (volume, units, toggles).

## Integration review: questions to ask of a finished resource

- [ ] Does any feature still use its own target, menu, notify, progress, input, stash, key, fuel, garage, door, weather, HUD or banking code?
- [ ] Does every prompt use `AddAction` with WHIP glyphs, and does every staff-only option have `require` AND a server check?
- [ ] Does all money go through `ChargePlayer` / `PayPlayer` / bank exports with a readable `reason`, and do business takings land in the job's account?
- [ ] Is every admin-editable value on a `Whip.configPage`, and every admin tool on a dev page or behind a `RegisterPermission`?
- [ ] Are the resource's items, containers, shops, jobs, doors and zones made with `Ensure…`/`Register…` so they show in `/whip`?
- [ ] Does every meaningful action call `LogActivity`?
- [ ] Is there a phone module for anything a player checks from afar (balances, listings, status)?
- [ ] Do own NUI pages ask for the screen (`SetScreenOpen`) and use WHIP's tokens?
- [ ] Does a whip_core restart, a logout mid-action and a resource stop all clean up (Whip.register, `IsSessionCurrent`, tags)?
- [ ] Does `whip_scan.py` report nothing above LOW?
