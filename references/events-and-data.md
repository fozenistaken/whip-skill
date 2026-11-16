# WHIP events, state bags and data structures

Every local event whip_core fires (server and client) with its side, trigger and payload; whip's internal network messages; every state bag key; every shared class/data shape; and short recipes. Built from doc anchors `#server-events`, `#client-events`, `#client-net-messages`, `#data-structures`, `#examples`, verified against `whip_core/types/events.lua`, `types/classes.lua`, `types/director.lua`, `shared/events.lua`, `shared/statebags.lua`, `server/sentinel.lua` and the emit sites in `server/*` and `client/*`.

## Contents
- Event rules (naming, listening, trust)
- Server events: readiness, players and characters
- Server events: items and inventory
- Server events: money
- Server events: vehicles
- Server events: world (doors, zones, time, properties, NPCs, containers)
- Server events: shops and jobs
- Server events: Director and lore
- Client events
- Internal events and network messages (not for you)
- State bags
- Data structures: player
- Data structures: inventory and items
- Data structures: bank
- Data structures: vehicles
- Data structures: jobs, ground items, containers, garages, shops
- Data structures: SecureEvent schema and params
- Data structures: UI, camera, progress, timed use
- Data structures: zones
- Data structures: store addresses and panels
- Examples
- Gotchas
- Docs vs code

## Event rules (naming, listening, trust)

- Name pattern: `whip_core:<domain>:<pastTense>`, ONE table payload (`function(e) ... e.source ... end`). Fields may be added later; don't depend on field count. Defined in `shared/events.lua` as `WhipEmit(name, payload)` = `TriggerEvent(name, payload)`: **local only**, heard by any resource on the same side.
- Names containing `client:` or `server:` are WHIP's own network messages, not events for you (their args change; they reach only a resource that `RegisterNetEvent`s them).
- Listen with `AddEventHandler` (not `RegisterNetEvent`). `AddEventHandler` needs no `Whip.register` wrapper and survives a whip_core restart.
- **Trust:** any server resource can `TriggerEvent` the same name. Before a handler pays out, gives an item, punishes or deletes anything for good, check `if GetInvokingResource() ~= 'whip_core' then return end`, and/or re-ask the authoritative export (named per event below). A handler that only logs or refreshes a display needs no check.
- Client events are local to the player's game. Any client script can fire them too, and the client is untrusted anyway: never grant anything on the server because of a client event.
- Order: inside whip_core, its own hooks (`Character.onLife`, `Vehicles` life hooks, job/NPC/door/container/zone hooks) run first under pcall, then the public event (`server/vehicles.lua:63`, `server/jobs.lua:885`).
- Typing: annotate with the stub class, e.g. `---@param e WhipEvtItemChanged`.

Legend for the "Check" column: **Yes** = verify `GetInvokingResource() == 'whip_core'` (or re-read via the named export) before acting on it with consequences; *log* = only harmless if used for display/logging.

## Server events: readiness, players and characters

| Event | Payload | When | Check |
|---|---|---|---|
| `whip_core:onReady` (S+C) | `WhipEvtReady { reason, resources? }` | whip_core ready for registrations. `reason`: `'coreStarted'` (just (re)started, remembers nothing: register everything) or `'resourceStarted'` with `resources` = names that just started. Fired from `server/player_lifecycle.lua:1523/1567`, `client/ready.lua:76/140`. Use `Whip.register` (lib/satellite.lua) instead, which filters this | n/a |
| `whip_core:player:loaded` | `WhipEvtPlayerLoaded { source, charId, name, newCharacter, player, phantom? }` | Character fully loaded (after the item baseline, `server/player_lifecycle.lua:1029-1039`). `name` = full name, `newCharacter` = true on a brand-new character's first load, `player` = `WhipPlayerData` sheet. `phantom = true` only for whip_test load-test players (`/testload announce=1`, no character in the world; `server/testseams.lua:878`) | Yes if granting |
| `whip_core:player:logout` | `{ source, charId, player, why }` | Character leaving. `why`: `'logout'` (back to char select, `server/player.lua:761`) or `'disconnect'` (`server/player_lifecycle.lua:1205`); test phantoms send `why = 'phantom', phantom = true`. Fired before cleanup; changes a listener makes to metadata/stats are saved afterwards | log |
| `whip_core:player:died` | `{ source, charId, killer, reported }` | Server accepted a death. `killer`: killer's server id when the server saw a player do it (a car's driver counts), else nil. `reported`: the victim game's description of the killing blow, display only | Yes |
| `whip_core:player:revived` | `{ source, charId, how, reason }` | Dead player alive again. `how`: `'revived'` or `'respawned'`. `reason`: `'revive'`, `'respawn'`, `'revive:admin'`, `'revive:self'` | Yes |
| `whip_core:character:created` | `WhipEvtCharacter { source, charId }` | New character created (then auto-loaded) | Yes |
| `whip_core:character:deleted` | `{ source, charId }` | Character deleted. Before removing anything for good, ask `exports.whip_core:IsCharacterDeleted(charId)`; whip's own release does not listen to the event | Yes |
| `whip_core:character:renamed` | `WhipEvtCharacterRenamed { charId, source?, firstName, lastName, name, oldName, by? }` | Admin renamed a character (Player Manager, `Character.rename`, `server/character.lua:357`). Name only; charId and everything keyed by it stay. Online or not (`source` nil when offline). `by` = who renamed. Not in the docs | log |
| `whip_core:flag:changed` | `{ source, charId, name, value, was }` | A character flag set, or cleared (`value` nil). Read truth with `GetPlayerFlag` | Yes |
| `whip_core:permission:changed` | `{ userId, permission, granted }` | Account gained (`granted = true`) or lost a permission. Read truth with `HasPermission` | Yes |

## Server events: items and inventory

| Event | Payload | When | Check |
|---|---|---|---|
| `whip_core:item:added` | `WhipEvtItemChanged { source, item, amount, count, reason?, by? }` | Player carries MORE of an item by any route (export, pickup, purchase, give, stash drag, cash). `amount` = how many arrived, `count` = new total carried. `reason` = caller's own words and `by = 'by <resource>'` only when an export made the change (`server/inventory.lua:1180`) | Yes |
| `whip_core:item:removed` | same | Player carries LESS: used, dropped, sold, given, stashed, taken by export | Yes |
| `whip_core:inventory:changed` | `{ source }` | Anything in the pockets changed, including moves between their own slots. Once per change. Not fired for a `quiet` `SetItemMetadata` | log |
| `whip_core:item:used` | `WhipEvtItemUsed { source, item, slot, addr }` | Item used (hotbar or Use). `slot` = `WhipInventorySlot` data, `addr` = `WhipStoreAddr` (pocket address). The use is already logged: don't write a second `'used'` row | Yes |
| `whip_core:item:given` | `WhipEvtItemGiven { source, target, item, amount }` | One player gave another an item | Yes |
| `whip_core:heldProps:lost` | `{ source, tag, reason, by? }` | Props from your `HoldProps` left the hand without the owner asking. `tag`: a resource's `'<resource>:<tag>'`, or WHIP's own `'emote'`, `'bar'`, `'give'`, `'take'`, `'camera'`. `reason`: `'replaced'` (`by` = the new tag) or `'world'` (moved to another routing bucket). Not fired for a drop the owner asked for, a new set of the same tag, logout or disconnect. `GetHeldPropsTag(source)` returns what is held now | log |
| `whip_core:container:opened` | `{ containerId, source, charId }` | Server opened a stash on a player's screen (E, `OpenStore`, a placed stash point; not the admin page). Their game may still decline. To know it is open now ask Stores (`GetOpenStores`/StoreRead), not the event | Yes |

Rules:
- `item:added` / `item:removed` fire only for the player's pockets: not for an item put in a stash, a rearrangement of own slots, items inside a bag, or logging in (login sets a baseline, `Inventory.resetCarried`).
- No per-move event. `inventory:changed` only says pockets changed: re-read with `GetInventory` / `FindItem`. For move detail use a panel's `onValidate` / `onChange` (`WhipPanelHookCtx`) or `GetOpenStores(source)`.

## Server events: money

| Event | Payload | When | Check |
|---|---|---|---|
| `whip_core:bank:balanceChanged` | `WhipEvtBankChanged` (below) | Any deposit, withdrawal or transfer | Yes |
| `whip_core:bank:accountChanged` | `{ accountId, what }` | Account changed, no money moved. `what`: `'label'`, `'type'`, `'owner'`, `'frozen'`, `'main'`, `'closed'`, `'access'` (`'access'` = Banks page only, not job rank changes) | Yes |

