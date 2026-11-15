# Players, Lifecycle, Stats, HUD, Death and Escort

Covers the player sheet and every player export (server and client), the character lifecycle and its events, the save system, flags and metadata, stats and effects (built-ins, `RegisterStat`, `OnStatChanged`, damage modifiers), the HUD ring framework, death / respawn / revive, escort, the hands block, and the Player Manager. Built from doc anchors `guide-lifecycle`, `player`, `client-player`, `guide-stats`, `server-stats`, `guide-hud`, `guide-death`, `guide-escort`, `guide-playermanager`, verified against `whip_core/server/{player,player_lifecycle,player_flags,character,stats,hands,events_misc,helpers,player_text,dev_players}.lua`, `shared/{body_state,hands,statebags}.lua`, `client/{player,stats,hud,hud_skin,death,escort,spawn,charselect}.lua`, `config.lua`, `types/{classes,server,client,events}.lua`.

## Contents
- Conventions (person refs, Whip.core, sides)
- The player sheet (WhipPlayerData) and its variants
- Server exports: finding and reading players
- Server exports: names, cash, messages, blips, props
- Metadata
- Flags
- Saving, kicking, logging out, appearance
- Client exports: local player, body, walk, emotes, voice
- Character lifecycle: connect, select, load, logout, delete
- Lifecycle events (server and client)
- Save system
- Stats: built-ins and config
- Stats: server API
- Stats: client API
- Effects and damage modifiers
- Stat tick internals
- HUD framework
- Death and respawn
- Death exports and events
- Escort
- Hands (BlockHands)
- Statebags
- Player Manager (admin)
- Gotchas
- Docs vs code

## Conventions

- **Person ref** (`WhipPersonRef`, `server/helpers.lua:96` `WhoIs`): a bare number is ALWAYS a server id (must be online with a character); a character, online or not, is `{ charId = n }`. Never pass a charId as a bare number. Exports whose name says Character/CharId take the charId directly (`GetCharacterNames`, `IsCharacterDeleted`).
  - `WhoIs` failures: `'A character is { charId = n }'`, `'No player with that server id is online (for a character, pass { charId = n })'`.
- `Whip.core:Name(...)` (from `@whip_core/lib/satellite.lua`) is the same call as `exports.whip_core:Name(...)`. Register stats, listeners, effects-related registrations inside `Whip.register(function() ... end)` (re-runs on whip_core restart and for late starters).
- `---@async` / WAITS: the export can yield (DB or player); call from a thread/handler, never at file scope.
- Sides: SERVER, CLIENT. Some names exist on both with different signatures (`GetPlayer`, `GetStat`, `OnStatChanged`, `GetPlayerFullName`, `IsPlayerDead`, `IsReady`, `GetEffects`, `HasEffect`, `BlockHands`...).

## The player sheet (WhipPlayerData)

Every `GetPlayer*` export returns a plain copy (`WhipPlayer:serialize()`), no methods (metatables do not cross resource boundaries). Change the player only through exports.

| Field | Type | Notes |
|---|---|---|
| `source` | number | server id |
| `session` | number | this character load's number; new every load; pass to `IsSessionCurrent`. Seeded from `os.time()*1000`, never reused across restarts (`server/player.lua:111`) |
| `userId` | number | account id (persists across characters) |
| `charId` | number | character id |
| `firstName`, `lastName` | string | |
| `fullName` | string | `firstName .. ' ' .. lastName` |
| `dateOfBirth` | string | `'YYYY-MM-DD'` (formatted by the DB, `server/character.lua:182`) |
| `gender` | `'male'\|'female'` | |
| `cash` | number | computed: banknote items across every carried container (`getCash`) |
| `position` | `{ x, y, z, w }` | live ped coords+heading when the sheet is made; the saved position until the ped has been "placed" (within 15 m of the spawn target, or 60 s after load outside the creator) |
| `health` | number | 0-200, 200 full, GTA dead at <=100; from the stats cache |
| `armour` | number | 0-100 |
| `isDead` | boolean | server's own death state |
| `metadata` | table | every key, incl. `appearance`; NOT secret (the client receives it) |

Variants:
- **Handler sheet** (`handlerSheet`): what a SecureEvent/SecureCallback handler, item use handler, context action or effect callback of another resource receives: the full sheet **without `metadata`**. Use `GetPlayer(source)` for metadata.
- **Light sheet** (`lightSheet`, `GetPlayers({ light = true })`, `sheet = 'light'` on an effect/SecureEvent): `source, session, userId, charId, firstName, lastName, fullName, dateOfBirth, gender, isDead` only (no position, cash, health, armour, metadata).
- **Client sheet** (client `GetPlayer()`): same serialized table the server sent at load plus extras `isNewCharacter`, `openCreator`, `wakeIn`, `nearCar`; `cash` and `metadata` are kept current by server pushes; `isDead`, `health`, `armour` read live at call; `position` is the load position (use `GetEntityCoords(PlayerPedId())`). `{}` before a character loads.
- Identifiers (`license`, `steam`, `discord`, `fivem`) are never on any sheet (the sheet also goes to the client). Use `GetPlayerIdentifiers`.
- Pockets and stats are not on the sheet: use `GetInventory` / `GetStats`.

## Server exports: finding and reading players

### IsReady() — SERVER
Whether whip_core finished starting. `Whip.register` does not need it. Returns `boolean`.

### GetPlayer(who) — SERVER
- `who`: server id, `{ charId = n }`, `{ userId = n }`, or `{ identifier = 'license:...' }` (kind must be `license`, `steam`, `discord` or `fivem`).
- Returns: `WhipPlayerData|nil` (nil until the character has fully loaded; online only). Copies the whole sheet including appearance; for one value use `GetCharId`.
```lua
local owner = exports.whip_core:GetPlayer({ charId = v.owner.charId })  -- nil when offline
```

