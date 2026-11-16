# WHIP core concepts, the satellite helper and the example resources

What WHIP is, how a resource plugs into it, the rules every WHIP resource follows, and the two worked examples. Built from doc anchors `#overview`, `#quickstart`, `#first-resource`, `#first-job`, `#common-calls`, `#how-whip-thinks` (incl. `#ensuretable`, `#commitwithaction`, `#giveonlogin`), `#patterns`, `#patterns-registering`, `#patterns-satellite`, `#whip-way`, `#glossary`, `#what-you-can-change`, `#testing`, `#both-platforms`, `#selling`; checked against `whip_core/lib/satellite.lua`, `types/satellite.lua`, `shared/registry.lua`, `server/migrations.lua`, `server/lifecycle.lua`, `server/setup_report.lua`, `server/requirements.lua`, `server/updates.lua`, `server/pending_gives.lua`, `server/satellites_back.lua`, `server/player_lifecycle.lua`, `client/ready.lua`, `shared/platform.lua`, `fxmanifest.lua`, `docs/examples/*`.

## Contents
- What WHIP is
- Install, server.cfg, setup report, updating
- The resource skeleton (fxmanifest, autocomplete)
- The one rule: Whip.register
- Five ideas (ids, stores, save model, declarations, server decides)
- Where your data lives
- EnsureTable, CommitWithAction, GiveOnLogin
- Return values, codes vs sentences
- Naming a person, lookups
- Two export gotchas (funcrefs, nil returns)
- The registration rule, prefixes, GetRegistrations, run tags (ReleaseTag, GetTagged)
- The satellite helper: every Whip.* function
- Calling whip_core: exports vs Whip.core
- How whip_core announces readiness (onReady) and restarts satellites
- Load order (whip_core fxmanifest) and why it matters
- whip_core's stop, final save and start steps
- Setup report, whip_requires, whip_updates
- The calls you'll use; how WHIP talks to your resource
- The WHIP way
- What a resource can change
- Testing and measuring; export cost tiers
- Legacy and Enhanced
- Selling, licence, escrow
- Glossary
- Example: whip_cafe_example
- Example: whip_delivery_example
- Gotchas
- Docs vs code

---

## What WHIP is

- A full FiveM framework: characters, inventory (F2), money as banknote items plus banks, jobs, vehicles, keys, garages, properties, prompts (`AddAction`), UI library, Director (scenario builder), admin panel `/whip`, quick tools `/w`. Needs only FiveM + oxmysql. Replaces QBCore/ESX/ox_core and their inventory, target, garage, banking resources. No bridge to other frameworks.
- ~650 exports; a typical job/shop/mission uses ~20 (see "The calls you'll use").
- Selling points (all enforced in code): `SecureEvent` declares what it accepts (rate, values, distance) and refuses the rest before your handler; items are physical (cash = banknotes, bags weigh their contents, a boot is a stash); one player action = one DB transaction; settings live in `/whip` → Settings and resources can add a page.

| Resource | What |
|---|---|
| `whip_core` | Players, characters, inventory, money/banks, jobs, vehicles, garages, properties, prompts, UI library, Director, admin panel, dev tools |
| `whip_gunny` | Weapons: magazines, calibers, melee, throwables, attachments |
| `whip_fuel` | Fuel tanks, pumps with hose, jerry can (registers the `fuel` vehicle stat; whip_core has no fuel of its own) |
| `whip_rope` | Physics rope: carry, tie, tow |
| `whip_phone` | The Duo phone; apps are modules from any resource |
| `whip_autos`, `whip_autos_shop` | Whiplash: customisation, turbos, nitrous; shop in Burton |
| `whip_voice` | 3D voice on its own voice server |
| `whip_chat`, `whip_loadingscreen` | Chat, loading screen |
| `whip_media_*` (`[assets]/[media]`) | Clothing/furniture/vehicle/NPC/tattoo pictures, emote videos, map |
| `whip_homes_mirrorpark`, `whip_graphics` (`[assets]`) | Every Mirror Park house walk-in + 25 garages; LED streetlights, lighting/sky |

Each depends only on whip_core. Every resource runs on FiveM Legacy and GTA V Enhanced.

## Install, server.cfg, setup report, updating

Requirements: FXServer with txAdmin — Legacy artifact 38435+ or Enhanced (cfx-server); MariaDB 10.2.3+ or MySQL 8.0.16+ with a login that can create a database; ~1 GB disk; ≥10 Mbit/s to GitHub (txAdmin gives each download 150 s; largest ~145 MB); voice ports inbound UDP 7882-7893 and TCP 7881.

Install = txAdmin "Remote URL Template" recipe (a fresh server only; cannot be added to an existing server):
- Legacy: `https://raw.githubusercontent.com/WHIPFX/txAdmin-recipe/main/whip-legacy.yaml`
- Enhanced: `https://raw.githubusercontent.com/WHIPFX/txAdmin-recipe/main/whip-enhanced.yaml`

The recipe downloads WHIP + WHIPFX's oxmysql, creates an empty DB, turns OneSync on, writes server.cfg, makes the txAdmin account admin. No SQL import: whip_core creates its tables.

server.cfg it writes (essentials):
```
sv_licenseKey "..."
set mysql_connection_string "mysql://user:password@localhost/whip_1A2B3C"
sv_enforceGameBuild 3889            # Legacy only
set sv_enforceSteamAuth true        # players need Steam linked to Cfx.re
ensure oxmysql
ensure whip_core
ensure whip_autos / whip_autos_shop / whip_chat / whip_fuel / whip_gunny / whip_loadingscreen / whip_phone / whip_rope
add_unsafe_child_process_permission whip_voice
ensure whip_voice
ensure [assets]
add_ace group.admin whip.devtools allow
add_principal identifier.fivem:1234567 group.admin
```
- Only `oxmysql` must precede WHIP's ensures; your resources go after them. Stock `chat`, `spawnmanager`, `basic-gamemode` are not installed (WHIP has its own; the setup report flags spawnmanager/basic-gamemode/chat as FIX).
- Enhanced instead of `sv_enforceGameBuild`: `setr whip_platform enhanced` (must be `setr`) and `set sv_resourceFileDownloadTimeout 600000`.
- Check: a few seconds after start the console prints the setup report; each `FIX` line says what to change; with nothing to fix `Framework loaded successfully!` follows. `whipsetup` (server console only) reprints. F2 inventory, `/w` quick tools, `/whip` admin panel. A player typing `/w` without the ACE makes the console print the `add_ace` line for them.
- Updating: each resource has its own GitHub releases; stop the server, replace the folder; DB carries over (whip_core migrates on next start). First copy out `whip_core/pack_exports` (Director packs), in-game pictures (`whip_media_props/img/props`, `whip_media_previews/img/vehicles`) and `whip_autos/engines.json`.

## The resource skeleton

```lua
fx_version 'cerulean'
game 'gta5'
lua54 'yes'
dependency 'whip_core'
whip_requires '1.0'
shared_scripts { '@whip_core/lib/satellite.lua', 'shared.lua' }
server_script 'server.lua'
client_script 'client.lua'
files { 'html/img/items/*.webp' }   -- item pictures, if any
```
- `dependency 'whip_core'`: whip_core starts first, and your resource is stopped when whip_core stops; whip_core then restarts it itself (see "readiness and restarts").
- `whip_requires '1.0'`: the setup report prints FIX when whip_core's `version` is older.
- `@whip_core/lib/satellite.lua`: load with `shared_script`, never copy (licence + it must run in your Lua state). whip_core lists it in its own `files {}` so clients can fetch it.
- Autocomplete: copy `whip_core/types/luarc.template.json` to your resource as `.luarc.json`; VS Code + sumneko Lua. It finds types at `../whip_core/types` or next to a `[whip]` folder; edit the path for other layouts.
- Item pictures: `html/img/items/<item key>.webp` (or `.png`; webp used over png) in the registering resource, listed in `files {}`.
- Coordinates: `/w` → Coords, stand there, press G copies `vector4(x, y, z, heading)`.
- Dev loop: server console `refresh`, `ensure myres`, later `restart myres`. Errors: server console and F8. `/whip` → System → Monitor lists every SecureEvent/SecureCallback call, accepted or refused, with reason and handler time.

## The one rule: Whip.register

whip_core keeps everything declared to it (items, use handlers, secure events, callbacks, actions, stats, zones, store kinds…) in memory and forgets it when it restarts. So every declaration goes inside `Whip.register(fn)`, which runs `fn` once whip_core is ready and again after every whip_core restart.
- Don'ts: `CreateThread(function() Wait(1000) … end)` registers once (a whip_core restart silently strips your items); watching `onResourceStart` misses the first start.
- Running twice is safe (registration rule: same thing again changes nothing).
- Inside `Whip.register`, call through `Whip.core:Name(...)`: a refused declaring call prints one console line naming resource, export, reason.
- One function may hold everything: loops over `Config`, storing an answer (an `AddAction` id), resetting your own state (`runs = {}` in the delivery example). It re-reads `Config` each run, so settings-page values are included.

## Five ideas

1. Accounts, characters, sessions:

| Id | Names | Lasts | Used by |
|---|---|---|---|
| `source` | connected player | until they leave; reused by next joiner | everything about someone online: `GetPlayer`, `AddItem`, `NotifyPlayer` |
| `{ charId = n }` | a character, online or not | forever — save this | calls that reach someone offline: `PayPlayer`, `GiveOnLogin`, bank |
| `userId` | an account (up to `Config.MaxCharacters` characters) | forever | staff permissions (`GrantPermission`) |
| `player.session` | one load of a character | until logout | `IsSessionCurrent(source, session)` after a wait |
| `vehicleId` | a car WHIP knows | owned: forever; others: until restart (ids 1,000,000,000+) | every vehicle export |

2. Every place items sit is a store, addressed `{ kind, id, sub, slot }` (pockets, stash/container, boot/glovebox/ignition, shop, wallet/panel). `StoreMove` moves between any two with the same checks.
3. Memory first: WHIP changes memory at once and writes within ~1 s; everything one player action changes is written in one transaction (a crash never leaves half).
4. Declarations live in whip_core's memory → `Whip.register`.
5. The server decides. A game only asks. `SecureEvent` checks who, how often, from where and every value before your handler. An action's `require` is a courtesy, never the check.

## Where your data lives

| Data | Put it in | Saved by | Visible to |
|---|---|---|---|
| Items/cash a player carries | pockets: `AddItem`, `PayPlayer` | WHIP, with the action | player, admins |
| Something about one item (serial, rounds, wear) | metadata: `SetItemMetadata` | WHIP, with the item | holder's game too — never a secret |
| Fact about a character (licence, quest step) | `SetPlayerFlag` (online); `SetPlayerMetadata`, `GiveOnLogin` or bank for offline | WHIP, with character | their game too — never a secret |
| Something about a car (fitted part, finance flag) | `SetVehicleData`; a gauge is a vehicle stat | WHIP, with the car | games near the car (stats) |
| Items kept somewhere new (mailbox, vault) | container (`EnsureContainer`) or your own store kind | WHIP | whoever its rules allow |
| Resource settings | `Whip.configPage` | WHIP, in DB | admins edit in `/whip`; every game reads it unless entry says `sides = 'server'` |
| A player's own choice (volume, toggle) | `Whip.playerSetting` | their PC (your KVP) | that player |
| Anything else (ledger, leaderboard) | own table via `EnsureTable`; `CommitWithAction` after an inventory change | you | whoever your code shows it |
| Item for an absent character | `GiveOnLogin` | WHIP until next login | them on arrival |

## EnsureTable, CommitWithAction, GiveOnLogin

### EnsureTable(name, createSql, migrations?) — SERVER, WAITS
Creates your own table the way WHIP creates its own (no `.sql` import). Source `server/migrations.lua:966`.
- `name`: letters/digits/`_`, ≤64 chars, else `false, 'a table name is letters, digits and _ (64 at most)'`.
- `createSql`: one complete statement containing `CREATE TABLE IF NOT EXISTS` (checked case-insensitively). Text collation `utf8mb4_unicode_ci` is appended to table options unless the options already name a `COLLATE` (`server/helpers.lua:15,21`).
- `migrations`: list, append-only, in order. Each `{ id = string, statements = {...}?, run = function? }`. Recorded in `schema_migrations` as `'<resource>:<id>'`; that string must be ≤64 chars (`migration "x": "res:x" is longer than 64`). Missing id → `migration N needs an id`.
- Statement: a plain SQL string, or `{ sql = '...', unless = guard?, onlyIf = guard? }`. Guard = `{ column = { table, name } }` | `{ index = { table, name } }` | `{ constraint = { table, name } }` (only the first present key is used: index, then column, then constraint; empty guard errors). `unless`: skip if it exists; `onlyIf`: skip if it does not.
- `run`: called after the statements (in whip_core, through pcall). Throw = failure; return `false` = "incomplete": not recorded, later migrations still run, retried next start. `Migrations.has.*` probes are whip_core-internal — a satellite's `run` must query `information_schema` itself.
- Behaviour: waits for whip_core ready (≤60 s, else `false, 'whip_core has not finished starting (see its console)'`). If this call created the table, all migrations are recorded done without running (the CREATE must already contain every change — "put each change in both places"). Otherwise pending ones run in order; the first failure returns `false, 'migration "<id>" failed: <err>'` and later ones wait for next start. CREATE failure: `false, 'could not create \`name\`: the server console says why'`.
- Returns `true` or `false, why`.
```lua
Whip.register(function()
  Whip.core:EnsureTable('mycafe_orders', [[CREATE TABLE IF NOT EXISTS `mycafe_orders` (
    `id` INT UNSIGNED NOT NULL AUTO_INCREMENT, `charId` INT NOT NULL, `note` VARCHAR(200) NULL,
    PRIMARY KEY (`id`)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4]], {
    { id = '002_note', statements = {
      { sql = 'ALTER TABLE `mycafe_orders` ADD COLUMN `note` VARCHAR(200) NULL',
        unless = { column = { 'mycafe_orders', 'note' } } } } },
  })
end)
```
whip_core's own migration list (internal): ids from 022 (001-021 squashed into CREATEs), a new database records them all as done ("new database: every table made"); failure halts start-up.

### CommitWithAction(queries, opts?) — SERVER, WAITS
Runs your queries in one transaction together with everything the player's current action changed that WHIP has not written yet (the item taken and your ledger row land together or neither). Outside an action: your queries alone.
- `queries`: non-empty list of `{ query = '...', values = {...}? }` (else `false, 'queries is a list of { query = "...", values = { ... } }'`).
- `opts`: `{ source?, vehicleId? }` — whose action, when called outside the handler that made the change.
- Returns `true`, or `false, 'Could not save that (database error)'` (nothing of the transaction landed; WHIP rewrites its own part later). `server/stores.lua:3083`.
```lua
local ok, why = exports.whip_core:RemoveItem(source, 'mycafe_coffee', 1)
if not ok then return false, why end
ok, why = exports.whip_core:CommitWithAction({
  { query = 'INSERT INTO `mycafe_orders` (`charId`, `note`) VALUES (?, ?)', values = { player.charId, 'coffee' } },
})
```

### GiveOnLogin(who, item, amount?, metadata?, opts?) — SERVER, WAITS
Item for someone who may be offline. `who`: server id or `{ charId = n }`. Online (and that sheet is current): given now via the inventory, returns `'now'` (pockets, or feet if full). Offline: row in `pending_gives`, returns `'login'`; handed over at next login into pockets (at their feet when full), each row deleted once given; a failed give stays for next login; a deleted character takes theirs (FK cascade).
- `opts`: `{ reason }` or a reason string; truncated to 120 chars; logged as `<reason> (from <resource>, while away)`.
- Failures: `false, why` for no such person, `Unknown item "x"` (must be in `Config.Items`, i.e. registered), bad amount, metadata not a table or not saveable, DB error. `server/pending_gives.lua:39`.

## Return values

Every export: first value is the result or `false`; second is why. Exports don't throw and never return `nil, 'reason'` (an export's returns are cut at the first nil).

| Kind | Success | Failure |
|---|---|---|
| Change something | `true` or more useful truthy (`AddItem` → `'inventory'`/`'ground'`; `StoreGive` → slot) | `false, why` |
| Read about a player | the value | list/count/yes-no → empty form + why: `{}, why` · `0, why` · `false, why`; a single value (stat, coords, sheet) → `nil` |
| Check (may they?) | `true` | `false, why` (`CanUseBankAccount`, `HasPropertyAccess`, `HasJobPermission`, `CanUseDoor`) |
| Create | the new thing (table); vehicles return `vehicleId` (`CreateOwnedVehicle`, `SpawnTempVehicle`, `AdoptVehicle`) | `false, why` |
| Delete | `true` | `false, why` |
| Look up | a table | `nil` when nothing; `false, why` when the question is wrong |
| Return an id | the id (`AddAction`, `AddPoint`, `HoldMoney`, `WatchVehicleStat`) | `false, why`; with a 3rd value (`AddAction`, `UpdateAction`, `AddPoint` warnings) the 2nd is `false` on success so the 3rd survives |

Codes vs sentences: `Progress` and `SkillCheck` return codes (`'busy'`, `'cancelled'`, `'too far'`, `'failed'`, ...) — branch on them and write your own words. Everything else returns a sentence (`'Not enough cash'`) — show it or return it from a SecureEvent; never compare it (wording may change).

## Naming a person, lookups

- Person argument: bare number = server id (must be online); `{ charId = n }` = a character, online or not. A bare number is never a charId except exports whose name says so (`GetCharacterProperties(charId)`). A param named `source` is always a server id. Some calls need the person online anyway (car key, `TransferVehicle`). Internally `WhoIs` errors: `'A character is { charId = n }'`, `'No player with that server id is online (for a character, pass { charId = n })'` (`server/helpers.lua:96`).
- Lookups: `GetX(ref)` with an id or a one-key table (`GetVehicle({ plate = 'ABC123' })`, `GetShop({ key = 'burgershot' })`, `GetPlayer({ charId = 42 })` — online only). Lists: `GetXs(filter?)` (`GetShops({ job = 'burgershot' })`).

## Two export gotchas

