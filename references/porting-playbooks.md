# Porting playbooks: common script types, and a worked case

`porting-to-whip.md` maps calls. This file maps whole *kinds* of script: for each one, what WHIP already owns
(delete it), what stays yours (rebuild it on WHIP primitives), which WHIP surfaces it must use to feel native
(`integration.md`), and the traps met in practice. It ends with a full worked port of a real housing resource.

Every export named here is in `export-index.md`. Check options in the topic reference before writing code.

## Contents
- The porting procedure (summary)
- How to present a port plan to the user
- Playbook: shops and stores
- Playbook: job resources (duty, boss menu, job garage, payroll)
- Playbook: police
- Playbook: EMS / ambulance
- Playbook: mechanic and tuning
- Playbook: vehicle shop / dealership
- Playbook: garages, keys, fuel, impound
- Playbook: housing and apartments
- Playbook: crafting, processing, drug labs
- Playbook: robberies and heists
- Playbook: gathering (fishing, mining, farming, hunting)
- Playbook: HUD, status, needs
- Playbook: banking, ATMs, billing and invoices
- Playbook: phone apps, MDT, tablets
- Playbook: admin menus and staff tools
- Playbook: gangs and territories
- Playbook: clothing, barber, tattoo shops
- Playbook: licences, IDs, documents
- Playbook: doorlocks, elevators, teleports
- Playbook: blips, map markers, routes, waypoints
- Playbook: chat, emotes, radial menus, notifications
- Worked case: a shell-based housing resource (QBCore/Qbox) on WHIP

## The porting procedure (summary)

1. Inventory the resource: its manifest, bridges, events, callbacks, exports, commands, tables, config, NUI and dependencies.
2. Run `scripts/whip_scan.py <res> --mode port --plan` to get a work list grouped by WHIP surface.
3. Classify every feature into one of three groups:
   - **WHIP owns it**: delete it.
   - **WHIP has a primitive for it**: rebuild it on that primitive.
   - **WHIP lacks it**: keep it, on WHIP primitives, and expose it on WHIP surfaces.
4. Present the plan to the user, using the shape below, before you write code.
5. Rewrite in this order:
   - manifest and `Whip.register`
   - identity and DB
   - SecureEvent and SecureCallback
   - money
   - items and stores
   - world
   - UI
   - admin, settings and logs
   - phone and Director
   - logout and restart edge cases
6. Run `whip_scan.py <res>` in review mode until nothing above LOW remains. Walk the checklists in
   `porting-to-whip.md` and `integration.md`.

## How to present a port plan to the user

1. **Verdict.** One paragraph: does WHIP already own this kind of script? Then the split: what moves onto
   WHIP and what stays.
2. **Delete list.** Bridges, guard and cooldown code, framework detection, the dependencies it no longer needs.
3. **Area table.** One row per feature area, showing "today" → "on WHIP" and naming the surface (world,
   admin, economy, inventory, UI, phone, Director).
4. **Traps.**
   - Behaviour WHIP cannot copy, for example an overdraft when the bank forbids it.
   - Missing exports.
   - Position saves, buckets, logout.
5. **Size and order.** Scanner counts and the rewrite order.

Do not edit the user's files when they only asked how a port would work.

## Playbook: shops and stores
- **WHIP owns:** shops (`EnsureShop`: unlimited, player-run stock, server's own), catalogues (`AddCatalogItem`,
  `RemoveCatalogItem`), staff and counters, basket and checkout, and charging. Shop money goes to the job's
  business account.
- **Delete:** shop NUI, price tables in config, item-box popups, cash checks.
- **Keep:** special shops with your own rules (black market, rotating stock). Build them on `EnsureShop`, plus a
  `Whip.configPage` `records` setting for stock and prices.
- **Surfaces:** `/whip` → Economy → Shops; prompts at the counter; prices editable in game.
- **Trap:** `CreateShop`/`UpdateShop` do not resolve job keys or check `mode`; use `EnsureShop`
  (jobs-shops-properties-doors.md, Docs vs code).

## Playbook: job resources (duty, boss menu, job garage, payroll)
- **WHIP owns:**
  - jobs, roles and levels, and per-role permissions (`EnsureJob`, `HasJobPermission`)
  - hire and fire, and clock on/off (phone Business app, `ClockOn`/`ClockOff`, `IsPlayerClockedOn`, `GetClockedOnEmployees`)
  - the business bank account (`GetJobBankAccounts`)
