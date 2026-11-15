# Autos, fuel, dealership: whip_autos, whip_autos_shop, whip_fuel, whip_dealership, chameleon_paint

Covers the vehicle-side satellites of WHIP: Whiplash (customisation, turbo, nitrous, power settings), its Burton building, fuel (tank stat, pumps, hose, jerry can), Simon's dealership, and the Chameleon paint ramps. Built from doc anchor `autos-patterns` (082) plus mentions in 001, 002, 006, 030, 033, 034, 042, 045, 046, 071, 075, 081, 094, 103, 104; verified against the source of every resource named (fxmanifest, config, shared/, server/, client/, README, html where relevant) and `txAdmin-recipe/*.yaml`.

## Contents
- Overview and install order
- whip_fuel: manifest and deps
- whip_fuel: config keys
- whip_fuel: the settings page
- whip_fuel: the `fuel` vehicle stat (tank, burn, empty engine, electric cars)
- whip_fuel: pumps and nozzles (model, keys, states, money holds)
- whip_fuel: SecureEvents and SecureCallbacks
- whip_fuel: server events other resources can hear
- whip_fuel: net events to clients
- whip_fuel: prompts (actions) players see
- whip_fuel: jerry cans
- whip_fuel: the hose and torn pumps (whip_rope)
- whip_fuel: screens, dials, map icons
- whip_fuel: using fuel from your resource
- whip_fuel: lessons
- whip_autos: manifest and deps
- whip_autos: config keys
- whip_autos: the settings page (/whip > Settings > Autos)
- whip_autos: the shop flow (claim, preview, purchase, release)
- whip_autos: SecureEvents, SecureCallbacks, NUI callbacks, net events
- whip_autos: basket lines and slot ids
- whip_autos: tuning as VehicleData
- whip_autos: engines.json and /whiplashengines
- whip_autos: turbo (`boost` live stat)
- whip_autos: nitrous (`nitro` consume stat, `nitro` item)
- whip_autos: power layers on every car (top speed, shift time, gearbox)
- whip_autos: Director cards, task, builder buttons
- whip_autos: export, commands, key mappings, Object Viewer option
- whip_autos: lessons (Learning from whip_autos)
- whip_autos_shop
- chameleon_paint
- whip_dealership
- Repository tooling: .githooks/enhanced_assets.py
- Gotchas
- Docs vs code

## Overview and install order

| Resource | Is | Needs | Own exports |
|---|---|---|---|
| `whip_fuel` | Tank stat on every car, every GTA pump works, hose, jerry can | `whip_core`; optional `whip_rope` (hose), `whip_gunny` (jerry can) | none |
| `whip_autos` | Whiplash shop, turbo stages, nitrous bottle, server-wide top speed / shift / gearbox | `whip_core`; `whip_autos_shop` for the building; `chameleon_paint` for paints 161-222 | `GetOpenSessions` (server) |
| `whip_autos_shop` | Map resource: the WHIPLASH building in Burton (replaces LS Customs Burton) | nothing | none |
| `whip_dealership` | Simon's car lot + Manage Keys; "the reference resource for building on whip" | `whip_core` | none |
| `chameleon_paint` | WildBrick142's `vehicle_paint_ramps.ytd` (not WHIP, not LGPL, never sell) | nothing | none |

- All Lua resources: `fx_version 'cerulean'`, `game 'gta5'`, `lua54 'yes'`, `shared_script '@whip_core/lib/satellite.lua'` (gives `Whip.register`, `Whip.core`, `Whip.configPage`, `Whip.onConfigChanged`, `Whip.isReady`, `Whip.ready(ms)`, `Whip.card`, `Whip.task`, `Whip.padScreen`, `Whip.sayStarted`, `Whip.startProblem`, ...).
- `whip_updates 'WHIPFX/<repo>'` (fuel, autos, autos_shop): whip_core checks that repo's releases. `whip_requires '1.0'` (fuel, autos): setup report flags an older whip_core.
- No SQL for any of them.
- Recipe (`txAdmin-recipe/whip-*.yaml`): installs `whip_autos`, `whip_autos_shop`, `whip_dealership`, `whip_fuel` into `resources/`, `chameleon_paint` into `resources/[assets]/`; `ensure whip_autos`, `ensure whip_autos_shop`, `ensure whip_dealership`, `ensure whip_fuel` after `ensure whip_core`; `[assets]` started by `ensure [assets]`.
- A `dependencies { 'whip_core' }` / `dependency 'whip_core'` means a whip_core restart stops the satellite first and starts it after (stated in `whip_autos/fxmanifest.lua:14-15`).

---

## whip_fuel: manifest and deps

