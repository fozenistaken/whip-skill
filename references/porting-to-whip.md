# Porting QBCore, Qbox, ESX and ox resources to WHIP

The guide for converting a script written for QBCore, Qbox (qbx_core), ESX Legacy or the ox stack (ox_core, ox_lib, ox_inventory, ox_target, ox_doorlock) into an idiomatic WHIP resource: rewrite it with WHIP's features, never as a call-for-call translation or compatibility shim. Built from doc anchor `#coming-from` plus `#common-calls`, `#how-whip-thinks`, `#patterns*`, `#whip-way`, the Secure Events, Jobs, Shops, Doors, Zones, Stats and UI library sections; every WHIP export below was checked in `whip_core/types/server.lua`, `types/client.lua`, `types/classes.lua`, `types/events.lua`, `shared/statebags.lua`, `server/secure.lua` and `docs/examples/whip_delivery_example`. Old-framework names follow those frameworks' public APIs; check the source server's copy when an old call is unclear.

A port is finished only when the resource is fully integrated, not when it runs: its prompts, money,
settings, staff, doors, storage, logs and phone app must sit on WHIP's own surfaces (3D prompts, bank
statements and business accounts, `/whip` pages, the Monitor, the activity log, the phone). Walk
`integration.md` for every feature after the mappings below.

## Contents
- Ground rules: what porting to WHIP means
- Upgrade, don't translate: hand-rolled code to delete
- Keep, replace, remove (resources)
- Manifest and bootstrap
- Mapping: server player and identity
- Mapping: money (cash, bank, crypto, black money, society)
- Mapping: items and inventory
- Mapping: callbacks and net events
- Mapping: target and interactions
- Mapping: menus, UI, notify, progress, input, text UI
- Mapping: jobs, grades, gangs, duty
- Mapping: vehicles, keys, fuel, garages
- Mapping: doors
- Mapping: zones
- Mapping: housing
- Mapping: HUD, status, metadata
- Mapping: player loaded / unloaded and other events
- Mapping: state bags
- Mapping: commands, permissions, config, database, locales
- No WHIP equivalent: what to do instead
- Rewrites with before/after code (usable item, server callback, target+job+payout, stash, shop, job vehicle)
- The qb delivery job, call by call
- What will surprise you
- Step-by-step porting procedure
- Porting checklist
- Gotchas
- Docs vs code

---

## Ground rules: what porting to WHIP means

- WHIP has no bridge. A QBCore/Qbox/ESX/ox resource will not run unchanged; the glue code is rewritten (about a day for a small job), and most hand-written code disappears because one WHIP call does it.
- Do not write an adapter layer (`Framework.getPlayer`, `bridge/qb.lua`...). Delete the framework detection and write directly against WHIP.
- The server decides. The client sends no prices, no item names, no amounts, no coordinates it could lie about. Everything a game sends is a `SecureEvent`/`SecureCallback` that declares `params`, `near`, `rateLimit`.
- Declarations (items, use handlers, secure events, callbacks, actions, jobs, stashes, shops, doors, zones, stats, blips) go inside `Whip.register` and are re-run on every whip_core restart; they are removed automatically when your resource stops (items stay registered but ownerless).
- Every export returns a value or `false, why` (never throws). Inside handlers whip_core runs, call `exports.whip_core:X`; everywhere else `Whip.core:X`.
- Save `charId` (a number), never a server id or a license string.
- Name everything with your resource prefix: items/stats/zone ids `myres_x`, events/callbacks `myres:x`.

## Upgrade, don't translate: hand-rolled code to delete

Typical qb/qbx/esx/ox scripts carry code WHIP already does. Delete it rather than port it:

| Delete this | Because WHIP does it |
|---|---|
| Distance checks in net handlers (`#(GetEntityCoords(ped) - coords) > 3.0`) | `near = { at = coords|fn|'vehicle', range, message }` on the SecureEvent; `Progress` `near` re-checks at the end |
| Cooldown tables, `os.time()` throttles, anti-spam flags | `rateLimit` (ms) + `burst` on the SecureEvent (default 100 ms, burst 10); `Whip.command` rate limit |
| `if isDead then return end` on events | SecureEvents refuse dead players by default (`whileDead = true` to allow) |
| Manual type/range checks of client args | `params` (`int`, `number`, `amount`, `id`, `string`, `key`, `enum`, `bool`, `slot`, `list`, `addr`, `vehicle`, `player`, `record`, `any`) |
| Client-sent price/item/amount/target | derive server-side from config; at most send a key validated with `'key'`/`'enum'` |
| Client progress bar followed by a "pay me" event | server `Progress(source, opts)` inside the SecureEvent, or a `RegisterUseHandler` table (timed use) |
| `RemoveItem` inside a usable-item callback | the use handler consumes one (function form: return `false` to keep; table form: `consume = false`) |
| `CanCarryItem` before `AddItem` | `AddItem` drops what doesn't fit at their feet and returns `'ground'` (or `{ noDrop = true }` to refuse); `CanFitItem` when you must know first |
| Remove-then-add item moves; "give back on failure" bookkeeping | `StoreMove` (one transaction), `StoreGive`/`StoreTake`; `ChargePlayer` receipt + `RefundPlayer` |
| Manual `MySQL.transaction` around inventory + your row | `CommitWithAction` |
| `.sql` install files, "run this SQL first" | `EnsureTable(name, createSql, migrations)` |
| Cash-item ↔ money-account sync (ox `money` item, qb cash) | cash IS banknote items; `ChargePlayer`/`PayPlayer` handle cash and bank |
| Vehicle key scripts called after spawning; fuel set on spawn; despawn timers; cleanup on stop | `SpawnTempVehicle(model, coords, { forSource, despawnAfter, tag, secure })`; fuel is a vehicle stat; temp cars go when your resource stops or after 10 idle minutes |
| Blip creation/cleanup, `SetBlipRoute` client events | `ShowBlip(audience, id, { coords, route = true })`, removed when you stop or the tag is released |
| Duty toggle commands, onduty/offduty job copies (`offpolice`) | `ClockOn`/`ClockOff`, the phone's Business app, `whipJob` state bag; duty isn't saved |
| Stash registration on every start (`RegisterStash`) | `EnsureContainer(key, data)` once in `Whip.register` (persistent, with `requirements`) |
| `onResourceStop` cleanup of target zones, prompts, zones, props, NPCs | registrations are swept on stop; `ReleaseTag(tag)` for per-run cleanup |
| "Is the player still here?" checks after `Wait`/awaits | `IsSessionCurrent(source, player.session)` |
| Mailbox/pending-reward tables for offline players | `GiveOnLogin({ charId = n }, item, ...)`; `PayPlayer({ charId = n }, amount, { method = 'bank' })` |
| `config.lua` values admins are told to edit | `Whip.configPage` (edited live in `/whip` → Settings) |
| Client preference menus/commands with KVP | `Whip.playerSetting` (pause menu Server Settings) |
| `RegisterCommand` + ACE + cooldown + dead checks | `Whip.command(name, { ace, dev, whileDead, rateLimit, console }, fn)` |
| Heist/mission cleanup loops over spawned NPCs/cars/blips | pass `{ tag = 'heist:42' }` / `tag = ...` everywhere, then `ReleaseTag('heist:42')` |
| `SetNuiFocus` juggling, `DisableControlAction` loops, phone/weapon conflicts | `SetScreenOpen(true, key)`, `BlockControls(id, spec)`, `FreeHands()` |
| Hand-rolled state-bag anti-tamper | Sentinel guards the state bags WHIP writes |
| Framework adapters / bridge files | delete; write against WHIP |
| Locale loaders for one language | optional: WHIP has no locale system; plain strings (or keep `lib.locale` from ox_lib) |

## Keep, replace, remove (resources)