`balanceChanged` payload by `type`:

| type | Fields |
|---|---|
| `'deposit'` | `type, accountId, amount, actorCharId?, newBalance, message?, ownerCharId?, accountType, label` (`accountType`: `'personal'`/`'savings'`/`'shared'`/`'business'`; `server/bank.lua:802,1344`) |
| `'withdraw'` | `type, accountId, amount, actorCharId?, newBalance, message?` only: no owner/type/label (`server/bank.lua:866`) |
| `'transfer'` | `type, fromAccountId, toAccountId, amount, actorCharId?, fromBalance, toBalance, message?, fromOwnerCharId, fromAccountType, fromLabel, toOwnerCharId, toAccountType, toLabel` (no `accountId`/`newBalance`; `server/bank.lua:1011`) |

`Bank.SystemPayFrom` (money made on the spot, e.g. a lore character paying a player) fires TWO events: a `'deposit'` into the payer account (message = its `madeNote`) then a `'transfer'` (`server/bank.lua:1095-1106`). The stub types `type` as `'deposit'|'withdraw'|'transfer'|...`.

## Server events: vehicles

All `whip_core:vehicle:<kind>`; lifecycle ones go through `Vehicles.announce` (core hooks first, `server/vehicles.lua:63`).

| Event | Payload | When | Check |
|---|---|---|---|
| `:created` | `{ vehicleId, ownerCharId }` | A vehicle row minted, by any path (`server/vehicles.lua:1145`) | Yes |
| `:ownerChanged` | `{ vehicleId, from, to }` | Owner charId changed (`server/vehicles.lua:1174`, Vehicle Manager save `server/vehicle_manager.lua:551`) | Yes |
| `:deleted` | `{ vehicleId, ownerCharId, wasOut }` | Record deleted (`server/vehicles.lua:1296`) | Yes |
| `:spawned` | `{ vehicleId, entity, netId, plate, model, session, temp? }` | Entity in the world. Owned car: `session = false`; temp car: `session = true, temp = true` (`server/vehicles.lua:2831,3173,3535`) | log |
| `:despawned` | `{ vehicleId, netId }` | Entity removed; next spawn gets a new netId (`server/vehicles.lua:2979`) | log |
| `:damageCleared` | `{ vehicleId }` | WHIP cleared a car's recorded damage for a repair (`ClearVehicleDamage`, `server/vehicle_damage.lua`; whip_core 1.2.0+). The entity is not repaired by it | log |
| `:released` | `{ vehicleId, reason, temp }` | Session/temp car no longer tracked (entity may remain). `reason`: `'expired'` (despawnAfter), `'idle'` (nobody near 10 min), `'gone'` (entity already left), `'stopped'` (spawning resource stopped), `'despawned'`, `'deleted'`, `'failed'` (SpawnTempVehicle couldn't finish), default `'released'` (`server/vehicles.lua:3035-3056`). Per-vehicle bookkeeping belongs to the id: clean up here | log |
| `:registered` | `{ vehicleId, plate, model, session, source }` | A street car adopted into the framework, first time only (`session = true`; `source` = reporter; `server/vehicles.lua:3375`) | log |
| `:dataChanged` | `{ vehicleId, key?, value?, old?, cleared, resource }` | `SetVehicleData` change; a full clear sends `key = nil, cleared = true` (`server/vehicle_data.lua:318,551`). Prefer the targeted `OnVehicleDataChanged` listener, which is fed from the write, not the event | Yes |
| `:lockChanged` | `{ vehicleId, plate, locked, source? }` | Locked/unlocked (fob, lockpick, `SetVehicleLocked`, admin), only on a real change. `source` nil when no player did it (`server/vehicles.lua:1855`) | Yes |
| `:lockpicked` | `{ vehicleId, plate, source }` | Lockpicked (with `:lockChanged`) | Yes |
| `:entered` | `{ vehicleId, plate, source, seat, previousSeat? }` | Got into, or moved seat in, a framework vehicle, server-checked. `seat` -1 = driver. `previousSeat` = seat moved from inside the same car, nil when getting in. In a different car with no exit between, an `:exited` for the old one fires first. Taking the driver's seat puts a strip key into an empty ignition | log |
| `:exited` | `{ vehicleId, plate, source, seat, left? }` | Left the seat. `left`: `'logout'` / `'dropped'` when leaving the game, nil when they got out. Getting out unlocks the car (if `Config.UnlockOnExit`) and returns a strip key; leaving the game changes neither | log |
| `:claimed` | `{ vehicleId, from, ownerCharId }` | `ClaimVehicle` made an unowned car someone's: `vehicleId` = new car id, `from` = old session id | Yes |
| `:plateChanged` | `{ vehicleId, from, to }` | `SetVehiclePlate` changed a plate | log |

Fuel is not whip_core's: whip_fuel announces `whip_fuel:nozzleTaken / :nozzleInserted / :nozzleRemoved / :nozzleDropped / :nozzlePickedUp / :nozzleTorn / :nozzleReturned` (payloads in `whip_fuel/server/pumps.lua`).

## Server events: world (doors, zones, time, properties, NPCs, containers)

| Event | Payload | When | Check |
|---|---|---|---|
| `whip_core:door:lockChanged` | `{ doorId, locked, source?, cause }` | Real change only. `cause`: `'press'`, `'lockpick'`, `'autolock'`, `'code'` (default), `'released'` (a `HoldDoor` ended), or the caller's own cause. Truth: `IsDoorLocked` | Yes |
| `whip_core:door:denied` | `{ doorId, source, reason }` | A press refused. `reason` is what that player was told: don't show it to others | log |
| `whip_core:zone:entered` | `WhipEvtZoneServer { zoneId, key?, source }` | Player entered a zone with `trackPlayers = true` (checked about once a second) | Yes |
| `whip_core:zone:exited` | `{ zoneId, key?, source, dropped?, removed? }` | Left. `dropped` = left the server inside; `removed` = zone removed | Yes |
| `whip_core:time:changed` | `{ hour, minute }` | Server time set (export or dev tool) | log |
| `whip_core:time:freezeChanged` | `{ frozen }` | Frozen or unfrozen | log |
| `whip_core:weather:changed` | `{ weather }` | Server weather changed | log |
| `whip_core:property:ownerChanged` | `{ propertyId, ownerCharId?, previousOwnerCharId?, by? }` | Given to someone, or made unowned (`ownerCharId` nil); every key taken back. `by` = charId who did it | Yes |
| `whip_core:property:keyGranted` | `{ propertyId, charId, by? }` | Key given (`charId` = keyholder) | Yes |
| `whip_core:property:keyRevoked` | `{ propertyId, charId }` | Key taken back | Yes |
| `whip_core:npc:spawned` | `{ npcId, tag, owner, netId, model, coords, lore?, look? }` | `SpawnNpc` NPC made (`lore`, `look` extra in code; `look` is a flag, `true` or nil, not the look table: `server/npcs.lua:885-886`) | log |
| `whip_core:npc:despawned` | `{ npcId, tag, owner, reason }` | `reason`: `'removed'`, `'stopped'`, `'released'`, `'lost'`, `'corpse'` | log |
| `whip_core:npc:damaged` | `{ npcId, tag, owner, amount, health, armour, attacker?, group? }` | Took damage. `attacker` server id or nil, `group` its group's name | Yes |
| `whip_core:npc:killed` | `{ npcId, tag, owner, killer?, weapon, coords }` | Died. A car's driver is attacker/killer of a run-over. Never pay out on the event alone: ask `GetNpc` (its `killer`, `killedAt`, `weapon` are the server's reading) | Yes |

## Server events: shops and jobs