- **Delete:** duty toggles, boss menus (hire/fire/grades/society money), `QBCore.Shared.Jobs`, society scripts.
- **Rebuild:**
  - Job vehicles: `SpawnTempVehicle(model, coords, { forSource, despawnAfter, tag })`.
  - Job stash: `EnsureContainer` with a job requirement.
  - Job shop: `EnsureShop` with `job`.
  - Payroll: `PayPlayer` or `BankSystemTransfer` from the business account, with a `reason`.
- **Surfaces:** prompts with `require = { job, onDuty = true }` AND a server check; `ShowBlip` to `{ job = 'x', onDuty = true }`.
- **Trap:** a level-100 role passes `HasJobPermission` for any permission name, typos included.

## Playbook: police
- **WHIP owns:**
  - escorting (Left/Right arrows; `IsEscorting`, `IsBeingEscorted`, state bags `whipEscorted`/`whipEscortedBy`)
  - lockpicking of doors
  - impound state on vehicles (the admin Vehicle Manager)
  - weapons (whip_gunny)
  - the radio (whip_voice)
  - armoury as a job shop, evidence as a container
- **WHIP lacks:** cuffs, jail and prison, MDT, dispatch, fines and bills, evidence collection, GSR. Keep these and rebuild them:
  - **Cuffs:** SecureEvent with a `'player'` param (target near, same bucket). Server-owned state: `RegisterSentinelKey({ key = 'mypd_cuffed', family = 'player' })` and `SetSentinelPlayerKey`. Block their actions with your own checks plus `BlockControls` on their client.
  - **Jail:** a zone (`EnsureZone`) plus a player flag (`SetPlayerFlag`) for remaining time, restored on `whip_core:player:loaded`.
  - **Dispatch:** `ShowBlip({ job = 'police', onDuty = true }, id, { coords, label, route })` plus `NotifyPlayer` to `GetClockedOnEmployees('police')`. A dispatch voice channel: `Whip.voice('OpenLine', { track = 'radio', minMembers = 1, … })`.
  - **Fines:** `ChargePlayer(target, amount, { method = 'bank', reason = 'Fine: …' })`, then `BankSystemDeposit` into the police business account.
  - **MDT:** a whip_phone module, or your own NUI with `SetScreenOpen`. Records go in `EnsureTable` tables keyed by `charId`.
- **Surfaces:** `LogActivity` on the officer and the suspect for every arrest, fine and search; Director cards for "arrest the crew".

## Playbook: EMS / ambulance
- **WHIP owns:** death and downed state, respawn, revive (`RevivePlayer`), health and armour stats, and effects (`ApplyEffect`).
- **Delete:** death screens, `isdead` metadata, hospital respawn scripts, laststand.
- **Rebuild:**
  - Hold the respawn while EMS comes: `HoldRespawn(source, 'myems', 'An ambulance is on its way')`, then `ReleaseRespawn`.
  - Treat a patient: SecureEvent with a `'player'` param (target near), server `Progress`, then `RevivePlayer`, or `AddStat(source, 'health', n, reason)`.
  - Bill the treatment as in Police → Fines.
  - Check-in desk: an `AddAction` prompt at the desk, SecureEvent `near`, `ChargePlayer`, then `RevivePlayer`.
- **Trap:** `RevivePlayer` revives where they lie with full health and no armour. For a hospital bed scene,
  move them first.

## Playbook: mechanic and tuning
- **WHIP owns:** customisation, turbo and nitrous (whip_autos, Whiplash), repair and damage state (`ClearVehicleDamage`), vehicle data and stats.
- **Delete:** LS Customs clones, nitrous scripts, damage-save scripts.
- **Rebuild:**
  - Mechanic repair job: an `AddAction` with `at = { vehiclePart = 'hood' }` (car-part list in interactions.md) with `require = { job = 'mechanic', onDuty = true }`, then SecureEvent, server `Progress`, `ClearVehicleDamage`, and `ChargePlayer` the customer to the business account.
  - Parts as items: `RegisterItem` plus `RegisterUseHandler`.
- **Trap:** a car's look is saved with `SetVehicleAppearance` (server), never only with client properties.

## Playbook: vehicle shop / dealership
- **WHIP owns:** owned vehicles (`CreateOwnedVehicle`), prices (`SetVehiclePrices`), the catalogue (`GetVehicleCatalog`), keys, garages, and whip_dealership.
- **Rebuild:** a custom showroom calls `ChargePlayer`, then `CreateOwnedVehicle`. If creation fails, `RefundPlayer(receipt)`. Previews go through `HoldVehicleAppearance` (client; always release it).
- **Trap:** `CreateOwnedVehicle` also returns a third value, `saved`, which the stubs do not mention.

