# whip_rope: physics rope, rope API, Director cards

Covers the `whip_rope` satellite: the player rope item, how ropes pull/sync, settings and `config.lua`, the server/client rope API (`exports.whip_rope`), notices, internal net events, Director cards, admin commands, and the WHIP patterns it teaches. Built from doc anchors `#guide-rope`, `#rope-owners`, `#rope-director`, `#rope-debug`, `#rope-patterns`, `#rope-files`, `#rope-exports` (`#rope-locked`, `#rope-ends`, `#createrope`, `#setropeend`, `#setroperules`, `#removerope`, `#getrope`, `#getropeendentity`, `#rope-notices`) and the whole `whip_rope` repo (fxmanifest.lua, config.lua, shared/settings.lua, server/{state,keep,item,main,api,director}.lua, client/*.lua, docs/whip_rope_seg.txt), plus `whip_fuel/server/hose.lua` (reference API user) and the whip_core stubs it calls.

## Contents
- Overview and resource layout
- Player use (item, prompts, wheel, hanging, dragging)
- How a rope pulls (coupling model)
- Server model: ropes, ends, ownership, sync
- Settings page (/whip → Settings → Rope)
- config.lua reference
- The rope item and owed ropes (KVP)
- Rope API (server exports)
- Rope API (client export)
- End specs (the end table)
- Notices (events your resource listens to)
- Internal net events and SecureEvent schemas
- Validation limits the server enforces
- Director cards
- Admin / debug commands
- Using the API from your resource (whip_fuel hose pattern)
- Learning from rope (WHIP patterns)
- Where to look (file map)
- Gotchas
- Docs vs code

## Overview and resource layout

- Name `whip_rope`, version `1.0.0`, `fx_version 'cerulean'`, `lua54 'yes'`, `whip_updates 'WHIPFX/whip_rope'`, `whip_requires '1.0'`, `dependencies { 'whip_core' }`. Licence LGPL-3.0.
- Install: shipped by WHIP's txAdmin recipe; by hand `ensure whip_rope` after `ensure whip_core`. No setup, no SQL.
- Shared: `@whip_core/lib/satellite.lua` (gives `Whip.register`, `Whip.core`, `Whip.configPage`, `Whip.onConfigChanged`, `Whip.command`, `Whip.card`), `config.lua`, `shared/settings.lua`.
- Client load order (one shared `Rope` namespace): `@whip_core/lib/cost.lua` (WhipCost timers for `/whipcost`), `client/state.lua`, `physics.lua` (Verlet nodes, constraints, end pull), `collision.lua` (ground/walls/peds/explosions), `contact.lua` (rope vs rope), `mesh.lua`, `visuals.lua`, `hang_ragdoll.lua`, `interaction.lua`, `sync.lua`, `drag.lua`, `keep.lua`, `ui.lua`, `main.lua` (loops, commands, cleanup), `api.lua`.
- Server load order (one global `Ropes` table, plus `Keepers`): `server/state.lua`, `keep.lua`, `item.lua`, `main.lua`, `api.lua`, `director.lua`.
- `files { 'html/img/items/*.webp' }` (item picture `html/img/items/rope.webp`).
- `data_file 'DLC_ITYP_REQUEST' 'stream/whip_rope_seg.ytyp'`; models `whip_rope_seg` and `whip_rope_seg_ns` (no-shadow twin, archetype flag 8192), textures `whip_rope_seg_d`/`_n`, lodDist 100, no collision. `stream_enhanced/` holds Enhanced (Alchemist-converted) copies kept in sync by the `.githooks/enhanced_assets.py` pre-commit hook (FiveM Enhanced ignores `stream/` when `stream_enhanced/` exists).
- Segment model (docs/whip_rope_seg.txt): capsule along local +Y, origin in the middle, body 0.25 m, radius 0.0175 m (3.5 cm), hemispherical caps to ±0.1425; HD 168 tris (to 15 m), LOD 24 tris (15–120 m). Placing: centre = midpoint of two nodes, Y axis = direction scaled by `|b-a|/0.25`, X and Z scaled by the SAME thickness factor (never different), overlap 0. A custom `look` model must follow this model space.
- The server never simulates: it keeps each rope's two ends, who hangs where, and checks requests. Every game near a rope simulates it from those ends.

## Player use

| To | How |
|---|---|
| Put a rope out | Use the `rope` item: the rope spawns with its origin in your hand, tail loose. Refused if at `Config.Rope.MaxRopes`, hands full, hanging, or in a vehicle. |
| Tie the held end | Aim at a car, prop or the map (wall/rock/ground) within `Rules.Reach` and press the prompt key ("Tie the rope to it" on a car, else "Tie the rope here"). If the other end lies loose you now hold it. |
| Put down / let go / coil | F1 wheel entries `wheel:putDown` ("Put the rope end down": on the ground under the hand), `wheel:letGo` ("Let go of the rope end": loose where it hangs), `wheel:coil` ("Coil up the rope": server progress bar `Config.Item.CoilDuration` 3000 ms, item to whoever coils). |
| Pick up / untie an end | Prompt on the end ("Pick up the rope end", or "Untie the rope" when tied to a car/prop/map), within `Config.Grab.GrabRadius` (1.5 m). |
| Hang on | Prompt "Hang on the rope" on the middle node nearest you, within `Config.PlayerHang.GrabRadius` (1.5 m). Never an end node. |
| Let go while hanging | Jump (control 22), only after 500 ms from grabbing; or wheel `wheel:unhang`. |

- Prompts go up within 15 m of a rope and down past 22 m (client/ui.lua:15). A locked rope shows no prompts.
- Hint capsule while holding: "Holding a rope end | [E] Tie it where you look | [F1] Put it down, let go or coil up" (pad variant uses `GetPadActionButton('radial')`); while hanging: "Hanging on a rope | [Space] Let go".
- Holding an end: `Config.Holding.Speed` (`'jog'` default: walk or jog, no sprint) via `Whip.core:BlockControls('holdWalk', { jog = true })` / `{ walk = true }`; walk clipset `Config.Holding.WalkStyle` via `Whip.core:SetWalkOverride`.
- Dragged along (`Config.Drag`): holding an end whose other end is tied to a car/prop moving away faster than `Drag.MinSpeed` (2 m/s) while stretched past `Coupling.ElasticStretch`: ragdolled and pulled behind it for `Drag.Seconds` (3 s), then let go (at once on death). Otherwise, 1 m past the easy stretch the end leaves your hands ("The rope was pulled out of your hands"); this pull-out applies to unlocked ropes only.
- Shot while hanging (`PlayerHang.ShotKnocksOff` true): knocked off, ragdoll `ShotRagdollMs` (3000), unhurt (the shot does no damage; hanging peds are invincible).
- Hanging: own ped is held via `Whip.core:HoldPlayerPed('hang', { hidden = true, invincible = true })` (ragdoll style) or `{ hidden = true, noCollision = true, invincible = true }` with a stand-in (animation style); controls blocked `BlockControls('hang', { groups = { 'move', 'combat' } })`. Other games draw a collisionless stand-in ped.
- Death and logout let go of a held end and any hang (server and client both).

## How a rope pulls

- Slack (end-to-end / length below `Physics.TautThreshold` 0.95) pulls nothing.
- Taut: easy stretch up to `Coupling.ElasticStretch` (0.15, i.e. +15%) with pull rising to `ElasticPull` (5 m/s² on a `BaseMass` 1500 kg car); beyond, `StiffPull` (24 m/s² per metre) up to `MaxAcceleration` (20); backstop past `MaxStretch` (1.0 = double length) up to `BackstopPull` (40) over `BackstopRamp` (0.5 m).
- Both ends feel the same tension: a light car moves more than a heavy truck. Vehicle mass from handling `fMass`, else a per-class table, else 1500. Prop mass: frozen = 10000 kg (anchor), else `max(50, box volume × 100)` kg, unless the API end gives `mass`.
- Per-entity caps: `VehicleMaxAcceleration` 60, `PropMaxAcceleration` 20. `HandPull` 2.0 (a player holding the other end).
- A towed car nobody drives rolls freely (`Coupling.FreeRolling`: handbrake released). `AttachGraceMs` 400: no pull right after tying.
- Hard length (API `maxStretch`): beyond it one pull draws both ends together, each moved by its weight; catches up at `HardCatchUp` 2 m/s; never stretches past `HardCeiling` × maxStretch (2.0: a 0.3 hose stops at 60%). A car driving away from something that does not move is never held back.
- Keepers (`Config.Keep.Enabled`, server/keep.lua): the player pulling (driver of the car at one end, else the hand) is given network control of what the rope pulls, locked from migration with `SetNetworkIdCanMigrate`, so a towed car follows at any ping. A driver beats a hand. A driven car is never kept. A kept car with someone at the wheel, or another player on foot within 4 m, is let go so they can take it. Servers with `sv_filterRequestControl` may refuse the hand-over. A car a Director take drives (`Whip.core:GetVehicleDriver` returns `'take'`) is never pulled.
- Two driven cars on one rope: each game moves its own car; the rope acts as a strap (no give-back once closing faster than `Keep.SplitRelease` 0.5 m/s), each game extrapolates the other car by `GuessShare` of the measured lag and they exchange span vectors (`whip_rope:span`, every 250 ms).
- Simulation runs every frame (`Physics.MaxFps` 0) in 1/60 s sub-steps, at most 4 per frame. A rope further than `Rope.SimulateRange` (120 m) waits, unless you hold/hang on it or your game moves a car tied to it. A slack rope still for 1.5 s (nodes moved < 1 cm) rests until disturbed.

## Server model

A rope (server/state.lua): `{ id, owner (server id, 0 for none), ownerCharId, createdAt, originPosition = {x,y,z}, origin = END, tail = END, coiling, nodes, link, kind?, byResource?, opts?, seen? }`.
- `nodes`/`link` are fixed at creation and sent to every game; later changes to `Config.Rope` never resize a rope out. Length = `(nodes - 1) * link`.
- `byResource` set → a resource's rope (API or Director): not an item, not counted in MaxRopes, survives its player leaving, removed when that resource stops.
- `opts` (API only): `locked`, `noTake`, `noHang`, `look`, `collide`, `heldAt`, `watch`, `maxStretch`.
- `Ropes.hanging[source] = { serverRopeId, nodeIndex }`; `Ropes.owed[charId] = n`; ids from `Ropes.nextId`, starting at 1 every start.
- Server END shapes: `{type='held', heldBy}`, `{type='free', at?}`, `{type='fixed', pos, tied?}`, `{type='vehicle', netId, offset, edge?, vehicleId?}`, `{type='vehicle', netId=0, model, worldPos, point, offset, localTo}` (a car only one player's game has, e.g. a whip_scenes scene; only that player sees/unties it), `{type='object', netId (0 = map prop), model, worldPos, offset, point, still?, mass?}`.
- A tied car/networked prop that stops existing (despawn, garage, delete): checked every 2 s; the end goes loose at its last seen point (server/main.lua:445).
- Every 5 s all games get `whip_rope:list` (ids and ends; once more after the last rope goes); a game builds ropes that came into scope and drops gone ones. A rope is built on a game only while an end is held by a ped it has, tied to an entity it has, or fixed/map prop/let-go point within 300 m (client/sync.lua:13); both-loose ropes by owner or creation point.
- Drift: the owner's game sends a few key nodes (hang nodes, fast loose ends; max 8 per rope, 20 ropes) every `Sync.DriftRateMs` (250); others ease toward them by `DriftLerp` (0.25), snap if > 5 m off.

## Settings page (/whip → Settings → Rope)

`Whip.configPage({ label = 'Rope', groups = ... })` (shared/settings.lua). Saved values override `config.lua` on both sides and apply at once.

| Key | Type / range | Default | Notes |
|---|---|---|---|
| `Rope.Length` | number 2–30, step 0.5, m | 6 | New ropes only. Re-registers the item description. Recomputes `Rope.SegmentLength`. |
| `Rope.SegmentCount` | int 8–64 | 24 | New ropes only; ~4 nodes per metre recommended. |
| `Rules.AnyoneCanHandle` | bool | true | Off: only the owner grabs, unties, coils; anyone may still hang. |
| `Rules.NeedKeysToTie` | bool | false | Server checks `exports.whip_core:HasVehicleKey(source, { netId = netId })`. |
| `Rules.TieToMap` | bool | true | Off: tie prompt only on cars/props; put-down still works. |
| `Rules.Reach` | number 1–6, step 0.5, m | 3.0 | Tie reach; server allows more (see limits). |
| `Rope.MaxRopes` | int 1–20 | 5 | Item ropes per player. |
| `Item.GiveBackOnLogout` | bool | true | |
| `Coupling.FreeRolling` | bool | true | |
| `Keep.Enabled` | bool | true | "The puller moves what it pulls". |
| `Physics.MaxFps` | int 0–500, step 10 | 0 | 0 = every frame. |
| `WorldCollision.Props` | bool | true | Map always collides. |
| `WorldCollision.Vehicles` | bool | true | |
| `PlayerInteraction.Enabled` | bool | true | People push the rope. |
| `RopeContact.Enabled` | bool | true | Rope vs rope. |
| `RopeContact.Carry` | bool | false | Experimental; shown when Enabled. |
| `WorldCollision.Ground` | enum `'rays'` / `'grid'` | `'rays'` | grid: 25 cm cached ground lookup. |
| `PlayerHang.Enabled` | bool | true | Turning off detaches anyone hanging. |
| `PlayerHang.ShotKnocksOff` | bool | true | Shown when hanging enabled. |
| `Holding.Speed` | enum `walk`/`jog`/`sprint` | `'jog'` | |
| `Drag.Enabled` | bool | true | |
| `Drag.Seconds` | number 0.5–15, step 0.5, s | 3.0 | Shown when Drag enabled. |

Pull/look/hang style are `config.lua` only.

## config.lua reference

- `Config.Item`: `Name = 'rope'`, `Label = 'Rope'`, `Weight = 2.0`, `MaxStack = 5`, `CoilDuration = 3000` (ms), `GiveBackOnLogout = true`.
- `Config.Rules`: `AnyoneCanHandle = true`, `NeedKeysToTie = false`, `TieToMap = true`, `Reach = 3.0`.
- `Config.Holding`: `Speed = 'jog'` (`'walk'|'jog'|'sprint'`), `WalkStyle = 'missfbi4prepp1_garbageman'` (`'none'` = own walk).
- `Config.Drag`: `Enabled = true`, `Seconds = 3.0`, `MinSpeed = 2.0` m/s, `Pull = 6.0` (m/s per metre past length), `MaxSpeed = 18.0`.
- Debug: `Config.Debug = false`, `Config.DrawDebugLines = false`, `Config.DrawDebugSpheres = false`.
- `Config.Rope`: `Length = 6`, `SegmentCount = 24`, `MaxRopes = 5`, `SimulateRange = 120.0`; derived `SegmentLength = Length / (SegmentCount - 1)`.
- `Config.Physics`: `MaxFps = 0`, `Gravity = vector3(0,0,-9.8)`, `Damping = 0.99`, `ConstraintIterations = 16`, `DefaultNodeMass = 0.5`, `TautThreshold = 0.95`, `EnergyStorageEnabled = true`, `EnergyAccumulationRate = 0.8`, `EnergyDecayRate = 0.95`, `SnapBackMultiplier = 2.0`, `SnapBackThreshold = 0.3`.
- `Config.Visuals`: `RenderProps = true`, `Style = 'segments'` (`'segments'|'gta'|'balls'`), `SegmentModel = \`whip_rope_seg\``, `SegmentModelNoShadow = \`whip_rope_seg_ns\``, `SegmentShadows = true`, `SegmentLength = 0.25`, `SegmentThickness = 1.0`, `SegmentOverlap = 0.0`, `GtaRopeType = 4`, `PropModel = \`prop_tennis_ball\``, `RotateProps = false`, `SplineSamplesPerSegment = 1`.
- `Config.WorldCollision`: `CheckSpacing = 2`, `GroundOffset = 0.05`, `GroundFriction = 0.7`, `WallOffset = 0.06`, `Props = true`, `Vehicles = true`, `Ground = 'rays'`.
- `Config.RopeContact`: `Enabled = true`, `Gap = 0.04`, `Slide = 0.85`, `Carry = false`.
- `Config.PlayerInteraction`: `Enabled = true`, `Radius = 0.5`, `WalkForce = 1.5`, `RunForce = 3.0`, `RagdollForce = 5.0`, `PedCacheInterval = 300`.
- `Config.ExplosionInteraction`: `Enabled = true`, `Radius = 15.0`, `Force = 20.0`, `Falloff = true`.
- `Config.Grab`: `GrabRadius = 1.5`.
- `Config.PlayerHang`: `Enabled = true`, `GrabRadius = 1.5`, `SolverMass = 5.0`, `ExtraWeight = 2.0`, `ShotKnocksOff = true`, `ShotRagdollMs = 3000`, `Style = 'ragdoll'` (`'ragdoll'|'animation'`), `RagdollTask = 'balance'` (`'balance'|'relax'|'script'`), `Hand = 'free'` (`'free'|'settle'|'locked'`), `Point = 'frozen'` (`'frozen'|'driven'`), `TieBone = 'ped'` (`'ped'|'ragdoll'`), `GrabMessage = 0`, `DangleMessage = 0`, `GrabHands = 'right'` (`'right'|'both'`).
- `Config.Coupling`: `Enabled = true`, `ElasticStretch = 0.15`, `ElasticPull = 5.0`, `ElasticCurve = 1.0`, `StiffPull = 24.0`, `StiffCurve = 1.0`, `Rebound = 0.6`, `StiffRebound = 0.15`, `Damping = 0.7`, `YankAbsorb = 0.25`, `MaxDampingBoost = 1.5`, `ForceRise = 0.5`, `ForceFall = 0.3`, `MaxAcceleration = 20.0`, `VehicleMaxAcceleration = 60.0`, `PropMaxAcceleration = 20.0`, `MaxStretch = 1.0`, `BackstopPull = 40.0`, `BackstopRamp = 0.5`, `HardCatchUp = 2.0`, `HardCeiling = 2.0`, `PullBack = true`, `ReturnSpeed = 3.0`, `ReturnRate = 1.0`, `ReturnAccel = 6.0`, `ReturnPull = 30.0`, `FreeRolling = true`, `AttachGraceMs = 400`, `HandPull = 2.0`, `GroundLift = 0.15`, `SteepRope = 0.7`, `BaseMass = 1500.0`.
- `Config.Keep`: `Enabled = true`, `SplitRelease = 0.5`, `GuessShare = 1.0`, `AircraftTwist = 0.1`.
- `Config.Sync`: `DriftEnabled = true`, `DriftRateMs = 250`, `DriftLerp = 0.25`.

## The rope item and owed ropes

- Registered in `Whip.register` (re-runs on every whip_core start) via `exports.whip_core:RegisterItem(Config.Item.Name, { name = Label, desc = 'A <Length> m rope. ...', weight = 2.0, type = 'tool', stack = true, maxStack = 5, usable = true, cooldown = 2, image = 'html/img/items/rope.webp' })` and `exports.whip_core:RegisterUseHandler('rope', onUse)` (server/item.lua:156-175).
- `onUse(source, player)`: returns `false, why` (item kept, reason shown: "You already have N ropes out", "Your hands are full", "Let go of the rope first", "Not now", "Get out of the vehicle first") or `true` (item consumed). Creates `{ owner = source, ownerCharId = player.charId, origin = held by source, tail = free, nodes = max(2, floor(SegmentCount)), link = Length/(nodes-1) }` and broadcasts `whip_rope:spawned`.
- Giving back: `Whip.core:AddItem(source, 'rope', n, nil, reason)`; failure prints and returns false.
- Owed ropes live in whip_rope's resource KVP key `owed` as JSON `{ "<charId>": n }`; survive restarts. Paid on `whip_core:player:loaded` (in a thread) and, on whip_rope start, to everyone loaded (after `Whip.ready(60000)`). Pay = `takeOwed` first, then give; on failure `owe` again. Notify "The rope you had out is back in your pockets".
- Who owes: `Ropes.playerGone` (logout / `playerDropped`, safe twice) removes the player's item ropes and owes them when `GiveBackOnLogout`; whip_rope `onResourceStop` owes every item rope out regardless of that setting; a coil whose AddItem fails owes; `/clearropes` owes when the owner is not the same loaded character.
- Director Test cars: a rope tied to a car a Test made (`whip_core:run:thingMade` with `test`) is taken back into its owner's pockets when that car is released as temp (`whip_core:vehicle:released`, `temp = true`). Real runs leave the rope loose.

## Rope API (server exports)

Ownership is keyed to `GetInvokingResource()` (falls back to whip_rope's own name). Add `dependency 'whip_rope'`, or check `GetResourceState('whip_rope') == 'started'` and wrap calls in `pcall`.

### CreateRope(spec) — SERVER
Makes a rope between two ends, built on every game near it. Broadcasts `whip_rope:spawned`.

| spec field | Type | Default | Meaning |
|---|---|---|---|
| `origin`, `tail` | end table | required | See End specs. At least one must resolve to a server-known position (held by an online player, fixed, networked car/prop that exists, or map prop with `worldPos`/`point`). |
| `length` | number? | `Config.Rope.Length` | Metres, clamped 0.5–100. Fixed for life. |
| `link` | number? | `Config.Rope.SegmentLength` | Metres between nodes, min 0.05. Nodes = `max(4, floor(length/link + 0.5) + 1)`, capped at 64 (links lengthened; printed once per resource). Actual link = length/(nodes-1). |
| `player` | number? | 0 | Player it is for: becomes `owner` (always built on their game; used for nearness and, with `AnyoneCanHandle` off, who may handle an unlocked rope). |
| `kind` | string? | nil | Your tag, truncated to 32 chars; non-strings dropped. Returned by `GetRope`. |
| `locked` | boolean? | nil | `true`: nobody grabs, ties, puts down, coils or hangs off it; no prompts; holding its end is not "holding a rope" (no walk limit, not pulled out of the hand). |
| `take` | boolean? | true | Unlocked only: `false` = nobody picks up/unties its ends. |
| `hang` | boolean? | true | Unlocked only: `false` = nobody hangs off it. |
| `look` | table? | rope's own | `{ model, modelNoShadow, thickness }`; models must be numbers (hashes): a string is dropped (`tonumber`). Loaded client-side before drawing; if not loaded first, the default pieces are kept. `modelNoShadow` used when `Visuals.SegmentShadows == false`. |
| `collide` | table? | settings | `{ spacing, vehicles, props }`: every `spacing`'th node probed (default 2, min 1); `vehicles`/`props` booleans (nil = `Config.WorldCollision.Vehicles/Props`). Map always probed. |
| `heldAt` | table? | hand | `{ model, offset }`: a held end sits at `offset` on the prop of `model` attached to the holder (found within 0.6 m of bone 57005, rechecked every 500 ms). `model` may be a name or hash (`GetHashKey` server-side). |
| `watch` | table? | none | `{ stretch, holdMs = 250, broken }`: fire `whip_rope:ropeStretched` when stretched past `stretch` (0.35 = 35%) for `holdMs`; `broken = true` fires `whip_rope:ropeEndBroken` when a map prop end is blown up. |
| `maxStretch` | number? | none (elastic) | Hard length, clamped 0–2 (0.2 = 20% over). |

Returns: `number` id, or `false, reason`. Reasons: `'spec is a table'`; `'origin: <why>'` / `'tail: <why>'` where why ∈ `'an end is a table: { type = ... }'`, `'a held end names heldBy (a player)'`, `'a fixed end names pos'`, `'a vehicle end names netId'`, `"a vehicle end's edge is 'front' or 'back'"`, `'a map prop end names model and worldPos'`, `'unknown end type "<t>"'`; `'neither end is anywhere yet'`.

```lua
local id, why = exports.whip_rope:CreateRope({
    origin = { type = 'vehicle', netId = NetworkGetNetworkIdFromEntity(truck), offset = vector3(0.0, -3.2, 0.6) },
    tail   = { type = 'vehicle', netId = NetworkGetNetworkIdFromEntity(car), edge = 'front' },
    length = 6.0, locked = true, kind = 'towline',
})
if not id then print('no tow line: ' .. why) return end
```

How `maxStretch` holds: pull at most a strong hose's; a snag jolts the car; stretches briefly up to `HardCeiling` × maxStretch where it holds. With `watch.stretch` > `maxStretch` the notice comes only when neither end can follow (whip_fuel hose: maxStretch 0.3, stretch 0.35 → told only when a car drives off with the nozzle in).

### SetRopeEnd(id, which, end) — SERVER
Moves one end of a rope your resource made; every game told (`whip_rope:ends`), keepers recomputed, Director listeners hear `'ends'`.
- `id` number; `which` `'origin'|'tail'`; `end` an end table.
- `{ type = 'free' }` becomes loose at where that end was (server-known position), not at any `at` you pass.
- Returns `true`, or `false, reason`: `'not your rope'` (another resource's or gone), `"which is 'origin' or 'tail'"`, or an end-validation reason (bare, no `origin:` prefix).
- No check that a `heldBy` player is online or has free hands.
- A locked rope's held end is never released by whip_rope: move it yourself on `whip_core:player:died`, `whip_core:player:logout` and `playerDropped`.

```lua
exports.whip_rope:SetRopeEnd(id, 'tail', { type = 'held', heldBy = source })
```

### SetRopeRules(id, rules) — SERVER
Changes player rules and the stretch watch from now on; fields left out unchanged. Broadcasts `whip_rope:opts`.
- `rules = { take?, hang?, stretch? }`: `take`/`hang` booleans as in CreateRope; `stretch` number > 0 (clamped to 2.0; `holdMs` defaults 250 if no watch existed) or `false` to stop the stretch watch.
- Returns `true`, or `false, reason`: `'not your rope'`, `'rules is { take?, hang?, stretch? }'`, `'stretch is how far past its length, 0.35 for 35%'`.

```lua
exports.whip_rope:SetRopeRules(id, { take = false })   -- winch set: nobody unhooks it
```

### RemoveRope(id) — SERVER
Removes a rope your resource made on every game; anyone hanging drops. Returns `true`, or `false` (not yours / gone). No `ropeRemoved` notice for your own removal.

### GetRope(id) — SERVER
Any rope (player's or resource's). Returns `{ kind, origin, tail, length }` (ends exactly as the server keeps them, incl. internal fields such as `at`, `tied`, `vehicleId`, `localTo`, `point`, `still`, `mass`; `length` = `(nodes-1)*link`), or `nil`. Ends can change without notice: re-read before relying on one.

```lua
local rope = exports.whip_rope:GetRope(id)
if rope and rope.tail.type == 'held' then print(rope.tail.heldBy, rope.length) end
```

## Rope API (client export)

### GetRopeEndEntity(id, which) — CLIENT
- `id` number (the server id), `which` `'origin'|'tail'`.
- Returns the car/prop entity that end is tied to on this game, or `nil` (not tied to an entity, not streamed in, rope not built here, bad `which`). When it returns the new entity, a `SetRopeEnd` has reached this game. For a take car shown as a local copy it returns the copy.
- whip_fuel calls it inside `pcall` (`whip_fuel/client/hose.lua:290`).

## End specs

| Type | Fields |
|---|---|
| `{ type = 'held' }` | `heldBy`: server id. Ends at the right hand, or at `heldAt`'s prop. |
| `{ type = 'fixed' }` | `pos` (vector3 or `{x,y,z}`/array); `tied = true`: tied to the map there (players see "Untie the rope"), else "put down". |
| `{ type = 'vehicle' }` | `netId` (> 0, networked car); `offset` in car space (default `{0,0,0}` = middle); or `edge = 'front'|'back'`: nose/tail from model dimensions, 30% up the body, computed per game (overrides offset). |
| `{ type = 'object' }` | `netId` (networked prop) or `0` for a map prop, which then needs `model` (number hash: a string fails) and `worldPos`, optional `point` (tie point, default `worldPos`), `still = true` (never woken/dragged; map props only); `offset`; `mass` kg (> 0, capped 100000). |
| `{ type = 'free' }` | Loose. `GetRope` may show `at` (where let go). |

- Map prop ends: each game finds its own copy by model within 1.5 m of `worldPos`; an unfrozen one is made a mission entity, dynamic, and dragged independently per game; frozen = anchor.
- An end comes loose without notice when its car/prop goes (any rope; server checks every 2 s); on unlocked ropes also when the holder dies/leaves or a player unties it.
- Vectors are normalised to `{x,y,z}` floats; `vector3` accepted.

## Notices

Every resource hears every rope's notices: filter on `resource == GetCurrentResourceName()`. Server notices are local `TriggerEvent` (use `AddEventHandler`, no `RegisterNetEvent`; clients cannot fake them).

| Event | Side | Args | When |
|---|---|---|---|
| `whip_rope:ropeStretched` | Server | `id, resource` | Stretched past `watch.stretch` for `watch.holdMs`; repeats every 3 s while it stays so: act once. Reported only by a game that runs an end (holder, or network owner of a car/prop end); believed only if the server-known ends are ≥ `length × (1 + stretch × 0.6)` apart and the reporter is near (`Ropes.near`: within length + 8 m of an end). |
| `whip_rope:ropeEndBroken` | Server | `id, which, resource` | A map prop end (`watch.broken`) was blown up: client sees `HasObjectBeenBroken`, server believes it only with an `explosionEvent` within 15 m in the last 10 s and the reporter near. Repeats every 3 s. |
| `whip_rope:ropeRemoved` | Server | `id, resource, why` | whip_rope removed it itself (`/clearropes`, why `'cleared by an admin'`). Not sent for your own `RemoveRope` or your stop. |
| `whip_rope:pulledFromHand` | Client | `id, which, resource` | Locked ropes only, on the holder's game: a drag ride ended (Drag.Seconds up, or they died). The end stays theirs until your server moves it. No new ride on that rope for 5 s. |

```lua
-- client: a locked line pulled from this player's hand
AddEventHandler('whip_rope:pulledFromHand', function(id, which, resource)
    if resource ~= GetCurrentResourceName() then return end
    TriggerServerEvent('mytow:dropLine', id)
end)
-- server, inside Whip.register: drop it at their feet if it is theirs
Whip.core:SecureEvent('mytow:dropLine', { params = { { 'id', 'id', 1, 2147483647 } } }, function(source, player, id)
    local rope = exports.whip_rope:GetRope(id)
    if not rope or rope.tail.type ~= 'held' or rope.tail.heldBy ~= source then return end
    exports.whip_rope:SetRopeEnd(id, 'tail', { type = 'fixed', pos = GetEntityCoords(GetPlayerPed(source)) })
end)
```

whip_rope restart: all API ropes go, no notice, ids restart at 1. Forget yours on its `onResourceStop`, recreate on its `onResourceStart` (whip_fuel waits 1 s for whip_rope's registrations).

## Internal net events and SecureEvent schemas

Client → server (all `exports.whip_core:SecureEvent('whip_rope:<name>', schema, fn)` inside `Whip.register`, server/main.lua:372-437, server/api.lua:359-367). `ID = { 'ropeId', 'id', 1, 2147483647 }`, `END = { 'which', 'enum', { 'origin', 'tail' } }`, coords `number` ±20000, offsets `number` ±20. End-changing events use `{ rateLimit = 150, burst = 6, onReject = correctOnReject }`.

| Event | Params | Schema extras |
|---|---|---|
| `take` | ID, END | end schema |
| `place` | ID, END, x, y, z | end schema |
| `tieMap` | ID, END, x, y, z | end schema |
| `release` | ID, END | end schema |
| `tieVehicle` | ID, END, netId (id ≥1), ox, oy, oz | end schema |
| `tieLocalVehicle` | ID, END, model, wx..wz, ox..oz, px..pz | end schema |
| `tieObject` | ID, END, netId (id ≥0), model, wx..wz, ox..oz, px..pz | end schema |
| `lost` | ID, END | rateLimit 250, burst 10, onReject correct |
| `hang` | ID, nodeIndex (id 1–4096) | rateLimit 500, burst 3, onReject sends `unhung` |
| `unhang` | none | `rateLimit = false, whileDead = true` |
| `shot` | target (id) | rateLimit 200, burst 5 |
| `coil` | ID | rateLimit 1000, burst 2, onReject sends `coilEnded` |
| `drift` | batch list ≤20 of `{ r, n = list ≤8 of { i, x, y, z } }` | rateLimit 100, burst 4, `sheet = 'light'` |
| `span` | batch list ≤20 of `{ r, x, y, z }` (±1000) | rateLimit 100, burst 4, `sheet = 'light'`; handler `Keepers.onSpan` |
| `ready` | restarted (bool, default false) | rateLimit 2000, burst 2, whileDead |
| `stretched` | ropeId | rateLimit 500, burst 2 |
| `endBroken` | ropeId, which enum | rateLimit 500, burst 2 |

Server → client: `whip_rope:spawned` (payload `{ serverRopeId, owner, originPosition, origin, tail, nodes, link, kind, opts, resource }`), `despawned` (id), `ends` (id, `{ origin?, tail? }`), `correction` (payload, to one player), `opts` (id, opts), `coilEnded`, `hung` (serverId, ropeId, nodeIndex), `unhung` (serverId), `shotOff` (x, y, z), `drift` (ropeId, owner, nodes), `list` (`{ maxId, ropes = { { id, owner, originPosition, origin, tail } } }`, every 5 s), `keep` (netId list), `letGo` (netId), `driven` (netId list), `lag` (map), `theirSpan` (list).

whip_core events consumed: server `whip_core:player:died`, `whip_core:player:logout`, `whip_core:player:loaded`, `whip_core:run:thingMade`, `whip_core:vehicle:released`, `whip_core:run:ended` (all checked `GetInvokingResource() == 'whip_core'` where it matters), plus `playerDropped`, `explosionEvent`, `onResourceStop`; client `whip_core:player:loaded`, `whip_core:player:spawned`, `whip_core:player:died`, `whip_core:player:logout`, `whip_core:vehicle:copied` (`{ entity, of }`: a take car's local copy).

whip_core APIs used: `SecureEvent`, `RegisterItem`, `RegisterUseHandler`, `AddItem`, `NotifyPlayer`, `GetPlayer`, `GetCharId`, `GetVehicle`, `GetVehicleDriver`, `HasVehicleKey`, `Progress`, `GetScenarioRun`; client `AddAction`, `UpdateAction`, `RemoveAction`, `ShowText`, `HideText`, `AcceptHint`, `KeyHint`, `IsControllerActive`, `GetPadActionButton`, `SetWalkOverride`, `BlockControls`, `UnblockControls`, `HoldPlayerPed`, `ReleasePlayerPed`, `LoadModel`, `Notify`, `IsPlayerLoaded`, `IsPlayerDead`, `HasDevTools`.

## Validation limits the server enforces

| Request | Check (server/main.lua) | Refusal text |
|---|---|---|
| take | rope exists; end not held; `mayHandle` (not locked; AnyoneCanHandle or owner); not `noTake`; hands free; not hanging; local-car end only by `localTo`; within `GrabRadius + 7` of the end (loose end: `Ropes.near`) | 'That rope is gone', 'Someone is holding that end', "That rope isn't yours", "That rope can't be picked up", 'Your hands are full', 'Let go of the rope first', 'Only the player who tied it can untie that', 'Too far away' |
| place | holds that end (unlocked); point within 10 m | 'Too far away' |
| tieMap | holds; `TieToMap`; point within `Reach + 7` | "Ropes can't be tied to the map here" |
| tieVehicle | entity exists and type 2; within `Reach + 11` of its centre; keys if `NeedKeysToTie` | "That car isn't there", 'You need the keys to this car' |
| tieObject / tieLocalVehicle | networked prop exists and type 3 (model/pos taken from server); within `Reach + 11` of worldPos; point within 15 m of worldPos | "That isn't there" |
| hang | `PlayerHang.Enabled`; not locked / `noHang`; node 2..nodes-1; hands free; near; not in a vehicle | 'Hanging on ropes is off', "That rope can't be hung from", 'Get out of the vehicle first' |
| shot | ShotKnocksOff; target hanging and not self; shooter not `WEAPON_UNARMED`; within 320 m | silent |
| coil | holds an end; not a resource's rope; mayHandle; not already coiling; after bar re-checks it still exists and is still held | 'Hold one of its ends first', "That rope isn't yours to coil up", 'Someone is already coiling it up' |
| drift | sender is owner; node index ≤ nodes; node within `length*2 + 5` of a known end (`believable`) | dropped |

After placing/tying one end, the server also gives the player the other end if it lies loose and their hands are free (`Ropes.takeOtherIfLoose`).

## Director cards

Registered with `Whip.card` (server/director.lua). Category "Ropes" (amber, icon `pickup`) unless a goal. A run's ropes are `Ropes.create(..., 'whip_rope')` (byResource = whip_rope, `kind = 'director'`), keyed by name (trimmed, lowercased, default `'rope'`), removed on `whip_core:run:ended`; Tests (no run:ended) are polled every 3 s with `GetScenarioRun(runId, { tests = true })`. Making a rope again under the same name removes the old one. Ropes never tie to NPCs (Check says so). A moving prop (networked physics object) is tied to itself; a still prop and a spot become a `fixed` end with `tied = true`.

| Id | Title | Props (key: default) | Outputs |
|---|---|---|---|
| `rope.make` | Make a Rope | `name`: 'rope' (≤24); `fromIs`: 'thing' (`thing`/`hand`/`loose`), `from` (world), `fromEdge`: 'back'; `toIs`: 'loose', `to`, `toEdge`: 'front' (`back`/`front`/`middle`); `length` 1–30 m: 6; `take`: true; `hang`: true | made / failed |
| `rope.moveEnd` | Move a Rope End | `name`; `which`: 'first' / 'second'; `toIs`: 'thing'; `to`; `edge`: 'back' | moved / noRope / failed |
| `rope.rules` | Change Rope Rules | `name`; `take`: true; `hang`: true | changed / noRope |
| `rope.remove` | Remove a Rope | `name` | removed / noRope |
| `rope.goalTie` | Goal: Tie a Rope (goals) | `text` (≤120), `target` (required), `target2`, `runOnly`: false, `name` (shown if runOnly), `seconds` 0–3600: 0 | tied / outOfTime / lost |
| `rope.goalHang` | Goal: Hang on a Rope (goals) | `text`, `hold` 0–600 s: 0, `runOnly`, `name`, `seconds` | hung / outOfTime |
| `rope.whenPulled` | When a Rope Is Pulled Too Far | `name`; `stretch` 5–200 %: 35; `snap`: true | pulled / noRope |

- `hand` end: the run's player; if their hands are full or hanging, the end is put down at their feet (logged). Both ends in hand → second is loose. Both loose → Check error.
- Goal: Tie is satisfied by any unlocked rope (a player's too) unless `runOnly`; target car gone → `lost`; spot/still prop match within 2 m (`TIE_NEAR`). Credited source: who tied, else a run player holding the other end, else the run's player. Goals time out after 3600 s (`GOAL_TIMEOUT`); `seconds` is the visible limit. Goals re-check every 500 ms for time/car/hold time and otherwise react to `Ropes.onChange`.
- When Pulled: sets `watch.stretch = stretch/100` on the run's rope; on a believed stretch answers `pulled` and, with `snap`, removes the rope; clears the watch when the card ends.

## Admin / debug commands

All need developer mode (whip.devtools with dev mode on, `/w`).
- `/ropedebug` (client `RegisterCommand`, gated by `Whip.core:HasDevTools()`): overlay of ends, stretch, pull, rays per second, resting ropes.
- `/ropestatus` (client): prints look style, held end, hang, and every rope on this game to F8.
- `/ropes` (server `Whip.command('ropes', { dev = true, whileDead = true })`, also console): lists ropes and hanging count.
- `/clearropes` (server, also console): removes every rope. Item ropes: given back now if the owner is still the same character, else owed. Resource ropes (incl. Director ropes): removed with `whip_rope:ropeRemoved` (`why = 'cleared by an admin'`).

## Using the API from your resource (whip_fuel hose pattern)

`whip_fuel/server/hose.lua` is the reference:
- `GetResourceState('whip_rope') == 'started'` guard; every export call inside `pcall`.
- Pump end: `{ type = 'object', netId = 0, model = <hash>, still = true, worldPos, offset, point }` (map prop anchor, never dragged), or `{ type = 'fixed', pos }` if the model is unknown.
- `CreateRope({ kind = 'hose', player = holder, origin = pumpEnd, tail = { type = 'held', heldBy = src }, length = Config.Hose.Length, link = Config.Hose.LinkLength, locked = true, look = { model = Config.Hose.Model, modelNoShadow = Config.Hose.ModelNoShadow, thickness = 1.0 }, collide = { spacing = 1, vehicles = ... }, heldAt = { model = 'prop_cs_fuel_nozle', offset = NOZZLE_HOSE_END }, watch = { stretch = 0.35, holdMs = 250, broken = true }, maxStretch = 0.3 })`.
- Moves the tail with `SetRopeEnd` as the nozzle goes hand → car → ground; listens to `ropeStretched` (breakaway), `ropeEndBroken` (pump destroyed, `which == 'origin'`), `ropeRemoved` (forget the id), client `pulledFromHand` (drop the nozzle).
- Keeps `hoses[key] = { id }` and `keyOfId[id] = key`; clears both on whip_rope `onResourceStop`; redraws all on whip_rope `onResourceStart` after `Wait(1000)`.

## Learning from rope (WHIP patterns)

1. **Client acts first, server corrects.** The game applies the change at once (`Rope.ApplyEnd(rope, which, { type = 'held', heldBy = Rope.MyServerId() })`) then `TriggerServerEvent('whip_rope:take', ...)`. Server handlers refuse via `refuse(source, ropeId, why)` = `Ropes.correct(source, ropeId)` (sends `whip_rope:correction` with the true rope) + `return false, why` (WHIP shows `why`). Rejections before the handler (rate, bad value) are corrected through the schema's `onReject = function(src, _, raw) Ropes.correct(src, tonumber(type(raw) == 'table' and raw[1])) end` (`raw` is unvalidated). `Rope.ApplyEnd` skips an unchanged end (`sameEnd`), so the server's echo is a no-op.
2. **A client report is a claim.** Check against what the server sees: drift nodes only within reach of known ends (`believable`); shots only from armed players in range (`onShot`); stretch only when ends really are apart (`onStretched`); blown-up props only with a server-seen `explosionEvent` nearby (`onEndBroken`).
3. **Nothing owned is lost.** Owe to KVP before giving (`Ropes.owe`, `Ropes.takeOwed`); debt taken off the books before the give so two loads can't both pay; put back if the give fails. Stop handler owes without waiting.
4. **Server-timed bar from a SecureEvent.** `Whip.core:Progress(source, { label = 'Coiling up the rope', duration = 3000, icon = 'pickup', item = 'rope', canCancel = true })` inside a SecureEvent handler (may wait; a SecureCallback may not). `done ~= true` → cancelled or left. Re-check after the bar (rope still there and still held by them). Mark `rope.coiling` to block a second coiler.
5. **Aim prompt.** `at = { aimBox = { 'vehicle', 'object', 'world' } }`; `ctx.entity`, `ctx.coords`, `ctx.world`, `ctx.normal`. An aimBox action casts a ray every frame while it exists, so add it only while needed (`AddAction` when an end is held, `RemoveAction('tie')` when not), checked 5×/s. `AddAction` returns the id string or `false, why`: test truthiness (`tieUp = Whip.core:AddAction(TIE) and true or false`). Update reach live with `UpdateAction('tie', { reach = ... })`.
6. **Satellite lifecycle.** All whip_core registrations (items, use handlers, SecureEvents, wheel actions) live in `Whip.register` so a whip_core restart re-runs them. A resource without `dependency 'whip_core'` that keeps running through a whip_core restart must reset its "prompt is up" flags in `Whip.onCoreLost`.
7. **Settings page that applies at once.** `Whip.configPage` + `Whip.onConfigChanged('Rope.Length', fn)` etc.; re-register an item a tick later (`SetTimeout(0, ...)`, guarded by `Whip.isReady()`) to avoid registering from inside whip_core's settings call.
8. **Ped hold and walk.** `HoldPlayerPed`/`ReleasePlayerPed` with a key, `BlockControls`/`UnblockControls` with a key, `SetWalkOverride`: whip_core sweeps them if the resource stops.
9. **Per-resource API ownership.** Exports key every object to `GetInvokingResource()`, refuse others with `'not your rope'`, clean up on that resource's `onResourceStop`.
10. **Idle loops.** Loops sleep `Rope.Const.IDLE_MS` (1000) when no rope exists/is awake; prompt loop 200 ms otherwise.
11. **Release on leave.** Handle `whip_core:player:died`, `whip_core:player:logout` and `playerDropped`; make the cleanup idempotent (`Ropes.playerGone` runs twice on logout+drop).

## Where to look

| To see how to | Read |
|---|---|
| Check requests and correct on refusal | `server/main.lua`: `refuse`, `Whip.register` block |
| Change locally before the server replies | `client/interaction.lua`: `Rope.TakeEnd`, `Rope.TieHeldEnd`, `Rope.ApplyEnd` |
| Put the game right on refusal | `client/sync.lua`: `whip_rope:correction` |
| Verify client claims | `server/main.lua`: `believable`, `onShot`; `server/api.lua`: `onStretched`, `onEndBroken` |
| Release on death/logout/leave | `server/main.lua` last handlers; `server/state.lua`: `Ropes.playerGone` |
| Owe an item on disk | `server/state.lua`: `Ropes.owe`; `server/item.lua`: `payOwed` |
| Item whose use spawns something | `server/item.lua`: `registerItem`, `onUse` |
| Server-timed bar | `server/main.lua`: `onCoil` |
| Prompts, wheel, hint capsule | `client/ui.lua` |
| Live settings page | `shared/settings.lua` |
| Hold ped, slow walk | `client/interaction.lua`: `HangPedOn`, `applyHoldWalk` |
| Offer an API per resource | `server/api.lua`, `client/api.lua` |
| Use the API | `whip_fuel/server/hose.lua` (`draw`), `whip_fuel/client/pumps.lua` |
| Network control hand-off | `server/keep.lua`, `client/keep.lua` |
| Idle loops | `client/main.lua`, `client/ui.lua` |

## Gotchas

1. Notices are server-local/client-local `TriggerEvent`s broadcast to every resource: always filter on `resource`, and use `AddEventHandler`, not `RegisterNetEvent`.
2. `ropeStretched` repeats every 3 s while stretched: act once (e.g. remove/move first, or keep a flag).
3. `ropeStretched` needs a game that runs an end (a player holding it, or the network owner of a car/networked prop end). A rope between two fixed points/map props, or with no owner game nearby, never reports. A `vehicle` end with `netId = 0` has no server position, so the stretch is never believed.
4. Map prop `model` in an end must be a number hash; `look.model`/`modelNoShadow` too. Only `heldAt.model` accepts a name.
5. `length` is clamped silently (0.5–100); nodes capped at 64 by lengthening links (min 4 nodes for API ropes); `kind` truncated to 32 chars. A rope's length can't change: remove and create again.
6. Locked ropes: whip_rope never releases the held end, even on death, logout or drop. You must move it, and `pulledFromHand` fires only after a drag ride, so with `Config.Drag.Enabled = false` you never hear it.
7. Unlocked API ropes: players can pick up, untie, re-tie and put down ends and you are not told; only coiling is blocked. Use `take = false`, `locked = true`, or poll `GetRope`.
8. `SetRopeEnd` does not check that `heldBy` is online, that their hands are free, or that a netId exists; `free` ignores any `at` you pass.
9. `SetRopeRules` applies `take`/`hang` to the server record before validating `stretch`; an invalid `stretch` returns false and the take/hang change is kept server-side but not broadcast to games (server/api.lua:242-253).
10. whip_rope restart: all API ropes vanish without `ropeRemoved`, and ids restart from 1, so a stale id may later point at someone else's rope (calls then fail with `'not your rope'`, but `GetRope` returns the other rope). Clear ids on its `onResourceStop`.
11. Resource ropes never count toward `MaxRopes`, are never items, and are removed when the creating resource stops; Director ropes belong to `whip_rope` itself.
12. Prompts and the aimBox tie action are whip_core's: register inside `Whip.register`; `AddAction` returns the id string, not `true`.
13. `/clearropes` and `/ropes` need dev mode in game but also work from the server console; `/ropedebug` and `/ropestatus` are client commands gated by `HasDevTools()`.
14. Item ropes of a player who leaves are removed from the world (not left lying) and owed only if `Item.GiveBackOnLogout`; whip_rope stopping owes all item ropes regardless of that setting. A rope whose owner had no `charId` is simply lost.
15. A tied entity that despawns makes the end loose within ~2 s (server poll) with no notice to API users.
16. Changing `Rope.Length`/`SegmentCount` affects only ropes made afterwards; API ropes without `length`/`link` read these at creation.
17. Server tie reach checks are generous (`Reach + 7`, or `+ 11` from a car's centre/prop's position) to absorb ping; the client prompt uses `Reach`.

## Docs vs code

1. Docs pattern example sets `tieUp = Whip.core:AddAction(TIE) == true`; `AddAction` returns the id string or `false, why` (`whip_core/types/client.lua:913-916`), so `== true` is always false. Code uses `Whip.core:AddAction(TIE) and true or false` (`whip_rope/client/ui.lua:256`).
2. Docs example declares the tie action with a fixed `at = { aimBox = { 'vehicle', 'object', 'world' } }`; code drops `'world'` when `Config.Rules.TieToMap` is false and re-adds the action on change (`client/ui.lua:178-181`, `319-325`).
3. `server/api.lua:31` header comment shows `collide = { spacing = 1, ... }`; the actual default when omitted is 2 (`server/api.lua:153`), matching the docs.
4. Docs say `ropeStretched` is "believed only when the ends really are far apart"; the exact rule is ends ≥ `length × (1 + stretch × 0.6)` apart plus reporter within length + 8 m of an end (`server/api.lua:315-316`, `server/state.lua:126-129`).
5. Docs: "Players who leave with ropes out get them back"; code removes them and owes only with `Config.Item.GiveBackOnLogout` (`server/state.lua:328`), but owes on whip_rope stop unconditionally (`server/item.lua:148-153`).
6. Docs `SetRopeRules` failure "a rule it can't read": in code only `stretch` is validated; non-boolean `take`/`hang` are coerced (`rules.take == false`), never refused (`server/api.lua:242-243`).