| Event | Payload | When | Check |
|---|---|---|---|
| `whip_core:shop:purchased` | `{ shopId, charId, source, items, total, paymentMethod, mode }` | Purchase completed. `items` = delivered lines only: `{ itemKey, amount, price }` (`price` = unit price; `server/shops.lua:2441-2460`). `mode` = shop mode | Yes |
| `whip_core:shop:opened` / `:closed` | `{ shopId, source, charId }` | Player opened / closed a shop | log |
| `whip_core:shop:created` / `:updated` | `{ shopId, shop }` | Created (export or dev tool) / updated; `shop` = definition | log |
| `whip_core:shop:deleted` | `{ shopId }` | Deleted | log |
| `whip_core:shop:priceChanged` | `{ containerId, item, slot?, price, forSale }` | A stocked shop's item priced or taken off sale; one price per item; `slot` when set from a shelf slot | log |
| `whip_core:job:created` | `{ jobId, key, name }` | Job made | Yes |
| `whip_core:job:updated` | `{ jobId, key, name, icon, ownerCharId, oldOwnerCharId }` | Changed | Yes |
| `whip_core:job:deleted` | `{ jobId, key }` | Deleted (fires only this; no per-employee `fired`) | Yes |
| `whip_core:job:hired` | `{ jobId, key, charId, source?, roleId, role, by }` | Hired. `role` = role name, `by` = hirer charId. `source` only while online | Yes |
| `whip_core:job:fired` | `{ jobId, key, charId, source? }` | Fired | Yes |
| `whip_core:job:roleChanged` | `{ jobId, key, charId, source?, roleId, role, oldRoleId }` | Role changed | Yes |
| `whip_core:job:clockedOn` / `:clockedOff` | `{ jobId, key, charId, source }` | On / off duty by any route (logout included); real changes only | Yes |

Every job event payload is built by `emitJobEvent` (`server/jobs.lua:880-897`): base `{ jobId, key, charId, source }` (charId/source nil for job-level events) merged with the extras above. Duty is also the `whipJob` player state bag (below).

## Server events: Director and lore

Sent AFTER the Director scheduler pass, never from inside it, and never for a builder's Test (except `run:thingMade`). `run` is a `DirectorRunView` copy (types/director.lua: `id, tag, scenario, name, rev, test, kinds, where?, players, starter?, startedAt, seconds, endsIn?, vars, objectives, things`). Give `run.tag` to anything you make for the run: it goes when the run ends; later creates under it are refused. An ended run is no longer there for `GetScenarioRun` to confirm, so check `GetInvokingResource() == 'whip_core'` before paying out.

| Event | Payload | When |
|---|---|---|
| `whip_core:run:started` | `{ run, startedBy = { mode, by } }` | `mode`: `'interaction'`, `'press'`, `'area'`, `'item'`, `'timer'`, `'script'` (`by` = resource), `'hand'` (admin/editor), `'enabled'` (scenario switched on: started with NOBODY in it, again after each run; its job begins as the first player joins, `run.begunAt`) |
| `whip_core:run:ended` | `{ run, outcome, reason, vars, payout, faultCard, stopping }` | `outcome`: `'succeeded'`, `'failed'`, `'calledOff'` (Call Off card), `'aborted'` (admin, last player leaving, whip_core stopping), `'faulted'`. `payout` floored integer. `faultCard = { id, type }` or nil. `stopping` = whip_core is stopping |
| `whip_core:run:playerLeft` | `{ run, source, charId, why, by, runEnds }` | Player left before the end (logout, disconnect, or a script: `by` = resource). `run` is without them; `runEnds` = it ends with them (sent before `run:ended`) |
| `whip_core:run:playerJoined` | `{ run, source, charId, by }` | A script added a player (`AddPlayerToScenarioRun`, `by` = resource) |
| `whip_core:run:signalled` | `{ run, name, data = { value }, source }` | A Send Signal card fired (`name` e.g. `'alarm'`) |
| `whip_core:run:thingMade` | `{ run, world, kind, label, netId, npcId, vehicleId, containerId, groundId, doorId, model, data }` | The run made something for a placed thing. `data = { [resource] = what it keeps }`; yours at `data[GetCurrentResourceName()]`. `netId` may be nil briefly after a car is made. Sent for a Test too (`run.test`). The Always-present layer sends it as the scenario switches on, with no run: `{ scenario, standing = true, test?, world, kind, ... }`. Not in the docs |
| `whip_core:scenario:switchedOn` | `{ scenario, name, rev, replaced, by }` | `replaced` = another revision was on; `by` = `{ source, name }` (player) / `{ resource }` (`SwitchScenario`) / nil (server) |
| `whip_core:scenario:switchedOff` | `{ scenario, name, rev, why, by }` | `why` default `'switched off'` |
| `whip_core:lore:changed` | `WhipEvtLoreChanged { key, character?, retired }` | Lore character made, changed or retired (`server/director/lore.lua:274`). `character` = `GetLoreCharacter` shape `{ key, name, model, bankName, payName, notes, retired, accountId }`. Not in the docs |

## Client events

Fired on each player's game about the local player. All local (`WhipEmit`).

### Loading and life

| Event | Payload | When |
|---|---|---|
| `whip_core:onReady` | `{ reason, resources? }` | As on the server. Use `Whip.register` |
| `whip_core:player:loaded` | `{ source, charId, name, newCharacter, player }` | Character in the world and picture back. The safe "player is ready" hook: `PlayerData` and inventory populated. Same table as the server's (`client/player.lua:201`) |
| `whip_core:player:spawned` | `{}` | Just put into the world: after every load, and again for a new character when the appearance creator closes |
| `whip_core:player:died` | `{ reconnected, respawnRefused }` | Died. `reconnected` = loaded in already dead. `respawnRefused` = server refused a too-early respawn, so the same death is back after a `revived` was already announced |
| `whip_core:player:revived` | `{ how }` | `'revived'` (where they lay) or `'respawned'` (hospital) |
| `whip_core:player:logout` | `{ charId? }` | Logging out to character select |
| `whip_core:player:renamed` | `{ charId, firstName, lastName, name }` | Local character renamed; `PlayerData` names already changed. Not in docs |
| `whip_core:death:screenChanged` | one of `{ state='count', left, total }` · `{ state='ready', progress, key }` · `{ state='held', label }` (a HoldRespawn) · `{ state='off' }` · `{ hidden }` | What the death screen shows, for a resource drawing its own (`Config.DeathScreen = false`). `left`/`total` seconds; `progress` 0-100 of E/A held; `key` = Interact key name; `hidden` = player hid it (H / Y). Not in this docs section |
| `whip_core:appearance:modelChanged` | `{}` | Ped rebuilt with a new model (load, `/charedit`). Starts with default walk, clipset, face: re-apply yours here |
| `whip_core:devtools:modeChanged` | `{ on }` | Developer mode on/off (the /w switch, or server taking dev tools away). Off at every join and whip_core start; `HasDevTools()` gives current state. For developer-only UI; server re-checks |
| `whip_core:permission:changed` | `{ permission, granted }` | This account gained or lost a permission, on every player game on that account. WHIP shows nothing |
| `whip_core:voice:rangeChanged` | `{ index, name, level }` | Voice-range key (Z). `index` 1 whisper / 2 normal / 3 shout; `name` `'Whisper'|'Normal'|'Shout'`; `level` 20/50/100 (bar %). Not in docs |
| `whip_core:voice:systemChanged` | `{ resource?, label?, features? }` | A voice resource started/stopped being the voice system; all nil when none. `features` as `GetVoiceSystem`. Not in docs |

### Jobs and the Director

| Event | Payload | When |
|---|---|---|
| `whip_core:job:clockedOn` / `:clockedOff` | `{ jobId, key }` | Local player on/off duty |
| `whip_core:job:listChanged` | `{ jobs }` | Hired, fired, promoted, job renamed. `jobs` = what `GetPlayerJobs` returns (`table<number, WhipPlayerJobInfo>`) |
| `whip_core:run:joined` / `:updated` | `{ runId, scenario, name, objective, countdown }` | In a Director run / its objective or clock changed. `countdown` = seconds left or nil. An update for a run this game never heard of is sent as `joined`. Never a Test. `GetPlayerScenarioRuns()` returns the same |
| `whip_core:run:left` | `{ runId, scenario, name, why }` | Left a run |
| `whip_core:run:ended` | `{ runId, scenario, name, outcome, payout }` | Run ended for them |
| `whip_core:director:builderCopy` | `{ id, kind, model, entity, data, driven }` | World builder made its local copy of a scenario car/NPC/prop a resource keeps data on (`data[GetCurrentResourceName()]`): dress it as a run would. Also a take's copies (`driven = true` on the car driven while recording). Not in docs |

### Screens and input