## Playbook: garages, keys, fuel, impound
- **WHIP owns all of it:**
  - garages: `CreateGarage`, `SetVehicleGarage`, `RetrieveVehicle`
  - keys as items: `GiveVehicleKey`
  - fuel: whip_fuel's `'fuel'` vehicle stat
  - impound state
- **Delete:** the whole resource. Port only unusual rules, for example a paid valet: a prompt plus `ChargePlayer`
  plus `RetrieveVehicle`.
- **Trap:** the `impounded` state is set only by the admin Vehicle Manager, and `RetrieveVehicle` refuses it. For a
  player-run impound, use an impound garage key instead.

## Playbook: housing and apartments
- **WHIP owns:** Properties.
  - MLO homes are templates with units and placements.
  - Buying happens at an outside sign; there are keys, the furnisher, stash furniture, interior themes, a private garage, and spawn choices.
  - Packs: `RegisterPropertyPack`.
- **WHIP lacks:** shell (instanced) homes, rent and leases, a realtor workflow, knocking and peepholes, warrants and offices.
- **Choose:**
  - **(a) MLO homes:** become WHIP Properties. Ship a property pack, or let admins create them.
  - **(b) Features WHIP lacks:** stay in your resource, built on WHIP primitives.
    - rent through bank system withdrawals
    - realtors as a job
    - doors through `EnsureDoors`
    - storage through `EnsureContainer`
  - To read a character's WHIP homes: `GetCharacterProperties`, `HasPropertyAccess`.
- See the worked case at the end.

## Playbook: crafting, processing, drug labs
- **WHIP has primitives:**
  - the bench: an `AddAction` prompt (or `at = { model }` on a prop)
  - SecureEvent with `near`, server `Progress` and `SkillCheck`
  - item exchange in one action
  - recipes on a `Whip.configPage` `records` setting
  - lab access by job, item or zone
- **Rebuild:** in the handler, check inputs (`HasItem`, `GetItemCount`), then `Progress`, then `IsSessionCurrent`, then `RemoveItem` each input, then `AddItem` the output. WHIP writes everything one action changed in one transaction.
- **Surfaces:** the timed use on items (`RegisterUseHandler` table); a `RegisterStat` "skill" meter if the script levels up; `LogActivity` for each craft.
- **Trap:** never trust a recipe id or a count from the client beyond an id the server looks up.

## Playbook: robberies and heists
- **WHIP owns:** the Director (no-code missions with cards, runs, teams, objectives, outcomes) and run tags (`ReleaseTag`).
- **Prefer:** make the heist a Director scenario. Add custom cards (`Whip.card`) only for the steps WHIP lacks.
- **If code:**
  - vault: `HoldDoor` + `SetHeldDoorAccess`, then `ReleaseDoor`
  - guards: `SpawnNpc({ behaviour = 'guard' }, { tag })`
  - loot: `StoreGive` into a container, or `AddItem`
  - police alert: `ShowBlip({ job = 'police', onDuty = true }, …)`
  - getaway car: `SpawnTempVehicle(…, { tag })`
  - cooldown: your own table keyed by the place, not by player
  - finally `ReleaseTag(tag)` to remove everything
- **Trap:** a store robbery's "register" must be checked on the server with `near`. A client-triggered payout event is the classic exploit.

## Playbook: gathering (fishing, mining, farming, hunting)
- **Rebuild:**
  - spots: an `AddAction` with `at = { model = 'prop_rock_…' }` on every prop of a model, or `EnsureZone` areas
  - the tool: an item with a timed use
  - server `Progress` + `SkillCheck`, then `AddItem` the result
  - spot positions: `Whip.configPage` `records` with `widget = 'mapPoints'`, so admins drag spots on the map
- **Surfaces:** a `RegisterStat` for the skill level; selling through `EnsureShop`, or a buyer NPC (`SpawnNpc` + prompt).
- **Trap:** depletion state lives on the server, keyed by spot. Respawn timers survive with `EnsureTable` if they must outlive restarts.