### GetCharId(source) · IsPlayerLoaded(source) · IsPlayerDead(source) — SERVER
No copy; use on hot paths. Returns `integer|nil` · `boolean` · `boolean` (`IsPlayerDead` is the server's reading, what SecureEvent `whileDead` checks; `false` for nobody loaded).

### IsSessionCurrent(source, session) — SERVER
True while the same character load is on that source, not logging out (`closing`), not replaced. Check after any long wait before giving/taking (a player who switched character mid-wait would be charged on one and paid on the other). Logout itself waits up to 2 s for running handlers, so short waits are covered.
```lua
local receipt = exports.whip_core:ChargePlayer(source, 500)  -- yields
Wait(4000)
if not exports.whip_core:IsSessionCurrent(source, player.session) then
    exports.whip_core:RefundPlayer(receipt)
    return false, 'You left before the sale went through'
end
```

### GetPlayers(opts?) — SERVER
- `opts.light` (boolean): light sheets (much cheaper).
- Returns `table<number, WhipPlayerData>` keyed by server id (a copy).

### GetPlayerIdentifiers(source) — SERVER
Returns `{ discord, fivem, license, steam }` (each may be nil) or `nil` when not loaded. Note: looks up `Players[source]` without `tonumber` (`server/player.lua:966`), so pass a number.

### GetPlayersInRange(coords, range?) — SERVER
- `coords`: vector3 or `{ x, y }` (height ignored). `range`: metres, default `Config.NetworkRange` (424).
- Returns `number[]` server ids; `{}` for bad input. Use instead of `-1` for news about a place.

### GetPlayerCoords(source) — SERVER
`vector4|nil`: ped position+heading now (the saved position until the ped is placed).

### IsCharacterDeleted(charId) — SERVER, WAITS
- Returns `true, 'deleted'` · `true, 'no such character'` · `false` (live; online characters answer `false` without a DB read) · `false, why` when it cannot tell (`'a character is named by its charId'`, `'could not read the character'`). A doubt never says "deleted".
- Always call it before removing data on `whip_core:character:deleted` (any resource can fire that event).

## Server exports: names, cash, messages, blips, props

### GetPlayerFullName(source) — SERVER
`string|nil`. Character name without copying the sheet (FiveM's `GetPlayerName` is the account name).

### GetCharacterNames(charIds) — SERVER, WAITS
- `charIds`: number[] (first 200 valid ids used).
- Returns `{ [charId] = 'First Last' }`, unknown ids omitted. Online names from memory, others cached/batched from DB. The query does not filter deleted characters (`server/helpers.lua:380`), so deleted characters' names are returned too.
- Check `CanSeePlayerName` before showing a stranger's name.

### CanSeePlayerName(viewer, target) — SERVER
- Both are person refs; the viewer must be online. Own name always allowed.
- `Config.ShowPlayerNames`: `'nearby'` (default: within `Config.PlayerNameRange` 25 m, same routing bucket, target not in the creator; an offline target is never nearby), `'always'`, `'never'`.
- Returns `true`, or `false, 'Too far away' | 'Names are hidden on this server' | 'Player not loaded'`.

### GetPlayerCash(source) — SERVER
Total banknotes in every container carried. Returns `number`; `0, 'Player not loaded'`. (Cash is the `cash` item; see money-banks.md.)

### NotifyPlayer(source, text, kind?, duration?) — SERVER
- `source`: player or `-1` for everyone. `text`: up to 300 chars (sanitized). `kind`: `'info'` (default) `'success'` `'warning'` `'error'` (anything else becomes info). `duration`: ms, clamped 500-30000 (`server/player.lua:1019`).
- Returns `true`, or `false, 'They are not on the server' | 'Nothing to say: the text is empty'`.
- A SecureEvent handler's `return false, 'why'` is shown through this toast.

### ShowPlayerText(source, text, opts?) · HidePlayerText(source) — SERVER
The instruction band (client `ShowText`). One band per player; a new one replaces it. Colour codes removed, max 200 chars. Goes when your resource stops, your tag is released, or they log out.
- `opts.position`: `'bottom'` (default) or `'top'`. `opts.progress`: 0-100 (clamped) fills the band. `opts.countdown`: seconds, a clock after the text run by the client, stops at 0:00 (0 to one week). `opts.countdownTotal`: full length if started earlier. `opts.tag`: run tag (`ReleaseTag`).
- Returns `true` or `false, reason` (`'no such player'`, `'text is empty'`, `'progress is a number, 0-100'`, `'countdown is a number of seconds, 0-604800'`). `HidePlayerText` removes only yours: `'nothing is shown'`, `"the text on screen is <res>'s"`.

### ShowBlip(audience, id, spec) · HideBlip(id) · SetPlayerWaypoint(source, coords) — SERVER
- `audience`: `'everyone'`, `{ people = { serverId | { charId = n } } }` (a charId follows them across relogs), or `{ job = 'police', onDuty = true }` (docs).
- `id`: string|number, yours; the same id updates/moves it.
- `spec`: `coords` (vector3, required), `label` (40 chars), `sprite` (default 1; 0 none), `color` (5 yellow default, 1 red, 2 green, 3 blue, 0 white), `route` (bool), `radius` (m, area), `shortRange`, `scale` (0.3-2, default 0.9), `flash`, `tag`.
- Gone when your resource stops or tag released. `SetPlayerWaypoint` sets GTA's waypoint on one player's map. All return `true` or `false, reason`.

### ShowPropSet(id, spec) · HidePropSet(id) — SERVER
Client-side-only props (never networked, frozen, not pickable) created by each game near them. Same `id` replaces.
- `spec.props` (max `Config.PropSetMaxProps` = 256): each `{ model, coords, rot?, heading?, interior?, light?, collision?, weapon?, attach?, attachOffset?, attachRot?, drawDistance? }`. `rot` = `vector3(tiltForward, tiltSideways, heading)`, rotation order 2. `collision = false` walk-through. `interior = true` waits for an MLO and files it in its room; `light = true` files it in the interior's limbo so a lamp lights it. `drawDistance` 1-500 m (default 150). `weapon`: a firearm world model (`'WEAPON_RPG'`). `attach`: `{ net = netId }`, `{ set = id, index = n }` or `{ index = n }`, offset `attachOffset` (m) / `attachRot` (deg).
- `spec.audience`: `'everyone'` (default) or `{ people = {...} }`; `spec.tag`.
- Returns `true` or `false, reason`; a model a game lacks is skipped there.

### RequestScreenshot(source, opts?) — SERVER, WAITS
Picture from the player's own game (up to 30 s). `opts`: `format` ('jpg'|'png'|'webp'), `quality`, `width`, `height`, `ui`, `frames`, `every`. Returns data URL string, or `false, why`. For tools, not anti-cheat (a game can send a fake).

## Metadata

### GetPlayerMetadata(who, key?) — SERVER, WAITS
- `who`: person ref; an offline character is read from the DB (after any owed save settles).
- Returns the key's value, the whole table (no key), or `nil` for nobody / read failure.

### SetPlayerMetadata(who, key, value) — SERVER, WAITS
- Writes one key, saved with the character (offline: the row is read-modified-written while the char is held in `LoadingCharIds` as `'metadata'`).
- Refused: non-string/empty key; WHIP keys `appearance`, `outfits`, `creatorPending`, `walk`, `mood`, `whipFlags`, `moneyHeldOwed`, `pourRefundOwed`, `lastSeat` (reading them is fine); non-JSON values (vector3, function, NaN): `'metadata "k" cannot be saved (not JSON-encodable — ...)'`; offline character busy/logging in: `'That character is busy right now — try again in a moment'`; no such person.
- Returns `true` or `false, reason`.
- Prefix keys (`'myjob_licences'`): one shared table. The owning client receives every value live (`whip_core:client:metadataChanged`): never put codes or cheat flags here.
- Only `setMetadata` persists; assigning to a sheet's `metadata` table does nothing.

## Flags

Named facts about a character that survive restarts ("met the fence", "jobs done: 3"), also used by Director scenarios. Stored in metadata key `whipFlags`; online characters only (`server/player_flags.lua`).

### SetPlayerFlag(who, name, value) · GetPlayerFlag(who, name) · GetPlayerFlags(who) — SERVER
- `who`: server id or `{ charId }` of an **online** character.
- `name`: starts with a letter, then letters/digits/`_ . - :`; max 64. Names starting `_` are WHIP's (cannot be set via exports; hidden from `GetPlayerFlags`).
- `value`: `true`, finite number, or string (max 100 chars). `nil` or `false` clears.
- Max 256 flags per character (WHIP's own `_` flags count toward it).
- Each real change fires server `whip_core:flag:changed { source, charId, name, value, was }`. Setting the same value returns `true` with no event.
- Returns: Set: `true` or `false, reason` (`'they are not online: flags are read and set while the character is on'`, `'a flag name is letters, digits and _ . - : (at most 64), starting with a letter'`, `'a flag holds at most 100 characters of text'`, `'a flag cannot hold that number'`, `'a flag holds true, a number or text'`, `'a character holds at most 256 flags'`). Get: value or `nil` (also nil for offline/invalid name). GetPlayerFlags: `{ [name] = value }` or `nil` offline.
```lua
local jobs = exports.whip_core:GetPlayerFlag(source, 'jobs_done') or 0
exports.whip_core:SetPlayerFlag(source, 'jobs_done', jobs + 1)
```

**Flags vs metadata:** flags are typed (true/number/short text), validated names, capped, evented, online-only, Director-visible. Metadata takes any JSON value, works offline (WAITS), no event, no cap. Both are visible to the player's own game.

## Saving, kicking, logging out, appearance

### SavePlayer(source) — SERVER, WAITS
Writes pockets (whole player unit) then the character row now. Use before your own DB write that must follow an inventory change, or before something outside WHIP reads the rows. Returns `true` or `false, 'Player not loaded' | 'The save did not complete (it is retried)'`.

### KickPlayer(source, reason) — SERVER
`DropPlayer` with the reason (default `'Kicked from server'`); the drop handler saves. Returns `true` or `false, 'Player not loaded'`.

### LogoutPlayer(source) — SERVER
Full teardown and back to character select (does not drop). Returns `true`, or `false, 'Player not loaded' | 'Already leaving'`. Unless building your own character select, use `KickPlayer`.

### SanitizeAppearance(appearance) — SERVER
Runs the creator's validator: whitelist-copy, clamp indexes, reject structural errors. Optional `tattoos` (`{ { collection, overlay }, ... }`, max 40) and `hairFade` (one `{ collection, overlay }`) kept only if `shared/tattoo_list.lua` / `shared/hair_fades.lua` list them for that body (once each, list spelling); others dropped silently. Models: `mp_m_freemode_01`, `mp_f_freemode_01`. Returns `true, cleaned` or `false, why`.

## Client exports: local player, body, walk, emotes, voice

### IsReady() — CLIENT
whip_core's client loaded (not a character). `boolean`.

### IsPlayerLoaded() — CLIENT
Character loaded. `boolean` (true from the start of the load sequence, before the client `player:loaded` event).

### GetPlayer() — CLIENT
Copy of the local sheet (see variants). `{}` before load.

### GetCharId() — CLIENT
`number|nil`.

### IsPlayerDead() — CLIENT
In the death state. `boolean`.

### EnterCharacter(opts?) — CLIENT, WAITS
For tools/tests: passes the welcome screen, picks a card, presses Play without the spawn map; arrives where they left. Waits up to 90 s.
- `opts.charId` or `opts.slot` (card position; default first card).
- Returns `true` or `false, why`: `'already in a character'`, `'the character screen never came up'`, `'no character with that id on this account'`, `'no character in slot N'`, `'a character is already loading'`, `'the character did not load in time'`.

### GetPlayerFullName(serverId, wait?) — CLIENT, WAITS (with wait)
Another player's character name, asked of the server (SecureCallback `whip_core:playerName`, rate 100 ms burst 20) under `Config.ShowPlayerNames`. Own name answered locally. Cached 15 s (refusals 4 s). Without `wait` the first call returns `nil` and starts a fetch (good for per-frame labels); `wait = true` waits up to 3 s. Returns `string|nil` (nil while fetching, too far, `'never'`, nobody).

### GetBodyState() — CLIENT
Returns `'underwater'|'swimming'|'falling'` plus the words (`'You cannot do that while underwater'` / `...swimming` / `...falling`), or `false`. Progress bars take the same names in `notWhile`; a `notWhile` containing `'swimming'` also refuses `'underwater'` (`shared/body_state.lua:37`).

### SetWalkOverride(clipset) — CLIENT
Override the walk (`'MOVE_M@DRUNK@VERYDRUNK'`); newest override wins; `nil` gives it back; when the last clears, the player's own `/walk` returns (not the game default). Keyed by your resource, cleared when it stops. Returns `true`.

### PlayEmote(cmd) · CancelEmote() · IsEmoting() — CLIENT
- `PlayEmote('drink')`: `/e` name from `shared/emote_list.lua`, with props, under WHIP's cancel (X) and cleanup. Returns `true` or `false, why` (no such emote, dead, in a vehicle, a bar running, a weapon out...). Starts a moment later (anim load). Use for anything held (a phone) instead of your own `TaskPlayAnim`.
- `CancelEmote()`: stops the current emote, props away; returns whether there was one. Check `IsEmoting() == 'phone'` first to end only yours.
- `IsEmoting()`: current `/e` name or `false`.

### GetVoiceLevel() · GetVoiceName() · SetVoiceTalking(talking, mode?) — CLIENT
- Voice range is client-owned, cycled by Z (command `whip_cyclevoice`, key mapping 'Cycle Voice Range'). Levels `20, 50, 100` = `'Whisper'`, `'Normal'` (start), `'Shout'`. Fires local `whip_core:voice:rangeChanged { index, name, level }`.
- `SetVoiceTalking(true[, 'radio'])` lights the HUD voice gauge blue (orange with a radio icon for `'radio'`); held by the calling resource, turned off when it stops. Returns nothing.
- `GetVoiceSystem()` (both sides): the running voice resource info or `false`; client event `whip_core:voice:systemChanged { resource, label, features }`.

## Character lifecycle

### Connect (`server/player_lifecycle.lua:293`)
1. `playerConnecting` deferral: if whip_core not ready, waits up to 60 s; boot halted → refused.
2. A `license` identifier is required (`'No license identifier found. Please restart FiveM.'`).
3. Ban check against license, steam, discord, fivem (active, not expired). Message: `You are banned from this server.` / `Reason:` / `Expires: <date %Z>` or `This ban is permanent.` / `Ban ID: #n`.
4. User row resolved by license, falling back to fivem then discord (a Rockstar licence change recovers the account; secondary ids are `COALESCE`-updated, never wiped). New user inserted otherwise.
5. `playerJoining` → private character-select routing bucket.

### Character screen
- Client asks `whip_core:server:requestCharacters`; receives list + `Config.MaxCharacters` (default 4, max 30). List rows: `charId, firstName, lastName, dateOfBirth, gender, lastPlayed, cash (sum of 'cash' items), isDead, appearance, spawns` (no raw position, no other metadata).
- **Create** (`whip_core:server:createCharacter`): names cleaned (`Character.cleanNames`: letters, spaces, hyphens; collapsed/trimmed; >= 2 letters each; <= 30 chars: `'Names need at least two letters each.'`, `'Names are 30 characters at most.'`); DOB `YYYY-MM-DD`, a real date 1900-2100; gender `male|female`; limit `'Character limit reached (4)'`. Inserts the row with `statuses = '{}'`, `metadata = '{}'`, and `Config.DefaultCash` (500) as a `cash` item in pocket slot 1 (rolled back if that insert fails). Creates the default personal account (`Config.DefaultAccountLabel`, `isDefault`, `Config.StartingBalance` 1000 with a 'Starting balance' ledger row). Fires `whip_core:character:created { source, charId }`, then loads with `isNewCharacter = true`.
- **Select** (`whip_core:server:selectCharacter`, params `charId`, `spawnId` default `'last'`): ownership checked (`Character.isOwnLive`). Spawn picker choice re-validated server-side; ignored for a dead character or when `Config.CharSelect.spawnPicker = false`.
- **Delete**: only from the character screen; refused while that character is loading/played on any connection. Soft delete (`characters.deleted` timestamp). See "Deleting" below.

### Load (`LoadCharacterForPlayer`, `loadCharacterInner`)
Order (each step can refuse the load with a reason and return the player to the screen):
1. One live copy: a character in game or loading is refused (`'That character is already in the game.'`; `'That character is being saved. Try again in a moment.'` while an offline metadata write holds it).
2. The previous session's owed save must land (`Stores.settle('player:<charId>')`), else `'Your last session is still being saved. Try again in a moment.'`.
3. Row loaded; spawn choice resolved; `WhipPlayer.new` (new `session`). `creatorPending` metadata set for a new character; an unfinished creator reopens on later loads.
4. Inventory loaded (failure refuses the load rather than saving empty pockets). Missing default bank account is created (with starting balance).
5. Registered in `Players` (now `GetPlayer` works). `Stats.initPlayer` (health/armour from row, needs/custom from `statuses` JSON for `persist` stats, else defaults; 10 s spawn guard starts).
6. Routing bucket 0 (a new character stays in the private bucket until `creatorDone`).
7. Net events to the client: `playerLoaded` (serialized sheet), `hudDefs`, `statsSync`. Statebags set: `whipDead`, `whipJob = false`, `whipEscorted = false`, `whipMood`.
8. Sync steps (each pcall'd): ground items (within `Config.GroundItemStreamRange`, default 100), containers, vehicles + keys, garages, prop catalog, properties, shops, doors, zones, time, jobs, inventory flags/item defs, theme, item baseline.
9. Core hooks (`Character.onLife('loaded')`, e.g. money-hold refunds owed), then server `whip_core:player:loaded`.
10. Client (behind black): apply appearance, spawn (`whip_core:player:spawned` local event), place in car / near car, wait up to 3 s for stats sync, curtain, creator (new character) or arrival scene, then client `whip_core:player:loaded` (same payload table). A logout during the client sequence stops it (no client loaded event).

### New characters
- Full needs (hunger/thirst default 100), other stats at their defaults, `DefaultCash` in pockets, `StartingBalance` in bank, opens the appearance creator.
- Only that first load has `e.newCharacter` / `player.isNewCharacter` true (a reopened creator is not new): the hook for a starter car/welcome pack.
- A new character is not a new player: deleting frees a slot, so gifts can be farmed. Tie gifts to `e.player.userId`, or make them non-transferable.

### Logout (`WhipPlayer:logout`) and disconnect (`playerDropped`)
Logout order (`server/player.lua:691`): `closing = true` (secure layer refuses this session's events) → end progress bars, skill checks, asks → wait up to 2 s for handlers in flight (the handler that requested the logout is not waited on) → `ReleaseCharacterSession` (close open stashes/boots and save them, close panels (`onClose` if last viewer), end player-inventory sessions, clear bank permission cache, clock off all jobs, end shop session (basket stock returned), settle money holds, release escorts both ways) → `Stats.endEffects('logout')` (each `onRemove` runs with `effect.reason = 'logout'`) → save (teardown) → clear statebags (dmg/melee mod, escorter, dead, job, mood) → activity log → char-select bucket → core hooks → server `whip_core:player:logout { why = 'logout' }` → client net `playerLogout` (client local `whip_core:player:logout { charId }`) → save again if a listener changed something → stats cleanup → removed from `Players`, back to pending.

Disconnect: same release and save with `why = 'disconnect'`; `onRemove` reason `'disconnect'`. Stats cleanup happens AFTER the event, so `GetStat` still works inside a logout listener.

### Deleting a character
| What | After the delete |
|---|---|
| Homes owned | For sale again, every key gone; furniture and stored items stay |
| Keys held elsewhere | Removed |
| Jobs | Left; a business they owned runs on unowned (reassign in `/whip` → Economy → Jobs) |
| Stashes locked to them | Contents stay; owner and lock cleared |
| Cars and bank accounts | Unchanged; an admin can reassign |
Core hooks run before the public `whip_core:character:deleted`. `Character.reconcileDeleted` re-runs the release hooks at every start for deleted characters still holding jobs/homes/keys/stashes.

## Lifecycle events

Fired with `WhipEmit` (local events, one table payload). Names containing `client:`/`server:` are WHIP's own network messages, not API.

| Event | Side | When | Payload |
|---|---|---|---|
| `whip_core:onReady` | S+C | core ready; prefer `Whip.register` | `{ reason = 'coreStarted'\|'resourceStarted', resources? }` |
| `whip_core:player:loaded` | S | character loaded and synced (fires last) | `{ source, charId, name, newCharacter, player, phantom? }` |
| `whip_core:player:loaded` | C | ped in world, picture back, controls given | same table |
| `whip_core:player:spawned` | C | put into the world (every load, and again when the creator closes) | `{}` |
| `whip_core:player:logout` | S | logout or disconnect, after the save | `{ source, charId, player, why = 'logout'\|'disconnect' }` |
| `whip_core:player:logout` | C | local player starting logout to char select | `{ charId }` |
| `whip_core:character:created` | S | new character row made | `{ source, charId }` |
| `whip_core:character:deleted` | S | character deleted | `{ source, charId }` (verify with `IsCharacterDeleted`) |
| `whip_core:character:renamed` | S | admin rename (Player Manager), online or not | `{ charId, source?, firstName, lastName, name, oldName, by }` |
| `whip_core:player:renamed` | C | local player renamed; sheet already updated | `{ charId, firstName, lastName, name }` |
| `whip_core:flag:changed` | S | a flag changed | `{ source, charId, name, value, was }` |
| `whip_core:appearance:modelChanged` | C | ped rebuilt with a new model (default walk/face) | `{}` |
| `whip_core:permission:changed` | C | account given/lost a permission | `{ permission, granted }` |
| death/revive/screen events | S/C | see Death | |

`player:loaded` is not resent when your resource restarts. Set up already-loaded players in `Whip.register` (make setup idempotent):
```lua
AddEventHandler('whip_core:player:loaded', function(e) setUp(e.source, e.player) end)
Whip.register(function()
    for source, player in pairs(exports.whip_core:GetPlayers()) do setUp(source, player) end
end)
```
`phantom = true` marks whip_test load-test players (no character in the world).

## Save system

You write no save code. Changes apply in memory at once and reach the DB in write-behind batches.
- One player action saves as one transaction: a SecureEvent/SecureCallback handler, a use handler, item action, `onComplete`, panel hook, `AddAction` callback. Use `StoreMove(fromAddr, toAddr)` for moves between players (RemoveItem+AddItem can be two saves). Your own DB writes join via `CommitWithAction`; before a plain oxmysql write, call `SavePlayer(source)`.

| What | When written |
|---|---|
| Pockets, stashes, boots, health and armour, activity log | within `Config.FlushInterval` (1000 ms) or when the action ends; both halves of a move together |
| Position, hunger, thirst, your persisted stats | every `Config.PlayerPositionSaveInterval` (30 s, min 5 s) if changed; position only if moved > `Config.PlayerPositionEpsilon` (2.0 m) |
| Car stats and position | every `Config.VehicleStatsSaveInterval` (15 s) or with the action |
| Car data, bank, ground items | immediately, with the running action's saves |
| Logout / disconnect | at once; next login waits for anything still owed |
| `restart whip_core` | every owed write sent as it stops |
| txAdmin restart/shutdown | on txAdmin's warning, most important first; set Shutdown Notice Delay to 15 s |

- A failed write is not a failed action: it retries forever (backoff); after 5 failures it shows as stuck in `/whipsaves`, and that character cannot load until it lands. DB gone: items lock until everything owed is written ("BACK TO NORMAL" in console).
- DB columns: `characters` has `health` (SMALLINT, default 200), `armour` (TINYINT), `isDead`, `statuses` JSON (persisted need/custom stats), `metadata` JSON; there is NO cash column (cash is `character_inventory` items).
- Health/armour are what the player's game last reported (as on QBCore/ESX); only a report of 0 health is verified against the ped. To sell armour, give it with `SetStat` after payment and keep your own record. Hunger, thirst and registered stats are server-only.

## Stats: built-ins and config

Stats live on the server; the client follows. Exception: combat damage (the hurt player's game reports health/armour; the server accepts it).

| Stat | Type | Range | Default | Persist | Behaviour |
|---|---|---|---|---|---|
| `health` | vital | 0-200 | 200 | yes (column) | synced to ped; 100 = GTA dead value; ring green `#34d399`, heartbeat |
| `armour` | vital | 0-100 | 0 | yes (column) | synced to ped; ring `#818cf8`, cracked shield `iconCritical`, `hideWhenEmpty` |
| `hunger` | need | 0-100 | 100 | yes (`statuses`) | decays `-100/(HungerMinutes*6)` every 10 s (120 min → -0.1389); at <= 10 each decay tick costs `Config.NeedDamage` (1) health; ring `#fb923c` |
| `thirst` | need | 0-100 | 100 | yes | `-100/(ThirstMinutes*6)` every 10 s (90 min → -0.1852); same threshold; ring `#38bdf8` |
| `oxygen` | custom | 0-100 | 100 | no | server tick: under water drains `100/OxygenSeconds` per s; above water refills `OxygenRecoverPerSecond` per s; at 0 (after grace) the game drowns them; ring `#22d3ee`, `showBelowFull`, `heartbeat`, `glide` |
| `developer` | custom | 0-1 | 0 | no | developer-mode HUD mark (`#fbbf24`, `showAboveZero`, `noCritical`); only developer mode can set it (`SetStat` refused) |

Config keys (`config.lua` section 4 and 12):

| Key | Default | Meaning |
|---|---|---|
| `Config.Hunger` / `Config.Thirst` | `true` | off: still registered (food works), no gauge, no drain, no damage, not saved, reads 100; turning off live resets everyone to 100 |
| `Config.HungerMinutes` / `Config.ThirstMinutes` | 120 / 90 | full to empty; damage starts at 10% (~1 h 48 min / 1 h 21 min after full) |
| `Config.NeedDamage` | 1 | health lost per 10 s tick at <= 10; 0 = never hurts |
| `Config.StatOrder` | `{ 'health','armour','hunger','thirst','oxygen' }` | gauge order left to right; unlisted stats after |
| `Config.StatHitFlash` | `{ health = 10, armour = 10 }` | display-% drop that pushes the gauge back on screen while chat/notification has the capsule (`interruptDelta`) |
| `Config.OxygenSeconds` | 20 | breath from full, clamped 1-45 |
| `Config.OxygenRecoverPerSecond` | 6 | clamped 0.5-100 |
| `Config.OxygenGraceSeconds` | 1 | at 0 breath before drowning; clamped 0-10 (client) |
| `Config.Stats` | `{}` | server's own stats registered at start (same fields as `RegisterStat`); a name clashing with a built-in is ignored |
| `Config.StatsTickInterval` | 1 | s between server stat ticks |
| `Config.StatsSyncInterval` | 5 | s between full stat syncs to each client |
| `Config.StatsSetGuardWindow` | 2 | s after a scripted health/armour set in which a reported 0 is ignored |
| `Config.Sentinel.damageModifierClamp` | `{ min = 0.05, max = 4.0 }` | range for combined damage modifiers |

Also editable in `/whip` → Settings → Config → "Hunger, thirst and breath" / Stats (gauge drag order). Changes re-register live.

## Stats: server API

### RegisterStat(name, config) — SERVER
Registers a stat owned by your resource. Config is copied. Declare in `Whip.register`; dropped when your resource stops (values stay in the cache and in `statuses`). Same definition again = no-op; a changed one replaces it (HUD rebroadcast). A stat registered after players loaded starts them at their stored value (if persist) else default.

| Field | Type | Default | Meaning |
|---|---|---|---|
| `type` | string | `'custom'` | `'need'` or `'custom'`; `'vital'` is WHIP's only; anything else refused |
| `default` | number | 0 | starting value |
| `min` / `max` | number | 0 / 100 | clamp range for every write |
| `persist` | boolean | `true` | saved in `statuses`; `false`: neither saved nor loaded (starts at default each login) |
| `decay` | number | none | added every `decayInterval`; negative drains; `0` = none |
| `decayInterval` | number | 10 | seconds |
| `thresholds` | table[] | none | `{ stat, delta, value, below }`: on each decay tick of THIS stat, if value `<= value` (`below = true`) or `>= value`, add `delta` to `stat` (skipped if that stat is already at its min). Only fire on stats that decay. Each entry needs `stat` string, numeric `delta` and `value` else refused |
| `hud` | table | none | ring config (see HUD framework) |

Returns `true` or `false, err`: `'a stat needs a name'`, `'stat "x": expected a config table'`, `'stat "x" is owned by whip_core'` (health, armour, oxygen, developer), `"stat \"x\": type is 'need' or 'custom', not \"y\""`, threshold error, or the registry's "owned by another resource" refusal. Refusals are also printed.
```lua
Whip.register(function()
    Whip.core:RegisterStat('stress', {
        type = 'custom', default = 0, min = 0, max = 100, persist = true,
        decay = -0.5, decayInterval = 15,
        hud = { icon = 'M12 2C6.48 2 2 6.48 2 12...', color = '#e879f9', order = 5 },
    })
end)
```

### GetStat(source, name) / GetStats(source) — SERVER
From the server cache (reported combat damage included, so `health` is current). `GetStat`: `number|nil` (nil when not loaded or unknown). `GetStats`: a copy `{ health = 200, hunger = 74, ... }` or `{}, 'Player not loaded'`.

### SetStat(source, name, value, reason?) — SERVER
Sets, clamped to range; client gets it at once; persisted stats queued. Vitals are applied to the ped by the client; re-setting a vital to its current value is still sent (corrects drift), but not announced.
- `reason`: shown in the debug change log and passed to `OnStatChanged` (truncated to 80 chars); default `'by <your resource>'`.
- Returns `true` or `false`: `'Player not loaded'`, `'no stat named "x" (RegisterStat it first)'`, `'value must be a number'` (NaN/inf too), `'the developer stat follows developer mode (/w) and nothing else'`.

### AddStat(source, name, delta, reason?) — SERVER
`current (or default if unset) + delta`, then as `SetStat`. For `health`/`armour` the client adds `delta` to the ped's LIVE value (the server cache trails the ped), and a positive health delta never lifts a dead ped. Extra failure: `'amount must be a number'`.
```lua
-- consumable use handler: refusal keeps the item
Whip.core:RegisterUseHandler('mycafe_sandwich', function(source, player, slotData)
    local ok, why = exports.whip_core:AddStat(source, 'hunger', 25, 'item:sandwich')
    if not ok then return false, why end
    return true
end)
```

### OnStatChanged(name, callback, id?, opts?) — SERVER
Called for any player's change by any path (decay, items, effects, combat damage via the vitals report, other resources).
- `name`: stat or `'*'`.
- `callback`: `(source, value, old, reason)`; for `'*'`: `(source, name, value, old, reason)`; with `opts.table`: one table `{ source, key, value, old, reason }` (prefer this: positional orders differ between `OnStatChanged`, `OnVehicleStatChanged`, `OnVehicleDataChanged`).
- `reason` examples: `'decay'`, `'item:food'`, `'combat (reported): Pistol'`, `'by my_resource'`, `'threshold:hunger'`, `'under water'`, `'breathing'`, `'killed (reported): ...'`, `'death'`, `'revive'`, `'respawn'`, `'revive:admin'`, `'settings'`, `'now'`.
- `id`: only to keep two listeners on one stat (key `<resource>:<id or name>`); a table passed as `id` with no `opts` is treated as `opts`.
- `opts.now`: also called once (in a new thread, after the `true` return) for every loaded player with the stat (`old = nil`, `reason = 'now'`); for `'*'` every stat of every player.
- Re-registering same key replaces; cleared on resource stop. Not re-entered: a listener that sets the stat it listens to does not get called for that nested change (the value still lands).
- Returns `true` or `false, "name is required (a stat name, or '*')" | 'callback is required'`.

## Stats: client API (read-only)

### GetStat(name) / GetStats() — CLIENT
From the client cache (bulk sync on login and every 5 s, plus per-change updates). `GetStat`: `number|nil` (nil if never synced). `GetStats`: a copy of all (vitals included).

### OnStatChanged(name, callback, id?, opts?) — CLIENT
Local player only. `callback(value, old)`; `'*'`: `(name, value, old)`; `opts.table`: `{ key, value, old }`. `old` is `nil` for the first value after login. `opts.now`: called once at once with the current value (`old = nil`). Same keying/replace/stop rules as the server. Returns `true` or `false, reason`.
```lua
Whip.register(function()
    Whip.core:OnStatChanged('drunk', setWalk, nil, { now = true })
end)
```

### HasEffect(name) / GetEffects() — CLIENT
Active effects on the local player: `GetEffects()` → `{ [name] = { duration, remaining, magnitude, tickRate, damageModifier, meleeModifier, resource } }` (`remaining` refreshed by the 5 s sync).

## Effects and damage modifiers

### ApplyEffect(source, name, config) — SERVER
A timed effect that runs your callbacks and removes itself when `duration` runs out. It moves no stat by itself.

| Field | Type | Default | Meaning |
|---|---|---|---|
| `duration` | number? | nil | seconds (positive); `nil` = until `RemoveEffect` |
| `magnitude` | number? | 1 | any number your callbacks read |
| `tickRate` | number? | 1 | seconds between `onTick` (positive) |
| `onTick` / `onApply` / `onRemove` | function? | | `(source, player, effect)`; `player` is the handler sheet (or light sheet), `effect` is the plain view plus `name` (and `reason` on logout/disconnect `onRemove`) |
| `damageModifier` / `meleeModifier` | number? | | incoming damage multiplier (positive): 0.5 half, 2.0 double |
| `replaceSilently` | boolean? | false | when replacing an active effect of this name, skip the old one's `onRemove` |
| `sheet` | `'light'`? | | callbacks get the light sheet (cheaper than the full sheet each tick) |

- Ownership is always the caller (a `resource` field is ignored). Stopping your resource removes your effects **without** `onRemove`.
- Nothing stacks: same name replaces (old `onRemove` runs first unless `replaceSilently`). To stack, read `GetEffects` and apply the sum. `stackable` is refused: `"'stackable' is now 'replaceSilently' — effects never stacked; a re-apply replaces"`.
- While dead and during the 10 s spawn guard `onTick` is held back, but `remaining` keeps counting down (dying does not extend an effect). A late wake fires at most 4 missed ticks.
- `onRemove` also runs on logout/disconnect before the save (`effect.reason = 'logout'|'disconnect'`).
- Callback errors are reported once per effect/callback/error under your resource (`GetErrorLog`).
- Returns `true` or `false`: `'an effect needs a name'`, `'an effect needs a config table'`, `'Player not loaded'`, `'duration must be a positive number of seconds, or nil'`, `'tickRate must be a positive number of seconds'`, `'magnitude must be a number'`, `'damageModifier must be a positive number'`, `'meleeModifier must be a positive number'`, `"sheet is 'light' or left out"`.
```lua
exports.whip_core:ApplyEffect(source, 'healing', {
    duration = 10, magnitude = 5, tickRate = 1,
    onTick = function(src, player, effect) exports.whip_core:AddStat(src, 'health', effect.magnitude) end,
    onRemove = function(src) exports.whip_core:NotifyPlayer(src, 'Healed!', 'success') end,
})
```

### RemoveEffect(source, name) — SERVER
Any resource may remove any effect. Runs `onRemove`, re-syncs modifiers, tells the client. Returns `true` or `false, 'Player not loaded' | 'no effect named "x" on this player'`.

### HasEffect(source, name) / GetEffects(source) — SERVER
`boolean` / `{ [name] = { duration, remaining, magnitude, tickRate, damageModifier, meleeModifier, resource } }` (`{}` when none or not loaded). No callbacks.

### GetDamageModifier(source) / GetMeleeModifier(source) — SERVER
Product of all active effects' `damageModifier` (or `meleeModifier`), clamped to `Config.Sentinel.damageModifierClamp` (0.05-4.0). `1.0` when none.
```lua
exports.whip_core:AddStat(source, 'health', -25 * exports.whip_core:GetDamageModifier(source))
```
How modifiers apply: the combined value is written to the player's statebag `whipDamageMod` / `whipMeleeMod` (absent when exactly 1.0, written through the Sentinel). Each ATTACKER's client sets its outgoing modifier (`SetPlayerWeaponDamageModifier` / `SetPlayerMeleeWeaponDamageModifier`) to the target's bag value while free-aiming or locked on at that player (or a vehicle's driver), or in melee with them; it re-reads every 50 ms when busy, 150 ms otherwise. **Hip fire without aiming does full damage.** Different effect names multiply (0.5 × 0.5 = 0.25; 0.5 × 2.0 = 1.0). WHIP's `damage_reducer` item is the reference (`server/items/damage_reducer.lua`).

## Stat tick internals (`server/stats.lua`)

- One server thread every `StatsTickInterval` (1 s) for all players. Skipped for a player with nothing to do (no decaying stat, no effects, breath full on land).
- Dead players: no decay, no thresholds, no oxygen; only the effect clock advances (no `onTick`).
- Decay advances by whole intervals; a decay far behind (> 2 intervals: first tick, after death) restarts rather than catching up.
- Thresholds fire only on a pass where their stat decayed; skipped during the 10 s spawn guard (respawn, revive, login). Decay still runs in the guard.
- Combat damage path: the client polls the ped every 200 ms and sends `whip_core:server:reportVitals(health, armour, context, under)` on change (rate 150 ms, burst 3). The server writes the cache directly, logs `combat (reported): <context>`, marks the row, and announces to `OnStatChanged`. A reported 0 within the guard window after a scripted set is ignored; an accepted 0 is a death only if, 1 s later, the server's ped also reads <= 100 health.
- Health loss caused by WHIP (thresholds, effects, scripts) is labelled for the death report: `threshold:hunger` → `'Starvation'`, `threshold:thirst` → `'Dehydration'`, anything else its reason.
- Change log: last 20 changes per player (debug panel shows 10).
- Player Stats Debug (`/w` debug panel, needs `whip.devtools`): live values, effects, decay rates, change log, ped health/armour, and cards over nearby players (40 m, 8 max). Hit causes there are REPORTED by the victim's own game: never decide anything from them; use `killer` on `whip_core:player:died`.
- The client disables GTA health regen on load (`SetPlayerHealthRechargeMultiplier 0`).

## HUD framework

Every status ring is drawn from a stat's `hud` block; no HTML/CSS/JS needed. A ring appears on every player's HUD when `RegisterStat` returns and goes when your resource stops. Below 20% the arc and icon turn red (unless `noCritical`); at 0% the ring ghosts (faded track, dim icon).

| `hud` field | Type | Req | Meaning |
|---|---|---|---|
| `icon` | string | yes | SVG path `d`, 24×24 viewBox (Material Design Icons, Lucide, Heroicons) |
| `color` | string | yes | hex arc colour; glow/haze derived |
| `order` | number | no | default 99; lower = further left, placed after stats listed in `Config.StatOrder`; placing the stat on the settings page wins. Sort key = index in StatOrder, else `1000 + order`, ties by name |
| `heartbeat` | boolean | no | icon heartbeat when critical (<20%) |
| `iconCritical` | string | no | alternate paths, pipe-delimited: first is the fill, the rest stroke lines (armour's crack) |
| `hideWhenEmpty` | boolean | no | fade to 25% opacity at 0 instead of empty ring |
| `noCritical` | boolean | no | no red warning below 20% |
| `showAboveZero` | boolean | no | hidden at 0, slides in above it |
| `showBelowFull` | boolean | no | hidden while full, slides in below full |
| `glide` | boolean | no | glides between readings (stats moved once a tick); off for stats that should snap |
| `interruptDelta` | number | no | code only: display-% move that brings the gauge back on screen while the capsule is busy (`server/stats.lua:162`) |
| `showWhenPresent` | boolean | no | vehicle stats only (not player stats) |

Other HUD facts:
- A voice gauge (`#a78bfa`, order 0, `noCritical`) is always prepended client-side; level from `GetVoiceLevel`.
- HUD hidden while dead or while a full screen is open (`IsAnyScreenOpen(true)`; screens opened with `keepHud`, and progress bars, keep it).
- `Config.HudSkin`: `'black'` (default: black discs in a draining white rim, no capsule; dark minimap tiles; blue waypoint/GPS) or `'classic'` (discs filling white inside the capsule). `Config.HudDeveloperMark` (true) shows the developer gauge in developer mode. `Config.MinimapMask`, `Config.MapOptions.onFoot/.inVehicle` (`'on'|'off'|'player'`) control the minimap (player prefs default: on foot off, in vehicle on). The minimap shown is WHIP's own; GTA's radar only in `/radardebug`.
- `SetScreenArea(area, key?)` — CLIENT: tell WHIP where your UI sits in the HUD corner so the vehicle dial moves/fades: `area = { left, top, right, bottom }` fractions 0-1 (`right > left`, `bottom > top`), `nil`/`false` removes; `key` default `'default'`; keyed by resource, released on stop. Hides nothing, takes no keys (use `SetScreenOpen`). Returns `true` or `false, why`.

Drunk example (server registers a stat with `persist = false, decay = -1, decayInterval = 2, hud = { ..., noCritical = true, showAboveZero = true }`, a timed use handler `onComplete` does `AddStat(source, 'drunk', 20, 'item:alcohol')`; client maps tiers to `SetWalkOverride` clipsets via `OnStatChanged('drunk', fn, nil, { now = true })` and resets on `whip_core:player:logout`).

## Death and respawn

WHIP handles death itself:
- Death detected client-side; client reports `whip_core:server:playerDied(killingBlow)` (string ≤ 120). Server verifies the ped health <= 100 (retries every 250 ms up to 2 s), else rejects. The vitals stream reporting 0 is a second path. Both funnel into `MarkPlayerDead`: `isDead = true`, `diedAt` stamped, holder releases any escort, `health` set to 100 and `armour` 0 (reason `'killed (reported): ...'` or `'death'`), statebag `whipDead = true`, activity log ("killed by Name (#id)" from `GetPedSourceOfDeath`, a vehicle counts as its driver; plus "reported: ..."), console line, core hooks, then server `whip_core:player:died`.
- While dead: they lie where they fell, take no more damage; all controls off except camera toggle V (0), look (1, 2), chat T (245), push-to-talk N (249) and E (38); others can still escort them; needs stop draining, low needs cost nothing, effects stop ticking; `health` reads 100, `armour` 0; HUD hidden; leaving does not end it (they reload dead, where they fell, no spawn picker).
- Dead in a vehicle: slumped, car still drivable; taken out, body falls; revive in a seat keeps them seated; respawn takes them out.
- Death screen: counts down `Config.RespawnTime` (10 s), then "Hold E to respawn" (A on pad); hold 1.5 s. H (Y on pad) hides/shows the screen; respawning requires it shown. Theme var `--ui-death-curtain`. `Config.DeathScreen = false` → draw your own from `whip_core:death:screenChanged`; WHIP still counts and reads E.
- Respawn: client teleports to a random `Config.RespawnLocations` vector4 (fallback Pillbox Hill `360.83, -585.28, 28.83, 250.38`) and sends `whip_core:server:playerRespawned`. Server refuses (client lies back down, `whip_core:client:respawnRefused`) if a respawn hold exists or less than `RespawnTime*1000 - 1000` ms passed since `diedAt`. Accepted: releases any escort holding them, `MarkPlayerAlive(..., 'respawn')`.
- `MarkPlayerAlive` (every revive and respawn): `isDead = false`, `lifeGen++` (stale death confirmations stand down), all respawn holds dropped, health 200, armour 0, full oxygen, 10 s spawn guard, `whipDead = false`, then (only if they were dead) core hooks and server `whip_core:player:revived { source, charId, how, reason }`.
- Admin: `/whip_revive <charId>` (console, or in game with `whip.devtools`), `/whip_reviveme` (in game, `whip.devtools`), `/w` Restore and the object viewer. Reasons `'revive:admin'`, `'revive:self'`.
- Default respawn hospitals: Pillbox Hill, Central Los Santos (`341.54, -1395.75, 32.51`), Mount Zonah (`-449.10, -333.17, 34.50`).

## Death exports and events

### HoldRespawn(source, key, label?) · ReleaseRespawn(source, key?) · GetRespawnHold(source) — SERVER
Keep a dead player from respawning while your resource comes for them (EMS call). Respawn refused until every hold is gone: released, a revive, logout/disconnect, or the holding resource stopping. Holds are per death.
- `key`: names your hold (same key again changes its words). Code defaults it to `'hold'` when nil.
- `label`: replaces "Hold E to respawn", max 80 chars (newlines/tabs become spaces); default `'Help is on the way'`. With several holds the screen shows the first by key order.
- `HoldRespawn` returns `true`, or `false, 'no such player' | 'they are not dead'`.
- `ReleaseRespawn(source, key)`: `true` when a hold went; without `key`, releases every hold of yours on them.
- `GetRespawnHold(source)`: the label shown, or `nil`.
```lua
local ok, why = exports.whip_core:HoldRespawn(patient, 'call', 'A medic is on the way')
exports.whip_core:ReleaseRespawn(patient, 'call')  -- they can respawn once the usual wait is over
```

### RevivePlayer(source, reason?) — SERVER
Revive where they lie (as `/w` Restore): server record first, then the client stands the ped up. Full health, no armour. `reason` goes after `'revive:'` (default the calling resource). Returns `true` or `false, 'Player not loaded' | 'not down'`.

### Checking death
- Client local: `exports.whip_core:IsPlayerDead()`. Server: `IsPlayerDead(source)` or `GetPlayer(source).isDead`. Any client, any player: `Player(serverId).state.whipDead`.

### Death events
| Event | Side | Payload |
|---|---|---|
| `whip_core:player:died` | S | `{ source, charId, killer, reported }`: `killer` = server id the server saw do it (a car's driver counts) or nil; `reported` = victim's own game's text, display only |
| `whip_core:player:revived` | S | `{ source, charId, how = 'revived'\|'respawned', reason = 'revive'\|'respawn'\|'revive:admin'\|'revive:self'\|'revive:<resource or reason>' }` |
| `whip_core:player:died` | C | `{ reconnected, respawnRefused }` (`reconnected`: loaded in dead; `respawnRefused`: same death again after a refused respawn) |
| `whip_core:player:revived` | C | `{ how }` |
| `whip_core:death:screenChanged` | C | one of `{ state = 'count', left, total }` · `{ state = 'ready', progress (0-100), key }` · `{ state = 'held', label }` · `{ state = 'off' }` · `{ hidden }` |

Console/Stats log death line: `[whip_core] John [3] has died — reported: Carbine Rifle by Jane (#5) (charId: 12)`. Hunger/thirst deaths read `Starvation`/`Dehydration`; health a script/effect took reads as its reason. **Never pay out on these events alone**: any server resource can fire `whip_core:player:died` / `:revived`.

## Escort

Left Arrow (`escort_grab`, key mapping 'Escort Player') grabs the nearest player within 3 m who is not in a vehicle and not already escorted (alive or dead); Right Arrow (`escort_release`) releases. The escorted player is attached beside the holder; only their movement is off (they can look, open inventory, chat).

Server rules (`server/events_misc.lua:461`): target online, not self, not already escorted (Sentinel ledger, not the client-writable bag), holder not escorting and not escorted, target not escorting anyone, target not in a vehicle, within 3 m and same routing bucket. Failures: `'Player not found'`, `'Cannot escort yourself'`, `'Player is already being escorted'`, `'Already escorting someone'`, `'You are being escorted'`, `'They are escorting someone'`, `'Player is in a vehicle'`, `'Too far away'`.

Breaks when: either ragdolls, either disconnects or logs out, the holder dies, horizontal distance > 10 m, the escorted player respawns, or the holder seats them in a vehicle (seat must be free, car within 7 m and unlocked). Pull from a vehicle (within 5 m, car not locked) starts an escort after 800 ms.

### IsEscorting() · IsBeingEscorted() · GetEscortTarget() — CLIENT
`boolean` · `boolean` · `number|nil` (escorted player's server id). The controls use WHIP's own network messages; they are not an API. Any player: statebags `whipEscorted` (boolean) and `whipEscortedBy` (holder's server id).

## Hands (BlockHands)

Server (`server/hands.lua`), keyed `<resource>:<source>:<id>`, gone at logout/drop or when your resource stops:
- `BlockHands(source, id, opts?)` — SERVER: `opts = { label?, only? = 'weapons' }`. Everything (hands emptied, `FreeHands` false) or weapons only. Default labels `'Your hands are busy'` / `'You cannot use a weapon here'`. Every block stops a draw and holsters a gun. Returns `true` or `false, why` (`'No player with that server id is online'`, `'a hands block needs an id'`, `"only is 'weapons', or nothing for everything"`, `'label is the words the player is shown'`).
- `UnblockHands(source, id)` — SERVER: `true` or `false, why`.
- `AreHandsBlocked(source, what?)` — SERVER: `what = 'weapon'` (any block) or nil (only blocks of everything). Returns `true, label` or `false`. Server's own blocks only.
- `FreeHands(source)` — SERVER: asks their game to empty the hands now; `true` or `false, why`.
- Client: `BlockHands(id, opts)`, `UnblockHands(id)`, `AreHandsBlocked(what)` (this game's and the server's), `FreeHands()` (WAITS; `false, words` while blocked). Client events `whip_core:hands:blocked { only, ... }` / `whip_core:hands:unblocked {}`.

## Statebags (`shared/statebags.lua`)

Player bags (written only by the server through the Sentinel; client tampering is reverted and logged, `Config.Sentinel.autoKick` 3 strikes):
| Key | Value |
|---|---|
| `whipDead` | boolean |
| `whipJob` | job key string, or `false` off duty |
| `whipEscorted` | boolean |
| `whipEscortedBy` | holder's server id or nil |
| `whipDamageMod` / `whipMeleeMod` | number, absent when exactly 1.0 |
| `whipMood` | `/mood` name or absent |
Names and charIds are deliberately NOT on bags.

## Player Manager (admin)

`/whip` → Players → Player Manager; needs `whip.devtools` (re-checked server-side per action). Lists the 1,000 most recently seen accounts; filter All/Online/Banned; search by player name, licence or character name.
- Player page: Profile (identifiers, characters, vehicles, jobs, position/current vehicle), Current Stats (online; every stat, type a value and Apply, clamped and console-logged; health in game units: empty 100, full 200), Vehicles, Their game (online: screenshot of WHIP screens + map position; pictures kept 5 min, each logged), Teleport To / Bring Here, Open Inventory (online or offline, asks which character), Kick (reason, adds admin note), Temp/Perma Ban, Unban, Admin Notes, Activity (30 rows a page, items link to the Item Log), Give Dev Tools.
- One licence on two clients shows two rows; `Config.PlayerManagerSessionWarn` (false) adds "2 SESSIONS" and "ALSO IN".
- Bans checked on connect against every identifier. Rank rules: nobody kicks/bans their own rank or above or lifts a ban placed by someone above them; server.cfg admins cannot be kicked/banned from the panel, nor can accounts sharing any identifier with one; panel-granted dev tools holders can be kicked/banned only by a server.cfg admin (a ban removes the tools); a ban by a server.cfg admin (or with no placer) is lifted only by one. Temp bans expire by themselves; time zone is the server's.
- Give Dev Tools: adds the licence to ACE group `group.whip_devtools` until restart (runtime principals are not saved). Only permanent admins can grant; each grant writes an admin note; temp admins cannot grant saved rights. server.cfg needs:
```
add_ace group.whip_devtools whip.devtools allow
add_ace group.whip_devtools command.w allow
add_ace resource.whip_core command.add_principal allow
add_ace resource.whip_core command.remove_principal allow
```
- Character rename (admin) changes the name only (charId and everything keyed by it stay); fires `whip_core:character:renamed`.
- Reveal Players (`/w` tool, `server/dev_players.lua`): once a second sends every loaded player's `{ s, c, n, a, x, y, z, h }` (server id, charId, character name, account name, position, heading) to admins with it on (developer mode required).

## Gotchas

1. `GetPlayer` returns `nil` until the character is fully loaded, and only for online players. Do not cache sheets; they are copies and go stale.
2. A bare number is always a server id. `{ charId = n }` for characters. `SetPlayerMetadata(12, ...)` targets server id 12, not charId 12.
3. The handler sheet given to SecureEvent/use-handler/effect callbacks has no `metadata`; call `GetPlayer(source)`.
4. `whip_core:player:loaded` is not replayed for your resource after a restart; iterate `GetPlayers()` in `Whip.register`.
5. `whip_core:character:deleted`, `whip_core:player:died` and `:revived` can be fired by any server resource: verify with `IsCharacterDeleted` and never pay out on death/revive events alone.
6. After any long wait (DB, `Wait`, progress bar) check `IsSessionCurrent(source, player.session)` before giving or taking.
7. `newCharacter` is only true on the first load after creation; a gift tied to it can be farmed by delete/recreate (tie to `userId`).
8. Metadata and flags are sent to the owning client: no secrets. WHIP's metadata keys are refused by `SetPlayerMetadata`.
9. Flags work only while the character is online; `GetPlayerFlag` returns `nil` (not an error) for offline characters.
10. `RegisterStat` with `persist = false` neither saves nor loads; with `persist = true` (the default) the value survives logins. `type` must be `'need'` or `'custom'`.
11. Thresholds only run on stats that `decay`, and only on the tick where that stat decayed; they are skipped during the 10 s spawn guard and while dead.
12. `AddStat(source, 'health', n)` changes the ped by `n` relative to its live value; `SetStat` sets an absolute value. Use `AddStat` for heals so recent combat damage is not undone.
13. Effects never stack; a same-name `ApplyEffect` replaces (and runs the old `onRemove` unless `replaceSilently`). Your effects are removed silently (no `onRemove`) when your resource stops.
14. Damage modifiers only apply when the attacker aims at (or melees) the player; hip fire does full damage. The combined value is clamped to 0.05-4.0.
15. Health and armour are client-reported; only a 0-health report is verified. Do not treat them as proof (selling armour: set it after payment).
16. Hit causes in the stats log and `reported` on death events come from the victim's game: display only. Use `killer`.
17. `HoldRespawn` only works on a dead player and only lasts that death; re-hold on the next death.
18. Respawning earlier than `Config.RespawnTime - 1 s` after death is refused server-side (the client lies back down).
19. `GetPlayerFullName` on the client returns `nil` on the first call for a given player (it starts a fetch); pass `wait = true` in a thread or call again later.
20. `NotifyPlayer` duration is clamped to 500-30000 ms; text to 300 chars.
21. `LogoutPlayer` waits up to 2 s for in-flight handlers; logout/disconnect run `onRemove` and fire `whip_core:player:logout` after the save but before stats are cleared.
22. Changing `Config.Hunger`/`Thirst` to off resets everyone online to 100 and stops saving; turning it back on starts everyone full.
23. `GetCharacterNames` also returns deleted characters' names.

## Docs vs code

1. Built-in stats: docs list five (health, armour, hunger, thirst, oxygen); code has a sixth, `developer` (0-1, HUD developer mark, refused to `SetStat`), and it is a reserved name for `RegisterStat` (`server/stats.lua:27`, `:311`, `:628`).
2. `hud.interruptDelta` exists in code (`server/stats.lua:162`, `:218`) but is not in the docs' ring field table.
3. `HoldRespawn` key: docs and stub say `key` (string) is required; code defaults a nil key to `'hold'` (`server/events_misc.lua:91`).
4. `KickPlayer`: docs say it saves then drops; the export only calls `DropPlayer` (`server/player.lua:682`), and the save happens in the `playerDropped` handler.
5. New characters: guide says they start with `Config.StartingBalance` in the bank; code also gives `Config.DefaultCash` (500) as cash items in pocket slot 1 (`server/character.lua:258`).
6. `GetCharacterNames`: docs say unknown ids are left out; deleted characters are not filtered (`server/helpers.lua:380`).
7. `RegisterStat` refusal list in docs names health, armour, oxygen; code also refuses `developer` (`server/stats.lua:27`).