1. A function passed through an export arrives as a callable reference, not `type() == 'function'`. Test `fn ~= nil` and call it (`pcall(fn, ...)`); never type-check callbacks in an export you write.
2. A `nil` returned through an export arrives as no value; nesting the call as an argument passes nothing. Assign to a local first: `local d = exports.whip_core:GetVehicleData(id, 'key'); if type(d) == 'table' then`.

## The registration rule

Implemented once in `shared/registry.lua` (~40 registries; server and client each have their own copy).

| You register | Result |
|---|---|
| New | yours, `true` (Reg:add returns `true, key`) |
| Same again (deep-equal, functions by identity) | nothing: no reset, no rebroadcast |
| Changed version of your own | replaces it |
| Someone else's (owner still running) | `false, '<label> "x" belongs to <owner>'`; printed once per reason in console (F8 on client) and listed (first 8) in the setup report |
| Name starting `whip_core:` (reserved registries) | `false, '<label> "x" is reserved: names starting "whip_core:" belong to whip_core'` |

- Owner is read via `GetInvokingResource()` at the call, never from arguments.
- Your entries are swept when your resource stops. Items are the exception (sweep = false: players still carry them), but they stop being yours and another resource may take the name.
- A stopped owner's names are free again (`alive()` checks resource state).
- whip_test's refusals are never printed.

Prefixes: items, right-click action names, stats, vehicle stats, server zone ids and permissions are one server-wide list, first come first served. Prefix with your resource name + `_` (`mycafe_coffee`); events/callbacks use `:` (`mycafe:buy`). Unprefixed names still work but a prefixed registry prints once per resource, 3 s after registration, a yellow line like `[whip_core] mycafe registers 3 items whose names do not start with "mycafe" (coffee, bagel, tea)...`. Accepted separators after the resource name: `_ : . -`, case-insensitive. Exempt: whip_core and any `whip_*` resource.

The resource name is the folder name, which you do not control once you publish: a GitHub ZIP unpacks as
`<repo>-main` (seen with an ATM resource: `whip-atmdui-main registers 2 items whose names do not start with...`).
Build item keys (and their `image` paths) from `GetCurrentResourceName()` instead of writing `myres_card` by hand:
`local CARD = GetCurrentResourceName() .. '_card'`. Tell server owners to pick the folder name once: renaming it
later renames the items, and items already handed out keep the old key.

Names WHIP already uses: items `phone`, `sim_card`, `rope`, `radio`, `megaphone`, `nitro`, whip_gunny's weapons/magazines/ammo (`weapon_pistol`...), every item in whip_core's `config.lua`; vehicle stats `nitro`, `boost`, `fuel`. `/whip` → Economy → Items shows each key's owner.

### GetRegistrations(resource?) — BOTH
Everything registered on this side (events, callbacks, items, stats, actions, stat listeners, client hooks, settings, `/w` pages, debug tools, held props, control blocks...) or one resource's share. Returns `{ { registry, key, owner }, ... }`; a non-string resource returns `{}`.

### ReleaseTag(tag) — BOTH
Removes everything your resource registered under a run tag in every module (registries plus "joiners": temp cars, NPCs, ground rows, bars, skill checks, blips, prop sets...) in a fixed order, and closes the tag for you: later registrations under it are refused `'<label> "x": <tag> has ended'`. Tag: non-empty string ≤100 chars. Returns `true, count` or `false, 'a tag is a short piece of text, like "run:42"'`. Releasing never touches another resource's entries or another tag. A stopped resource's closed tags are forgotten (it may reuse labels). Pass tags as `{ tag = 'run:42' }` in a registration's options on modules that support it (e.g. `SpawnNpc(def, { tag })`, `SpawnTempVehicle(model, coords, { tag })`, `ShowBlip` spec `tag`, `Progress`/`SkillCheck` `tag`). Shared-key registries refuse tags. Director runs use a run tag released for every owner (`Registry.releaseTagEverywhere`), so anything any resource made with `run.tag` goes when the run ends.
```lua
local tag = 'heist:' .. jobId
exports.whip_core:SpawnNpc({ model = 's_m_m_security_01', coords = guardPos, behaviour = 'guard' }, { tag = tag })
exports.whip_core:SpawnTempVehicle('stockade', vanPos, { tag = tag })
local ok, count = exports.whip_core:ReleaseTag(tag)
```

### GetTagged(tag) — BOTH
What you hold under a tag: `{ { registry, key }, ... }`; `{}` for an unknown or bad tag.

## The satellite helper: every Whip.* function

