# Security: SecureEvent, SecureCallback, Callback, Sentinel, Permissions

Covers every way a player's game talks to a WHIP server and how WHIP checks it: `SecureEvent` / `SecureCallback` schemas and every value type, the client `Callback`, the refusal and logging model (Monitor), the Sentinel statebag tamper guard, ACE vs WHIP permissions and developer mode, `Whip.command`, and a review checklist. Built from doc anchors `#guide-secure`, `#secure-events`, `#guide-sentinel`, `#permissions` (plus `#guide-devtools`, `#whip-way`, `#patterns-satellite`), and source `whip_core/server/secure.lua`, `server/sanitize.lua`, `server/callback.lua`, `client/callback.lua`, `server/sentinel.lua`, `server/permissions.lua`, `server/devtools_base.lua`, `server/devtools.lua`, `server/helpers.lua`, `server/requirements.lua`, `shared/statebags.lua`, `shared/registry.lua`, `shared/invoker.lua`, `shared/events.lua`, `lib/satellite.lua`, `types/server.lua`, `types/client.lua`, `types/classes.lua`, `config.lua`.

## Contents
- Threat model and the rules
- SecureEvent(eventName, schema, handler)
- Schema keys
- What happens to each call (check order)
- Rate limits: rateLimit and burst
- Who may send it: requirePlayer, whileDead, ace, permission
- params: value types
- near: where they are
- ownerOf: network owner of an entity
- The handler: arguments and the player sheet
- Saying no: return values, what the player sees
- SecureCallback(name, schema, handler)
- Callback(name, ...) (client)
- RecordEventRejection(eventName, src, reason?)
- TrackInvocationLock(releaseFn, eventName?, src?)
- Handlers that wait: IsSessionCurrent, logout, one transaction
- Logging: console and the Monitor
- What Sanitize does to incoming values
- Whip.command(name, opts, fn)
- Server-side `require` tables (Requirements)
- Sentinel: the statebag tamper guard
- Sentinel exports
- Permissions model: ACE, WHIP permissions, developer mode
- Permission and dev-tools exports
- WHIP's own unguarded net events
- Coming from ESX / QBCore / ox_lib
- Security review checklist for WHIP resources
- Gotchas
- Docs vs code

---

## Threat model and the rules

- Any connected game can fire any net event, with any arguments (any type, NaN, huge strings, function references in msgpack), at any rate, from anywhere. A client handler can also be fired by a cheat, so nothing that matters is ever decided on the client.
- WHIP rule ("The WHIP way"): every message from a game is a `SecureEvent` or `SecureCallback` that names its values, with `near` where position matters. The server decides.
- `near` trusts the position the client's game reports (server `GetEntityCoords` of the ped). Teleports, god mode, aimbots still need an anticheat.
- A client's `require` table on an action is only a hint about what to show; the server re-checks (Requirements, below).
- Players can write their own player statebag and bags of entities they own (`sv_stateBagStrictMode` is off on purpose). WHIP's own bag keys are guarded by the Sentinel; server code reads the server's truth, never the bag.

---

## SecureEvent(eventName, schema, handler) — SERVER

Registers a net event; every incoming call is checked against `schema` before `handler` runs. Declare it inside `Whip.register(function() ... end)` so it is re-declared after a whip_core restart (whip_core forgets all registrations when it restarts).

| Param | Type | Meaning |
|---|---|---|
| eventName | string | 1 to 128 characters. Convention: start with your resource's name (`'myshop:buy'`) |
| schema | table | The rules (below). `{}` = every default, no values passed |
| handler | function | `function(source, player, ...values)`; values in `params` order. `return false, 'why'` refuses |

Returns: `true`, or `false, reason` (the reason is also printed: `[whip_core:secure] REFUSED SecureEvent from <res>: <reason>`).

Refusal reasons at registration (secure.lua:1373-1411, 1237-1305):
- name not a string of 1–128 chars: `SecureEvent: the name must be a string of 1 to 128 characters`
- name starts `cb:` (callbacks live under `cb:<name>` in the same registry)
- name is a server lifecycle event: `playerDropped, playerConnecting, playerJoining, onResourceStart, onResourceStop, onResourceStarting, onServerResourceStart, onServerResourceStop, onResourceListRefresh, entityCreated, entityCreating, entityRemoved, playerEnteredScope, playerLeftScope, rconCommand, chatMessage, gameEventTriggered`, or any name starting `txAdmin:` or `__cfx_` ("a client could fire it": RegisterNetEvent marks a name network-safe for every handler in the runtime)
- schema not a table; handler `nil` (checked with `~= nil`, since a function crossing an export is a callable table)
- schema errors (see "Schema checks at registration")
- name owned by another running resource: `event "x" belongs to <owner>`; names starting `whip_core:` are reserved for whip_core: `event "x" is reserved: names starting "whip_core:" belong to whip_core`

Name ownership (shared/registry.lua): first resource to register owns the name. The same resource registering again replaces its handler (the net listener is added only once; the registry entry is swapped; counters survive). When the owner stops, its entries are marked dead: further calls of that event are dropped silently (no log); a callback answers `'That is no longer available'`. A stopped owner's name is free for anyone. The resource-name prefix is a convention only; it is not enforced or warned for events (see Docs vs code).

Unknown schema keys are warned, not refused: `WARNING SecureEvent("x") from res: "ratelimit" is not a schema key — it does nothing (...)`.

```lua
Whip.register(function()
    Whip.core:SecureEvent('mycafe:tip', {
        rateLimit = 2000,
        params    = { {'amount', 'amount', 500} },      -- whole number 1..500
        near      = { at = Config.Counter, range = 3.0 },
    }, function(source, player, amount)
        local receipt, err = exports.whip_core:ChargePlayer(source, amount, { reason = 'Tip' })
        if not receipt then return false, err end       -- shown to the player as an error
    end)
end)
-- client: TriggerServerEvent('mycafe:tip', 20)
```

---

## Schema keys

The full set read by SecureEvent/SecureCallback (`SCHEMA_KEYS`, secure.lua:1328): `rateLimit, burst, ace, requirePlayer, whileDead, params, near, onReject, sheet, ownerOf, permission`.