| Resource | With WHIP |
|---|---|
| `oxmysql` | Keep; ensure before WHIP. WHIPFX's build has WHIP's patch (setup report notes when missing) |
| `qb-core`, `qbx_core`, `es_extended`, `ox_core` (also `vrp`, `ND_Core`) | Remove: one framework at a time; the setup report prints FIX for each running |
| `ox_inventory`, `qb-inventory` (`ps-`, `qs-`, `lj-inventory`) | Remove: WHIP's inventory (F2); setup report FIX |
| `ox_target`, `qb-target`, `qtarget` | Replace with `AddAction`; setup report FIX |
| `ox_lib` | Its helpers (math, tables, `lib.waitFor`) are fine. Anything on screen uses WHIP's UI library (WHIP keeps one screen open at a time; ox_lib screens don't know about it) |
| Garages, keys, fuel, banking, doorlock, housing, shops, multicharacter, spawn, HUD | Remove: part of WHIP; fuel is `whip_fuel` |
| `pma-voice`, `mumble-voip` (`saltychat`, `tokovoip_script`, `yaca-voice`) | Remove if using `whip_voice` (two voice systems = FIX) |
| `chat`, `spawnmanager`, `basic-gamemode` | Remove (whip_chat; WHIP spawns players itself) |

## Manifest and bootstrap

| Old | WHIP |
|---|---|
| `local QBCore = exports['qb-core']:GetCoreObject()` | nothing to fetch |
| `exports.qbx_core:...`, `@qbx_core/modules/lib.lua`, `@qbx_core/modules/playerdata.lua` | nothing to fetch |
| `ESX = exports.es_extended:getSharedObject()`, `@es_extended/imports.lua` | nothing to fetch |
| `@ox_core/lib/init.lua` (+ client/server init) | nothing to fetch |
| `@ox_lib/init.lua` | optional, helpers only |
| `dependencies { 'qb-core' }` etc. | `dependency 'whip_core'` (+ `whip_requires '1.0'`) |

```lua
fx_version 'cerulean'
game 'gta5'
lua54 'yes'
dependency 'whip_core'
whip_requires '1.0'
shared_scripts { '@whip_core/lib/satellite.lua', 'config.lua', 'shared/settings.lua' }
server_scripts { '@oxmysql/lib/MySQL.lua', 'server/*.lua' }   -- MySQL only if you keep own tables
client_scripts { 'client/*.lua' }
files { 'html/img/items/*.webp' }
```
Then `Whip.core:...` inside `Whip.register`, `exports.whip_core:...` inside WHIP-run handlers. Copy `whip_core/types/luarc.template.json` to `.luarc.json` for typed autocomplete.

## Mapping: server player and identity

| QBCore | Qbox | ESX | ox_core | WHIP (server) |
|---|---|---|---|---|
| `QBCore.Functions.GetPlayer(src)` | `exports.qbx_core:GetPlayer(src)` | `ESX.GetPlayerFromId(src)` | `Ox.GetPlayer(src)` | `GetPlayer(source)` → plain sheet `{ source, session, userId, charId, firstName, lastName, fullName, dateOfBirth, gender, cash, position, health, armour, isDead, metadata }` or nil; no methods — act through exports. Inside a SecureEvent the handler already gets `player` (sheet without `metadata`) |
| `QBCore.Functions.GetPlayerByCitizenId(cid)` | `exports.qbx_core:GetPlayerByCitizenId(cid)` | `ESX.GetPlayerFromIdentifier(id)` | — | `GetPlayer({ charId = n })` (online only); also `{ userId = n }`, `{ identifier = 'license:...' }` |
| `PlayerData.citizenid` | same | `xPlayer.identifier` | `player.charId` | `player.charId` (number; save this). `GetCharId(source)` copies nothing |
| `PlayerData.license`, identifiers | same | `xPlayer.identifier` | `player.userId` | `GetPlayerIdentifiers(source)` → `{ license, steam, discord, fivem }` (not on the sheet by design); account = `player.userId` |
| `PlayerData.charinfo.firstname/lastname` | same | `xPlayer.getName()` | `player.get('firstName')`-style | `player.firstName`, `player.lastName`, `player.fullName`; `GetPlayerFullName(source)` |
| `QBCore.Functions.GetPlayers()`, `GetQBPlayers()` | `exports.qbx_core:GetQBPlayers()` | `ESX.GetExtendedPlayers()` | `Ox.GetPlayers()` | `GetPlayers({ light = true }?)` keyed by source; `GetPlayersInRange(coords, range?)` |
| `ESX.GetExtendedPlayers('job', 'police')` / `Ox.GetPlayers({ groups = 'police' })` | | | | `GetClockedOnEmployees('police')` → `{ { charId, source } }` (on duty); `GetJobEmployees(job)` (payroll) |
| `Player.Functions.Save()` | same | `xPlayer.save()`-style | — | not needed (memory first, written within ~1 s); `SavePlayer(source)` exists for edge cases |
| `QBCore.Functions.Kick` / `DropPlayer` | | | | `KickPlayer(source, reason)`; `LogoutPlayer(source)` (back to character select) |
| "still the same player after a wait?" (usually skipped) | | | | `IsSessionCurrent(source, player.session)` |

Client side: `QBCore.Functions.GetPlayerData()` / `QBX.PlayerData` / `ESX.GetPlayerData()` / `Ox.GetPlayer()` → client `exports.whip_core:GetPlayer()` (a copy kept current; `{}` before load), `GetCharId()`, `IsPlayerLoaded()`. Treat it as display data only.

## Mapping: money

| Old | WHIP idiom |
|---|---|
| `Player.Functions.AddMoney('cash', n, reason)` / `xPlayer.addMoney(n, reason)` / ox `money` item `AddItem` | `PayPlayer(who, n, { reason })` — `auto` pays cash while online else bank; cash that doesn't fit lands at their feet. `who` may be `{ charId = n }` (offline → bank). Returns `{ method, amount, currency, placement, accountId }` or `false, why` |
| `AddMoney('bank', n)` / `xPlayer.addAccountMoney('bank', n)` / OxAccount `addBalance` | `PayPlayer(who, n, { method = 'bank', reason })` (`accountId` to pick an account) |
| `RemoveMoney('cash'|'bank', n)` / `xPlayer.removeMoney(n)` / `removeAccountMoney` / ox `RemoveItem(src, 'money', n)` | `ChargePlayer(source, n, { method = 'cash'|'bank'|'auto', accountId?, currency?, reason })` → receipt `{ id, amount, method, accountId, currency, refunded }` or `false, 'Not enough cash (have $20, need $500)'`-style. `auto` (default): cash if they carry enough, else bank (player's own withdraw permission). Amount 0 returns a receipt and moves nothing |
| Give money back after a failed sale | `RefundPlayer(receipt, amount?)` — only the charging resource, within 30 min; goes back where it came from; refused bank refund comes back as cash; cash for a player who left goes to their bank. After 30 min: `PayPlayer` |
| `GetMoney('cash')` / `xPlayer.getMoney()` | `GetPlayerCash(source)` → number (0, 'Player not loaded') |
| `GetMoney('bank')` / `xPlayer.getAccount('bank').money` | `GetBalance(source | { charId } | { accountId })` (WAITS on the first read, then memory) |
| Metered payments (fuel pumps, taxi meters) | `HoldMoney(source, max, { method, reason, vehicle? })` → holdId; `SpendMoneyHold(id, spent)`; `SettleMoneyHold(id, spent?)` |
| `crypto` (qb money type), `black_money` (ESX account) | no third balance: make an item (`myres_crypto`, `myres_dirtycash`) and use `ChargePlayer(..., { currency = 'myres_dirtycash' })` / `PayPlayer(..., { method = 'cash', currency = '...' })` — a cash payment in that item, refunded in that item |
| Society/boss money (`qb-management`, `esx_society`, addon accounts) | the job's business bank account (made with the job; owner + roles' `bankAccess`): `GetJobBankAccounts(job)`, `BankDeposit(accountId, amount, actor, opts)`, `BankWithdraw(...)`, `BankSystemDeposit(accountId, amount, opts)`; shop sales in `infinite`/`stocked` mode pay it automatically |
| `setMoney` | none (no direct balance writes); charge or pay the difference |

Rules: there is no lower-level cash call; cash is banknote items that can be dropped, stolen and stashed. Charge first, give second, refund on failure.

## Mapping: items and inventory

