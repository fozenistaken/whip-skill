# Vehicles, keys, stats, data and garages

Everything about WHIP cars: references, owned/street/temp cars and their lifetimes, keys and ignition, locks, seats, boot/glovebox/ignition stores, damage persistence, appearance, vehicle data, handling/power/dial, vehicle stats (consume/live/gauges), the client vehicle API and garages. Built from doc anchors `guide-vehicles`, `vehicles`, `client-vehicles`, `vehicle-data-api`, `vehicle-stats`, `guide-garages`, `garages-exports`, verified against `whip_core/server/vehicles.lua` (read fully), `vehicle_claim.lua`, `vehicle_damage.lua`, `vehicle_data.lua`, `vehicle_stats.lua`, `vehicle_catalog.lua`, `vehicle_manager.lua`, `garages.lua`, `garage_spots.lua`, `events_vehicles.lua`, `seats.lua`, `items/vehicle_key.lua`, `items/hacked_vehicle_key.lua`, `stores.lua` (vehicle kind), `secure.lua` ('vehicle' param), `actors.lua`, `prices.lua`, client `vehicles.lua`, `vehicle_data.lua`, `vehicle_handling.lua`, `vehicle_properties.lua`, `vehicle_stats.lua`, `vehicle_points.lua`, `vehicle_hud.lua`, `vehicle_damage.lua`, `garage_helper.lua`, `shared/garage_bay.lua`, `config.lua`, `types/*.lua`.

## Contents
- Vehicle references (how to name a car)
- Kinds of car and their lifetimes
- States, persistence, boot-time restore
- Keys, the ignition and locks (concepts)
- Server: reading a car
- Server: keys and locks exports
- Server: engine holds
- Server: making cars
- Server: in and out of the world
- Server: ownership and deletion
- Appearance (server) and properties (client)
- Catalog, pictures, prices
- Storage: boot, glovebox, ignition as stores
- Seats and occupancy
- Damage a car keeps
- Vehicle data
- Handling, power and the rev dial (client)
- Vehicle stats: registration and server API
- Vehicle stats: client API, consume and live, gauges
- Client vehicles API: finding cars, control, points, part actions
- Garages: concepts, bays, private garages, the wizard
- Garages API
- Events
- SecureEvent 'vehicle' param
- Config keys
- Internal net events and limits (reference)
- Gotchas
- Docs vs code

---

## Vehicle references (how to name a car)

Every vehicle, stat and data export (server and client) takes the car first, in one of these forms:

```lua
vehicleId          -- a bare number is ALWAYS a vehicleId (strings of digits too, server)
{ id = vehicleId } -- also { vehicleId = n }: a GetVehicle snapshot is itself a reference
{ entity = veh }   -- an entity handle (server: a server entity)
{ plate = 'ABC123' }  -- spaces ignored, case-insensitive
{ netId = netId }
```

- Never pass a bare entity handle: ids and handles are both integers in overlapping ranges. Only `GetVehicleId(entity)` and `ResolveVehicle(entity)` (client) take a bare handle (they also take `{ entity = }`).
- Precedence when a table names several (server `Vehicles.idFromRef`, `vehicles.lua:1483`): `id`/`vehicleId` first, then `plate`, then `entity`/`netId`.
- Server failure strings: `'Invalid vehicleId'` (bad number), `'Vehicle not found'` (reference names no car WHIP knows), `'Invalid vehicle reference'` (table names nothing / wrong type). Read-style exports (`GetVehicle`, `GetVehicleStat`, `GetVehiclePosition`) return `nil` instead.
- A bare unknown number passes `idFromRef` (it is just an id), so the export's own check produces the error (e.g. `'Vehicle not found'`, or `'no such vehicle'` for data).
- `{ plate = }` on the server picks the lowest vehicleId wearing the plate (owned cars, ids from 1, come before street cars, ids from 1,000,000,000).
- On the client a reference only resolves for a car streamed in near the player; otherwise reads return `nil` / `{}` / `false`. Client `{ plate = }` scans `GetGamePool('CVehicle')`.
- Exceptions that do NOT take references: `HoldVehicleEngine`, `ReleaseVehicleEngine`, `GetVehicleEngineHold` (numeric vehicleId only, `tonumber`), and a SecureEvent `'vehicle'` param (numeric id only).

## Kinds of car and their lifetimes

| Kind | Made by | Saved? | vehicleId | `GetVehicle` flags | Ends when |
|---|---|---|---|---|---|
| Owned | `CreateOwnedVehicle`, `ClaimVehicle`, admin Vehicle Manager | Yes, `vehicles` row | DB auto-increment (1, 2, 3...) | `session=false, temp=false` | `DeleteVehicle` only |
| Street ("session") | GTA traffic, registered on first use | No (memory only) | from 1,000,000,001 up | `session=true, temp=false` | released (see below) |
| Temp | `SpawnTempVehicle` | No | session id range | `session=true, temp=true`, `secure` if asked | released (see below) |

