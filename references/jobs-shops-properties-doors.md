# Jobs, Shops, Properties & Doors

Jobs (roles, duty, business account), shops (npc / infinite / stocked), properties (templates, units, keys, furniture, stashes, themes, packs) and doors (declared, managed, held). Built from doc anchors `guide-jobs`, `server-jobs`, `client-jobs`, `guide-shops`, `shops`, `client-shops`, `shop-talk`, `guide-properties`, `housing`, `guide-doors`, `server-doors`, `client-doors`, `doors-managed`, and source `whip_core/server/{jobs,shops,shop_counters,shop_talk,prices,properties,property_*,doors,prop_catalog,events_misc,helpers}.lua`, `whip_core/client/{jobs,shops,doors,properties,property_objects,property_furnish}.lua`, `whip_core/shared/property_math.lua`, `whip_core/docs/properties.md`, `whip_core/types/*.lua`, `whip_homes_mirrorpark/`.

## Contents
- Conventions shared by all four systems
- Jobs: model and rules
- Jobs: config, storage, state bag
- Jobs: server exports
- Jobs: client exports
- Jobs: events
- Shops: model
- Shops: config and the shop record
- Shops: server exports
- Shops: client exports
- Shops: the shopping flow (server internals)
- Shops: stock management and shelf layout
- Shops: events and shop talk
- Prices and SetVehiclePrices
- Properties: model
- Properties: config
- Properties: buying, keys, doors, garage
- Properties: server exports
- Properties: furniture and the prop catalogue
- Properties: stashes
- Properties: interior themes (provider contract)
- Properties: property packs (format)
- Properties: client exports and events
- Doors: model
- Doors: requirements
- Doors: server exports
- Doors: managed sets and held doors
- Doors: client exports and behaviour
- Doors: events, rate limits, internals
- Gotchas
- Docs vs code

---

## Conventions shared by all four systems

- **Person** (`who`): a bare number is a SERVER ID (online player); `{ charId = n }` is any character, online or offline. Resolved by `WhoIs` (`server/helpers.lua:96`), which answers `charId, source` (source nil while offline) or `nil, 'No player with that server id is online (for a character, pass { charId = n })'` / `nil, 'A character is { charId = n }'`. Exception: exports whose name says Character/CharId (`GetCharacterProperties(charId)`) take the charId directly.
- **Job**: `jobId` (number) or `key` (string). **Role**: `roleId` (number) or name (case-insensitive).
- **Answer shape**: a value / `true`, or `false, why` where `why` is a sentence a player may read. Database failures answer `DB_ERROR` = `'Could not save that (database error)'`. Exports return `false` (never `nil`) before a reason, because an export's return list is cut at the first nil.
- **Ensure\* exports** (`EnsureJob`, `EnsureShop`, `EnsureDoors`, `EnsureDoor`, also `CreateDoor`, `HoldDoor`, `RegisterProps`) call `WaitForCoreReady()`: wait at most 60 s for whip_core to finish starting, else `false, NOT_READY` = `'whip_core has not finished starting (see its console)'` (`helpers.lua:77-85`). Declare inside `Whip.register(function() ... end)` (satellite lib) with `Whip.core:EnsureX(...)` or `exports.whip_core:EnsureX(...)`.
- **One owner per key**: a job/shop/door set declared by a running resource is refused to other running resources (`Registry.alive`). A thing made in `/whip`, or whose declaring resource is stopped, is open to any resource. Refusals are also printed to the declaring resource's console (`Registry.sayRefused`).

---

## Jobs: model and rules

A job is a business: `key`, name, icon, roles (with levels 1-100 and permissions), employees, optional owner, and a business bank account that exists only while it has an owner.