| Key | Type | Default | Behaviour |
|---|---|---|---|
| `params` | table (list of defs) | `{}` | One `{name, type, ...}` per value, in order. Only listed values reach the handler; extra args are dropped; an unlisted position arrives as `nil` |
| `rateLimit` | number (ms) \| `false` | 100 ms with burst 10 | Minimum ms between calls per player per event (token bucket). `false` = no limit. `0`, negative, NaN, non-number refused at registration |
| `burst` | integer ≥ 1 | `1` if `rateLimit` given; `10` if not | Calls allowed back to back before the interval applies. A `burst` with no `rateLimit` keeps the 100 ms interval |
| `near` | table | none | `{ at, range = 5.0, message?, allowUnknown? }` (near section) |
| `ace` | string | none | FiveM ACE the player must hold. `'whip.devtools'` also needs developer mode on. Lets a DEAD player through |
| `permission` | string \| string[] | none | WHIP permission, or list (any one). Does NOT let a dead player through |
| `whileDead` | boolean | `false` | `true` lets a dead player send it |
| `requirePlayer` | boolean | `true` | `false` accepts a source with no character loaded (handler's `player` is then `nil`) |
| `ownerOf` | string | none | Names an `'id'` param holding a netId; only that entity's network owner may send it; refused quietly |
| `onReject` | function | none | SecureEvent only: `function(source, reason, rawArgs)`, run when WHIP refuses before the handler. `rawArgs` are unchecked. On a SecureCallback it is accepted but never called (a warning is printed) |
| `sheet` | `'full'` \| `'light'` | `'full'` | `'light'`: handler's `player` is the light sheet (below). Any other value refused at registration |

### Schema checks at registration (secure.lua:1237-1305)
Each fails the registration with a printed reason:
- `rateLimit must be a number of milliseconds above 0, or false for no limit`
- `burst must be a whole number, 1 or more`
- `ace must be the name of an ACE permission` (non-empty string)
- `permission must be a permission name, or a list of them (any of)` (non-empty string, or non-empty list of non-empty strings)
- `sheet must be 'full' (the default) or 'light'`
- `params must be a list of param definitions`; each def: must be a table, `[1]` a non-empty string name, `[2]` a known type; `enum` needs a table of values at `[3]`; `player` options must be a table if given; `record` needs a non-empty list of field defs; `list` needs an entry def; no `addr` inside a `record` or a `list` (either form)
- `near must be a table like { at = ..., range = 5.0 }`; `near needs an \`at\``; `near.range` must be a number > 0 or a function; a string `at` other than `'vehicle'` is refused; `at = 'vehicle'` needs a `'vehicle'` param in the schema
- `ownerOf must name a param (a netId)`; the param must exist (`ownerOf: there is no param called 'x'`) and be of type `'id'`

Known param types (`PARAM_TYPES`): `int, number, id, amount, string, key, enum, bool, addr, vehicle, slot, list, any, player, record`.

---

## What happens to each call (check order)

For `SecureEvent` (secure.lua:1467-1626); `SecureCallback` runs the same gates in the same order (1684-1792).

1. Owner stopped (`reg.dead`) → event: dropped silently; callback: `false, 'That is no longer available'`.
2. Counted (`calls`, `lastCall`) — every arrival, including later refusals.
3. Rate limit → `'Rate limited'`.
4. `ace` → `'ACE denied: <ace>'`, or for `whip.devtools` with developer mode off `'Developer mode is off: turn it on in /w'` (the player also gets that as an error toast, at most once per 3 s).
5. `permission` → `'Permission denied: <label>'` (label of the declared permission, or the names joined with `' or '` for a list/undeclared).
6. `requirePlayer` → `'No player session'` when no character is loaded OR the session is closing (logout/disconnect has started).
7. Dead → `'Player is dead'` unless `whileDead = true` or `ace` is set. A player in developer mode also gets a toast `<event> refused while dead: whileDead = true in its schema lets dead players through` (once per event per 5 s).
8. `params` validated in order, under `pcall` (a throw inside a check becomes `'malformed parameters'` and is printed). First failing param refuses with its reason. If that refusal is one a real player can meet, a player-facing sentence is shown (event: error toast; callback: returned as the reason).
9. For another resource's handler: `player` becomes the full or light sheet; `addr` values become `{ addr, item, amount, metadata }`.
10. `near` → refused `'Too far away'` (toast `near.message` or `'Too far away'`, unless `message = false`); a broken `near` (throw, bad range) is logged as `error` with no toast.
11. `ownerOf` → `'not the network owner of that entity'` (no toast).
12. Handler runs (pcall'd, profiler scope `whip:secureHandler`, invocation record opened for locks/refusals/actions).

Every refusal before the handler: counted, logged to the Monitor, printed (throttled), and for events `onReject(source, reason, rawArgs)` runs. Note the rate limit is consumed by calls that are later refused.

---

## Rate limits: rateLimit and burst

Token bucket per player per event key (`RateLimit(source, action, cooldownMs, burst)`, helpers.lua:152). Key = the event name, or `cb:<name>` for a callback. Bucket starts with `burst - 1` tokens after the first call; refills one token per `cooldownMs`, capped at `burst`; a call needs one token. Buckets are cleared on `playerDropped` (not on character switch).

| You write | A player may send |
|---|---|
| nothing | 10 in a row, then one per 100 ms |
| `rateLimit = 2000` | 1, then one every 2 s (a flat cooldown) |
| `rateLimit = 2000, burst = 5` | 5 in a row, then one every 2 s |
| `burst = 4` (no rateLimit) | 4 in a row, then one per 100 ms |
| `rateLimit = false` | unlimited |

- A pause earns calls back up to `burst`.
- Give a `burst` to anything done quickly by hand (drag and drop), and to anything that closes/releases something: a refused close leaves it open.
- Keep `burst = 1` (i.e. declare a `rateLimit`) on a handler that takes locks via `TrackInvocationLock` (overlapping calls can't be told apart).
- Callbacks also pass a transport flood ceiling first (below): 25 ms with burst 40 per player, shared by ALL callbacks; drops there are silent and the client times out after 10 s.
- The Monitor shows the effective rate (default included).

---

## Who may send it: requirePlayer, whileDead, ace, permission

- `requirePlayer` (default `true`): a source with no loaded character, or whose session is closing, is refused `'No player session'`. With `false`, calls from the character screen pass and `player` is `nil` when nothing is loaded (if a character is loaded you still get the sheet and the dead rule applies).
- Dead rule: everything refuses a dead player unless `whileDead = true` (respawn flow, closing a screen, releasing an escort, chat, logout, background reports) or `ace` is set (admin tools). The dead flag read is `player.isDead`, the same one `IsPlayerDead(source)` returns.
- `ace = 'myres.admin'`: `IsPlayerAceAllowed(source, ace)`. For `ace = 'whip.devtools'` the player must also have developer mode on (`DevTools.aceRefusal`). Dead players with the ACE pass.
- `permission = 'mygarage.manage'` or `{ 'a.b', 'c.d' }` (any one): `Permissions.hasAny`. Full admins (whip.devtools + developer mode on) hold every permission unless it was declared `devtools = false`. Does not excuse the dead rule: add `whileDead = true` if dead holders need it.
- Order matters for the reason you see: rate limit, then ace, then permission, then session, then dead.

---

## params: value types

Each param def is a positional table `{name, type, ...}`. Rules that apply to every type:
- A function reference (a table with `__cfx_functionReference`, or any table with a `__call` metamethod) is refused for every type: `<name>: a function is not a value`.
- Numbers sent as text count as numbers (`wireNumber`: `tonumber` on strings) for `int`, `number`, `id`, `amount`, `player`, `slot`, `vehicle` — not for `enum`, and a `key` must be a string.
- Two families: "refused, never corrected" (`amount`, `id`, `key`, `slot`, `vehicle`, `addr`, `player`) and "softer, for settings" (`number`, `int` clamp; `enum`, `bool`, `string` fall back to a `default` if given).
- Refusal reasons start with the param name (`amount: Amount must be a whole number of 1 or more`); inside lists/records they are prefixed with the path (`basket[2].slot: invalid id`, `args.note: empty string`).

| Type | Written | Accepts / does | Refusal reason |
|---|---|---|---|
| `amount` | `{name, 'amount', max?}` | Whole number ≥ 1 and ≤ `max` (no max = unbounded); numeric strings ok; `nil` refused | `<name>: Amount must be a whole number of 1 or more` (also for > max) |
| `id` | `{name, 'id', min?, max?}` | Whole number in `[min (default 1), max]`; numeric strings ok; fractions, NaN, ±inf refused; never clamped. Returns an integer | `<name>: invalid id` |
| `key` | `{name, 'key', maxLen?}` | String of only letters, digits, `_`, `-`, length 1..`maxLen` (default 60). Anything the cleaner would change is refused (no cleaning, no truncation); non-strings (numbers too) refused | `<name>: invalid key` |
| `enum` | `{name, 'enum', {values}, default?}` | Exact `==` match against the list (`"1"` is not `1`). Without match: `default` if given, else refused | `<name>: invalid enum value` |
| `bool` | `{name, 'bool', default?}` | true: `true, 1, "true", "1"`; false: `false, 0, "false", "0", ""`; `nil` → `default == true` (so `false` with no default); anything else → `default` if given, else refused | `<name>: expected true or false` |
| `string` | `{name, 'string', maxLen, default?}` | Non-string → `default` (or `''`). Control chars 0x00–0x1F except tab (0x09), newline (0x0A) and CR (0x0D) stripped; cut to `maxLen` bytes, then a split UTF-8 character at the end is dropped. Result `''` → `default`, or refused when no default | `<name>: empty string` |
| `number` | `{name, 'number', min, max, default?}` | A number (or numeric string); NaN/±inf → `default` (or 0); then clamped to `[min, max]` (missing bounds: ±1e12). Not a number at all → `default` if given (returned unclamped), else refused | `<name>: expected number, got <type>` |
| `int` | `{name, 'int', min, max, default?}` | As `number`, then floored (`math.floor` after the clamp). Never for money, counts or ids | same as `number` |
| `slot` | `{name, 'slot', opts?}` | A slot in the CALLER's own pockets: a number (main pockets), or `{ sub = 'accessory', slot = 3 }`. Handler gets `{ addr = {kind='player', id=source, sub, slot}, item, amount, metadata }` (metadata a copy). `opts.item` = key or list of keys; `opts.allowEmpty = true` accepts an empty slot (handler gets `{ addr }` only) | see below |
| `vehicle` | `{name, 'vehicle', opts?}` | A `vehicleId` (not entity, not netId) the caller owns. Handler gets a `GetVehicle`-style snapshot (`Vehicles.context`, a copy). `opts.anyOwner = true`: any owned car (pair with `near`); `opts.session = true`: also adopted street cars | see below |
| `addr` | `{name, 'addr', opts?}` | A store address the caller may name (resolved and authorised by `Stores.fromWire`). Satellite handler gets `{ addr, item, amount, metadata }` as for `slot`; `opts.slotOptional = true` accepts a whole store (no slot) and then only `addr` is filled. Not allowed inside `list`/`record` | `<name>: <store reason>` (silent) |
| `list` | `{name, 'list', entry, max?}` | A Lua sequence (keys exactly 1..n, no gaps, no other keys) of ≤ `max` entries (default 50). `entry` is one def (`{'mod','int',0,50}`) or a list of defs for table entries (`{ {'slot','id',1,50}, {'index','int',-1,99} }`, only those fields kept). Returns a new list of checked values | `<name>: expected a list`, `...: expected a list (1, 2, 3...), not a table with other keys`, `<name>: the list has gaps`, `<name>: at most N entries`, `<name>[i]: expected a table`, `<name>[i].<why>` / `<name>[i]: <why>` |
| `player` | `{name, 'player', { range?, notSelf? }}` | Another loaded player's server id (numeric strings ok): has a character, not in the character creator, same routing bucket as caller, within `range` m (default 3, 3D) of caller; not the caller unless `notSelf = false` (then no range check for self). Handler gets the target's light sheet | `<name>: expected a server id` (silent); `not yourself` → shows "Not on yourself"; `not here` → "They are not here"; `too far` → "They are too far away" |
| `record` | `{name, 'record', fields}` | One table; each field def checked like a list entry's; only those fields passed (others dropped); player-facing sentences from fields propagate | `<name>: expected a table`, `<name>.<field>: ...` |
| `any` | `{name, 'any'}` | Unchecked (only function refs refused). Prefer `record`, `list`, `slot` | — |

`slot` refusals: sub not one of `PlayerContainers` (`{'player'}` or `{'player','accessory'}` when `Config.AccessoryStrip ~= false`) → `not one of your pockets` (silent); slot not a whole number in `1..Config.ContainerSlots[sub]` (default config: player 30, accessory 5; 500 if unset) → `invalid slot` (silent); no inventory → `no inventory`; empty without `allowEmpty` → `that slot is empty`, player sees "That item is not there any more"; wrong item → `not the right item`, player sees "That slot holds something else now".

`vehicle` refusals: not a whole id ≥ 1 → `must be a whole vehicle id` (silent); unknown → `no such vehicle`, player sees "That vehicle is not there any more"; adopted street car without `session = true`, or owned by another character without `anyOwner` → `not your vehicle`, player sees "That is not your vehicle".

`addr` store reasons (silent) include `address must be a table`, `not a client-addressable store`, `You can only look at that`, `You are too far away from that`, `store kind "x" is server-only`, `you do not have that <kind> open`, `slot must be a positive integer`, `container address needs a whole-number id`, `that container is not open for you`, `that container is read-only for you`. Every item move in WHIP passes this gate (see the Inventory/Addresses reference).

Forged values (another player's pocket, a bad id) are refused silently; refusals a real player can meet by acting on stale UI are shown as an error toast (event) or returned as the callback reason.

```lua
Whip.core:SecureEvent('mykit:install', {
    params = { {'kit', 'slot', { item = 'mykit_turbo' }}, {'vehicle', 'vehicle'} },
    near   = { at = 'vehicle', range = 5.0 },
}, function(source, player, kit, v)
    local taken, why = exports.whip_core:StoreTake(kit.addr, 1, { reason = 'fitted to ' .. v.plate })
    if not taken then return false, why end
    exports.whip_core:SetVehicleData(v.vehicleId, 'mykit_turbo', { fittedAt = os.time() })
end)
```

---

## near: where they are

`near = { at, range = 5.0, message?, allowUnknown? }`. Checked once, when the call arrives, after params (so `at` can use a checked param).

`at` forms:
- a fixed position: `vector3`/`vector4`, `{ x=, y=, z= }` or `{ 1, 2, 3 }`
- `'vehicle'`: the car named by the schema's `'vehicle'` param. Sitting in that car counts as near; otherwise distance to the tracked entity's origin; a car with no entity is near nobody (`IsPlayerNearVehicle`)
- a function `function(source, player, ...checkedValues)` returning `x, y, z`, a `vector3`/`vector4`, or a table position; `nil` = no position. Receives the values in the form your handler gets (satellite form for `addr`).

`range`: metres (> 0), or a function returning metres, asked at every call (follows a setting). A function that errors or returns a non-number/≤0/inf → logged as `error`, call refused, no toast.

No position from `at` → refused `'Too far away (near.at found no position)'` unless `allowUnknown = true` (then the call passes, for a handler that reports an unknown id with a better message).

Distance: `IsPlayerNear` (helpers.lua:273) — squared 3D distance from the player's ped; false when the ped does not exist or the player is in the character creator.

`message`: what the player is told when too far (default `'Too far away'`); `false` = silent (for calls fired on a timer, not a press). For a SecureCallback the toast is shown AND the call answers `false, 'Too far away'` (the log reason, not `message`).

A throw inside an `at` function → logged `error` (`near.at: <err>`), printed `ERROR in near for "<event>"`, refused, no toast.

```lua
near = {
    range = 15.0,
    at = function(source, player, shopId)
        local shop = exports.whip_core:GetShop(shopId)
        if not shop then return nil end      -- refused as too far
        return shop.x, shop.y, shop.z
    end,
    message = 'You are too far from the shop',
},
```

For a long action, the event's `near` only covers arrival; re-check at the end (e.g. `Progress` with its own `near = { coords, range }`).

---

## ownerOf: network owner of an entity

`ownerOf = 'npcNet'` names an `'id'` param holding a netId. The call passes only if `NetworkGetEntityOwner(NetworkGetEntityFromNetworkId(netId)) == source`. Use for things only the simulating client can report (an NPC's state, a death it saw). Refused quietly (reason `not the network owner of that entity`, no toast), because ownership migrates and a refused report is usually just late.

---

## The handler: arguments and the player sheet

`handler(source, player, ...values)`:
- `source`: the caller's server id. Use this parameter, never the global `source` (it changes after any yield and in helpers).
- `values`: the checked values, exactly `#params` of them in `params` order (a `nil` may sit among them, e.g. `bool` cannot be nil but `any` can).
- `player` for another resource's handler is a COPY:
  - full sheet (`handlerSheet`, default): `source, session, userId, charId, firstName, lastName, fullName, dateOfBirth, gender, cash, position = {x,y,z,w}, health, armour, isDead` — no `metadata`, no methods, no inventory. `GetPlayer(source).metadata` has metadata.
  - light sheet (`sheet = 'light'`): `source, session, userId, charId, firstName, lastName, fullName, dateOfBirth, gender, isDead` — no position (3 natives), cash (pocket scan), health/armour (stat reads). For events fired many times a second.
  - `nil` when `requirePlayer = false` and no character is loaded.
  - whip_core's own handlers get the live `WhipPlayer` object; satellites never do.
- Handlers run inside an "action": what whip_core saves while the handler runs (items, money, vehicle data) is written in one transaction when it ends. `return false` or an error does NOT undo it: refund yourself.
- Inside a handler, call `exports.whip_core:X` directly (types/satellite.lua); `Whip.core` is for your own threads, commands, timers and NUI callbacks.

---

## Saying no: return values, what the player sees

SecureEvent handler returns (secure.lua:1599-1625):

| Handler returns | Player sees | Monitor records |
|---|---|---|
| `false, 'You need a wrench'` | the message as an error notification (`NotifyPlayer(src, msg, 'error')`) | rejected, with the message |
| `false` (or `false, ''` / non-string) | nothing | rejected, `refused by the handler` |
| anything else / nothing | only what you send | ok |
| throws | nothing | `error`, with the error text; printed `[whip_core:secure] ERROR in <res>'s event "<name>" (source N): <err>` (throttled, " — and N more like it"); locks tracked with TrackInvocationLock released |

To record a refusal without showing a message: call `RecordEventRejection(name, source, reason)` then `return` (or `return false`).

Before-handler refusals show a toast only for: `near` (unless `message = false`), param refusals with a player sentence (slot/vehicle/player), developer-mode-off ACE refusals, and dead refusals to developers. Everything else (rate limit, ACE, permission, session, forged params, ownerOf) is silent to the player.

---

## SecureCallback(name, schema, handler) — SERVER

Registers a server callback the client asks with `Callback(name, ...)`. Same name rules (own namespace; stored as `cb:<name>`; `whip_core:` reserved; 128 chars) and same checks as SecureEvent. Schema as SecureEvent's without `onReject` (accepted but never called; a warning is printed).

| Param | Type | Meaning |
|---|---|---|
| name | string | 1–128 chars, start with your resource's name |
| schema | table | as SecureEvent |
| handler | function | `function(source, player, ...values)` returning the answer |

Returns: `true`, or `false, reason` (as SecureEvent).

Answer semantics:
- Every value the handler returns goes back (`table.pack`, all of them on the wire). Across the export boundary into your resource the list is cut at its first `nil`, so refuse with `false, 'why'`, never `nil`.
- A handler's `false, why` is an ANSWER: the Monitor records it as `ok` (and no toast is shown). Call `RecordEventRejection` to record it as refused.
- So answer an ordinary "no" with data (a word, a table) and keep `false, why` for refusals.
- Handler throws → client gets `false, 'Server error'` (error text stays in the server console; logged `error`).
- WHIP refusals answer `false, <reason>`: `'Rate limited'`, `'ACE denied: x'`, `'Developer mode is off: turn it on in /w'`, `'Permission denied: <label>'`, `'No player session'`, `'Player is dead'`, `'<param>: <why>'` (or the player sentence, e.g. `'That is not your vehicle'`, when there is one), `'malformed parameters'`, `'Too far away'` / `'Too far away (near.at found no position)'`, `'not the network owner of that entity'`, `'near.at: <err>'` / near.range errors.
- Don't block a callback past 10 s (the client gives up): no long `Progress`/bars inside one; use a SecureEvent.

```lua
local PRICES = { mycafe_coffee = 15, mycafe_muffin = 8 }
Whip.core:SecureCallback('mycafe:getPrice', {
    rateLimit = 500,
    params    = { {'itemKey', 'key', 60} },
}, function(source, player, itemKey)
    local price = PRICES[itemKey]
    if not price then return false, 'Not sold here' end
    return price
end)
```

---

## Callback(name, ...) — CLIENT, WAITS

`exports.whip_core:Callback(name, ...)` asks a server SecureCallback and blocks until the answer (promise + `Citizen.Await`). Must run where the client may wait: commands and event handlers are fine; inside a `RegisterNUICallback` handler or other non-yieldable place wrap it in `CreateThread`.

| Param | Type | Meaning |
|---|---|---|
| name | string | the callback's name |
| ... | any | values in its `params` order |

Returns: the server handler's values, or `false, reason`:

| Reason | When |
|---|---|
| WHIP check reasons (`'Rate limited'`, `'Player is dead'`, `'No player session'`, `'Too far away'`, `'itemKey: invalid key'`...) | the gate refused |
| yours | handler returned `false, 'why'` |
| `'Server error'` | handler threw |
| `'Unknown callback'` | no callback has that name (answered at once) |
| `'That is no longer available'` | its resource stopped |
| `'No answer from the server'` | nothing within 10 s (`CALLBACK_TIMEOUT = 10000`) |

`if not result then` catches them all; the second value says why.

```lua
local price, why = exports.whip_core:Callback('mycafe:getPrice', 'mycafe_coffee')
if not price then return exports.whip_core:Notify(why, 'error') end
```

Transport (server/callback.lua): one net event `whip_core:server:triggerCallback(cbId, name, ...)` answered with `whip_core:client:callbackResponse(cbId, results)`.
- Flood ceiling: `RateLimit(src, 'triggerCallback', 25, 40)` for ALL callbacks from one player combined. Drops are silent (no reply); the client sees `'No answer from the server'` after 10 s. Console (if `Config.LogSecureRejections ~= false`): `[whip_core:callback] REFUSED N callback(s) from src S in the last 5000ms — rate limit 25ms/burst 40...`, one line per player per 5 s.
- Non-string names or names over 128 chars are dropped silently.
- Unknown names: answered `false, 'Unknown callback'`; the first sighting of a name is printed once (control chars → `?`), at most 64 distinct names, then only counted.
- The underlying `RegisterCallback` global is not exported: SecureCallback is the only public way to register.

---

## RecordEventRejection(eventName, src, reason?) — SERVER

Records the call your handler is answering as refused in the Monitor, and marks the running invocation so the wrapper does not log `ok` over it. Use for a SecureCallback saying no (its `false` is an answer, logged ok) or a SecureEvent refusing without a message on screen.

| Param | Type | Meaning |
|---|---|---|
| eventName | string | the event or callback as registered (`'myres:getPrice'`; `'cb:myres:getPrice'` also accepted) |
| src | number | the player refused |
| reason | string? | what the Monitor shows |

Returns: nothing.
- Counts a reject on the registry entry; finds the running handler by coroutine, else by name+source; marks it only if the name matches.
- Outside a running handler it only logs.
- A `cb:` name matching no callback prints once: `RecordEventRejection("cb:x"): no callback has that name...`.
- Two overlapping calls of one event by one player could swap marks (log only).

```lua
exports.whip_core:RecordEventRejection('mycafe:getPrice', source, 'Not sold here')
return false, 'Not sold here'
```

---

## TrackInvocationLock(releaseFn, eventName?, src?) — SERVER

Registers a release function for a lock your handler took: if the handler THROWS, WHIP calls it (also if your resource stops mid-handler). On a normal return the lock stays: release it yourself.

| Param | Type | Meaning |
|---|---|---|
| releaseFn | function | releases the lock (checked `~= nil`) |
| eventName | string? | the event/callback your handler answers |
| src | number? | the `source` your handler was given |

Returns: `true`, or `false, reason`: `'TrackInvocationLock: a release function is required'`, `'not inside a SecureEvent or SecureCallback handler'`, `'no handler for "x" is running for source N'`, `'N of your handlers are running at once: pass the event name and the source'`.
- Without name/source it attaches to your resource's single running handler; refused when several are running.
- Two overlapping calls of the same event from the same player can't be told apart: the lock lands on the newer one. Keep `burst` at 1 (declare a `rateLimit`).
- Release errors are printed (`lock release failed after handler error`).

```lua
local release = acquireSafeLock(safeId)
if not release then return false, 'Someone is already at that safe' end
exports.whip_core:TrackInvocationLock(release, 'myheist:crackSafe', source)
crackSafe(safeId, source)       -- if this errors, WHIP calls release
release()
```

---

## Handlers that wait: IsSessionCurrent, logout, one transaction

- `IsSessionCurrent(source, session)` — SERVER: `true` while the same character load is playing (loaded, `session` matches, not closing). Call it after any wait (DB await, `Wait`, `Progress`, a yielding export) before giving or taking. `player.session` is on both sheets.
- Logout/disconnect sets the session `closing` (new calls refused `'No player session'`) and waits up to 2 s for handlers already running for that player (`HandlersInFlight`), so short waits are covered; longer ones need `IsSessionCurrent`.
- One action, one transaction: whip_core saves made during a handler are linked and written together when it ends. Use one call per move (`StoreMove`, not `RemoveItem` then `AddItem`) so both sides land together; your own rows go with `CommitWithAction`.

```lua
local done, reason = exports.whip_core:Progress(source, { label = 'Brewing...', duration = 6000,
    near = { coords = Config.Counter, range = 3.0 } })
if not done then return false, reason end
if not exports.whip_core:IsSessionCurrent(source, player.session) then return end
local given, why = exports.whip_core:AddItem(source, 'mycafe_coffee', 1, nil, 'brewed')
if not given then return false, why end
```

---

## Logging: console and the Monitor

- Monitor: `/whip` → System → Monitor (needs whip.devtools + developer mode). Two ring buffers of 500 each: accepted (`ok`) and refused (`rejected` + `error`), so successes never evict refusals; kept until whip_core restarts; Clear empties the rings (counters stay). Each row: time, event (`cb:<name>` for callbacks), source, character name, status, reason, handler ms. Registry view: per event resource, calls, rejects, last call, effective rate limit. Live feed batched every 250 ms (max 200 per batch).
- Sentinel tampers appear as `sentinel:<key>` refusals (red "Tampered with <key>" rows); the Sentinel tab has its own 200-entry ring.
- Console: refusals print `[whip_core:secure] REFUSED <event> from <name> (src N): <reason>` (dead refusals add the `whileDead` hint). Throttled per player per event: one line per 5 s, then `(+N more held back in the last 5s)`. Successes never print. `Config.LogSecureRejections = false` silences refusal lines (default `true`); errors still print.
- Reasons are sanitised before logging: control characters → space, cut to 300 characters (a client cannot forge console lines).
- `GetErrorLog` (server/client) lists recent errors including SecureEvent/SecureCallback handler errors.

---

## What Sanitize does to incoming values

`Sanitize` (server/sanitize.lua) is whip_core-internal (not exported); the param types above are built on it.

| Helper | Behaviour |
|---|---|
| `Sanitize.string(val, maxLen?, default?)` | non-string → `default` (or `''`); pre-cut to `maxLen*4+64` bytes; strips 0x00–0x08, 0x0B, 0x0C, 0x0E–0x1F (keeps tab, newline, carriage return); cut to `maxLen` bytes, dropping a split trailing UTF-8 character; `''` → `default` |
| `Sanitize.key(val, maxLen=60)` | non-string → nil; removes everything but `%w`, `_`, `-`; empty → nil; truncates to maxLen (the `key` param refuses when this changed anything) |
| `Sanitize.number(val, min=-1e12, max=1e12, default=0)` | `tonumber`; NaN/±inf/non-number → default; then clamped (the fallback is clamped too) |
| `Sanitize.int(...)` | `math.floor(Sanitize.number(...))` |
| `Sanitize.id(val, min=1, max?)` | `tonumber`; rejects NaN, inf, fractions, < min, > max → nil; returns an integer |
| `Sanitize.amount(val, default?)` | `nil` → default; then `Sanitize.id(val)` (≥ 1, whole) |
| `Sanitize.enum(val, allowed, default)` | exact match or default |
| `Sanitize.AMOUNT_ERR` | `'Amount must be a whole number of 1 or more'` — the exact refusal every item, cash and bank export uses for a bad amount |

Note on control characters: the pattern `[%z\1-\8\11\12\14-\31]` keeps 0x09 (tab), 0x0A (newline) and 0x0D (carriage return); all other 0x00–0x1F are removed (sanitize.lua:41).

---

## Whip.command(name, opts, fn) — SERVER (lib/satellite.lua)

A chat/console command behind the same kind of gate as a SecureEvent. Use instead of `RegisterCommand` with hand-written checks. Requires `@whip_core/lib/satellite.lua` in your fxmanifest.

| opts key | Default | Behaviour |
|---|---|---|
| `dev` | `false` | `true`: only the server console and players with `HasDevTools` (whip.devtools + developer mode). Refusal `/<name> needs developer mode on (/w)` |
| `ace` | none | player needs this ACE (`IsPlayerAceAllowed`; no developer-mode rule). Refusal `/<name> is not for you` |
| `whileDead` | `false` | `true` allows while downed; else `Not while downed` |
| `rateLimit` | 3 at once, then one per second | `false`: none; or `{ burst = n, everyMs = ms }`. Refusal `Slow down` |
| `console` | allowed | `false`: refuse the server console (`/<name> is for players only`) |

- `fn(source, args, raw)` runs in its own thread (may wait). Errors print `/<name> failed: <err>`.
- Refusals: error toast to the player (`NotifyPlayer`), printed for the console. Console (source 0) skips dev/ace/dead/rate checks.
- Registered with `RegisterCommand(name, ..., false)` (not ACE-restricted by FiveM; WHIP does the gating). Per-player buckets cleared on drop.

```lua
Whip.command('ropes', { dev = true }, function(source, args, raw) ... end)
```

---

## Server-side `require` tables (Requirements)

`AddAction`'s `require` is a client hint; whatever the server does behind it (runtime points, item options) re-checks the same table with `Requirements.met(source, player, req)` (server/requirements.lua). Keys: `alive` (`false` allows downed), `vehicle` (`'in'`/`'out'`), `job` (keys or jobIds, ≤ 10), `onDuty`, `jobPermission`, `item` (key or `{item, count}`, ≤ 10, carried anywhere incl. accessory strip), `held` (server's record of the hand), `zone` (server's trusted zones only), `charId` (≤ 50), `ace` (with developer-mode rule for whip.devtools). A requirement key that cannot be read makes the caller refuse (never "no requirement"). Player-facing refusals: `Not while downed`, `You need to be in a vehicle`, `Get out of the vehicle first`, `Not for your job`, `You need to be on duty`, `You need <item>`, `You need it in your hand`, `Not here`, `Not for you`, `Not permitted`. Your own SecureEvent handlers must still check duty/job themselves (`IsPlayerClockedOn`, `HasJobPermission`).

---

## Sentinel: the statebag tamper guard

FiveM lets a client write its own player bag and bags of entities it owns; WHIP keeps `sv_stateBagStrictMode` off on purpose (voice resources etc. need client writes). The Sentinel (server/sentinel.lua) makes WHIP safe anyway. On by default, nothing to write.

### What it watches (every WHIP key starts `whip`)

| Key | Family | Value / truth source |
|---|---|---|
| `whipDead` | player | boolean; absent while alive at load; ledger |
| `whipJob` | player | active job key string, or `false` off duty; ledger |
| `whipEscorted` | player | boolean; ledger |
| `whipEscortedBy` | player | escorter's server id or nil; ledger |
| `whipDamageMod` | player | number, absent at exactly 1.0; ledger |
| `whipMeleeMod` | player | number, absent at exactly 1.0; ledger |
| `whipMood` | player | /mood name, absent for none; ledger |
| `whipVehicleId` | entity | tracked vehicle id for the entity |
| `whipVehicleSession` | entity | `true` for adopted street cars, else absent |
| `whipStats` | entity | stored stats block (empty → absent) |
| `whipLive` | entity | live stat values block |
| `whipAppearance` | entity | stored appearance (empty → absent) |
| `whipVehData` | entity | per-vehicle resource data (empty → absent) |
| `whipVehDoors` | entity | door bitmask, server's copy |
| `whipEngineHold` | entity | engine hold reason from the server's holds |
| `whipOvHold` | entity | Object Viewer hold bitmask (1 hidden, 2 invincible, 4 frozen) |

Names and charIds are never in a bag (bags replicate to everyone): use `GetPlayerFullName` (subject to `Config.ShowPlayerNames`).

Why it matters: e.g. attacker clients read the TARGET's `whipDamageMod`/`whipMeleeMod` bag and apply it with `SetPlayerWeaponDamageModifier` / `SetPlayerMeleeWeaponDamageModifier`; a forged modifier would make everyone pull their punches. Clients clamp the bag value to `Config.Sentinel.damageModifierClamp` (client/stats.lua:659) until the correction replicates, and the server's `GetDamageModifier` reports the same clamp.

### How a detection works
1. One `AddStateBagChangeHandler(key)` per watched key (native key filter: unwatched keys never reach Lua).
2. Player family: truth = the server ledger (what the server last wrote via its sanctioned write path). Entity family: truth = the key's registered `truth(entity)` function (`nil` = the entity should not carry the key → stripped).
3. Bag value deep-equals truth → echo, nothing happens. Otherwise: correction is queued for the next tick (`SetTimeout(0)`: FiveM runs change handlers before storing the value), re-reading truth and bag then; and the incident is recorded.
4. Record: reason `client wrote <value> (server: <truth>)` (values json, ≤ 120 chars); `RecordEventRejection('sentinel:<key>', src, reason)` (Monitor row); entry in the Sentinel tab ring (200); pushed to viewers; console `[whip_core:sentinel] TAMPER <key> (<family>) by <name> [src]: <reason> — reverted, strike N`.
5. Attribution: player family = the bag's player; entity family = `NetworkGetEntityOwner(entity)` at handler time (for a car, its driver). Ownership can migrate in between (rare).
6. An entity write made through `SetSentinelEntityKey`/WHIP's own writer that disagrees with truth is corrected and printed (`... wrote key = v but its truth says t — corrected, nobody struck (change your truth first, then write)`); nobody is struck.
7. A truth function that throws is printed and no correction is made.

### Strikes and kicks
- Every logged detection adds a strike to the attributed player. Repeats of the same key by the same player within `logDebounceMs` are one (no log, no strike; the correction still happens).
- Strikes reset after `strikesForgetMinutes` with no new strike, and when the player drops/rejoins.
- At `autoKick` strikes: a note is inserted into `admin_notes` (`SENTINEL KICK: N statebag tampers this session (last: <key> — <reason>)`, `createdBy = 0`, `createdByName = 'Sentinel'`, visible in Player Manager), then `DropPlayer(src, 'Kicked: statebag tampering detected (<key>)')`. A kick is not a ban.
- Reading results: one player struck on a key that helps them = a cheat. Several players struck on one key at once (e.g. right after an admin menu's revive) = a resource writing WHIP's keys: set `autoKick = false` and find it.

### Config.Sentinel (config.lua:1817)

| Key | Default | Meaning |
|---|---|---|
| `enabled` | `true` | `false`: no handlers are installed (zero cost); keys stay registered |
| `autoKick` | `3` | strikes before kick; `false` = record only |
| `strikesForgetMinutes` | `60` | minutes without a strike before the count resets; `false` = never |
| `logDebounceMs` | `1000` | repeats of one key by one player within this window count once |
| `bootSweep` | `true` | 2 s after whip_core starts, put back values left wrong across the restart (corrections only, no strikes) |
| `damageModifierClamp` | `{ min = 0.05, max = 4.0 }` | range damage/melee modifiers are held to (0.05 = 5% of the damage) |

`enabled`, `autoKick`, `strikesForgetMinutes` can be changed live in `/whip` → Settings → Config → Server (a saved value wins over config.lua; an empty "Kick after" box turns kicking off). Turning `enabled` back on reinstalls the handlers and runs a forced sweep (corrections, no strikes).

FiveM's own client bag-write limits (from FiveM source, noted in sentinel.lua): past 75 writes/s (burst 125) writes are dropped (`sbag-update-dropped`); past 150/s (burst 175) or 128 KB/s (burst 256 KB) the client is kicked ("Reliable state bag packet overflow").

### Rules for resource developers
- On the server, read the player sheet, `IsPlayerDead`, or `GetSentinelTruth(src, key)` — never `Player(src).state.whipX`.
- Never write WHIP's keys with `Player(src).state:set` / `Entity(e).state:set`: the writer looks exactly like a cheat and the player (or the car's driver) is struck. Use WHIP's exports (its revive for `whipDead`, job exports for `whipJob`, etc.).
- Guard your own replicated facts with `RegisterSentinelKey` + `SetSentinelPlayerKey` / `SetSentinelEntityKey`, or send them as server events instead of bags.
- Absence rule: write `nil` for "off", not `false` or a default value (an absent key replicates nothing). For entity truths, return `nil` at default, not `{}`.

---

## Sentinel exports

### RegisterSentinelKey(def) — SERVER
Puts one of your statebag keys under the Sentinel. Call inside `Whip.register`.

| Field | Type | Meaning |
|---|---|---|
| def.key | string | the bag key (non-empty) |
| def.family | `'player'` \| `'entity'` | player keys: truth = what you last wrote with `SetSentinelPlayerKey`; entity keys need `truth` |
| def.truth | function? | required for entity keys: `function(entity) -> value|nil`, run when the key changes; `nil` strips the key |

Returns: `true`, or `false, reason`: `'def (table) is required'`, `'def.key (string) is required'`, `"def.family must be 'player' or 'entity'"`, `'entity-family keys require def.truth (...)'`, or `Sentinel key "x" belongs to <owner>` (another resource's key, and WHIP's own keys, which whip_core always holds). Same resource again: no-op if family and truth unchanged; a satellite's truth function is a new reference each time, so it replaces (detection counters kept). Watches go when your resource stops.

```lua
Whip.core:RegisterSentinelKey({ key = 'mygang_tag', family = 'player' })
```

### SetSentinelPlayerKey(src, key, value) — SERVER
Writes the ledger first, then `Player(src).state[key] = value`. Your keys, or keys nobody watches.
- `src`: connected server id; `key`: non-empty string; `value`: any, `nil` for off.
- Returns `true`, or `false, reason`: `'key (string) is required'`, `'no such player'`, `'key "whipDead" is owned by whip_core'` / `'key "x" is owned by <resource>'`.

### SetSentinelEntityKey(entity, key, value) — SERVER
Writes an entity key with the "server writing" flag. Update the table your `truth` reads FIRST, then write. If they disagree the console warns, nobody is struck, and the key is set back to your truth.
- Returns `true`, or `false, reason`: `'key (string) is required'`, `'no such entity'`, `'key "x" is owned by <resource>'`, `'key "x" is watched as a player key'`, or a write error.
- A bare `Entity(e).state:set` of a watched key strikes whoever runs the entity (for a car, its driver).

```lua
tunes[plate] = t                                              -- your truth first
exports.whip_core:SetSentinelEntityKey(veh, 'mytune_data', t) -- then the key
```

### GetSentinelTruth(src, key) — SERVER
Returns the value the server last wrote for that player key (ledger), never the bag. Works for WHIP's keys too (`'whipDead'`, `'whipJob'`...). `false` and `nil` are different values. `nil` when nothing was written.

---

## Permissions model: ACE, WHIP permissions, developer mode

Two gates, plus the full-admin rule.

| | `ace = '…'` | `permission = '…'` |
|---|---|---|
| Given | `server.cfg` `add_ace` (FiveM ACE) | `GrantPermission`, or `/whip` → Players → Player Manager → player → Permissions (Director: `/whip` → Director → Access) |
| Scope | FiveM principal (identifier/group) | the ACCOUNT (`users.userId`): every character on it |
| Changes | server.cfg / console | at once, no restart; stored in DB table `whip_permissions` |
| Best for | full admins | staff roles given and taken while the server runs (builder, moderator, garage manager) |
| Dead player | let through (admin tool) | refused unless `whileDead = true` |

Permissions are staff roles, not jobs: for "police only" check the job (`HasJobPermission`, `IsPlayerClockedOn`, `require.job`).

### Full admins and developer mode
- Full admin = `whip.devtools` ACE AND developer mode on. With developer mode off, an account with the ACE is treated as an ordinary player everywhere (`/whip`, dev commands, admin doors, zones, `HasDevTools`, `ace = 'whip.devtools'`, permissions).
- Developer mode: switched in `/w`; per session — off at every join and after every whip_core restart; kept across a character swap. Visible (HUD stat "Developer Access Enabled", `Config` `HudDeveloperMark`) and logged (console line, activity log `dev_mode_on` / `dev_mode_off` with position). Turning it off closes every dev tool. Client local event `whip_core:devtools:modeChanged { on }`.
- Full admins hold every WHIP permission except ones declared `devtools = false` (and also hold undeclared names).
- A bare `IsPlayerAceAllowed(src, 'whip.devtools')` only means "may turn developer mode on"; ask `HasDevTools(source)` instead.
- First admin: a player without the ACE who types `/w` or `/whip` makes the server console print (once per player per visit) the line to paste: `add_ace identifier.license:<hex> whip.devtools allow` (works at once in the console; add it to server.cfg to keep it).
- Temporary dev tools: a permanent admin can give a player dev tools from the Player Manager until the restart: WHIP runs `add_principal identifier.license:<hex> group.whip_devtools`. server.cfg needs:
  ```
  add_ace group.whip_devtools whip.devtools allow
  add_ace resource.whip_core command.add_principal allow
  add_ace resource.whip_core command.remove_principal allow
  ```
  FiveM does not persist runtime principals, so a restart ends it. Temporary admins cannot give permissions unless they hold the permission's `grantedBy` by grant, and are not shown settings pages.
- Viewers of dev tools are re-checked on every push; an admin who loses the ACE is dropped from feeds and developer mode is switched off (`whip_core:client:devtoolsRevoked`).

---

## Permission and dev-tools exports

### RegisterPermission(name, def?) — SERVER
Declares a permission; the declaring resource owns the name. Call inside `Whip.register`. The declaration goes when your resource stops; grants stay in the DB and come back into force when it is declared again.

| Field | Type | Meaning |
|---|---|---|
| name | string | 3–64 chars of letters, digits, `.`, `_`, `-` (`^[%w_%.%-]+$`); convention: start with your resource's name |
| def.label | string? | shown in the Monitor when someone lacks it (cut to 60; default the name) |
| def.description | string? | a sentence for your screens (cut to 200) |
| def.implies | string[]? | permissions this one includes (each a valid name; itself ignored); walked transitively with loop protection |
| def.devtools | boolean? | `false`: full admins don't hold it automatically (default true) |
| def.grantedBy | string? | a permission whose holders (by grant) may give/take this one in WHIP's screens. Permanent full admins always may |

Returns: `true`, or `false, reason`: `'a permission is 3-64 letters, digits, ".", "_" and "-"'`, `'implies: x is not a permission name'`, `'grantedBy must be a permission name'`, `permission "x" belongs to <owner>`. A name not starting with your resource's name is warned in the console (once), not refused.

### HasPermission(source, name) — SERVER
Returns `boolean`: true via full admin (whip.devtools + developer mode on, unless `devtools = false`), a direct grant on the account, or a granted permission that implies it. Read from memory (no DB). Works on the character screen (joined account). `source` ≤ 0 (the console) or an invalid name → `false`.

### GrantPermission(who, name) · RevokePermission(who, name) — SERVER, WAITS
Give/take a permission on an account at once (DB write, then memory).

| Param | Type | Meaning |
|---|---|---|
| who | number \| table | an online server id; `{ charId = n }` (online or not; looked up in DB when offline); or `{ userId = n }`. A bare number is always a server id |
| name | string | the permission |

Returns: `true`, or `false, reason`. Reasons: `'No player with that server id is online (for a character, pass { charId = n }; for an account, { userId = n })'`, `'a person is a server id, { charId = n } or { userId = n }'`, `'an account is { userId = n }'`, `'no such character'`, `'that is not an account'`, `'no permission called x'` (grant needs a currently declared name; revoke only a valid name), `'permissions are still loading'`, `'Could not save that (database error)'`.
- Grant of a permission already held → `true`, nothing fires. Revoke of one not held → `true`.
- On change: server local event `whip_core:permission:changed { userId, permission, granted }`; on every online game of that account, client local event `whip_core:permission:changed { permission, granted }` (carried by whip's own `whip_core:client:permissionChanged`; do not listen to that one). WHIP shows the player nothing. Activity log `permission_given` / `permission_taken` names your resource as the giver.
- The exports are trusted server code: they don't check `grantedBy` (that rule is for WHIP's panel). Gate your own command/screen that calls them.

### GetPermissionHolders(name) — SERVER, WAITS
Everyone given it directly (full admins are not listed), named by their online or latest character.
Returns: `{ { userId, name, charId, account, grantedBy, grantedAt, online }, ... }` sorted by name, or `false, 'no permission called x'` for an invalid name. `grantedBy` is the giver's name text.

### HasDevTools(source) — SERVER / HasDevTools() — CLIENT
Server: `true` when the player holds `whip.devtools` AND developer mode is on (console `0` → true via DevTools; the export takes `tonumber(source)`). Client: whether developer mode is on for this player — for display only; the server's answer is the one that counts.

### SetDeveloperMode(source, on) — SERVER
For tools acting for a player (e.g. keeping it on across whip_core restarts). On only for a player with whip.devtools; logged with the asking resource. Returns `true`, or `false, 'You do not have dev tools'`.

### Built-in permissions (whip_core)
| Name | Label | Implies | grantedBy |
|---|---|---|---|
| `director.build` | Director builder | — | `director.admin` |
| `director.admin` | Director admin | `director.build` | `director.admin` |
| `director.live` | Dungeon Mode | — | `director.admin` |

Panel sections opened by permission: Director overview/scenarios/lore/shipped/runs (`director.build`), Access (`director.admin`), Live (`director.live`). Full admins open everything.

```lua
Whip.register(function()
    Whip.core:RegisterPermission('mygarage.manage', { label = 'Garage manager' })
    Whip.core:SecureEvent('mygarage:remove', {
        permission = 'mygarage.manage',
        params     = { {'garageId', 'id'} },
    }, function(source, player, garageId) --[[ only managers or full admins ]] end)
end)
exports.whip_core:GrantPermission(targetSource, 'mygarage.manage')
```

---

## WHIP's own unguarded net events

For reviewers: the only raw `RegisterNetEvent`s on whip_core's server, each deliberately outside SecureEvent and gated by hand:
- `whip_core:server:triggerCallback` — the callback transport (flood ceiling 25 ms / burst 40; SecureCallback's checks run inside).
- Event Monitor: `whip_core:server:emGetAll`, `whip_core:server:emClearLog` (both `DevTools.isAllowed`), `whip_core:server:emClosed` (ungated: leaving is never refused).
- Sentinel tab: `whip_core:server:snGetAll`, `whip_core:server:snClearLog` (gated), `whip_core:server:snClosed` (ungated).

`whip_core:client:*` / `whip_core:server:*` names are WHIP's internal network messages; resources listen to the local `whip_core:<domain>:<pastTense>` events instead (one table payload, `WhipEmit` = `TriggerEvent`).

---

## Coming from ESX / QBCore / ox_lib

| Today | WHIP |
|---|---|
| `RegisterNetEvent` + `AddEventHandler` (server) | `SecureEvent` |
| `ESX.RegisterServerCallback`, `QBCore.Functions.CreateCallback`, `lib.callback.register` | `SecureCallback` — return the answer, no `cb` |
| `ESX.TriggerServerCallback`, `QBCore.Functions.TriggerCallback`, `lib.callback.await` | `Callback` — waits and returns the answer |
| `RegisterCommand` with own checks | `Whip.command` |
| `IsPlayerAceAllowed(src, 'admin')` for staff roles | `permission = '…'` / `HasPermission` |

Migrating an event: swap the call, list its values in `params`, delete the hand-written checks (alive, rate, type, range), declare it in `Whip.register`, treat `return false` as "refused". One event at a time is fine.

---

## Security review checklist for WHIP resources

Grep and check, server side first.

1. `RegisterNetEvent(` in server files → should be `SecureEvent` (only exceptions: client-side handlers for your own server→client messages). `AddEventHandler` for a net name is the same problem.
2. `TriggerServerEvent(` in client files → each name must match a `SecureEvent` with a `params` entry for every argument, in order; no extra args relied on.
3. `lib.callback`, `CreateCallback`, `RegisterServerCallback` → `SecureCallback`; client side → `exports.whip_core:Callback`.
4. `'any'` params → replace with `record`, `list`, `slot`, `id`, `key`, or check the value by hand.
5. `'int'` or `'number'` used for money, counts, quantities or ids → `'amount'` (with a `max`) or `'id'`; they clamp `-50` into range instead of refusing.
6. `'string'` without `maxLen` → unbounded length; always give one. `'key'` for anything that names a thing.
7. Values taken from the client that the server already knows: prices, item keys to give, amounts to pay, job names, coords, entity handles, charIds, another player's id without `'player'`, a vehicle as entity/netId instead of `'vehicle'` (vehicleId). The server looks them up itself.
8. Item/stash/car access: uses `'slot'`, `'addr'`, `'vehicle'` (ownership checked), not a raw slot number/container id/plate.
9. Anything location-bound (shop, counter, door, stash, car, NPC) without `near` → add `near`. `near.at` as a function must return `nil` for unknown ids (not a default position). Long actions re-check position at the end (`Progress` `near`).
10. Handlers that wait (`Wait`, `Progress`, `SkillCheck`, `MySQL.*.await`, any `---@async` export) then give/take → `IsSessionCurrent(source, player.session)` after the wait.
11. Global `source` used inside the handler body after a yield or in helper functions → use the handler's `source` parameter.
12. Handlers that refuse with bare `return` (silent, logged ok) → `return false, 'why'` (or `RecordEventRejection`).
13. SecureCallback returning `nil` to refuse → `return false, 'why'`; long-running work inside a callback (> 10 s) → SecureEvent.
14. `rateLimit = false` → justify it; drag-and-drop/close events have a `burst`; lock-taking handlers keep `burst = 1` and use `TrackInvocationLock`.
15. `whileDead = true` → only for respawn, closing UI, releasing escorts, chat, logout, passive reports.
16. Admin actions: `ace = 'whip.devtools'` (or `HasDevTools(source)`), never `IsPlayerAceAllowed(src, 'whip.devtools')` (skips developer mode). Staff roles: `permission`. Dev pages, Object Viewer options, Director buttons: the server handler checks `HasDevTools` or the permission itself.
17. `Player(src).state:set` / `Player(src).state.x =` / `Entity(e).state:set` on server → never for `whip*` keys; own keys through `RegisterSentinelKey` + `SetSentinel*Key`. Server reads of `state.whipDead`/`whipJob` → sheet / `IsPlayerDead` / `GetSentinelTruth`.
18. Client-side checks deciding outcomes (client computes reward, client says "job done") → server decides; client only asks.
19. `RemoveItem` then `AddItem` / separate money and item calls for one action → `StoreMove` / one action; own rows with `CommitWithAction`. Remember `return false` does not roll back.
20. Registrations at file top level instead of inside `Whip.register` → lost on whip_core restart, and may run before whip_core is ready.
21. Event/permission names without your resource prefix → collisions are first-come-first-served; prefix them.
22. `onReject` hooks reading `rawArgs` without checks; `near.at` / `range` functions that can throw.
23. `RegisterCommand` with own checks → `Whip.command` (dead rule, rate limit, dev/ace gating).
24. Monitor test: send bad values from F8 (`TriggerServerEvent('x', -50)`, strings, tables, huge strings) and confirm refusals appear with reasons in `/whip` → System → Monitor.

---

## Gotchas

1. `rateLimit = N` alone is a flat cooldown (burst 1), stricter than the default (10 then 100 ms). A UI that fires a few quick calls will silently lose them: add `burst`.
2. Rate-limit tokens are spent by calls that are then refused for other reasons (ACE, dead, params, near).
3. Callbacks share a hidden per-player flood ceiling (25 ms, burst 40) across ALL callbacks; drops are silent and surface as `'No answer from the server'` after 10 s.
4. `ace` lets dead players through; `permission` does not. Add `whileDead = true` if a dead permission-holder must act.
5. `ace = 'whip.devtools'` refuses admins with developer mode off (they get a toast); `IsPlayerAceAllowed` alone would not.
6. Dead players are refused everything by default; an event that "does nothing while downed" is usually missing `whileDead`. The console line names it.
7. `bool` with no default turns a missing value into `false`, not a refusal.
8. `key` refuses rather than cleans: `'legion.sq'`, a number, or a string longer than `maxLen` is refused.
9. `enum` matches exactly: a number sent as `"1"` does not match `1`.
10. `string` without `maxLen` has no length limit; a non-string with a `default` silently becomes the default.
11. `number`/`int` without a `default` refuse a non-number, but with a `default` a non-number becomes the default UNCLAMPED, while NaN/inf become the default clamped.
12. `slot`/`addr` values handed to your handler are copies: changing `metadata` changes nothing; use `SetItemMetadata` etc. with `.addr`.
13. `vehicle` takes a vehicleId, not an entity or netId; adopted street cars are refused unless `session = true`.
14. `near` uses the client-reported ped position, checked only on arrival; `near.at` returning nil refuses (`allowUnknown` to let it through).
15. For a SecureCallback, a `near` refusal answers `'Too far away'` (not your `near.message`, which is only the toast).
16. SecureCallback `false, why` is logged as ok and shows no toast; SecureEvent `false, 'why'` shows an error notification.
17. A callback answer is cut at its first `nil` across the export boundary: never return `nil, 'why'` or put `nil` before useful values.
18. `return false` or an error in a handler does not undo whip saves made in it: refund explicitly.
19. Use the handler's `source`, not the global; `player` is a copy without `metadata` (`GetPlayer(source).metadata`).
20. A stopped resource's events are dropped silently until it registers again; another resource may take the name meanwhile.
21. Registering the same event from two resources: the second is refused with the owner's name; check the return of `SecureEvent` (Whip.core inside `Whip.register` prints refusals for you; `exports.whip_core` does not).
22. Writing a `whip*` statebag key directly from any resource strikes players (and kicks at 3). After an admin menu revive, mass strikes on `whipDead` mean a resource, not cheaters.
23. Write entity truth before calling `SetSentinelEntityKey`; write `nil` (not `false`/`{}`) for "off".
24. `HasPermission(0, ...)` (console) is false; `HasDevTools(0)` is true.
25. Developer mode is off after every join and every whip_core restart; tools that need it on use `SetDeveloperMode`.
26. Grants are per account (`userId`), so every character of that player has the permission; a declaration disappearing (resource stopped) leaves grants in force and makes full admins hold the name.
27. `Whip.command` `ace` does not apply the developer-mode rule; use `dev = true` for admin commands.

---

## Docs vs code

1. Names "starting with your resource's name": not enforced for SecureEvent/SecureCallback (registries created without `prefixed`, secure.lua:1150-1151, so not even a warning) and only warned for permissions (`prefixed = true`, permissions.lua:40; shared/registry.lua:221). Ownership is first-come-first-served.
2. `types/classes.lua` `WhipSecureSchema.burst` says "default 1"; code defaults to 10 when `rateLimit` is omitted and 1 when it is given (secure.lua:990-994). The docs table is correct.
3. Docs list SecureCallback refusals as the check reasons; code returns the player sentence instead of the detailed reason when a param check has one (e.g. `'That is not your vehicle'`, secure.lua:1729), and returns the log reason (`'Too far away'`), not `near.message`, for a near refusal (secure.lua:1751).
4. `GetPermissionHolders` rows also carry `charId` (permissions.lua:271), not in the docs' return shape.
5. `HasPermission` returns `false` for source 0 / non-positive ids (permissions.lua:132); not stated in docs.
6. Docs: `string` written `{name, 'string', maxLen, default?}` implies maxLen is required; code does not check it and treats a missing `maxLen` as unlimited (secure.lua:1177-1231, sanitize.lua:39).
7. Undocumented: calls of a stopped resource's SecureEvent are dropped silently with no Monitor entry (secure.lua:1472); only callbacks answer `'That is no longer available'`. Docs also say `string` strips control characters "but tab and newline"; carriage return (0x0D) is kept too (sanitize.lua:41).
8. `types/server.lua` SecureEvent stub lists the sheet fields without `session`; `handlerSheet`/`lightSheet` do include `session` (player.lua:810, 846).