## Playbook: HUD, status, needs
- **WHIP owns:** the HUD, minimap, health, armour, hunger, thirst, oxygen, voice light, vehicle HUD, stat displays and theme.
- **Delete:** standalone HUDs, esx_status, qb-hud, ps-hud.
- **Rebuild:** extra needs (stress, drunk) through `RegisterStat`, read with `OnStatChanged`. Timed buffs through `ApplyEffect`. The look through WHIP theming, never a second HUD.

## Playbook: banking, ATMs, billing and invoices
- **WHIP owns:** banks, personal, savings, shared and business accounts, ATMs, statements and transfers.
- **Delete:** qb-banking, okokBanking, Renewed-Banking, esx_society.
- **WHIP lacks:** invoices. Rebuild them:
  - an invoice table (`EnsureTable`, `charId`, job, amount, status)
  - creation: SecureEvent with a `'player'` param (target near) and a job permission
  - payment from a phone module or a prompt: `ChargePlayer(source, amount, { method = 'bank', reason = 'Invoice #n' })`, then `BankSystemDeposit` into the job account, plus `CommitWithAction` for the invoice row
- **Trap:** balances never go below 0 (DB constraint). Any "allow overdraft" policy must change.
- **Custom ATMs** (DUI screens, card + PIN; ported and tested: an `osm-atmdui`-style resource):
  - WHIP puts its own ATM prompt on every model in whip_core's `Config.AtmProps`, and it has no settings-page
    entry. Ask the user, then set `Config.AtmProps = {}` in whip_core's `config.lua` (back it up first), or
    split the models between the two.
  - Bind each card to one account (`GetDefaultBankAccount` at issue). Withdraw with `BankWithdraw` then
    `PayPlayer` (cash). Deposit with `ChargePlayer` (cash), then `BankDeposit`, refunding on failure. Transfer
    with `BankTransfer` to `GetBankAccount({ number = 'WB-######' })`: a keypad types only the six digits.
    The bank's permission, frozen-account and own-character rules then apply by themselves.
  - Never store a PIN in item metadata: the holder's game sees it. Keep a hash in your own table
    (`GetPasswordHash` / `VerifyPasswordHash`, server natives), with the lockout server-side.
  - A correct PIN opens a server-side session (card, account, expiry, `charId`). Withdraw/deposit/transfer
    callbacks take amounts only. End the session on Esc and on `whip_core:player:logout`.
  - After `BankWithdraw` waits, check `IsSessionCurrent` before paying the notes; otherwise put the money back
    with `BankSystemDeposit`.
  - The camera mode takes the screen with `SetScreenOpen(true, 'atm')` in place of a HUD toggle event.
  - An `AddAction` with `at = { model = … }` puts the prompt at the prop's origin: for an ATM that is its base,
    inside the mesh (seen in game). Give `offset` (x across, y out of the face, z up), `heading`, and a
    `perModel` entry per model. For ATMs, reuse whip_core's `Config.AtmBadgeOffset` figures, for example
    `prop_atm_01 = { offset = vector3(-0.05, -0.20, 1.10), heading = 180.0 }`. `/actionplace <id>` aims one in
    game.
  - DUI option labels beside physical side keys: one fixed row grid does not line up on every model. The keys
    sit in front of a recessed screen, so from the scripted camera each side lines up at a different height
    (seen in game: left rows about 9% lower than right). Send row centres per model and per side with the
    model message, and add a dev command that shows the slots and moves them live, printing the config line.
  - Map props spawned for show (cash, card) are local: `CreateObject(..., false, false, false)`.
  - WHIP's ATMs have no server-known positions, so `near` cannot check that the player is at an ATM. Rate
    limits, the PIN session and the bank's own rules carry the security instead.

## Playbook: phone apps, MDT, tablets
- **WHIP owns:** the Duo phone (whip_phone). Every app is a module.
- **Rebuild:** each app becomes a module (`exports.whip_phone:RegisterModule({ id, script })`). Requests become `SecureCallback('<res>:<action>', { params = { { 'args', 'any' } } }, fn)`. Keep the `params` line, or `args` never arrives.
- **Delete:** apps written for lb-phone, qb-phone, npwd or gksphone.

## Playbook: admin menus and staff tools
- **WHIP owns:** `/whip` (players, bans, items, vehicles, economy, world, Director, Monitor, settings) and `/w` (noclip, coords, object viewer, overlays).
- **Delete:** qb-adminmenu, vMenu-style tools.
- **Rebuild:**
  - custom tools: `RegisterDevPage` rows (client), each server action checked with `HasDevTools(source)`
  - staff roles: `RegisterPermission` (granted in Player Manager)
  - settings: `Whip.configPage`
  - commands: `Whip.command(name, { dev = true } | { ace = '…' } | …)`