**Roles and levels**
- Levels 1-100 (whole numbers). Level >= 100 holds every permission (built-in or the job's own) and `'manager'` business-account access.
- **Built-in permissions** (`Jobs.BUILTIN_PERMISSIONS`, `jobs.lua:57`): `canHire`, `canFire`, `canPromote`, `canDemote`, `canManage` ("roles, shop stock and prices").
- **Job's own permissions**: declared with `EnsureJob`'s `permissions = { cuff = 'Cuff suspects' }` (or a list `{ 'cuff' }`, label = name). Name: `^[%a_][%w_]*$`, at most 40 chars; label truncated to 60; may not be a built-in or `bankAccess`. They appear as toggles on each role in the Job Manager and answer `HasJobPermission` like built-ins. A permission the job stops declaring counts for nothing even if still stored on a role (`knownPermission`, `jobs.lua:1734`).
- **`bankAccess`** (role permission, not a yes/no): `'none' | 'view' | 'deposit' | 'withdraw' | 'manager'`. Stored only when not `'none'`. A role's account access = `'manager'` if level >= 100, else its `bankAccess`, else `'none'` (`roleBankAccess`, `jobs.lua:1044`). Hire, promote, demote, fire, role edits and owner changes keep every holder's account access in step (lowering happens before the role write, raising after).
- **Owner**: `ownerCharId`. The owner holds the job's TOP role (highest level) whether hired or not (`Jobs.getPlayerRole`, `jobs.lua:1713`), may clock on, appears in `GetPlayerJobs`, counts in `GetClockedOnEmployees`, but is listed in `GetJobEmployees` only if also hired. Owning ends the moment ownership moves.
- **Business account**: created (label `'<job name> Account'`, type `'business'`) when a job is made with an owner, or when `UpdateJob` gives it an owner and none exists. It follows a new owner (`Bank.SetAccountOwner`); the old owner then keeps only what their role gives (nothing if not employed). An owner cannot be cleared while the job has an account. `exports.whip_core:GetJobBankAccounts(job)` returns its accounts, or `{}, 'No such job'`; with no owner it returns `{}`.

**Rank rule (`opts.by`)**: when `opts.by` names the acting player, WHIP checks (`actorMayAct`, `actorHas`, `actorCovers`, `jobs.lua:1186-1235`):
1. the actor has a role at the job (`'You do not work there'`);
2. below level 100, the target level (person's current role and/or the role given) is strictly below the actor's level (`'They (or that role) outrank you'`); level 100 may act on anything including other level-100 roles;
3. the actor holds the act's permission (`'Your role is not allowed to do that'`);
4. below level 100, the actor gives no permission they lack and no more account access than both the target's previous access and their own (`'That rank can do more than yours: you cannot give more than you have'`).
Leaving `by` out = trusted caller (your code, an admin tool): nothing is checked. `by` that resolves to nobody answers `'opts.by names nobody (a source, or { charId = n })'`.

**One character per account** (`Config.JobOneCharacterPerAccount`, default `true`): hiring is refused when another character of the same account already works there or owns it (`'That is another character of someone who already works there, so they cannot be hired (one character per player at a job)'`), and an owner is refused when another character of theirs works there (`'Another character of that player works there, so they cannot own it (one character per player at a job)'`). Applies to trusted calls too; `false` turns it off.

**Duty**
- Runtime only, never saved: logout, disconnect or restart ends it (`player_lifecycle.lua:1151` calls `Jobs.clockOffAll`).
- A player may be on duty at several jobs; the "current" job is the most recent clock-on (a global sequence number). Clocking on again where already on duty makes that job current again but fires no event.
- `Config.JobDutyOneAtATime = true`: clocking on clocks off every other job first (each with its own clockedOff event).
- `selfClockOn = false` (EnsureJob): the client's ClockOn and `ClockOn(..., { by = })` are refused with `'This job puts people on duty itself'`; your server code calls `ClockOn(who, job)` without `by`. Going off duty is always allowed.
- "Works here" without duty: `GetPlayerRole(source, 'police') ~= nil`.

**Character deleted**: fired from every job (no actor, account access revoked); a job they owned loses its owner and keeps running (staff, shop, account stay) until an admin names a new owner (`jobs.lua:1534-1559`).

## Jobs: config, storage, state bag

| Config | Default | Meaning |
|---|---|---|
| `Config.JobDefaultRoles` | Owner 100 (all five + `bankAccess='manager'`), Manager 50 (hire/fire/promote/demote, `canManage=false`, `'withdraw'`), Employee 1 (`'view'`) | Roles of a new job when `EnsureJob` gives no `roles`. Schema: 1-20 records, unique names. |
| `Config.JobDutyOneAtATime` | `false` | `true`: one job on duty at a time. |
| `Config.JobOneCharacterPerAccount` | `true` | See above. |

Tables (`jobs.lua:271-317`): `jobs` (`jobId`, `key` VARCHAR(50) UNIQUE, `name` VARCHAR(100), `icon` VARCHAR(100), `ownerCharId`, `settings` JSON, `createdAt`, `createdBy`), `job_roles` (`roleId`, `jobId`, `name` VARCHAR(60), `level` SMALLINT, `permissions` JSON; unique (jobId,name)), `job_employees` (PK jobId+charId, `roleId`, `hiredAt`, `hiredBy`; FK to characters ON DELETE CASCADE).

Job `settings` keys WHIP itself writes: `declaredBy` (resource), `permissions` (declared own permissions), `selfClockOn` (stored only as `false`).

Limits: key `^[%a_][%w_]*$`, at most 50 (`'A job key is letters, digits and _ (starting with a letter or _), up to 50'`); role name 1-60 chars, no control chars, unique per job ignoring case.

**State bag**: `Player(src).state.whipJob` / client `LocalPlayer.state.whipJob` (constant `PLAYER_JOB_KEY = 'whipJob'`, `shared/statebags.lua:96`): the KEY of the current (most recent) on-duty job, or `false` off duty. Set `false` at character load, updated on every clock on/off that has a source. Server logic should read the server's own answer (`GetPlayerJob`), not the client-writable bag.

## Jobs: server exports

All in `whip_core/server/jobs.lua:1909-2366`.

### GetJob(job) — SERVER
Returns the cached job `{ jobId, key, name, icon, ownerCharId, settings, createdAt, createdBy }` (createdAt epoch seconds), or `nil`.

### GetJobs() — SERVER
Every job, sorted by jobId.

### GetJobRoles(job) — SERVER
Roles highest level first, copies: `{ roleId, name, level, permissions }[]`, or `false, 'No such job'`.

### EnsureJob(key, data) — SERVER, WAITS
Find-or-create by key; call from `Whip.register`.
- `data.name` string (default: the key), `data.icon` string?, `data.roles` `{ { name, level, permissions? } }` (default `Config.JobDefaultRoles`), `data.permissions` (job's own, `{ name = 'label' }` or list), `data.owner` person (create only: holds top role + business account), `data.selfClockOn` boolean, `data.settings` table (create only, copied into job settings).
- First call: creates job, roles, and (with owner) the business account; fires `whip_core:job:created`.
- Later calls: updates `name` (if given and different), `icon` (if not nil), `permissions` (only when given; omitted leaves the stored ones), `selfClockOn` (only when given: `false` stores false, `true` clears it), and adds listed roles the job lacks (by name). Never changes an existing role, the owner (use `UpdateJob`), or other settings.
- Role definitions are checked before anything is written: list non-empty, name 1-60, level whole 1-100, permissions a table, no duplicate names (`'roles[2] (Cadet): level must be a whole number from 1 to 100'`, `'roles[%d]: "%s" is listed twice'`). Role permission keys are passed through `cleanPermissions`: unknown keys are silently dropped, invalid `bankAccess` dropped.
- Returns the job, or `false, why`: bad key, `'permissions must be a table: ...'`, `'permission name "x": letters, digits and _ only'`, `'permission "canHire" is built in'`, `'settings must be a table'`, `'job "x" is declared by <resource>'`, `WHY.player` for a bad `owner`, `'No such character'`, `'Another job already uses that key'`, `DB_ERROR`, `NOT_READY`. A new owned job whose account could not be opened is still returned (console note).

```lua
Whip.register(function()
  Whip.core:EnsureJob('police', {
    name = 'Police Department', icon = 'shield', selfClockOn = false,
    roles = {
      { name = 'Chief', level = 100 },
      { name = 'Sergeant', level = 50, permissions = { canHire = true, canFire = true, cuff = true } },
      { name = 'Officer', level = 20, permissions = { cuff = true, bankAccess = 'view' } },
      { name = 'Cadet', level = 1 },
    },
    permissions = { cuff = 'Cuff suspects' },
  })
end)
```

### UpdateJob(job, patch) — SERVER
`patch = { name?, icon?, owner? }`; `owner = person` sets, `owner = false` removes (refused while the job has a business account: `'This job has a business account, which needs an owner — set a new owner instead of clearing it'`). Only `name`, `icon`, `owner` are read. Account follows a new owner; old owner unemployed there loses account access and is clocked off if on duty only by owning. Returns `true` (even if the account could not follow; console says so) or `false, why`: `'No such job'`, `'nothing to change'` (patch not a table), `'job "x" is declared by <res>: only it can change or delete it'`, `WHY.player`, `'No such character'`, same-account-owner refusal, `DB_ERROR`. Fires `whip_core:job:updated`.

### DeleteJob(job) — SERVER
Refused while any business account holds money (`"Empty the job's business account first"`) or if declared by another running resource. Closes accounts, clocks everyone off, revokes access, deletes roles/staff/job in one transaction. Fires `whip_core:job:deleted { jobId, key }`.

### GetPlayerJob(who) — SERVER
Current on-duty job (most recent clock-on): `{ jobId, key, name, icon, roleId, roleName, roleLevel }`, or `nil` off duty or for nobody.

### GetPlayerJobs(who) — SERVER
Every job they have a role at (employed or owner), on duty or not, keyed by jobId: `{ jobId, key, name, icon, roleId, roleName, roleLevel, clockedOn, dutyOrder, permissions }` (`permissions` = `{ [name] = true }` they effectively hold; `dutyOrder` higher = more recent, nil off duty). `{}, why` for nobody.

### IsPlayerClockedOn(who, job?) — SERVER
`job` nil: on duty anywhere. Returns boolean; `false, WHY.player` / `false, 'No such job'` when the question names nobody (so "off duty" and "nobody" differ).

### GetPlayerRole(who, job) — SERVER
Their role (owner gets top role): `{ roleId, jobId, name, level, permissions }` or `nil` (also nil for bad who/job).

### HasJobPermission(who, job, permission, opts?) — SERVER
`opts.onDuty = true` also requires duty there. Holds on duty or off otherwise. Returns `true` or `false, why`: `'Not on duty at <job name>'`, `'Not allowed at <job name>'`, `WHY.player`, `'No such job'`.
```lua
if not exports.whip_core:HasJobPermission(source, 'police', 'cuff', { onDuty = true }) then
  return false, 'Only an officer on duty can do that'
end
```

### GetJobEmployees(job) — SERVER
By charId: `{ charId, roleId, roleName, roleLevel, hiredAt (epoch s), hiredBy, onDuty, source (online only) }`. Owner only if hired. `false, 'No such job'`.

### GetClockedOnEmployees(job) — SERVER
`{ { charId, source } }` everyone on duty, owner included. `false, 'No such job'` (use `or {}`).

### HirePlayer(who, job, role?, opts?) — SERVER
`role` default: lowest-level role. Offline characters can be hired (`{ charId }`). `opts.by` = recorded `hiredBy` and checked (outranks the role, holds `canHire`, covers the role's permissions/access). Returns `true` or `false, why`: `'They already work there'`, `'No such role at that job'`, `'No such character'`, `'Your role is not allowed to do that'`, `'They (or that role) outrank you'`, `'You do not work there'`, power/one-character refusals, `DB_ERROR`. Fires `whip_core:job:hired`; the target's client list resyncs.

### CanHirePlayer(who, job, role?, opts?) — SERVER
Every `HirePlayer` rule, nothing written (for a job offer that waits on acceptance; `HirePlayer` checks again).

### FirePlayer(who, job, opts?) — SERVER
`opts.by`: outranks the person, holds `canFire`. Clocks them off, revokes account access, deletes the row. `'They do not work there'`. Concurrent change to the same person: `'Another change to that person is still being saved'`. Fires `whip_core:job:fired`. Cannot fire the owner (owner holds the role by ownership, not employment).

### SetPlayerRole(who, job, role, opts?) — SERVER
`opts.by`: outranks old AND new role, holds `canPromote` (new level higher) or `canDemote` (lower or same), covers what the new role adds. Nobody promotes themselves (rank rule). Fires `whip_core:job:roleChanged { ..., roleId, role, oldRoleId }`.

### CreateJobRole(job, data, opts?) — SERVER
`data = { name, level, permissions? }`; permissions = built-ins, job's own, `bankAccess`. Unknown permission key REFUSED (`'"x" is not a permission at this job'`), non-boolean (`'Permission "x" is true or false'`), bad bankAccess (`'bankAccess is none, view, deposit, withdraw or manager'`), `'A role name is 1 to 60 characters'`, `'There is already a role called X'`, `"A role's level is a whole number from 1 to 100"`. `opts.by`: `canManage`, level strictly below theirs (below 100), gives nothing they lack. Returns `{ roleId, name, level, permissions }`.

### UpdateJobRole(job, role, patch, opts?) — SERVER
`patch = { name?, level?, permissions? }`; unnamed permissions keep their value, `false` removes one. Holders' account access follows. With `by`: `canManage`, role's current and new level below theirs, gains nothing they lack, and cannot leave the job without a level-100 role (`'The job needs a level 100 role: its owner holds it'`). (Without `by` the level-100 rule is not checked.)

### DeleteJobRole(job, role, opts?) — SERVER
Refused while anyone holds it: `'Move the people in that role to another role first'`. `by` checked as UpdateJobRole (including the level-100 rule).

### ClockOn(who, job, opts?) — SERVER
`who` must be online (`'They are not online'`). Must be employed or owner (`'They do not work there'`). `opts.by`: must be themselves (`'A player clocks only themselves on'`) and the job must allow self clock-on (`WHY.selfClock`). Without `by` it ignores `selfClockOn`. Sends client `whip_core:client:jobClockState`, sets `whipJob` bag, fires `whip_core:job:clockedOn` (only on a real change).

### ClockOff(who, job?) — SERVER
With job: `'They are not on duty'` when not. Without job: off duty everywhere, always `true`.

## Jobs: client exports

`whip_core/client/jobs.lua`. Cached job list (sent by `whip_core:client:jobsSync` at load and after any change); no round trip except ClockOn/ClockOff.

- **GetPlayerJobs() — CLIENT**: `{ [jobId] = { jobId, key, name, icon, roleId, roleName, roleLevel, clockedOn, dutyOrder, permissions } }`.
- **IsPlayerClockedOn(job?) — CLIENT**: jobId or key; nil = any. Boolean.
- **HasJobPermission(job, permission) — CLIENT**: from the cached `permissions` map; a hint for what to offer (server re-checks). No `onDuty` option.
- **GetPlayerJob() — CLIENT**: entry of the most recent clock-on, or `nil`.
- **ClockOn(job) — CLIENT, WAITS**: `Callback('whip_core:jobs:clockOn')`, rate limit 1 per 1000 ms, refused while dead. Call from a thread. Returns `true` or `false, why` (`'They do not work there'`, `'No such job'`, `'This job puts people on duty itself'`, `'Rate limited'`, `'Player is dead'`).
- **ClockOff(job?) — CLIENT, WAITS**: allowed while dead; nil = every job.

Client job lookups by key only work for jobs in the player's own list. Related: `AddAction`'s `require = { job = ..., jobPermission = ..., onDuty = true }` reads this same cache.

## Jobs: events

Server (one payload table; person events carry `charId` and `source`, source only while online):

| Event | Fields |
|---|---|
| `whip_core:job:created` | `jobId, key, name` |
| `whip_core:job:updated` | `jobId, key, name, icon, ownerCharId, oldOwnerCharId` (also fired when a deleted owner is released) |
| `whip_core:job:deleted` | `jobId, key` |
| `whip_core:job:hired` | `jobId, key, charId, source, roleId, role, by` (`by` = hiredBy charId) |
| `whip_core:job:fired` | `jobId, key, charId, source` |
| `whip_core:job:roleChanged` | `jobId, key, charId, source, roleId, role, oldRoleId` |
| `whip_core:job:clockedOn` / `clockedOff` | `jobId, key, charId, source` |

Client (local player, `WhipEmit`): `whip_core:job:clockedOn` / `clockedOff` `{ jobId, key }`; `whip_core:job:listChanged { jobs }` (same map as `GetPlayerJobs`). Internal net events: `whip_core:client:jobsSync`, `whip_core:client:jobClockState(jobId, state)`.

---

## Shops: model

A shop sells items through a prompt on a shopkeeper NPC or a prop. Three modes (`shops.mode` ENUM):

| Mode | Stock | Price | Revenue |
|---|---|---|---|
| `npc` | unlimited | the shop's `catalog` | none: a money sink |
| `infinite` | unlimited | the shop's `catalog` | job business account (needs `jobId`) |
| `stocked` | a real container (`containerId`) staff fill by hand | one price per item (`shop_item_prices`), set by staff, plus a for-sale flag | job business account; a shop priced in an item puts the paid items into its stock container |

- **Catalog**: `{ [itemKey] = price }`, whole dollars (fractional floored, `{ price = n }` accepted and normalised, negative/NaN/inf refused). Item keys are NOT checked against the registry at create (satellite items may register later); unknown items are simply not shown.
- **Currency**: `settings.currency` = an item key the shop is priced in (default `'cash'` banknotes). Non-cash: bank payment refused (`'This shop takes <item>, not bank payments'`), and no money reaches the business.
- **Keeper / prop / counter** (`server/shop_counters.lua`): `npcModel` spawns a server NPC (invincible, frozen, scenario `WORLD_HUMAN_STAND_IMPATIENT`) with the prompt on it; `prop` (and no `npcModel`) is spawned per client within `Config.ShopStreamRange`, prompt 1.0 m above the spot; neither = no prompt (open only via other paths). Prompt reach `Config.ShopInteractRange` (2.5). Options: `browse` (label = shop name, everyone) and, for a stocked shop with a job, `Manage Stock` (`require = { job = <key>, jobPermission = 'canManage' }`, re-checked on the server).
- **Blip**: only if `blipSprite` set and non-zero; colour `blipColor` (default 2); hidden while the resource that made the shop (EnsureShop/CreateShop) is not running.
- A job can own several shops.

## Shops: config and the shop record

| Config | Default | Meaning |
|---|---|---|
| `Config.Shops` | `{}` | `[key] = { name, mode, npcModel \| prop, pos = vector4, blipSprite, blipColor, catalog, jobId?, containerId?, settings? }`. Created at start when no shop has that key; managed in `/whip` afterwards; deleted there, recreated next start while listed. `pos` (vector4) is required here (EnsureShop uses x/y/z instead). |
| `Config.ShopBasketSlots` | `10` | Basket lines, clamped 1-50. |
| `Config.ShopInteractRange` | `2.5` | Prompt reach. |
| `Config.ShopStreamRange` | `100.0` | Prop shop stream distance. |
| `Config.ShopTalk` | see Shop talk | Lines and timings. |

Shop record (`GetShop`): `{ shopId, key, name, mode, jobId, containerId, npcModel, prop, x, y, z, heading, blipSprite, blipColor, catalog, settings, createdAt, createdBy }`.

`settings` keys: `categories` (tab names, in order), `layout` (`{ [itemKey] = { category, order } }`), `currency` (item key), plus WHIP's own `layoutRev`, `ensured = { by, decl }` (EnsureShop), `owner` (CreateShop's caller). Table `shops` (key VARCHAR(60) UNIQUE, name VARCHAR(100), npcModel/prop VARCHAR(60), blipColor default 2); `shop_item_prices` (PK containerId+item, price INT UNSIGNED, forSale TINYINT; cascades with the container).

## Shops: server exports

`whip_core/server/shops.lua:2518-2652`.

### GetShop(ref) — SERVER
`ref`: shop id, `{ id = }`, `{ key = }`, or `{ containerId = }` (the shop whose stock that is). Returns the record or `nil`.

### GetShops(filter?) — SERVER
All, sorted by shopId; `{ job = jobId|key }` filters. `{}, 'No such job'` for an unknown job.

### GetShopViewers(shopId) — SERVER
Sources with that shop open (compares the id as given: pass a number).

### EnsureShop(key, data) — SERVER, WAITS
`data = { name, mode, npcModel?, prop?, x, y, z, heading, catalog?, jobId?, containerId?, blipSprite?, blipColor?, settings? }`.
- Validation (`declaration`, `shops.lua:1661`): x, y, z numbers required (`'a shop needs x, y and z'`), rounded to mm; `name` non-empty string; `mode` `'npc'|'infinite'|'stocked'`; `jobId` jobId or key that exists (`'No such job'`); `containerId` must exist (`'No such container'`); `npcModel`/`prop` non-empty strings; `blipSprite`/`blipColor` whole numbers; catalog valid; settings a table. Defaults on create: name `'Shop'`, mode `'npc'`, heading 0, blipColor 2.
- New key: created, declaration stored in `settings.ensured`. Same declaration as last time (deep equal): nothing changes (admin edits stand). Changed declaration: every named field applied; a field the last declaration named and this one drops (`jobId`, `containerId`, `npcModel`, `prop`, `blipSprite`) is cleared; settings merged (declared keys replace, keys the last declaration set but this one drops are removed, others such as Edit Shelf layout kept).
- Returns the record, or `false, reason` (validation, `'shop "x" is declared by <res>'`, `'EnsureShop needs a string key'`, DB error, NOT_READY).

```lua
Whip.register(function()
  Whip.core:EnsureShop('my_gunshop', {
    name = 'Ammu-Nation', mode = 'npc', npcModel = 's_m_m_ammucountry',
    x = -330.2, y = 6084.3, z = 31.5, heading = 228.0, blipSprite = 110,
    catalog = { gunny_pistol = 2500, gunny_mag_pistol = 150 },
  })
end)
```

### CreateShop(data) — SERVER
Creates every call, no key check (a pop-up stall). Same fields as EnsureShop but only x/y/z and catalog are validated (see Docs vs code: `jobId` must be a numeric jobId here). Stamps `settings.owner = <caller>` (copy) for a non-core caller. Fires `whip_core:shop:created { shopId, shop }`. Returns record or `false, reason` (`'a shop needs x, y and z'`, catalog error, `'Could not save the shop (database error)'`).

### UpdateShop(shopId, data) — SERVER
Changes included fields; `false` clears `jobId`, `containerId`, `npcModel`, `prop`, `blipSprite`, `key`. `catalog` replaces the whole catalog. A new `mode` or `containerId` closes every open basket (stock returned) and is refused while someone is paying (`'a customer is paying there right now, try again in a moment'`). One update per shop at a time (waits up to 5 s: `'that shop is being changed — try again in a moment'`). Refused for another running resource's shop (`'shop "x" belongs to <res>: only it can change or delete it'`). Returns `true` or `false, 'Shop not found' | why`. Fires `whip_core:shop:updated`.

### DeleteShop(shopId) — SERVER
Closes it for viewers (baskets back to shelf), despawns keeper/prompt. Same ownership rule. Fires `whip_core:shop:deleted { shopId }`.

### SetShopLayout(shopId, { categories, layout }) — SERVER
`categories`: tab names in order, 1-24 chars each (trimmed, case-insensitive dedupe), at most 12; omitted = kept. `layout`: `{ [itemKey] = { category, order } }` each REPLACES that item's place; an entry with neither removes it; items not mentioned keep theirs; at most 500 entries; item must be registered (`'No such item: x'`); category must be one of the tabs; `order` clamped 1-100000. A tab removed is stripped from every item. Lower `order` first, unplaced goods after, A to Z. Errors include `'Shop not found'`, `'SetShopLayout needs { categories, layout }'`, `'a shop has at most 12 tabs'`, `'%s is in a tab the shop does not have: %s'`.

### GetShopCatalog(shopId) — SERVER
`{ [itemKey] = price }` for infinite/npc, `nil` for no shop (a stocked shop usually answers nil).

### AddCatalogItem(shopId, itemKey, price) — SERVER
Infinite/npc only (`'Shop is not infinite/npc mode'`); item must be registered (`'Unknown item: x'`); `price` must be a Lua number >= 0 (`'Invalid price'`), floored. Saves.

### RemoveCatalogItem(shopId, itemKey) — SERVER
`'Item not in catalog'` if absent.

### GetShopStock(shopId) — SERVER
Stocked only. `{ [slot] = { item, amount, metadata, price, forSale } }` (price 0 / forSale false when unpriced), or `false, 'Shop not found' | 'Shop is not stocked mode' | 'Shop has no container'`.

### GetShopPrices(shopId) — SERVER
`{ [itemKey] = { price, forSale } }` (copy), same failures.

### SetShopItemPrice(target, itemKey, price, forSale) — SERVER
`target` = stock containerId or `{ shopId = n }`. One price per item for every slot holding it. Price: number (negative becomes 0, floored); `forSale = false` keeps the price but hides the item. Returns `true` or `false`: `'Unknown container'`, `'Unknown item'`, `'Invalid price'`, `'Shop not found'`, `'That shop has no stock container (not stocked mode)'`, `DB_ERROR`, another resource's shop. Fires `whip_core:shop:priceChanged { containerId, item, slot, price, forSale }`; every customer redraws.
```lua
exports.whip_core:SetShopItemPrice({ shopId = shopId }, 'drink', 5, true)
```

## Shops: client exports

- **IsShopOpen() — CLIENT**: shop screen open.
- **GetActiveShopId() — CLIENT**: shopId being browsed or `nil` (global `ActiveShopId`).

There is no client event or export to open a shop: it opens only through the counter prompt (server `Shops.openFor`), a Systems card, or whip_test's seam.

## Shops: the shopping flow (server internals)

- **Open** (`events_misc.lua:977`): one shop at a time (`'You already have a shop open'`); creates a session and a basket (server-side store). Fires `whip_core:shop:opened { shopId, source, charId }`.
- **Basket**: the screen asks by ITEM and basket LINE, never shelf slot or price. Stocked: goods physically move from the stock container into the basket as picked (others see stock drop), and back on removal or close. Infinite/npc: lines conjured, simply dropped on removal. Events: `whip_core:server:basketAdd` (item key <= 50 chars, amount <= 999, default 100 ms rate, burst 10), callback `whip_core:basketSetItem` (total per item, 0-999, rate 30 ms burst 20), `whip_core:server:basketSetQuantity` (line 1-50, qty 0-999). Partial: `'Only 3 left'`, `'Your basket is full'`, `'Sold out'`, `'That is all there is'`, `'That is not for sale'`, `'The shelf has no room to take that back'`. While paying: `'Paying — wait a moment'`.
- **Range**: actions require being within 20 m of the shop (`SHOP_KEEP_RANGE`); every 10 s a session farther than that (and not paying) is closed and its basket returned (no closed event).
- **Purchase** (`whip_core:server:shopPurchase`, rate 1000 ms, params `paymentMethod` `'cash'|'bank'`, `accountId`, `expectedTotal` -1..2e9): prices every line from the server's own records now; refuses if any line is no longer for sale (`'<Item> is no longer for sale'`); refuses if the total differs from what the screen showed (`'The prices changed. Check your basket and buy again.'`); checks carrying (room per line in main pockets, free slots, weight) BEFORE payment (`'No room in your pockets for X x3'`, `'Not enough free pocket slots for everything in your basket'`, `'That is more than you can carry'`); for business shops refuses a frozen first business account (`'This business cannot take payments right now'`) and paying from the business's own account (`'You cannot pay a business from its own account'`); bank needs an account (`'No bank account selected'`). Payment via `Money.charge(..., 'held')` and written with the goods in one transaction. Lines that fail delivery are refunded in the currency paid. Bank dropdown lists only accounts the buyer has withdraw access to (cash-currency shops only).
- **Revenue**: infinite/stocked with `jobId`, total > 0, paid in money: `Bank.SystemDeposit(jobAccounts[1].accountId, total, 'Sale: <name>', buyerCharId)`. No business account: the customer still pays and the revenue goes nowhere (console WARNING). Paid in an item at a shop with a container: the items go into the container.
- Infinite/npc goods with a `forBuyer` metadata generator are regenerated for the buyer; stocked goods keep exact item, metadata and serial. Item log: `'bought'` (catalog) or `'received'` (stocked).
- Closing (`whip_core:server:closeShop`, allowed while dead) returns the basket and fires `whip_core:shop:closed { shopId, source, charId }`. On whip_core stop every basket is returned.

## Shops: stock management and shelf layout

- **Manage Stock** (stocked shop with a job, `canManage` holder): opens the stock container through the container UI, anchored to the shop (works within 20 m). Unrelated players never see the option.
- **Set Price / Mark For Sale** on a stock slot (`whip_core:server:shopSetPrice`, rate 200 ms, must be within 15 m, slot 1-1000, price 0-999999999): requires `canManage` at the shop's job (a job-less shop has no employee management). Mark For Sale on a never-priced item: `'Set a price first'`; slot changed meanwhile: `'That shelf slot changed — try again'`.
- **Edit Shelf** (`whip_core:server:shopSetLayout`, rate 1000 ms burst 3): `canManage` at the shop's job or a `/whip` admin; saves against `settings.layoutRev` (stale draft refused: `'Someone else changed the shelf while you were editing: open Edit Shelf again'`).
- Shelf shown per item (stock = units across slots); an item priced for sale with none left shows SOLD OUT; items not for sale are not shown; items unknown to `Config.Items` are not shown.

## Shops: events and shop talk

Server events (`WhipEmit`): `whip_core:shop:created` / `updated` `{ shopId, shop }`, `deleted` `{ shopId }`, `opened` / `closed` `{ shopId, source, charId }`, `purchased` `{ shopId, charId, source, items = { { itemKey, amount, price } }, total, paymentMethod, mode }` (items = delivered lines only; total after refunds), `priceChanged` `{ containerId, item, slot, price, forSale }`.

**Shop talk** (`server/shop_talk.lua`, `Config.ShopTalk`): the shopper's `/me` bubble and the keeper's answer (also in the shop header). Keys: `enabled` (true), `batchSeconds` (1: basket changes are said once left alone that long), `keeperDelay` (1.2 s), shopper lists `open`, `add`, `change`, `remove`, `paid`, `broke`, `leave`; keeper lists `keeperOpen`, `keeperAdd`, `keeperChange`, `keeperRemove`, `keeperPaid`, `keeperBroke`, `keeperLeave`. Placeholders `{n}`, `{item}`, `{total}` and `{items}` (the last two in `paid`/`keeperPaid` only; `{items}` = first two items, then "and N more"). Silent when the shopper is down or in the creator, when the shop is shut by death/logout/walk-away, on reopening the same shop within 15 s; `broke` at most once per 8 s; keeper answers only within 10 m (prop shops have no keeper).

## Prices and SetVehiclePrices

`server/prices.lua` (used to value inventories, cars and homes in `/whip`): an item's price = average over every cash-currency shop selling it (catalog, or stocked for-sale price; free not counted). A property's = its effective price (>0).

### SetVehiclePrices(prices) — SERVER
`{ [model] = price }` whole dollars (> 0); replaces the caller's list; removed when the caller stops. `false, 'invalid price for <model>'` / `'prices must map a vehicle model to its price, e.g. { adder = 1000000 }'`.

---

## Properties: model

| Piece | What |
|---|---|
| **Template** | one per interior (MLO archetype, or `archetype = 0` for no interior: units in world space around the placement). Has `rooms`, `settings`, `fingerprint`. |
| **Unit** | one home inside the template, all parts in the interior's own space: `space`, `doors`, `sign`, `manager`, `visit`, `garage`. |
| **Property** | one unit at one placement `{ hash, x, y, z, yaw }` of the interior. What players own. |

- Every copy of an interior shares its units (one Mega floor's four flats, then each other floor is a button).
- **Layers**, per part, highest wins: `property.overrides` (this property) > `unit.overlay` (admin change for every property on the unit) > `unit.base` (pack or creator). `false` at any layer = none.
- **Space shapes**: `{ type = 'interior' }`, `{ type = 'rooms', rooms = { names } }` (both need the template's rooms, given or found by Verify), `{ type = 'box', center, size, heading }`, `{ type = 'poly', points = { {x,y},... }, minZ, maxZ }`. Everything within 250 m of the interior origin.
- **Signs**: `sign` (outside, shown while for sale: name, price, bays, rooms; can stand on a sign post from `Config.PropertySignPosts`) and `manager` (inside, shown to owner, keyholders and admins: Keys, Furnish, Theme). Until a manager sign is placed, Keys stand at the outside sign and Furnish is not offered (owner can type `/furnish` in the home).
- **Status**: `'ok'` (checked by Verify, unchanged since), `'unverified'` (never checked or changed since), `'attention'` with `statusReason` (prefix `'verify: '` or `'reconcile: '`).
- **Pack properties** have `source = 'pack:<packId>'`, `propertyKey = '<packId>:<key>'`, `active = false` while the pack's resource is stopped (closed: no sale, no furnishing), `packIssue` `'orphaned: ...'` / `'conflict: ...'` / `'its pack is not installed'`. Admin properties: `source = 'admin'`.
- Admin setup in game: `/whip` → World → Properties → New property (Interior, Space, Doors, Signs, Garage, Name & settings, Review; nothing saved until Save); Register here / Stamp mode (pattern `{b}` building, `{u}`/`{k}` unit label/key, `{f}` floor, `{n}`/`{nn}` counter; `B{f}{nn}` floor 8 from 5 = B805..B808; Stamp: E register, PgUp/PgDn floor, Tab/Q number block, Esc done); Verify / Quick check; Templates & packs → Export.

Tables: `property_templates`, `property_template_units` (base/overlay JSON), `properties` (`theme` TINYINT, `status`, `deletedAt` tombstone, FK owner ON DELETE SET NULL), `property_keys` (PK propertyId+charId, `grantedBy`), `property_objects`, `property_packs`.

## Properties: config

| Config | Default | Meaning |
|---|---|---|
| `PropertyMaxObjects` | `150` | Furniture limit unless the property's settings say otherwise (settings 0-1000). |
| `PropertyKeyGrantRange` | `5.0` | Distance for face-to-face key giving. |
| `PropertyStreamRange` | `60.0` | Sign stream distance (from anchor, plus anchor radius). |
| `PropertyFurnitureDistance` | `20.0` | Furniture appears within this of the walls (goes 2 m further out); `0` = only inside. |
| `PropertyFurnitureRooms` | `4` | Properties furnished at once: yours, then the nearest. |
| `PropertySignPlaceRange` | `12.0` | Admin aiming distance for signs. |
| `PropertySignPosts` | 2 posts (`whip_forsale_timber`, `whip_forsale_hanging`) | `{ model, label, panel = { x, y, z, w, h }, ink, accent, back? }`. |
| `PropertyStashProps` | 4 models | `['model'] = { label, slots, weight }`. |
| `PropertyStashLimit` | `6` | Most stashes per property. |
| `FurnishPlaceRange` | `8.0` | Furnisher placement ray. |
| `FurnishMoveSteps` / `FurnishTurnSteps` | `{0.05,0.25,1.0}` / `{15,45,1}` | Snap steps (Shift drag, G cycles). |
| `PropCategories`, `PropClusters`, `PropSeeds` | | Furnisher catalogue categories and extra props. |

Property `settings` (resolved: defaults, then template's, then property's): `price` (0 = not for sale; 0-1e9), `maxObjects`, `autolock` (bool, applied to entrance/garage doors), `autolockDelay` (packs/admin 1-300 s; default 10).

## Properties: buying, keys, doors, garage

- **Buying** at the outside sign (within 6 m of it): callback `whip_core:property:payOptions` then `whip_core:property:purchase` (rate 2000 ms; method `'cash'` or `'bank'` + account with withdraw access, not frozen). Requires: unowned (`'This property has been sold'`), active (`'This property is closed right now'`), price > 0 (`'This property is not for sale'`), at sign (`'Stand at the sign to buy it'`), one buyer at a time (`'Someone is buying this property right now'`). The held payment rides the owner-change transaction; a failed hand-over refunds. Log `property_bought`.
- **Owner change** (sale, admin, `SetPropertyOwner`): deletes every key, relocks open doors, rewrites door access, moves former keyholders'/old owner's cars out of the private garage, fires `whip_core:property:ownerChanged`. Theme, furniture and stashes (with contents) stay with the property.
- **Keys**: given by the OWNER only, face to face at the sign, to a player within `Config.PropertyKeyGrantRange` in the same routing bucket (`whip_core:server:propertyKeyGrant`, rate 1000 ms; `'They are too far away'`, `'They are not here'`). Revoked by charId (`whip_core:server:propertyKeyRevoke`), which also relocks. A key = owner-level access to doors, private garage and stashes; keyholders cannot give keys, sell, furnish or change the theme. No admin bypass on the player events (admins use the panel). Exports skip the distance rule.
- **Doors**: units' doors with role `'entrance'` or `'garage'` (or `'interior'` + `lock = true`) become MANAGED doors (manager system `'property'`, id = propertyId, folder `'Properties/<building or Other>'`, label `'<name> — Entrance|Garage|Door'`) with `requirements = { charIds = { owner, keyholders... } }`; unowned = `{ charIds = {} }` = nobody. A door already on the spot is adopted (restored when released). `pair` links two leaves. Autolock from the property's settings. `rec.doorIds` = `{ [doorKey] = doorId }`.
- **Private garage**: a unit with `garage.bays` (1-8) gives each property a garage keyed `'property:<id>'`, no blip, usable only by owner and keyholders; `GetNearestGarage` never returns it. Losing access (key revoked, sale) moves that player's cars in it to the nearest public garage. Removed bays/garage evict cars first.
- **Character deleted**: their keys and owned homes released (owned homes lose all keys).
- **Delete**: admin property deleted outright; pack property tombstoned (`deletedAt`), never recreated by its pack. Keys and furniture go; stashes deleted with contents logged as lost; doors released; garage evicted and removed.

## Properties: server exports

`whip_core/server/properties.lua:2126-2159`, `property_stashes.lua:344`, `property_themes.lua:358-367`, `property_packs.lua:691-702`, `prop_catalog.lua:619-698`.

### GetProperty(propertyId) — SERVER
Full view or `nil`: wire fields `{ id, name, label, building, ownerCharId, active, place = { hash, x, y, z, yaw }, anchor = { x, y, z, r }, sign, manager, visit, shapes, maxObjects, price, bays (count), rooms (count or nil), garageKey, themes (bool or nil) }` plus `templateId, unitKey, source, propertyKey, packIssue, status, statusReason, settings` (effective `{ price, maxObjects, autolock, autolockDelay }`), `keys` (charIds), `doorIds` (`{ [doorKey] = doorId }`). The id field is `id`, not `propertyId`.

### GetProperties() — SERVER
Every property as clients see them (wire only: no keys, doors, settings, status), sorted by id.

### GetPropertyAt(x, y, z) / GetPropertyAt(vector3) — SERVER
The property whose space contains the point (full view as GetProperty), or `nil`.

### GetCharacterProperties(charId) — SERVER
`{ owned = { ids }, keys = { ids } }` sorted (a property owned is not also listed under keys).

### HasPropertyAccess(propertyId, who) — SERVER
Owner or keyholder: `true`, or `false, 'No key to that property' | 'No such property' | <WhoIs why>`.

### SetPropertyOwner(propertyId, who) — SERVER, WAITS
`who` person, or `nil`/`false` = unowned. A new owner takes back every key and locks the doors. Setting the current owner again is a no-op `true` (keys kept). Runs in the property's turn (waits up to 5 s). Returns `true` or `false`: `'Unknown property'`, `'There is no character #n'`, `'The property changed hands while this was waiting. Try again.'`, `'That property is being changed — try again in a moment'`, `DB_ERROR`, WhoIs why. Not a sale: no price check, no payment.
```lua
local receipt, err = exports.whip_core:ChargePlayer(buyerSource, price, { method = 'bank', reason = 'House' })
if not receipt then return false, err end
local ok, why = exports.whip_core:SetPropertyOwner(propertyId, buyerSource)
if not ok then exports.whip_core:RefundPlayer(receipt) return false, why end
```

### GivePropertyKey(propertyId, who) — SERVER, WAITS
No distance rule. `false`: `'Unknown property'`, `'Unknown character'`, `'They already own this property'`, `'They already have a key'`, `'There is no character #n'`, `'The property changed hands — nothing was given'`, `'The property is gone — nothing was given'`, `DB_ERROR`. A door that failed to update marks the property `attention` but the answer is still `true`. Fires `whip_core:property:keyGranted`. An unowned property can still be given keys.

### RemovePropertyKey(propertyId, who) — SERVER, WAITS
`'They do not have a key'`, `'The property changed hands — nothing was taken back'`. Relocks doors, evicts their cars. Fires `whip_core:property:keyRevoked`.

### GetPropertyStashes(propertyId) — SERVER
`{ { containerId, name, slots, maxWeight, x, y, z } }` sorted by containerId; `{}` for none. Use `containerId` with the container exports.

### GetPropertyThemes(propertyId) — SERVER
`{ label, current, themes = { { id, name, walls, trim, floor } } }` or `nil` (no theme resource matches). `label` = theme resource's description up to the first colon (else its name). `current` = stored theme, or the first theme id if unset/invalid.

### SetPropertyTheme(propertyId, themeId) — SERVER, WAITS
No check on who asks. Saved, then the theme resource's `SetHomeTheme` is called. `false`: `'Unknown property'`, `'This property has no themes'`, `'That is not one of its themes'`, `'Its themes are not running right now'`, `'Saved, but the home did not change: <why>'`, DB error.

### RegisterPropertyPack(pack) — SERVER
Registers an MLO's homes from a script (same table a pack file returns; owned by the caller). Data only (functions refused with path). Returns `true, 'applied' | 'unchanged' | 'queued'` (queued: WHIP still starting; a later refusal goes to the console and `GetPropertyPacks().problems`) or `false, 'path: why'`. Re-applying is free.

### GetPropertyPacks() — SERVER
`{ packs = { { id, resource, version, label, running } }, problems = { { file, error } } }`.

### RegisterProps(list) — SERVER, WAITS
`list = { { model, name?, category, image? } }`: the caller's whole add-on prop list for the furnisher while it runs (omitted ones removed; all go when it stops). `category` must be a `Config.PropCategories` key; `image` a file in your resource (listed in `files {}`) or `'@other/img/x.webp'`; model <= 80 chars, name <= 64. A model WHIP already lists keeps its row (and admin choices) and takes your picture. `false`: `'prop N needs a model'`, `'prop "x": category is one of the furnisher's (Config.PropCategories)'`, picture errors, `'add-on prop "x" belongs to <res>'`, NOT_READY.
```lua
exports.whip_core:RegisterProps({
  { model = 'mypack_armchair', name = 'Velvet armchair', category = 'seating', image = 'img/armchair.webp' },
})
```

### IsPlaceableProp(model) — SERVER
`true` if the catalogue lists the model (any case) and it is not `unavailable`. Check before placing a model a client named.

Internal/test exports (do not use): `__GetPropertyObjectCount`, `__GetPropertyObjectVersion`, `__Test*` (inert unless `Config.EnableTestSeams`).

## Properties: furniture and the prop catalogue

- Rows stored in the interior's own space (`property_objects`: model, lx/ly/lz, rx/ry/rz, containerId), spawned per client, non-networked; fetched when the property streams in (`whip_core:property:objects`, only within stream range + anchor radius + 40 m).
- **Who furnishes**: the OWNER (at the property) or a `/whip` admin (anywhere). One furnisher per property (lock; `'<name> is furnishing this property right now — try again when they are done'`); lost when the holder leaves the property, logs out, or the property closes/goes. `/furnish` command (client), `whip_furnish_exit`.
- **Save rules** (`PropertyObjects.replace`): property active; based on the current version (`'This room changed since you opened the furnisher (someone else saved it) — close it and open it again'`); space set up; count <= maxObjects (`'That is %d objects — the limit here is %d'`); every new model placeable (an existing unavailable model may stay but not be added); every position inside the space with 0.3 m slack (`'"model" is outside the property'`). Save rate 1 per 4000 ms.
- Lamps (catalogue lighting category) are filed in the interior's limbo room.
- Admin `/prop add <category>` / `/prop remove` edit the catalogue in game; `/propprobe <archetype>` writes an interior report to `whip_core/dev/probe/`.

## Properties: stashes

- Furniture whose model is in `Config.PropertyStashProps` becomes a container when placed: `type = 'stash'`, `slots` (capped 500), `maxWeight` = `weight`, label <= 40 chars, `prop = false`, `propertyId`, `requirements = { property = id }` (owner and keyholders open it; admins from `/whip` → Economy → Containers).
- It moves with its furniture (contents and all) and passes to a new owner full.
- A furniture save or admin Clear that would remove a stash holding anything is refused (`'Empty the <name> first — it still holds N things'`).
- Limit `Config.PropertyStashLimit` applies to ADDING; lowering it removes none (`'That is N stashes — one property may have M'`).
- Deleting the property deletes its stashes, contents logged as lost. At start-up, a stash no furniture claims is deleted if empty, kept and logged if not.

## Properties: interior themes (provider contract)

An interior resource offers looks (one entity set each) by adding `whip_interior_themes 'v1'` to its `fxmanifest.lua` and four SERVER exports (read when either resource starts):

| Export | Contract |
|---|---|
| `GetThemes()` | `{ { id, name, walls = '#rrggbb', trim = '#rrggbb', floor = '#rrggbb' }, ... }`; id integer 0-255, `0` the default; at most 64 themes; name <= 40 chars; colours are the swatch. |
| `GetHomes()` | `{ { key, archetype, designArchetype?, position = vector3 }, ... }`: archetype name and the MLO instance origin; at most 4000; key `^[%w_%-%.:]+$` <= 64. `designArchetype` = interior a replaced home used to place. |
| `SetAllThemes(map)` | `{ [homeKey] = themeId }`, every home (one left out = 0); sent whenever either resource starts. Return `false, why` to report failure. |
| `SetHomeTheme(key, themeId)` | One home changed. Return `true`, or `false, why`. |

Matching: a property whose placement hash equals the home's archetype (or designArchetype) and whose origin is within 2 m gets a Theme option on its sign (owner at the property, or admin; `whip_core:server:propertySetTheme` rate 1500 ms). The lowest property id wins a home two share.

Your client draws the look; on a ready interior refresh it and tell WHIP to remake furniture:
```lua
ActivateInteriorEntitySet(interiorId, 'wh_theme_2')
RefreshInterior(interiorId)
TriggerEvent('whip_core:interiorRefreshed', interiorId)
```
`whip_homes_mirrorpark` is the reference implementation: 71 homes (16 designs) + 25 garages, eight looks (`wh_theme_0..7`: Original, Charcoal, Navy, Forest, Oxblood, Slate, Espresso, Midnight), server exports `GetThemes`, `GetHomes`, `SetAllThemes`, `SetHomeTheme` (+ its own `GetHomeTheme`). It does NOT ship a property pack: an admin makes each house a property (New property standing inside it). Its client covers windows until `GetInteriorFurnishState` answers `done`/`none` and listens to `whip_core:property:furnishStateChanged`. Enhanced servers need `setr whip_platform enhanced`.

## Properties: property packs (format)

Ship homes with an MLO: `whip_property_pack 'whip_properties.lua'` (or `.json`) in its fxmanifest; read when the resource starts; on a server without WHIP the line does nothing. Several lines allowed.

- `.lua` packs are PARSED, never run: `return { ... }` of tables, strings (quoted or `[[ ]]`), numbers, `true/false/nil`, `vec3(x,y,z)`/`vector3(...)`, comments. Any code (variables, loops, calls) is refused. Max 512 KB; compiled Lua and escrow-encrypted files refused (`list it in escrow_ignore ... or ship the pack as .json`). JSON positions: `{ "x":..,"y":..,"z":.. }`. Build code-generated packs in a server script and pass them to `RegisterPropertyPack`.
- Validated whole; the first mistake refuses it with a path, e.g. `templates[1].units[2].doors[1].model: a door needs a model (a name or a hash)` (console `[whip_core:packs] REFUSED <res>/<file> — ...`).

```lua
return {
  format = 1, id = 'yourname.mlo', version = '1.0.0', label = 'Your MLO',
  templates = { {
    key = 'house', label = 'Two-bedroom house', archetype = 'your_mlo_name',
    rooms = { { name = 'living', min = vec3(-8.7, -2.1, 0.4), max = vec3(-0.6, 4.6, 3.1) } },
    settings = { price = 0, maxObjects = 150, autolock = false, autolockDelay = 10 },
    units = { {
      key = 'flat_1', label = 'Flat 1', space = { { type = 'interior' } },
      doors = { { key = 'front', role = 'entrance', model = 'your_door', pos = vec3(1, 2, 0), heading = 90 } },
      sign = { pos = vec3(3, -4, 1), heading = 0 }, manager = { pos = vec3(0, 0, 1), heading = 180 },
      visit = vec3(0, 0, 1), garage = { bays = { { pos = vec3(2, -9.5, 0), heading = 90 } } },
    } },
  } },
  properties = { { key = 'flat_1', template = 'house', unit = 'flat_1', name = 'Flat 1',
    label = '1', building = 'Your Building', placement = { pos = vec3(x, y, z), heading = h } } },
}
```

Rules (`property_validate.lua`): `format` must be `1`; `id` `^[a-z0-9_.-]+$`, 3-48 chars; `version` string <= 32 (default `'1'`); keys `^[%w_%-%.]+$` (template/unit/property <= 64, door <= 32); labels <= 100 (property `label` <= 60); `archetype` required (name or hash; `0`/`false` = no interior). Door: `role` `'entrance'|'interior'|'garage'` (default interior), `model` required, `pos` required, `lock` bool, `pair` = another door key of the unit. Sign/manager `{ pos, heading }` (sign may name `post`). Limits: templates 256, units 64/template, shapes 16/unit (>= 1), polygon points 3-64, doors 32/unit, bays 1-8, rooms 64/template, properties 2000, everything in a unit within 250 m of the origin; box size x/y 0.1-500, z 0.1-100. `properties` optional (a template-only pack teaches WHIP the interior; admins then use Register here).

Applying: identical pack writes nothing (`'unchanged'`). It may change templates, unit bases, each property's template/unit/placement, and name/label/building only if an admin has not changed them since. Never owners, keys, furniture, admin settings or overlays. A property the pack drops is flagged orphaned (not deleted); one an admin deleted is never recreated; a unit part both changed keeps the admin's and flags `conflict`; a pack property landing on an admin property (same interior, placement and flat) takes it over with owner, keys, furniture; when the resource stops its properties stay, owned, closed. A pack id belongs to one resource while it runs (`'the pack id "x" already belongs to <res>, which is running'`).

## Properties: client exports and events

### GetCurrentProperty() — CLIENT
`{ id, name, label, building, ownerCharId, mine, key }` or `nil`; `mine` = local character owns it, `key` = holds a key.

### GetInteriorFurnishState(interiorId) — CLIENT
`'pending'` (will be made or remade, e.g. after `whip_core:interiorRefreshed`, not up yet) | `'done'` (up, or the furnisher has the room) | `'none'` (no saved furniture, not a property interior, or 0/nil id) | `'idle'` (has furniture but beyond `PropertyFurnitureDistance` or not among the nearest `PropertyFurnitureRooms`). Interior matched to a property within 2 m of its placement; cached per interior for 1 s. Ask a few times a second or listen for the event; wrap in `pcall` in case whip_core is not running.

Client events (`WhipEmit`, local): `whip_core:property:entered` / `exited` `{ propertyId, name }`; `whip_core:property:furnished` `{ propertyId, interiorId, count }`; `whip_core:property:unfurnished` `{ propertyId, interiorId }`; `whip_core:property:furnishStateChanged` `{ propertyId, interiorId, state }` (interiorId may be nil before the copy is found). Event you fire: `whip_core:interiorRefreshed(interiorId)`.

Server events: `whip_core:property:ownerChanged` `{ propertyId, ownerCharId, previousOwnerCharId, by }` (`by` = buyer's charId on a sale, nil from exports); `whip_core:property:keyGranted` `{ propertyId, charId, by }`; `whip_core:property:keyRevoked` `{ propertyId, charId }`.

---

## Doors: model

- Saved doors live in table `doors` (`model` stored SIGNED as `GetEntityModel` returns; names hashed, unsigned numbers converted). Lock state is memory only: EVERY door starts locked at every server start (`locked`/`defaultLocked` columns are unread).
- Each door within 15 m (nearest 24) gets an E prompt on both handle faces within `Config.DoorInteractRange` (3.0 m); the circle follows the swinging door and flashes green (unlocked) / red (locked) / amber (someone was refused). The server decides every lock and unlock.
- **Double doors**: two saved leaves linked (`link` in EnsureDoors, `LinkDoors`, Door Editor E, `pair` in property packs); they lock together; the toggle also checks the partner's requirements.
- **Garage doors**: no separate type. A model wider than 1.7 m and at least 1.6 m tall (not in `Config.DoorPromptOffsets`) is treated as a garage door on the client: one padlock prompt that slides along the door with the player and tilts with it, labelled `'Open Garage'` / `'Close Garage'`. Sliding doors have no special handling (the GTA DoorSystem moves them). Prompt placement: `Config.DoorHandleAlong` (0.85 of width), `Config.DoorHandleHeight` (1.05 m), overrides `Config.DoorPromptOffsets = { [hash] = { x, y, z } }`.
- **Auto-lock**: `autolock` + `autolockDelay` (seconds 1-3600, default 10; EnsureDoors default 10). After any unlock (press, `SetDoorLocked`, `UpdateDoor{locked}`, Door Manager) the door and its partner relock after the delay; every later state change supersedes the timer. A PICKED lock never auto-locks. A held door never relocks by itself.
- **Kinds of door ownership**: plain (admin / `CreateDoor`: anyone may change it); **managed** (a declared set via `EnsureDoors`/`EnsureDoor`, or a property: only the manager may change `requirements`, link, `autolock`, `autolockDelay`, `metadata`; label and folder open to all); **held** (in memory, a run's, via `HoldDoor`).
- Door Editor (`/whip` → World → Doors, `whip.devtools`): G save aimed door, E link two, R delete; + New Door wizard (one or two leaves, name, folder, locked/unlocked start, autolock delay 1-300, access).

## Doors: requirements

Any-of: ONE match opens. `nil` or `{}` = anyone. Normalised shape (`normaliseRequirements`, `doors.lua:343`):

| Key (aliases) | Opens for |
|---|---|
| `jobs` (`job`): key or list of keys | anyone with a role there (employed or owner), on duty or not |
| `onDuty = true` | with `jobs`: only while on duty at that job; without `jobs`: on duty at any job |
| `charIds` (`charId`): id or list | those characters. An EMPTY list = nobody (used for vacant properties) |
| `items` (`item`): key, `{ key = }`/`{ item = }`, or a list; `count = n` (whole >= 1) | anyone carrying that many (counted across all their containers, accessory strip included) |
| `ace = 'whip.admin'` | anyone with the ACE (developer mode counts for `whip.devtools`) |
| `lockpick = true` | a LOCKED door offers a lockpick attempt to someone refused |

Any other key is refused (`'requirements: "x" is not a door requirement — jobs, charIds, items, ace, onDuty, lockpick'`). `onDuty`/`lockpick` kept only when `true`.

`require` (the action word) is accepted on doors (and stashes) in place of `requirements` only when it names ONE rule; more than one is refused (an action's `require` needs ALL its rules, a door's requirements ANY). Giving both is refused.

Refusal reasons (first recorded wins, in this order): `'Requires being on duty'`, `'Requires job: police, ems (on duty)'`, `'Not authorized for this door'`, `'Missing required key'`, `'Missing permission: <ace>'`, else `'Door is locked'`; unreadable stored requirements: `'This door is misconfigured: <why>'`. With no loaded player, charIds and items checks are skipped (fail closed).

## Doors: server exports

`whip_core/server/doors.lua:2218-2468`. A door argument is a doorId, or `{ key = 'office' }` (+ `set = '<id>'` with several sets) for a door the CALLER declared; a key never reaches another resource's doors (`'you have declared no door "x"'`).

### EnsureDoors(list, opts) — SERVER, WAITS
Entry fields (others warned in console): `key` (required, `^[%w_%-%.:]+$`, <= 60), `model` (required, name or hash, signed or not), `coords` (required: vector3, vector4 with w = heading, or table `{x,y,z[,w|heading]}`; or plain `x, y, z`), `heading` (wins over w), `label` (default the key), `folder`, `requirements` (or single-rule `require`), `autolock` (bool), `autolockDelay` (default 10), `link` (key of the other leaf in this list).
`opts`: `id` (set id, default `'doors'`), `label` (Doors page name, default the resource name), `prune` (default `true`; `false` keeps doors a key left).
- New key: makes the door, or ADOPTS the door already within 0.5 m (same model; its old requirements/label/folder/autolock/link kept to restore on release). Known key: label, folder, requirements, autolock, link follow the list. Key left the list (prune): released (deleted if made, restored if adopted).
- Checked whole first (bad key, duplicate key, missing model/coords, requirements not a table, link to self or to a key not in the list): one bad entry = nothing changes, `false, reason`. A door that cannot be placed (another model on the spot, another manager's door, held door) goes to `failed`.
- Returns `{ doors = { [key] = doorId }, failed = { [key] = why }, released = n }` or `false, reason`. Declared doors stay when your resource stops. Requirements, autolock, link and existence belong to the list; a Doors page rename lasts until your next start.

```lua
Whip.register(function()
  local res, why = exports.whip_core:EnsureDoors({
    { key = 'lobby_l', model = 'v_ilev_ph_gendoor004', coords = vector4(-868.84, -1275.53, 5.10, 110.0), link = 'lobby_r' },
    { key = 'lobby_r', model = 'v_ilev_ph_gendoor004', coords = vector4(-867.60, -1273.20, 5.10, 110.0) },
    { key = 'office', model = 'v_ilev_ph_gendoor', coords = vector3(-870.1, -1280.4, 5.1),
      requirements = { jobs = { 'realestate' }, onDuty = true }, autolock = true },
  }, { label = 'Pink Lady' })
  if not res then print('doors: ' .. why) return end
  for key, reason in pairs(res.failed) do print('door ' .. key .. ': ' .. reason) end
end)
```

### EnsureDoor(key, data, opts) — SERVER, WAITS
One door, never prunes. `data` = an entry without `key`; `link` is refused (it must name a door in the same call: use EnsureDoors for pairs). Own set `'door:<key>'` unless `opts.id`; so EnsureDoors neither prunes nor undoes it. Returns the door record or `false, reason`. Release it: `EnsureDoors({}, { id = 'door:<key>' })`.

### CreateDoor(data) — SERVER, WAITS
`data = { label, folder, model, x, y, z, heading, requirements, metadata, linkedDoorId? }` (or `require`). Saved, always LOCKED (`data.locked` ignored), `autolock = false` (set it with `UpdateDoor`). Not managed: left to admins. Returns the door, or `false, reason, existingDoorId`: `'A door needs a model'`, `'A door needs x, y and z'`, `'Door already exists at this position (#id)'` (within 0.5 m), `'A door is being created at this position right now'`, `'Could not save the door'`, requirements errors, NOT_READY.

### SetDoorLocked(door, locked) — SERVER
Locks/unlocks the door and its linked partner, tells nearby players; unlock schedules auto-lock. `locked` FiveM-truthy (nil, false, 0 = unlocked). `true` or `false, 'Door not found'`. Works on held and managed doors.

### IsDoorLocked(door) — SERVER
`boolean`, or `nil` for no such door.

### CanUseDoor(source, door) — SERVER
`true`, or `false, reason` (the reason the player is shown). For a held door, the hold's requirements apply.

### GetDoor(door) — SERVER
Full record `{ doorId, label, folder, model, x, y, z, heading, locked, autolock, autolockDelay, linkedDoorId, requirements, metadata }` (`metadata.managedBy = { system, id, key, label, created|adopted, prev }` on managed doors) or `nil`.

### GetDoors() — SERVER
Every door (including runtime held ones).

### GetDoorsNearby(x, y, z, range) / GetDoorsNearby(coords, range) — SERVER
Measured FLAT (z ignored: a stairwell's doors all come back). Range default 25. `{}, 'GetDoorsNearby needs a point: ...'` without a point.

### GetDoorByPosition(x, y, z, range?) / (coords, range?) — SERVER
3D, range default 1.0; the FIRST door found in range, not the nearest.

### UpdateDoor(door, updates, manager?) — SERVER, WAITS
Allowed fields: `label`, `folder` (`''` clears it), `locked` (takes the lock path, partner too), `requirements` (clear with `{}`, never `nil`), `autolock` (bool or 0/1), `autolockDelay` (1-3600), `linkedDoorId`, `metadata`. Any other field: `'"x" is not an updatable door field'` (position, model, heading are fixed; move = delete and recreate). Managed fields (`requirements`, `linkedDoorId`, `metadata`, `autolock`, `autolockDelay`) on a managed door need `manager` = its set (`{ id = 'doors' }`, your `opts.id`, or `'door:<key>'`); the system is always `'resource:<caller>'`. Refusals: `'Door #n belongs to <label>. Change it in its EnsureDoors list, or through the manager that holds it'`, `"A door's manager is set by EnsureDoors or EnsureDoor, not by UpdateDoor"` (metadata whose `managedBy` differs from the door's), `"Door #n is a run's and is not saved"`, `'The door is busy — try again'`.

### DeleteDoor(door, manager?) — SERVER, WAITS
Unlinks partners in the same transaction. Managed door: only its manager (a declared door comes back on your next EnsureDoors). Runtime door: refused (it goes with its hold).

### LinkDoors(door1, door2, manager?) — SERVER, WAITS
Links two doors (accepts ids or `{ key }`), unlinking each one's old partner, in one transaction. Refused: same door, a runtime or held door, any involved door (including old partners) managed by someone else.

### UnlinkDoors(door, manager?) — SERVER, WAITS
Unlinks both halves; `true` if not linked. `UpdateDoor(id, { linkedDoorId = nil })` cannot do this.

### GetManagedDoors(id?) — SERVER
Doors the calling resource manages (system `'resource:<caller>'`), all sets or one set id.

## Doors: managed sets and held doors

Sets: `'doors'` (EnsureDoors default), your `opts.id`, or `'door:<key>'` (EnsureDoor). Pass `{ id = <set> }` as `manager`. To give doors back, declare the set without them. A key may move between `'door:<key>'` and another set of the same resource keeping its history. Properties manage their own doors under system `'property'` (no resource can change them). The Door Manager offers Release on a door whose managing resource is no longer running.

### HoldDoor(data, opts?) — SERVER, WAITS
`data = { model, x, y, z, heading?, label? }` (as the Door Editor reads them). Holds the door within 0.5 m (both leaves of a linked pair), or makes a TEMPORARY unsaved door (id >= 2^32, sent to every client) where there is none. While held nobody may press it until you say who (default requirements `{ charIds = {} }`), and it never relocks by itself; lock with `SetDoorLocked`. `opts = { tag?, requirements? }`: `tag` releases it with your run (`ReleaseTag`). The hold ends on `ReleaseDoor`, tag release, or your resource stopping: a temporary door goes; a saved door returns to the lock it had (and its pending auto-lock if one was armed). Lockpicking still follows the row's own `lockpick`. Returns `doorId, 'held' | 'made' | 'already'` or `false, why`: different model on the spot, `'Door #n is held by another run'`, `"Door #n belongs to <x>, and is not a run's to take"` (property or managed door), other leaf held/managed, `'Door #n is being taken over by its manager right now'`, `'A door is being saved at this spot right now: try again'`, `'<tag> has ended'`, NOT_READY.
```lua
local vault = exports.whip_core:HoldDoor({ model = vaultModel, x = pos.x, y = pos.y, z = pos.z }, { tag = 'heist:' .. jobId })
exports.whip_core:SetDoorLocked(vault, false)
exports.whip_core:SetHeldDoorAccess(vault, { charIds = crewCharIds })
```

- **SetHeldDoorAccess(doorId, requirements) — SERVER**: door-shaped requirements; `nil` = nobody, `{}` = anyone. `false, 'Door #n is not one you hold'`.
- **ReleaseDoor(doorId) — SERVER**: give it back now. Same refusal.
- **GetDoorHold(doorId) — SERVER**: `{ owner, tag, doorId, made }` or `nil`.

## Doors: client exports and behaviour

The client holds EVERY door (seven wire fields `{ doorId, label, model, x, y, z, locked }`; requirements never leave the server), sent at login (`whip_core:client:doorsSync`) and on core restart; lock changes reach only players near the door (cell index), and a player entering new cells is caught up (`doorStatesBatch`). A far door's `locked` may be stale; ask the server for anything that matters.

- **IsDoorLocked(doorId) — CLIENT**: boolean from cache, `nil` unknown.
- **GetDoorsNearby(range) / (coords, range) / (x, y, z, range) — CLIENT**: flat distance, default 25; `(range)` alone measures from the player.
- **GetLoadedDoors() — CLIENT**: every door the client holds (see Docs vs code).
- **GetDoor(ref) — CLIENT**: by id, `{ id = }`, or `{ entity = }` (the saved door a world entity is: same model, nearest within 2 m among doors within 50 m).

Native registration: doors within 50 m (flat), nearest 40 (DoorSystem holds 75), registered with `AddDoorToSystem` under hash `GetHashKey('%.2f_%.2f_%.2f')` of position; a refused registration (another script claimed it, or the 75 slots exhausted) is logged and retried each second. Do not run another door script on the same doors. A press sends `whip_core:server:doorToggle` (client cooldown 500 ms).

## Doors: events, rate limits, internals

Server events (`WhipEmit`; any resource can fire them, so ask `IsDoorLocked` for truth):
- `whip_core:door:lockChanged { doorId, locked, source, cause }`: only on a real change; `cause` `'press' | 'lockpick' | 'autolock' | 'code' | 'released'`.
- `whip_core:door:denied { doorId, source, reason }`: a press refused.

Press handling (`whip_core:server:doorToggle`, rate 500 ms, must be within `DoorInteractRange + 2` m): authorization runs for locking AND unlocking; the partner leaf is checked too (refusal uses the partner's reason). Refused: the player sees the reason, onlookers see an amber flash; if the door is locked and `requirements.lockpick`, the client is offered the pick.

Lockpick (`whip_core:server:doorLockpickAttempt`, rate 2500 ms): door must be locked and pickable; player must carry item `'lockpick'` (`'You need a lockpick'`); server-run skill check `LockpickSkill(source, 'medium')`; must still be near (`'You moved away from the door'`). Success unlocks (cause `'lockpick'`), logs `lockpick_door`; failure logs `lockpick_fail` (`'Lockpick failed'`). The partner opens only if it is itself pickable. No auto-lock after a pick.

Boot warning: if `ceil(Config.GroundItemStreamRange / GroundItemCellSize) * cellSize < 50`, door lock changes lag (raise `GroundItemStreamRange`).

---

## Gotchas

1. `HasJobPermission` for a level-100 role answers `true` for ANY permission string, even a typo or one the job never declared (`jobs.lua:1746`); below 100 an undeclared name is always false.
2. `bankAccess` is not a permission: `HasJobPermission(x, job, 'bankAccess')` is false below level 100.
3. `EnsureJob` role definitions silently drop unknown permission keys (`cleanPermissions`), whereas `CreateJobRole`/`UpdateJobRole` refuse them. Declare `permissions` (job's own) in the same `EnsureJob` call so role toggles referencing them survive.
4. `EnsureJob` never edits an existing role and never changes the owner; to fix a role after first boot use `UpdateJobRole` or `/whip`. Omitting `permissions` or `selfClockOn` on a later call leaves the stored values (pass `selfClockOn = true` to re-enable self clock-on). `data.settings` and `data.owner` apply only on creation.
5. A job has NO business account until it has an owner; `infinite`/`stocked` shop sales then still charge the customer and the revenue is lost (console warning only). Give business jobs an owner.
6. Duty is never persisted; `whipJob` bag is `false` off duty, not `nil`. Clocking on again at the current job fires no event. Server `ClockOn` requires the player online.
7. `ClockOn` with `opts.by` enforces `selfClockOn`; without `by` it does not. Station-only duty = `selfClockOn = false` + server `ClockOn(source, job)` without `by`.
8. Client `HasJobPermission`/`IsPlayerClockedOn` are hints from a cached list; always re-check on the server.
9. The owner is not an employee: `FirePlayer` on the owner answers `'They do not work there'`; `GetJobEmployees` omits them unless hired; `UpdateJob { owner = false }` is refused while an account exists.
10. `EnsureShop` uses `x, y, z, heading`; `Config.Shops` uses `pos = vector4(...)`. EnsureShop with an unchanged declaration does nothing even if an admin changed the shop since; changing the declaration overwrites those fields.
11. `CreateShop`/`UpdateShop` do not resolve job keys or validate `mode`/`containerId`; pass a numeric `jobId`.
12. `AddCatalogItem` needs `price` as a Lua number (a numeric string is refused), and only works on `npc`/`infinite`. Stocked shops are priced with `SetShopItemPrice` (any container id is accepted there).
13. A stocked shop needs a real `containerId` (e.g. from `EnsureContainer`) and a `jobId` for Manage Stock; a job-less stocked shop has no staff management at all.
14. The shop basket holds real stock for stocked shops; stock is back on the shelf only when the session ends (close, walk-away sweep every 10 s beyond 20 m, delete, mode change).
15. `whip_core:shop:closed` fires only for the player's own close, not for walk-away, deletion or mode change.
16. `SetPropertyOwner` is not a sale: no price check, no payment, no `property_bought` log; take the money first and refund on failure. Setting the same owner keeps keys.
17. Property keys are owner-only in game; keyholders cannot furnish, give keys or change themes. Exports have no distance or ownership checks.
18. `GetProperty` uses `id`, not `propertyId`; events use `propertyId`.
19. Property doors are managed: you cannot change their requirements with `UpdateDoor`, `HoldDoor` refuses them, and lockpick only works if requirements include `lockpick` (they never do for property doors).
20. A door `requirements = { lockpick = true }` alone locks the door to EVERYONE except a successful pick (no rule matches a press).
21. `requirements = nil` in `UpdateDoor` does nothing (nil is no key); clear with `{}`. `linkedDoorId = nil` likewise: use `UnlinkDoors`.
22. A door with `charIds = {}` is "nobody"; `{}` requirements is "anyone".
23. Every door starts LOCKED at every server start, including doors you created unlocked; property interior doors are left out of management unless `lock = true` for that reason.
24. Door `jobs` requirements take job KEYS (strings), not jobIds; employed or owner counts, duty only with `onDuty = true`.
25. `GetDoorsNearby` (both sides) is flat; `GetDoorByPosition` returns the first match within range, not the nearest: keep the range small.
26. `EnsureDoors` adopts an existing door within 0.5 m of the same model; a different model there goes to `failed`. Declared doors are not deleted when your resource stops; declare the set empty (or without them) to release.
27. `UpdateDoor` on a managed door with `metadata` must carry the same `managedBy` block, or it is refused.
28. Client door cache: requirements are never on the client; a far door's lock state can be stale (only nearby cells get pushes).
29. Theme provider exports run on the SERVER; `SetAllThemes` replaces everything (missing homes = 0). After redrawing an interior, fire `whip_core:interiorRefreshed` or furniture lamps stop lighting.
30. `.lua` property packs may not contain any code; generate with code in a script and call `RegisterPropertyPack`. `RegisterPropertyPack` before WHIP is ready answers `true, 'queued'`, and a later refusal is only in the console and `GetPropertyPacks().problems`.

## Docs vs code

1. Client `GetLoadedDoors`: docs say "every door the client has streamed in, not every door"; code returns every door the server synced at login (`clientDoors` holds every door, `client/doors.lua:11, 467-484, 635-641`), with possibly stale lock states for far doors.
2. `CreateShop`/`UpdateShop`: docs say data is "as EnsureShop's" with `jobId` taking a jobId or key; only `EnsureShop` resolves keys (`server/shops.lua:1682-1684, 1739`). `Shops.create` writes `data.jobId` straight into the INT column (`shops.lua:1238`) and `updateNow` does the same (`shops.lua:1322-1328`), and neither checks `mode`, `containerId` or `name`.
3. `GetDoorByPosition` and `LinkDoors`: docs list only `(x, y, z, range)` and numeric ids; code also accepts `(coords, range)` (`doors.lua:2222-2230`) and `{ key = }` refs (`doors.lua:2438-2445`).
4. `ClockOff(who)` with no job always answers `true` (`jobs.lua:1658-1663`); `'They are not on duty'` only comes with a named job.
5. `GetPlayerJobs` entries (server and client) also carry `dutyOrder` (`jobs.lua:1488`), not listed in docs.
6. `types/client.lua:1354` `GetCurrentProperty` return type omits `key`, which the code returns (`client/properties.lua:773-774`) and the docs list.
7. `types/server.lua:3570` says a property's `price` is "nothing is sold yet"; buying at the sign is implemented (`server/properties.lua:1988-2101`).
8. `UpdateJobRole`/`DeleteJobRole`: the "no job without a level 100 role" rule is enforced only when `opts.by` is given (`jobs.lua:2216, 2238`); trusted calls can remove or demote the last level-100 role.