- `owner.charId` is `0` for street and temp cars.
- A **street car** is registered when a player takes its driver's seat (client reports it), lockpicks it, opens its boot, refuels it at a pump, a client calls `ResolveVehicle`, or a server calls `AdoptVehicle`. It then has a vehicleId, boot, glovebox, ignition, lock and stats/data (memory only). If its engine was running when the driver took it, one `vehicle_key` is minted into its ignition (once per car, `keyMinted`). Its lock is read from the world at adoption.
- A street car is pinned (KeepEntity, and asked to `SetEntityAsMissionEntity` on its network owner) while WHIP holds it.
- Per-player cap: 20 street cars brought into tracking at once (`SESSION_ADOPT_CAP`, `events_vehicles.lua:578`); `ResolveVehicle` past it: `'You already hold 20 street cars'`; `AdoptVehicle({ entity, player = src })`: `'Too many street cars brought in already'`.
- Session-car sweep (every 60 s, `vehicles.lua:3589`): a session car whose entity is gone is forgotten (`reason 'gone'`); one with no player within 300 m and nobody with its trunk/glovebox open for 10 minutes is released (`'idle'`). Temp cars with `idleDespawn = false` skip the idle rule.
- Releasing a **street** car hands it back to GTA where it stands (strips WHIP statebags, orphan mode 0, unpins); a **temp** car is deleted. Either way the record goes, boot/glovebox/ignition contents are logged as lost, the vehicleId means nothing afterwards, and `whip_core:vehicle:released` fires.
- A temp car takes back the key it gave `forSource` (from that character's pockets, if online) when it goes; a key passed on or stashed stays as a dead item.
- Session ids restart every clean start; keys persist, so a session car's key must also match the car's plate (`Vehicles.keyFits`).
- A resource's local, non-networked car is ignored: prompts work on that one game and it has no boot.

## States, persistence, boot-time restore

- `state` column: `'out'` (in the world, position tracked), `'garaged'` (no entity, no position), `'impounded'` (no entity; only settable by the admin Vehicle Manager; `RetrieveVehicle` refuses it: `'Vehicle is not garaged'`). Use an impound *garage* key rather than this state.
- Owned `out` cars stay in the world when the player leaves/drives off (orphan mode 2 / KeepEntity) and come back where they stood after a restart. At boot: rows with `out` but no x/y/z become `garaged`; garaged rows lose coordinates; NULL `garage` is set to the default garage.
- Boot reconcile (`Vehicles.reconcileWorld`): entities still stamped with an id from before the restart are re-adopted if within 75 m of the recorded position and the right model; extras are deleted (or handed back to GTA if occupied); old street cars are handed back to GTA.
- A locked `out` car whose own key sits in its ignition is unlocked at boot (otherwise the owner is locked out). Every other car keeps its saved lock.
- Positions: write-behind. Every `Config.VehiclePositionSaveInterval` (30 s, min 5 s) cars that moved more than `Config.VehiclePositionEpsilon` (2.0 m) are marked; the car's save unit `vehrow:<id>` writes stats and position every `Config.VehicleStatsSaveInterval` (15 s, min 1 s). Garaging, despawning and stopping the resource save position themselves.
- Default garage = the non-private garage with the lowest `garageId` (`Vehicles.getDefaultGarage`), so the seeded config garage, not a later impound, catches cars.
- DB tables: `vehicles` (incl. `vehStats` JSON, `vehData` JSON, `properties` JSON, `locked`, `vehType`, `keyToken`, `parkedReversed`, per-car storage sizes; plate UNIQUE, `VARCHAR(10)`), `vehicle_inventory` (`storageType` ENUM trunk/glovebox/key, CASCADE delete), `vehicle_meta` (per model), `vehicle_class_meta` (per GTA class), `vehicle_catalog`, `garages`, `garage_spots`.
- Entity statebags WHIP writes (Sentinel-guarded, client-writable but reverted): `whipVehicleId`, `whipVehicleSession`, `whipStats`, `whipLive`, `whipAppearance`, `whipVehData`, `whipVehDoors`, `whipEngineHold`. Read through the exports, never the bags.

## Keys, the ignition and locks (concepts)

- A key is the item `vehicle_key`: weight 0.1, not stackable, `usable = false`, metadata `{ vehicleId, plate, model, token? }` (`token` only for a car whose locks were changed, or a secure temp car). Picture per maker (`html/img/items/keys/{make}.webp`).
- Fit rule (`Vehicles.keyFits`, `vehicles.lua:3799`): `metadata.vehicleId` must equal the id; if the car has a `keyToken`, `metadata.token` must equal it; for a session car the key's plate must match the current plate (or a plate it wore earlier this session, after `SetVehiclePlate`).
- Ignition keys = `vehicle_key`, `hacked_vehicle_key`, plus anything a resource registers with `RegisterIgnitionKey(itemName)` (server; follows the vehicle_key fit rule; unregistered when the resource stops). `HasVehicleKey`/`CountVehicleKeys`/`RemoveVehicleKey` count every ignition-key item that fits.
- The ignition is a one-slot store (`sub = 'key'`, `Config.VehicleKeySlots` 1, `Config.VehicleKeyMaxWeight` 1.0). Only a fitting key goes in; a key whose locks were changed is refused with `'This key is deactivated.'`; a second key cannot be swapped in while one is there.
- Engine: driver scrolls mouse wheel up to start, down to stop. Start needs a fitting key in the ignition (`'No key in ignition!'` otherwise) and no engine hold; a bicycle needs no key. Stopping is always allowed. The engine is the stat `engine` (0/1, `persist = false`); a car that leaves the world comes back off.
- Accessory strip: a fitting `vehicle_key` in the player's accessory (Key) slots goes into an empty ignition automatically when they take the driver's seat, and comes back to the same slot (else first free strip slot, else pockets, else stays in the car) when they leave that seat.
- Leaving the game in the driver's seat of a locked car takes its ignition key out with them; if their pockets are full the car is unlocked instead.
- `hacked_vehicle_key`: an unhacked one (no `vehicleId`) goes into any ignition but does not start it; the driver hacks it (server-run `'hard'` skill check, 8 s rate limit); on success it is linked (`vehicleId, plate, model, status = 'hacked', token`) and then fits that car. Secure temp cars: `'This ignition can\'t be hacked'`.
- Locking: L, or Lock/Unlock on a door prompt. From the driver's seat the key may be in the ignition or pockets; on foot it must be in pockets within `Config.VehicleLockRange` (8.0 m). Nearby players see 2 flashes for lock, 1 for unlock.
- `Config.UnlockOnExit = true` (default): any player getting out of a WHIP car unlocks it; leaving the game in it does not.
- Street cars stay locked (client NPC lock rule within `Config.NpcVehicleLockRange`, 10 m; `0` turns it off) until lockpicked (`lockpick` item, server-run `'medium'` check, 10 m, 5 s rate limit), then stay unlocked. Secure temp cars: `'This lock can\'t be picked'`.
- A locked boot cannot be opened and closes on anyone viewing it at the moment of locking.
- No client event can cut a key: keys come only from `CreateOwnedVehicle{giveKey}`, `GiveVehicleKey`, `TransferVehicle`, `ClaimVehicle`, `SpawnTempVehicle`, a running street car, and the admin Vehicle Manager.

## Server: reading a car

### GetVehicle(vehicle, opts?) — SERVER
- `vehicle`: id or reference. `opts.occupants = true` adds players sitting in it (scans every player; ambient peds never reach the server, so `occupantsPlayersOnly = true` is set).
- Returns a **copy** or `nil` (unknown). Fields: `vehicleId, plate, model, displayName` (catalog; nil if unknown model), `class` (GTA class number from catalog; nil), `vehType` (`'automobile'|'bike'|'boat'|'heli'|'plane'|...`), `session`, `temp`, `secure`, `owner = { charId, name, online }` (`name` only while online), `state, garage, coords` (live if spawned, else last saved), `heading, spawned, entity, netId` (nil when not out), `locked, stats` (all registered stats, defaults filled), `data` (always a table), `properties` (stored look copy or nil), `occupants` (`{ serverId, charId, name, seat }`, only when asked), `occupantsPlayersOnly`, `storage` (`{ trunk = { slots, maxWeight, used }, glovebox = {...} }` only if storage already loaded), `storageLoaded`.
- Never includes `keyInIgnition` (asking would load the inventory).

```lua
local v = exports.whip_core:GetVehicle({ plate = 'ABC123' })
if not v then return false, 'No such vehicle' end
print(v.plate, v.owner.charId, v.state, v.locked, v.stats.fuel)
```

### GetVehiclesOf(who) — SERVER
`who`: server id or `{ charId = n }` (online or not). Returns array of `GetVehicle` snapshots, or `{}, why` when `who` names nobody (`'No player with that server id is online (for a character, pass { charId = n })'`, `'A character is { charId = n }'`). A charId that names no character returns `{}` with no why.

### IsPlayerDrivingVehicle(source, vehicle) / IsPlayerInVehicle(source, vehicle) — SERVER
Three natives, no snapshot: use on hot paths. Driving = seat -1. `false` for a car not in the world or bad input.

### GetVehicleDriver(vehicle) — SERVER
`vehicle`: id, `{ plate }`, or `{ netId }`/`{ entity }` (any networked car, WHIP's or not). Returns `source, 'seat'` (a player at the wheel), `source, 'take'` (the game playing a Director recorded drive on it; it reclaims the car every ~2 s), or `nil` (parked, NPC driver, no car). Ask before moving a car to another game (tow, rope). Source: `actors.lua:369`.

### GetPlayerVehicle(source, opts?) — SERVER
Which WHIP car the player sits in, from the server's view. `opts.driver = true`: driver seat only. Returns `vehicleId` or `false, why`: `'Invalid source'`, `'Player not found'`, `'You need to be in a vehicle'`, `'You need to be driving'`, `'That vehicle is not one whip looks after'`.

### GetPlayerSeat(source) — SERVER
Any vehicle, street cars included. Returns `{ seat, driver, vehicleId, netId }` (`vehicleId` nil for an untracked car; seat -1 driver, 0 front passenger, 1+ rear; probed -1..15) or `false, why`: `'Invalid source'`, `'Player not found'`, `'Not in a vehicle'`, `'Not in a seat yet'`.

### GetVehiclePosition(vehicle) — SERVER
`x, y, z` of the live entity, or `nil` when not in the world (garaged, despawned, lost). For last-seen use `GetVehicle(id).coords`.

### IsVehicleWrecked(vehicle) — SERVER
`true` when blown up (health <= 0 while a game runs it) or sunk (the owning client reports it: >= 85% submerged for 5 consecutive 1 s checks). `false` for a car not out. Per entity: a fresh spawn starts sound.

## Server: keys and locks exports

### SetVehicleLocked(vehicle, locked) — SERVER, WAITS
Saves, applies `SetVehicleDoorsLocked` (2 locked / 1 unlocked), fires `whip_core:vehicle:lockChanged` only on an actual change (no `source` when code does it). Locking closes anyone's open boot screen. Returns `true` or `false, err` (`'Vehicle not found'`, reference errors, DB failure). The lock survives restarts (see Docs vs code).

### GiveVehicleKey(who, vehicle, opts?) — SERVER, WAITS
- `who`: server id or `{ charId }` and must be **online** (`'They are not online: a key goes into their pockets, so give it when they are'`).
- `opts.spare = true`: cut another even if they already hold a fitting key.
- Key metadata is `{ vehicleId, plate, model, token }`; logged as gained; pockets flushed and keys synced.
- Returns `true` or `false, reason`: `'Already has a key for this vehicle'`, `'Failed to give key: <err or No room>'`, `'Vehicle #N not found'`, `'Player has no inventory'`, reference errors.

### RemoveVehicleKey(who, vehicle) — SERVER, WAITS
Removes **every** fitting ignition-key item from all the online player's containers. Returns `true` or `false, why`: `'They have no key for that vehicle'`, not online, reference errors.

### ChangeVehicleLocks(vehicle) — SERVER, WAITS
New `keyToken` saved on the row: every key cut before stops fitting wherever it is (pockets online or not, stashes, boots, ignition, ground); keys cut after fit; survives restart; a car running on an old ignition key stops; holders' key lists resync. Old keys remain as dead items. Street/temp car: `'Only a car someone owns'` (a temp car uses `secure = true` instead). Also `'Vehicle not found'`, `'Could not save the new locks'`.

```lua
local ok = exports.whip_core:ChangeVehicleLocks(vehicleId)
if ok then exports.whip_core:GiveVehicleKey(source, vehicleId) end
```

### CountVehicleKeys(vehicle) — SERVER, WAITS
Number of fitting keys anywhere: every living character's pockets (DB for offline), every stash, every car's boot/glovebox/ignition, the ground; stacks count each key. Not counted: keys inside another item (a bag), resource-owned stores, open panel slots, keys from before a lock change. Returns `number` or `false, why` (`'Vehicle not found'`, `'The database could not be reached — try again'`).

### HasVehicleKey(who, vehicle) — SERVER, WAITS
Pockets only (all player containers). Offline characters read from the DB (`'Their last save has not landed yet — try again in a moment'`, `'No such character'`, `'The database could not be reached — try again'`). Returns `bool` or `false, why`.

### GetPlayerVehicleKeys(who) — SERVER, WAITS
`{ [vehicleId] = plate }` for keys that still fit (plate may be `true` if the car record is gone), or `{}, why`.

### RegisterIgnitionKey(itemName) — SERVER
Adds an item the ignition accepts and key sweeps count. `true` or `false, err`. Dropped when the caller stops.

## Server: engine holds

### HoldVehicleEngine(vehicleId, key, reason) — SERVER
- Numeric `vehicleId` only. `key` default `'hold'` (yours; same key replaces the reason). `reason` shown to the driver, trimmed to 80 chars, default `'The engine will not start'`.
- While any hold exists: the engine won't start (client refuses, server backstop), a running one is set off; the car still rolls. The reason rides the `whipEngineHold` statebag so the next driver's game knows before starting.
- Ends on `ReleaseVehicleEngine`, your resource stopping, or the car's id going for good (`released`/`deleted`).
- Returns `true` or `false, 'no such vehicle'`.

### ReleaseVehicleEngine(vehicleId, key?) — SERVER
With key: that hold; without: all your holds on that car. Returns `true` or `false, why` (`'you hold no engine hold "x" on that car'`, `'you hold no engine hold on that car'`, `'vehicleId is a number'`).

### GetVehicleEngineHold(vehicleId) — SERVER
Any resource's hold reason, or `nil`.

whip_fuel uses `HoldVehicleEngine(id, 'empty', 'Out of fuel')`.

## Server: making cars

### CreateOwnedVehicle(source, data, opts?) — SERVER, WAITS
The only way a resource mints an owned car. Owner = the player's current character (never from `data`).

`data`:
| Key | Notes |
|---|---|
| `model` | required, max 60 chars (`'No model'`) |
| `plate?` | trimmed, upper-cased, max 8 (`'A plate is text'`, `'A plate is 8 characters at most'`, `'That plate is already taken'`); default generated `AA000AA` (letters exclude I/O) |
| `garage?` | must exist (`'No such garage: x'`); default the default garage |
| `stats?` | `{ [stat] = number }` starting values; names must match `^[%a_][%w_]*$`; absent ones read their default |
| `properties?` | stored look, sanitised (plate/model dropped) |
| `vehType?` | one of `automobile bike boat heli plane submarine trailer train`; else from catalog class (8/13 bike, 14 boat, 15 heli, 16 plane, else automobile); self-corrects on first spawn |
| `trunkSlots?, trunkMaxWeight?, gloveboxSlots?, gloveboxMaxWeight?` | per-car storage sizes |
| `state?` | `'garaged'` or `'out'` only; `'out'` without `opts.spawnAt`: `"state = 'out' needs opts.spawnAt: that is what puts the car in the world"`; `data.x/y/z` are never read |

`opts`: `giveKey?` (bool, default no key), `spawnAt?` (`vector4`, `vector3`, or `{ x, y, z, heading }`/`{ ..., w }`; makes it `out` there).

Order: model check (`'There is no vehicle called "x" in this game'`), spot check (`'Something is already parked in that spot'`, `'Someone is standing in that spot'`; the buyer may stand there), Isolate check (`'Leave Isolate world first: cars come out in the shared world'`), insert, spawn (re-checks the spot), key. If spawn or key fails the car is deleted (3 tries) and you get `false, 'could not spawn it: ...'` / `false, 'could not give the key: ...'`; if the delete keeps failing the car stays the buyer's, garaged, and the vehicleId is returned.

Returns `vehicleId` or `false, err, saved?`:
- `false, 'Player not loaded' | 'Expected a table' | ...` → nothing made; refund.
- `false, 'The vehicle was registered but could not be brought out yet', true` → saved (with the payment in the same transaction) but its id did not read back; it arrives in their garage (with key if `giveKey`) when it does. **Do not refund.**
- `false, 'Database insert failed'` → nothing saved.
Read the plate with `GetVehicle(id).plate`. Fires `whip_core:vehicle:created`.

```lua
local ok, why = exports.whip_core:CanBringOutVehicleFor(source)
if not ok then return false, why end
local receipt, err = exports.whip_core:ChargePlayer(source, 250000, { reason = 'Adder' })
if not receipt then return false, err end
local id, cerr, saved = exports.whip_core:CreateOwnedVehicle(source, { model = 'adder' },
    { giveKey = true, spawnAt = vector4(-56.7, -1097.2, 26.4, 160.0) })
if not id and not saved then exports.whip_core:RefundPlayer(receipt) end
```

### CanBringOutVehicleFor(source) — SERVER
`true` or `false, 'Leave Isolate world first: cars come out in the shared world'` (builder in the Director's Isolate world). Ask before charging.

### VehicleModelExists(model) — SERVER
`true`/`false`/`nil`. Players' games report `GetAllVehicleModels()` (add-ons included) at the character screen, once per account per server run; saved per platform + `sv_enforceGameBuild` in KVP; names unreported for 14 days dropped; ceiling 20,000 names. `nil` before any game reported, or when the list is full and the model isn't on it: nothing is refused then, so test `== false`. `CreateOwnedVehicle`, `SpawnTempVehicle`, `SpawnVehicle`, `RetrieveVehicle` and garage bays refuse a model that is `false`.

### SpawnTempVehicle(model, coords, opts?) — SERVER, WAITS
A rental / job van / test drive: no owner, no row, but id, stats, data, boot, glovebox, keys. Belongs to the calling resource.

| opt | Default | Meaning |
|---|---|---|
| `forSource` | none | must be a loaded player (`'forSource is not a loaded player'`); gets a key unless `giveKey = false`; may stand on the spot |
| `giveKey` | `true` with forSource | `giveKey = true` without forSource: `'giveKey needs forSource (who to give it to)'` |
| `despawnAfter` | none | seconds; removes it even while driven (`reason 'expired'`) |
| `locked` | `true` | `false` spawns open |
| `keyInIgnition` | false | a key in its ignition: anyone at the wheel can start it |
| `idleDespawn` | `true` | `false`: never removed by the 10-minute/300 m idle sweep |
| `tag` | none | one of your run tags; `ReleaseTag(tag)` removes it (`'released'`); spawning under an ended tag: `'<tag> has ended'`; bad tag refused by the registry tag rule |
| `secure` | false | no lockpick, no ignition hack; only keys cut with its token fit |
| `force` | false | spawn even if the spot is occupied (else `'Something is already parked in that spot'` / `'Someone is standing in that spot'`) |
| `plate` | generated | normalised (max 8); `'plate X is already on a vehicle'` if taken |
| `vehType` | catalog | same enum as CreateOwnedVehicle |
| `bucket` | 0 | routing bucket from birth (whole number 0..2^31-1); stub-only, not in docs |

`coords`: `vector4`, `vector3` (heading 0), or `{ x, y, z, heading }` (`'coords must be a vector4 or { x, y, z, heading }'`, `'coords needs x, y and z'`). Other failures: `'No model'`, missing model, `'Could not create the vehicle'`, `'Vehicle did not network'`, `'could not give the key: ...'` (car removed, `reason 'failed'`), `'the car went while its key was being given'`.
Returns `vehicleId` or `false, err`. Fires `whip_core:vehicle:spawned` with `session = true, temp = true`. Removed (and its given key taken back, `whip_core:vehicle:released`) when the owning resource stops (`'stopped'`), `despawnAfter` runs out, idle sweep (`'idle'`), `DespawnVehicle` (`'despawned'`), `DeleteVehicle` (`'deleted'`), `ReleaseTag`.

```lua
local id, err = exports.whip_core:SpawnTempVehicle('blista', vector4(x, y, z, h),
    { forSource = source, despawnAfter = 1800 })   -- warn the driver before it expires
```

### ClaimVehicle(vehicle, who, opts?) — SERVER, WAITS
Turns a session car (temp or street) into a new owned car: new id, new plate unless `opts.plate`; keeps model (resolved from the entity's hash in the catalog; a temp car's model name as fallback), look, every saved stat (fuel, damage, resources'), boot and glovebox contents (moved stack by stack, logged). The old session car goes (`released` with reason `'claimed'`), the new one is spawned where the old one stands now and the driver is put back at the wheel.

| opt | Default | Meaning |
|---|---|---|
| `plate` | new | max 8, unused (may equal the session car's own plate) |
| `here` | `true` | `false`: put away in its garage instead |
| `garage` | default garage | its garage |
| `key` | `true` | `false`: no key (key only if the person is online) |
| `reason` | `'claimed'` | activity log text (max 120) |
| `leave` | none | `function(metadata, item) -> true` leaves that stack in the old car (written off with it) |

Returns new `vehicleId` (plus a note when it waits in its garage, e.g. `'it is waiting in its garage (...)'`, or `'no key: ...'`) or `false, why`: `'No such car'`, `'That car is someone\'s already'`, `'That car is going'`, `'That car is being claimed already'`, `'That plate is already taken'`, `'That car is not one whip knows the model of (the vehicle catalog), so it cannot be kept'`, `'That car went while it was being claimed'`, `'What is in the car could not be read'`, `'the trunk would not take what was in it (...)'`. A failure undoes everything. Fires `whip_core:vehicle:claimed { vehicleId (new), from (old session id), ownerCharId }` (and `created`).

### SetVehiclePlate(vehicle, plate) — SERVER, WAITS
Any car. Owned: saved; session: until it goes. Old keys still fit (owned: by id; session: old plates remembered). Owner's car list resynced, logged. Returns `true` or `false, why`: `'No such car'`, `'A plate is text'`, `'A plate is 8 characters at most'`, `'A plate is 1 to 8 characters'`, `'That plate is already taken'`. Fires `whip_core:vehicle:plateChanged { vehicleId, from, to }`. The entity shows the plate centred in 8 chars (padding added for Enhanced).

### AdoptVehicle(ref) — SERVER, WAITS
Registers a car already in the world as a session vehicle; returns the id of a car WHIP already knows. Never creates a car; not a lookup (it searches and pins).
- `ref = { entity = veh }` or `{ netId = n }` (preferred): exactly that car. Optional `player = source`: counts against their 20-car cap.
- `ref = 'PLATE'` (max 10 chars after sanitising): first car wearing that plate (`GetVehicleNumberPlateText` scan); if any WHIP car (owned included) has that plate, its id is returned.
- Returns `vehicleId` or `false, err`: `'No vehicle there'`, `'That is not a vehicle'`, `'Too many street cars brought in already'`, `'That vehicle has no plate'`, `'Another vehicle already has that plate'`, `'Could not identify that vehicle'`, `'Could not adopt that vehicle'`, `'Pass a plate, or { entity = vehicle } / { netId = id }'`, `'plate required'`, `'No vehicle with that plate'`.
- Fires `whip_core:vehicle:registered` for a new record. To read by plate use `GetVehicle({ plate = })`.

## Server: in and out of the world

### SpawnVehicle(vehicle, coords?) — SERVER, WAITS
Owned cars only (session: `'Session vehicles are adopted, not spawned'`). Server creates the entity (`CreateVehicleServerSetter`); a car already out is moved (despawned and rebuilt), never cloned. `coords`: `vector3`, `vector4` (w = heading) or table with `x,y,z,w|heading`; default the saved position (`'No position to spawn at'`). Refused if occupied (the car itself excepted). Sets state `out`, saves position, applies lock and stored look, fires `spawned`. Returns `netId` or `false, err` (`'Vehicle is busy'`, `'Could not create the vehicle'`, `'Vehicle did not network'`, missing model, `'Spawn failed'`). Does not check garage state: retrieve first for a garaged car.

### DespawnVehicle(vehicle, opts?) — SERVER, WAITS
- No `opts.garage`: an owned `out` car is stored in the garage it is filed under (state `garaged`, position cleared, storage flushed), even occupied; it stays put away after restart. A car already out of the world: success. A temp car: removed for good, key taken back. A street car: handed back to GTA, forgotten, contents logged lost, `released` fires.
- `opts.garage = key`: only an owned `out` car; stored into that garage. Errors: `'A street car cannot be put in a garage'`, `'A temporary car cannot be put in a garage'`, `'Vehicle is already stored'` (use `SetVehicleGarage`), `'No such garage: x'`.
- `opts.refuseOccupied`: default `true` with a garage, `false` without; `'Somebody is still in that vehicle'` (players only).
- Returns `true` or `false, err`; `'Vehicle is busy'` mid spawn/store/delete (retry).

```lua
local c = GetEntityCoords(GetPlayerPed(source))
local key = exports.whip_core:GetNearestGarage(c.x, c.y, c.z, 15.0)
if key then exports.whip_core:DespawnVehicle(vehicleId, { garage = key }) end
```

### RetrieveVehicle(vehicle, garageKey?) — SERVER, WAITS
Marks a garaged car `out` and sets its lock (locked, unless its own key is in its ignition; `lockChanged` fires). Then call `SpawnVehicle` where you want it. `garageKey` default its own garage; a car filed under another garage: `'Wrong garage'` (a car with no garage is retrievable anywhere). Errors: `'Vehicle not found'`, `'Vehicle is not garaged'`, `'Vehicle is busy'`, missing model.

## Server: ownership and deletion

### TransferVehicle(vehicle, newOwner, opts?) — SERVER, WAITS
`newOwner`: server id or `{ charId }`, must be online (`'The new owner must be online'`). `opts.giveKey` (default `true`), `opts.revokeOldKeys` (default `true`). Writes the owner, resyncs both players' lists, fires `whip_core:vehicle:ownerChanged { vehicleId, from, to }`. Errors: `'Session vehicles have no owner'` (use `ClaimVehicle`), `'Already owned by that character'`, `'Invalid character'`, `'Vehicle not found'`. Revoking only empties the seller's pockets while online; stashed/boot/ground/ignition keys still work (use `ChangeVehicleLocks`). If the buyer's pockets are full they get no key and it still returns `true`.

### DeleteVehicle(vehicle) — SERVER
Owned car: row, boot, glovebox, ignition, entity and queued writes removed in one transaction; contents logged lost on the owner's timeline; refused if contents can't be read or settled (`'Could not read what is in it'`, `'Its trunk could not be saved first'`, `'Could not delete the vehicle'`, `'Vehicle is busy'`). Session car: forgotten (`released` reason `'deleted'`); a street car stays in the world (read its entity first, then `DeleteVehicle` + `DeleteEntity` to make it vanish); a temp car is deleted. Fires `whip_core:vehicle:deleted { vehicleId, ownerCharId, wasOut }` (owned only). Ungated: check permission yourself.

## Appearance (server) and properties (client)

- **Properties** = GTA's look on an entity, client natives (`Get/SetVehicleProperties`). **Appearance** = the look WHIP stores per vehicleId (server, `properties` column, stamped on the `whipAppearance` statebag so any client streaming the car dresses it).
- Stored appearance whitelist (`APPEARANCE_FIELDS`, `vehicles.lua:1528`): `color1 color2 pearlescent wheelColor wheelType windowTint livery plateIndex dirtLevel headlightColor interiorColor dashboardColor` (numbers), `turbo smokeEnabled xenon` (booleans; 0/1 accepted), `customColor1 customColor2 tyreSmoke neonColor neonEnabled extras` (tables), `mods` (`{ ["0".."49"] = index }`, mods 18/20/22 dropped: they are the toggles), `extras` (`{ ["1".."14"] = bool }`). Everything else (plate, model) dropped.
- A client's report of its car's look is believed for **dirt only**; any other difference is logged and held back. Paid looks go through `SetVehicleAppearance`.
- Shop flow: `HoldVehicleAppearance(id, true)` on the client, preview with `SetVehicleProperties`, server `SetVehicleAppearance` what was paid, `RestoreVehicleAppearance` to strip the rest, release the hold.

### SetVehicleAppearance(vehicle, props, opts?) — SERVER, WAITS
- `props` merged over the stored look; `mods` and `extras` merge one level deeper (slot keys normalised, `11` = `"11"`); pass a field at its default to clear it. Performance mods allowed (trusted code).
- `opts.data = { key = value }`, `opts.clearData = { 'key', ... }`: your vehicle-data keys written in the same transaction (checked as a `SetVehicleData` batch; a key both set and cleared is refused).
- Pushes the look to the client simulating the car (or players in range).
- Returns `true` or `false, why` with nothing changed (car shows the old look again; refund): `'props must be a table'`, `'opts must be a table'`, `'opts.data must be a table of key = value'`, `'opts.clearData must be a list of keys'`, `'vehicle not found'`, data refusals, `'save failed'`.
- A session car keeps the look only while it exists.

```lua
exports.whip_core:SetVehicleAppearance(vehicleId, { mods = { ['23'] = 4 }, color1 = 27 },
    { data = { myStance = { height = -0.05 } } })
```

### RestoreVehicleAppearance(vehicle) — SERVER
Pushes the stored look back onto the car for everyone (undo for a client preview; previews replicate). `true` or `false, err`.

### HoldVehicleAppearance(vehicle, held) — CLIENT
Marks a car as being previewed so this client doesn't report it. Returns `true` or `false, reason` (another resource holds it, release isn't yours, `'HoldVehicleAppearance: no such vehicle'`); releasing an unheld car is `true`. Releasing reports the car immediately. If the holder resource stops, the stored look is restored. Always release on close and on death.

### GetVehicleProperties(vehicle) — CLIENT
Returns `{ model (hash), plate (raw, padded), plateIndex, color1, color2, customColor1?, customColor2?, pearlescent, wheelColor, mods (slots 0-49 except 18/20/22, as strings), wheelType, turbo, smokeEnabled, xenon, tyreSmoke, neonColor, neonEnabled (4 bools), windowTint, livery, extras ({ ["n"] = bool } for existing extras), dirtLevel, headlightColor, interiorColor, dashboardColor }`; `{}` for an invalid handle.

### SetVehicleProperties(vehicle, props) — CLIENT
Applies, unsaved; needs network control (else natives silently do nothing). Absent fields untouched; a mod value `-1` removes the mod; `props.plate` (if present) is applied to the entity; extras switched without GTA's repair. Returns `true` or `false, why`: `'props is a table, as GetVehicleProperties answers'`, `'no such vehicle here'`, `'that number is an entity handle, not a vehicleId: pass { entity = veh }'` (bare handle; printed once per resource). Reverts when the server next pushes the appearance.

```lua
local before = exports.whip_core:GetVehicleProperties({ entity = veh })
exports.whip_core:SetVehicleProperties({ entity = veh }, { livery = 3 })  -- preview
exports.whip_core:SetVehicleProperties({ entity = veh }, before)         -- undo
```

### SetVehicleExtras(vehicle, extras) — CLIENT
`{ [n] = true|false }`, n 1-14 (1/0 accepted). Only switches extras that exist and differ, and restores engine/body/tank health, fuel level, dirt, broken doors and burst tyres afterwards (GTA's `SetVehicleExtra` repairs the car). Dents can't be kept. Returns count switched. Needs control.

### TakeVehicleControl(vehicle, opts?) — CLIENT, WAITS
`opts.attempts` (default 3, clamped 1-10), `opts.wait` ms per try (default 500, clamped 10-5000). Returns `true` or `false, why`: `'no such vehicle'`, `'another player is driving it'` (do it on the driver's client), `'control was not granted'`.

## Catalog, pictures, prices

### GetVehicleCatalog() — SERVER
Copy: `{ [model] = { model, displayName, class (GTA class number), hasImage, image (URL or false), inGame (VehicleModelExists result) } }`. Seeded from `server/vehicle_catalog_list.lua` (930 cars) into the `vehicle_catalog` table, plus `RegisterVehicles` packs. Don't sell `inGame == false`. A picture exists when a media pack has `img/vehicles/<model>.webp` (non-empty).

### RegisterVehicles(list) — SERVER, WAITS
`list = { { model, name?, class, image? } }`: the whole list for your resource (models left out later are removed; all go when you stop). `class`: a class name or `GetVehicleClass` number 0-22. `image`: a file in your resource (listed in `files {}`) or `'@res/path'`. A model WHIP already lists keeps its name/class and takes your picture. Waits for core ready. Returns `true` or `false, why` with nothing added: `'vehicle N needs a model (60 characters at most)'`, bad class, picture not in your resource, `'add-on vehicle "x" belongs to <res>'`, not-ready text.
Classes: `compacts sedans suvs coupes muscle sportsclassics sports super motorcycles offroad industrial utility vans cycles boats helicopters planes service emergency military commercial trains openwheel` (0..22 in that order).

### GetVehicleImage(model) / HasVehicleImage(model) — SERVER
URL (e.g. `https://cfx-nui-whip_media_previews/img/vehicles/sultan.webp`, or a pack's own) or `nil`; `HasVehicleImage` boolean. Case-insensitive.

### SetVehiclePrices(prices) — SERVER
`{ [model] = price }` whole dollars > 0; your list (replaced when declared again, dropped when you stop). Used by `/whip` Banks to value owned cars (average across sellers). `true` or `false, why` (`'prices must map a vehicle model to its price, e.g. { adder = 1000000 }'`, `'invalid price for x'`).

## Storage: boot, glovebox, ignition as stores

- Address: `{ kind = 'vehicle', id = <vehicleId or reference>, sub = 'trunk' | 'glovebox' | 'key' }`. Use the generic store exports (`StoreRead`, `StoreCount`, `GetItemAt`, `StoreGive`, `StoreTake`, `StoreMove`, `OpenStore`, `CloseStore`). Storage loads on demand (`'could not read that vehicle\'s storage'`, `"vehicle address needs sub = 'trunk', 'glovebox' or 'key'"`).
- `OpenStore(source, addr, opts)` opens only the **trunk** (glovebox and ignition open from the seat: `"only a vehicle's 'trunk' opens this way; ..."`); same rules as a player (within `Config.VehicleTrunkRange + 3.0` = 5.5 m, unlocked); `opts.skipAccess = true` opens a locked boot (warrant, spare key); distance can't be skipped.
- Sizes, first that is set: the car's own (`trunkSlots`, ... from creation), its model's (`vehicle_meta`), its GTA class's (`vehicle_class_meta`), config (`Config.VehicleTrunkSlots` 40, `Config.VehicleTrunkMaxWeight` 200.0, `Config.VehicleGloveboxSlots` 10, `Config.VehicleGloveboxMaxWeight` 20.0, motorbikes (class 8) `Config.MotorbikeGloveboxSlots` 1). Ignition always 1 slot / 1.0.
- Models and classes are set in `/whip` → Vehicles → Vehicle Adjustments (ACE `whip.devtools`); either can turn the boot or glovebox off (model beats class). Slots 1-500. Shrinking or turning off is refused while any car of that model still holds items in the affected slots.
- Bicycles (class 13) have no glovebox and no ignition. A storage turned off refuses to open (`'This vehicle has no trunk'`).
- A boot is shared like a stash (several viewers, atomic moves); moves are re-checked against `Config.VehicleStorageKeepRange` (5.5 m) on each move; a locked car refuses reaching inside. Destroying a key in the ignition: `'Take the key out first'`.
- Session cars' storage is memory only: lost (logged) when the car is released.

## Seats and occupancy

- `Config.Seats.NoAutoShuffle = true` (default): passengers never slide into an empty driver's seat; GTA's shuffle (H / D-pad right) does nothing. Players move seats via Seats on the F1 wheel or `/seats`; the server claims the target seat for 3 s so two players can't race for it (`'That seat is occupied'`, `'Someone is already moving into that seat'`).
- Server `whip_core:vehicle:entered` fires on entering any seat of a WHIP car and again on a seat change (with `previousSeat`); `whip_core:vehicle:exited` on leaving (with `left = 'logout'|'dropped'` when leaving the game). The server only announces seats it can see the ped in.
- `Config.BikeAutoHelmet = false`: no automatic helmet.

## Damage a car keeps

- Owned cars only; `Config.VehicleDamage.remember` (default true) turns it on. Kept: engine and body health, doors torn off, burst/rim tyres. Not kept: dents (deformation).
- Five built-in stats (reserved names), read with `GetVehicleStat`:

| Stat | Range | Meaning |
|---|---|---|
| `engineHealth` | 0-1000 (default 1000) | GTA scale; below 400 smokes |
| `bodyHealth` | 0-1000 (default 1000) | |
| `doorsOff` | 0-255 mask | bit n = door n: 0 FL, 1 FR, 2 RL, 3 RR, 4 bonnet, 5 boot (6/7 extra rear doors) |
| `tyresFlat` | 0-255 mask | bits over GTA tyres `0,1,2,3,4,5,45,47` |
| `tyresRim` | 0-255 mask | same bits; a tyre on its rim is not also flat |

- Read: engine/body by the server (driver gets out, the position sweep, last look before despawn); doors/tyres reported by the driver's game. Saved with the car's row unit. A stat at its default is cleared (an undamaged car carries none).
- Put back when the car leaves a garage or after a restart when a game takes it (offered at 0.5, 1.5, 3, 6, 10 s after spawn, then by the sweep, always to whoever takes the wheel). Only ever adds damage. A wreck comes back with engine at least `Config.VehicleDamage.engineFloor` (100): smoking, never burning.
- A repair must clear it or the next spawn puts it back.

### ClearVehicleDamage(vehicle) — SERVER
Forgets the stored damage (clears the five stats; reads paused 2 s so a pre-repair read doesn't restore it). Does not fix the car in the world: the game running it must (e.g. `SetVehicleFixed`). `true` or `false, 'Vehicle not found'`.

## Vehicle data

For anything that should stick to a car that is not a gauge (stat), items (store) or a GTA mod (appearance): a part's grade, a finance flag, a kit's roll distances.
- Values: any JSON-encodable (`false` included; never clamped/drawn). Saved in the row's `vehData` (owned), replicated in `whipVehData` to every client with the car in scope (so no secrets). Follows the car through garaging, despawn, restart; deleted with the car. Session cars: memory only.
- Keys: 1-40 chars of `[A-Za-z0-9_]`. A key belongs to the resource that first wrote it; anyone reads, only the owner writes/clears (`'key "k" on vehicle N belongs to <res>'`). Owners are saved in the same JSON under `@owners` (never replicated).
- Limits: 32 keys per resource per car (`'<res> already has 32 data keys on vehicle N'`); whole block <= 8192 bytes serialized (`'vehicle N data block would be X bytes serialized — the ceiling is 8192 (refused for <res>)'`). Not a database: no index, build your own table for queries/history.

### SetVehicleData(vehicle, key, value) — SERVER, WAITS
`nil` value removes. Returns `true` or `false, why`: `'key must be 1-40 characters of [A-Za-z0-9_]'`, foreign key, budget, size, `'value for "k" is not json-encodable: ...'`, `'vehicle N data could not be saved'` (undone), `'no such vehicle'`.

### SetVehicleData(vehicle, values) — SERVER, WAITS
Batch `{ [key] = value }`: one replication, one write; each key fires its own `dataChanged` after commit. Cannot remove keys (use `ClearVehicleData`). Keys past your 32 are skipped and logged; a foreign key or busting 8 KB refuses the whole batch. Returns `number written` or `false, reason` (incl. `'nothing written: no valid key (1–40 of A-Z a-z 0-9 _), or the key ceiling is full'`).

### GetVehicleData(vehicle, key?) — BOTH
Value (stored `false` reads `false`), `nil` if absent (no default). No key: copy of the whole block (`{}` for none / unknown car). Client: only for a car streamed in.

### ClearVehicleData(vehicle, key) — SERVER, WAITS
Only your key. `true` also when already absent.

### ClearAllVehicleData(vehicle) — SERVER, WAITS
Every key **your** resource put on the car; one `dataChanged` per key. Stats untouched (`ClearVehicleStat`).

### OnVehicleDataChanged(key, callback, id?, opts?) — SERVER
- Positional callback `(vehicleId, value, cleared, old)`; with `opts.table = true` one table `{ vehicleId, key, value, old, cleared, resource }`.
- `id`: only for two listeners on one key (same id replaces; default = key; registration key `<resource>:<id>`). `opts` may go third.
- `opts.now = true`: also called once (in a thread) for every car carrying the key (the `now` call has no `old`/`resource`).
- Dropped when your resource stops. Returns `true` or `false, why` (`'key is required (a vehicle data key)'`, `'callback is required'`).
- Driven by the writes (a fired copy of `whip_core:vehicle:dataChanged` never reaches it). `ClearAll` by whip_core itself tells every listener `cleared = true`.

```lua
Whip.register(function()
  Whip.core:OnVehicleDataChanged('kit', function(c)
    if c.cleared then --[[ c.old was the kit ]] end
  end, { table = true, now = true })
end)
```

### OnVehicleDataChanged(key, callback, id?, opts?) — CLIENT
For cars streamed to this client. Positional `(vehicleId, value, old, entity)` (note the different order from the server); table `{ vehicleId, key, value, old, cleared, entity }`. `now = true`: every car in range carrying the key. Table values are announced on every replication (only scalars are diffed); a car that streams back in re-announces everything.

### WatchVehicleData(key, data) — CLIENT
Run code while a car in scope carries a data key (twin of `WatchVehicleStat`), for per-client effects GTA doesn't replicate (engine sound, stance, handling).

| Field | Signature | Meaning |
|---|---|---|
| `onGained` | `(entity, value, vehicleId)` | a car in scope has the key (cars already in scope announced at registration) |
| `onChanged` | `(entity, value, old, vehicleId)` | new value; without it: `onLost(old)` then `onGained(new)` |
| `onLost` | `(entity, value, vehicleId)` | key removed or car left scope; `value` = what it was |
| `onStart` | `(entity, value, vehicleId)` | starts for the car (with `driverOnly`: you now drive it) |
| `onStop` | `(entity, value, vehicleId)` | you got out / key or car went; a new value while started fires `onStop(old)`, `onStart(new)` |
| `driverOnly` | bool, default false | narrow start/stop to the car you drive |
| `id` | string | two watchers on one key; same id replaces (old one's onStop fired) |

Returns watcher id (`'<resource>:<id or key>'`) or `false, why` (`'key is required (a vehicle data key)'`, `'data must be a table of callbacks'`, `'give at least one of onGained, onChanged, onLost, onStart, onStop'`). Values compared by content (another key changing doesn't re-fire). Sweep every 200 ms detects cars leaving scope / driver changes. Your resource stopping (or whip_core stopping) never calls `onStop`: restore in your own `onResourceStop` (and `Whip.onCoreLost` without `dependency 'whip_core'`).

### UnwatchVehicleData(watcherId) — CLIENT
Fires `onStop` for what it started (not `onLost`). Returns `boolean`.

## Handling, power and the rev dial (client)

Physics belongs to the driver: set these from a `driverOnly` watcher's `onStart` and clear in `onStop`. One car at a time per client: naming a different car puts the previous one back first.

### SetVehicleHandlingLayer(vehicle, name, spec) — CLIENT
- Never write handling directly: declare a layer. WHIP captures each field's stock value, applies all resources' layers, and restores on every exit (layer cleared, another car, car gone/dead, a resource stopping, whip_core stopping).
- `name`: 1-40 chars, one per feature; setting again replaces.
- `spec.set = { field = value }` absolute (`CHandlingData` fields `f...` floats, `n...` ints, pattern `^[fn][A-Z]%w+$`, max 48 chars); `nInitialDriveGears` kept 1-7 (also sets high gear).
- `spec.add = { field = amount }` (-1000..1000), summed after every layer's `set`.
- `spec.scale = { field = factor }` (0.01..100), multiplied after sets and adds.
- `spec.order` (default 0): when two layers `set` one field the higher order wins (ties by layer key).
- Drivetrain fields (`fInitialDriveForce, fInitialDriveMaxFlatVel, fDriveInertia, nInitialDriveGears, fClutchChangeRateScaleUpShift, fClutchChangeRateScaleDownShift, fDriveBiasFront`) are committed for you (`ModifyVehicleTopSpeed(0.0)`).
- Returns `true` or `false, why` (`'no such vehicle'`, `'name is required (1-40 characters)'`, `'"x" is not a handling field'`, range errors).

### ClearVehicleHandlingLayer(name) — CLIENT
Returns `boolean` removed; the car goes back to stock once no layer is left.

### GetVehicleHandlingBase(vehicle, field) — CLIENT
A field's value after every `set` and `add`, before `scale` (the current value for an unmodified car); `nil` for a bad car/field.

```lua
exports.whip_core:SetVehicleHandlingLayer({ entity = veh }, 'tune', { scale = { fSuspensionForce = 1.2 } })
exports.whip_core:ClearVehicleHandlingLayer('tune')
```

### SetVehiclePower(vehicle, name, multiplier) / ClearVehiclePower(name) — CLIENT
Torque, not gearing (turbo boost, nitrous). `multiplier` 0-10 (1.0 = stock). The car gets the product of every resource's ask, written every frame via `SetVehicleCheatPowerIncrease`; back to normal when nothing is asked. Asking again just updates (cheap; call as the amount changes). Returns `true`/`false, why` (`'multiplier must be a number from 0 to 10'`, ...); Clear returns `boolean`. Never call `SetVehicleCheatPowerIncrease` yourself (last write in a frame wins). Scaling `fInitialDriveMaxFlatVel` stretches every gear; use power for more speed.

### SetVehicleRevRange(vehicle, engine) — CLIENT
Which engine this player's rev dial follows. `engine`: a model spawn name (that engine's `rpmByModel`/electric/class; `'"x" is not a vehicle model'`), `{ max, idle? }` in thousands (max 2-20, idle >= 0 and < max), or `nil` for its own. Owned by the setter resource (another running resource's setting is refused); dropped when you stop. Set it on every client (in a `WatchVehicleData` `onGained`, clear in `onLost`). Returns `boolean, why`.

### IsVehicleElectric(vehicle) — CLIENT
GTA's electric flag on the car's engine model (its own, or the one `SetVehicleRevRange` names). `false` for a car not here or a build without the flag. whip_fuel gives electric cars no fuel.

### SetVehicleDialGear(vehicle, gear) — CLIENT
Forward gear the dial shows when your resource drives the gears: 1-20 whole number, `'speed'` (dial derives gear from speed and ratios, shows R going backwards), or `nil` (game's gear again; from `'speed'` it puts GTA's gearbox in the shown gear). Reverse and N stay the game's. This player's dial only; cleared when you stop. Errors: `"gear must be a whole number, 1 to 20, or 'speed'"`, `'no such vehicle'`, another resource's setting.

## Vehicle stats: registration and server API

A vehicle stat is a number a car carries (fuel, nitrous, wear, boost). WHIP saves it, replicates it (`whipStats`, live values in `whipLive`) to everyone with the car in scope, draws its gauge, and polices client reports.

Built-ins: `engine` (whip_core, `Config.VehicleStats.engine`: 0/1, `persist = false`, iconOnly hud, order 90), the damage stats; `fuel` is whip_fuel's (default 100, 0-100, `consume`, order 1); `nitro` (whip_autos: default 0, `consume { clearAtMin = true, interval = 0.5 }`, order 4, `showAboveZero`), `boost` (whip_autos: `persist = 'presence'`, `live { interval = 0.25 }`, psi display, order 6, `showWhenPresent`). The dial has its own glyphs for fuel, boost (turbo) and nitro, so those registrations give no icon.

### RegisterVehicleStat(name, config) — SERVER
- `name`: letters, digits, `_`, not starting with a digit, max 32 (`'turbo-boost'`, `'2step'` refused). Reserved: `engine, engineHealth, bodyHealth, doorsOff, tyresFlat, tyresRim` (`'vehicle stat "x" is owned by whip_core'`). A name another running resource registered is refused; re-registering your own identical config changes nothing.
- Registration is your resource's: dropped when it stops; **values stay** (use `PurgeVehicleStat` to retire). Declare it inside `Whip.register` so it returns after a whip_core restart.

| Field | Default | Meaning |
|---|---|---|
| `default` | 0 | what a car without a stored value reads |
| `min` / `max` | 0 / 100 | writes clamped |
| `persist` | `true` | `false`: never saved; `'presence'`: written only when the stat appears or goes (fitted turbo survives, its momentary value comes back at default) |
| `decay` | none | added every `decayInterval` to cars in the world (negative drains); omit to disable (`0` treated as none in code); presence stats decay only on cars that carry them |
| `decayInterval` | 10 | seconds |
| `hud` | none | gauge (see below) |
| `consume` | none | client reports usage (see below) |
| `live` | none | client reports current value |
| `display` | none | how the value reads |

`hud` keys: `label`, `icon` (SVG path in 24x24 box; omit for the dial's own fuel/boost/nitro glyphs), `iconCritical` (alt icon when nearly empty; extra paths separated by `|`), `color` (hex; not used on the dial, which draws white), `order` (default 99, lower first; fuel is 1; max five gauges shown), `iconOnly` (lit/unlit symbol, no gauge; never with `showAboveZero`), `heartbeat` (pulse when low), `hideWhenEmpty`, `noCritical` (no red flash below 20%), `showAboveZero` (only once > 0, for quantities that run out), `showWhenPresent` (only when the car carries it, for fittings). A `hud` stat also gets a meter on the garage card.

`display` (one shape, checked): `{ unit = 'psi', range = { bottom, top } }` or `{ unit = '°C', points = { {pct, reading}, ... } }` (2-16 pairs, pct 0-100), and/or `{ ends = { 'E', 'F' } }` (<=3 chars each); `decimals` 0-2 (default 0); `unit` max 8 chars and needs range or points; range and points are exclusive. Errors e.g. `'display needs range, points or ends'`.

`consume` / `live` (one or the other, both refused): `maxRate` required (> 0, units/s: consume = drain ceiling, live = rise ceiling), `driverOnly` (default `true`), `interval` (seconds; default 1.0 consume / 0.5 live, floor 0.25), `slack` (default 1.25), `clearAtMin` (consume only, default false; requires `default == min` else refused: a cleared stat reads its default and would refill itself).

Returns `true` or `false, err`.

```lua
Whip.register(function()
  Whip.core:RegisterVehicleStat('nos', {
    default = 0, min = 0, max = 100,
    consume = { maxRate = 5.0, clearAtMin = true, interval = 0.5 },
    hud = { label = 'NOS', icon = 'M6 2h6v20H6z', color = '#60a5fa', order = 2, showAboveZero = true },
  })
end)
```

### GetVehicleStat(vehicle, name) — BOTH
Stored value, else registered default; `nil` for unknown car or unregistered stat. Client: car streamed in (live block first).

### GetVehicleStats(vehicle, opts?) — BOTH
`{ [name] = value }` for every registered stat, defaults filled. Server `opts.stored = true`: only what the car stores (no defaults; `nil` for an installable = not fitted; `{}` for unknown car). Client has no `stored` option (`{}` for a car not here).

### SetVehicleStat(vehicle, name, value, changeSource?) / AddVehicleStat(vehicle, name, delta, changeSource?) — SERVER
Clamped, saved (write-behind on `vehrow:<id>`), replicated, announced (`changeSource` default `'direct'`). Unregistered names refused: `'unknown vehicle stat "x" — RegisterVehicleStat it first'`; also `'Vehicle not found'`, `'value for "x" must be a number'`. Add on an absent stat starts from the default (fits it). Each single write re-sends the car's whole stat block.

### SetVehicleStats(vehicle, values, changeSource?) — SERVER
Several in one replication and one announcement batch. Unregistered names and non-numbers skipped (logged). Returns `number written` or `false, reason` (`'values must be a table of [statName] = number'`, `'unknown vehicle stat(s) a, b — RegisterVehicleStat them first'`, `'Vehicle not found'`, `'nothing to write: no stat in the table had a number for a value'`).

### HasVehicleStat(vehicle, name) — BOTH
Does the car carry the stat (stored), not just read its default. Use for "is one fitted"; `GetVehicleStat(...) > 0` is wrong for stats resting above zero.

### ClearVehicleStat(vehicle, name) — SERVER
Takes the stat off one car (part removed); reads fall back to default; announced with `cleared = true` (`source 'clear'`); resets a live stat's rate cursor. `true` includes already absent. Setting 0 is not the same (bottle fitted and empty).

### PurgeVehicleStat(name) — SERVER
Clears the stat from every car, permanently. Returns count of cars that had it, or `false, 'vehicle stat "x" belongs to <res>'` when another running resource owns it (anyone may purge a stat with no running owner). Stopping a resource never purges.

### OnVehicleStatChanged(name, callback, id?, opts?) — SERVER
- `name`: a stat or `'*'` (every stat; costly).
- Positional `(vehicleId, value, previous, cleared, source)`; `'*'`: `(vehicleId, name, value, previous, cleared, source)`; `opts.table = true`: `{ vehicleId, key, value, old, cleared, source }`.
- `source` values seen: `'direct'` (default), your `changeSource`, `'consume'`, `'live'`, `'decay'`, `'clear'`, `'ignition'`, `'held'`, `'despawned'`, `'damage'`, `'now'`.
- `opts.now = true`: once for every car carrying it (`source = 'now'`); `now = 'all'` (named stat only): every car WHIP has, defaults included (re-registering after the default changed visits them again).
- Same id replaces; options may go third. Dropped when your resource stops. Called on a change, not on a clock; no event exists for stat changes.
- Must not wait (runs inside the stat write; changes inside a batch are delivered once, after it). Put DB work in `CreateThread`.
- Returns `true` or `false, why`.

```lua
exports.whip_core:OnVehicleStatChanged('boost', function(vehicleId, value, previous)
  if value >= 20 then --[[ flat out ]] end
end)
```

## Vehicle stats: client API, consume and live, gauges

### OnVehicleStatChanged(name, callback, id?, opts?) — CLIENT
Cars in scope. Positional `(vehicleId, value, old, entity)`; table `{ vehicleId, key, value, old, cleared, entity }`. Same `table`/`now` options (no `'*'`, no `'all'`).

### WatchVehicleStat(name, data) — CLIENT
Runs code while a car in scope carries a stat (presence from the stored block). `name` may be a list: each callback then gets the stat name second (`onGained(entity, name, value)`) and one id covers the list.

| Field | Signature | Meaning |
|---|---|---|
| `onGained` | `(entity, value)` | a car in scope gained it (existing ones announced at registration); ignores driverOnly |
| `onLost` | `(entity)` | a car in scope lost it; getting out does NOT fire it |
| `onStart` | `(entity, value)` | `whileHeld` about to run for this car |
| `onStop` | `(entity)` | `whileHeld` stopped (got out, stat lost, car despawned, part pulled) |
| `whileHeld` | `(entity, value, dt)` | repeatedly; `dt` real seconds, clamped to max(0.25, 2 x interval); return a number to show it on this client's gauge until `onStop` |
| `interval` | ms, default 0 | 0 = every frame (120 calls/s at 120 fps); start at 50 |
| `driverOnly` | default false | narrow whileHeld/onStart/onStop to the car you drive (use for handling/physics) |
| `id` | | two watchers on one stat; same id replaces (old onStop fired) |

Returns id (`'<resource>:<id or name>'`) or `false, why` (`'data must be a table of callbacks'`, `'give at least one of onGained, onLost, onStart, onStop, whileHeld'`, `'name is a stat name or a list of them'`, `'the list holds no stat names'`). A list's `whileHeld` runs once per stat. Your resource stopping never reaches `onStop`: restore in `onResourceStop` (make restore safe to run twice) and `Whip.onCoreLost`.

```lua
exports.whip_core:WatchVehicleStat('boost', {
  onStart   = function(entity) captureHandling(entity) end,
  whileHeld = function(entity, value, dt) simulate(entity, dt) end,
  onStop    = function() restoreHandling() end,
  interval = 50, driverOnly = true,
})
```

### UnwatchVehicleStat(watcherId) — CLIENT
Fires `onStop` for what it was running (not `onLost`); a list's id stops all. `boolean`; only your own.

### SetVehicleStatWatchInterval(watcherId, ms) — CLIENT
`false` when unchanged or not yours. 0 = every frame.

### consume vs live

| | `consume` | `live` |
|---|---|---|
| Value | only falls | rises and falls |
| Client reports | amount used | current value |
| Client export | `ConsumeVehicleStat(s)` | `ReportVehicleStat` |
| Server caps | drain rate | rise rate (falling uncapped) |
| For | fuel, nitrous, tyre wear | boost, heat, charge |

- One batched event per car per interval (`whip_core:server:reportStatBurn` running totals / `reportStatLive` values; <=64 stats per batch); the client sender wakes every 250 ms and repeats the final total/value 3 times so a lost last report doesn't freeze a gauge.
- Driver check (`driverOnly`), cap against the wall clock: elapsed capped at 4 x interval; take = min(claimed, maxRate x elapsed x slack). The first report of a run sets the baseline and bills nothing. With `driverOnly = false` one reporter is latched until it goes quiet for 4 intervals.
- A live report for a stat the car doesn't carry is ignored (reporting never fits a part). A non-`live` write (`SetVehicleStat`) resets the live cursor.
- `interval` sets how often others' gauges and the server hear; apply the effect locally every frame and show your own value via `whileHeld`'s return. Reporting is the most expensive thing WHIP does server-side: slower is cheaper.

### ConsumeVehicleStat(vehicle, name, delta) — CLIENT
Accumulates locally (positive delta), sent on the stat's cadence. Safe every frame. `false` when the car doesn't resolve to a WHIP id or delta <= 0. Doesn't check the tank: the server clamps at min; read `GetVehicleStat` to stop at empty.

### ConsumeVehicleStats(vehicle, deltas) — CLIENT
`{ [name] = used }`. Returns `ok, accepted`: `(true, 0)` = car resolved, nothing usable; `(false, 0)` = car didn't resolve. Check `ok`.

### ReportVehicleStat(vehicle, name, value) — CLIENT
Newest value wins, sent at `interval`. `boolean` whether taken locally (not whether the server accepts). ~20 µs a call: call when it moved enough, not every frame; compare by difference so a refused send is retried.

### Gauges (this player's dial only; one rule per stat, owned by its setter, dropped when it stops)
- `SetVehicleStatDisplay(name, fn)` / `ClearVehicleStatDisplay(name)`: `fn(entity, replicated) -> number|nil` local reading instead of the replicated value (changes the number, not visibility). Without a watcher the needle moves about once a second; a `whileHeld` return is cheaper and wins. Returns `true` or `false, reason` (another resource provides it; `'SetVehicleStatDisplay: a stat name and a provider are required'`).
- `SetVehicleStatShown(name, fn)` / `ClearVehicleStatShown(name)`: `fn(entity) -> false` hides the gauge on that car; answer from what the car is.
- `SetVehicleStatIcon(name, fn)` / `ClearVehicleStatIcon(name)`: `fn(entity)` returns a dial glyph (`'fuel' 'fuel_left' 'fuel_right' 'turbo' 'nitro' 'coolant' 'hack' 'weapon'`), an SVG path (24x24), or `nil` for the stat's own; asked at most once a second.

```lua
exports.whip_core:SetVehicleStatShown('fuel', function(entity)
  return not exports.whip_core:IsVehicleElectric({ entity = entity })
end)
```

## Client vehicles API: finding cars, control, points, part actions

All are instant cache reads except `ResolveVehicle` and `TakeVehicleControl` (they wait).

### GetVehicleId(entity) — CLIENT
Bare handle or `{ entity = veh }`. vehicleId from the replicated stamp (cached), or `nil` for a car WHIP hasn't met. Safe in `canInteract`.

### GetVehicleEntity(vehicle) — CLIENT
Entity for a vehicleId/reference, or `nil` when not streamed in here.

### ResolveVehicle(entity) — CLIENT, WAITS
Bare handle or `{ entity }`. Returns the id (registering a street car on the server first, one round trip) or `false, why`: `'That vehicle is not there'`, `'That is not a vehicle'`, `'That vehicle has no plate'`, `'That vehicle is not networked'`, `'That vehicle is not near you'` (20 m), `'That plate belongs to an owned vehicle'`, `'You already hold 20 street cars'`, `'That vehicle could not be registered'`, `'That vehicle could not be identified'`. Only in `onSelect`, commands, one-offs; never in `canInteract`, labels, loops or per-frame code.

```lua
onSelect = function(ctx)
  local id = exports.whip_core:GetVehicleId(ctx.entity)
  local why
  if not id then id, why = exports.whip_core:ResolveVehicle(ctx.entity) end
  if not id then return ctx.refuse(why) end
  TriggerServerEvent('tow:hookVehicle', id)
end,
```

### GetVehicle(vehicle) — CLIENT
`nil` when not streamed in. Fields: `vehicleId, entity, netId, plate` (raw entity text, padded), `model` (name), `modelHash, class` (GTA number), `vehType, session, mine` (in this player's owned list), `hasKey` (key cache), `keyInIgnition` (only for the car you're in), `coords, heading, locked, engineOn, engineHealth, bodyHealth, colorPrimary, colorSecondary, occupants` (`{ seat, ped, isPlayer, serverId? }`, ambient peds included), `stats` (copy, defaults filled), `data` (copy). No owner/garage.

### GetNearbyVehicles(radius?) — CLIENT
Default 25, max 100 m; closest first: `{ entity, plate, vehicleId (or nil), distance, model }` (`model` = lower-cased display name).

### HasVehicleKey(vehicle) — CLIENT
From the synced key cache. `{ plate = }` reads the cache by plate (works for a car not streamed in).

### GetVehiclePoint(vehicle, action) — CLIENT
Where a named point is, on the side nearest the player: `'fuel'` (filler), `'engine'`, `'storage'` (boot), `'mount'` (bike), `'board'` (boat/heli/plane), `'cargo'`, or a resource's own. Returns `{ x, y, z, heading (facing out), side ('left'|'right'|'front'|'rear'), fixed (side doesn't follow the player) }` or `nil`. A car's filler: petrol cap bone, else above a rear wheel on the side from `Config.VehicleFillers[hash] = { side = 'left'|'right'|'rear' }`, else a side tank, else picked per model. `/vehpoints` draws them.

### SetVehiclePointRules(action, rules) — CLIENT
Your own point: `rules = { default = { place, ... }, bike = {...}, cycle, boat, heli, plane, car }` tried in order. A place: a bone name, a list of bone names (nearest), `'entry'`, `'box'`, `'box:rear'`, `'box:front'`, `'filler'`. WHIP's points and other resources' can't be taken; yours go when you stop. Returns `true` or `false, why` (`'"x" is whip\'s own point'`, `'rules = { default = { place, ... }, <kind> = { ... } }'`, `'name the point'`, ...).

```lua
exports.whip_core:SetVehiclePointRules('charge', { default = { 'petrolcap', 'box:front' } })
```

### Options on a car part
`AddAction({ id, at = { vehiclePart = part }, label, icon, canInteract, onSelect })`; `ctx.entity` is the car. Parts: `'hood'` (shown only while the bonnet is open or torn off: engine work), `'trunk'`, `'door_dside_f'`, `'door_pside_f'`, `'door_dside_r'`, `'door_pside_r'`, and the single prompt of a `'bike'`, `'bicycle'` or `'boat'`. One action per part (loop with distinct ids). A vehiclePart action is always on foot and alive; `first = true` puts it at the top of the part's stack while `canInteract` says yes. Prompt geometry is `Config.VehiclePartPrompts`.

### GetGarageHelperStatus() — CLIENT
`{ enabled, duiActive, drawing, driving, qualifies }`: observable state of the bay outline (for tuning/tests).

## Garages: concepts, bays, private garages, the wizard

- A garage = a key, a name, a marker (x/y/z/heading), a blip, and parking **bays** (`garage_spots` rows). Which cars are in it is each vehicle's `garage` field. Keys are permanent (cars are filed under them); get keys from `GetGarages`/`GetNearestGarage`, never hardcode from `config.lua` (a renamed/deleted garage gives `'Wrong garage'`).
- `Config.Garages` is a seed read only on the very first start (when no garage exists); default seed `legion_square` "Public Garage". Manage in `/whip` → Vehicles → Garages.
- A new garage gets one bay at its spawn point (or its marker if the spawn is 0,0,0). Garage with no bays can't be reached.
- **Out**: an empty bay's prompt shows the garage name; E lists cars garaged at that garage (plus "lost" cars: owned, `out`, no entity, filed here or nowhere); E on a car brings it into this bay with its look. Blocked bay (car body overlapping the bay outline, or a player within 2.5 m): `'Something is already parked in that spot'` / `'Someone is standing in that spot'`. A car stored backed-in (more than 90° off the bay heading) comes out backed-in. Isolate builders refused. Bay events need the player within 8 m of the bay.
- **In**: a bay with a car has no prompt; the car's doors get Store. Server checks the player may use the garage and the car is within `Config.GarageSpotRadius` + 2 m (3.5 + 2) of the bay; occupied cars can't be stored by players (`'Somebody is still in that vehicle'`). Bay events use a SecureEvent `'vehicle'` param, so only the owner's cars.
- Bay occupancy is by outline (`shared/garage_bay.lua`): bay `Config.GaragePositionHelper.length x width` (5.20 x 2.60) less 0.15 m all round; unknown car size taken as 5.0 x 2.1; another floor (> 2.5 m vertical) doesn't count.
- Bay outline (driver hint, no events): drawn for free bays (and the one you're in) when driving any car (or only owned ones with `requireStorable = true`); on foot every usable bay within `onFootRange` (10 m; 0 = drivers only); `showRange` 30 m; `alignDeg` 25°. Keep length:width at 2:1.
- **Private garages**: keys with a registered prefix containing `:` (properties use `property:<id>`): no blip, bays shown only to allowed players, bay events refuse others (`'That garage is private'`), `GetNearestGarage` never returns them, never the default garage. When access is lost (key taken, house sold) cars there move to the nearest public garage and owners are notified.
- Garages made by `CreateGarage` remember the creating resource; their blip shows only while it runs (the garage and cars stay).
- Wizard (ACE `whip.devtools`): `/whip` → Vehicles → Garages → + New Garage: Name (key derived/typed, permanent), Bays (bay tool, up to 40; property garages up to 8), Map (blip place/icon/colour), Create. Change on Name/Bays/Map later; bays keep their numbers; a garage keeps at least one bay. New/moved bays or markers further than `Config.GarageWizardReach` (250 m) from the admin are refused. A garage with cars can't be deleted in `/whip` until the admin picks the public garage they move to.
- Bay tool keys: ENTER (A) place/pick up, Q/E (LT/RT) rotate (the heading a car comes out facing), Up/Down (D-pad) raise/lower up to 5 m, hold ALT for slow, X remove, C (B) put back / undo the visit, ESC (Menu) finish. Nothing is written until Create / Save changes.

## Garages API

### GetGarage(key) / GetGarages() — SERVER
Copies: `{ garageId, key, resource, name, x, y, z, heading, spawnX, spawnY, spawnZ, spawnHeading, blipSprite, blipColor }` plus `private = true, managedBy` for a private garage; `nil` for unknown. `GetGarages()` → `{ [key] = garage }`.

### GetNearestGarage(x, y, z, maxRange?) — SERVER
Also `(coords, maxRange)` with a vector3/vector4/table. Distance to the marker or the nearest bay (big car parks count). Public garages only. Returns `key, distance` or `nil`.

### GetGarageVehicles(key) — SERVER
`GetVehicle` snapshots of cars with `state == 'garaged'` filed there; `{}` for unknown key.

### CreateGarage(data) — SERVER, WAITS
`data = { key (required, unique, permanent), name? ('Garage'), x?, y?, z?, heading? (marker, default 0), spawnX?, spawnY?, spawnZ?, spawnHeading? (first bay; 0,0,0 means "at the marker"), blipSprite? (357), blipColor? (3) }`. Clients get blip/marker at once. Returns the garage copy or `false, err` (`'Expected a table'`, `'Key is required'`, `'Key already exists'`, DB error, `'Could not create the garage'`). Add more bays in `/whip`.

```lua
local g, err = exports.whip_core:CreateGarage({ key = 'impound', name = 'Impound Lot',
    x = 409.3, y = -1623.1, z = 29.3, heading = 230.0 })
```

### UpdateGarage(key, data) — SERVER, WAITS
Only fields sent change (numbers that don't parse keep the old value). Row written before memory. `true` or `false, err` (`'key required'`, `'Garage not found'`, `'Expected a table'`, `'garage "x" belongs to <res>: only it can change or delete it'`).

### DeleteGarage(key) — SERVER, WAITS
Cars filed there move (one transaction) to the nearest other public garage (or the default one); online owners are notified; its bays are deleted. With no other garage the cars get none (offered at every garage). Same ownership rule as Update. A garage another **running** resource made is refused; one made in `/whip`, by a property, or by a stopped resource is open to anyone.

### SetVehicleGarage(vehicle, garageKey) — SERVER, WAITS
Re-files a car (impound release, dealer delivery). Use it for a car already stored (`DespawnVehicle{garage}` refuses those). Doesn't check access: ask `CanUseGarage` before filing into a private garage (WHIP evicts later if they can't use it). Errors: reference errors, `'garageKey required'`, `'No such garage'`, `'Vehicle not found'`, DB error.

### CanUseGarage(key, who) — SERVER
`true` for any public garage; private: owner and keyholders. `who`: server id or `{ charId }`. `false, why`: `'No such garage'`, `'That garage belongs to <label>'`, `'That garage is private'`, WhoIs errors.

```lua
local ok, why = exports.whip_core:CanUseGarage(garageKey, source)
if not ok then return false, why end
exports.whip_core:SetVehicleGarage(vehicleId, garageKey)
```

Impound pattern: `CreateGarage{ key = 'impound' }` once (or in `/whip`), `DespawnVehicle(id, { garage = 'impound' })` to seize an out car, `SetVehicleGarage(id, 'impound')` for a garaged one, `RemoveVehicleKey` to confirm keys, `SetVehicleGarage(id, homeKey)` to release.

## Events

Server events, for `AddEventHandler` (local; a client can't send them). Any server resource can fire them, so never fire them yourself, and before paying out on one check `GetInvokingResource() == 'whip_core'`. whip_core's own hooks run before the public event.

| Event | Payload | Fires when |
|---|---|---|
| `whip_core:vehicle:created` | `{ vehicleId, ownerCharId }` | any path mints an owned car |
| `whip_core:vehicle:ownerChanged` | `{ vehicleId, from, to }` | owner character changes |
| `whip_core:vehicle:deleted` | `{ vehicleId, ownerCharId, wasOut }` | an owned car stops existing: drop your per-car state |
| `whip_core:vehicle:dataChanged` | `{ vehicleId, key, value, old, cleared, resource }` | vehicle data set/removed by `resource` (`key` nil for a whip_core ClearAll) |
| `whip_core:vehicle:lockChanged` | `{ vehicleId, plate, locked, source }` | lock actually changed, by anything; `source` when a player did it |
| `whip_core:vehicle:spawned` | `{ vehicleId, entity, netId, plate, model, session, temp? }` | owned car comes out (also boot re-adoption) or temp car made (`session=true, temp=true`) |
| `whip_core:vehicle:despawned` | `{ vehicleId, netId }` | owned car leaves the world (record stays; next spawn gets a new netId) |
| `whip_core:vehicle:released` | `{ vehicleId, reason, temp }` | WHIP lets go of a street car or removes a temp car; id now meaningless |
| `whip_core:vehicle:registered` | `{ vehicleId, plate, model, session = true, source }` | WHIP takes on a street car (driven, lockpicked, pump, ResolveVehicle, AdoptVehicle); `source` = reporting player if any |
| `whip_core:vehicle:claimed` | `{ vehicleId, from, ownerCharId }` | session car became owned; `from` = old session id |
| `whip_core:vehicle:plateChanged` | `{ vehicleId, from, to }` | plate changed |
| `whip_core:vehicle:lockpicked` | `{ vehicleId, plate, source }` | a player lockpicked a car open |
| `whip_core:vehicle:entered` | `{ vehicleId, plate, source, seat, previousSeat? }` | player in a seat of a WHIP car; again on seat change (`previousSeat` set) |
| `whip_core:vehicle:exited` | `{ vehicleId, plate, source, seat, left? }` | left a seat; `left = 'logout'|'dropped'` when leaving the game |

`released` reasons: `'expired'` (despawnAfter), `'idle'`, `'gone'` (entity already gone), `'stopped'` (owning resource stopped), `'despawned'`, `'deleted'`, `'released'` (ReleaseTag), `'failed'` (SpawnTempVehicle key failed), plus `'claimed'` and `'not adopted'` in code.

Client events: `whip_core:vehicle:entered` / `:exited` `{ vehicleId, entity, plate, seat }`; `whip_core:vehicle:copied { entity, of }` (Experimental drive sync made a local copy of a networked car: dress it from `of`'s data).

```lua
AddEventHandler('whip_core:vehicle:lockpicked', function(d)
  if GetInvokingResource() ~= 'whip_core' then return end
  TriggerClientEvent('dispatch:alert', -1, 'Vehicle Break-In', GetEntityCoords(GetPlayerPed(d.source)))
end)
```

## SecureEvent 'vehicle' param

`params = { { 'vehicle', 'vehicle', opts? } }` resolves a client-sent **numeric** id (no references) and authorises it; the handler gets a `GetVehicle` snapshot (no occupants). Default: only the caller's own owned car (`'That is not your vehicle'`). `opts.session = true` also accepts session cars (street and temp). `opts.anyOwner = true` accepts anyone's owned car (pair with `near`). Unknown id: `'That vehicle is not there any more'`. `near = { at = 'vehicle', range = 8.0 }` measures to the car's current position (being seated in it counts as near).

```lua
Whip.core:SecureEvent('tow:hookVehicle', {
  rateLimit = 2000,
  params = { { 'vehicle', 'vehicle', { anyOwner = true, session = true } } },
  near = { at = 'vehicle', range = 8.0 },
}, function(source, player, v) print(v.model, v.plate) end)
```

## Config keys

| Key | Default | Meaning |
|---|---|---|
| `Config.VehicleLockRange` | 8.0 | L lock range on foot |
| `Config.UnlockOnExit` | true | getting out unlocks a locked WHIP car |
| `Config.NpcVehicleLockRange` | 10.0 | NPC traffic kept locked within this; 0 off |
| `Config.Seats.NoAutoShuffle` | true | no GTA seat shuffle |
| `Config.VehicleTrunkRange` | 2.5 | boot open gate = this + 3.0 m |
| `Config.VehicleStorageKeepRange` | 5.5 | move range for boot/glovebox |
| `Config.VehicleTrunkSlots` / `MaxWeight` | 40 / 200.0 | |
| `Config.VehicleGloveboxSlots` / `MaxWeight` | 10 / 20.0 | |
| `Config.MotorbikeGloveboxSlots` | 1 | |
| `Config.VehicleKeySlots` / `VehicleKeyMaxWeight` | 1 / 1.0 | ignition |
| `Config.VehicleStats` | `{ engine = ... }` | built-in stats (re-registered on /whip Settings change) |
| `Config.VehicleStatsTickInterval` | 1 | s, decay tick (min 0.25) |
| `Config.VehicleStatsSaveInterval` | 15 | s, car row unit write (min 1) |
| `Config.VehiclePositionSaveInterval` | 30 | s (min 5) |
| `Config.VehiclePositionEpsilon` | 2.0 | m moved before a write |
| `Config.VehicleDamage` | `{ remember = true, engineFloor = 100 }` | damage persistence |
| `Config.VehicleHud` | `{ speedUnit = 'mph', rpmMax = 8, redline = 0.87, rpmElectric = 20, idleRpm = 0.8, idleMeasured = false, rpmByClass = {...}, rpmByModel = {}, attitude = 'ball', flipBank = false, dashSkins = true }` | rev dial |
| `Config.VehicleFillers` | `{}` | `[GetHashKey(model)] = { side = 'left'|'right'|'rear' }` |
| `Config.VehiclePartPrompts`, `VehiclePartPromptScan` (15.0), `VehiclePartOpenAngle` (70.0), `VehiclePartHingeTopFrac` (0.52), `VehiclePartHinges`, `VehicleMakeLogos` | | part prompt geometry |
| `Config.BikeAutoHelmet` | false | |
| `Config.ExperimentalDriveSync` | false | recorded drives played on local copies |
| `Config.LogVehicleStorage` | false | log every storage open/refusal |
| `Config.GarageSpotRadius` | 3.5 | spot radius; store check +2 m |
| `Config.GarageSpotPromptHeight` | 1.22 | |
| `Config.GaragePositionHelper` | `{ enabled = true, showRange = 30.0, onFootRange = 10.0, length = 5.20, width = 2.60, zOffset = 0.02, alignDeg = 25.0, fadeMs = 180, requireStorable = false, idleReleaseMs = 60000 }` | bay outline (`/garagehelper` tunes live) |
| `Config.GarageWizardReach` | 250.0 | |
| `Config.Garages` | `{ legion_square = { name, pos, spawnPos, blipPos, blipSprite = 357, blipColor = 3, ... } }` | first-boot seed only |
| `Config.LockpickGame` | `'ring'` | lockpick minigame |

## Internal net events and limits (reference)

Client → server (SecureEvent; don't call from resources): `whip_core:server:garageSpotList` (500 ms), `garageSpotRetrieve` / `garageSpotStore` (2000 ms), `toggleVehicleLock` (500 ms), `toggleVehicleDoor` (250 ms, burst 4, doors 0-7, `'toggle'|'open'|'shut'`, 8 m, a locked WHIP car's doors won't open), `openVehicleStorage` (500 ms, burst 3), `closeVehicleStorage`, `checkIgnition` (500 ms), `attemptLockpick` (5000 ms), `attemptHackIgnition` (8000 ms), `registerSessionVehicle` (1000 ms, 20 m from the car), `vehicleSeat` (250 ms), `setVehicleEngine` (250 ms, burst 3), `reportStatBurn` (200 ms, burst 6), `reportStatLive` (150 ms, burst 6), `vehicleDamageReport` (1000 ms), `vehicleWrecked`, `syncVehicleProperties` (5000 ms, burst 3; dirt only), `vehicleModels` (once per account per run, <= 6000 names). Callbacks: `whip_core:resolveVehicle` (500 ms), `whip_core:seats:claim` (250 ms, burst 4).

## Gotchas

1. A bare number is always a vehicleId on both sides; pass `{ entity = veh }` for a handle. `SetVehicleProperties(veh, props)` with a raw handle (QBCore/ox habit) fails with a hint.
2. `ResolveVehicle` waits on the server: never in `canInteract`, labels, loops or per-frame; use `GetVehicleId` there.
3. `CreateOwnedVehicle` returning `false, err, true` means the car (and the payment in the same transaction) was saved: do not refund. Refund only on a plain `false`.
4. `CreateOwnedVehicle` without `opts.giveKey = true` gives no key; `data.x/y/z` are ignored; only `spawnAt` puts it out.
5. Ask `CanBringOutVehicleFor` before charging for a car with `spawnAt` (Isolate-world builders are refused).
6. `VehicleModelExists` returns `nil` (unknown) on a new server/build or a full list: test `== false`, not `not`.
7. `SpawnTempVehicle` `despawnAfter` removes the car even while driven; warn the driver. Temp cars also vanish when your resource restarts.
8. `GetVehicle(id).session == true` covers rentals too; use `.temp` to tell a `SpawnTempVehicle` car from street traffic (a tow job must not take a rental).
9. `TransferVehicle` doesn't revoke keys outside the seller's online pockets; use `ChangeVehicleLocks` + `GiveVehicleKey` for a clean sale.
10. `DespawnVehicle` on a street car hands it back to GTA (it stays in the world, its boot contents are lost). `DeleteVehicle` on a street car also leaves the entity: read the entity first and `DeleteEntity` it.
11. `DespawnVehicle(id, { garage = k })` refuses a car already stored (`'Vehicle is already stored'`): use `SetVehicleGarage`. It also refuses occupied cars by default with a garage.
12. `RetrieveVehicle` only marks the car out; call `SpawnVehicle` after it, or the car is "lost" (shows as recoverable at its garage bay).
13. Session ids reset on a clean restart; never persist a street/temp vehicleId in your own DB. Owned ids are stable.
14. Repairs must call `ClearVehicleDamage`, or the next spawn puts the damage back; it does not fix the entity.
15. `GetVehicleStat(id, name) > 0` is not "fitted": use `HasVehicleStat`. `ClearVehicleStat` (not set 0) removes a part.
16. `RegisterVehicleStat` before writing (`SetVehicleStat` refuses unregistered names). `clearAtMin` requires `default == min`. `consume` and `live` together are refused. `decay = 0` means no decay.
17. Stopping your resource drops your stat registrations, data listeners, watchers, handling layers, power asks, engine holds, temp cars, gauge rules and add-on catalog cars, but never stored stat values or vehicle data. Watchers' `onStop` is NOT called then: restore in `onResourceStop` too.
18. `OnVehicleStatChanged` callbacks must not yield (they run inside the write); positional argument order differs between server `(id, value, previous, cleared, source)`, client `(id, value, old, entity)` and data listeners (server `(id, value, cleared, old)`, client `(id, value, old, entity)`): prefer `{ table = true }`.
19. Vehicle data is readable by every client near the car: no secrets. 32 keys per resource per car, 8 KB block, first writer owns a key.
20. Handling: never write `SetVehicleHandling*` or `SetVehicleCheatPowerIncrease` directly; use layers / `SetVehiclePower`. Only one car per client is tuned at a time.
21. Client natives that change a car (`SetVehicleProperties`, `SetVehicleExtras`) need network control (`TakeVehicleControl`), which is refused while another player drives.
22. Previews replicate to everyone: always `RestoreVehicleAppearance` after an abandoned preview and release `HoldVehicleAppearance` on close/death.
23. Client `GetVehicle(...).plate` / `GetVehicleProperties().plate` are the raw padded entity text; compare plates without spaces. `SetVehicleProperties` applies `props.plate` to the entity if present.
24. `HoldVehicleEngine` family takes a numeric vehicleId only, not a reference.
25. A garage key is permanent and a garage another running resource created can only be changed/deleted by that resource.
26. Events like `whip_core:vehicle:lockpicked` can be fired by any server resource: check `GetInvokingResource() == 'whip_core'` before rewarding.
27. Locking a car closes anyone's open boot; a locked car's boot can only be opened by `OpenStore(..., { skipAccess = true })`.
28. Lock state persists across restarts (except a locked car with its own key in the ignition, which comes back unlocked); a car leaving a garage is locked unless its key is in the ignition.

## Docs vs code

- `types/server.lua:1642` (SetVehicleLocked stub) says every car is unlocked at server start; code saves `locked` and restores it (`whip_core/server/vehicles.lua:448-507`). Docs are right; the stub is stale.
- `released` reasons: docs list 8; code also emits `'claimed'` (`server/vehicle_claim.lua:191`) and `'not adopted'` (`server/vehicles.lua:3346`).
- Docs say every vehicle export takes a reference; `HoldVehicleEngine`, `ReleaseVehicleEngine`, `GetVehicleEngineHold` do `tonumber(vehicleId)` only (`server/vehicle_stats.lua:1564,1581,1598`).
- `SpawnTempVehicle` has an undocumented `bucket` option (routing bucket from birth) (`server/vehicles.lua:4381-4385`, `types/classes.lua:499`).
- `SetVehicleGarage` is documented for stored cars but does not check state: it re-files an `out` car too, and on a session car "succeeds" without saving (`server/garages.lua:793-803`).
- `CreateGarage` docs: spawn "default the marker"; the row keeps spawnX/Y/Z = 0 and only the first bay is placed at the marker (`server/garages.lua:28-39`, `server/garage_spots.lua:89-92`).
- Guide lists `doorsOff` bits 0-5; the mask covers doors 0-7 (`server/vehicle_damage.lua:33`, `client/vehicle_damage.lua:17`).
- `GetVehicleCatalog` `class` is the GTA class number, not the class name the docs list for `RegisterVehicles` (`server/vehicle_catalog.lua:275`).
- Client `GetNearbyVehicles().model` is the lower-cased display name, not the spawn name (`client/vehicles.lua:2993`).
- `SetVehicleAppearance` returns lower-case `'vehicle not found'` unlike other exports (`server/vehicles.lua:4757`); vehicle data uses `'no such vehicle'` for an unknown numeric id (`server/vehicle_data.lua:264`).
- `whip_core:vehicle:entered` / `:exited` (server payloads with `previousSeat` / `left`) are not in the guide's event table (`types/events.lua:501-508`, `server/events_vehicles.lua:343-395`).