## Playbook: gangs and territories
- **WHIP lacks gangs.** A gang is a job (`EnsureJob`), with a business account as the gang bank.
- **Territories:** `EnsureZone` with `trackPlayers`; control points as prompts; wars as Director scenarios.
  Protect gang state bags with `RegisterSentinelKey`.

## Playbook: clothing, barber, tattoo shops
- **WHIP owns:** the appearance editor (character creator), saved outfits and tattoos.
- **Gap:** no export to open the clothing editor for a shop was found in `types/*.lua`. Check the current
  source before promising a clothing-store port. Otherwise keep the store and save looks only with what WHIP
  exposes (`SanitizeAppearance` validates an appearance table).

## Playbook: licences, IDs, documents
- **Rebuild:**
  - a fact on the character: `SetPlayerFlag(who, 'mydmv_driving', true)`
  - a physical card: an item with metadata (`AddItem(source, 'mydmv_licence', 1, { name, class })`)
- **Trap:** metadata is visible to the holder's game. Never put secrets there.

## Playbook: doorlocks, elevators, teleports
- **WHIP owns:** doors (`EnsureDoors`, managed in its own folder; requirements by job, item, charIds or property; lockpick; autolock).
- **Delete:** qb-doorlock, ox_doorlock, nui_doorlock.
- **Rebuild:** elevators and teleports are prompts with options (one per floor), then a SecureEvent with `near`, then a server teleport.

## Playbook: blips, map markers, routes, waypoints

WHIP replaces GTA's pause map and radar with its own renderers: the 3D pause map from `whip_media_map`, and the
minimap tiles. The world and its coordinates are GTA's, unchanged, so no coordinate in a ported script changes.

How the maps get their markers, from source:
- `client/pause.lua` `readBlips()` and `client/minimap.lua` `scanBlips()` read every native GTA blip on this
  client: sprites 0-1000 through `GetFirstBlipInfoId`/`GetNextBlipInfoId`. So `AddBlipForCoord`,
  `AddBlipForEntity` and so on, from any resource, appear without porting.
  - The radar spreads the scan over frames and measures it with WhipCost.
  - The radar shows colour, short range, rotation and flashing.
- **Names do not carry over.** GTA lets nothing read back a blip's name. A blip WHIP did not make shows its
  sprite's default name on the pause map. Only blips from WHIP's `ShowBlip` keep their label
  (`WhipBlipLabel`, `client/blips.lua:18`).
- **Area circles are not drawn.**
  - Sprites 4, 5, 9 and 10 (the wanted and area circles, i.e. `AddBlipForRadius`) are skipped by both maps.
  - So are sprites 6, 7, 161, 163 and 164 (noise and status rings).
  - The waypoint (8) is read separately (`GetFirstBlipInfoId(8)`).
  - A script that shows zones as radius circles (drug areas, territories, search areas) shows nothing on
    WHIP's maps. Even `ShowBlip`'s `radius` makes a GTA area blip that these maps skip.
- **Hidden displays are skipped:**
  - pause map: display 0, 5 and 9 (radar-only)
  - radar: 0, 1 and 7
- **Routes work.**
  - `SetBlipRoute` and the waypoint route are read from GTA's GPS (`GetPosAlongGpsTypeRoute`, slots 0 and 1)
    and drawn as a line.
  - `ShowBlip(..., { route = true })` and `SetPlayerWaypoint` are the server-side ways.
- **Unplaced blips:** a blip GTA gives no position (NaN; often attached to an entity this client cannot see) is
  left off. It is printed once in F8: `[whip_core:pause] a blip GTA gives no position (NaN) is left off the map`.

Porting rule:
- Point markers work as they are. Port them to `ShowBlip(audience, id, { coords, label, sprite, color,
  shortRange, route })` from the server anyway, because that gives:
  - their names on the map
  - audiences by person, `{ charId }` or `{ job, onDuty }`, re-sent on login and cleared on logout
  - cleanup when the resource stops or its run tag is released
  - no client loop
- Zones shown as radius circles need another form on WHIP: a point blip at the centre with a label, plus
  `EnsureZone` for the logic. Tell the user the circle itself will not show.
- Do not draw your own map overlay to compensate. The pause map and radar are WHIP's screens.

