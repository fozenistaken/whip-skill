# World: zones, time & weather, NPCs, blips

Zones (client, server, saved/EnsureZone, rules, tracking events, the Zone Editor), the world clock and weather with per-player layers, server-managed NPCs (SpawnNpc and the brain), and server blips/waypoints. Built from doc anchors `#guide-zones` (057), `#server-zones` (058), `#client-zones` (059), `#guide-timeweather` (060), `#timeweather` / `#client-timeweather` (061), `#npcs` (062), and source `whip_core/server/zones.lua`, `client/zones.lua`, `tools/zones.lua`, `shared/shapes.lua`, `server/time.lua`, `client/time.lua`, `server/clock.lua`, `server/npcs.lua`, `client/npcs.lua`, `server/actors.lua`, `server/blips.lua`, `client/blips.lua`, `server/audience.lua`, `config.lua`, `types/server.lua`, `types/client.lua`, `types/classes.lua`, `types/events.lua`.

## Contents
- Zones: concepts
- Zone shapes and fields
- Zone rules
- Zone events (client and server)
- Client zone exports
- Server zone exports
- Saved zones: EnsureZone / DeleteZone
- Zone Editor (admins)
- Time & weather: concepts and config
- Time & weather server exports
- Weather layers (server and client)
- Client time & weather exports
- Time events
- NPCs: concepts
- SpawnNpc / DespawnNpc / SetNpcState / GetNpc / GetNpcs — SERVER
- NPC events
- Blips and waypoints: ShowBlip / HideBlip / SetPlayerWaypoint — SERVER
- Audiences
- GetVehicleDriver — SERVER
- Server clock (internal)
- Gotchas
- Docs vs code

## Zones: concepts

- A zone is a box, sphere or poly that knows when players enter/leave and can enforce `rules` with no code of yours.
- Three kinds:
  - **Client zones** — `RegisterZone(data)` on the client. Polled locally every `Config.ZonePollInterval` (300 ms). Also reported up to the server (if the id is letters/digits/`_`/`-`, ≤ 60) as a "mirror": the server keeps the shape most reporters agree on (one modified client is outvoted, but a zone only one player has is whatever they say). Max 500 reported zones per player, polys max 256 points.
  - **Server zones** — `RegisterZone(id, data)` on the server. Authoritative, not visible to clients, no tick unless `trackPlayers = true`. Owned by your resource (one server-wide id list), removed when it stops or by `ReleaseTag(data.tag)`.
  - **Saved zones** — `EnsureZone(key, data)` on the server or drawn in the Zone Editor. Stored in the DB table `zones`, synced to every client (they become client zones owned by whip_core), id `'dbzone_<n>'`, looked up everywhere by their `key`. Use a saved zone for anything every player shares or the server must trust (`require = { zone = 'mrpd' }` on an `AddPoint` requires a saved zone).
- Every lookup export takes an id or a saved zone's key; a saved zone wins a name over a client zone with the same id (server and client both resolve saved first).
- The client poll only considers zones within `Config.ZoneCheckRange` (200 m) via a `Config.ZoneCellSize` (50 m) grid.
- Containment: sphere = 3D distance; box = `pos` is the CENTRE including height (`pos.z ± size.z/2`), rotated by `heading` degrees; poly = winding-number test on `points` between `minZ`..`maxZ` (each point may carry its own `minZ`/`maxZ`; the effective range is the widest). A poly with no `minZ`/`maxZ` is unbounded vertically.

## Zone shapes and fields

| Field | Type | Applies | Notes |
|---|---|---|---|
| `type` | `'box'` \| `'sphere'` \| `'poly'` | all | Required |
| `pos` | vector3 | box, sphere (poly: centroid computed) | Centre |
| `size` | vector3 | box | Width (X), length (Y), height (Z). Client default `vector3(10, 10, 5)`; server: each side > 0 and ≤ 4000 |
| `heading` | number | box | Degrees, default 0 |
| `radius` | number | sphere | Client default 10.0; server: > 0 and ≤ 2000 |
| `points` | vec2[] / `{x,y[,minZ,maxZ]}`[] | poly | 3+ points (server ≤ 256). `p.x`/`p.y` or `p[1]`/`p[2]` |
| `minZ`, `maxZ` | number | poly | Height band |
| `id` | string | client | Yours; same id again replaces (only your own). Omitted: `auto_<owner>_<hash>` from type, group, label, first position. For the server to learn it: `^[%w_-]+$`, ≤ 60 |
| `label` | string | all | Shown on enter/exit notices; defaults to id |
| `group` | string | all | For `RemoveZoneGroup` / filtering |
| `priority` | number | client, saved | Default 0. Overlapping zones all apply; priority settles only the speed limit, the weather layer and callback order (enters highest first, exits lowest first) |
| `rules` | table | client, saved | See Zone rules |
| `notify` | boolean | client, saved | On-screen "Entered <label>" (info, 2 s) / "Left <label>" (warning, 2 s). Default false. Events fire either way |
| `weather` | string \| layer table | client | Pushes layer `zone:<id>` on enter, pops on exit (see Weather layers) |
| `onEnter(zone)`, `onExit(zone)` | function | client | Called with the zone's internal table |
| `inside(zone)` | function | client | Every poll (300 ms) while inside |
| `condition()` | function → boolean | client | While it returns false/errors the player counts as outside (no rules, no events) |
| `trackVehicles` | boolean | client, saved | Vehicle enter/exit detection (see below); defaults on when `onVehicleEnter`/`onVehicleExit` is given |
| `onVehicleEnter(entity, plate, zone)`, `onVehicleExit(entity, plate, zone)` | function | client | Every vehicle in the pool tested every `Config.ZoneVehiclePollInterval` (2000 ms), only while a zone has `trackVehicles` and a vehicle callback |
| `debug` | boolean | client | Draws the outline every frame; dev only |
| `trackPlayers` | boolean | server, saved | Server sweep + server events |
| `tag` | string | server `RegisterZone` | Run tag |