| Event | Payload | When |
|---|---|---|
| `whip_core:ui:stateChanged` | `{ open }` | A screen/dialog opened (`true`) or all closed (`false`): the `IsAnyScreenOpen` question. A progress bar alone doesn't fire it |
| `whip_core:ui:cleanScreen` | `{ on, world }` | Screen clean for a recording (Camera Creator). Hide your UI while `on`; hide your in-world things (DUI) only while `world` (the camera item keeps world things) |
| `whip_core:hands:blocked` | `{ label, only }` | A `BlockHands` began. `only` = `'weapons'`, or nil = everything (also runs the `'freeHands'` moment). Every block covers weapons |
| `whip_core:hands:unblocked` | `{}` | The last block went |
| `whip_core:hotbar:slotUsed` | `{ slot }` | Hotbar slot 1-5 used (number key or pad wheel), just before the server is asked: put away what must not stay up through a use. Not in docs |
| `whip_core:pad:deviceChanged` | `{ pad }` | Keyboard <-> pad, settled for 400 ms; also once at start. Swap your button hints here, not on a timer |
| `whip_core:keyboard:opened` / `:closed` | `{ id, owner }` / `{ id }` | On-screen keyboard (`OpenKeyboard`) up / gone. `owner` = requesting resource. Each `opened` gets one `closed`. Leave the pad alone between (`Whip.padScreen` does) |
| `whip_core:nui:capsDetected` | the `GetNuiCaps` table | Browser capabilities known/changed: `chrome` (version, 0 if unknown), `has`, `colorMix`, `relativeColor`, `textBalance`, `startingStyle`, `heightAuto`, `anchor`, `fieldSizing`, `viewTransitions`, `schedulerYield`, `webgpu`, `zoomScreenPx` (false on Chromium 103), `gameView` (all booleans) |
| `whip_core:ask:cancelled` | `{ token }` | whip_core gave up on a question (timeout, run end, logout): take down your `RegisterAskChannel` screen |

### World and vehicles

| Event | Payload | When |
|---|---|---|
| `whip_core:zone:entered` / `:exited` | `{ zoneId, key?, label?, group? }` | Local player entered/left a zone. Match on `key` (the `EnsureZone` name) |
| `whip_core:weather:layerChanged` | `{ name, layer? }` | A local time/weather layer set (`layer` = its settings) or removed (`layer` nil) |
| `whip_core:vehicle:entered` | `{ vehicleId?, entity, plate, seat }` | Got into ANY vehicle or changed seat. Driver `seat == -1`. `vehicleId` nil until known / non-WHIP car. Also fired for a car the player is already in when whip_core starts |
| `whip_core:vehicle:exited` | `{ vehicleId?, entity, plate?, seat }` | Got out of any vehicle (server sends its own `:exited` once it agrees) |
| `whip_core:vehicle:copied` | `{ entity, of }` | This game made its own copy of networked car `of` (Experimental recorded drive sync). Draw on the copy what you draw from `of`'s data (`GetVehicleData({ entity = of }, key)`). Not in docs |
| `whip_core:property:entered` / `:exited` | `{ propertyId, name }` | Walked into / out of a property (`GetCurrentProperty` follows) |
| `whip_core:property:furnished` | `{ propertyId, interiorId, count }` | Its furniture is up on this client (`count` pieces) |
| `whip_core:property:unfurnished` | `{ propertyId, interiorId }` | Taken away (walked off, interior unloaded/redrawn, furnisher opened) |
| `whip_core:property:furnishStateChanged` | `{ propertyId, interiorId?, state }` | `GetInteriorFurnishState` changed: `'pending'`, `'done'`, `'none'`, `'idle'`. `interiorId` nil until first ready |

## Internal events and network messages (not for you)

`whip_core:client:*` = whip_core server -> its own client (all exist in code). Not events: they reach only a resource that `RegisterNetEvent`s them, arguments change, several fire at the START of something. Use the public events.

| Message | Arguments | Use instead |
|---|---|---|
| `whip_core:client:playerLoaded` | `serializedData` (`.isNewCharacter` on first load) | `whip_core:player:loaded` |
| `whip_core:client:playerLogout` | none | `whip_core:player:logout` |
| `whip_core:client:updateCash` | `cashTotal` | cash: `GetPockets`/inventory reads |
| `whip_core:client:inventoryUpdate` | `{ inventory, weights }` | — |
| `whip_core:client:vehicleLockState` | `vehicleId, locked` (players near the car) | `whip_core:vehicle:lockChanged` (server) |
| `whip_core:client:vehicleKeysSync` | `keysTable` | — |
| `whip_core:client:notify` | `message, kind, duration` | `NotifyPlayer(source, text, kind)`, or `return false, text` in a SecureEvent |
| `whip_core:client:groundItemCreated` / `Deleted` | `data` / `id` | — |
| `whip_core:client:containerCreated` / `Deleted` | `def` / `containerId` | — |
| `whip_core:client:jobsSync` | `jobsTable` | `whip_core:job:listChanged` |
| `whip_core:client:jobClockState` | `jobId, state` (`true` = on) | `whip_core:job:clockedOn/Off` (client) |
| `whip_core:client:permissionChanged` | — | `whip_core:permission:changed` (client) |
| `whip_core:client:directorRun` | `op, info, extra` | `whip_core:run:joined/updated/left/ended` |