## Playbook: chat, emotes, radial menus, notifications
- **WHIP owns:** whip_chat, the emote menu (F1 wheel), the radial menu (`AddAction` wheel entries), notifications and text UI.
- **Delete:** dpemotes, rpemotes, qb-radialmenu, notify resources.
- **Trap:** whip_chat has no `provide 'chat'`, so old `exports.chat:addMessage` calls break: change them to `exports.whip_chat:addMessage`, or use the stock chat events, which need no change (phone-chat-loadingscreen.md).

## Worked case: a shell-based housing resource (QBCore/Qbox) on WHIP

**Source:** a commercial-style housing resource, about 17,600 lines. It has:
- bridges for qb and qbx, ox and qb targets, ox and qb inventories
- about 70 `lib.callback`s, 12 tables, its own NUI panel and decor editor
- shells spawned above the door in a routing bucket (`50000 + houseId`)
- rent with offline billing and four unpaid-rent policies, keys, knocking, a peephole, warrants, offices, beds that log you out, wardrobes and a Discord webhook

The scanner's port pass found 88 points. The largest groups were 27 callbacks, 18 locale calls and 5 citizenids.

**Verdict.** Split it:
- Shell homes, listings, rent, realtors, knock and peephole, and warrants stay in the resource, as a WHIP
  satellite.
- Ownership-adjacent concerns move to WHIP primitives.
- MLO homes stay WHIP Properties, read for "my homes".

**Area map.**

| Today | On WHIP |
|---|---|
| `bridge/*` (framework, target, inventory), `guard.lua` | Deleted |
| `lib.callback.register` × ~70 + `Guard.Shape/Cooldown/Near` | `SecureCallback` with `params`, `rateLimit`, `near` (the door as a function) |
| `citizenid` columns | `charId` INT; `EnsureTable` with migrations; no `install.sql` |
| Realtor job + grade + `Config.Realtor.can[action]` | `EnsureJob` with roles; per-action role permissions via `HasJobPermission`; `IsPlayerClockedOn` |
| Admin ACE | `RegisterPermission('myhousing.admin')` |
| Admin commands (door setter, photos, calibrate) | `RegisterDevPage` rows |
| `config.lua` / `server/config.lua` | `Whip.configPage`; server-only values `sides = 'server'` |
| Purchase `Bridge.Charge/Refund` | `ChargePlayer` receipt → owner row via `CommitWithAction` → `RefundPlayer` on failure; price from the server row |
| Offline rent `ChargeCid` | `GetDefaultBankAccount({ charId })` + `BankSystemWithdraw`; income `BankSystemDeposit` to the realty business account |
| Sell-back, refunds | `PayPlayer({ charId = n }, amount, { method = 'bank', reason })` |
| Storage furniture stashes, escrow of belongings | `EnsureContainer` + `OpenStore`; escrow via `StoreMove` into an escrow container, or `GiveOnLogin` |
| ox_target/qb-target door spheres | `AddAction` prompts (enter, knock, keys, rent, unit picker as `options`) |
| Real door models | `EnsureDoors` in a "Housing" folder with `requirements = { charIds = … }`; warrant breach via `HoldDoor` |
| Blips | `ShowBlip` (listings, offices, your home) |
| Weather sync off indoors | `SetPlayerWeatherLayer` / `ClearPlayerWeatherLayer` |
| Panel NUI with `SetNuiFocus` | Same NUI with `SetScreenOpen`; `BlockControls` in the placement editor; `Confirm`/`Input` for small dialogs |
| Discord webhook | `LogActivity` (plus an optional webhook) |
| Bed → logout | `LogoutPlayer(source)`; sleep marker via `SetPlayerFlag` |
| `/myhomes` | A whip_phone "Homes" module (rent, autopay, keys, listings) |

**Traps found.**
1. **Floating logins.** WHIP saves the live ped position at logout, so a player in a shell is saved in the air.
   Set a player flag on entry; on `whip_core:player:loaded`, restore them to the door or rebuild the shell.
2. **Spawn picker.** It lists WHIP Properties only; no export was found to add shell homes.
3. **Wardrobe.** No export opens WHIP's outfit menu for a resource. The wardrobe furniture needs a different design.
4. **No overdraft.** The "may go negative" rent policy is impossible: bank balances can't go below 0.
5. **Routing buckets.** WHIP uses `1000 + source` (character select) and `100000 + source` (Director isolation).
   Keep the house range clear of both. Drop held props before a bucket move.
6. **Locales.** WHIP has no locale system; keep the resource's own.