`lib/satellite.lua` runs inside your resource (it must remember your registrations across a whip_core restart; whip_core's state dies with it). It defines the global `Whip`.

### Whip.register(fn) — BOTH
- Appends `fn` to your list; if whip_core is already ready (an announcement concerning you has been heard) runs it immediately too (so calling it late from a thread works).
- Runs all functions on every `whip_core:onReady` that concerns you: `reason = 'coreStarted'` always; `reason = 'resourceStarted'` only if your resource is in `resources`; any other/older payload: yes.
- Each function in `pcall`; a throw prints `^1[res] Whip.register failed: <err>` and counts as a start problem. Runs over a snapshot (a function added during a pass isn't run twice).
- Called from inside a registration pass (a helper that registers, used inside your own `Whip.register`): runs once, not remembered (the outer one re-runs it).
- While a pass runs (tracked per coroutine), declaring calls through `Whip.core`/`Whip.call` that return `false, why` print `^1[res] whip_core:<Export> refused: <why>`. Declaring = name starts `Register`, `Ensure`, `Add`, `On<Upper>`, `Watch`, or is `SecureEvent`/`SecureCallback`. Direct `exports.whip_core` calls are not printed.

### Whip.core:Name(...) — BOTH
Proxy table: `Whip.core:AddItem(source, 'cookie', 1)` ≡ `Whip.call('AddItem', source, 'cookie', 1)`. Colon or dot both work. Typed as `WhipCoreServerExports|WhipCoreClientExports`. Returns exactly what the export returns, or `false, why`:
- whip_core not started: `false, 'whip_core is not running'`.
- export threw / no such export: `false, 'whip_core:<Name> failed: <err>'`.
- Exports in the WAITS list (generated from `---@async`, separate lists per side, e.g. server `AddItem`, `ChargePlayer`, `PayPlayer`, `Progress`, `SkillCheck`, `Ensure*`, `Store*`, `CommitWithAction`, `GiveOnLogin`...; client `Callback`, `ClockOn`, `ClockOff`, `Progress`, `Input`, `Confirm`, `Alert`, `SkillCheck`, `LoadModel`, `ResolveVehicle`, `FreeHands`...) run in their own `CreateThreadNow` + promise; if whip_core stops mid-wait every pending promise resolves `false, 'whip_core stopped'` — meaning "no answer", not "didn't happen" (a charge already sent may land; check, don't blindly repeat).
- Non-waiting exports go straight through (cheap).
- Called where nothing can yield (file scope, a sort comparator): a waiting export returns `false, 'whip_core:<Name> waits, so its answer cannot reach you here — it STARTED and will finish; call it from a thread or a handler to get the answer'`.

### Whip.call(name, ...) — BOTH
Same as `Whip.core`, for a name built at runtime. No editor checking (a misspelt name just returns false).

### Whip.ready(timeoutMs?) — BOTH
Polls `Whip.isReady()` every 100 ms in the current thread; `true`, or `false` on timeout (nil = forever). Must be in a thread.

### Whip.isReady() — BOTH
`true` once an onReady concerning you was heard (cached until whip_core's `onResourceStop`); before that asks `exports.whip_core:IsReady()` if started. On the client "ready" means whip_core's client files have loaded, not that the server finished starting (server calls made then can find it booting).

### Whip.command(name, opts, fn) — SERVER
`RegisterCommand` behind SecureEvent-like gates; `fn(source, args, raw)` runs in its own thread (may wait); errors print `^1[res] /name failed`. Refusals are toasts (`NotifyPlayer`, 'error') or console prints.

| opt | Default | Effect / refusal text |
|---|---|---|
| `dev = true` | off | player needs `HasDevTools(source)` (whip.devtools + developer mode on): `'/<name> needs developer mode on (/w)'` |
| `ace = 'my.perm'` | none | `IsPlayerAceAllowed`: `'/<name> is not for you'` |
| `whileDead = true` | refused while down | `'Not while downed'` (checks `IsPlayerDead`) |
| `rateLimit` | token bucket burst 3, refill 1/s | `false` = none; `{ burst, everyMs }` to tune; refusal `'Slow down'` |
| `console = false` | console allowed | console refused: `'/<name> is for players only'` |
Console (source 0) skips dev/ace/dead/rate checks. Registered with `restricted = false` (gates are the helper's). Per-player buckets cleared on `playerDropped`.

### Whip.sayStarted() / Whip.startProblem(fmt, ...) — SERVER
- `sayStarted()` once in a server file: after each onReady pass that concerns you prints `<resource> started successfully!` if `_startProblems == 0`, then resets the counter. On the client it's a no-op.
- Start problems counted since resource start / last report: a `Whip.register` function threw, an error caught by the error tap, any `print` whose first arg starts with `^1`, any `Whip.startProblem`, any refusal printed during a pass.
- `startProblem(fmt, ...)`: `string.format`s (no args → `tostring(fmt)`), prints `^1[res] text^0`, counts.

### Whip.registry(name, opts?) / Whip.caller() — BOTH
- `registry` loads `whip_core/shared/registry.lua` into a private env (no globals/exports added to yours; error if the file is missing) and returns `Registry.new(name, opts)` — WHIP's registration rule in your resource, for things others extend (phone apps, MDT plugins, parts).
- opts: `label` (word used in reasons), `scoped` (keys become `'<owner>:<id>'`), `shared` (several owners may hold the same key with the same value), `sweep` (default true; false keeps a stopped owner's entries, free to take over), `same` (custom equality fn, or `false` = every add replaces), `validate(id, value, owner) → ok, why`, `onAdd(key, value, owner, old)`, `onRemove(key, value, owner, why)` (why `'removed'|'stopped'|'released'`; must not yield), `prefixed` (warn unprefixed keys), also `store`, `reserved`, `releaseOrder`.
- Methods: `:add(owner, id, value, opts?) → true, key | false, why` (refusal also printed once), `:remove(owner, id) → true | false, why`, `:get(key)`, `:ownerOf(key)`, `:keysOf(owner)`, `.entries`. A stopping resource's entries are swept by the copy's own `onResourceStop` handler.
- `Whip.caller()` = `GetInvokingResource() or GetCurrentResourceName()`; read it first in your export, before anything yields.
```lua
local Apps = Whip.registry('app', { label = 'app' })
exports('RegisterApp', function(id, def) return Apps:add(Whip.caller(), id, def) end)
```

### Whip.registerWith(resource, fn) — BOTH
Runs `fn` (each run in its own thread, pcall'd; failure prints) now if `resource` is started, and on every `onResourceStart` of it. For registering into another resource's registry so its restart brings yours back.

### Whip.requires(min) / Whip.has(name) / Whip.versionAtLeast(have, want) — BOTH
- `requires('1.0')`: compares whip_core's fxmanifest `version`; false prints once `^1[res] needs whip_core X or newer; this server has Y. Update whip_core.`
- `has('GetBalance')`: `exports.whip_core:HasExport(name)` on this side; false if whip_core isn't started or older.
- `versionAtLeast`: numeric compare, `'1.0'` = `1.0.0`.

### Whip.onCoreLost(fn) — BOTH
Only for a resource WITHOUT `dependency 'whip_core'` (with it, FiveM stops you first, so it never runs). Runs on whip_core's `onResourceStop` (after pending `Whip.core` waits are resolved `'whip_core stopped'`). Every player has been logged out with no `whip_core:player:logout`; drop per-player state. Registrations need no cleanup; `Whip.register` re-runs when whip_core is back.

### Whip.configPage(def) / Whip.onConfigChanged(path, fn) — BOTH
- `configPage({ label, settings | groups = { { label, settings, id? } }, config? })`: call once at file scope in a shared script after `config.lua` (not in `Whip.register`; it wraps its own registration in one). Each entry's `key` is a dotted path into `config` (default `Config`; numeric segments are list indices unless the table has that string key). Defaults are captured at declaration from config.lua's values (entries carry no `default`). An entry whose value holds a function, or a `records`/`map` row with an undeclared non-scalar field, is left off with a console line. `type = 'record'`: one card whose `fields` each become their own setting `'<key>.<field>'`. Registered via `__RegisterSettings`; refusal printed `[res] settings page refused: why`. Saved values are written into `Config` in place (tables cleared and refilled, so a held reference sees updates) on declare and on every change. Returns false (printed) if `Config`/def missing. Page appears in `/whip` → Settings, permanent admins only; values keyed by resource folder name (renaming the folder resets to defaults). `sides = 'server'` on an entry keeps the value server-only. Entry types include `int`, `number`, `bool`, `string`, `enum`, `vec3` (`here = true` button), `list`, `map`, `records`, `record`.
- `onConfigChanged(path, function(value, old, key) end)`: at file scope; hears its own path, anything under it, and changes to a table it is inside. Must not wait. Use to rebuild what you derived from `Config` at load (blips, price lists).

### Whip.playerSetting(def) — CLIENT
A row on the pause menu's Server Settings page: a per-player choice your resource stores (its own KVP). `def`: `key` (required), `label`, `help`, `group` (`'Controller'`, `'Vehicles'`, `'Map & HUD'`, `'Chat & voice'` or yours; default `'Other'`), `type` (`'toggle'`, `'choice'` with `options = { { value, label } }` ≥2, `'slider'` with `min, max, step, unit`), `default` (what "Reset to the server's defaults" restores), `get()` and `set(value)` (required). File scope; re-declared on every whip_core start; removed when your resource stops. Server call prints and returns false. `GetPlayerSetting(key)` (client export) reads any row.

### Whip.voice(name, ...) / Whip.voiceSystem() — BOTH
`voiceSystem()` → `{ resource, label, features = { lines, speaker, pickup, quality, sounds = 'full'|'basic' } }` or `false` (via `GetVoiceSystem`, and only if that resource is started). `voice('OpenLine', ...)` calls that resource's export: returns its first two values, or `false, 'no voice system is running'` / `false, '<res>: <err>'`. Never name a voice resource directly. Lines are yours and close when your resource stops.

### Whip.padScreen(def?) — CLIENT
Controller support for your own NUI. Returns a screen object `:open() → pad?`, `:close()`, `:typing(on)`, `:pause(on)`, `:isPad()`. Sends your page `{ action = 'pad', cmd, down, rep }` and `{ action = 'padDevice', pad }`. def: `buttons` (default up/down/left/right/a/b/x/y; also lb, rb, menu), `stick` (default true), `releases = { a = true }`, `keepInput = 'always'`, `block` (default groups move/look/combat/radio/weaponWheel + controls 22,23,36,44,45,199,200; `false` none), `onButton(cmd, down, rep)`, `onDevice(pad)`, `onFrame()`. LB is WHIP's combo key; first frame ignores already-held buttons; D-pad repeat 380 ms then 110 ms; device swap settles 150 ms. Leaves the pad to WHIP's `OpenKeyboard` automatically.

### Director / tools helpers
- `Whip.card(type, def)` SERVER: your Director card `'<namespace>.<name>'` (first running resource to use a namespace owns it). Needs `run(card)`, or `event`, or `fail`. Fields: title, desc, help, category, categoryTitle, color, icon, outputs, labels, bad, props, testSays, test = 'run', instant, timeout (30 s), v, permission, renamed, once, onceOut, event `{ name, match, once, filter }`, fail `{ event, match, ends, reason, filter }`, check(props, doc), onEnd(callId, why). The `card` object: callId, runId, cardId, scenario, name, rev, test, tag, player, starter, players, trigger, props, and methods var/setVar/state/setState/place/made/record/objective/clearObjective/clock/give/pay/charge/finish/log (getters return `nil, why` on failure). `Whip.removeCard(t)`.
- `Whip.answerCard(callId, outcome, data?)` SERVER: a thread card's later answer.
- `Whip.scenario(key, doc)` / `Whip.template(name, doc)` SERVER: ship a scenario (pending admin acceptance unless trusted) / a New-list template.
- `Whip.task(type, def)` BOTH: Director NPC/car task; `run(entity, args, info)` on the owning game; `done(entity, args)` for 'until'; timing instant/timed/until/either; ≤8 fields. `Whip.removeTask(t)`.
- `Whip.directorButton(id, def)` CLIENT: button on a placed thing's page/bubble; `press(thing)` with `thing:save(data)` (≤4 KB JSON) and `thing:back(data)`. `Whip.removeDirectorButton(id)`.
- `Whip.skillCheckGame(id, def)` BOTH: own skill-check game; server needs `levels = { name = { minMs, timeoutMs } }` (`minMs` faster fails as 'too fast'), client needs `run(difficulty, token) → passed, why`; optional `canStart(source)`, `cancel(token)`. `Whip.removeSkillCheckGame(id)`.
- `Whip.weapons(list, opts?)` BOTH: add-on weapons `{ name = 'WEAPON_...', label, group, model? }` into WHIP's weapon lists; one bad entry refuses the whole list. `Whip.removeWeapons()`.
- `Whip.objectViewerOption(id, def)` CLIENT: `/w` object viewer option; `select(target)`; anything it does server-side must check permissions itself. `Whip.removeObjectViewerOption(id)`.
- All of these re-send themselves on every whip_core start (they wrap `Whip.register`) and are removed when your resource stops; calling again changes them.

### WhipCost (`@whip_core/lib/cost.lua`)
`WhipCost.start()` → reading or nil; `WhipCost.stop('area: what', t)`; never a `Wait` between them. `WhipCost.on` true while `/whipcost` runs. Without lib/cost.lua the satellite still reports your resource's memory churn and per-loop allocations during `/whipcost` (client).

### What else the helper does (side effects of loading it)
- Error tap (unless `whip_error_tap 'no'` in your fxmanifest): replaces `Citizen.CreateThread`, `CreateThreadNow`, `SetTimeout` (and the `CreateThread`/`SetTimeout` globals), `RegisterCommand`, `AddStateBagChangeHandler`, `RegisterNUICallback`/`RegisterNuiCallback` and `print` in your resource with versions that report failures to whip_core (`whip_core:errorTap:report`; `GetErrorLog`, Monitor, `whiperrors`). Thread errors are caught and printed `^1SCRIPT ERROR`; command/statebag/NUI errors are re-raised. Each event handler costs one extra xpcall (~0.5 µs). Threads keep their original names in profiler/resmon.
- A client resource with a `ui_page` gets `whip_core:probe:ask` handling (only from whip_core) and NUI callbacks `whipProbe` and `whipErrorTap` registered (for `ReadScreen`/`PressScreen` and page error logging when the page loads `https://cfx-nui-whip_core/html/js/page-tools.js`).

## Calling whip_core

| Where | Call | Why |
|---|---|---|
| Inside a handler whip_core runs (SecureEvent, SecureCallback, use handler, right-click action, hook) | `exports.whip_core:Name(...)` | whip_core is up; a payment and what it pays for are written together |
| Your own code: `Whip.register`, threads, commands, timers, NUI callbacks, your own net events, key presses | `Whip.core:Name(...)` | may run before whip_core is ready; returns `false, why` instead of throwing; refusals printed in `Whip.register` |
| Per-frame code | `exports.whip_core:Name(...)` behind `Whip.isReady()`, quick exports only | `Whip.core` checks state and guards every call; waiting exports get a thread — too much at 60 Hz |

A WAITS export may wait on the DB or the player: call from a thread/handler, never at file scope; re-read anything that may have changed after it returns (e.g. `IsSessionCurrent`).

## How whip_core announces readiness and restarts satellites

- Server: after start-up finishes, `CoreReady = true`, item setting pages declared, `CoreStart.run()` (Director, Systems, permission grants each in its own thread), then `TriggerEvent('whip_core:onReady', { reason = 'coreStarted' })` and `TriggerClientEvent('whip_core:client:coreReady', -1)` (`server/player_lifecycle.lua:1516`). Export `IsReady()`.
- Re-announce: any resource starting while ready → after one tick (`Wait(0)`, bursts coalesced) `whip_core:onReady { reason = 'resourceStarted', resources = {...} }`. Same on the client (`client/ready.lua`).
- Client: `client/ready.lua` is the LAST client script; it announces `coreStarted` locally one tick after load (so client "ready" = client files loaded), then sends `whip_core:server:coreUpHere`.
- Stop step 10 sets `CoreReady = false`.
- Satellites back (`server/satellites_back.lua`): resources whose manifest names whip_core in `dependency`/`dependencies` and stopped within 1 s of whip_core are written to a KVP. On the next `coreStarted` (if the list is <300 s old and the server process has been up ≥90 s — a cold start leaves it to server.cfg), whip_core waits until every connected player's game reported whip_core up (≤45 s), then `StartResource`s each one still stopped and prints which. A satellite stopped by hand earlier is not restarted.
- Raw `AddEventHandler('whip_core:onReady', fn)` hears every other resource's start too; `Whip.register` filters it.

## Load order (whip_core fxmanifest) and why it matters

- `fx_version 'cerulean'`, `lua54 'yes'`, `version '1.0.0'` (setup banner, `whip_requires`, update check), `whip_updates 'WHIPFX/whip_core'`, `dependency 'oxmysql'`, `ui_page 'html/index.html'`, `nui_callback_strict_mode 'true'` (NUI callbacks answer only whip_core's own page).
- Shared, in order: `shared/invoker.lua` first (while whip_core loads `GetInvokingResource()` names no caller), `shared/error_tap.lua`, `config.lua`, `shared/config_guard.lua` (names a config.lua mistake by line and stops the start), `shared/config_schema.lua` + `shared/settings.lua` (`/whip` settings over config defaults, before anything reads a setting at load), `inventory_shape`, `statebags` (state bag key names), ..., `shared/registry.lua` (before every server/client file: registries are built on it at file scope), `shared/platform.lua` (before anything platform-specific), assets/events/hands/body_state/skillcheck, shapes before property_math, Director kit before any Director file.
- Server: `@oxmysql/lib/MySQL.lua`, `server/db_guard.lua` right after (no MySQL await waits forever), `server/lifecycle.lua` first of whip's own (later files add `CoreStop` steps at file scope), `db_health`, `migrations`, `testseams`, then the security layer `callback.lua`, `sanitize.lua`, `secure.lua` (creates the `SecureEvent` global; nothing before it can use it at file scope), `sentinel.lua` (before any module writing a player state bag at file scope), then player/character/permissions/settings/.../bank/money, `item_options`+`item_settings`+`retired_items` before `inventory.lua` (config items checked at load), `activity_log` before files whose handlers call Log, stores/ground/containers, `panels.lua` before `server/items/*.lua`, prop catalog seed before catalog, garages, properties (validate before packs), vehicles, `money_holds`, `pending_gives`, vehicle catalog before its list, jobs, shops, zones, time, stats, voice, doors, `helpers.lua`, themes before `player_lifecycle.lua`, `requirements.lua`, runtime points, Director files (core → fields → ... → api → cards_api → satellite_api), Systems Creator, `player_lifecycle.lua` (start-up and the onReady announce), `satellites_back.lua`, event files, `server/items/*.lua` (after RegisterItem/RegisterUseHandler/RegisterPanelItem exist), devtools, `updates.lua` (after devtools_base, before setup_report), `setup_report.lua`, `lib/cost.lua`, `whipcost.lua`. No JavaScript on the server (any JS makes FXServer enter whip_core every server frame).
- Client: `client/profiling.lua` first (wraps handler registration), `lib/cost.lua` early, callback, `dev_commands` early (DevCommand), settings/player_prefs early (rows declared at file scope), leaf modules, ..., `actions.lua` after every engine it mounts into, ..., `client/ready.lua` LAST (onReady must mean every file has run).
- Why it matters to you: (1) your resource starts after whip_core but whip_core may still be building tables — `Ensure*` exports wait up to 60 s (`WaitForCoreReady`) and return `'whip_core has not finished starting (see its console)'` after that; (2) declarations made outside `Whip.register` can hit an empty or not-yet-ready whip_core; (3) only `oxmysql` must precede whip_core in server.cfg.

## whip_core's stop, final save and start steps (`server/lifecycle.lua`)

- One `onResourceStop` handler runs `CoreStop.add(order, name, fn)` steps in number order, each in its own thread (a waiting step only loses its own tail): 5 end Director runs/Systems, record run containers; 10 stop being ready, freeze stats cache, revoke temp dev tools, record satellites stopping; 15 delete held props and NPCs; 20 hand back in-memory things (open panels, shop baskets, money holds); 40 mark moved players/cars; 60 send every owed write; 90 DB-waiting work (world clock).
- txAdmin stop/restart never stops resources: on `txAdmin:events:serverShuttingDown` WHIP runs `FinalSave` (budget = notice delay − 500 ms, min 250 ms): 5 settle money holds, 8 run containers, 10 stores, 11 per-kind counts, 20 characters/positions, 40 vehicle positions, 50 wait for kicked players' saves, 52 stores again, 60 activity log, 70 world clock. Recommends txAdmin → Settings → FXServer → Shutdown Notice Delay ≥ 15 s (default 5 s); warns if lower. Outcome stored in KVP `whip:finalSave` and reported on the next `coreStarted` (`started` = killed mid-save, `cut` = not everything written, or "only just saved"). A scheduled restart's last warning (≤60 s) runs the same save early (30 s budget).
- `CoreStart.add` steps run in their own threads after ready; `Every(name, ms, fn)` is whip_core's crash-proof periodic loop helper (internal).

## Setup report, whip_requires, whip_updates

Printed once per start, 5 s after the last resource start following ready (max 60 s after ready); `whipsetup` reprints (console only; refuses while not ready). Lines `ok`/`FIX`/`note`, then `Nothing to fix` or `N to fix`, then (if 0 fixes) the `Framework loaded successfully!` banner. Checks (`server/setup_report.lua`):
- OneSync on (else FIX). Platform: server version string vs `whip_platform` mismatch → FIX `setr whip_platform <x>`. Legacy: missing `sv_enforceGameBuild` → FIX suggesting 3889; below 3407 → FIX.
- Database version/problem, oxmysql version and whether it has WHIP's patch (4 `whip P-001 patch` marks in `oxmysql/dist/build.js`); unpatched → note (a query can wait forever while the DB is down; WHIP gives up after 65 s).
- Asset packs missing or not started → FIX.
- Satellites (any resource whose manifest depends on whip_core) running with versions; ones present but not started → note; property packs (`whip_property_pack` metadata).
- Update lines from `server/updates.lua`.
- `whip_requires` of every resource vs whip_core `version` → FIX `<res> needs whip_core X or newer`.
- `<name>_enhanced` packs on Legacy / Legacy packs on Enhanced → FIX.
- Second loading screen beside whip_loadingscreen → FIX. Custom inventory renderer not running / no `renderer.js` → FIX.
- Voice: none → note; another voice (`pma-voice`, `saltychat`, `tokovoip_script`, `mumble-voip`, `yaca-voice`) beside the voice system → FIX.
- Clashes → FIX: `chat` beside `whip_chat`, `spawnmanager`, `basic-gamemode`, frameworks `es_extended`, `qb-core`, `qbx_core`, `ox_core`, `vrp`, `ND_Core`, inventories `ox_inventory`, `qb-inventory`, `ps-inventory`, `qs-inventory`, `lj-inventory`, targets `ox_target`, `qb-target`, `qtarget`.
- Test seams on → note. Registry refusals so far (first 8) → FIX.
- Also console commands: `whiperrors [resource]` (server error log grouped by resource), `whipsupport` (report + errors to paste to a seller).

Update checks (`server/updates.lua`): `whip_updates 'owner/repo'` (or a github.com URL) in a fxmanifest makes whip_core compare `api.github.com/repos/<repo>/releases/latest` tag with the resource's `version` (leading `v` ignored). Each repo asked at most every 12 h (cached in KVP across restarts, ETag/304), 1.5 s apart, first round 30 s after ready then hourly; GitHub rate-limit (403/429 with remaining 0) pauses until reset. Newer releases are printed once, shown in the setup report, `whipupdates` (console; `whipupdates check` forces), and told once per session to an admin turning dev mode on. `set whip_update_check false` disables. Exports `GetUpdate(resource?)` → `{ resource, repository, current, latest, url, newer, checkedAt, problem }` or nil (own resource when omitted) and `GetUpdates()`.

## The calls you'll use

| To | Call | Side |
|---|---|---|
| Item + what using it does | `RegisterItem`, `RegisterUseHandler` | S |
| Accept a checked message | `SecureEvent` | S |
| Answer a checked question | `SecureCallback`; ask with `Callback` | S; C |
| Prompt, wheel option, car-part choice | `AddAction` | C |
| Job/stash/shop that always exist | `EnsureJob`, `EnsureContainer`, `EnsureShop` | S |
| Who is this | `GetPlayer` | S |
| Tell them | `NotifyPlayer`; client `Notify` | S; C |
| Remember about a character | `SetPlayerFlag`, `GetPlayerFlag` | S |
| Same character after a wait? | `IsSessionCurrent` | S |
| Charge / refund | `ChargePlayer`, `RefundPlayer` | S |
| Pay | `PayPlayer` | S |
| Give/take items | `AddItem`, `RemoveItem` | S |
| Have it / how many | `HasItem`, `GetItemCount` | S |
| Change one item | `SetItemMetadata` | S |
| Move between any two places | `StoreMove` | S |
| On duty / allowed | `IsPlayerClockedOn`, `HasJobPermission` | S |
| Job/rental car; read a car | `SpawnTempVehicle`, `GetVehicle` | S |
| Blip / waypoint | `ShowBlip` | S |
| Server-timed bar; skill check | `Progress`, `SkillCheck` | either |

How WHIP talks to your resource:
| Want | Use | Note |
|---|---|---|
| Hear something happened | event `AddEventHandler('whip_core:…', fn)` (e.g. `whip_core:player:loaded`) | after the fact, can't be stopped; any server resource can fire one — check `GetInvokingResource() == 'whip_core'` where it matters |
| Hear a value change | listener `OnStatChanged`, `OnVehicleStatChanged`, `WatchVehicleStat` | only WHIP calls it; removed when you stop |
| Act just before WHIP does something client-side | `RegisterClientHook` (`'beforeGiveMode'`, `'beforePlaceMode'`, `'freeHands'`) | WHIP waits ≤1 s; can't refuse |
| Refuse something of yours | `canUse`, `canInteract`, panel `onValidate` | |
| Add to WHIP | `Register…`, `Add…`, `Ensure…` in `Whip.register` | |

## The WHIP way

| Rule | Because |
|---|---|
| Declare in `Whip.register` | whip_core forgets on restart |
| Every game message is a `SecureEvent`/`SecureCallback` naming its values, with `near` where it matters | a modified game can send anything from anywhere |
| Return `false, 'why'`; never throw or bare `nil` | callers tell refusal from bug; players read why |
| Save `charId`, never server id | ids are reused |
| Ask WHIP for shared things: screen `SetScreenOpen`, controls `BlockControls`, hands `FreeHands` | one owner each, released when you stop |
| React to events; no `while true do Wait(0)` polling | per-frame loops cost every player |
| One call per action: `StoreMove` not `RemoveItem`+`AddItem`; own rows via `CommitWithAction` | one action, one transaction |
| Prefix names (`mycafe_coffee`, `mycafe:buy`) | names are server-wide, first come first served |
| Put a check where every path passes (in your export) | the next caller can't forget it |
| Settings on a page (`Whip.configPage`) | owners edit in `/whip`; survives updates |

## What a resource can change

Without touching whip_core: add items, stats, prompts, jobs, shops, stashes, store kinds, item windows (panels), settings pages, Director cards, `/w` pages, skill-check games, a voice system; change ~200 WHIP rules in `/whip` → Settings → Config or `config.lua` (respawn wait, hospitals, hunger, lockpick game...); hold WHIP things (`HoldRespawn`, `HoldVehicleEngine`, `BlockControls`, `BlockHands`, `HoldPlayerPed`); refuse your own things; hear events.

Cannot change: WHIP's own items' uses (lockpick, bandage, food/drink — register your own item, or edit the item in `/whip` → Economy → Items); the status HUD (add gauges with `RegisterStat` `hud`; `Config.HudSkin` picks one of two looks; can't be turned off or redrawn); spawn picker choices (last location, `config.lua` presets, their homes).

Replacing screens: every screen's look = a theme (`theme.css` resource via `Config.Theme` or `SetActiveTheme`); inventory = `Config.InventoryRenderer` (renderer seat, needs `renderer.js`); death screen = `Config.DeathScreen = false` + draw from `whip_core:death:screenChanged`; phone = stop `whip_phone`, use `SetScreenOpen`, `SetScreenArea`, `FreeHands`; chat = any resource handling stock chat events; loading screen = any (whip_core closes it on arrival); status HUD, char select/creator, spawn picker, notifications, progress bar = theme only.

## Testing and measuring

| Test | Use |
|---|---|
| Inventory UI without the game | `node whip_core/dev/inventory-preview/preview.js my_inventory_ui` |
| Director card/scenario | `TestDirectorCard(type, props, { player = source })`, `TestDirectorScenario(doc, opts)` |
| Something done to another player | pass `{ charId = n }` of your second character, then log in as them |
| Two players | two FiveM clients on one PC, same account, different characters; turn off `Config.BlockOwnCharacterTransfers` on a test server to move money between them |
| Dying, healing, broken car | `/w` → Kill Me, Restore Player Cores, Repair Vehicle |
| What your events did | `/whip` → System → Monitor |
| Missed errors | `whiperrors` (server console; F8 in dev mode); `GetErrorLog(opts?)` → `{ entries = { { seq, at, side, resource, kind = 'error'|'warning', text, count } }, last, side }` (last 200, `since`, `max`) |

Measuring: `/whipcost` (client, dev mode) µs/frame per timed section + memory per resource; `WhipCost.start()/stop()` with `client_script '@whip_core/lib/cost.lua'`; `MeasureFrames({ seconds })` (FPS, worst 1%, frames >33/50 ms); server `whipcost [seconds]` with `server_script '@whip_core/lib/cost.lua'` (CPU time); Monitor shows handler time incl. DB waits; `profiler record 500` / `profiler view` (with `setr whip_profiling 1` handlers are named by event; captures inflate ~5×). Usual culprit: a `Wait(0)` loop.

Export cost tiers (cheapest first):
| Cost | Examples | Use |
|---|---|---|
| Memory | `HasItem`, `GetItemCount`, `IsPlayerClockedOn`, `GetPlayerJob`, `GetBalance` after first read | µs; as often as needed |
| A copy (serialised) | `GetPlayer`, `GetVehicle`, `StoreRead` | keep what you need, don't re-read per frame |
| Sends to a game | `NotifyPlayer`, `ShowBlip`, `ShowPlayerText`, `SetPlayerMetadata` | per action, never in a loop over all players |
| Waits on DB (WAITS) | `Ensure*`, bank reads, `ChargePlayer`, `PayPlayer`, `AddItem`, `SetVehicleData` | ms; thread/handler; re-read after |
| Waits on other side/player (WAITS) | server `Progress`, `SkillCheck`; client `Callback`, `ResolveVehicle`, `Input` | round trip or player time |

## Legacy and Enhanced

| What | On Enhanced | Do |
|---|---|---|
| Models/maps/props | Legacy models must be converted | ship `stream/` (Legacy) and `stream_enhanced/` (used instead when present) |
| NPCs made at start | an NPC made before any character loads can lose its network id | make NPCs after `whip_core:player:loaded`, or in `Whip.register` once a player is on |
| Wide DUI | `CreateDui` refuses pages wider than 8192 px | pack atlases into rows |
| Anything else | | `exports.whip_core:GetPlatform()` → `'legacy'|'enhanced'` (both sides) |

Server declares Enhanced with `setr whip_platform enhanced` (`setr` so clients get it; a plain `set` never reached Enhanced clients). Any value other than legacy/enhanced reads as legacy with a console warning; the server also replicates the value itself (enough on Legacy). Client `/whipplatform` (dev mode) prints what the game read (`shared/platform.lua`). Packs with models come as `<name>` and `<name>_enhanced`; the setup report flags the wrong one.

## Selling, licence, escrow

- WHIP is LGPL-3.0 (`COPYING.LESSER` + `COPYING` GPL-3.0; `shared/emote_list.lua` is GPL-3.0). A resource calling exports and loading `@whip_core/lib/satellite.lua` from whip_core's folder is your own work, any licence, open/closed, free/paid (WHIP's reading, not legal advice).
- Never copy WHIP files into your resource (a copied file stays LGPL and buyers must be able to change it — incompatible with encryption). Load the helper via `shared_script`. Examples (`*_example(s)`) are MIT: copy freely.
- Don't name your resource WHIP; "Works with WHIP" is fine. `whip_core/NOTICE.md` lists what the licence doesn't cover (name/logo).
- Escrow: WHIP never reads your Lua (knows you by name; settings in its DB). Keep readable: your `config.lua` (`escrow_ignore`, or use `Whip.configPage`), property packs as `.lua` (`escrow_ignore` or ship `.json`); Director scenario packs are JSON already; `ui_page`, images, sounds untouched. Untested with escrow — send console output if something breaks.
- Buyers can copy HTML/JS/CSS/images/sounds/property packs/Director scenarios (a shipped scenario can be duplicated and exported in their Director).

## Glossary

| Term | Meaning (other frameworks' word) |
|---|---|
| ACE | FiveM permission via `add_ace`; `whip.devtools` gates WHIP's admin tools |
| Action | something a player can do: world prompt, F1 wheel option, car-part choice; `AddAction` (target option) |
| Address | `{ kind, id, sub, slot }` naming a store/slot |
| Audience | who a server-shown thing is for: `'everyone'` or `{ people = { serverId | { charId = n } } }` |
| Card | one step of a Director scenario |
| charId | character id; saved, never changes — save this |
| Consume, live | two ways a client reports a vehicle stat: amount used (fuel) or current value (boost); server caps both |
| Container | a storage box in the world; one kind of store (stash) |
| Developer mode | a `/w` switch; off, an admin is treated as a normal player |
| Director | scenario builder in `/whip` (missions from cards, no code) |
| DUI | web page drawn on something in the world |
| `Ensure…` | first call creates, later calls bring in line with the declaration; safe every start |
| F1 wheel | radial menu (F1 / hold D-pad down); `at = { radial = true }` |
| Ground item | item lying in the world; not a store; own exports (drop) |
| Hook | your function WHIP calls at a set moment and waits for (panel `onValidate`, client hook); can reply |
| Item key | registered item name (`'mycafe_coffee'`) |
| Layer | named stacked change removed to restore (weather layer, handling layer) |
| Lore character | Director story person with name/face/phone/voice |
| Managed door | door owned by a resource (`EnsureDoors`) or a home; admins can rename, not change who opens |
| Monitor | `/whip` → System → Monitor: every secure call + Sentinel detections |
| `near` | SecureEvent rule: refuse unless within range of a spot or the named car |
| Owned / session vehicle | owned: saved car; session: other cars WHIP knows (street cars, `SpawnTempVehicle`), memory only |
| Panel | inventory-like window beside the inventory, `OpenPanel` (secondary inventory) |
| Panel item | item that holds items (wallet), `RegisterPanelItem` |
| Permission | WHIP staff role on an account (between player and full admin); not an ACE |
| Person | server id (online) or `{ charId = n }` |
| Player sheet | plain table `GetPlayer` returns, no methods (PlayerData/xPlayer) |
| Pockets | main inventory `sub = 'player'` + accessory strip `'accessory'` |
| Point | interaction point added by server code (`AddPoint`) |
| Presence | `persist = 'presence'` vehicle stat: DB remembers the car has it at its fitted value |
| Receipt | `ChargePlayer` result; pass to `RefundPlayer` |
| Registry, registration rule | whip_core's memory of declarations; same again = nothing, others' names refused |
| Run tag | label like `'run:42'`; `ReleaseTag` removes everything under it |
| Satellite | any resource built on whip_core loading the helper |
| SecureEvent, SecureCallback | `RegisterNetEvent` / server callback with built-in checks |
| Sentinel | guard against games changing the state bags WHIP writes |
| Session | number on the sheet, new each character load; `IsSessionCurrent` (not a session vehicle) |
| Setup report | start-up console report with fix lines |
| Server id, source | FiveM's number for a connected player; never save |
| Snapshot | the car copy `GetVehicle` returns; can be passed back as a reference |
| Stat, effect | server-side character numbers (health, hunger, yours) and timed changes |
| Store | anywhere items sit (inventory); not a shop |
| Store kind | `'player'`, `'container'`, `'vehicle'`, or your own |
| Use handler | what using an item does: function, or table for a timed use (usable item) |
| userId | an account, ≤ `Config.MaxCharacters` characters |
| Vehicle data | non-gauge data on a car, `SetVehicleData` |
| Vehicle reference | `{ id }`, `{ entity }`, `{ plate }`, `{ netId }`; bare number = vehicleId |
| Vehicle stat | gauge WHIP keeps/syncs/saves (fuel, nitrous, boost), `RegisterVehicleStat` |
| vehicleId | WHIP's car id: DB id when owned, ≥1,000,000,000 otherwise; not entity/netId |
| Watcher | `WatchVehicleStat`/`WatchVehicleData`: your code runs while a nearby car has it |
| `Whip.register` | where declarations go so they re-run after restarts |

## Example: whip_cafe_example (`whip_core/docs/examples/whip_cafe_example`, MIT)

The tutorial (Your First Resource steps 1-7 + Your First Job steps 1-4), line for line, plus `html/img/items/mycafe_coffee.webp`. Lives inside whip_core's folder so it never starts by itself; copy to resources and `ensure whip_cafe_example`. Uses the tutorial's names (`mycafe_coffee`, job `mycafe`): run either it or your own `mycafe`, not both (the second is refused).

- `fxmanifest.lua`: cerulean, lua54, `dependency 'whip_core'`, `whip_requires '1.0'`, shared `@whip_core/lib/satellite.lua` + `shared.lua`, `files { 'html/img/items/*.webp' }` (inventory loads pictures from `html/img/items/<key>` of the registering resource).
- `shared.lua`: `Config = { Counter = vector3(-361.0, 49.0, 54.4), Price = 15, BrewPay = 5 }` — shared so the client places the prompt and the server refuses anyone elsewhere.
- `server.lua` (one `Whip.register`):
  - `RegisterItem('mycafe_coffee', { name, desc, weight = 0.3, type = 'consumable', stack = true, maxStack = 10, usable = true })`.
  - `RegisterUseHandler` with a TABLE (timed use): `label`, `duration = 4000`, `anim = { dict, clip }`, `prop = { model = 'p_amb_coffeecup_01', bone = 28422 }`, `disable = { move = false }`, `onComplete = function(source) return exports.whip_core:AddStat(source, 'thirst', 20, 'item:mycafe_coffee') end` — returning AddStat's `false, why` gives the coffee back. Server times the bar; item taken before onComplete.
  - `SecureEvent('mycafe:buy', { rateLimit = 1000, near = { at = Config.Counter, range = 3.0, message = 'Walk up to the counter' } }, fn(source))`: client sends nothing; `ChargePlayer(source, Config.Price, { reason = 'Coffee' })` (cash, else bank) → on fail `return false, err`; `AddItem` → on fail `RefundPlayer(receipt)` and `return false, why`; `NotifyPlayer(..., 'success')`.
  - `EnsureJob('mycafe', { name = 'Bean Machine', roles = { { name = 'Owner', level = 100 }, { name = 'Barista', level = 1 } } })`.
  - `SecureEvent('mycafe:brew', { rateLimit = 2000, near = ... }, fn(source, player))`: server duty check `IsPlayerClockedOn(source, 'mycafe')` → `'Clock on first'`; server `Progress(source, { label, duration = 6000, near = { coords = Config.Counter, range = 3.0 } })` (near re-checked at the end; event `near` is only on arrival); after the wait `IsSessionCurrent(source, player.session)` else return silently; `AddItem(source, 'mycafe_coffee', 1, nil, 'brewed')`; `PayPlayer(source, Config.BrewPay, { reason = 'Brewed a coffee' })` (cash; overflow lands at their feet).
- `client.lua`: one `AddAction({ id = 'counter', at = { coords = Config.Counter }, options = {...} })` with options: `buy` (icon `cash`, `TriggerServerEvent('mycafe:buy')`); `clockon` (`require = { job = 'mycafe' }`, `canInteract` = `LocalPlayer.state.whipJob ~= 'mycafe'`, calls client `exports.whip_core:ClockOn('mycafe')` and `ctx.refuse(why)` on failure); `brew` (`require = { job = 'mycafe', onDuty = true }`); `clockoff` (same require, `ClockOff('mycafe')`).
- Patterns shown: declarations in `Whip.register`; client sends no values; `near` + `rateLimit`; charge → give → refund on failure; timed use with stat reward; options with `require` as UI hints while the server re-checks; server-timed Progress with `near`; session check after waits; `whipJob` state bag (job key or `false` off duty).
- To try: hire yourself in `/whip` → Economy → Jobs → Bean Machine → Change; buy; clock on; brew; walk away during brewing → "too far", nothing given; Monitor shows each call.

## Example: whip_delivery_example (`whip_core/docs/examples/whip_delivery_example`, MIT)

A qb-style delivery job rewritten the WHIP way (doc "A qb delivery job, call by call"). Copy, `ensure whip_delivery_example`; desk at "Post Op depot" beside the Public Garage.

- `fxmanifest.lua`: `dependency 'whip_core'`, helper + `shared.lua`, `files { 'html/img/items/*.webp' }` (package picture). No `whip_requires`.
- `shared.lua`: `Config.Depot` (desk vector3), `VanSpawn` (vector4 bay), `VanModel = 'speedo'`, `VanBack = 40.0` (m from desk to count as returned), `Deposit = 500` (bank), `Pay = 120` per package, `Packages = 3`, `Drops` = 5 `{ label, coords }` doors.
- `server.lua`:
  - State: `runs[source] = { vanId, receipt, stops, done }`; `blipId(source) = 'mydelivery_' .. source`; `currentStop(run)` = `Config.Drops[run.stops[run.done + 1]]`; `showNext` = `ShowBlip({ people = { source } }, blipId, { coords, label, route = true })` to the next door, or a green (`color = 2`) route back to the depot + notify when empty; `takeBackPackages` = `GetItemCount` then `RemoveItem(..., { reason = 'delivery run ended' })`; `pickStops(n)` = shuffled distinct drops.
  - `Whip.register`: resets `runs = {}` (whip_core restarted: vans and blips went with it); `RegisterItem('mydelivery_package', { weight = 2.0, stack, maxStack = 5 })` (not usable); `EnsureJob('mydelivery', { name = 'Post Op', roles = Manager 100 / Driver 1 })` with result printed on failure; depot blip `ShowBlip('everyone', 'mydelivery_depot', { coords, label, sprite = 67, color = 5, shortRange = true })`; shared `atDepot = { at = Config.Depot, range = 3.0, message = 'Go to the depot desk' }`.
  - `mydelivery:signon` (rate 3000, near depot): refuses if `GetPlayerRole(source, 'mydelivery')` already; `HirePlayer(source, 'mydelivery', 'Driver')` (no `by`: code decides).
  - `mydelivery:start`: on duty (`IsPlayerClockedOn`) else `'Clock on first'`; one run per player — `runs[source] = run` is set BEFORE any wait so a double press is refused; `undo(reason, receipt, vanId)` clears the run, despawns, refunds. Steps: `ChargePlayer(source, Config.Deposit, { method = 'bank', reason = 'Van deposit' })`; `SpawnTempVehicle(Config.VanModel, Config.VanSpawn, { forSource = source, despawnAfter = 1500 })` (driver gets key; 25 min so the deposit is still refundable within the receipt's 30 min); `StoreGive({ kind = 'vehicle', id = vanId, sub = 'trunk' }, PACKAGE, Config.Packages, nil, 'delivery run')` (packages in the boot; player drags them to pockets); then after the waits: `runs[source] ~= run or not IsSessionCurrent(...)` → undo silently.
  - `mydelivery:drop` with a dynamic `near.at = function(source) return currentStop(runs[source]).coords end` (nil → refused as too far, `message = 'Not this door: follow the route on your map'`): requires `HasItem(source, PACKAGE)`; server `Progress(source, { duration = 4000, near = { coords = stop.coords, range = 3.0 } })`; re-checks run identity + session; `RemoveItem(..., { reason = 'delivered' })`; `run.done += 1`; `PayPlayer(source, Config.Pay, { reason = 'Delivery: ' .. label })`; next blip. This `near` closes the classic "fire the pay event from anywhere" exploit.
  - `mydelivery:finish`: needs a van out; `GetVehicle(run.vanId).coords` within `VanBack` of the depot else `'Park the van at the depot first'`; clears run, `HideBlip`, `DespawnVehicle`, `RefundPlayer(run.receipt)`, takes back leftover packages, notifies.
  - Logout edge case: `AddEventHandler('whip_core:player:logout', function(e) ... end)` — guarded by `GetInvokingResource() ~= 'whip_core'` and `type(e) == 'table'`; ends the run, hides blip, despawns van, takes back packages; the deposit is NOT refunded (kept by the depot).
  - Van taken back edge case: `whip_core:vehicle:released` (same guard; ignores `e.reason == 'despawned'`, i.e. your own DespawnVehicle): when the van's time ran out or it sat alone 10 minutes, finds the run by `e.vehicleId`, clears it, hides blip, takes packages, notifies `'The depot took the van back. Your deposit is kept'`.
- `client.lua` (`Whip.register`): depot `AddAction` with options `signon` (icon `id`, `canInteract = offDuty`), `clockon` (`require = { job = 'mydelivery' }`, offDuty, client `ClockOn` + `ctx.refuse`), `start` (icon `car`, on duty), `finish` (icon `garage`, on duty), `clockoff`; plus one `AddAction` per drop (`id = 'drop_' .. i`, icon `give`, `require = { job = 'mydelivery', onDuty = true, item = 'mydelivery_package' }`) — every door shows a prompt only while carrying a package; the server decides which door is right.
- Patterns shown: refundable deposit via receipt; temp vehicle with key and auto-despawn; items into a vehicle store; route blips per player; dynamic per-player `near`; latch-before-wait to prevent double starts; identity re-check after waits; reacting to logout and vehicle release events with invoker checks.

## Gotchas

1. Declarations outside `Whip.register` vanish on a whip_core restart (and may hit whip_core before it is ready).
2. Direct `exports.whip_core` calls inside `Whip.register` do not print refusals; use `Whip.core` there or check returns.
3. `'whip_core stopped'` from `Whip.core` means "no answer", not "nothing happened".
4. A waiting export called through `Whip.core` at file scope only STARTS; you get a `false` explaining that.
5. Exports return `false, why` (never nil+why); compare only `Progress`/`SkillCheck` codes, never sentences.
6. A bare number is a server id, not a charId; save charIds.
7. Function args through exports are not `type 'function'`; nil returns vanish in nested calls.
8. Item names stay registered after your resource stops (not yours anymore; another may take them).
9. A refusal from a registration is printed only once per owner+reason.
10. `RegisterUseHandler` table form: a bare `false` from `onComplete` gives the item back (unlike the function form, where `false` keeps it); set `consume = false` to keep a tool.
11. An action's `require` is client UI only; re-check on the server (duty, items, distance).
12. Server `Progress` belongs in a SecureEvent, not a SecureCallback (client gives up callbacks after 10 s); its `near` is checked at start and finish, the event's `near` only on arrival.
13. After any wait, check `IsSessionCurrent(source, player.session)` before giving/taking.
14. `RefundPlayer` only by the charging resource, within 30 minutes; later use `PayPlayer`.
15. `EnsureTable`: put every schema change in BOTH the CREATE and a migration; the call that creates the table records all migrations as done without running them.
16. `Whip.configPage` must be at file scope after config.lua (not in `Whip.register`); renaming the resource folder resets saved values.
17. `Whip.onCoreLost` never fires for resources with `dependency 'whip_core'`.
18. Local server events (`whip_core:player:logout`, `vehicle:released`...) can be fired by any server resource: check `GetInvokingResource() == 'whip_core'` before acting on money/items.
19. Error tap wraps `print`: any print starting `^1` counts as a start problem and suppresses `started successfully!`.
20. Enhanced needs `setr whip_platform enhanced` (not `set`).
21. txAdmin restarts kill the process without stopping resources; set Shutdown Notice Delay ≥15 s so WHIP's final save completes.

## Docs vs code

1. `Whip.command` has an undocumented `console = false` option and `rateLimit` may be a table `{ burst, everyMs }` (`lib/satellite.lua:586-606`, `types/satellite.lua:75`); docs only mention `rateLimit = false`.
2. SecureEvent schema keys `permission` (string or list, any-of; `server/secure.lua:1249`) and param type `'amount'` (`server/secure.lua:124`, used in the docs' Secure Events guide) are missing from the `WhipSecureSchema` stub (`types/classes.lua:543-587`).
3. `GiveOnLogin` also accepts `opts` as a plain reason string, truncated to 120 chars (`server/pending_gives.lua:51-52`); docs say `opts.reason`.
4. `EnsureTable` limits not in docs: table name `[%w_]` ≤64, `'<resource>:<id>'` ≤64, statement must contain `CREATE TABLE IF NOT EXISTS`, 60 s ready wait (`server/migrations.lua:966-983`).
5. `types/server.lua:653` says `set whip_platform enhanced`; docs and `shared/platform.lua:11-17` require `setr`.
6. `types/satellite.lua:125` places `configPage` under "/whip → Config"; docs say `/whip` → Settings (own page beside Config).
7. Setup report accepts Legacy builds ≥3407 as ok (`server/setup_report.lua:16`); docs present 3889 as "the game build WHIP is made for (or newer)" — 3889 is only the suggested value.
8. Docs list the error tap's wraps without `CreateThreadNow` and without the client `RegisterNuiCallback` alias, both wrapped (`lib/satellite.lua:118-148`).
9. `whip_delivery_example/fxmanifest.lua` omits `whip_requires`, which the tutorial recommends for every resource.