Callbacks that throw are reported once per zone per callback; the poll keeps running.

## Zone rules

Framework-enforced while the player is inside (only while `condition` passes).

| Rule | Type | Inside the zone |
|---|---|---|
| `noWeapons` | bool | `RemoveAllPedWeapons` on entry; re-equipping blocked |
| `noPvP` | bool | Player invincible (ped hold `zoneNoPvP`), and can't fire or melee |
| `noMelee` | bool | No punching/melee |
| `disableFiring` | bool | No firing; carrying is fine |
| `speedLimit` | number (km/h) | Vehicle max speed capped (`SetVehicleMaxSpeed(limit/3.6)`); highest-priority zone that sets one wins, ties take the lower limit; restored on leaving |
| `noVehicles` | bool | Player is made to leave the vehicle |
| `heal`, `healRate` | bool, number | +`healRate` HP (default 2) every 300 ms up to 200 health. Each heal zone adds separately |
| `noWantedLevel` | bool | Wanted level cleared continuously |
| `noCollision` | bool | No collision with other players' peds |
| `noFallDamage` | bool | Collision-proof ped: no fall damage, and crashes/being run over do no damage either |
| `jobWhitelist` | string[] | Job keys allowed |
| `aceWhitelist` | string | ACE required (asked of the server; up to 3 attempts; no answer = allowed) |
| `charWhitelist` | number[] | charIds allowed |
| `ejectUnauthorized` | bool | With any whitelist: unauthorised players are told "You are not authorized in this area" and teleported to the nearest point outside (searched in 15° steps, 5–100 m) |
| `enterNotify`, `exitNotify` | string | Custom notice text when `notify = true` |

Whitelists do nothing on their own: meeting any one is enough, and they only act with `ejectUnauthorized`. Rules are enforced every 250 ms (1000 ms when none apply) plus a per-frame control block.

```lua
-- Client, in Whip.register
exports.whip_core:RegisterZone({
  type = 'box', id = 'myres_station', pos = vec3(440, -980, 30), size = vec3(20, 20, 10),
  label = 'Police Station', group = 'police', notify = true,
  rules = { noPvP = true, noWeapons = true, heal = true },
  onEnter = function(zone) end, onExit = function(zone) end,
})
```

## Zone events (client and server)

Client (local event, any client resource hears the local player cross any zone, including saved zones):
- `whip_core:zone:entered` / `whip_core:zone:exited` — `{ zoneId, key?, label, group }` (`key` set for saved zones).

Server (local server events, only for zones with `trackPlayers = true`, server or saved — never client mirrors), swept every `Config.ZoneTrackInterval` ms (1000):
- `whip_core:zone:entered` — `{ zoneId, key?, source }`
- `whip_core:zone:exited` — `{ zoneId, key?, source, dropped?, removed? }`: `dropped = true` (left the server inside it), `removed = true` (the zone went or stopped tracking).
- A player in the character creator or logging out is in no zone; routing buckets are ignored (a zone is a place).
- Any server resource can fire these events; for anything that pays out, re-check with `IsPointInZone(id, coords, true)`.

```lua
AddEventHandler('whip_core:zone:entered', function(e)
  if e.key == 'mrpd' then --[[ server: e.source ]] end
end)
```

## Client zone exports

### RegisterZone(data) — CLIENT
Makes a zone (fields above). Same `id` again replaces it (rules of the old one are reverted, no fake exit/enter). Returns: zone id `string`, or `false, why` (`"RegisterZone needs { type = 'box', pos, size }, { type = 'sphere', pos, radius } or { type = 'poly', points }"`, `'zone "x" belongs to <resource>'`). An id the server can't take prints a console line once; the zone still works locally.

```lua
local id = exports.whip_core:RegisterZone({ type = 'sphere', pos = vec3(200, -800, 30), radius = 8.0,
  onEnter = function(zone) end })
```