Other internal local events (plumbing; don't fire or rely on them): `whip_core:cost:started { seconds }` / `:stopped {}` / `:reported` / `:askedReported` / `:serverStarted` / `:serverStopped` / `:serverReported` (the `/whipcost` protocol, answered automatically by `lib/cost.lua` and `lib/satellite.lua`), `whip_core:errorTap:report` (error collection, `shared/error_tap.lua:206`), `whip_core:probe:ask` / `:answer` (`client/screen_probe.lua`). The `whip_core:server:*` names are client -> server net events (e.g. `whip_core:server:useItem`, `whip_core:server:vehicleSeat`).

## State bags

No `GlobalState` key is written by whip_core (none found in source). All keys are named in `shared/statebags.lua`.

### Player bags (`Player(src).state.<key>`)

Watched by the Sentinel (`server/sentinel.lua:492-498`). whip_core writes them only through `Sentinel.setPlayerKey`. A direct `Player(src).state.x = ...` write to one of these, from a client or another resource, is treated as tampering: reverted and logged. Prefixed `whip` so another resource's `isDead` stays its own. No name or charId is ever put in a bag (bags replicate to every client).

| Key | Constant | Value | Lifecycle |
|---|---|---|---|
| `whipDead` | `PLAYER_DEAD_KEY` | boolean | Set to `player.isDead` at load; `true` on death, `false` on revive; cleared (absent) at logout |
| `whipJob` | `PLAYER_JOB_KEY` | job KEY string while on duty, else `false` | `false` at load (not clocked on yet); key on clock-on; `false` or the next on-duty job's key on clock-off; absent at logout. A late-starting resource can read duty here |
| `whipEscorted` | `PLAYER_ESCORTED_KEY` | boolean | `false` at load; `true` while escorted |
| `whipEscortedBy` | `PLAYER_ESCORTER_KEY` | escorter's server id, or nil | Set with escort, nil when it ends |
| `whipDamageMod` | `PLAYER_DMGMOD_KEY` | number, ABSENT when exactly 1.0 | Damage modifier; clients clamp to `Config.Sentinel.damageModifierClamp` (default 0.05-4.0, `client/stats.lua:657`) |
| `whipMeleeMod` | `PLAYER_MELEEMOD_KEY` | number, ABSENT when 1.0 | Melee modifier |
| `whipMood` | `PLAYER_MOOD_KEY` | facial expression (a `/mood` name), ABSENT for none | From metadata `mood` at load |

At their default, modifiers and mood are absent (never 1.0 or ''). Dead, escorted and job go `false` when they end and are cleared at logout. Read from any side: `Player(id).state.whipDead`, `Player(source).state.whipJob`.

### Entity bags (`Entity(ent).state.<key>`)

| Key | Constant | Value |
|---|---|---|
| `whipVehicleId` | `VEHICLE_STATE_KEY` | The vehicle's whip id, stamped when the server creates or adopts it; replicates with the entity so a client knows which car it is on stream-in |
| `whipVehicleSession` | `VEHICLE_SESSION_KEY` | `true` on street cars whip adopted; absent on owned cars (never written `false`) |
| `whipStats` | `VEHICLE_STATS_KEY` | Table of stored stat values `{ fuel = 62.5, nitro = 40, ... }`; any change re-replicates the whole table. Absent key = at registered default (a full tank reads nil). Presence = car has the stat. Never read raw: client `ResolveVehicleStat` / `GetVehicleStat` |
| `whipLive` | `VEHICLE_LIVE_KEY` | Current value of every `live` stat `{ boost = 87.4 }` (changes several times a second); the copy in `whipStats` is stale for live stats |
| `whipAppearance` | `VEHICLE_APPEARANCE_KEY` | Stored appearance block (colours, mods, extras), written at spawn and every change, applied client-side. Absent = stock |
| `whipVehData` | `VEHICLE_DATA_KEY` | Per-vehicle resource data `{ turbo_mod = true }` (`SetVehicleData`); opaque, json-encodable, persisted. Stored values only |
| `whipVehDoors` | `VEHICLE_DOORS_KEY` | Open doors bitmask: bit N = door N open (0-3 doors, 4 bonnet, 5 boot, 6/7 rear doors). Absent = all closed. Server keeps the truth and never reads the bag back; Sentinel restores a forged mask |
| `whipOvHold` | `ENTITY_OV_HOLD_KEY` | Object Viewer admin hold bitmask: 1 hidden, 2 invincible, 4 frozen. Absent = none. Every owning client applies it |
| `whipEngineHold` | `VEHICLE_ENGINE_HOLD_KEY` | Reason a car's engine won't run (`HoldVehicleEngine`), shown to the driver; absent when not held |

### Writing your own keys (SERVER)

- `RegisterSentinelKey(def)` — `def = { key, family = 'player'|'entity', truth = fn|nil }` (`truth` required for entity). Call from `whip_core:onReady` / `Whip.register`. Same again is a no-op; another resource's key is refused `(false, reason)`; unwound when your resource stops.
- `SetSentinelPlayerKey(src, key, value)` -> `true` | `false, reason` (`'key (string) is required'`, `'no such player'`, `'key "x" is owned by y'`). Your own keys only; whip's refused to everyone else; an unwatched key is anyone's.
- `SetSentinelEntityKey(entity, key, value)` -> `true` | `false, reason` (`'no such entity'`, owned by another, `'watched as a player key'`). Writes with whip's own flag so a mismatch during it isn't blamed on the driver. Change your truth first, then write.

## Data structures: player

### WhipPlayerData — what every `GetPlayer*` export returns (plain data, no methods)
| Field | Type | Meaning |
|---|---|---|
| source | number | Server id |
| session | number | This character load's number: pass to `IsSessionCurrent` after a wait |
| userId | number | Account id (persists across characters) |
| charId | number | Active character id |
| firstName, lastName | string | |
| fullName | string | `firstName .. ' ' .. lastName` |
| dateOfBirth | string | |
| gender | `'male'|'female'` | |
| cash | number | Cash on hand (computed) |
| position | `{ x, y, z, w }` | Position + heading when the sheet was made (read live) |
| health | number | Ped health 0-200 |
| armour | number | 0-100 |
| isDead | boolean | |
| metadata | `table<string, any>` | Persistent metadata |

The sheet drops the four identifiers (own export) because the same sheet goes to the client on load. A SecureEvent with `sheet = 'light'` gets only `source, userId, charId, names, dateOfBirth, gender, isDead`.

### WhipPlayer — the live object, inside whip_core only
Fields: `source, userId, charId, firstName, lastName, fullName, dateOfBirth, gender, position (vector4, last known), health, armour, isDead, metadata, license, steam?, discord?, fivem?`.
Methods: `:getMetadata(key?)`, `:setMetadata(key, value) -> ok, err`, `:getCoords() -> vector4`, `:save(teardown?, seatNoted?) -> ok`, `:kick(reason)`, `:logout(invoker?)`, `:serialize() -> table`, `:getCash() -> number`, `:addCash(amount, why?, withNext?) -> ok, err`, `:removeCash(amount, why?, withNext?) -> ok, err` (`withNext` is whip_core-only). A metatable doesn't cross a resource boundary: satellites never get these methods.

## Data structures: inventory and items

- **WhipInventorySlot**: `item` (key), `amount`, `metadata?` (table).
- **WhipInventoryCache** (`GetInventory(source)`): `player = table<slot, WhipInventorySlot>` (1-30), `accessory = table<slot, WhipInventorySlot>` (1-5); a server that adds a pocket adds a field. Sparse: empty slots are absent.
  ```lua
  { player = { [1] = { item = 'food', amount = 3 },
               [3] = { item = 'vehicle_key', amount = 1, metadata = { vehicleId = 42, plate = 'ABC123', model = 'adder' } } },
    accessory = { [4] = { item = 'id_card', amount = 1 } } }   -- accessory slots 4 and 5 take anything
  ```
- **WhipFoundItem** (`FindItem` / `FindAllItems`): `item`, `amount`, `metadata?` (a copy), `addr` (`WhipStoreAddr` `{ kind='player', id=source, sub=pocket, slot }`).
- **WhipItemDef** (`RegisterItem` / `Config.Items`): `name` (display), `desc?`, `weight` (kg per unit), `type?` (category label), `stack?`, `maxStack?`, `image?` (path in the registering resource; default `'html/img/items/<key>.png'`, needs `files { 'html/img/items/*.png' }`), `usable?`, `cooldown?` (s), `prop?`, `grab?` (`'1h'` default / `'2h'`), `playerWalk?` (default false: keep own walk while holding out), `metaFields?` (`{ key, label, format?, value? }` tooltip rows; `value` shown when metadata lacks `key`), `fuelCapacity?` (fuel can for whip_fuel; metadata `fuel` 0-100), `defaultAction?`, `contextOptions?` (`{ action, label, order?, when?, whyNot?, require?, anywhere? }`: under Use, lowest `order` first; Give/Place/Split/Destroy below; `anywhere = true` offers it in a boot/stash/bag), `groundOptions?` (max 3 `{ action, label, icon? }`; picks up then runs the option on the landed slot), `images?` (`{ when?, image }`; `{field}` and `{make}` placeholders), `pictureFields?` (`{ key, label?, type? = 'bool'|'number'|'text' }`), `settings?` (max 20 entries `{ key, type = 'int'|'number'|'bool'|'string'|'enum', default, label, min?, max?, step?, unit?, maxLen?, nullable?, options?, help? }`, read with `GetItemSetting`).
- **WhipAddItemOpts** (`AddItem`'s last arg, or a plain reason string): `reason?`, `noDrop?` (refuse instead of dropping at feet), `pocket?` (`'player'|'accessory'`), `coords?` (vector3 drop point).

## Data structures: bank

- **WhipBankAccount**: `accountId`, `accountNumber` (e.g. `'WB-123456'`), `label`, `type` (`'personal'|'savings'|'business'|'shared'`), `ownerCharId?` (nil for a job's account), `jobId?`, `balance`, `isDefault`, `frozen`, `createdAt` (epoch s), `closedAt?`, `role?` (`'owner'|'manager'|'withdraw'|'deposit'|'view'`; only from `GetCharacterBankAccounts`).
- **WhipBankTransaction** (`GetBankTransactions` row): `txId`, `fromAccountId?` (nil for deposit), `toAccountId?` (nil for withdrawal), `type` (`'deposit'|'withdraw'|'transfer'|'payment'`), `amount`, `fromBalance?`, `toBalance?` (balances after), `actorCharId?`, `message?`, `createdAt`. A transfer appears in both accounts' histories: compare `fromAccountId` with yours to tell out from in.
- **WhipBankAccess** (`GetBankAccessList` row): `charId`, `role`, `grantedAt`, `grantedBy?`.
- Bank event payload: see Server events: money.

## Data structures: vehicles

### WhipVehicleContext — server `GetVehicle` / `GetVehiclesOf` / `GetGarageVehicles` and the `'vehicle'` SecureEvent param (a COPY, safe to keep and change)
| Field | Type | Meaning |
|---|---|---|
| vehicleId | number | |
| plate | string | |
| model | string | Model name |
| displayName | string? | From the vehicle catalog; nil for a model it lacks |
| class | number? | GTA class from catalog |
| vehType | string | `'automobile'`, `'bike'`, `'boat'`, `'heli'`, ... |
| session | boolean | True for a car nobody owns: adopted street traffic OR a temp car |
| temp | boolean | `SpawnTempVehicle` car (rental, job van); `session` true too |
| secure | boolean | Temp car made with `secure = true`: no lockpick, no ignition hack |
| owner | WhipVehicleOwnerInfo | `{ charId (0 if unowned), name? (nil if offline/unowned), online }` |
| state | string? | `'out'` or `'garaged'` (docs also list `'impounded'`) |
| garage | string? | Garage key while garaged |
| coords | vector3? | Where it is, or where parked |
| heading | number? | |
| spawned | boolean | In the world |
| entity | number? | Server entity while spawned |
| netId | number? | While spawned |
| locked | boolean | |
| occupants | table? | Only with `{ occupants = true }` |
| stats | `table<string, number>` | Stats it carries, e.g. `{ fuel = 85.0 }` |
| data | `table<string, any>` | `SetVehicleData` keys; always a table |
| properties | table? | Saved look (paint, mods) |
| storage | table? | `{ trunk = { slots, maxWeight, used }, glovebox = {...} }` only when already loaded |
| storageLoaded | boolean | Whether `storage` is filled |

- **WhipVehicleDef** (row shape): `vehicleId, ownerCharId, model, plate, state ('out'|'garaged'|'impounded'), garage?, fuel (0-100), properties?, x?, y?, z?, heading?, trunkSlots?, trunkMaxWeight?, gloveboxSlots?, gloveboxMaxWeight?, locked, createdAt, session?`.
- **WhipNearbyVehicle**: `entity, plate, vehicleId?, distance (m), model?`.
- **WhipVehicleRef** (every vehicle/stat/data export, both sides; fill ONE): `{ id }`, `{ vehicleId }`, `{ entity }`, `{ plate }` (spaces ignored), `{ netId }`. A bare number is a vehicleId everywhere, so an entity handle must be `{ entity = veh }`. A `GetVehicle` snapshot is itself a ref.
- **WhipVehicleChange** (listener arg with `{ table = true }`): `vehicleId, key, value (nil when cleared), old?, cleared, source?` (server stats only: `'direct'`, `'refuel:pump'`, `'now'`...), `resource?` (server data only), `entity?` (client only).
- **WhipVehicleListenOpts** (`OnVehicleStatChanged` / `OnVehicleDataChanged`): `table?`, `now?` (`true` = call once now for every car already carrying it; `'all'` = server, named stat: every car incl. defaults).
- **WhipTempVehicleOpts** (`SpawnTempVehicle`): `plate?` (<=8 chars, generated), `vehType?` (from catalog), `forSource?` (gets a key unless `giveKey = false`), `giveKey?` (default true with forSource), `despawnAfter?` (s, even while driven), `locked?` (spawns locked unless false), `keyInIgnition?`, `idleDespawn?` (false = never removed for 10 min idle), `tag?` (`ReleaseTag(tag)` removes; no spawns after release), `secure?`, `bucket?` (default 0).
- **WhipVehicleStatConfig** (`RegisterVehicleStat`): `default?` (0), `min?` (0), `max?` (100), `persist?` (true; `'presence'` = only that the car has it), `decay?` (points per `decayInterval`; negative drains; OMIT to disable, 0 does not disable), `decayInterval?` (10 s), `hud?`, `consume?`, `display?`.
- **WhipVehicleStatHudConfig**: `icon?` (SVG path; omit for built-in fuel/boost/nitro), `iconCritical?` (`|`-separated paths), `color` (hex), `order?` (99), `iconOnly?` (never with showAboveZero), `heartbeat?`, `hideWhenEmpty?`, `noCritical?` (no red below 20%), `showAboveZero?`.
- **WhipVehicleStatConsumeConfig**: `maxRate` (units/s flat out, REQUIRED; more is refused as a lie), `driverOnly?` (true), `clearAtMin?` (false; true for installables), `slack?` (1.25), `interval?` (1.0 s report period).
- **WhipVehicleStatDisplay**: `unit?` (<=8 chars; `'°'`/`'%'` join the number), `range?` (`{ bottom, top }`), `points?` (2-16 `{ percent, reading }`), `decimals?` (0/1/2), `ends?` (`{ empty, full }`, <=3 chars each). Give `range` OR `points` (with `unit`), and/or `ends`.

## Data structures: jobs, ground items, containers, garages, shops

- **WhipJobDef**: `jobId, key, name, icon?, ownerCharId? (holds top role and business account), settings? (incl. permissions { name = label } and selfClockOn), createdAt, createdBy?`.
- **WhipJobRole**: `roleId, jobId, name, level (1-100; 100 holds every permission), permissions`.
- **WhipJobPermissions**: `canHire?, canFire?, canPromote?, canDemote?, canManage? (roles, shop stock/prices), bankAccess? ('none'|'view'|'deposit'|'withdraw'|'manager')`; a job's own permissions sit beside as `name = true`.
- **WhipJobEmployee** (`GetJobEmployees`): `charId, roleId, roleName?, roleLevel?, hiredAt, hiredBy?, onDuty, source?`.
- **WhipPlayerJobInfo** (`GetPlayerJobs` / `GetPlayerJob`, both sides): `jobId, key, name, icon?, roleId, roleName, roleLevel, clockedOn?, permissions?`.
- `GetClockedOnEmployees(jobKey)` rows: `{ charId, source }` (doc example).
- **WhipGroundItem**: `id, item, amount, metadata?, x, y, z, heading?, createdAt, createdBy? (charId)`.
- **WhipContainerDef**: `containerId, name, type? ('stash'), slots, maxWeight, ownerCharId?, locked, x, y, z, heading?, prop?, allowedItems? (list of keys; a keyed table's keys count; nil = anything), createdAt, accessCharId? (only this character), key? (EnsureContainer/UpdateContainer key), declared? ({ by, decl }), requirements?`.
- **WhipContainerRequirements** (ANY ONE lets a player in; checked at open and every move): `jobs?` (or `job`; string or list), `onDuty?` (with jobs: on duty there; without: on duty anywhere), `charIds?` (or `charId`; empty list = nobody), `items?` (or `item`: key, `{ key, count }` or list; a required item can never be put into the container it opens), `ace?`, `property?` (propertyId or key: owner and keyholders). `lockpick` is a door's and is refused.
- **WhipGarageDef**: `garageId, key, name, x, y, z, heading, spawnX, spawnY, spawnZ, spawnHeading, blipSprite?, blipColor?`.
- **WhipShopDef**: `shopId, key? (EnsureShop), name, mode ('infinite' sells catalog forever | 'stocked' sells its shelf container | 'npc' shopkeeper), npcModel?, prop?, x, y, z, heading, containerId? (stocked), catalog? (item key -> whole-dollar price), settings?, blipSprite?, blipColor (default 2), jobId?, createdAt?, createdBy?`.

## Data structures: SecureEvent schema and params

- **WhipSecureSchema**: `rateLimit?` (ms between calls per source; omitted = 100 ms with burst 10; `false` = unlimited), `burst?` (default 1 when rateLimit given), `ace?`, `requirePlayer?` (true), `whileDead?` (false: dead refused unless this or `ace`), `near?`, `ownerOf?` (name of an `'id'` param holding a netId: caller's game must be network owner), `onReject?` (SecureEvent only: `fn(source, reason, rawArgs)`, rawArgs unvalidated), `sheet?` (`'full'` | `'light'`), `params?`.
- **WhipSecureNear**: `at` (function returning x,y,z / vector3 / `{x,y,z}`; a fixed vector3/table; or `'vehicle'` = the schema's `'vehicle'` param, seated in it counts; NO position REFUSES), `range?` (5.0 m, or function), `message?` (`'Too far away'`; false = silent), `allowUnknown?`.
- **WhipSecureParam** = `{ name, type, ...options }`:

| type | Form | Behaviour |
|---|---|---|
| `int` | `{name,'int',min,max,default}` | Quantity: out of range CLAMPED |
| `number` | `{name,'number',min,max,default}` | Same, not floored |
| `id` | `{name,'id',min?,max?}` | Address: out of range / not whole REJECTED, never clamped |
| `string` | `{name,'string',maxLen,default}` | |
| `key` | `{name,'key',maxLen}` | Letters, digits, `_`, `-` only |
| `enum` | `{name,'enum',{allowed...},default}` | |
| `bool` | `{name,'bool',default}` | true/false, 1/0, "true"/"false" |
| `slot` | `{name,'slot',{item=key|{keys}, allowEmpty=true}?}` | Slot in the CALLER'S pockets (number or `{sub, slot}`); refused if empty/wrong item. Handler gets `WhipSlotParam` |
| `list` | `{name,'list',entry,max?}` | Every entry checked against `entry` (def or list of defs); max default 50; `'addr'` entry refused |
| `addr` | `{name,'addr',{slotOptional=true}?}` | Store address, resolved and authorised; handler gets `WhipSlotParam` |
| `vehicle` | `{name,'vehicle',{session=true}?}` | Vehicle id the caller OWNS; `session=true` also street cars; `anyOwner=true` any owner's car (`server/secure.lua:207`). Handler gets `WhipVehicleContext` |
| `player` | `{name,'player',{range=3, notSelf=true}?}` | Another player: loaded, not in creator, same bucket, in range. Handler gets their light sheet |
| `record` | `{name,'record',{ {field,type,...}, ... }}` | One table of named fields; handler gets only those |
| `any` | `{name,'any'}` | Unchecked |

- **WhipSlotParam**: `addr` (WhipStoreAddr), `item?`, `amount?`, `metadata?` (a COPY; use `SetItemMetadata`).

## Data structures: UI, camera, progress, timed use

- **WhipSkillDifficulty**: `'easy'|'medium'|'hard'|string` (names in `Config.SkillCheckDifficulty`).
- **WhipSkillLevel**: `pieces, parts, widest, narrowest, msPerPart, holdMs?, mouseSpeed?` (defaults `Config.SkillCheckHoldMs` / `MouseSpeed`).
- **WhipInputField**: `label, type ('text' default, 'number', 'textarea', 'select', 'checkbox', 'password', 'email', 'tel', 'url', 'date', 'time', 'color', 'range'), placeholder?, default?, required?, min?, max?, options? ({ label, value })`.
- **WhipCameraOptions**: `pos?` (gameplay cam), `rot?` (0,0,0), `fov?` (60), `filter?` (`'none'`), `canLook?` (false), `canMove?` (false), `exitKey?` (true, Escape ends), `transitionIn?`, `transitionOut?` (ms), `async?`.
- **WhipCameraWaypoint**: `pos, rot, fov?`.
- **WhipProgressAnim**: `dict?, clip?, flag?` (49, upper body), `scenario?`.
- **WhipProgressProp**: `model, bone?` (18905 right hand), `offset?`, `rot?`.
- **WhipProgressOptions**: `label?`, `icon?` (glyph name; default hourglass), `item?` (key or slot data: picture in the disc), `duration?` (client default 3000; REQUIRED for server `Progress`), `canCancel?` (false for Progress; true in a timed use), `anim?`, `prop?`, `disable?` (`{ move?: boolean|'walk', combat?, car? }`; default move and combat off, driving allowed), `cancelOnDeath?` (true), `cancelOnExit?` (false), `notWhile?` (`'swimming'|'underwater'|'falling'` list).
- **WhipTimedUse** (`RegisterUseHandler(item, def)`; extends progress options): `duration` (REQUIRED), `consume?` (true), `reason?` (`'used'`), `canUse?(source, player, slotData, addr) -> bool, why?`, `onComplete?(source, player, item, addr) -> bool?, why?`. Flow: canUse -> server-timed bar -> same item still at addr -> taken -> onComplete. `onComplete` returning `false, 'why'`, bare `false`, or erroring gives the item back (bare false = silent, no cooldown; unlike the function form where bare false keeps the item used).
- **WhipExternalPanelConfig**: `id, label? ('Panel'), slots (1-50), items?, resource?`.
- **WhipExternalPanelItemConfig**: `slots, label, storageKey` (metadata key holding nested inventory), `allowedItems?` (per-item `maxPerSlot` not enforced).

## Data structures: zones

- **WhipZoneRules**: `noWeapons?`, `noPvP?` (invincible inside), `noMelee?`, `disableFiring?`, `speedLimit?` (km/h), `noVehicles?`, `heal?`, `healRate?` (HP per tick, default 2, every 300 ms), `noWantedLevel?`, `noCollision?` (ped-ped), `noFallDamage?` (collision-proof: crashes/run-overs too), `jobWhitelist?` (keys), `aceWhitelist?`, `charWhitelist?` (charIds), `ejectUnauthorized?`, `enterNotify?` / `exitNotify?` (string, or false to disable).
- **WhipZoneBoxData**: `type='box', id?, pos, size (vector3 W/L/H), heading? (0), onEnter?, onExit?, inside? (every tick), condition?, priority? (0; higher fires first), group?, label?, debug?, trackVehicles?, rules?, onVehicleEnter?(entity, plate, zone), onVehicleExit?`.
- **WhipZoneSphereData**: same with `type='sphere', pos, radius`.
- **WhipZonePolyData**: same with `type='poly', points (vector2[]), minZ?, maxZ?`.

## Data structures: store addresses and panels

- **WhipStoreAddr** (THE slot handle; GetItemAt, SetItemMetadata, StoreGive, StoreTake, StoreMove, LogActivity take it; use handlers, context actions, FindItem, FindItemByUid, GetOpenStores give it): `kind, id?, sub?, slot?, owner? (panel: player whose session), label? (filled on the way out, ignored in)`.

| kind | id | sub |
|---|---|---|
| `player` | server id | `'player'` (default) / `'accessory'` |
| `container` | containerId (loaded on demand) | — |
| `vehicle` | vehicleId or a ref `{ plate = 'X' }` | `'trunk'`, `'glovebox'`, `'key'` |
| `panel` | panel id (`owner` optional) | — |
| your kind | passed to its `resolve({ id, sub })` | |
| `shop`, `basket` | CLIENT ONLY; no server address, `StoreMove` refuses | |

Slot is omitted where a call chooses (StoreGive, StoreRead, StoreMove destination). A `{ container, slot }` table is not an address.
- **WhipStoreContents** (`StoreRead`, a copy): `kind, id?, sub?, label, slots, maxWeight, weight, items` (by slot).
- **WhipPanelHookCtx** (`onValidate(ctx)` / `onChange(ctx)`): `source, panel, host?` (RegisterPanelItem: `{ source, container, slot, addr, item, amount, metadata }`), `direction` (`'in'|'out'|'within'`, from the panel's view), `slot, otherSlot?, other?` (address; nil when destroyed), `item, amount, metadata?, swap?` (returning half of a swap), `replacing?` (forward half: `{ item, amount, metadata }`), `destroyed?`, `items?` (onChange: panel contents copy).

## Examples

Register secure events, callbacks, actions and items inside `Whip.register` (anything registered at file top vanishes when whip_core restarts). `AddEventHandler` needs neither. Items like `repair_kit` aren't shipped: define with `RegisterItem` or `Config.Items` first.

### Listen safely (server)
```lua
AddEventHandler('whip_core:item:used', function(e) ---@param e WhipEvtItemUsed
    if GetInvokingResource() ~= 'whip_core' then return end   -- paying/acting? check the sender
    if e.item ~= 'lottery_ticket' then return end
    exports.whip_core:LogActivity(e.source, 'ticket_scratched', { slotData = e.addr })
end)
AddEventHandler('whip_core:job:clockedOn', function(e)          -- duty for late starters: Player(src).state.whipJob
    print(('%s on duty at %s'):format(e.charId, e.key))
end)
```

### Mechanic: server checks and takes the kit, client repairs
Client `AddAction({ id='repair', at={ vehiclePart='hood' }, label='Repair Engine', require={ item='repair_kit' }, canInteract=function(ctx) return GetVehicleEngineHealth(ctx.entity) < 900.0 end, onSelect=function(ctx) TriggerServerEvent('mechanic:repair', VehToNet(ctx.entity)) end })`. Server:
```lua
Whip.register(function()
  Whip.core:SecureEvent('mechanic:repair', {
    rateLimit = 2000,
    params = { {'netId', 'id'} },                         -- refused if bad, never clamped
    near = { at = function(src, player, netId)
               local veh = NetworkGetEntityFromNetworkId(netId)
               if DoesEntityExist(veh) then return GetEntityCoords(veh) end
             end, range = 6.0 },
  }, function(source, player, netId)
    if not exports.whip_core:RemoveItem(source, 'repair_kit', 1, nil, { reason = 'repair' }) then
      return false, 'No repair kit!'                      -- shown to the player, logged as refused
    end
    TriggerClientEvent('mechanic:client:repair', source, netId)  -- client: TakeVehicleControl({ entity = veh }) then SetVehicleEngineHealth
  end)
end)
```

### Refund a failed sale
```lua
local receipt, err = exports.whip_core:ChargePlayer(src, price, { method = 'cash', reason = 'Car sale' })
if not receipt then return false, err end
local ok, why = exports.whip_core:TransferVehicle(vehicleId, src)   -- gives a key by default
if not ok then exports.whip_core:RefundPlayer(receipt) return false, why end
```
New car: `CreateOwnedVehicle(source, data, { giveKey = true, spawnAt = vector4(...) })` undoes itself on failure; only the payment is yours to undo.

### Fuel is a vehicle stat (needs whip_fuel)
```lua
Whip.core:SecureEvent('gasstation:refuel', {
  rateLimit = 2000, params = { {'vehicle', 'vehicle'} }, near = { at = 'vehicle', range = 5.0 },
}, function(source, player, v)                         -- v = WhipVehicleContext, caller owns it
  local fuel = exports.whip_core:GetVehicleStat(v.vehicleId, 'fuel')
  local cost = math.ceil((100 - fuel) * 5)
  if cost < 1 then return false, 'The tank is already full' end
  local receipt, err = exports.whip_core:ChargePlayer(source, cost, { method = 'cash', reason = 'Fuel' })
  if not receipt then return false, err end
  exports.whip_core:SetVehicleStat(v.vehicleId, 'fuel', 100.0, 'gasstation:refuel')  -- last arg = change source
end)
```
No `SetVehicleFuel` exists.

### Impound any car, and lockpick alerts
```lua
Whip.core:SecureEvent('impound:seize', {
  rateLimit = 2000,
  params = { {'vehicle', 'vehicle', { anyOwner = true, session = true }} },   -- any car, street cars too
  near = { at = 'vehicle', range = 8.0 },                                     -- where the car is now
}, function(source, player, v)
  if not exports.whip_core:IsPlayerClockedOn(source, 'police') then return false, 'Only on-duty police can impound' end
  local owner = v.owner.charId and exports.whip_core:GetPlayer({ charId = v.owner.charId })
  if owner then exports.whip_core:RemoveVehicleKey(owner.source, v.vehicleId) end
  exports.whip_core:SetVehicleLocked(v.vehicleId, true)
end)
AddEventHandler('whip_core:vehicle:lockpicked', function(e)        -- dispatch only: no check needed
  local c = GetEntityCoords(GetPlayerPed(e.source))
  TriggerClientEvent('dispatch:alert', -1, { title = 'Vehicle Break-In', plate = e.plate, x = c.x, y = c.y, z = c.z })
end)
```

### Plate check: `require` only decides what is offered
Client action with `require = { job = 'police', onDuty = true }`; server SecureEvent `params = { {'plate','string',8} }` re-checks `IsPlayerClockedOn(source,'police')`, then `GetVehicle({ plate = plate })`; `v.session` true = street car or rental, no record.

### Shops: react to purchases and visits
```lua
AddEventHandler('whip_core:shop:purchased', function(e)
  local shop = exports.whip_core:GetShop({ key = 'dynamic_store' })
  if not shop or e.shopId ~= shop.shopId then return end
  for _, line in ipairs(e.items) do sold[line.itemKey] = (sold[line.itemKey] or 0) + line.amount end
  exports.whip_core:UpdateShop(shop.shopId, { catalog = recomputePrices(sold) })
end)
AddEventHandler('whip_core:shop:opened', function(e)
  local w = GetSelectedPedWeapon(GetPlayerPed(e.source))
  if w == 0 or w == `WEAPON_UNARMED` then return end
  local shop = exports.whip_core:GetShop(e.shopId); if not shop then return end
  for _, cop in ipairs(exports.whip_core:GetClockedOnEmployees('police') or {}) do   -- rows { charId, source }
    exports.whip_core:NotifyPlayer(cop.source, 'Armed customer at ' .. shop.name, 'warning')
  end
end)
```

### Another WHIP resource, and `Whip.core` after a wait
With `dependency 'whip_gunny'`: charge, `exports.whip_gunny:GiveWeapon(source, 'gunny_pistol', nil, 'Pistol purchase')`; on failure `Whip.core:RefundPlayer(receipt)`; then `exports.whip_gunny:GiveMagazine(source, 'gunny_mag_pistol', 12, reason)` and `Whip.core:AddItem(source, 'ammo_9mm', 24, nil, reason)`. Once something has waited (GiveWeapon goes through AddItem), call whip_core via `Whip.core`, which returns even if whip_core stops meanwhile.

## Gotchas

1. Every server event is a local `TriggerEvent`: any server resource can forge it. Check `GetInvokingResource() ~= 'whip_core'` before paying, giving, punishing or deleting; better, re-read truth (`GetNpc`, `IsDoorLocked`, `HasPermission`, `GetPlayerFlag`, `IsCharacterDeleted`, Stores).
2. Never `RegisterNetEvent` a `whip_core:client:*` / `whip_core:server:*` name to hook WHIP: arguments change and several fire at the start (e.g. `client:playerLoaded` before the player is ready). Use `whip_core:player:loaded`.
3. `item:added/removed` don't fire for login, stashing into containers, own-slot moves, or bag contents; `inventory:changed` carries only `{ source }`.
4. `bank:balanceChanged` withdraw payloads have no `ownerCharId/accountType/label`; transfers have no `accountId/newBalance`. A lore payment (`SystemPayFrom`) fires a deposit and a transfer back to back.
5. `vehicle:entered` (server) fires on seat changes too; use `previousSeat == nil` for "got in". Changing car without exiting fires `:exited` for the old car first.
6. Client `vehicle:entered/exited` fire for ANY vehicle; `vehicleId` may be nil. The server's versions are only for framework vehicles and only once it agrees.
7. `vehicle:released` is the cleanup point for per-vehicle state of session/temp cars; `:despawned` means the netId is dead (next spawn gets a new one).
8. `player:died` `reported` is the victim client's text: display only. Use `killer`.
9. Client `player:died` with `respawnRefused = true` repeats the same death after a `revived` was already sent.
10. Director run events never fire for a builder's Test, except `run:thingMade` (check `run.test`). After `run:ended` the run can't be looked up: check the invoker.
11. `whipJob` is `false` (not nil) while loaded and off duty, absent when not loaded. `whipDamageMod`, `whipMeleeMod`, `whipMood` are ABSENT at default (treat nil as 1.0 / none).
12. Never write WHIP's player bag keys yourself: the Sentinel reverts and logs it as tampering. Use your own keys via `RegisterSentinelKey` + `SetSentinelPlayerKey` / `SetSentinelEntityKey`.
13. `whipStats` holds stored values only: an absent stat reads nil at its default (a full tank). Live stats are in `whipLive`. Always read through `GetVehicleStat`.
14. `GetInventory` tables are sparse by slot number; iterate with `pairs`, not `ipairs`.
15. `WhipSlotParam.metadata` and `WhipFoundItem.metadata` are copies; changing them does nothing. A uid given to a copy belongs to nothing.
16. A bare number in a vehicle ref is a vehicleId; pass entity handles as `{ entity = veh }`.
17. `decay = 0` does not disable stat decay; omit it.

## Docs vs code

1. Events in code/stubs but absent from the Server/Client Events docs: `whip_core:character:renamed` (S, `server/character.lua:357`), `whip_core:player:renamed` (C, `client/player.lua:248`), `whip_core:death:screenChanged` (C, `client/death.lua`), `whip_core:voice:rangeChanged` (C, `client/stats.lua:184`), `whip_core:voice:systemChanged` (C, `client/voice_system.lua:12`), `whip_core:hotbar:slotUsed` (C, `client/inventory.lua:2836`), `whip_core:lore:changed` (S, `server/director/lore.lua:274`), `whip_core:run:thingMade` (S, `server/director/satellite_api.lua:249`), `whip_core:director:builderCopy` (C), `whip_core:vehicle:copied` (C, `client/take_copies.lua:112`).
2. `whip_core:ui:cleanScreen` also carries `world` (`client/clean_screen.lua:35`); docs list only `on`.
3. `whip_core:heldProps:lost`: WHIP tags also include `'camera'` (`types/events.lua:401`); docs list emote/bar/give/take.
4. `whip_core:npc:spawned` also carries `lore` and `look` (`server/npcs.lua:885-886`), beyond the stub's `{ npcId, tag, owner, netId, model, coords }`.
5. `whip_core:player:logout` / `:loaded` can carry `phantom = true` and `why = 'phantom'` for whip_test load-test players (`server/testseams.lua:832,878`); docs give `why` as only `'logout'|'disconnect'`.
6. `WhipVehicleContext.state` is typed `'out' or 'garaged'` (`types/classes.lua:240`); the Data Structures doc shows `'out' | 'garaged' | 'impounded'`. `storageLoaded` (`classes.lua:253`) is not in the doc snapshot.
7. Bank withdraw payload lacks `ownerCharId/accountType/label` (`server/bank.lua:866-868`); docs say only deposits have them (consistent) but don't say withdraw omits them.
8. `shared/events.lua:9-11` header example shows `item:added { source, item, count, reason, by }` and `player:died { reconnected }`; the real payloads also carry `amount` (`server/inventory.lua:1181`), and the server `player:died` is `{ source, charId, killer, reported }`.
9. The `WhipSecureParam` stub (`types/classes.lua:580`) documents only `session=true` for the `'vehicle'` param; the code also takes `anyOwner = true` (a car whoever owns it, `server/secure.lua:185,207`), as the docs' impound example uses.
10. `whip_core:door:lockChanged` `cause` may also be the caller's own value (`types/events.lua:412`), beyond the five documented causes; default when none is `'code'` (`server/doors.lua:775`).