| Old | WHIP |
|---|---|
| `qb-core/shared/items.lua` entry `{ name, label, weight (g), type, image, unique, useable, shouldClose, description }`; `ox_inventory/data/items.lua` `{ label, weight (g), stack, close, description, client/server }`; ESX `items` table | `RegisterItem(key, { name = label, desc, weight (KG per unit), type, stack = not unique, maxStack, usable, image?, cooldown?, prop?, metaFields?, contextOptions?, defaultAction?, settings? })` inside `Whip.register`; or an admin adds it in `/whip` → Economy → Items. Picture: `html/img/items/<key>.webp|png` in your resource + `files {}`. Key: letters, digits, `_`, `-`, ≤50 chars |
| `QBCore.Functions.CreateUseableItem(name, fn(source, item))` / `ESX.RegisterUsableItem(name, fn(source))` / ox `exports('name', fn(event, item, inventory, slot, data))` or `registerHook('usingItem')` | `RegisterUseHandler(key, fn(source, player, slotData, addr))` (one consumed unless it returns `false`) or a TABLE for a timed use `{ label, duration (required), anim, prop, disable, canCancel, consume, reason, canUse(source, player, slotData, addr), onComplete(source, player, item, addr) }` — WHIP runs the server-timed bar, checks the item is still there, takes it, then `onComplete`; `false, 'why'` gives it back |
| `Player.Functions.AddItem(name, n, slot, info)` / `xPlayer.addInventoryItem` / `ox_inventory:AddItem(src, name, n, metadata)` | `AddItem(source, item, amount?, metadata?, opts?)` → `'inventory'|'ground'|false, why`; opts = reason string or `{ reason, noDrop, pocket, coords }` |
| `RemoveItem(name, n, slot)` / `removeInventoryItem` / `ox_inventory:RemoveItem` | `RemoveItem(source, item, amount?, metadata?, opts?)` (`metadata` filters stacks carrying those values) |
| `Player.Functions.HasItem(name, n)` / `ox_inventory:Search(src, 'count', name)` / `GetItemCount` / `xPlayer.getInventoryItem(name).count` | `HasItem(source, item, amount?)`, `GetItemCount(source, item)` (memory, across every pocket) |
| `CanCarryItem` / `xPlayer.canCarryItem` | `CanFitItem(source, item, amount?, metadata?)` → `true` or `false, 'Only 3 fit'`; usually unnecessary (AddItem drops at feet) |
| `GetItemByName` / `ox_inventory:GetSlotWithItem` | `FindItem(source, item, pocket?)` → `{ ..., addr }`; `FindAllItems(source, item, pocket?)` |
| `info` / ox `SetMetadata(src, slot, meta)` | `SetItemMetadata({ kind = 'player', id = source, sub = 'player', slot = n }, meta, { replace?, remove?, quiet? })` (merges by default) |
| Default metadata (serials) via ox `createItem` hook | `RegisterItemDefaultMetadata(itemKey, generator(itemKey, ctx), opts?)` |
| Moving between player and stash/trunk (remove + add) | `StoreMove(fromAddr, toAddr, { amount?, mode?, reason? })` — one committed move |
| Put items into a stash/trunk | `StoreGive({ kind = 'container'|'vehicle', id, sub }, item, amount?, metadata?, reason)` → slot |
| Take items out of a store (destroy) | `StoreTake(addr, amount?, { item?, reason? })` |
| Read a stash | `StoreRead(addr)` → `{ kind, id, sub, label, slots, maxWeight, weight, items }`; `StoreCount(addr, item)` |
| `RegisterStash(id, label, slots, weight, owner, groups)` | `EnsureContainer(key, { x, y, z, heading?, name?, slots?, maxWeight?, prop?, locked?, allowedItems?, requirements = { jobs, onDuty, charIds, items, ace, property } })` (persistent, declared by key; admin edits stand until your declaration changes). New one per call: `CreateContainer(data)` (`ownerCharId`, `accessCharId`, `persist = false` + `tag` for temporary) |
| `ox_inventory:forceOpenInventory(src, 'stash', id)` / `openInventory('stash', id)` / `TriggerServerEvent('inventory:server:OpenInventory', ...)` | `OpenStore(source, { kind = 'container', id = containerId }, opts?)` (server); players also open world containers with E |
| `openInventory('player', target)` (robbing, searching) | `OpenPlayerInventory(source, target, { range? })` |
| Item right-click actions | `contextOptions` in the item + `RegisterContextAction(actionKey, handler)`; add options to other resources' items with `AddItemOption(itemKey, option)` |
| Wallet/bag items holding items | `RegisterPanelItem(itemKey, { slots, label, storageKey, allowedItems })` |
| Trunk/glovebox access | stores `{ kind = 'vehicle', id = vehicleId|{ plate = 'X' }, sub = 'trunk'|'glovebox' }` |
| Item events (`ox_inventory` hooks `swapItems`) | server events `whip_core:item:added`/`removed` `{ source, item, amount, count, reason, by }`, `whip_core:inventory:changed`, `whip_core:item:used`, `whip_core:item:given`; refusing a move: your own panel's `onValidate` or store kind hooks |

Weight: qb and ox_inventory weights are grams; WHIP item `weight` is kg per unit (divide by 1000).

## Mapping: callbacks and net events

| Old | WHIP |
|---|---|
| `RegisterNetEvent('x:server:do', fn)` on the server | `SecureEvent('myres:do', schema, fn(source, player, ...))` in `Whip.register`. Schema: `rateLimit` (ms, default 100 with burst 10; `false` none), `burst`, `near = { at, range (5.0), message, allowUnknown }`, `params`, `whileDead`, `ace`, `permission` (WHIP permission name or list), `requirePlayer` (default true), `ownerOf`, `sheet = 'light'`, `onReject`. Return `false, 'why'` to refuse (player sees why; Monitor logs it); bare `false` refuses silently |
| `QBCore.Functions.CreateCallback(name, fn(source, cb, ...))` / `ESX.RegisterServerCallback` / `lib.callback.register(name, fn(source, ...))` | `SecureCallback('myres:get', schema, fn(source, player, ...))` — return values ARE the answer (no `cb`); refuse with `false, 'why'` (never `nil, why`) |
| `QBCore.Functions.TriggerCallback(name, cb, ...)` / `ESX.TriggerServerCallback` / `lib.callback.await(name, false, ...)` | client `exports.whip_core:Callback(name, ...)` (WAITS; from a thread / handler). Gets the handler's returns or `false, reason` ('Rate limited', 'Player is dead', 'Too far away', a param's reason, 'Server error', 'Unknown callback', 'That is no longer available', 'No answer from the server' after 10 s) |
| `lib.callback.await(name, playerId)` (server→client) | no verified WHIP server→client callback; use server-side UI exports (`Progress(source)`, `SkillCheck(source)`, `NotifyPlayer`, `ShowPlayerText`) or a plain client event |
| `TriggerClientEvent('QBCore:Notify'/'ox_lib:notify'...)` | `NotifyPlayer(source, text, kind, duration?)` |