### RemoveZone(id) — CLIENT
Deletes one of your zones (another resource's refused), firing `onExit` if the player was inside. Returns `true` or `false, why`.

### RemoveZoneGroup(group) — CLIENT
Deletes all YOUR zones in a group. Returns `true, count` or `false, 'a group name is required'`.

### UpdateZone(idOrKey, patch) — CLIENT
Changes one of your zones, only the keys given; validated before anything is applied (a bad key changes nothing). Keys, applied in this order: `pos` (vector3; a poly's points move with it), `size` (box: vector3; sphere: radius number or a vector whose x is the radius; poly refused: resize by points), `condition` (function, or `false` to remove), `debug`, `trackVehicles`, `label`, `priority`, `notify`, `rules` (replaces the whole table; `false` = none; to turn one rule off send the rules without it). Not patchable: `weather`, `group`, `points`, callbacks.
Returns `true`, or `false, why` (`'no zone "x"'`, `'zone "x" belongs to …'`, `'UpdateZone: no key "x" (pos, size, condition, debug, trackVehicles, label, priority, notify, rules)'`, `'a poly zone is resized by editing its points'`, `"UpdateZone: a box zone's size is a vector3"`, `"UpdateZone: a sphere zone's size is its radius (a number)"`).

```lua
exports.whip_core:UpdateZone('myres_station', { label = 'Closed', rules = { noWeapons = true } })
```

### IsPointInZone(id, point) — CLIENT
Instant maths, no polling. `id` = zone id or saved key. Returns `boolean` (`false` for unknown zone or nil point).

### IsInZone(id) — CLIENT
Whether the local player was inside at the last poll. Returns `boolean`.

### GetZonesInside() — CLIENT
Every zone id the local player is inside (saved zones as `'dbzone_<n>'`). Returns `string[]`.

### GetZonesNearby(pos, radius?) — CLIENT
Zones whose `pos` is within `radius` (default 50) on the XY plane, nearest first. Returns `{ id, type, label, pos, dist }[]`.

### GetZone(id) — CLIENT
Returns `{ id, type, pos, size, radius, heading, points, minZ, maxZ, group, label, priority, rules, notify, debug, inside, hasCondition }` or `nil`. The condition function itself is never returned.

## Server zone exports

### RegisterZone(id, data) — SERVER
NOTE the signature differs from the client's: id first. Registers a server-side zone for checks; no tick unless `data.trackPlayers`. `data`: `type, pos, size, heading, radius, points, minZ, maxZ, group (≤ 60), label (≤ 80), trackPlayers, tag`. No `rules`, `notify`, `priority` or callbacks on server zones. Shape validated: sphere needs `pos` + `radius` (0 < r ≤ 2000), box `pos` + `size` (each 0 < s ≤ 4000), poly 3–256 `points`; pos within ±16000 (z ±5000); `maxZ` ≥ `minZ`. Same owner registering again re-applies the geometry; another resource's id is refused. Removed when your resource stops or `ReleaseTag(tag)` (released last in a run).
Returns `true`, or `false, reason` (`"the server's RegisterZone takes (id, data): an id of your own first, then the zone"`, `'RegisterZone: data must be a table'`, `'RegisterZone "x": radius is a number of metres, above 0 and at most 2000'`, ...).

### RemoveZone(id) — SERVER
Removes one of YOUR server zones (a client zone of the same id is separate and stays). Returns `true` or `false, reason`.

### IsPointInZone(id, point, trusted?) — SERVER
`id` = zone id or saved key; `point` vector3/table. Without `trusted`, a client-mirrored zone counts as its players report it. `trusted = true`: only saved zones and `RegisterZone` zones answer; a client-made zone is `false` — use for anti-cheat. Returns `boolean`.

```lua
if not exports.whip_core:IsPointInZone('mrpd', GetEntityCoords(GetPlayerPed(source)), true) then
  return false, 'You need to be at the station'
end
```

### GetPlayersInZone(id) — SERVER
Server ids of every player inside, testing every player each call (use `trackPlayers` to react to entering/leaving). Excludes players in the creator or logging out; buckets ignored. Returns `number[]`.

### GetVehiclesInZone(id) — SERVER
Returns `{ vehicleId, entity }[]`; `vehicleId` is `nil` for a car WHIP doesn't track.

### GetZones() — SERVER
Every zone the server knows (server zones, client mirrors and saved zones) as a LIST (`GetZones()[id]` is always nil; use `GetZone`). Returns `table[]`.

### GetZone(id) — SERVER
One zone's definition by id or saved key. Returns `table|nil` (saved zones carry `id = 'dbzone_<n>'`, `zoneId`, `key`, `dbZone = true`, `metadata`, shape fields).

## Saved zones: EnsureZone / DeleteZone

### EnsureZone(key, data) — SERVER, WAITS
A saved zone declared by your key; call it in `Whip.register` so it runs at every start. Waits for whip_core to finish starting. Made once; updated only when your declaration CHANGES (each zone remembers its last declaration in `metadata.ensured = { by, decl }`, numbers rounded to the millimetre), so an admin's Zone Editor edits stand until you change your code. A different `type` deletes the old row and makes a new zone under the same key (new `'dbzone_<n>'`: always look it up by key). Optional fields you drop from the declaration are cleared.

| Param | Type | Description |
|---|---|---|
| `key` | string | `^[%w_%-%.:]+$`, ≤ 60. Refused if another RUNNING resource declared it; a stopped resource's or an editor-made key is taken over |
| `data` | table | `type`, `pos`, `size` + `heading` (box), `radius` (sphere), `points` (poly, 3+, may carry per-point `minZ`/`maxZ`), `minZ`, `maxZ`, `label` (default key), `group`, `priority`, `rules`, `notify`, `trackVehicles`, `trackPlayers` |

Returns: the `zone` table, or `false, reason` (`'a zone key is letters, digits, _ - . and :, at most 60'`, `'zone "x" is declared by <res>'`, `"type is 'box', 'sphere' or 'poly'"`, `'a poly needs at least 3 points'`, `'a box needs size'`, `'a sphere needs a radius'`, `'the zone could not be saved'`, not-ready). Refusals are also printed. New/changed zones are pushed to every connected client at once (`whip_core:client:zoneDbCreated` / `zoneDbUpdated`).

```lua
Whip.register(function()
  Whip.core:EnsureZone('mrpd', { type = 'box', pos = vector3(441.0, -982.0, 30.7),
    size = vector3(60, 50, 20), heading = 0, label = 'Mission Row PD', trackPlayers = true })
end)
```

DB table `zones`: `zoneId` (PK), `key` (unique, VARCHAR 60), `label`, `type` ENUM, `groupName`, `priority` TINYINT, `x,y,z`, `sizeX/Y/Z`, `heading`, `radius`, `points` JSON, `minZ`, `maxZ`, `metadata` JSON (rules, notify, trackVehicles, trackPlayers, ensured), `createdAt`, `createdBy`.

### DeleteZone(keyOrId) — SERVER, WAITS
Deletes a saved zone for everyone. Refused for a zone a running resource declares (it would be made again; `'zone "x" is declared by <res>'`), and for a server zone (`'not a saved zone — RemoveZone removes your own server zones'`). `'Zone not found'`, `'Database error — the zone was not deleted'`. Returns `true` or `false, reason`.

## Zone Editor (admins)

`/whip` → World → Zones → Open the editor: free camera. `1` / `2` / `3` draw a box, sphere, poly; scroll sizes it. Room scanner: inside a room press `H` and fly, WHIP traces the walls (smoothing doorways/windows; Douglas-Peucker simplified); `H` previews, scroll sets height, `G` confirms. Vertex editor: `4` (`ze_vertex_mode`) moves a poly's points, `5` (`ze_height_mode`) sets each point's own height (`E` grabs, `G` confirms, `Esc` reverts) — one zone can cover a garage lower than the house. The manager lists all zones (teleport, toggle debug, delete saved zones). Editor zones are saved zones.

## Time & weather: concepts and config

- The server keeps one clock and one weather for everyone; every client follows it (clients re-anchor on `whip_core:client:timeSync`, broadcast every `Config.TimeSyncInterval` (60000 ms) and on every change; between syncs each client ticks its own clock once a second).
- Time, weather, freeze, blackout and time scale are saved in DB table `whip_world` (one row: `gameMinutes`, `weather`, `frozen`, `blackout`, `timeScale`) on every set, every 5 minutes while not frozen, and on stop. A new server starts from `Config.StartTime`.
- GTA speed: scale 1.0 = 30 game seconds per real second (48 real minutes = 24 game hours).
- Weather is applied instantly on clients (`SetWeatherTypeNowPersist` + `SetOverrideWeather`), no transition.

```lua
Config.TimeScale    = 1.0
Config.StartTime    = { hour = 12, minute = 0 }
Config.StartWeather = 'CLEAR'
Config.WeatherTypes = { 'CLEAR', 'EXTRASUNNY', 'CLOUDS', 'OVERCAST', 'RAIN', 'CLEARING', 'THUNDER',
  'SMOG', 'FOGGY', 'XMAS', 'SNOWLIGHT', 'BLIZZARD', 'HALLOWEEN', 'NEUTRAL' }
Config.TimeSyncInterval = 60000
```

`Config.WeatherTypes` is the whitelist for `SetWeather` and layers (case-insensitive; changeable in `/whip` → Settings). Changing `Config.TimeScale` in `/whip` → Settings applies to the running clock immediately. Admins: `/whip` → World → Time & Weather (time or Dawn/Noon/Sunset/Midnight, weather, freeze, blackout, time scale 0–10), applies server-wide at once.

## Time & weather server exports

### GetTime() — SERVER
Server time exact at call. Returns `hour, minute` (numbers).

### GetWeather() — SERVER
Returns the weather `string`, upper case.

### GetTimeScale() — SERVER
Returns `number`.

### IsTimeFrozen() — SERVER
Returns `boolean`.

### IsBlackout() — SERVER
Returns `boolean`.

### SetTime(hour, minute?) — SERVER, WAITS
Sets the time, broadcasts, saves, fires `whip_core:time:changed { hour, minute }`. Each value wraps on its own (`hour % 24`, `minute % 60`: 25:61 → 01:01; minutes do not carry into hours). `minute` default 0. Waits for whip_core to be ready.
Returns `true`, or `false, reason` (`'hour must be a number'`, `'minute must be a number'`).

### SetWeather(weather) — SERVER, WAITS
One of `Config.WeatherTypes`, any case. Fires `whip_core:weather:changed { weather }`.
Returns `true`, or `false, reason` (`'Invalid weather type'`, `'weather must be a weather type name'`).

### SetTimeFrozen(frozen) — SERVER, WAITS
Freezes/unfreezes for everyone (re-anchors so no jump). Fires `whip_core:time:freezeChanged { frozen }` (also on unfreeze). Returns `true`.

### SetBlackout(blackout) — SERVER, WAITS
Turns every artificial light off/on. No event. Returns `true`.

### SetTimeScale(scale) — SERVER, WAITS
`1.0` normal, `2.0` twice as fast; clamped 0.0–10.0; re-anchored and broadcast at once. No event.
Returns `true`, or `false, 'scale must be a number (0 to 10)'` (not read as 1.0).

## Weather layers (server and client)

A layer is a named change to what ONE player sees; layers stack. Each field resolves independently: the highest-`priority` layer that sets it (ties: by name, ascending) wins, else the server's value. Each source clears only its own layer, so what was under it comes back. A layer is owned by the resource that set it: another resource can't replace or clear it (whip_core can), and it comes off when the owner stops.

| Field | Type | Meaning |
|---|---|---|
| `priority` | number | Higher wins. Default 0 |
| `weather` | string | From `Config.WeatherTypes` (upper-cased) |
| `hour`, `minute` | number | Where the clock starts (`% 24`, `% 60`); it runs unless `frozen` |
| `frozen` | boolean | Holds the clock |
| `blackout` | boolean | City lights off |

- `frozen = false` / `blackout = false` is an opinion ("not frozen") that overrides lower layers; leaving it out means "no opinion". Never build layers with `x and y or nil`.
- Zone layers: a client zone with `weather = 'FOGGY'` (or a layer table `{ weather = 'FOGGY', hour = 3 }`) pushes layer `zone:<zoneId>` on enter and pops it on exit; its priority defaults to `10 + zone.priority`.
- Server layers reach the client named `'server:' .. name`, so they never collide with client layers.

### SetPlayerWeatherLayer(source, name, opts) — SERVER
Pushes (or with `opts = nil` clears) a layer on one player. `name` ≤ 64 chars. `opts`: only `priority, hour, minute, weather, frozen, blackout` are read (others ignored); numbers must be numbers, weather valid.
Returns `true`, or `false, reason` (`'a layer needs a name (at most 64 characters)'`, `'no such player'`, `'layer "x" belongs to <res>'`, `'opts must be a table, or nil to clear'`, `'priority must be a number'`, `'hour must be a number'`, `'Invalid weather type'`).

```lua
exports.whip_core:SetPlayerWeatherLayer(source, 'nightclub',
  { hour = 1, minute = 0, weather = 'CLEAR', frozen = true, priority = 50 })
exports.whip_core:ClearPlayerWeatherLayer(source, 'nightclub')
```

### ClearPlayerWeatherLayer(source, name) — SERVER
Removes one of your layers from one player. Returns `true`, or `false, reason` (also `true` when there was nothing to clear).

### GetPlayerWeatherLayers(source) — SERVER
Layers the SERVER pushed to this player (not the client's own, e.g. zone layers; the client's `GetWeatherLayers` has the full picture). Returns `{ [name] = opts }`.

### SetWeatherLayer(name, opts) — CLIENT
Adds/replaces a layer on this client only (no round trip); `opts = nil` removes it. Returns `true`, or `false, why` (`'a layer needs a name'`, `'Invalid weather type'`, `'layer "x" belongs to …'`, `'there is no layer "x"'` when clearing a missing one, `'priority must be a number'`...).

```lua
exports.whip_core:SetWeatherLayer('zone:swamp', { weather = 'FOGGY', priority = 10 })
```

### ClearWeatherLayer(name) — CLIENT
Removes one of your layers. Returns `true`, or `false, why` (none, or another resource's).

### GetWeatherLayers() — CLIENT
For debugging a stack. Returns `{ layers = { { name, priority } } (highest first), owners = { hour, minute, weather, frozen, blackout = '<layer name>' | 'server' } }`.

## Client time & weather exports

### GetTime() — CLIENT
What the local player sees, layers included. Returns `hour, minute` (floored).

### GetWeather() — CLIENT
Resolved weather. Returns `string`.

### IsTimeFrozen() — CLIENT
Frozen for this player by the server or a layer. Returns `boolean`.

### IsTimeOverridden() — CLIENT
Whether any layer is active (`GetWeatherLayers` says which). Returns `boolean`.

## Time events

- Server: `whip_core:time:changed { hour, minute }`, `whip_core:time:freezeChanged { frozen }`, `whip_core:weather:changed { weather }`.
- Client: `whip_core:weather:layerChanged { name, layer }` (`layer` nil when removed).

## NPCs: concepts

- NPCs the server makes and looks after (guards, hostages, targets, quest givers). The server creates a networked mission ped (`CreatePed`, orphan mode 2) and keeps its "brain" (behaviour, targets, task, weapon, conditions). Whichever player's game owns the ped runs its AI; the brain is re-sent to every new owner (each second until acked), when targets change, and when its task ended while alive (at most every 2 s and 10×/min). So it never wanders off when ownership changes.
- The ped exists at once; the first nearby player's game takes it over within about half a second.
- Who it fights: its `hostileTo` audience plus anyone who attacked it in the last minute (`fightBack`), never a downed player. Focus changes only when there is none, the focus is no longer a target, or after 5 s.
- Guard `range`: hostileTo counts only within that distance of its post; an attacker is chased up to 3× the range; out of range it walks back.
- `group`: hurt one (even with one fatal shot) and every NPC of yours in the same group fights the attacker.
- `interior = true`: each owning game keeps it frozen until that game has the MLO loaded (a ped otherwise falls through).
- Health/damage/death come from the server's own reads; the killer is the server's reading (a car's driver for a run-over), waiting up to 1 s after the owner reports a death.
- Removal: the owner is asked to delete it; the server deletes it only if no game holds it, or after 3 s.
- Yours: removed when your resource stops or by `ReleaseTag(opts.tag)` (a released tag refuses new NPCs).
- Debug: `/npcdebug` shows an NPC's record (owner, step, applied).

## SpawnNpc / DespawnNpc / SetNpcState / GetNpc / GetNpcs — SERVER

### SpawnNpc(def, opts?) — SERVER
Never waits.

| def | Type | Description |
|---|---|---|
| `model` | string | Ped model name `^[%w_]+$`, ≤ 64 (ignored when `look` is given) |
| `coords` | vector3 \| vector4 \| `{ x, y, z, heading? }` | Spawn point = its post; `w`/`heading` faces it |
| `behaviour` | `'stand'` \| `'guard'` | `'stand'` (default) stays put; `'guard'` wanders near its spot. Both walk back after a fight |
| `conditions` | table? | `{ invincible = false, canMove = true, reacts = false, flees = false }` (defaults shown). `flees` (run instead of fight) needs `reacts = true`. `canMove = false` freezes it |
| `weapon` | string \| `{ name, ammo? }` | Must match `^WEAPON_[A-Z0-9_]+$` (GTA's or a streamed add-on with that prefix), ≤ 64; `ammo` default 250, clamped 0–9999 |
| `armour` | number? | 0–100 (clamped) |
| `look` | table? | A character-editor appearance, checked like a character save, ≤ 10,000 bytes of JSON; the ped becomes the look's freemode model |
| `outfit` | table? | Flat component table (`c<0-11>d`/`c<n>t`, props `p<0,1,2,6,7>d`/`t`, values ≤ 999, prop drawable −1 allowed); not used with `look` (undocumented) |
| `interior` | boolean? | Stands inside an MLO: frozen until the interior loads on its owner's game |
| `gateAt` | coords? | Where to look for that MLO, if not at its spot |

| opts | Type | Description |
|---|---|---|
| `tag` | string? | Run tag |
| `hostileTo` | audience? | `{ people = { serverId \| { charId = n } } }` (≤ 64): fights the nearest of them online and not down. `{ except = { ... } }`: everyone else, only with `range`. Never `'everyone'` or a job |
| `fightBack` | boolean? | Default `true`: fights its attacker until they go down or a minute after their last hit |
| `corpseMs` | number? | Body stays (default 60000; `0` = until removed) |
| `range` | number? | 1–500 m (see concepts). Left out: anywhere |
| `group` | string? | ≤ 128 chars; group defence |
| `bucket` | integer? | Routing bucket set at birth (default 0) (types only, not in docs) |

Returns `npcId, netId`, or `false, reason` (`'an NPC needs a definition table'`, `'model is a ped model name, like s_m_y_dealer_01'`, `'coords must be a vector3/vector4 or { x, y, z, heading }'`, `"behaviour is 'stand' or 'guard'"`, `'conditions.x is true or false'`, `'weapon is a GTA weapon name, like WEAPON_PISTOL'`, `'look: …'`, `'range is 1-500 metres'`, `'an NPC that fights everyone but some needs a range (metres round its post)'`, `"'everyone' is not allowed here: name the people"`, `'group is a name, up to 128 characters'`, `'bucket is a routing bucket, a whole number 0 or more'`, `'the ped could not be made (is the model right?)'`, a closed tag).

```lua
local npcId, netId = exports.whip_core:SpawnNpc({
  model = 's_m_y_dealer_01', coords = vector4(x, y, z, heading),
  behaviour = 'guard', weapon = 'WEAPON_PISTOL',
}, { tag = 'run:42', hostileTo = { people = { source } } })
```

Pair with `AddPoint({ at = { netId = netId }, talk = true, ... })` for a Talk prompt and `StartConversation` for dialog (see interactions.md).

### DespawnNpc(npcId) — SERVER
Removes one of your NPCs (owner's game deletes the ped). Returns `true` or `false, reason` (`'an npcId is a number'`, `'no such NPC of yours'`).

### SetNpcState(npcId, patch) — SERVER
Changes what one of your NPCs does; whichever game runs it next carries on.

| patch | Type | Description |
|---|---|---|
| `behaviour` | `'stand'` \| `'guard'` | |
| `hostileTo` | audience \| `false` | `false` calms it and forgets its attackers |
| `fightBack` | boolean | |
| `conditions` | table | Merged over current conditions |
| `range` | number \| `false` | `false`: anywhere again |
| `post` | coords | New spot to walk to and stand/guard at (ends a patrol) |
| `interior` | boolean | The new post is inside an MLO |
| `gateAt` | coords | Where to look for that MLO, if not at the post |
| `pace` | `'walk'` (default) \| `'run'` | |
| `follow` | serverId \| `false` | Walks after that loaded player, waiting while they're gone or down. `false` stops: set `post` too or it walks back |
| `flee` | serverId \| `false` | Runs from that player, fighting nobody |
| `anim` | `{ dict, clip }` \| `{ scenario }` \| `false` | Looped where it stands (scenario `^[%w_]+$` ≤ 64) |
| `attack` | `{ net = netId }` \| `{ at = coords }` \| `false` | What it attacks while it has nobody to fight: a car (leaves it burnt out) or a point (a prop); shoots, or walks up without a weapon |
| `ride` | `{ net, seat = -1..14 }` \| `false` | Sits in that car's seat, re-seated by every new owner (undocumented) |
| `style` | `{ accuracy 0-100, rate 10-100, pattern = 'single shots'\|'bursts'\|'full auto', skill = 'a rookie'\|'a pro'\|'a killer' }` \| `false` | How it fights (undocumented, Director) |

Returns `true` or `false, reason` (`'no such NPC of yours'`, `"pace is 'walk' or 'run'"`, `"follow is a loaded player's server id, or false"`, `'post must be a vector3/vector4 or { x, y, z, heading }'`, ...).

```lua
exports.whip_core:SetNpcState(npcId, { hostileTo = { people = { source } } })   -- the alarm tripped
exports.whip_core:SetNpcState(hostageId, { follow = source, pace = 'run' })    -- the rescue
```

### GetNpc(ref) — SERVER
`ref` = npcId, `{ id = }`, or `{ entity = }` / `{ netId = }` (found only while that is still the NPC's ped). Any resource's NPC. Returns a copy or `nil`:
`{ npcId, owner, tag, model, netId, lore, look, alive, health, armour, behaviour, conditions, targets (server ids), focus, range, group, killer, killedAt (GetGameTimer), weapon (hash that killed it), coords, post = { x, y, z, heading }, pace, follow, flee, interior, tasks = { i, n }|nil, patrols }`.

### GetNpcs(filter?) — SERVER
`filter = { tag? }`. Your NPCs (or one of your tags), sorted by id. Returns `table[]` of the same shape.

## NPC events

Server local events (`types/events.lua:389`):
- `whip_core:npc:spawned { npcId, tag, owner, netId, model, coords }`
- `whip_core:npc:despawned { npcId, tag, owner, reason }` — `'removed'`, `'stopped'`, `'released'`, `'lost'`, `'corpse'`
- `whip_core:npc:damaged { npcId, tag, owner, amount, health, armour, attacker, group }` — attacker server id or nil
- `whip_core:npc:killed { npcId, tag, owner, killer, weapon, coords }` — killer server id or nil

Any server resource can fire these: confirm with `GetNpc` before paying.

```lua
local paid = {}
AddEventHandler('whip_core:npc:killed', function(e)
  local npc = exports.whip_core:GetNpc(e.npcId)
  if not npc or npc.owner ~= GetCurrentResourceName() or paid[npc.npcId] then return end
  if not npc.alive and npc.killer then
    paid[npc.npcId] = true
    exports.whip_core:PayPlayer(npc.killer, 500, { reason = 'Bounty' })
  end
end)
```

## Blips and waypoints: ShowBlip / HideBlip / SetPlayerWaypoint — SERVER

Server-driven map markers; the client makes a GTA blip when told (no frame loop). Ids are your resource's own; the same id again moves/changes the blip. Gone when your resource stops or your run tag is released. Re-sent to a character on login (a charId audience follows them across relogs); cleared on logout. Not documented in the doc sections; source `server/blips.lua`, stubs `types/server.lua:147`.

### ShowBlip(audience, id, spec) — SERVER

| spec | Type | Default / rule |
|---|---|---|
| `coords` | vector3 \| `{ x, y, z }` | Required |
| `label` | string? | Map legend name, ≤ 40 chars (cleaned, `~` removed) |
| `sprite` | integer? | GTA blip icon 0–1000. Default 1 (dot); default 0 (no dot) for a bare area (`radius` with no `label` and no `route`) |
| `color` | integer? | GTA blip colour 0–85, default 5 (yellow, objective) |
| `route` | boolean? | GPS route drawn (route colour = `color`); needs the dot |
| `radius` | number? | 1–5000 m: an AREA (translucent circle, alpha 90) |
| `shortRange` | boolean? | Only on the radar when near; default false (always) |
| `scale` | number? | Clamped 0.3–2 (default 0.9) |
| `flash` | boolean? | Flashes |
| `tag` | string? | Run tag |

`audience`: `'everyone'`, `{ people = { serverId | { charId = n } } }` or `{ job = 'police', onDuty = true }` (followed as people clock on/off, are hired/fired).
Returns `true` or `false, reason` (`'coords must be a vector3 or { x, y, z }'`, `'radius is 1-5000 metres'`, `'sprite is a GTA blip icon number'`, `'color is a GTA blip colour number (0-85)'`, `'label is text'`, `'scale is a number'`, audience errors).

```lua
exports.whip_core:ShowBlip({ people = { source } }, 'dropoff', {
  coords = vector3(x, y, z), label = 'Drop-off', sprite = 1, color = 5, route = true, tag = 'run:42' })
exports.whip_core:HideBlip('dropoff')
```

### HideBlip(id) — SERVER
Takes one of your blips down. Returns `true` or `false, reason`.

### SetPlayerWaypoint(source, coords) — SERVER
GTA's own waypoint on one player's map. Returns `true` or `false, reason` (`'no such player'`, bad coords). WHIP also shares a waypoint between everyone in the same vehicle (set or cleared by any occupant).

## Audiences

`'everyone'`; `{ people = { serverId | { charId = n } } }` (≤ 64; a server id counts only while it has a loaded character); `{ job = 'key', onDuty? }` (blips and points only); `{ except = { ... } }` (NPC `hostileTo` only, with a `range`). NPC `hostileTo` never accepts `'everyone'` or a job.

## GetVehicleDriver — SERVER

### GetVehicleDriver(vehicle) — SERVER
From `server/actors.lua` (Director car tasks). Whose game drives a car now: the player in its driver's seat (`'seat'`) or the game a recorded Director take plays it on (`'take'`). `vehicle`: a vehicleId, `{ netId }`, `{ entity }` (any networked car) or `{ plate }`. Returns `source, how` or `nil` (parked, NPC driver, no car). Ask it before moving a car to another game (rope, tow): a take's game reclaims its car every 2 s.

## Server clock (internal)

`whip_core:clock:now` (SecureCallback, `rateLimit = 50, burst = 12`, no player session needed) returns the server's `GetGameTimer()`; clients sample it to sync Director playback. Not an export.

## Gotchas

1. Server `RegisterZone(id, data)` vs client `RegisterZone(data)` — shared code calling the client form on the server is refused.
2. A client zone is not trustworthy on the server; use `EnsureZone`/server `RegisterZone` and `IsPointInZone(id, p, true)` for gates. `AddPoint`'s `require.zone` must be a saved zone.
3. A client zone id with characters other than letters/digits/`_`/`-`, or longer than 60, never reaches the server (a console line says so).
4. Saved zones synced to clients belong to whip_core: a satellite's `UpdateZone('mrpd', ...)` is refused ("belongs to whip_core"); change the declaration in `EnsureZone` instead.
5. `EnsureZone` only writes when the declaration changes; admin edits in the editor stand. Changing `type` gives a new `dbzone_<n>` id — always use the key.
6. Server zone events need `trackPlayers = true`; they are local server events any resource can fake.
7. `GetZones()` is a list, not a map.
8. Zone `heal` stacks across overlapping heal zones; `speedLimit` does not (priority decides).
9. Whitelist rules do nothing without `ejectUnauthorized`; the ACE check lets a player stay if the server never answers.
10. `rules` in `UpdateZone` replaces the whole table.
11. Time/weather setters wait for whip_core to be ready — don't call them from a context that can't yield.
12. `SetTime(25, 61)` gives 01:01 (no carry), not 02:01.
13. `frozen = false` in a layer is an override, not "unset"; don't build layer tables with `cond and v or nil`.
14. NPC `weapon` must be a `WEAPON_*` name; `hostileTo` can never be `'everyone'`; `except` requires a `range`.
15. On FiveM Enhanced, make NPCs after `whip_core:player:loaded`: one made with nobody in the game can have its netId reused later (console warning).
16. `follow = false` alone makes the NPC walk back to its post; give a new `post` if you want it to stay.
17. NPC events can be fired by any resource: verify with `GetNpc` (owner, alive, killer) before rewarding.
18. A blip `radius` with no label/route gets no dot (sprite 0) and so no name or route.

## Docs vs code

- `trackVehicles`: docs (059 UpdateZone) say it "tests the player's vehicle position instead of the ped's". Code: it enables vehicle enter/exit callbacks (`onVehicleEnter`/`onVehicleExit`) over the whole vehicle pool every 2 s; the player poll always uses the ped's position (`client/zones.lua:811`, `1166-1225`).
- `SetTime` wrap: types say `25:61 is 02:01` (`types/server.lua:2829`); code wraps each value separately → 01:01 (`server/time.lua:234-235`), as the docs say.
- `enterNotify`/`exitNotify = false`: types say `false` disables the notice (`types/classes.lua:697-698`); code uses `rules.exitNotify or ('Left ' .. label)`, so `false` shows the default text (`client/zones.lua:866`, `879`). Use `notify = false` to silence.
- `SpawnNpc` `look`, `gateAt`, `outfit` are read by code (`server/npcs.lua:776-833`) but `look`/`gateAt` are missing from the `WhipNpcDef` stub and `outfit` from the docs; `opts.bucket` is in the stub but not the docs.
- `SetNpcState` also accepts `ride` and `style` (`server/npcs.lua:972-1070`), not documented.
- Docs say a weapon may be "a streamed add-on"; code still requires the `WEAPON_` prefix (`server/npcs.lua:649-651`).
- `ClearPlayerWeatherLayer` documents `false, reason` for "nothing to clear"; server code returns `true` when the layer did not exist (`server/time.lua:404-406`). The client `ClearWeatherLayer` does return `false, 'there is no layer "x"'`.
- `Config.TimeSyncInterval` ships as 60000 (`config.lua:1752`); the code fallback when unset is 5000 (`server/time.lua:445`).
- `ShowBlip`/`HideBlip`/`SetPlayerWaypoint` and `{ job }` audiences have no doc section; behaviour above is from `server/blips.lua` and `server/audience.lua`.