- `shared_script`: `@whip_core/lib/satellite.lua`, `config.lua`, `shared/settings.lua` (the /whip page), `shared/pumps.lua` (pump keys).
- `client_scripts`: `@whip_core/client/world_quad.lua` (WorldQuad, the 3D prompts' quad drawer, used for pump screens), `client/tank.lua`, `client/pumps.lua`, `client/car.lua`, `client/hose.lua`, `client/stations.lua`, `client/dials.lua` (after pumps.lua).
- `server_scripts`: `server/tank.lua`, `server/pumps.lua`, `server/jerry_can.lua`, `server/hose.lua`.
- `files { 'html/pump3d/*.html' }` (DUI pages: `pump_lcd.html`, `oldpump_dial.html`).
- `data_file 'DLC_ITYP_REQUEST'` for: `stream/fuel_pump/whip_pump_lcd.ytyp` (unused screen prop), `whip_pump_torn.ytyp`, `_1a`, `_1b`, `_1d`, `whip_pump_torn_glow(.ytyp, _1a, _1b, _1d)`, `stream/hose/whip_hose_seg.ytyp`, `stream/classic_pump/whip_oldpump_dial.ytyp`, `whip_vintage_dial.ytyp`.
- Streams its own versions of `prop_gas_pump_1a/1b/1c/1d`, `prop_gas_pump_old2`, `prop_gas_pump_old3` (now old2's model with two hoses), `prop_vintage_pump`. Another resource streaming the same names clashes.
- `dependencies { 'whip_core' }`. whip_rope is detected at runtime: `GetResourceState('whip_rope') == 'started'` (`server/hose.lua:32`).
- Without whip_fuel there is no fuel at all: cars just drive (docs 094: "Without it, cars need no fuel").

## whip_fuel: config keys

`config.lua` (shared). Values saved in /whip > Settings > Fuel win over the file.

| Key | Default | Meaning |
|---|---|---|
| `Config.Tank.GtaFloor` | `5` | Tank 0-100 is mapped onto GTA fuel `GtaFloor..100` so GTA's own fuel never goes near 1% (cars can drive backwards). `0` off. Cosmetic/local only |
| `Config.Tank.GaugeOrder` | `1` | Gauge place around the rev dial, lowest at bottom |
| `Config.Tank.GaugeEnds` | `{ 'E', 'F' }` | Gauge ends instead of a number; `false` shows a percentage |
| `Config.Tank.GaugeIcon` | SVG path | Gauge icon |
| `Config.Burn.Rate` | `0.03` | % of tank per second driving steadily. Idle ~1/3, flat out 2.5x. Server cap = `abs(Rate) * 2.5` per second |
| `Config.Burn.ReportEvery` | `5` | Seconds between consume reports (passenger gauges move this often) |
| `Config.Pump.Price` | `1` | $ per 1% of a tank (half-empty tank = $50). `0` = free. Floored to integer |
| `Config.Pump.FullSeconds` | `120` | Seconds to fill an empty tank; rate = `100 / FullSeconds` %/s. Jerry can fills at the same flow |
| `Config.Pump.Reach` | `3.0` | Distance to take a nozzle (server allows `Reach + 2`) |
| `Config.Pump.Leash` | `5.0` | Walk further from the pump with the nozzle and it drops (server backstop: `Leash + 3`) |
| `Config.Pump.CarReach` | `5.0` | Distance to insert/remove at a car (server allows `+1`) |
| `Config.Pump.CarMayRoll` | `1.5` | Car may move this far while filling, else fill stops "The car moved away" |
| `Config.Pump.HoldWalk` | `'clipset@move@trash_fast_turn'` | Walk while holding a nozzle; `nil` = own walk |
| `Config.Pump.GroundSeconds` | `30` | Nozzle on the ground returns to the pump after this |
| `Config.Pump.IdleMinutes` | `5` | Nozzle left in a car with nothing done returns after this |
| `Config.Pump.TornMinutes` | `5` | A torn pump's unplugged nozzle is gone after this and the pump is back |
| `Config.Pump.SpraySeconds` | `10` | The spill: "Start Refuelling" with the nozzle on the ground or in a hand sprays this long (paid) |
| `Config.Pump.ErrorSeconds` | `60` | That side is out of order this long after a spill |
| `Config.PumpModels` | the 7 pump names | Every prop of these models anywhere works; add your map's pumps here |
| `Config.PumpCircle` | `SeenFrom = 3.5`, `UsableFrom = 1.5`, `Placing = { offset = vector3(0.0, 0.4, 1.0), heading = 0.0 }`, `PlacingByModel = { prop_gas_pump_1a..1d = { offset = vector3(0.05, -0.26, 1.2855), heading = 180.0 }, prop_gas_pump_old2/old3 = { offset = vector3(-0.25, -0.372, 0.974), heading = 180.0 } }` | Pump prompt placement. Measure with `/actionplace whip_fuel:pump` (whip_core command) and paste the copied line |
| `Config.NozzleCircle` | `Placing = { offset = vector3(0.35, -0.45, 0.8), heading = 180.0 }`, `PlacingByModel` per model; `prop_vintage_pump` has `single = true` | Nozzle prompt (Take / Put Away). Measure with `/actionplace whip_fuel:nozzle` |
| `Config.PumpPanels` | `{ prop_gas_pump_1a = 'RON', _1b = 'GLOBE OIL', _1c = 'LTD', _1d = 'XERO' }` | Pumps with whip's LCD screen and holster nozzles, and the brand shown |
| `Config.Hose.Enabled` | `true` | Hose with whip_rope; `false` = car pulls the nozzle out instead |
| `Config.Hose.Length` | `3.0` | m |
| `Config.Hose.LinkLength` | `0.125` | m between nodes (rope's default 0.25) |
| `Config.Hose.CollisionCheckSpacing` | `1` | Probe every Nth node |
| `Config.Hose.CollideWithVehicles` | `true` | |
| `Config.Hose.Model` / `ModelNoShadow` | `` `whip_hose_seg` `` / `` `whip_hose_seg_ns` `` | Hose segment models (hashes) |
| `Config.Hose.Outlets` | per model, 1-2 `vector3` in pump space | Where the hose leaves the pump; the outlet nearest that side's nozzle is used |
| `Config.Hose.OutletHeight` | `1.1` | Unlisted pump: straight up from origin |
| `Config.Hose.BreakStretch` / `BreakHoldMs` | `0.35` / `250` | Stretch held that long tears the pump off (or breaks the hose at the car) |
| `Config.Hose.MaxStretch` | `0.3` | whip_rope `maxStretch`: beyond it the hose drags its ends together |
| `Config.Hose.TornModels` | `1a = whip_pump_torn_1a`, `1b = whip_pump_torn_1b`, `1c = whip_pump_torn`, `1d = whip_pump_torn_1d` | Loose 1,400 kg copies; a pump not listed never comes away (hose breaks at car) |
| `Config.Hose.TornMass` | `1400` | kg told to the rope (prop mass can't be read) |
| `Config.Hose.TornGrip` | `6.0` | m/s^2 sliding deceleration applied by whip_fuel; `0` = game's (none) |
| `Config.Hose.TornGlow` | glow models per pump | Lit sign/canopy prop on the copy for its last seconds |
| `Config.Hose.LeakSeconds` | `20` | Torn pump leaks a burning petrol trail this long |
| `Config.Hose.FireAtBase` | `false` | Island catches fire (on: pump explodes before it can be dragged) |
| `Config.JerryCan.PourSeconds` | `3` | Pour bar (server min 500 ms) |
| `Config.StationIcon` | `{ Sprite = 361, Colour = 1 }` | Blip |
| `Config.Stations` | 27 `{ pos = vector3, label = 'Gas Station' }` | Map icons only; refuelling works at every pump regardless |
| `Config.ClassicDials.Enabled` | `true` | Old pumps' rolling counters show last sale |
| `Config.ClassicDials.LitresPerTank` | `60` | For LITERS/GALLONS drums |
| `Config.ClassicDials.SeenFrom` | `80.0` | Further pumps show 0 |

## whip_fuel: the settings page

`shared/settings.lua` -> `Whip.configPage({ label = 'Fuel', groups = ... })`:
- Group "Fuel": `Burn.Rate` (number 0.001-1, step 0.005, '%/s'), `Pump.Price` (int 0-1000), `Pump.FullSeconds` (int 5-900), `Tank.GaugeOrder` (int 1-99), `Stations` (`type = 'records'`, `maxItems = 200`, `widget = 'mapPoints'`, `marker = { sprite, colour, name }`, fields `pos` vec3 with `limits` and `here = true`, `label` string maxLen 50).
- Group "The hose": `Hose.Enabled` (bool), `Hose.Length` (1-10 step 0.5), `Hose.LeakSeconds` (0-120), `Hose.FireAtBase` (bool); the last three `shownWhen = { path = 'Hose.Enabled', equals = true }`.
- Everything else (reaches, timers, circles, outlets, dials) is config.lua only.
- Reactions: `Whip.onConfigChanged('Tank'|'Burn')` re-registers the stat (`server/tank.lua:100-101`); `'Hose'` rebuilds outlet lookups; `'Hose.Enabled'` draws/removes hoses; `'PumpModels'|'PumpCircle'|'NozzleCircle'` re-adds pump actions; `'Stations'|'StationIcon'` redraws blips.

## whip_fuel: the `fuel` vehicle stat

Registered in `server/tank.lua:37-58` inside `Whip.register`:

```lua
exports.whip_core:RegisterVehicleStat('fuel', {
  default = 100, min = 0, max = 100, persist = true,
  hud = { label = 'Fuel', icon = Config.Tank.GaugeIcon, color = '#f59e0b', order = Config.Tank.GaugeOrder or 1 },
  display = { ends = Config.Tank.GaugeEnds },        -- nil when GaugeEnds is false
  consume = { maxRate = abs(Burn.Rate) * 2.5, interval = Burn.ReportEvery or 5, driverOnly = true },
})   -- NOT clearAtMin: an empty tank stays at 0
```

- Name `fuel` is reserved for whip_fuel (docs 046). A car with no stored value reads the default: full (street cars, new cars).
- Burn: client `client/tank.lua` ticks once a second in a car; the DRIVER (seat -1, engine running, fuel > 0) calls `exports.whip_core:ConsumeVehicleStat({ entity = veh }, 'fuel', Rate * speedFactor * throttleFactor)` with `speedFactor = 1 + min(speed, 70 m/s)/70 * 1.5` and `throttleFactor = 0.3 + |throttle| * 0.7`. whip_core batches, checks driver, caps by wall clock.
- Every client in a car sets GTA's own fuel `SetVehicleFuelLevel(veh, GtaFloor + fuel * (100 - GtaFloor)/100)` (sputter/backfire effects only).
- Empty tank: server `OnVehicleStatChanged('fuel', fn, { now = 'all' })` -> `HoldVehicleEngine(vehicleId, 'empty', 'Out of fuel')`; refilled -> `ReleaseVehicleEngine(vehicleId, 'empty')`. Engine won't start / stops; car still rolls and can be pushed. Also re-checked on `whip_core:vehicle:spawned` and `whip_core:vehicle:registered`. `nil` (stat not yet registered) never holds.
- On whip_core restart the module releases every hold it had, then re-registers and re-listens.
- Electric cars: client asks `exports.whip_core:IsVehicleElectric({ entity = veh })` (cached per entity+model); if electric, sends `TriggerServerEvent('whip_fuel:electric', netId)` once per vehicleId; server (SecureEvent, must be sitting in that car) marks it and releases any hold. Electric cars burn nothing, show no gauge (`SetVehicleStatShown('fuel', fn)`), get no nozzle or jerry-can prompts.
- Gauge icon: `SetVehicleStatIcon('fuel', fn)` returns `'fuel_left'`/`'fuel_right'` from `GetVehiclePoint({ entity }, 'fuel')` when `point.fixed`, else default.
- `TankOf(vehicleId)` (server global, `server/tank.lua:105`): `level, 100.0`, nil stat read as 100.

## whip_fuel: pumps and nozzles

- No pump list: any prop of `Config.PumpModels`. Each SIDE of each pump has its own nozzle, keyed `pump_<x>_<y>_<z>_<A|B>` with the pump's position in tenths of a metre (`shared/pumps.lua: Pumps.keyOf(at, side)`), `Pumps.KEY_PATTERN = '^pump_%-?%d+_%-?%d+_%-?%d+_[AB]$'`, `Pumps.prefixOf(key)` (drops `_A`), `Pumps.otherSide(key)`, `Pumps.placingOf(model, nozzle)`, `Pumps.sideOfFace(model, face, nozzle)`. Side A faces the pump's -y, B its +y.
- Nozzle states (server `nozzles[key]`, only while out of its holster): `'hand'` (holder), `'car'` (in a filler), `'ground'` (object; back after `GroundSeconds`), `'torn'` (in a car whose pump was torn off), `'dead'` (on the ground after that; gone after `TornMinutes`).
- Nozzle in hand: `exports.whip_core:HoldProps(src, { { model = 'prop_cs_fuel_nozle', bone = 28422, offset = {0.13,0.05,0.02}, rot = {-80,0,15} } }, 'nozzle')`; removed with `DropHeldProps(src, 'nozzle')`. `whip_core:heldProps:lost` with `tag == 'whip_fuel:nozzle'`: reason `'world'` returns it to the pump, else (e.g. `'replaced'`) drops it on the ground.
- Taking the nozzle is free. Paying is at the pump: `whip_fuel:start` holds the whole price with `exports.whip_core:HoldMoney(src, price, { method = payment, reason = 'Fuel', vehicle = vehicleId })` (`vehicle`: the car row held unwritten until settle, so unpaid fuel is never saved). Each 1 s tick: `GetMoneyHold(holdId)` (gone -> stop), `SetVehicleStat(vehicleId, 'fuel', target, 'refuel:pump')`, `SpendMoneyHold(holdId, spentSoFar)`. End: `SettleMoneyHold(holdId, spent)` returns `{ spent, refunded, paidNow }`; refund not `paidNow` comes "next time you join".
- Units: whole percent, `units = ceil(100 - level)`; `'25'|'50'|'75'` add that % of the tank, capped at need; price = units x Price.
- Fill stops on: `'done'`, `'stopped'` (Stop Refuelling / nozzle out), `'moved'` (beyond `CarMayRoll`), `'gone'` (entity gone or netId reused), `'wrecked'` (`IsVehicleWrecked`), `'torn'`, `'returned'`, `'disconnected'`.
- Pulling the nozzle out mid-fill keeps pumping out of the hand as a spill until stopped or paid units run out; spill ends -> side out of order `ErrorSeconds`.
- A street car the server never saw is adopted at the fill: `exports.whip_core:AdoptVehicle({ entity = entity, player = src })` (counts against the player's street-car limit). Price quotes never adopt. Vehicle id is resolved through `GetVehicle({ entity })`, never the raw `whipVehicleId` stamp.
- Anyone at the pump may Stop Refuelling; change goes to the payer. Whoever starts pays.
- The client's word only names the pump point and model (map prop); a "pump" farther than 3 m from the point is refused; all money maths is server-side.
- Logout/drop: the nozzle in hand returns; pours paid by that player are dropped (whip_core already settled their holds); nozzles they put in cars stay.
- Resource stop: every pour settled `'disconnected'`, nozzle objects deleted, `whip_fuel:reset` to all.

## whip_fuel: SecureEvents and SecureCallbacks

All registered inside `Whip.register` (server). `KEY = { 'key', 'string', 64 }`, `CAR_ID = { 'netId', 'id', 1, 4294967295 }`, `PAYMENT = { 'payment', 'enum', { 'cash', 'bank' } }`. Callbacks answer `true` / a table, or `false, why`.

| Name | Kind | Opts | Params | Does / returns |
|---|---|---|---|---|
| `whip_fuel:faces` | Callback | `rateLimit = 2000, whileDead = true` | - | `{ [key] = faceInfo }` for every busy side |
| `whip_fuel:sales` | Callback | `rateLimit = 2000, whileDead = true` | - | `{ [prefix] = { p = $, u = % } }` last sales |
| `whip_fuel:takeNozzle` | Callback | `rateLimit = 750`, `near = { at = (x,y,z param), range = Reach + 2 }` | `side` enum A/B, `x`,`y` (+-20000), `z` (+-2000), `model` (number, default 0), `ex`,`ey`,`ez` (default 0.0), `eh` (+-720) | `true` or `false, 'You are already holding a nozzle'|'No pump there'|'This pump is gone'|'This pump is out of order'|'Its nozzle is on the ground'|'That nozzle is in use'` |
| `whip_fuel:nozzleAway` | Event | `rateLimit = 250, burst = 3, whileDead = true` | - | Hang it back (`'Too far from its pump'`, `'Stop the pump first'`) |
| `whip_fuel:drop` | Event | `rateLimit = 500, burst = 2, whileDead = true` | `netId` int 0.. (0 = none) | Holder's game dropped it / walked off / died |
| `whip_fuel:insert` | Callback | `rateLimit = 750` | `CAR_ID`, `nozzleNetId` id, `ox`,`oy`,`oz` (+-50, default 0) | Nozzle (object made by that client) into car; refusals incl. `'There is a nozzle in that car already'`, `'The hose does not reach that far'`, `'The nozzle did not go in'` |
| `whip_fuel:remove` | Callback | `rateLimit = 750, whileDead = true` | `CAR_ID`, `made` int (default 0) | Back to hand; a torn pump's goes to the ground for good |
| `whip_fuel:pickUp` | Callback | `rateLimit = 750` | `KEY` | Off the ground (within 3 m) |
| `whip_fuel:quote` | Callback | `rateLimit = 250, burst = 4` | `CAR_ID` | `{ units, price, perUnit, tank = 100 }` |
| `whip_fuel:start` | Callback | `rateLimit = 1000` | `KEY`, `amount` enum `'full'|'25'|'50'|'75'` default `'full'`, `PAYMENT` | `{ seconds, price }`; refusals `'That tank is already full'`, `'That car is wrecked'`, `'Already refuelling'`, payment errors |
| `whip_fuel:spray` | Callback | `rateLimit = 1000` | `KEY`, `PAYMENT` | Spill; `{ seconds, price }` |
| `whip_fuel:stop` | Event | `rateLimit = 250, burst = 3, whileDead = true` | `KEY` | Stop a pour (at the pump) |
| `whip_fuel:electric` | Event | `rateLimit = 1000, burst = 3` | `netId` id | Driver says the car is electric |
| `whip_fuel:pourCan` | Event | `rateLimit = 2000` | `netId` id | Pour can in hand into car |
| `whip_fuel:fillCan` | Event | `rateLimit = 1000, burst = 2`, `onReject` -> `whip_fuel:canFillEnded`, `near = { at = x,y,z, range = Reach + 2 }` | `payment` enum, `x`,`y`,`z` | Fill can at pump |
| `whip_fuel:tornCopy` | Event | `rateLimit = 250, burst = 2, whileDead = true` | `key` string 64, `netId` int (0), `why` string 40 ('') | The car's game made (or failed) the torn copy |
| `whip_fuel:tornCopyFree` | Event | same | `key`, `tied`,`gone`,`owned` bool (false) | Maker let the copy go |

`faceInfo(key)` (sent as `whip_fuel:face`): `nil` while the nozzle hangs and the side works; else `{ n = state, h = holder, car = netId, obj = netId, p = { e = seconds in, s = seconds total, u = units paid, c = $/unit, spray? }, sp = spill price (hand/ground), err = seconds out of order, gone = pump torn }`.

## whip_fuel: server events other resources can hear

Fired with `TriggerEvent` (server-local) from `server/pumps.lua`; `pump = { x, y, z, model, at, heading }`:

| Event | Payload |
|---|---|
| `whip_fuel:nozzleTaken` | `{ source, key, pump }` |
| `whip_fuel:nozzleInserted` | `{ source, key, pump, vehicleNetId, nozzleNetId, hoseOffset? }` |
| `whip_fuel:nozzleRemoved` | `{ source, key, pump }` |
| `whip_fuel:nozzleDropped` | `{ key, nozzleNetId, dead? }` |
| `whip_fuel:nozzlePickedUp` | `{ source, key, pump }` |
| `whip_fuel:nozzleTorn` | `{ key, pump, nozzleNetId, other? }`; `other = { key, state = 'car'|'hand', holder? }` |
| `whip_fuel:nozzleReturned` | `{ key, reason, pump }`; reasons `'put away'`, `'ground'`, `'idle'`, `'gone'`, `'pulled'`, `'expired'`, `'logout'`, `'torn'`, `'destroyed'`, `'world'` |
| `whip_fuel:pumpBack` | `{ prefix }` (torn pump back on its island) |

These are plain events: there is no invoking-resource check on them (hose.lua consumes them the same way).

## whip_fuel: net events to clients

`whip_fuel:face(key, info|nil)` (all), `whip_fuel:hand(key|nil, {x,y,z}|nil)` (holder), `whip_fuel:sale(prefix, { p, u })` (all), `whip_fuel:reset` (all, on stop), `whip_fuel:canFillEnded` (filler), `whip_fuel:makeTornCopy(key, pumpEnd, tornModel)` (car owner), `whip_fuel:tornCopyTied(key, ropeId)` (maker), `whip_fuel:tornCopyRefused(key)`, `whip_fuel:pumpFree(key)`, `whip_fuel:pumpTorn(key, pumpEnd, late, copyNetId, agoMs, free)` (all, and to a loading player), `whip_fuel:pumpRepaired(pumpEnd)`.

## whip_fuel: prompts (actions) players see

Built with `exports.whip_core:AddAction` / `Whip.core:AddAction` (client):
- `id = 'pump'`: `at = { model = Config.PumpModels, faces = 2, offset, heading, perModel }`, `press = true`, `seeFrom = PumpCircle.SeenFrom`, `reach = PumpCircle.UsableFrom`. Options: `fillcan` "Fill Jerry Can" (`require = { held = 'jerry_can' }`, `options = PAY`, `press = false`), `tankfull` "Tank Is Full", `fillfull` "Fill Up  $N", `fill25|fill50|fill75` "Add N%  $N", `stop` "Stop Refuelling", `spray` "Start Refuelling  $N", `broken` "Pump Gone"/"Out of Order". `PAY` sub-options `{ id = 'cash', label = 'Pay Cash' }`, `{ id = 'bank', label = 'Pay by Bank' }`. Busy options only while a busy side is within 25 m (re-added on change, to keep canInteract crossings cheap).
- `id = 'nozzle'` (2 faces) / `'nozzle1'` (`single` pumps): "Take Nozzle" (`take`) or "Put Nozzle Away" (`putaway`, 750 ms grace after taking).
- `id = 'pumpHolsters'`: hidden (`enabled = false`), only `onFound`/`onLost` to place holster nozzles on panel pumps within range.
- Per ground nozzle: "Pick Up Nozzle".
- Car (`client/car.lua`), `first = true`: `nozzle_in:<part>` "Insert Nozzle" and `nozzle_out:<part>` "Remove Nozzle" on vehicle parts `'fuel'`, `'bike'`, `'boat'` (added only while wanted); `jerrycan:<door>` "Refuel (jerry can)" on `door_dside_f`, `door_pside_f`, `door_dside_r`, `door_pside_r`, `bike`, `boat` with `require = { held = 'jerry_can' }`.
- Client hook: `RegisterClientHook('freeHands', onFreeHands)`; walk via `SetWalkOverride`; controls via `Whip.core:BlockControls('nozzle', { controls = list })`.

## whip_fuel: jerry cans

- Any item def with `fuelCapacity` (percent of a tank a FULL can holds) is a fuel can server-side; metadata `fuel` = how full (0-100). whip_gunny's `jerry_can` has `fuelCapacity = 30` (`whip_gunny/items/weapons.lua:1009-1015`) and is equipped as `WEAPON_PETROLCAN`; gunny calls `SetHeldItem`, whip_fuel reads `exports.whip_core:GetHeldItem(src)` -> `{ addr, item, amount, metadata }` and `GetItemDef(item).fuelCapacity`. A new can is empty.
- Pour (`whip_fuel:pourCan`): adopt street car if needed; refuse full tank; server bar `Whip.core:Progress(src, { label = 'Refueling...', duration = PourSeconds*1000, canCancel = true, near = { vehicle = vehicleId, range = CarReach + 1 }, item = { item, metadata } })`; re-check after bar; `SetVehicleStat(vehicleId, 'fuel', target, 'jerry_can')` FIRST, then `SetItemMetadata(addr, { fuel = left% })` (not quiet: that push tells gunny the can is lighter).
- Fill at pump (`whip_fuel:fillCan`): units = `ceil((100 - level)/100 * capacity)`, price = units x Pump.Price; pre-check cash (`GetPlayerCash`) or `GetDefaultBankAccount(src).balance`; bar duration `units / (100/FullSeconds)` s (min 1 s); after: `SetItemMetadata(addr, { fuel = 100 })` then `ChargePlayer(src, price, { method, reason = 'Fuel: jerry can' })` in the same handler (one transaction); refused -> metadata put back. Stopped bar = nothing paid. Not allowed with a nozzle in hand.

## whip_fuel: the hose and torn pumps (whip_rope)

`server/hose.lua` is the worked example of whip_rope's rope API (docs 081):
- On `whip_fuel:nozzleTaken`, `exports.whip_rope:CreateRope({ kind = 'hose', player, origin = pumpEnd, tail = { type = 'held', heldBy = src }, length = Hose.Length, link = Hose.LinkLength, locked = true, look = { model, modelNoShadow, thickness = 1.0 }, collide = { spacing, vehicles }, heldAt = { model = 'prop_cs_fuel_nozle', offset = { x = 0, y = -0.027, z = -0.2 } }, watch = { stretch = BreakStretch, holdMs = BreakHoldMs, broken = true }, maxStretch = MaxStretch })`, all inside `pcall`.
- Pump end: `{ type = 'object', netId = 0, model, still = true, worldPos, heading, offset = outlet, point }` (map prop anchor), or `{ type = 'fixed', pos }`.
- Tail moves with `SetRopeEnd(id, 'tail', end)`: `vehicle` (with `hoseOffset` from the inserting client), `held`, `object` (nozzle on the ground). `RemoveRope(id)` when returned.
- `whip_rope:ropeStretched(id, resource)` (only own ropes, tail on a vehicle): a pump in `TornModels` comes away, else `Fuel.breakaway` (hose breaks at the car, nozzle drops, still-pumping fill becomes a spill).
- Tear sequence (never visible): server asks the car's network owner `whip_fuel:makeTornCopy` -> client makes FROZEN copy inside the island pump -> `whip_fuel:tornCopy` (3 s timeout `COPY_WAIT_MS` else breakaway; copy must be first-owned by that client, of the torn model, within 3 m) -> server `SetEntityOrphanMode(copy, 2)`, `Fuel.pumpTorn`, moves both sides' hose origins to the copy with `mass = TornMass` -> `whip_fuel:tornCopyTied` -> maker hides the island pump then lets copy go (`whip_fuel:tornCopyFree`; server frees it itself after 4 s) -> `whip_fuel:pumpFree` to all. Each step prints `[whip_fuel] torn pump <key>: ...` to the server console.
- Torn pump's other side: in another car -> that car is on the pump too; in a hand -> whip_rope drags the holder (Config.Drag), dropped after 30 s at the latest; else returned.
- `whip_rope:ropeEndBroken(id, 'origin', resource)`: pump blown up -> both nozzles return (`Fuel.pumpDestroyed`).
- `whip_rope:ropeRemoved` (e.g. admin `/clearropes`): forgotten; nozzle behaves as hoseless.
- whip_rope stop: hoses forgotten; whip_rope start: after 1 s, `drawMissing()` redraws a hose for every nozzle out (docs 081: ropes die silently with whip_rope and ids restart from 1).
- Without a hose (`hasHose(key)` false): a car more than `Leash + 1` from the pump pulls the nozzle out (`'pulled'`).

## whip_fuel: screens, dials, map icons

- Panel pumps (1a-1d): one DUI `html/pump3d/pump_lcd.html?atlas=1280x1024&cells=...` drawn as world quads over each busy side's LCD within 20 m (nearest full-size cell, rest half-size, up to 13 cells); released 15 s after last screen; shows fill progress, thank-you 4 s, ERROR on torn sides.
- Old pumps (`old2`, `old3`, `prop_vintage_pump`): overlays `whip_oldpump_dial_<n>` / `whip_vintage_dial_<n>` show cell n of `html/pump3d/oldpump_dial.html?atlas=bands|vintage` (4 cells per kind: four nearest pumps with a sale within `ClassicDials.SeenFrom`). Last sale kept until server restart.
- Map icons: blips from `Config.Stations` drawn on `whip_core:player:loaded`, cleared on logout.

## whip_fuel: using fuel from your resource

- There is no `SetVehicleFuel`/`GetFuel` export. Use whip_core's stat exports: `exports.whip_core:GetVehicleStat(vehicleId, 'fuel')`, `SetVehicleStat(vehicleId, 'fuel', 100, 'myres:reason')`, `AddVehicleStat`, `OnVehicleStatChanged('fuel', fn)`; client `GetVehicleStat({ entity = veh }, 'fuel')` (replicated). whip_fuel must be running (docs 103, 006: replaces `SetFuel`).
- New owned cars: `CreateOwnedVehicle(src, { model, stats = { fuel = 100.0 } }, ...)` (dealership does this).
- An item can be a fuel can by `fuelCapacity` on its def (docs 033) - but see Docs vs code: the client prompts only appear for `jerry_can`.

## whip_fuel: lessons

1. Fuel is a declared vehicle stat, not a script variable: whip_core saves, replicates, caps client reports (`consume` with `driverOnly`), and draws the gauge.
2. Long services billed per tick use `HoldMoney` / `SpendMoneyHold` / `SettleMoneyHold` with `vehicle =` so the car row is held until paid; `GetMoneyHold` before each tick.
3. Single paid instant actions (`fillCan`) call `ChargePlayer` inside the SecureEvent so item metadata and payment commit together; undo the metadata on refusal.
4. Client sends only network ids and choices; prices, reach, and car identity are resolved server-side (`GetVehicle({ entity })`, never a stamp).
5. Objects a client creates are accepted only if `NetworkGetFirstEntityOwner(obj) == src`, the right model, near the right place; otherwise deleted.
6. Optional dependency (whip_rope) is feature-detected and every call is `pcall`ed; redraw on its `onResourceStart`.
7. `onReject` on a SecureEvent whose client waits on an answer (`fillCan`), so the client never hangs.
8. Callbacks needed at character load use `whileDead = true` or a dead-loading character sees blank pumps.

---

## whip_autos: manifest and deps

- `shared_script`s in order: satellite, `config.lua`, `shared/shop.lua`, `shared/tuning.lua`, `shared/power.lua`, `shared/settings.lua` (after config and power), `shared/goals.lua`, `shared/director.lua`.
- `server_scripts`: `server/main.lua`, `server/director.lua`, `server/engines.lua`, `server/tuning.lua`, `server/look.lua`, `server/dev.lua`, `server/power/turbo.lua`, `server/power/nitrous.lua`.
- `client_scripts`: `@whip_core/lib/cost.lua` (WhipCost for `/whipcost`), `client/boxfit.lua`, `camera.lua`, `catalogue.lua`, `tuning.lua`, `session.lua`, `director.lua`, `look.lua`, `ui.lua`, `main.lua`, `dev.lua`, `power/handling.lua`, `power/turbo.lua`, `power/nitrous.lua`, `power/top_speed.lua`, `power/shift_time.lua`, `power/gearbox.lua`.
- `ui_page 'html/index.html'`, `nui_callback_strict_mode 'true'`. `files`: `html/index.html`, `html/js/*.js` (app.js state/rules, view.js + kit.js drawing, three.module.min.js r170), `html/img/wheels|mods|art/*.webp`, `html/img/art/*.svg`, `html/img/pad/*.svg`, `html/fonts/*.woff2`, `html/img/items/*.webp` (whip_core looks for an item's picture here: `nitro.webp`). One `files` line per folder: a `*` in a folder name matches nothing.
- `dependencies { 'whip_core' }`. Building is separate (`whip_autos_shop`) so restarting autos/core never unloads an interior under players. Chameleon ramps are separate (`chameleon_paint`): without it paints 161-222 turn a car black.

## whip_autos: config keys

`config.lua` (shared; server charges from its own copy, client only displays).

| Key | Default | Notes |
|---|---|---|
| `Config.Shop` | `{ label = 'Whiplash', coords = vector3(-336.23, -116.73, 38.70), radius = 3.0, marker = false }` | The lift. Driver on it opens from the F1 radial. Pay range = radius + 4. `marker` = pink cylinder (thread only while on) |
| `Config.WhoCanModify` | `'anyone'` | `'anyone'` / `'ownerTuning'` (owner only for performance+tuning) / `'owner'` (owner only; others repair only). Unowned cars: open to the driver |
| `Config.Camera` | `followParts = true`, `blendRate = 3.0`, `pitchMin = -12`, `pitchMax = 60`, `zoomMin = 0.25`, `zoomMax = 2.20`, `zoomStep = 0.10`, `turntable = { enabled = false, delay = 2.0, speed = 8.0 }`, `enterTime = 0.85`, `enterRateMin = 2.6`, `enterRateMax = 20.0`, `sensitivity = 1.0`, `yawSpeed = 16`, `pitchSpeed = 10`, `deadzone = 0.005`, `invertX/Y = false`, `framings = { default, spoiler, frontbumper, rearbumper, sideskirt, exhaust, rollcage, grille, hood, roof, trim, wheels, wheelpaint, livery }` (each `{ yaw, pitch, distRatio, aim = {x,y,z}, aimPitch?, aimYaw?, fov }`), `default = 'default'`, `shiftedYaw = 207.0` | Shots measured from the car's size |
| `Config.Areas` | slot -> framing name | e.g. `[0] = 'spoiler'`, `[23] = 'wheels'`, `neon = 'default'`, `wheelcolor = 'wheelpaint'`, `interior = 'trim'` |
| `Config.Cosmetics` | list `{ id, name, price }` for slots 0-10, 14, 25-47, 49 | e.g. Spoilers 1200, Front Bumper 2400, Hydraulics (38) 4500 |
| `Config.Wheels` | `{ 23 'Wheels' 3400 }`, `{ 24 'Rear Wheels' 3400 }` | |
| `Config.WheelCategories` | `[0] 'Sport'` .. `[12] 'Track'` | GTA wheel types |
| `Config.Performance` | `11 Engine 12000`, `12 Brakes 8000`, `13 Transmission 11000`, `15 Suspension 6500`, `16 Armour 9000` | Price per level |
| `Config.Toggles` | `18 Turbo 0` (unused: stages priced), `20 Tyre Smoke 1500`, `22 Xenon Lights 2500` | |
| `Config.TyreSmokeColours` | `colourPrice = 500`, 11 options, White first; `Patriot` (0,0,0) = GTA's red-white-blue | |
| `Config.Extras` | `price = 500` | Each switch |
| `Config.XenonColours` | `colourPrice = 750`, `{ index = 255 'Stock' }` first then 0-12 | |
| `Config.Neon` | `price = 3000`, `colourPrice = 750`, 13 colours | Cars only |
| `Config.WindowTints` | `price = 1500`, options index 0-6 (`4` = Stock, free) | |
| `Config.PaintTargets` | `color1` 1800, `color2` 1400, `pearl` 2200 (prop `pearlescent`), `wheelcolor` 900, `interior` 1200 (`interiorColor`), `dashboard` 1200 (`dashboardColor`) | `{ id, name, price, prop }` |
| `Config.PaintExtras` | `{ id = 48, name = 'Livery', price = 2800 }` | |
| `Config.PaintFamilies` | `order = { 'Classic','Metallic','Matte','Util','Worn','Metals','Chameleon' }`, `map` by first word, `default = 'Classic'` | |
| `Config.Colours` | indices 0-222 `{ index, name, hex, hex2?, family? }` | 161-222 Chameleon (build 2612+) |
| `Config.Services` | `{ { id = 'repair', name = 'Repair', desc, price = 1000 } }` | New entries need code |
| `Config.Sections` | `cosmetics`, `wheels`, `performance`, `extras`, `paints`, `tuning` with `framing` | |
| `Config.Tuning` | `EngineSwapPrice = 25000`, `StancePrice = 15000`, `SetupPrice = 15000`, `DrivetrainPrice = 20000`, `MinDriveForce = 0.10`, `MaxDriveForce = false`, `SoundOnlyEngineClasses = { 14, 15, 16 }`, `HiddenEngineClasses = {}`, `EngineSoundOverrides = {}` | Stance/setup/drive bought once per car then free |
| `Config.Tuning.Stance` | `Height {-16,16,0.5}`, `Track {-5,10,0.5}`, `Camber {-12,4,0.5}`, `Width {80,140,5}`, `Size {70,250,5}` (`{min,max,step}`), `PhysicalHeight = false`, `Travel = { perCm = 0, min = 0.3, max = 2.0 }`, `DrawRange = 150`, `FrameRange = 60`, `NearRange = 25`, `NearCount = 6`, `FarEvery = 3`, `SettledFrames = 1`, `Mode = 'handling'` (`'follow'` fallback) | Server clamps and snaps |
| `Config.Tuning.Setup` | `Springs {50,200,5}`, `Dampers {50,200,5}`, `AntiRoll {10,200,5}`, `Steering {80,170,5}`, `Grip {70,130,1}`, `Handbrake {50,250,10}` | % of stock |
| `Config.Tuning.Drive` | `Split {30,70,5}` | AWD front share % |
| `Config.Turbo` | `Stages = { {psi=5,price=10000}, {10,15000}, {15,20000}, {20,25000}, {25,30000}, {30,35000} }`, `TorquePerPsi = 0.033`, `SpoolFastest = 0.5`, `SpoolSlowest = 3.0`, `ShiftLossMin = 20`, `ShiftLossMax = 50` | psi whole 1-30, unique; never remove or re-psi a sold stage |
| `Config.Nitrous` | `Torque = 3.0`, `BottleSeconds = 20`, `InstallSeconds = 10` | |
| `Config.TopSpeedBonusMph` | `35` | Every car/bike, via gearing; `0` off |
| `Config.RealisticShifting` | `true` | |
| `Config.TransmissionBestShare` | `0.09` | Fully upgraded share of stock shift time |
| `Config.TransmissionSteps` | `{ 0.25, 0.5, 1.0 }` | |
| `Config.ShiftTimeByClass` | Compacts 3.7, Sedans 2.6, SUVs 2.2, Coupes 2.4, Muscle 3.0, SportsClassics 3.0, Sports 1.6, Super 2.2, Motorcycles 4.0, OffRoad 4.0, Industrial 2.6, Utility 2.6, Vans 2.5, Service 2.5, Emergency 2.8, Military 3.0, Commercial 5.0, OpenWheel 2.0 | 0.25-5, 1 = GTA |
| `Config.PlainShiftTimeByClass` | all `1.0` | When realistic off |
| `Config.ShiftTimeByModel` | `{}` | `{ sultan = 1.5 }` |
| `Config.Gearbox` | `Enabled = true`, `EcoUpRpm = 0.30`, `EcoDownRpm = 0.21`, `SportDownRpm = 0.55`, `CoastDownRpm = 0.21`, `RiseSeconds = 1.0`, `FallSeconds = 4.0`, `Kickdown = 0.8`, `KickdownRoom = 0.10`, `HandsOff = 0.92` | Controller only |
| `Config.EngineDumpAt` | `vector3(-670.59, -2186.69, 5.99)` | /whiplashengines spawns 60 m below, one at a time |

`PowerClasses` (shared/power.lua): classes 0-12, 17-20, 22 (never 13 bicycles, 14 boats, 15 helis, 16 planes, 21 trains) -> `{ key, label }` used by top speed, shifting, nitrous.

## whip_autos: the settings page

`shared/settings.lua` -> `Whip.configPage({ label = 'Autos', groups = ... })`:
- "The shop": `Shop.label` (string 30), `Shop.coords` (vec3, `here = true`), `Shop.radius` (1-50 m), `WhoCanModify` (enum), `Camera.followParts` (bool).
- "Price list": `Tuning` record (4 prices), `priceList()` records for `Cosmetics`, `Wheels`, `Performance`, `Toggles`, `PaintTargets`, `PaintExtras`, `Services` (`minItems = maxItems = #rows`: names/prices only, ids are config.lua's), single prices `TyreSmokeColours.colourPrice`, `XenonColours.colourPrice`, `WindowTints.price`, `Neon.price`, `Neon.colourPrice`, `Extras.price`.
- "Power": `Turbo` record (`TorquePerPsi` 0-0.1, `SpoolFastest`/`SpoolSlowest` 0.3-30 s with cross check, `ShiftLossMin/Max` 0-90 %), `Nitrous` record (`Torque` 1-10, `BottleSeconds` 2-120, `InstallSeconds` 1-60), `TopSpeedBonusMph` 0-200, `Tuning.MinDriveForce` 0.01-5, `Tuning.MaxDriveForce` (`offWhenEmpty = true`, `emptyLabel = 'no cap'`), `Gearbox.Enabled`.
- "Shifting": `RealisticShifting`, `ShiftTimeByClass` record (shownWhen realistic), `ShiftTimeByModel` (`type = 'map'`, `keyPattern = '^[%w_]+$'`).
- "How far the sliders go": `Tuning.Stance`, `Tuning.Setup`, `Tuning.Drive` limits; each min/max must be a whole step and contain neutral (0 or 100, 50 for Split) via `cross` validators; `Travel.*` have `apply = 'restart'`.
- `Config.Turbo.Stages` is NOT on the page (config.lua only).
- Out-of-range config values leave the row off the page (whip_core prints which) and `shared/power.lua` clamps reads.
- Derived lookups are rebuilt in place on change (`refill` keeps table identity): `SHOP_PAINT_PROP`, `SHOP_SERVICES`, `SHOP_XENON_COLOUR`, `SHOP_SMOKE_COLOUR`, `SHOP_NEON_COLOUR`, `PERFORMANCE_SLOT`, server `priceBySlot`/`VALID_COLOUR`/`VALID_TINT`, `PowerTurbo.stages`.

## whip_autos: the shop flow

1. Radial: client `AddAction({ id = 'enter', at = { radial = true }, label = 'Enter ' .. Config.Shop.label, icon = 'turbo', group = 'whip_autos', canInteract = Session.canEnter (natives only), onSelect = Session.open })`. Re-added when `Shop.label` changes.
2. `Session.open`: `Whip.core:ResolveVehicle(veh)` (adopts street cars) -> `Whip.core:Callback('whip_autos:claim'|'whip_autos:claimAnywhere'|'whip_autos:claimDirector', vId)` -> answer `true, may` (`'all'|'looks'|'repair'`) -> `Whip.core:TakeVehicleControl({ entity }, { attempts = 3, wait = 600 })` -> `GetVehicleProperties` snapshot -> `Whip.core:HoldVehicleAppearance(vId, true)` (WHIP doesn't record the unpaid preview as the car's look; if autos stops, WHIP restores) -> `Whip.core:SetScreenOpen(true, 'session')` -> `BlockControls('shop', ...)` -> UI.
3. Preview: networked mods on the real car (bystanders see them); tuning slots preview locally via client/tuning.lua.
4. Purchase: `TriggerServerEvent('whip_autos:server:purchase', vehicleId, method, lines, shown)`; result via `whip_autos:client:purchaseResult(ok, err, total, repairing)`.
5. End: every exit restores: page close / `whip_autos:server:release`, leaving the driver seat (`whip_core:vehicle:exited`, or `whip_core:vehicle:entered` with `seat ~= -1`), `playerDropped`, `onResourceStop` -> `RestoreVehicleAppearance(vehicleId)`. A successful purchase ends the session WITHOUT a restore.
- Sessions: one per car, one car per player; another player's claim counts only while they still drive it (`IsPlayerDrivingVehicle`).
- `onPurchase` checks: basket non-empty; `'free'` only with `HasDevTools(source)`; session owner; still driving; car exists; `ShopMayChange` asked AGAIN at payment; lines outside permission dropped (printed); duplicate slots dropped; each kind's index range validated; lines already fitted on the STORED look dropped (`ShopFitted`); Director goal coverage subtracted (`DirectorGoals.cover`); `total > shown` (shown >= 0, not free) refused "The prices changed while you were here. Leave and come back to see them."; `ChargePlayer(source, total, { method = bank|cash, reason = 'Whiplash customisation' })`; `TuningServer.write` = one `SetVehicleAppearance(vehicleId, props, { data, clearData })`; failure -> `RefundPlayer(receipt)` (console `refunded` or `COULD NOT REFUND`); repair -> `ClearVehicleDamage(vehicleId)` and client repairs entity; session car (`def.session`, no saved record) -> notify "work lasts as long as the car does"; free order -> `LogActivity(source, 'whiplash_free', { detail })`; `DirectorGoals.purchased`.

## whip_autos: SecureEvents, SecureCallbacks, NUI callbacks, net events

`SHOP_NEAR = { at = fn (player position for an `anywhere` session opened by Director or a devtools player, else Config.Shop.coords), range = fn -> (Config.Shop.radius or 6.0) + 4.0, message = 'Drive onto the Whiplash floor first' }`.

| Name | Kind | Opts | Params |
|---|---|---|---|
| `whip_autos:claim` | Callback | `rateLimit = 1000`, `near = SHOP_NEAR` | `{ 'vehicleId', 'id' }` -> `true, may` / `false, why` |
| `whip_autos:claimAnywhere` | Callback | `ace = 'whip.devtools'`, `rateLimit = 1000` | vehicleId |
| `whip_autos:claimDirector` | Callback | `rateLimit = 1000` | vehicleId; needs a Director grant |
| `whip_autos:server:release` | Event | `whileDead = true`, `rateLimit = 500, burst = 3` | vehicleId |
| `whip_autos:server:purchase` | Event | `rateLimit = 3000, burst = 2`, `near = SHOP_NEAR`, `onReject` -> purchaseResult false | `vehicleId` id; `method` enum `cash|bank|free`; `basket` `list` of `{ slot any, index id -1..255, wheelType any, engine any, stance any, setup any, drive any }` max 40; `shown` int 0..1e9 default -1 |
| `whip_autos:cash` | Callback | `rateLimit = 500, burst = 2` | -> `GetPlayerCash(source)` |
| `whip_autos:engineList` | Callback | `rateLimit = 2000` | only with a session or `HasPermission(source, 'director.build')`; ~60 KB list |
| `whip_autos:engineData` | Callback | `rateLimit = 500` | `{ 'model', 'string', 64 }` -> `Engines.data(model)` |
| `whip_autos:engineDumpAllowed` | Callback | `ace = 'whip.devtools'`, `requirePlayer = false`, `rateLimit = 1000` | -> true |
| `whip_autos:server:engineDumpChunk` | Event | `ace = 'whip.devtools'`, `requirePlayer = false`, `rateLimit = 100, burst = 10` | `{ 'chunk', 'any' }` = `{ run, index, total (<=1000), entries }` |
| `whip_autos:server:devTune` | Event | `ace = 'whip.devtools'`, `rateLimit = 500` | `what` enum `engine|stance|setup|drive|clear`, `args` any |
| `whip_autos:server:nitroFlames` | Event | `rateLimit = 150, burst = 4, sheet = 'light'` | `{ 'on', 'bool' }` |
| `whip_autos:server:taskOpen` | Event | `rateLimit = 1000, burst = 3` | `{ 'netId', 'id' }`; sender must own the entity and car must be in a run (`GetScenarioRunOf({ netId }, { tests = true })`) |
| `whip_autos:server:carMost` | Event | `rateLimit = 2000, burst = 3` | `hash` int, `most` int 0..1e8; stored in resource KVP `most:<hash>` only during a session |

- NUI callbacks (`client/ui.lua`, each wrapped by `cb()` that `pcall`s and always answers `done({})`): `focus`, `preview`, `add`, `remove`, `close`, `cash`, `shown`, `camera`, `layout`, `typing`, `checkout`, `saveLook`.
- Net events to client: `whip_autos:client:purchaseResult(ok, err, total, repairing)`, `whip_autos:client:cash(count)` (pushed on `whip_core:item:added|removed` with `item == 'cash'`), `whip_autos:client:nitroFlames(netId, on)` (relayed to players within 300 m except sender), `whip_autos:client:engineDumpSaved(ok, count)`, `whip_autos:client:forceOpen(netId, candidates)`, `whip_autos:client:job(netId, job|false)`.
- whip_core events consumed: server `whip_core:vehicle:exited`, `whip_core:vehicle:entered`, `whip_core:vehicle:spawned` (only if `GetInvokingResource() == 'whip_core'`), `whip_core:item:added`, `whip_core:item:removed`, `whip_core:run:thingMade`, `whip_core:run:playerLeft`, `whip_core:run:playerJoined`; client `whip_core:vehicle:entered/exited`, `whip_core:pad:deviceChanged`, `whip_core:player:died`, `whip_core:devtools:modeChanged`, `whip_core:director:builderCopy`, `whip_core:vehicle:copied`.

## whip_autos: basket lines and slot ids

A line: `{ slot, index, wheelType?, engine?, stance?, setup?, drive? }`.

| slot | index meaning | price |
|---|---|---|
| number 0-49 (mod slot) | -1 stock (free), 0..99 part | `priceBySlot[slot]` |
| `23`, `24` | wheel index; `wheelType` 0-12 required to match range | Wheels price |
| `48` | mod livery, or `100 + n` = model livery n (`SHOP_MODEL_LIVERY = 100`; sets `props.livery = n`, `mods['48'] = -1`) | 2800 |
| `18` | turbo stage 1..#Stages, 0 off (stored as tuning data `turbo = { psi }` + `props.turbo = true` for GTA's sound part) | stage price; off free |
| `22` | 0 off, 1.. `XenonColours.options[n]` | fitting 2500, colour change on fitted 750 |
| `20` | 0 off, 1.. smoke colour | 1500, colour change 500 |
| `'tint'` | GTA tint index (4 stock, free) | 1500 |
| `'neon'` | bitmask 0-15 (1 left, 2 right, 4 front, 8 back; sold layouts 4, 8, 3, 12, 7, 11, 15) | 3000, off free |
| `'neoncolor'` | 1..#Neon.colours | 750 |
| `'color1'`,`'color2'`,`'pearl'`,`'wheelcolor'`,`'interior'`,`'dashboard'` | GTA paint index in `Config.Colours` | per target |
| `'extra1'..'extra14'` | 0 off, 1 on | 500 |
| `'repair'` | pinned to 1; sets `dirtLevel = 0.0`, server `ClearVehicleDamage`, client fixes entity | 1000 |
| `'engine'` | `engine = '<model>'|'stock'` (<= 40 chars) | `EngineSwapPrice`, stock free |
| `'stance'` | `stance = { height, trackF, trackR, camberF, camberR, width, size }` | once `StancePrice`, then free |
| `'setup'` | `setup = { springs, dampers, antiroll, steering, grip, handbrake }` (%) | once `SetupPrice` |
| `'drive'` | `drive = { layout = 'stock'|'fwd'|'rwd'|'awd', front = 30..70 }` | once `DrivetrainPrice` |

Shared helpers (globals): `ShopMayChange(charId, ownerCharId)` -> `'all'|'looks'|'repair'`; `ShopIsPerformance(slot)` (18, Config.Performance slots, tuning slots; xenons are looks); `ShopFitted(props, line, turboIndex)`; `ShopNeonLayout(sides)`, `ShopNeonSides(index)`, `ShopNeonColourIndex(rgb)`, `ShopXenonIndex(on, colour)`, `ShopSmokeIndex(on, rgb)`, `ShopModelLiveryOf(index)`, `ShopExtraOf(slot)`, `SHOP_EXTRA_LAST = 14`, `ShopPropsFromLines(lines)` (server).

## whip_autos: tuning as VehicleData

`shared/tuning.lua` keys (VehicleData owned by whip_autos):

| Key | Value |
|---|---|
| `engine` (`TUNING_ENGINE_KEY`) | `{ v = 1, model, label, sound, mass, drive = { fInitialDriveForce, fDriveInertia, nInitialDriveGears, fClutchChangeRateScaleUpShift, fClutchChangeRateScaleDownShift, fInitialDriveMaxFlatVel }, soundOnly? }` |
| `stance` | `{ v = 1, height, trackF, trackR, camberF, camberR, width, size }` (cm/deg/%) |
| `setup` | `{ v = 1, springs, dampers, antiroll, steering, grip, handbrake }` (% of stock) multiplying `fSuspensionForce`, `fSuspensionCompDamp`+`fSuspensionReboundDamp`, `fAntiRollBarForce`, `fSteeringLock`, `fTractionCurveMax`+`fTractionCurveMin`, `fHandBrakeForce` |
| `drive` | `{ v = 1, layout, front }` |
| `turbo` (`TUNING_TURBO_KEY`) | `{ psi }` |
| `turbo_mod` (server/power/turbo.lua `GTA_TURBO_NOTE`) | `true` when whip_autos itself put GTA's turbo part on (so only it takes it off) |

- Write: `TuningServer.write(vehicleId, changes, props)` = `exports.whip_core:SetVehicleAppearance(vehicleId, props or {}, { data = { key = value }, clearData = { keys } })`: one atomic write with the payment in the same SecureEvent.
- Clean/clamp: `TuningCleanStance`, `TuningCleanSetup`, `TuningCleanDrive` (missing field = neutral; clamp then snap to step).
- Swapped engine force: `donor.fInitialDriveForce * donor.mass / car.fMass`, capped by `MaxDriveForce`, floored at `MinDriveForce` (`TuningEngineSet`). Sound-only classes 14/15/16 swap only the sound (`soundOnly = true`; sound name = model unless `EngineSoundOverrides` names another), and clients call `Whip.core:SetVehicleRevRange({ entity = entity }, model)` so the rev dial follows the swap (`client/tuning.lua:77`).
- Applied by every client via `exports.whip_core:WatchVehicleData(key, opts)` inside `Whip.register`: ids `engineSound` (all cars in view: `onGained/onChanged/onLost`), `enginePower` (`driverOnly = true`, `onStart/onStop`: `SetVehicleHandlingLayer({ entity }, 'engine', { set = set })` / `ClearVehicleHandlingLayer('engine')`), `stanceLooks` (all), `setup` (driverOnly, layer `'setup'` with `{ scale = ... }`), `drive` (all), `stanceHeight` (driverOnly, layer `'stance'` on `fSuspensionRaise`).
- Pricing (`TuningServer.price`): value identical to stored -> `0, nil` (dropped); engine 'stock' free; stance/setup/drive paid once then any change free.

## whip_autos: engines.json and /whiplashengines

- `engines.json` at resource root: `{ schema = 1, builtAt = 'YYYY-MM-DD HH:MM:SS', builtBy = name, engines = { [model] = { label, class, mass, drive = { 6 fields above }, topSpeed, accel } } }`. The shipped file has 833 engines, built 2026-09-29.
- Missing/unreadable -> `Whip.startProblem(...)`: engine swaps offer nothing.
- `/whiplashengines` (client, `whip.devtools`): asks `engineDumpAllowed`, spawns every vehicle model 60 m below `Config.EngineDumpAt`, reads handling, sends chunks (`engineDumpChunk`); list replaced only when all chunks of a run arrived; `SaveResourceFile`; reply `whip_autos:client:engineDumpSaved`. Entry validation: model `^[%w_%-]+$` <= 40, finite fields, `fInitialDriveForce > 0` (trailers excluded), label <= 60.
- hp/torque shown are derived: torque = force x mass (Nm), hp from torque x 9.81 x 0.9 at 80% of redline speed (`flatVel x 1.2 / 0.9` km/h).
- Copy `engines.json` out before updating the folder (docs 002, README).
- `HiddenEngineClasses` hides classes from the list; `Engines.get` returns nil for them.

## whip_autos: turbo (`boost` live stat)

Server `server/power/turbo.lua`:

```lua
exports.whip_core:RegisterVehicleStat('boost', {
  default = 1.0, min = 1.0, max = 100.0,            -- PowerTurbo.IDLE / MAX
  persist = 'presence',                              -- fitted survives restart; the number comes back at idle
  live = { maxRate = PowerTurbo.fastestRise / 0.9, interval = 0.25 },  -- 0.25 s is whip_core's floor
  display = { unit = 'psi', range = { -3, 30 } },    -- PSI_LOW..PSI_HIGH
  hud = { label = 'Boost', color = '#facc15', order = 6, showWhenPresent = true, noCritical = true },
})
```

- Stat follows turbo data: `OnVehicleDataChanged('turbo', fn, { table = true, now = true })` -> `SetVehicleStat(id, 'boost', 1.0, 'turbo:fitted')` when a sold stage is present, `ClearVehicleStat(id, 'boost')` when none. A stage removed from config: no boost, no gauge, stays on car; works again if re-added.
- `OnVehicleStatChanged('boost', fn(vehicleId, value, previous, cleared), { now = true })`: arrival/removal only (`previous == nil` or `cleared`) -> GTA mod 18 follows via `SetVehicleAppearance(id, { turbo = bool })` with note `turbo_mod`; per-car worker queue so overlapping DB writes can't finish out of order. A boost stat with no stage (pre-stage bolt-on) or GTA turbo part from old Whiplash (on `whip_core:vehicle:spawned`) gets `{ psi = 15 }` (`OLD_TURBO_PSI`).
- Re-registered on `Whip.onConfigChanged('Turbo')` (cap follows stages/spool).
- Per stage (`PowerTurbo.stage(psi)`): `index`, `psi`, `price`, `top = levelOf(psi)` with `levelOf(psi) = (psi + 3)/33 * 100` clamped, `spool` linear from `SpoolFastest` (smallest) to `SpoolSlowest` (biggest), `spoolPeak = (top - 1)/spool` per s, `gain = TorquePerPsi * psi`.
- Client `client/power/turbo.lua`: `exports.whip_core:WatchVehicleStat('boost', { onStart, whileHeld = fn(entity, _, dt) -> gauge reading, onStop, interval = 125, driverOnly = true })`. Simulates spool (rate = spoolPeak x throttle x (0.12 + 0.88 x rpm^2)), blow-off dump in 0.3 s off throttle, wastegate trim, shift purge of `ShiftLossMin..Max` %; `ReportVehicleStat({ entity }, 'boost', level)`; torque via `PowerHandling.set('turbo', veh, 1 + gain x fraction)` -> `exports.whip_core:SetVehiclePower(ref, 'turbo', mult)`. Returning a value from `whileHeld` draws the driver's own capsule without waiting for the server copy.
- Other resources: `OnVehicleStatChanged('boost', ...)` (docs 042 example: a coolant add-on).

## whip_autos: nitrous (`nitro` consume stat, `nitro` item)

Server `server/power/nitrous.lua`:
- Stat: `RegisterVehicleStat('nitro', { default = 0, min = 0, max = 100.0, persist = true, consume = { maxRate = 100 / BottleSeconds, driverOnly = true, clearAtMin = true, interval = 0.5 }, hud = { label = 'Nitrous', color = '#60a5fa', order = 4, showAboveZero = true, noCritical = true } })`. Empty -> stat removed (no bottle). Failure -> `Whip.startProblem`.
- Item: `exports.whip_core:RegisterItem('nitro', { name = 'Nitrous Bottle', desc = ..., weight = 2.0, type = 'consumable', stack = true, maxStack = 5, usable = true, cooldown = 3, prop = 'p_s_scuba_tank_s' })`. Picture `html/img/items/nitro.webp`. No shop sells it until you stock it.
- Install (timed use): `exports.whip_core:RegisterUseHandler('nitro', { label = 'Installing nitrous...', duration = InstallSeconds*1000, reason = 'fitted to a car', cancelOnExit = true, canUse = fn(source) -> true | false, why, onComplete = fn(source) -> nil | false, why })`. Car is `GetPlayerVehicle(source)` (server's view), must be `vehType` automobile/bike and class in `PowerClasses`, not already `HasVehicleStat(id, 'nitro')`. `onComplete` returning `false, why` gives the bottle back. Sets `SetVehicleStat(id, 'nitro', 100, 'whip_autos:nitrous')`. Refusals: `'Nitrous only fits cars and motorbikes'`, `'This car already has nitrous'`, `'Could not fit the bottle'`.
- Flames: `whip_autos:server:nitroFlames(on)`; only the driver (`GetPlayerVehicle(source, { driver = true })`) of a car with nitro; relayed via `Whip.core:GetPlayersInRange(coords, 300.0)`.
- Client: hold `+whip_nitrous` (default `LSHIFT`, "Nitrous Boost") or pad action `RegisterPadAction('nitrous', { label = 'Nitrous (hold)', where = 'car', slot = 'veh_a', ready, onPress, onRelease })`; `SetPadActionReady('nitrous', bool)`; torque `PowerHandling.set('nitrous', veh, Nitrous.Torque)`; burn `Whip.core:ConsumeVehicleStat({ entity }, 'nitro', burn)`; `WatchVehicleStat('nitro', ...)` with `SetVehicleStatWatchInterval(id, 100 | 1000)`; local estimate shown until the server catches up (<= 2 s after release). Ends on `whip_core:player:died`. Boost only if `Whip.core:IsGameInputFree()`.

## whip_autos: power layers on every car

All client, `PowerHandling.driverLayer(layer, label, spec)` applies a whip_core handling layer to the car the player drives (seat -1), cleared on exit; via `whip_core:vehicle:entered/exited`:
- `topSpeed`: `{ add = { fInitialDriveMaxFlatVel = mph * 1.609344 * 0.9 / 1.2 } }` for classes in `PowerClasses`; `TopSpeedBonusMph = 0` off.
- `shiftTime`: scales clutch change rates by 1/time from `ShiftTimeByModel` / `ShiftTimeByClass` (or Plain), quickened by transmission (mod 13) per `TransmissionSteps` toward `TransmissionBestShare`.
- Gearbox computer (`client/power/gearbox.lua`): controller only (`Whip.core:IsControllerActive()`, `whip_core:pad:deviceChanged`); drives the dial gear with `SetVehicleDialGear({ entity }, gear)` (docs 045) and dips torque with `PowerHandling.set('gearbox', veh, ...)`.
- Torque asks (`SetVehiclePower`) multiply across resources; sent only when moved 1% (turbo 3%), repeated twice, or back to 1.0; guarded by `GetResourceState('whip_core') == 'started'` and `pcall` (docs' rule for per-frame/hot calls). whip_core sweeps a stopped resource's asks.
- These three settings change EVERY car on the server, police included (README: check them first when players say cars feel slow).

## whip_autos: Director cards, task, builder buttons

- `Whip.card('autos.customise', { category = 'goals', title = 'Goal: Customise Vehicle', outputs = { 'done', 'lost', 'outOfTime' }, labels, bad = { 'lost', 'outOfTime' }, timeout = 3600, test = 'run', props, check, run, onEnd })`. Props: `car` (`kind = 'world'`, `worldKind = 'vehicle'`, required), `text` (default 'Customise the car', max 120), `pays` (select, default `'job'`), `seconds` (duration 5-86400), `exact` (bool), `ways` (`kind = 'entries'`, `button = 'autos.exactWay'`, up to `ShopGoal.MAX_WAYS = 8`, each <= `MAX_STANDARD = 24` lines), `free` (bool), `spend` (number 0-1e7, `showIf = 'free'`). Uses `card:objective(text)`, `card:clock(seconds, text)`, `Whip.answerCard(job.id, pin, data)`.
- `Whip.card('autos.forceOpen', { categoryTitle = 'Whiplash', color = 'violet', title = 'Force Open Whiplash', outputs = { 'opened', 'nobody' }, timeout = 20, test = 'run', props = { { key = 'who', kind = 'players' } } })`. Grant lasts 30 s (`GRANT_MS`), waits 10 s for a claim.
- `Whip.task('autos.openWhiplash', { label = 'Force Open Whiplash', group = 'car', kinds = { 'vehicle' }, timing = 'instant', once = true, standing = false, run = fn(car, _, info) })` in `shared/director.lua` (both sides); skips `info.preview`.
- Who gets Whiplash: the car's player driver; no driver -> nearest passenger moves over; NPC driver or other player driving -> nobody.
- Builder buttons (client/look.lua): `Whip.directorButton('autos.look', { label = 'Whiplash', icon = 'turbo', kinds = { 'vehicle' }, where = 'bubble', takesOver = true, press })` saves a LOOK on a placed car (`data.look` or `data.looks[model]` for random vehicles); applied server-side on `whip_core:run:thingMade` (kind `'vehicle'`, only when invoked by whip_core) through `TuningServer.write`. `Whip.directorButton('autos.exactWay', { label = 'Pick in Whiplash', kinds = { 'card' }, where = 'page', takesOver = true })`.

## whip_autos: export, commands, key mappings, Object Viewer option

### GetOpenSessions() — SERVER
- `exports.whip_autos:GetOpenSessions()` -> array of `{ vehicleId, source, charId, startedAt }` (`startedAt` = `os.time()`). The only export of whip_autos (`server/main.lua:606`).

Commands (client; dev ones check server-side):
| Command | Gate | Does |
|---|---|---|
| `/whiplash` | `whip.devtools` with developer mode on (`claimAnywhere` ace; `SHOP_NEAR` uses `HasDevTools`) | Open on the car you drive anywhere; again closes |
| `/whiplashtune <engine <model|stock> | stance h tF tR cF cR [w] [s] | setup sp da ar st gr hb | drive <stock|fwd|rwd|awd> [front%] | clear>` | `whip.devtools` | Free tuning on the car you drive |
| `/whiplashengines` | `whip.devtools` | Rebuild engines.json (minutes) |
| `+whiplash_leave` / `-whiplash_leave` | - | Key mapping "Whiplash Autos: Leave (fallback)", default `BACK`; stands down once the page drew |
| `+whip_nitrous` / `-whip_nitrous` | - | "Nitrous Boost", default `LSHIFT` |

- `Whip.objectViewerOption('autos.whiplash', { label = 'Open Whiplash', group = 'Whiplash', tint = 'violet', kinds = { 'vehicle' }, whip = true, hint, select = fn(target) })`: G on a saved car in `/w`.
- Developer mode adds "Free" payment; logged as `whiplash_free`.
- Controls in shop: scroll / arrows (D-pad) browse, hold RMB (right stick) camera, C (RB) standard camera, Esc (B) back, Backspace leave. `Whip.padScreen({ buttons = { 'up','down','left','right','a','b','x','y','rb' }, keepInput = 'always', block = false, onDevice })`.

## whip_autos: lessons (Learning from whip_autos)

Docs anchor `autos-patterns` ("skip camera, view.js, kit.js, gearbox, stance maths: they teach nothing about WHIP"):
1. **Server prices the basket again.** Page sends picks + the total it showed (`shown`), never prices. Purchase is a SecureEvent with `near` (whose `at` is a function: a /whiplash session's floor is wherever its car is) and `onReject` replying to the page so the pay button never hangs.
2. **Paid and fitted in one write.** `ChargePlayer` called directly inside the SecureEvent lands in the same transaction as `SetVehicleAppearance` (look + VehicleData); failed fit -> `RefundPlayer(receipt)`. Never charge more than shown.
3. **A claim that every exit gives back.** One session per car/player; restore on page close, seat exit (`whip_core:vehicle:exited`), `playerDropped`, resource stop. Client `HoldVehicleAppearance(vId, true)` so WHIP doesn't record the preview.
4. **Data on a car that every game applies.** Non-mod state is VehicleData; clients apply with `WatchVehicleData` (`onGained/onChanged/onLost` for every car in view, or `driverOnly` with `onStart/onStop` for handling layers).
5. **Two kinds of vehicle stat.** `live` (turbo boost: driver simulates, whip_core caps rise rate, gauge from `whileHeld`) vs `consume` (nitrous: game bills burn, whip_core caps and clears when empty). Item install is a declared timed use on the car the server sees.
6. **Who may change a car.** One shared function (`ShopMayChange`) both sides load; server asks at claim (hide shelves) and again at payment (the rule).
7. **Settings page and derived data.** `Whip.configPage` writes into `Config`; lookups built from Config are rebuilt in place with `Whip.onConfigChanged` (docs 071: saved values arrive after your files load).
8. **Own NUI page.** `nui_callback_strict_mode 'true'`; every callback replies even on error; `Whip.padScreen` for controller/cursor; `SetScreenOpen` stands WHIP's HUD down.
9. **Director integration** via `Whip.card`, `Whip.task`, `Whip.directorButton`.
10. **Dev commands in their own files** (`client/dev.lua`, `server/dev.lua`).
11. Calling rule (fxmanifest comment): `exports.whip_core:X` inside handlers whip_core runs for you (Whip.register, SecureEvent/Callback, WatchVehicleData, OnVehicleStatChanged, AddAction callbacks, card run; a payment inside SecureEvent); `Whip.core:X` in your own code (threads, commands, keys, NUI callbacks, own events; answers `false, why` while whip_core is loading); hot paths call the export straight behind a started check.

"Where to look" (docs table): `onPurchase`, `priceOf`, `SHOP_NEAR`, `onClaim`, `endSession` (server/main.lua); `Session.open`, `teardownLocal` (client/session.lua); `TuningServer.write`; `registerBoostStat`, `whileHeld`; `registerNitroStat`, `registerInstall`, `billBurn`; `PowerHandling.driverLayer`; `ShopMayChange`, `Catalogue.looksOnly`; `refill`; `cb`, `show`, `html/js/app.js`; F1 wheel entry `AddAction` with `radial`; `server/director.lua`, `shared/director.lua`, `client/look.lua`, `server/look.lua`; `client/dev.lua`, `server/dev.lua`.

---

## whip_autos_shop

- Map resource, author "3D Clanker, for Whippy". Rockstar's Tuners Auto Shop interior placed inside the Los Santos Customs building in Burton, entered through a roller door from the car park; car lift (whip_autos' floor), paint booth. LS Customs Burton is gone; airport LSC untouched.
- `fxmanifest.lua`: `lua54 'yes'` (client.lua uses `&`), `files { 'whiplash_shop_interiorproxies.meta', 'data/whiplash_shop_timecycle.xml' }`, `data_file 'DLC_ITYP_REQUEST' 'stream/whiplash_shop.ytyp'` and `'stream/whiplash_shop_ext.ytyp'` (roller door world map), `data_file 'INTERIOR_PROXY_ORDER_FILE' 'whiplash_shop_interiorproxies.meta'` (`startFrom 5300`, proxy `whiplash_shop_placement`; whip_homes_mirrorpark uses 5000-5094), `data_file 'TIMECYCLEMOD_FILE' 'data/whiplash_shop_timecycle.xml'` (modifier `whiplash_shop_tc` = Rockstar's `MP_Heist_Tuner_SmShop_Default` without the two natural-ambient intensity lines that blacked out the street). On Enhanced nothing from `stream/` may go in `files {}`, hence `data/`. `client_script 'client.lua'`. No dependencies.
- `stream/` (Legacy) and `stream_enhanced/` (Enhanced; 27 files each): replaces 12 Rockstar `bt1_02*` files plus `ss1_occl_00`, `apa_`/`hei_` variants of the occlusion and `v_carmod` milo ymaps. No other resource may stream those names.
- `client.lua`:
  - Disables Rockstar's `v_carmod` interior at Burton (`vector3(-342.73, -131.94, 38.04)`, matched by type, name hash and position within 2 m) with `DisableInterior(id, true)`; re-checks every 30 s (5 s when not found).
  - Door wake-up: `whiplash_shop_door` at `(-349.824, -117.245, 38.103)` and `whiplash_spray_door` at `(-338.129, -125.069, 39.177)`: within 12 m, `ActivatePhysics` every frame (GTA high-frame-rate door sleep bug; FiveM fixed Legacy only, PR 4058).
  - Far stand-in `whiplash_shop_door_far`: hidden with `CreateModelHide` while the real door object exists (checked within 120 m).
  - F8 command `whiplash_doors` (status) / `whiplash_doors on|off`.
- Doors are GTA automatic doors, NOT in WHIP's door system (anyone can open). To lock the roller door, save a door in WHIP's Door System: model `whiplash_shop_door` at `-349.824, -117.245, 38.103`.
- **Never restart whip_autos_shop with players on**: the interior unloading crashes their games; restart the whole server. Restarting whip_autos or whip_core leaves it alone.
- Without it, move `Config.Shop.coords` (the floor) in /whip.
- Its map files are Rockstar's (not LGPL); code is LGPL-3.0.
- "Mostly Python?" No: by code it's one Lua client script plus map assets. The only Python is the shared `.githooks/enhanced_assets.py` (below). whip_autos_shop has a `.enhanced-manual` file: its `stream_enhanced/` is hand-made, not converted; the hook only reminds you when `stream/` changes.

## chameleon_paint

- `fxmanifest.lua`: `fx_version 'cerulean'`, `game 'gta5'`, author `WildBrick142`, version `2.0.0`. No scripts. `stream/vehicle_paint_ramps.ytd` (original) and `stream_enhanced/vehicle_paint_ramps.ytd` (converted for Enhanced).
- Holds the colour ramps GTA's colour-shift paints 161-222 draw from; FiveM Legacy doesn't load them by itself. Without it those paints turn a car black.
- Only one resource may stream `vehicle_paint_ramps.ytd`.
- Not WHIP, not under WHIP's licence: credit WildBrick142, Disquse, Rockstar. Never sell or monetise; a paid bundle must leave it out AND remove the Chameleon entries from `whip_autos` `Config.Colours`. Author may refuse any server.
- Recipe installs it in `resources/[assets]/chameleon_paint`.

---

## whip_dealership

Simon's car lot: browse whip_core's vehicle catalog with pictures, pay cash or from a bank account, car delivered to the lot with a key; plus "Manage Keys". Described as "the reference resource for building on whip: everything it touches is a public whip_core export". Not listed in docs' overview table or quickstart ensure list, but installed and ensured by the txAdmin recipe.

Manifest: satellite + `config.lua` shared, `client/main.lua`, `server/main.lua`, `ui_page 'html/index.html'`, `nui_callback_strict_mode 'true'`, `files` listed one by one (`html/index.html`, `html/css/dealership.css`, `html/js/dealership.js`: a missing one 404s and the panel is blank), `dependency 'whip_core'`, `lua54 'yes'`.

### Config
| Key | Default |
|---|---|
| `Config.Salesman` | `{ model = 's_m_y_dealer_01', coords = vector4(801.48, -805.88, 26.18, 178.19), label = 'Browse Vehicles', keysLabel = 'Manage Keys', useRange = 12.0 }` |
| `Config.Delivery` | `vector4(800.82, -817.61, 26.18, 91.89)` |
| `Config.Blip` | `{ show = true, label = 'Car Dealership', sprite = 326, color = 3, scale = 0.8 }` |
| `Config.SellableClasses` | `[0..9] = true, [11] = true, [12] = true` (no 10 industrial, 13 cycles, 14-16, 17-22) |
| `Config.ClassPrice` | `[0] 18000, [1] 26000, [2] 42000, [3] 38000, [4] 45000, [5] 68000, [6] 120000, [7] 850000, [8] 22000, [9] 55000, [11] 32000, [12] 30000` |
| `Config.ModelPrice` | `adder 1000000, zentorno 725000, t20 2200000, osiris 1950000, blista 16000, panto 85000, faggio 5000, sanchez 8000, bati 15000, dump 750000, phantom 120000, tulip 60000, asea 14000, bison 30000` |
| `Config.DefaultPrice` | `35000` |
| `Config.PriceFor(model, class)` | ModelPrice > ClassPrice[class] > DefaultPrice (shared function) |

### What is sold
`core:GetVehicleCatalog()` rows with `hasImage`, a `class` in `SellableClasses`, and `inGame ~= false`; entries `{ model, name = displayName or MODEL, class, image = row.image, price }`, sorted by price then name. Catalog list: `whip_core/server/vehicle_catalog_list.lua` (~930 `{ model, class, name }` lines; add a car = picture in `whip_media_previews/img/vehicles/<model>.webp` + a line + restart whip_core). Client adds model stats (`GetVehicleModelEstimatedMaxSpeed*3.6`, acceleration, braking, traction, seats).

### Registrations (server, in `Whip.register`)
- `core:SetVehiclePrices({ [model] = price })` (for the /whip Banks page valuation).
- `whip_dealership:catalogue` SecureCallback: `rateLimit = 1000`, `near = { at = simonAt, range = useRange, message = false }` -> `{ vehicles, accounts = [{ accountId, label, accountNumber, balance }] (only where CanUseBankAccount(accountId, { charId }, 'withdraw')), cash }`.
- `whip_dealership:server:buy` SecureEvent: `rateLimit = 3000, burst = 2`, `near` (message false), `onReject` -> `whip_dealership:client:purchaseResult(false, why == 'Rate limited' and 'One moment — try that again' or why)`, params `{ 'model', 'key', 60 }`, `{ 'payment', 'enum', { 'cash', 'bank' }, 'cash' }`, `{ 'accountId', 'id', 0 }` (0 = none).
- Manage Keys callbacks, all with `near = atSimon` and param `{ 'vehicle', 'vehicle' }` (refuses a car that isn't theirs, hands the handler a snapshot): `whip_dealership:myVehicles` (`rateLimit = 1000, burst = 2`, no param) -> `[{ vehicleId, name, plate, image = GetVehicleImage(model) }]`; `whip_dealership:keyCount` (`500, burst 4`) -> `CountVehicleKeys(vehicleId)`; `whip_dealership:makeKey` (`1000, burst 2`) -> `CanFitItem(src, 'vehicle_key', 1)` then `GiveVehicleKey(src, vehicleId, { spare = true })`; `whip_dealership:disableKeys` (`2000`) -> `ChangeVehicleLocks(vehicleId)`.
- `core:ShowBlip('everyone', 'lot', { coords, label, sprite, color, scale, shortRange = true })`.
- Simon: `core:SpawnNpc({ model, coords, behaviour = 'stand', conditions = { invincible = true, canMove = false, reacts = false, flees = false } }, { fightBack = false })` then `core:SetNpcState(npcId, { anim = { dict = 'anim@amb@business@bgen@bgen_no_work@', clip = 'idle_a' } })`. Spawned only once a character has loaded (`whip_core:player:loaded` or `GetCharId` of any player at register): on Enhanced an NPC made on an empty server can lose its network id. Existence checked through `core:GetNpcs()` (npcIds restart after whip_core restarts).

### Buy flow (`onBuy`)
1. Re-resolve from catalog: unknown / no image / class not sold -> "That car is not for sale here"; `inGame == false` -> "That car is not in this game".
2. Before money: `CanFitItem(source, 'vehicle_key', 1)` ("No room for the key — free a slot first"), `CanBringOutVehicleFor(source)` (e.g. Director Isolate world).
3. `ChargePlayer(source, price, { method, accountId (bank, nonzero), reason = 'Vehicle: <label>' })`.
4. `CreateOwnedVehicle(source, { model, stats = { fuel = 100.0 } }, { giveKey = true, spawnAt = Config.Delivery })` -> `vehicleId, err, saved`. All or nothing (car deleted on spawn/key failure).
5. `not vehicleId and saved` (DB fault, saved but not read back): DON'T refund; car comes to their garage.
6. `not vehicleId`: `RefundPlayer(receipt)`; "The sale did not complete (<err>). You have not been charged." (common: "Something is already parked in that spot").
7. Success: plate from `GetVehicle(vehicleId).plate`; `purchaseResult(true, '<label> is yours — plate <plate>', model)`.

### Client
- `AddAction({ id = 'simon', at = { coords = vector3 }, label, icon = 'car', group = 'dealership', options = { { id = 'browse', ... onSelect = openMenu }, { id = 'keys', label = keysLabel, icon = 'lock', options = myCars } } })` at Simon's spot (not on his ped: prompt exists before the ped streams).
- Dynamic menus: `options` as a FUNCTION filled when opened (may wait; whip shows "One moment..."); per car page `{ id = 'veh<id>', label, icon = 'car', image, options = fn }` with `make` (`stay = true`), `disable` (`holdMs = 1500`, `stay = true`), `count` (info row). `ctx.flash(r,g,b)`, `ctx.status(text, ms)`, `ctx.refuse(why)`.
- Menu: `exports.whip_core:Callback('whip_dealership:catalogue')`; `SetScreenOpen(true)` while open (prompts, aim, HUD, chat read this switch); `Whip.padScreen()`; search on pad via `Whip.call('OpenKeyboard', { title = 'Search cars', maxLength = 30, value })`.
- NUI callbacks: `dealershipClose`, `dealershipType`, `dealershipBuy` (sends only model, payment, accountId).
- Net: `whip_dealership:client:purchaseResult(ok, message, model)`; failures not toasted here (whip already shows the handler's `false, why`).
- Closes on `whip_core:player:died` and `whip_core:player:logout`.
- `/buycar <model> [cash|bank] [accountId]`: dev tool, client checks `HasDevTools()`; uses the same SecureEvent so near/rate/price still apply.
- No `onResourceStop`: whip removes the NPC, prompt, blip, screen and control blocks a stopping resource made.

### Lessons
1. Client sends a model name only; price, existence and eligibility come from server data.
2. Do the cheap failure checks (key room, can-spawn) BEFORE charging so the common refusals never need a refund.
3. Charge inside the SecureEvent so payment and the car row share one transaction; refund only on `false` with no `saved`.
4. `onReject` answers the menu for refusals before the handler runs.
5. `'vehicle'` param type does ownership checks for you.
6. Everything whip_core keeps (actions, NPCs, blips, callbacks) is declared in `Whip.register` with fixed ids so a whip_core restart re-declares and replaces.

---

## Repository tooling: .githooks/enhanced_assets.py

Identical file (same md5) in whip_core, whip_autos, whip_autos_shop, whip_fuel, whip_gunny, whip_rope, whip_graphics, whip_homes_mirrorpark, whip_media_map, whip_voice. Not loaded by FiveM; a developer-side git hook.
- Purpose: FiveM Enhanced ignores `stream/` when `stream_enhanced/` exists, so `stream_enhanced/` must hold an Alchemist-converted copy of every `stream/` file.
- Setup per machine: `git config core.hooksPath .githooks`; `git config alchemist.cli "<path>/AlchemistCli.exe"` (or env `ALCHEMIST_CLI`).
- `.githooks/pre-commit` runs `python .githooks/enhanced_assets.py hook`; `.githooks/.gitattributes` forces LF.
- Commands: `hook` (convert staged `stream/` changes, stage results; creates `stream_enhanced/` for a resource first changed), `sync RESOURCE...` (rebuild from working tree; `sync .` for repo root), `check` (report mismatches, exit 1 if any).
- Markers: `.enhanced-manual` (hand-made stream_enhanced, only reminded; whip_autos_shop has it), `.enhanced-skip` or a sibling `NAME_enhanced` folder (never get one), `.fxap` (escrowed, never converted). Enhanced-only resources (no `stream/`) left alone.
- Alchemist run with `-f`; failures retried with `--relaxed`; still failing -> copied unconverted with a warning. Only changed files converted (output not deterministic).
- Warns on drawables (`.ydr/.ydd/.yft`) with a model of more than 127 geometries: Enhanced crashes streaming them; split the model.

---

## Gotchas

1. There is no fuel export. Fuel is the `fuel` vehicle stat; `GetVehicleStat(id, 'fuel')` returns nil when whip_fuel isn't running (and whip_fuel itself treats nil as full). Check `GetResourceState('whip_fuel')` if you depend on it.
2. Don't register a stat named `fuel` yourself: whip_fuel owns it (docs 046).
3. An empty tank holds the engine through `HoldVehicleEngine(vehicleId, 'empty', ...)` keyed per resource; releasing it from another resource doesn't work. Refill with `SetVehicleStat` and whip_fuel releases it via `OnVehicleStatChanged`.
4. Fuel pumps adopt never-seen street cars (`AdoptVehicle` with `player = src`) at the fill; that counts against the player's street-car limit and can refuse with its reason.
5. A refund from a pump hold may arrive "next time you join" (`paidNow == false`) if the payer left.
6. whip_fuel streams GTA's own pump model names; any other pump/map resource streaming `prop_gas_pump_*` or `prop_vintage_pump` clashes. Custom map pumps need `Config.PumpModels`, `PumpCircle`, `NozzleCircle`, `Hose.Outlets`.
7. Hose ids from whip_rope restart at 1 after whip_rope restarts; whip_fuel forgets and redraws. Copy this if you use ropes.
8. whip_fuel's server events (`whip_fuel:nozzleTaken` etc.) are unauthenticated plain events; don't treat them as proof in security-relevant code.
9. whip_autos `Config.Turbo.Stages`: never remove a stage or change its psi once sold; a car keeps `{ psi }` and an unlisted psi gives no boost and no refund. psi must be whole 1-30, unique; bad rows are dropped with a startup problem.
10. `Torque per psi = 0` makes turbos only GTA's small turbo part (sound) - "A turbo does nothing" in troubleshooting.
11. Top speed bonus, realistic shifting and the gearbox computer change EVERY car on the server, including police and job cars.
12. `method = 'free'` on purchase is accepted only when `HasDevTools(source)` (whip.devtools AND developer mode on in `/w`), not the bare ACE.
13. The purchase refuses when the server total exceeds `shown` (prices changed in /whip mid-visit); a page that sends no `shown` uses `-1` (no check).
14. Lines already on the car's STORED look are silently dropped (printed to console), not charged; Repair is never "fitted".
15. Session cars (no saved record) keep bought work only as long as the car exists.
16. `/whiplashengines` takes minutes and overwrites `engines.json` in the resource folder; back it up before updating whip_autos.
17. Never restart `whip_autos_shop` while players are online (client crash); restart the server.
18. Chameleon paints (161-222) need `chameleon_paint` started and must be the only resource streaming `vehicle_paint_ramps.ytd`; selling a bundle requires removing both the resource and the paints from `Config.Colours`.
19. `whip_dealership` uses `CreateOwnedVehicle`'s third return `saved`: refund only on `false` with no `saved`, or you refund a car the buyer still receives.
20. Spawn whip NPCs (like Simon) only after a character has loaded; on Enhanced an NPC created on an empty server can lose its network id.
21. A `+command` key mapping needs its `-command` registered too, or key-up falls through to chat as text (`client/main.lua:97-99`).
22. Key mappings fire under `SetNuiFocusKeepInput` screens (whip_autos keeps input): check `IsGameInputFree()` / screen state per press (docs 064).
23. NUI callbacks must always answer (`cb`/`done`), even on error, or the page's fetch hangs; whip_autos wraps every one in `pcall` + `done({})`.

## Docs vs code

1. Docs 082 shows the purchase params as `method` enum `{ 'cash', 'bank' }` and a trimmed basket; code has `{ 'cash', 'bank', 'free' }` and basket fields `slot, index, wheelType, engine, stance, setup, drive` (`whip_autos/server/main.lua:523-534`). Docs also pass `method = method` to `ChargePlayer`; code maps to `method == 'bank' and 'bank' or 'cash'` (`server/main.lua:390`).
2. Docs 033 says any item with `fuelCapacity` is a fuel can that whip_fuel fills and pours. The server accepts any such item (`whip_fuel/server/jerry_can.lua:19-28`), but the client prompts require `held = 'jerry_can'` and `WEAPON_PETROLCAN` in hand (`whip_fuel/client/pumps.lua:147-157,1034`, `client/car.lua:238`), so only gunny's `jerry_can` works in practice.
3. `whip_fuel/config.lua:239-240` says the jerry can's `fuelCapacity` is in `whip_gunny/config/data.lua`; it is in `whip_gunny/items/weapons.lua:1009-1015` (copied onto the def by `whip_gunny/server/items.lua:81`).
4. `whip_core/types/server.lua:1800` types `CreateOwnedVehicle` as returning `vehicleId, err`; the implementation documents and returns a third `saved` boolean (`whip_core/server/vehicles.lua:4162-4164`), which whip_dealership relies on (`whip_dealership/server/main.lua:132,143`).
5. `whip_dealership/README.md` says car pictures are in `whip_assets_4`; whip_core says `whip_media_previews/img/vehicles/<model>.webp` (`whip_core/server/vehicle_catalog_list.lua:9`).
6. Docs 001 (resource table) and 002 (quickstart `ensure` list) omit `whip_dealership`; the txAdmin recipe installs and ensures it (`txAdmin-recipe/whip-enhanced.yaml:42-44,173`, `whip-legacy.yaml:43-45`).
7. whip_fuel README says the nozzle drops beyond 5 m; that is the client leash (`Config.Pump.Leash`). The server's own backstop is `Leash + 3` = 8 m (`whip_fuel/server/pumps.lua:975`).
8. `shared/power.lua:52` help text uses 0.03 per psi (15 psi = +45%); the shipped default is `0.033` (~+50%, `whip_autos/config.lua:692`). This is example wording only, not a behaviour difference.