Param type cheat sheet (`{ name, type, ... }`): `int`/`number` (min, max, default; out of range CLAMPED), `amount` (whole ≥1, optional max; REFUSED otherwise — use for quantities/money), `id` (refused if out of range or fractional — addresses), `string` (maxLen, default), `key` (letters/digits/`_`/`-`, maxLen), `enum` ({allowed}, default), `bool`, `slot` (a slot in the caller's own pockets, `{ item = key }`; handler gets `{ addr, item, amount, metadata }`), `list` (entry def, max 50), `addr` (store address, authorised), `vehicle` (a vehicleId the caller owns; `{ session = true }` allows street cars; handler gets the vehicle snapshot), `player` (another player `{ range = 3, notSelf = true }`; handler gets their light sheet), `record` (named fields), `any` (unchecked).

## Mapping: target and interactions

| Old | WHIP |
|---|---|
| `exports['qb-target']:AddBoxZone(name, coords, l, w, {...}, { options, distance })` / `exports.ox_target:addBoxZone({ coords, size, options })` / `addSphereZone` | client `AddAction({ id, at = { coords = vec3, heading? }, label, icon, require, canInteract, onSelect, options, reach })` |
| `AddTargetEntity` / `ox_target:addLocalEntity(entity, options)` / `addEntity(netId)` | `at = { entity = handle }` or `at = { netId = id }` (+ `offset`, `bone`) |
| `AddTargetModel` / `ox_target:addModel(model, options)` | `at = { model = 'prop_name' | { names } }` (names, not hashes; `perModel`, `faces`, `onFound`/`onLost`) |
| `addGlobalVehicle` with bones (`door_dside_f`, `boot`) | `at = { vehiclePart = 'hood'|'trunk'|'door_dside_f'|'door_pside_f'|'door_dside_r'|'door_pside_r'|'bike'|'bicycle'|'boat' }` |
| `addGlobalPed`/`addGlobalPlayer`/aim targets | `at = { aimBox = 'vehicle'|'object'|'ped'|'world'|{...} }` (`ctx.entity`, `ctx.player.serverId`) |
| Radial menu (qb-radialmenu, `lib.addRadialItem`) | `at = { radial = true }` (F1 wheel; `label` required, `description` pill) |
| option `job = 'police'` / `groups = { police = 0 }` | `require = { job = 'police' }` (has a role), `+ onDuty = true`, `+ jobPermission = 'armory'` for rank gating; also `item`, `held`, `zone`, `charId`, `ace`, `vehicle = 'in'|'out'`, `alive = false` |
| `distance = 2.0` | `reach = 2.0` (default `Config.InteractActiveRange` 2; set it to what your server `near` allows); `seeFrom` for visibility |
| `canInteract(entity, distance, coords, name)` | `canInteract(ctx)` (must not wait) |
| `event`/`serverEvent`/`action` fields | `onSelect(ctx)` (own thread; may wait); typically `TriggerServerEvent('myres:x')` with no values. `ctx.refuse(why)`, `ctx.status(text)`, `ctx.flash(r,g,b)`, `ctx.beginInput{...}` |
| `removeZone(id)` on stop | automatic on resource stop; mid-run `RemoveAction(id)`, `RemoveActionGroup(group)`, or hide with `UpdateAction(id, { enabled = false })` |
| Server-defined points | server `AddPoint(def)` |

`require` only decides what is offered. Re-check everything on the server (duty with `IsPlayerClockedOn`, rank with `HasJobPermission`, items with `HasItem`, position with `near`).

## Mapping: menus, UI, notify, progress, input, text UI

| Old | WHIP (client unless noted) |
|---|---|
| `qb-menu` `exports['qb-menu']:openMenu`, `lib.registerContext`/`lib.showContext`, `lib.registerMenu`, `esx_menu_default` | no list menu: options on a prompt (`AddAction` `options`, nested `options` = submenus with Back, a function `options = function(ctx) ... end` filled when opened and may wait, `stay = true`), or a `select` field in `Input` |
| `QBCore.Functions.Notify(text, type, ms)` (`'primary'|'success'|'error'|'warning'`), `ESX.ShowNotification`, `lib.notify({ title, description, type })`, `exports.qbx_core:Notify(src, ...)` | `Notify(text, 'info'|'success'|'warning'|'error', ms?)` (default 'info', 3000 ms); server `NotifyPlayer(source | -1, text, kind?, duration?)`; from a SecureEvent just `return false, 'why'` |
| `QBCore.Functions.Progressbar(...)`, `lib.progressBar`, `lib.progressCircle`, `ESX.Progressbar` | if anything is handed out at the end: server `Progress(source, { label, duration (required), anim, prop, disable, canCancel, cancelOnDeath, cancelOnExit, notWhile, near = { coords|vehicle, range }, tag })` in a SecureEvent, or a timed-use table. Cosmetic only: client `Progress(label, duration, opts)` / `Progress({ ... })` → `true` or `false, 'busy'|'cancelled'|'timeout'|'refused'` |
| option names | `useWhileDead = true` → `cancelOnDeath = false`; `disable = { move, car, combat }` same names (`move = 'walk'` walking only); `anim = { dict, clip }` (+ `flag` default 49, `scenario`); `prop = { model, bone, pos, rot }` → `{ model, bone (default 18905), offset, rot }` |
| `lib.skillCheck`, qb-skillbar, ps-ui circle | `SkillCheck('easy'|'medium'|'hard' | { difficulty, game, level })`; when passing gives something: server `SkillCheck(source, difficulty, { timeoutMs, minMs, tag, game, quiet })` from a SecureEvent |
| `lib.inputDialog(title, rows)`, `exports['qb-input']:ShowInput` | `Input(title, { { label, type = 'text'|'number'|'textarea'|'select'|'checkbox'|..., placeholder, default, required, min, max, options = { { label, value } } } })` → values by position, or `false, 'busy'|'cancelled'|'timeout'` |
| `lib.alertDialog({ cancel = true })` | `Confirm(title, message, yes?, no?)` → `true` or `false, 'cancelled'`; single OK: `Alert(title, message, btn?)` |
| `lib.showTextUI`, `DrawText3D`, `ESX.TextUI`, `exports['qb-core']:DrawText` | usually unnecessary (prompts say it). `ShowText(text, position|{ position, progress, icon, tone }, progress?)` / `HideText()`; server `ShowPlayerText(source, text, { position, progress, countdown, countdownTotal, tag })` / `HidePlayerText` |
| Objective HUD | client `ShowObjective(id, text, opts)` / `HideObjective(id)` |
| Own NUI with `SetNuiFocus` | `SetScreenOpen(true, key?, { keepHud? })` / `SetScreenOpen(false, key)`; controls `BlockControls(id, { groups, controls, all, except, walk, jog, mode })` / `UnblockControls`; hands `FreeHands()`; pad support `Whip.padScreen` |
| One-line text entry (chat-like) | `OpenComposer({ onSubmit, ... })` |

## Mapping: jobs, grades, gangs, duty

| Old | WHIP |
|---|---|
| `qb-core/shared/jobs.lua`, `QBCore.Shared.Jobs`, ESX `jobs`/`job_grades` SQL, ox_core groups | `EnsureJob(key, { name, icon?, owner?, roles = { { name, level (1-100), permissions? } }, permissions = { myperm = 'Label' }?, selfClockOn?, settings? })` in `Whip.register`; existing jobs keep owner/roles, missing roles are added |
| grade numbers / `isboss` | roles with `level` 1-100 (100 = every permission); built-in permissions `canHire`, `canFire`, `canPromote`, `canDemote`, `canManage`, `bankAccess` ('none'|'view'|'deposit'|'withdraw'|'manager'); your own job permissions |
| `PlayerData.job.name` / `xPlayer.job.name` / `player.getGroup('police')` | ON DUTY: `GetPlayerJob(who)` → `{ jobId, key, name, roleId, roleName, roleLevel, clockedOn, permissions }` or nil off duty. WORKS THERE AT ALL: `GetPlayerRole(who, 'police')` → role `{ roleId, jobId, name, level, permissions }` or nil. All jobs: `GetPlayerJobs(who)` |
| `job.grade.level >= 3` checks | `HasJobPermission(who, job, 'permName', { onDuty = true })` → `true` or `false, why` (gate by permission, not grade number) |
| `Player.Functions.SetJob(name, grade)` / `xPlayer.setJob` / `player.setGroup` | `HirePlayer(who, job, role?, { by? })`, `SetPlayerRole(who, job, role, { by? })`, `FirePlayer(who, job, { by? })`. Pass `by = source` from a boss menu: WHIP checks rank and permissions. A player can hold roles at several jobs |
| `PlayerData.job.onduty`, `Player.Functions.SetJobDuty(bool)`, `QBCore:ToggleDuty`, ESX `off<job>` copies | `ClockOn(who, job, { by? })` / `ClockOff(who, job?)` (server) or `ClockOn(job)` / `ClockOff(job)` (client, WAITS). `IsPlayerClockedOn(who, job?)`. Duty isn't saved (logout/restart ends it); players clock on in the phone's Business app unless `selfClockOn = false`; `Config.JobDutyOneAtATime` |
| `PlayerData.gang`, `SetGang`, `QBCore.Shared.Gangs` | no gangs: make each gang a job with `EnsureJob`; membership = `GetPlayerRole(source, 'ballas')`; `require = { job = 'ballas' }` |
| Job update events | client `whip_core:job:clockedOn`/`clockedOff` `{ jobId, key }`, `whip_core:job:listChanged` `{ jobs }`; server `whip_core:job:hired`, `:fired`, `:roleChanged`, `:clockedOn`, `:clockedOff`, `:created`, `:updated`, `:deleted` |
| `LocalPlayer.state` job bags | `LocalPlayer.state.whipJob` / `Player(id).state.whipJob`: on-duty job KEY or `false` |

## Mapping: vehicles, keys, fuel, garages

| Old | WHIP |
|---|---|
| `QBCore.Functions.SpawnVehicle`, `qbx.spawnVehicle`, `ESX.Game.SpawnVehicle`, `CreateVehicle` + keys + fuel (job/rental/test drive) | server `SpawnTempVehicle(model, coords, { forSource, giveKey (default true with forSource), despawnAfter (s), locked (default true), keyInIgnition, idleDespawn (default true: 10 min alone), tag, secure, plate, vehType, bucket })` → vehicleId; removed on resource stop / despawnAfter / idle / `DespawnVehicle`; fires `whip_core:vehicle:released` with `reason`; key taken back when it goes |
| Dealership sale (insert into `player_vehicles`/`owned_vehicles`) | `CreateOwnedVehicle(source, { model, plate?, garage?, stats? = { fuel = 100 }, properties? }, { giveKey = true, spawnAt = vector4 })` → vehicleId (owner taken from the caller's record); ask `CanBringOutVehicleFor(source)` before charging; `VehicleModelExists(model)` |
| Vehicle keys (`vehiclekeys:client:SetOwner`, qbx_vehiclekeys, wasabi_carlock) | keys are items: `GiveVehicleKey(who, vehicleId, { spare? })`, `RemoveVehicleKey`, `HasVehicleKey`, `CountVehicleKeys`, `ChangeVehicleLocks`; locks `SetVehicleLocked(vehicleId, locked)` |
| `exports['LegacyFuel']:SetFuel/GetFuel`, ox_fuel `Entity(veh).state.fuel`, cdn-fuel | the `fuel` vehicle stat (registered by whip_fuel): server `GetVehicleStat(vehicleId, 'fuel')`, `SetVehicleStat(vehicleId, 'fuel', 100.0, 'refuel:myres')`; client `GetVehicleStat(vehicle, 'fuel')` for a nearby car. Never write the `whipStats` bag |
| Garages (qb-garages, esx_garage, jg-advancedgarages) | built in (bays set up by owners in `/whip`); impound `DespawnVehicle(vehicleId, { garage = 'impound', refuseOccupied })`; `GetVehiclesOf(who)`; `TransferVehicle`; `SetVehicleGarage` |
| `GetVehicleProperties` / `SetVehicleProperties(veh, props)` | client `SetVehicleProperties({ entity = veh }, props)` (a bare number is a vehicleId); to keep a look: server `SetVehicleAppearance(vehicleId, props, opts)`; saved look in `GetVehicle(id).properties` |
| Plate lookups | `GetVehicle({ plate = 'ABC123' })` (also `{ netId }`, `{ entity }`, id) → snapshot `{ vehicleId, plate, model, owner = { charId, name, online }, state, garage, coords, spawned, entity, netId, locked, stats, data, temp, session, ... }` |
| Custom per-car data (mileage, finance) | `SetVehicleData(vehicleId, key, value)` / `GetVehicleData`; gauges: `RegisterVehicleStat(name, config)` |
| Street car adoption | `AdoptVehicle(ref)`; client `ResolveVehicle(entity)` |
| Engine disable | `HoldVehicleEngine(vehicleId, key, reason)` / `ReleaseVehicleEngine` |

## Mapping: doors

| Old | WHIP |
|---|---|
| `ox_doorlock` doors (DB/UI), `qb-doorlock` `Config.DoorList`, `esx_doorlock` | `EnsureDoors({ { key, model, coords = vector4, label?, folder?, requirements = { jobs, onDuty, charIds, items = { { key } }, ace, lockpick }, autolock?, autolockDelay?, link? } }, { id?, label?, prune? })` in `Whip.register` — the list is your whole set; managed doors (admins can't change access); one door: `EnsureDoor(key, data, opts)` |
| `TriggerServerEvent('ox_doorlock:setState')` / `exports.ox_doorlock:setDoorState` | `SetDoorLocked(door, locked)` (doc example passes `{ key = 'front' }`) |
| Access checks | `CanUseDoor(source, doorId)`; heist holds `HoldDoor(data, opts)`; events `whip_core:door:lockChanged`, `whip_core:door:denied` |

Door requirements are ANY-OF; `jobs` means has a role there unless `onDuty = true`.

## Mapping: zones

| Old | WHIP |
|---|---|
| PolyZone `BoxZone:Create`/`CircleZone`/`PolyZone:Create`, `lib.zones.box/sphere/poly`, `lib.points.new` | client `RegisterZone({ type = 'box'|'sphere'|'poly', id = 'myres_x', pos, size, heading, radius, points, minZ, maxZ, label, group, notify, priority, condition, rules, onEnter, onExit, inside, trackVehicles })` |
| Zones the server must trust / shared by all | server `EnsureZone(key, { type, pos, size, heading, radius, points, minZ, maxZ, label, group, priority, rules, notify, trackVehicles, trackPlayers })` (saved, editable in the Zone Editor); `IsPointInZone(id, point, true)` |
| Safe zones, no-weapon areas, speed limits (custom loops) | declarative `rules = { noWeapons, noPvP, noMelee, disableFiring, speedLimit, noVehicles, heal, healRate, noWantedLevel, noCollision, noFallDamage, jobWhitelist, aceWhitelist, charWhitelist, ejectUnauthorized, enterNotify, exitNotify }` |
| `onEnter`/`onExit` server logic | `trackPlayers = true` → server events `whip_core:zone:entered`/`exited` `{ zoneId, key, source, dropped?, removed? }` (checked every `Config.ZoneTrackInterval`, 1000 ms) |
| "Only usable in zone" | `require = { zone = 'key' }` on an action; the server re-check uses trusted zones only |

## Mapping: housing

| Old (qb-houses, ps-housing, esx_property, qs-housing) | WHIP |
|---|---|
| House ownership/keys tables | built-in properties: `SetPropertyOwner(propertyId, who|nil)`, `GivePropertyKey(propertyId, who)`, `RemovePropertyKey(propertyId, who)`, `HasPropertyAccess(propertyId, who)`, `GetCharacterProperties(charId)` → `{ owned, keys }`, `GetPropertyAt(x, y, z)` |
| House stashes | property stash furniture (`Config.PropertyStashProps`); containers can require `requirements = { property = id|key }` |
| Interiors/shells | property packs and templates (server owners), `whip_homes_mirrorpark` |
| Events | server `whip_core:property:ownerChanged`, `:keyGranted`, `:keyRevoked`; client `whip_core:property:entered`/`exited` |

## Mapping: HUD, status, metadata

| Old | WHIP |
|---|---|
| `PlayerData.metadata.hunger/thirst`, `SetMetaData('hunger', v)`, `esx_status:add('hunger', 200000)` (0-1,000,000 scale), ox `player.set('hunger')` | built-in stats `hunger`, `thirst` (0-100, 100 full, decay `Config.HungerMinutes` 120 / `ThirstMinutes` 90; ≤10 costs health). `AddStat(source, 'thirst', 20, 'item:myres_water')`, `SetStat`, `GetStat`, `GetStats`; `health` 0-200 and `armour` 0-100 are stats too |
| `metadata.stress` (qb/qbx), custom status bars | `RegisterStat('myres_stress', { type = 'custom', default, min, max, persist, decay, decayInterval, thresholds, hud = { icon, color, order } })` — the HUD ring appears with no UI code |
| Other metadata (licences, quest progress, `jailtime`) | `SetPlayerFlag(who, name, value)` / `GetPlayerFlag` (online, ≤256 flags, text ≤100) or `SetPlayerMetadata(who, key, value)` / `GetPlayerMetadata` (online or offline, WAITS; refuses non-JSON values and reserved keys `appearance`, `outfits`, `creatorPending`, `walk`, `mood`, `whipFlags`, `moneyHeldOwed`, `pourRefundOwed`, `lastSeat`). Both are visible to the player's own game |
| `isdead`, `inlaststand` metadata; `hospital:client:Revive`, `esx_ambulancejob:revive` | `IsPlayerDead(source)`, `RevivePlayer(source, reason?)`, `HoldRespawn(source, key, label?)` (EMS on the way) / `ReleaseRespawn`; events `whip_core:player:died`/`revived` |
| qb-hud / ps-hud / esx_hud | WHIP's status HUD can't be replaced; add gauges via `RegisterStat` `hud` or `RegisterVehicleStat` `hud`; `Config.HudSkin` picks one of two looks; listen with `OnStatChanged` |

## Mapping: player loaded / unloaded and other events

| QBCore / Qbox | ESX | ox_core | WHIP |
|---|---|---|---|
| server `QBCore:Server:OnPlayerLoaded` | `esx:playerLoaded` (playerId, xPlayer) | `ox:playerLoaded` | server `AddEventHandler('whip_core:player:loaded', function(e) end)` — `e = { source, charId, name, newCharacter, player }` |
| server `QBCore:Server:OnPlayerUnload`, `playerDropped` | `esx:playerDropped` | `ox:playerLogout` | server `whip_core:player:logout` `{ source, charId, player, why = 'logout'|'disconnect' }` |
| client `QBCore:Client:OnPlayerLoaded` | client `esx:playerLoaded` | client `ox:playerLoaded` | client `whip_core:player:loaded` (same table; character in the world, picture back); `whip_core:player:spawned` |
| client `QBCore:Client:OnPlayerUnload` | client `esx:onPlayerLogout` | client `ox:playerLogout` | client `whip_core:player:logout` `{ charId }` |
| `QBCore:Client:OnJobUpdate`, `QBCore:Client:SetDuty` | `esx:setJob` | group events | client `whip_core:job:clockedOn`/`clockedOff`/`listChanged` |
| `QBCore:Client:OnMoneyChange` | `esx:setAccountMoney` | — | server `whip_core:bank:balanceChanged`, `whip_core:item:added`/`removed` (cash is an item) |
| — | — | — | `whip_core:character:created`/`deleted` (ask `IsCharacterDeleted(charId)` before acting), `whip_core:player:died`/`revived`, `whip_core:vehicle:entered`/`exited`/`released`/..., `whip_core:flag:changed`, `whip_core:shop:purchased` |

All `whip_core:*` events are LOCAL (`AddEventHandler`, not `RegisterNetEvent`), one table payload. Any server resource can fire them: `if GetInvokingResource() ~= 'whip_core' then return end` before paying or deleting anything.

## Mapping: state bags

| Old | WHIP |
|---|---|
| `LocalPlayer.state.isLoggedIn` (qb/qbx) | none; `IsPlayerLoaded()` (client) / `IsPlayerLoaded(source)` (server), or the loaded event |
| job/duty bags | `whipJob` (job key string, or `false` off duty) |
| dead / last stand bags | `whipDead` (boolean) |
| escort/drag scripts' bags | `whipEscorted` (boolean), `whipEscortedBy` (server id) |
| Other player bags WHIP writes | `whipDamageMod`, `whipMeleeMod` (absent at 1.0), `whipMood` (facial expression name) |
| Vehicle bags (fuel, keys, owner) | `whipVehicleId`, `whipVehicleSession` (street cars), `whipStats` (stored stats; never read raw — absent = default; use `GetVehicleStat`), `whipLive`, `whipAppearance`, `whipVehData`, `whipVehDoors`, `whipEngineHold` |

No name or charId is ever on a bag. WHIP's bags are read-only for you; Sentinel catches games that change them. Store your own data through exports (`SetVehicleData`, `SetPlayerFlag`), not by writing WHIP-prefixed bags.

## Mapping: commands, permissions, config, database, locales

| Old | WHIP |
|---|---|
| `QBCore.Commands.Add(name, help, args, required, fn, perm)`, `ESX.RegisterCommand(name, group, fn, ...)`, `lib.addCommand(name, { help, restricted, params }, fn)`, `RegisterCommand` | `Whip.command(name, { ace = 'my.perm', dev = true, whileDead = true, rateLimit = false|{ burst, everyMs }, console = false }, function(source, args, raw) end)` (server; runs in a thread; no typed params — parse `args` yourself) |
| `QBCore.Functions.HasPermission(src, 'admin')`, `xPlayer.getGroup() == 'admin'`, `IsPlayerAceAllowed` | `RegisterPermission('myres.manage', { label, description, implies, devtools, grantedBy })` + `HasPermission(source, name)`; gate events with `permission = 'myres.manage'` or `ace = '...'`; admin tools `HasDevTools(source)`; grants are per account (`GrantPermission(who, name)`) |
| `config.lua` admins edit | `Whip.configPage({ label, groups = { { label, settings = { { key = 'Prices.coffee', type = 'int', min, max, unit, label } } } } })` at file scope after config.lua; react with `Whip.onConfigChanged(path, fn)` |
| Per-player client settings | `Whip.playerSetting({ key, label, group, type = 'toggle'|'choice'|'slider', default, get, set })` |
| `.sql` files | `EnsureTable(name, createSql, migrations)`; plain `MySQL.*` for your own queries is still fine; `CommitWithAction` when the row must land with an inventory/money change |
| `Lang:t`, `_U`, `locale()` | no locale system; your strings are your own (ox_lib's `lib.locale` may be kept as a helper) |
| Logging (qb-log, Discord webhooks) | `LogActivity(source, event, { detail, slotData })` into the activity log; item/money changes are logged with your `reason` automatically |

## No WHIP equivalent: what to do instead

| Concept | Instead |
|---|---|
| Gangs | a job per gang (`EnsureJob`); membership via `GetPlayerRole`; no duty needed |
| `crypto` money type, `black_money` | an item + `currency` option on `ChargePlayer`/`PayPlayer` |
| List/context menus | prompt `options` (nested, dynamic), `Input` select, `Confirm` |
| Locales | plain strings |
| Generic server→client callback | server UI exports or a client event |
| `setMoney`, direct balance edits | charge/pay the difference |
| Replacing the status HUD / spawn picker / WHIP's own item uses | not possible; add gauges, themes, own items |
| Client-authoritative progress/minigame rewards | server `Progress`/`SkillCheck` or timed use (a patient cheater still passes a minigame: don't gate must-be-uncheatable outcomes on one) |
| Global "job grade ≥ N" checks | job permissions on roles + `HasJobPermission` / `require.jobPermission` |
| Persisted duty | duty is per session by design |
| Scripted missions/heists as long Lua state machines | consider the Director (missions from cards in `/whip`, no code); start runs from code with `StartScenarioRun(key, who, opts)`; extend it with `Whip.card`, `Whip.task`, `Whip.directorButton` |

## Rewrites with before/after code

Each "after" lives in `Whip.register` unless marked otherwise.

### 1. A usable item (bandage)
Before (QBCore; ESX/ox are the same shape):
```lua
QBCore.Functions.CreateUseableItem('bandage', function(source, item)
  TriggerClientEvent('hospital:client:UseBandage', source)   -- client progressbar, then:
end)
RegisterNetEvent('hospital:server:bandageDone', function()   -- client says "done"
  local Player = QBCore.Functions.GetPlayer(source)
  Player.Functions.RemoveItem('bandage', 1)
  TriggerClientEvent('hospital:client:heal', source, 25)
end)
```
After (server):
```lua
Whip.core:RegisterItem('myems_bandage', { name = 'Bandage', weight = 0.1, stack = true, maxStack = 10, usable = true })
Whip.core:RegisterUseHandler('myems_bandage', {
  label = 'Bandaging...', duration = 4000,   -- add anim = { dict, clip } / prop = { model, bone } as wanted
  canUse = function(source) if (exports.whip_core:GetStat(source, 'health') or 0) >= 200 then return false, 'Not hurt' end return true end,
  onComplete = function(source) return exports.whip_core:AddStat(source, 'health', 25, 'item:myems_bandage') end,
})
```
No client code, no "done" event; the server times the bar, takes the item, returns it if `onComplete` fails.

### 2. A server callback
Before (qb / ox):
```lua
QBCore.Functions.CreateCallback('shop:getPrice', function(source, cb, item) cb(Config.Prices[item]) end)
-- client: QBCore.Functions.TriggerCallback('shop:getPrice', function(p) ... end, 'coffee')
lib.callback.register('shop:getPrice', function(source, item) return Config.Prices[item] end)
```
After:
```lua
Whip.core:SecureCallback('mycafe:getPrice', { rateLimit = 500, params = { { 'itemKey', 'key', 60 } } },
  function(source, player, itemKey)
    local price = Config.Prices[itemKey]
    if not price then return false, 'Not sold here' end   -- never nil, 'why'
    return price
  end)
-- client, in a thread/handler:
local price, why = exports.whip_core:Callback('mycafe:getPrice', 'mycafe_coffee')
```

### 3. Target zone + job check + payout (mechanic repair)
Before (qb-target + progressbar + pay event):
```lua
exports['qb-target']:AddBoxZone('mech_bench', vector3(...), 1.5, 1.5, {}, { options = {
  { event = 'mech:client:repair', label = 'Repair', job = 'mechanic' } }, distance = 2.0 })
-- client: QBCore.Functions.Progressbar(...) then TriggerServerEvent('mech:server:pay', 250)
RegisterNetEvent('mech:server:pay', function(amount)
  QBCore.Functions.GetPlayer(source).Functions.AddMoney('cash', amount)   -- exploitable from anywhere
end)
```
After (client):
```lua
Whip.register(function()
  Whip.core:AddAction({ id = 'bench', at = { coords = Config.Bench }, label = 'Repair', icon = 'car',
    require = { job = 'mymech', onDuty = true }, reach = 2.0,
    onSelect = function() TriggerServerEvent('mymech:repair') end })
end)
```
After (server):
```lua
Whip.core:SecureEvent('mymech:repair', { rateLimit = 5000, near = { at = Config.Bench, range = 3.0 } },
  function(source, player)
    if not exports.whip_core:IsPlayerClockedOn(source, 'mymech') then return false, 'Clock on first' end
    local done, why = exports.whip_core:Progress(source, { label = 'Repairing...', duration = 8000,
      near = { coords = Config.Bench, range = 3.0 } })
    if not done then return false, why == 'too far' and 'Stay at the bench' or nil end
    if not exports.whip_core:IsSessionCurrent(source, player.session) then return end
    exports.whip_core:PayPlayer(source, Config.RepairPay, { reason = 'Bench repair' })
  end)
```
The amount lives in config; the client sends nothing; distance, rate, duty and timing are server facts.

### 4. A stash
Before (ox_inventory / qb):
```lua
exports.ox_inventory:RegisterStash('police_evidence', 'Evidence', 100, 200000, false, { police = 0 }, vec3(...))
-- client target option: exports.ox_inventory:openInventory('stash', 'police_evidence')
```
After (server):
```lua
Whip.core:EnsureContainer('mypd:evidence', { x = 441.0, y = -995.0, z = 30.7, heading = 90.0,
  name = 'Evidence', slots = 100, maxWeight = 200,
  requirements = { jobs = 'police', onDuty = true } })
```
Players open it at its spot; from code `OpenStore(source, { kind = 'container', id = container.containerId })` (the id is on the returned definition / `GetContainer({ key = 'mypd:evidence' })`). Fill from code with `StoreGive({ kind = 'container', id = id }, item, n)`. A per-player stash: `CreateContainer({ ..., ownerCharId = charId })` once and remember its id (your own `EnsureTable` row or a flag), not one `RegisterStash` per restart.

### 5. A shop
Before (ox_inventory):
```lua
exports.ox_inventory:RegisterShop('cafe', { name = 'Cafe', inventory = { { name = 'coffee', price = 15 } },
  locations = { vec3(...) }, groups = { cafe = 0 } })
```
After (server):
```lua
Whip.core:EnsureShop('mycafe_shop', { name = 'Bean Machine', mode = 'npc', npcModel = 's_f_y_shop_mid',
  x = -361.0, y = 49.0, z = 54.4, heading = 90.0, blipSprite = 52,
  catalog = { mycafe_coffee = 15 } })
AddEventHandler('whip_core:shop:purchased', function(e)
  if GetInvokingResource() ~= 'whip_core' then return end
  -- e = { shopId, charId, source, items, total, paymentMethod, mode }
end)
```
Modes: `npc` (unlimited, catalog prices, money sink), `infinite` (unlimited, revenue to `jobId`'s business account), `stocked` (a container staff fill, staff-set prices, revenue to the business). Business shop: `mode = 'infinite'|'stocked', jobId = 'mycafe'` (key or id), `containerId` for stocked. For a bespoke counter (one item, no shop UI) use the cafe pattern: AddAction + SecureEvent + `ChargePlayer` → `AddItem` → `RefundPlayer` on failure.

### 6. A job vehicle
Before (qb):
```lua
QBCore.Functions.SpawnVehicle('speedo', function(veh)
  SetVehicleNumberPlateText(veh, 'WORK' .. math.random(1000, 9999))
  exports['LegacyFuel']:SetFuel(veh, 100.0)
  TriggerEvent('vehiclekeys:client:SetOwner', QBCore.Functions.GetPlate(veh))
end, Config.VanSpawn, true)
-- plus a despawn command, a timer, an onResourceStop cleanup...
```
After (server, inside a SecureEvent at the depot):
```lua
local vanId, err = exports.whip_core:SpawnTempVehicle('speedo', Config.VanSpawn, {
  forSource = source, despawnAfter = 1500, tag = 'mydelivery:' .. player.charId, secure = true })
if not vanId then return false, err end
-- fuel only if your server runs whip_fuel and the van should start other than at the stat default:
exports.whip_core:SetVehicleStat(vanId, 'fuel', 100.0, 'job van')
```
The driver gets a key; the van goes after 25 minutes, after 10 idle minutes, on `DespawnVehicle(vanId)`, on `ReleaseTag(tag)` or when your resource stops, firing `whip_core:vehicle:released`.

## The qb delivery job, call by call

| The qb job does | The WHIP version does |
|---|---|
| A job in `shared/jobs.lua` | `Whip.core:EnsureJob('delivery', { ... })` in `Whip.register` |
| qb-target box at the depot, `job = 'delivery'` | `AddAction({ at = { coords = DEPOT }, require = { job = 'delivery', onDuty = true }, ... })` |
| Van deposit `RemoveMoney('bank', 500)` | `ChargePlayer(source, 500, { method = 'bank' })`; keep the receipt |
| `CreateVehicle` + vehiclekeys + `SetFuel` | `SpawnTempVehicle`: the driver gets a key; the van goes on despawn, after `despawnAfter`, or when your resource stops |
| Packages: `AddItem` + ItemBox | `StoreGive` into the van's boot, or `AddItem` |
| Blip and route to the drop-off | `ShowBlip({ people = { source } }, 'drop', { coords = DROP, route = true })` |
| `Progressbar`, then `TriggerServerEvent('delivery:pay')` | prompt at the door; a `SecureEvent` with `near` runs the server's `Progress`, takes the package, pays — `near` closes "fire the pay event from anywhere" |
| Pay `AddMoney('cash', 120)` | `PayPlayer(source, 120, { reason = 'Delivery' })` |
| Van back: refund the deposit | `RefundPlayer(receipt)` within 30 minutes; after that `PayPlayer` |

The full job is `whip_core/docs/examples/whip_delivery_example` (described in core-concepts.md), including logout (`whip_core:player:logout`: run ends, van despawned, packages taken, deposit kept) and the van being taken back (`whip_core:vehicle:released` with `reason ~= 'despawned'`). Its door event uses a per-player `near.at = function(source) return currentStop(runs[source]).coords end`, latches `runs[source]` before any wait, and re-checks `IsSessionCurrent` after each wait.

## What will surprise you

- Declarations go in `Whip.register`, not at the top of a file.
- "Their job" means on duty: `GetPlayerJob` is nil off duty; `GetPlayerRole` is "works there at all". Players clock on in the phone's Business app, or your resource calls `ClockOn`.
- Pay with `PayPlayer`, charge with `ChargePlayer`; no lower-level cash call. Cash is items.
- A receipt lasts 30 minutes; after that refund with `PayPlayer`.
- A bar on the player's game is their word; for anything handed out at the end use the server's `Progress` or a timed use.
- Exports return `false, 'why'` instead of throwing.
- `SetVehicleProperties` on the client takes `{ entity = veh }`; a bare number is a vehicleId.
- Item weight is kg, not grams.
- An action's `require` hides options; it is not security.
- Items you register stay registered after your resource stops (ownerless); everything else is swept.
- `AddItem` never fails for a full inventory unless `noDrop`: it drops at the feet (`'ground'`).
- `GetPlayer({ charId })` is online-only; offline reads go through `GetPlayerMetadata({ charId })`, `GetBalance({ charId })`, `GetCharacterNames({ charId1, charId2 })` (a plain list of charIds).

## Step-by-step porting procedure

1. Inventory the old resource: list every framework call (grep `QBCore.`, `exports.qbx_core`, `ESX.`, `xPlayer`, `Ox.`, `exports.ox_inventory`, `exports.ox_target`, `exports['qb-target']`, `lib.`, `RegisterNetEvent`, `TriggerServerEvent`, `CreateCallback`, `TriggerCallback`, `MySQL`, `.sql`), every net event and what the client sends, every item, job, stash, shop, door, zone, blip, vehicle spawn, command, config value.
2. Decide what to delete (see "Upgrade, don't translate") and what moves into WHIP declarations.
3. New manifest: `dependency 'whip_core'`, `whip_requires`, `@whip_core/lib/satellite.lua`; drop framework imports; `.luarc.json` from the template.
4. Rename everything with your resource prefix (items `myres_x`, events/callbacks `myres:x`, stats, zone ids, permissions).
5. Server `Whip.register`: `RegisterItem`/`RegisterUseHandler` (timed uses), `EnsureJob`, `EnsureContainer`, `EnsureShop`, `EnsureDoors`, `EnsureZone`, `EnsureTable`, `RegisterStat`, `RegisterPermission`, static `ShowBlip`s, and every `SecureEvent`/`SecureCallback`.
6. Rewrite each net event as a SecureEvent: remove client-sent values; add `params` for what must stay; `near` for every place-bound action; `rateLimit`; server checks (duty, permission, items); server `Progress`/`SkillCheck` where a bar/minigame gates a reward; `IsSessionCurrent` after waits; `ChargePlayer` → do → `RefundPlayer` on failure; `return false, 'why'` for every refusal.
7. Client `Whip.register`: `AddAction` prompts with `options` and `require`; zones via `RegisterZone`; UI through `Notify`, `Input`, `Confirm`, `ShowText`; own NUI through `SetScreenOpen`/`BlockControls`/`FreeHands`.
8. Vehicles through `SpawnTempVehicle`/`CreateOwnedVehicle`; keys/fuel via exports/stats; blips via `ShowBlip`; per-run things carry a `tag` and the run ends with `ReleaseTag`.
9. Persistence: flags/metadata for character facts, `EnsureTable` + `CommitWithAction` for your own rows, `GiveOnLogin`/bank `PayPlayer` for offline rewards.
10. Settings: `Whip.configPage` for admin-tunable values, `Whip.playerSetting` for player choices; commands via `Whip.command`.
11. Listen to `whip_core:player:loaded`/`logout` (server) to set up and tear down per-player state; guard with `GetInvokingResource() == 'whip_core'`.
12. Test: start after WHIP's ensures; read the setup report and console (refusals print once with reasons); use `/whip` → System → Monitor for every secure call; walk away during bars; log out mid-run; `restart whip_core` (your resource should come back by itself and re-declare); `whiperrors`.

## Porting checklist

- [ ] No `QBCore`, `qbx_core`, `ESX`, `xPlayer`, `Ox.`, `ox_inventory`, `ox_target`, `qb-target`, `qb-menu`, `qb-input` references left; no framework bridge file.
- [ ] Manifest has `dependency 'whip_core'`, `whip_requires`, `@whip_core/lib/satellite.lua` via `shared_script`; item images in `files {}`.
- [ ] Every declaration is inside `Whip.register` and called through `Whip.core`.
- [ ] All names prefixed with the resource name.
- [ ] Every client→server message is a `SecureEvent`/`SecureCallback`; no plain `RegisterNetEvent` handlers on the server.
- [ ] The client sends no prices, amounts, item names, rewards or coordinates the server trusts; anything sent has `params`.
- [ ] Every place-bound event has `near`; every event has a sensible `rateLimit`.
- [ ] Every reward that follows a bar or minigame uses server `Progress`/`SkillCheck` or a timed use.
- [ ] `IsSessionCurrent(source, player.session)` after every wait before giving/taking.
- [ ] Charges use `ChargePlayer`; failures after charging call `RefundPlayer(receipt)`.
- [ ] Item moves use `StoreMove`/`StoreGive`/`StoreTake`; own rows that must match use `CommitWithAction`.
- [ ] No `.sql` file; own tables via `EnsureTable` with append-only migrations mirrored in the CREATE.
- [ ] Item weights converted to kg; `usable = true` on usable items.
- [ ] Jobs via `EnsureJob`; on-duty checks via `IsPlayerClockedOn`/`GetPlayerJob`; employment via `GetPlayerRole`; rank via job permissions; gangs as jobs.
- [ ] Stashes/shops/doors/zones declared with `Ensure*` (no per-start registration code).
- [ ] Vehicles via `SpawnTempVehicle`/`CreateOwnedVehicle`; no key/fuel/despawn scripts; fuel through the `fuel` stat.
- [ ] Blips via `ShowBlip` (route), cleared with `HideBlip`/tags.
- [ ] Per-run objects carry a run tag and are cleaned with `ReleaseTag`.
- [ ] `charId` saved, never server ids or licenses.
- [ ] Offline rewards via `GiveOnLogin` / `PayPlayer({ charId }, n, { method = 'bank' })`.
- [ ] Admin-tunable values on `Whip.configPage`; player prefs via `Whip.playerSetting`; commands via `Whip.command`.
- [ ] Own NUI uses `SetScreenOpen`, `BlockControls`, `FreeHands`; no per-frame `DisableControlAction` loops.
- [ ] Server handlers of `whip_core:*` events check `GetInvokingResource() == 'whip_core'`.
- [ ] No `while true do Wait(0)` polling where an event/listener exists; loops measured with `/whipcost`.
- [ ] Setup report has no FIX lines for your resource (refusals, `whip_requires`); Monitor shows expected accepts/refusals.
- [ ] Survives `restart whip_core` and `restart <yourres>` with no duplicate blips/prompts/items.

## Gotchas

1. Don't port `RegisterNetEvent` handlers as-is "for now": they bypass every WHIP check and are where dupes live.
2. `GetPlayerJob` ≠ QBCore's `PlayerData.job`: nil off duty. Use `GetPlayerRole` for employment.
3. `require` on actions has no grade/level field; model ranks as job permissions.
4. qb `job = { police = 2 }`-style minimum grades have no direct equivalent; use `jobPermission` + `HasJobPermission`.
5. `RemoveMoney` returning false in qb ≠ WHIP: `ChargePlayer` returns a receipt (keep it) or `false, why`.
6. `RefundPlayer` only works for 30 minutes and only for the resource that charged.
7. Server `Progress` must be inside a SecureEvent, not a SecureCallback (callbacks time out client-side after 10 s).
8. The function-form use handler consumes the item unless it returns `false`; the table form gives the item back on `false` (use `consume = false` to keep tools).
9. `AddItem` returns `'ground'` (truthy) when pockets are full: tell the player, or pass `noDrop = true`.
10. `whip_core:*` events are local events; `RegisterNetEvent` for them is wrong, and a server handler must check the invoker.
11. Flags/metadata reach the player's own game: never store secrets there.
12. `GetPlayer` returns a copy; editing it changes nothing.
13. Item and stat names are a server-wide list; a name another running resource holds is refused (printed once).
14. Weight units differ (grams → kg).
15. `EnsureContainer`/`EnsureShop`/`EnsureZone` keep admin edits until your declaration changes; don't expect a restart to reset a container an admin edited.
16. Duty is not saved; don't port "restore duty on login" logic.
17. Temp vehicles are removed after 10 idle minutes unless `idleDespawn = false`; handle `whip_core:vehicle:released`.
18. A plain number where a person is expected is a server id; pass `{ charId = n }` for characters.

## Docs vs code

1. The Secure Events guide uses param type `'amount'` and RegisterPermission's stub mentions a schema `permission` key; both exist in `server/secure.lua` (`:124`, `:1249`) but are missing from `WhipSecureSchema` in `types/classes.lua:543-587`.
2. Doc "Coming from" says `SetVehicleProperties({ entity = veh }, props)` on the client; the stub's first param is named `vehicle` (`types/client.lua:1066`) — same call, documented as a vehicle reference.
3. The doc example `SetDoorLocked({ key = 'front' }, false)` passes a key reference while the stub names the parameter `doorId` (`types/server.lua:3173`); treat the key form as accepted per docs.
4. `EnsureContainer` and `EnsureDoors` also accept an action-style `require` (taken when it names exactly one rule, refused with more) — only in the stubs (`types/server.lua:2443`, WhipDeclaredDoor `require`), not in the porting docs.
