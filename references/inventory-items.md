# Inventory and Items

Player pockets (slots, weight, accessory strip, hotbar), item definitions, icons, use handlers (plain and timed), right-click and ground options, item settings, retiring items, and every server and client inventory export. Built from doc anchors `#guide-inventory`, `#item-definitions`, `#inventory`, `#client-inventory` and verified against `whip_core/server/inventory.lua`, `inventory_sync.lua`, `item_options.lua`, `item_settings.lua`, `retired_items.lua`, `pending_gives.lua`, `hands.lua`, `timed_action.lua`, `held_props.lua`, `events_inventory.lua`, `server/items/*.lua`, `client/inventory.lua`, `client/hands.lua`, `client/item_settings.lua`, `client/main.lua`, `shared/inventory_shape.lua`, `shared/hands.lua`, `config.lua`, `docs/nui-inventory.md`, `types/*.lua`, `lib/satellite.lua`. Stores/addresses, ground piles, containers and panels: see `stores-containers-panels.md`.

## Contents
- Model: pockets, slots, weight, hotbar
- Accessory strip
- Give vs move, full inventory
- Stacking and metadata rules
- Persistence and DB
- Item definition (every field)
- Item icons and pictures
- Right-click options (contextOptions, when, require, anywhere)
- Ground options
- Using an item: the use pipeline
- Server exports: giving and taking
- Server exports: finding and reading
- Server exports: registering items
- Server exports: use handlers and options
- Server exports: item settings
- Server exports: retiring items
- Server exports: lookups, pockets, accessory strip
- Server exports: hands and held item
- Server exports: another player's pockets
- Client exports
- Events
- Built-in items (Config.Items)
- Config keys
- Replacing the inventory UI
- Gotchas
- Docs vs code

## Model: pockets, slots, weight, hotbar

| Pocket (container) | Slots (`Config.ContainerSlots`) | Max weight (`Config.MaxWeight`, kg) | Notes |
|---|---|---|---|
| `player` | 30 | 80.0 — covers everything carried, strip included | Main grid; items go here first |
| `accessory` | 5 | 10.0 — the strip's own limit, inside the 80 | Typed slots (see Accessory strip) |

- `PlayerContainers` (shared/inventory_shape.lua:16) = `{ 'player', 'accessory' }`, or `{ 'player' }` when `Config.AccessoryStrip == false`. Not a setting: the DB column is `ENUM('player','accessory')`. There is no backpack container; bags are items (`duffle_bag`).
- With the strip off, what a character had in it moves into `player` at login. `GetPockets()` gives the live list; read it inside `Whip.register` (strip setting applies at whip_core's next start).
- Hotbar = main-pocket slots 1-5. Number keys 1-5 (key mappings `hotbar_1`..`hotbar_5`) fire `whip_core:server:useItem('player', i)`; TAB (`+tabhotbar`) holds/taps the hotbar display. Client event `whip_core:hotbar:slotUsed { slot }` fires just before (client/inventory.lua:2832).
- Weight is nested: an item's `weight` is its empty weight per unit; contents (read through its `RegisterPanelItem` registration: `read(host)` hook, or the slot array at `metadata[storageKey or 'slots']`) are added at every level. Followed `MAX_WEIGHT_DEPTH = 4` levels (inventory.lua:536); a move into a bag that would nest deeper is refused. A `read` hook that throws reads as empty (item weighs its base weight). An item with no definition weighs 0. Contents are weighed once per stack, not per unit.
- Weight check on entry: the target pocket's own max AND the pockets' combined limit (`Config.MaxWeight.player`). Container weight is rounded to 0.01 kg (inventory.lua:629).
- Slots above a lowered `Config.ContainerSlots` stay in the cache but are unreachable: counts, takes and finds ignore them.
- `Config.WeightUnit` (`'kg'` default, or `'lb'`) only changes display; all weights in config and `RegisterItem` are kilograms.

## Accessory strip

Default slots (`AccessoryStripSlots`, shared/inventory_shape.lua):

| Slot | Label | Takes | Icon |
|---|---|---|---|
| 1 | Phone | anything (whip_phone replaces it to take phones only, and looks here first) | `phone` |
| 2 | Money | `cash`, `wallet` | `cash` |
| 3, 4, 5 | Key | any ignition key (`keys = true`) | `vehicle_key` |

- Enforced on the server on drags, `StoreMove` and `AddItem`. Refusal text: `"Only <Name> or <Name> can go there"` (plus `keys` for key slots; label when the slot lists nothing) (inventory.lua:706).
- `AddItem` overflow into the strip only lands in a slot whose rule takes the item. What a slot held before its rule changed stays until moved.
- Ignition keys: `vehicle_key`, `hacked_vehicle_key` are whip_core's (inventory.lua:1808); add more with `RegisterIgnitionKey`. A `vehicle_key` in the strip goes into the ignition when its holder takes the driver's seat of the car it fits, and back when they leave. Keys in `player` never move by themselves.
- The strip can't be set smaller than the highest seeded slot (/whip → Settings, Accessory Inventory Size).

## Give vs move, full inventory

| Operation | Meaning | When it won't fit |
|---|---|---|
| Give | Item enters the world (reward, purchase, refund, admin spawn): `AddItem`, `StoreGive`, `GiveOnLogin` | Dropped at the player's feet (`'ground'`), unless `Config.DropOnFullInventory = false` or `opts.noDrop`: then refused, nothing created |
| Move | Item already exists (pickup, stash transfer, drag, trade) | Left where it is. Never dropped (would duplicate) |

- A dropped give makes one ground pile per stack (`maxStack` per pile for stackables, 1 per pile otherwise); more than `Config.MaxGroundPilesPerDrop` (50) piles are shared out evenly. Piles spiral up to 0.35 m from the feet. All-or-nothing: a failed pile deletes the ones made (inventory_sync.lua:152).
- A dropped give notifies the player `"Inventory full — <name> dropped at your feet"` (warning), logs `'... · dropped at their feet'`, and does NOT fire `whip_core:item:added`.
- Cash exports (`PayPlayer` etc.) never drop: notes that won't fit are refused.

## Stacking and metadata rules

- Stacks only when `stack = true` and `maxStack > 1`. Adding tops up existing stacks of the same item (lowest slot first) whose metadata `stacksWith` the new metadata, then fills empty slots lowest first. Removing drains `PlayerContainers` in order, highest slot first within each.
- `stacksWith` (stores.lua:493): deep-equal metadata ignoring the top-level `uid` key; `nil` equals "only a uid". Different metadata never merges.
- The whole amount is proven to fit before anything changes; a refused add changes nothing.
- Metadata is any JSON-saveable table (`Inventory.saveableData`, inventory.lua:854): string/number/boolean values, vectors/quats, nested tables up to depth 16, keys string or number. Refused: functions, userdata, NaN, ±infinity, non-string/number keys. Refusal: `'metadata cannot be saved: <what>'`.
- Every slot write copies metadata (two slots never share a table). Copy depth limit 16.
- Metadata with a generator (`RegisterItemDefaultMetadata`): when a non-stacking (or multi-slot) give spans slots, the generator runs once per slot (each gun its own serial).
- Reserved/meaningful keys: `uid` (activity-log instance id, minted on first logged touch; ignored for stacking; kept by `SetItemMetadata` unless `uid = false`), `director` / `systest` (test-run stamps: such items may only move within the test's players' pockets and its cars/containers, and are taken back when the test ends or at next login; a live Director run stamps nothing), `slots` (default panel `storageKey`: a bag's/wallet's contents), `vehicleId`, `plate`, `model`, `token` (vehicle keys; `status` on hacked keys), `fuel` (0-100 on `fuelCapacity` items), `serial` (`SetHeldItem` tracks it).
- Item metadata is visible to the holder's game: never put secrets in it.

## Persistence and DB

- Table `character_inventory` (inventory.lua:27): PK `(charId, container, slot)`; `container ENUM('player','accessory')`, `slot SMALLINT UNSIGNED`, `item VARCHAR(50)`, `amount INT UNSIGNED`, `metadata JSON`, index `idx_inventory_item`, FK to `characters` ON DELETE CASCADE.
- Write-behind: changes are in memory at once and flushed within `Config.FlushInterval` (1000 ms). Only changed rows are written (none on the first save after a load); both halves of a move share one transaction. A `true` means "owed to disk": a hard crash can lose up to one interval.
- Durability per store kind: player inventories, containers and vehicle storage defer; ground items and shop stock write through; the bank writes immediately with what the running action saved. A move touching any write-through store commits immediately. Use `CommitWithAction` to put your own queries in the same transaction (see stores file).
- A load that fails returns `nil`, never an empty cache (an empty cache would delete every row on save).
- Unreadable `metadata` JSON in a row: the item loads without metadata and the console names the row.
- Items are locked while the database is down (`DbHealth.refusal()`): uses, context actions, gives refused with its message.
- Other tables: `pending_gives` (GiveOnLogin), `whip_item_holds` (hand positions), `whip_settings` / `whip_settings_log` (item settings). Item registrants persisted in resource KVP `whip_core:itemRegistrants` (5 s after the last change).

## Item definition (every field)

Fields of `RegisterItem(key, def)` and `Config.Items[key]` (`WhipItemDef`, types/classes.lua:136).

| Field | Type | Default / rule |
|---|---|---|
| `name` | string | REQUIRED, non-empty. Display name. Admin-editable |
| `desc` | string? | Tooltip text. Admin-editable |
| `weight` | number | REQUIRED, finite, ≥ 0, kg per unit. Numeric strings accepted and converted (`'0.5'` → 0.5). Admin-editable |
| `type` | string? | Category label shown on the tooltip (`'consumable'`, `'weapon'`, `'tool'`, ...) |
| `stack` | boolean? | Several share one slot |
| `maxStack` | number? | Not stacking: forced to 1; >1 with `stack` falsy is REFUSED. Stacking and unset: 100 (`REGISTERED_DEFAULT_MAX_STACK`). Given: whole number ≥1 (floored), not inf; `0`, `-3`, `'x'` refused. Config items with a contradiction are held to the fallback with a console warning |
| `usable` | boolean? | Usable from hotbar / Use. Without it players see "Item not usable" (falls back to `defaultAction`) |
| `cooldown` | number? | Seconds between uses, per player per item key (0 = none) |
| `prop` | string? | World model when dropped/thrown/held. Missing in game files → `Config.DefaultGroundProp` (`'prop_cs_cardbox_01'`) |
| `grab` | `'1h'`\|`'2h'`? | How it is picked up; default `'1h'`. Admin-editable (hand position editor) |
| `playerWalk` | boolean? | Held out to give/throw, the player keeps their own walk instead of `Config.GiveModeStyle`. Default false |
| `metaFields` | table[]? | Tooltip rows from metadata: `{ key, label, format?, value? }`; `value` shows when the key is missing; `format`: `'uppercase'`, `'percent'`, `'phone'` (html/js/core/inv-actions.js:926) |
| `fuelCapacity` | number? | Makes it a fuel can (read by whip_fuel): share of a car's 100 tank a full one holds (`30` = 30%). Metadata `fuel` 0-100 = how full. Held via `SetHeldItem`, whip_fuel fills it at pumps and refuels from it. whip_gunny's `jerry_can` is one |
| `defaultAction` | string? | Context action run on double-click; also what Use/hotbar does when the item is not `usable` |
| `contextOptions` | table[]? | See Right-click options |
| `groundOptions` | table[]? | See Ground options (max 3) |
| `image` | string? | Icon path in the owning resource, or `'@resource/path'` for another resource's. See icons |
| `images` | table[]? | Pictures by state (max 20). See icons |
| `pictureFields` | table[]? | `{ { key, label?, type? } }` (max 20); `type` `'bool'`\|`'number'`\|`'text'` (default text); key `^[%a_][%w_]*$`, ≤40, not `amount`. Fields an admin may show a picture by |
| `settings` | table[]? | Item's own admin settings (max 20). See Item settings |

- Key rule (`RegisterItem`): string, non-empty, ≤ 50 chars (VARCHAR(50)), pattern `^[%w_%-]+$` (letters, digits, `_`, `-`; no colon, no spaces). A key not starting with `<resource>` + one of `_ : . -` gets a console warning once per resource (not for `whip_*`). Convention: `myres_item`.
- An item registered with `RegisterPanelItem` cannot stack (`stack = true` refused, either order).
- `css` is also passed to the NUI payload (inventory.lua:1556), undocumented.
- Internal fields written onto the stored def: `_declared`, `_declaredImages`, `_fromServer` (client). Don't rely on them.

### Items in the wallet: wallet = true (1.3.0)
An item whose definition sets `wallet = true` (`RegisterItem('mybank_card', { ..., wallet = true })`) can go in the wallet, and counts as carried there: `HasItem`, `GetItemCount`, `FindItem`, `RemoveItem` (after the pockets), item requirements on prompts, points and doors, and the item events all look inside it. The wallet is a panel item registered with `allowedFlag = 'wallet'`. Cash in a wallet is put away, not counted.

## Item icons and pictures

Icon resolution (`Inventory.resolveItemImage`, inventory.lua:1431):
1. `image = '@<resource>/<path>'` (pattern `^@([%w_%-%.]+)/([%w_%-%./]+)$`, no `..`): `https://cfx-nui-<resource lowercased>/<path>`.
2. Item owned by whip_core: NUI built-in `img/items/<key>.png`, unless `html/img/items/<key>.webp` exists in whip_core.
3. Item owned by another resource: `def.image` (relative to the owning resource's root), else `html/img/items/<key>.webp`, else `<key>.png`, else the `.png` path anyway (NUI then tries whip_core's folder, then `missing.png`). URL uses the lowercased resource name (the scheme handler 404s on capitals).
4. Owner unknown (`GetInvokingResource()` nil at registration): no icon.

- WebP wins over PNG when both exist; prefer WebP (every player downloads every icon).
- **Pictures without drawing any:** WHIP's media pack `whip_media_props` (installed by the recipe in
  `resources/[assets]/[media]`) holds a 256 px render of about 14,600 GTA props at `img/props/<model>.webp`.
  An item can point at one: `image = '@whip_media_props/img/props/prop_ecola_can.webp'` (groceries: `prop_ld_can_01`,
  `prop_cs_milk_01`, `v_ret_247_noodle1`, `v_ret_247_bread1`, ...). Check the file exists first. The pictures are
  Rockstar's (the pack's NOTICE.md): reference them, do not copy them into a published resource.
- Required in your fxmanifest: `files { 'html/img/items/*.webp', 'html/img/items/*.png' }` (or the one you use). Without it the "missing" picture shows.
- Lookups are cached per resource; a resource (re)start clears its cache and tells clients (`whip_core:client:itemDefsStale`). A new picture shows after its resource restarts.

`images` (item_options.lua:319): list of `{ when?, amount?, image }`, at most 20; first passing entry is drawn, else the item's own; a missing file shows the item's own.
- `image` path: inside the owning resource, ≤200 chars, no `..`, no leading `/`, no `:` or `\`, chars `[%w_-./{}]`, ends `.png`/`.webp`/`.jpg`/`.jpeg`.
- `{field}` is filled from metadata (lowercased, letters/digits/`_`/`-` only); a missing field skips that picture. `{make}` = maker of the car named by metadata `model` (asked of the game client-side).
- `when`: same tests as options (below). `amount`: table of `above`, `below`, `atLeast`, `atMost` (numbers) on the slot's count. With no slot (a shop list, /whip Items), no `amount` picture fits: make the plain `image` suit any amount.
- Admins edit pictures on /whip → Economy → Items (`pictures` rows `{ image, field, op, value }`, op `is|above|below|atLeast|atMost|has|empty`, max 24; pasted links only from `Config.LorePictureLinks` sites, Fivemanage by default). Reset restores the definition's `images`.

## Right-click options (contextOptions)

Entry fields (item_options.lua:51, `cleanOption`):

| Field | Rule |
|---|---|
| `action` | REQUIRED string ≤ 32 chars; the `RegisterContextAction` key. Unique within the item |
| `label` | REQUIRED string ≤ 40 chars |
| `order` | finite number; lowest first, then options without one in listed order |
| `when` | metadata tests (below) |
| `whyNot` | string 1-80 chars: shown when `when` fails on double-click/hotbar. Default `"<label> isn't possible right now"` |
| `require` | player tests, AddAction's words: `alive`, `vehicle`, `job`, `onDuty`, `jobPermission`, `item`, `held`, `zone`, `charId`, `ace`. A `zone` must be a saved zone. Unreadable word → refused at registration |
| `anywhere` | boolean. Also offer the option when the item is in an open boot, glovebox, stash, bag, wallet or panel (not on the ground, in an ignition, or on a shop shelf). Handler `addr` is then that store's (`{ kind = 'vehicle', id, sub = 'trunk', slot }`), so handle any address |
| `icon` | accepted and dropped (menu draws words only) |

Any other field is refused with a "did you mean" hint (e.g. `text` → `label`, `priority` → `order`).

Menu layout: your options at the top under Use; Give, Place, Split, Destroy (developer mode only) below. Options show only while the item is in the player's pockets unless `anywhere`.

`when` tests (all must pass; one per metadata field name `^[%w_]+$` ≤ 50):
- `ammo = 0` — equal (number, text, boolean). `'5'` is text, not a number.
- `model = { 'adder', 't20' }` — one of (≤ 50 entries, literals only).
- `ammo = { above = 0 }` — also `below`, `atLeast`, `atMost` (finite numbers; several = all).
- `slots = { empty = false }` — empty is `nil`, `false`, `''`, `0`, or an empty table.
- `ammo = { below = 12, default = 0 }` — `default` stands in for a missing field; must sit beside another test.
- Unknown test words are refused at registration (with hints: `gt`→`above`, `min`→`atLeast`, ...).

The server re-checks `when` and `require` before running (`Inventory.optionAllowed`); the page only hides failing options. Failing option on double-click/hotbar → `whyNot` or `"<label> isn't possible right now"`.

## Ground options

`groundOptions = { { action, label, icon? } }` (item_options.lua:266):
- At most 3. `action` (≤ 32) must be one of the item's own options (a `contextOptions` action or `defaultAction`). `label` ≤ 24 chars, shown before the item name ("Equip Pump Shotgun"). `icon` = glyph name from `html/js/glyphs.js` (`^[%w_]+$`, ≤ 32); default Pick up's arrow. Only these three fields.
- Choosing it picks the pile up exactly as Pick up does, then runs the option on the slot it landed in with the usual checks; the handler gets `how = { from = 'ground' }`. A refusal leaves the item on the ground.

## Using an item: the use pipeline

`Inventory.useItem` (inventory.lua:1982), reached from hotbar (`whip_core:server:useItem`) and the menu's Use (`useItemFromMenu`), both pocket-only, rate limit 500 ms:
1. DB down → refusal message. Pockets frozen by a bank payment → `'Paying — wait a moment'`.
2. Empty slot → silent. Unknown item → `'Unknown item'`.
3. Not `usable` → runs `defaultAction` instead (checking that option's `when`/`require`; no handler → `"<name> can't be used right now"`).
4. Cooldown (`os.time()` seconds, per player per item key) → `'Item on cooldown'`.
5. No use handler registered (resource stopped) → `"<name> can't be used right now"`.
6. A second use of the same item while its handler still runs → silently refused.
7. Handler called through `Actions.call` with `(source, player, slotData, addr)`. `player` = live object for whip_core's own handlers, the data sheet (`player:handlerSheet()`, GetPlayer's table less `metadata`) for other resources. `addr = { kind = 'player', id = source, sub = pocket, slot }`.
8. Return value:

| Return | Result |
|---|---|
| `true`, nil, anything not `false` | One unit consumed; cooldown starts; `whip_core:item:used` fires; use logged |
| `false` | Kept; still a use: cooldown starts, event fires, logged |
| `false, 'why'` | Refused: kept, no cooldown, no event, not logged; player sees `why` (`''` = silent) |
| handler throws | `'Use failed'`, error filed under the owner (ErrorTap) |

9. Consumption takes from the stack used: if the handler yielded and the stack moved, it is followed by `metadata.uid`; if it left the player, nothing is taken (console warning).

## Server exports: giving and taking

All server exports are called as `exports.whip_core:Name(...)` or `Whip.core:Name(...)` from a satellite (`shared_script '@whip_core/lib/satellite.lua'`). WAITS = listed in `lib/satellite.lua`'s WAITS / `---@async`.

### AddItem(source, item, amount?, metadata?, opts?) — SERVER, WAITS
Gives an item: pockets in `PlayerContainers` order, else dropped at feet (see Give vs move).
- `source` number. `item` registered key. `amount` whole number ≥ 1 (default 1; numeric strings accepted). `metadata` table or nil (nil to skip and still pass opts).
- `opts`: a reason string, or `{ reason?, noDrop?, pocket?, coords? }` (`WhipAddItemOpts`): `reason` for the activity log (logged as `'<reason> · by <resource>'`); `noDrop = true` refuse instead of dropping; `pocket = 'player'|'accessory'` only that pocket; `coords` (vector3) where to drop if it doesn't fit.
- Returns `'inventory'` | `'ground'` | `false, reason`. Failure reasons: `'Unknown item "x"'`, `'Amount must be a whole number of 1 or more'`, `'Invalid pocket "x"'`, `'Player not loaded'`, `'metadata must be a table or nil — a reason goes fifth: AddItem(src, item, n, nil, reason)'`, `'metadata cannot be saved: ...'`, with `noDrop`/no-drop config: the add's reason (`'No empty slots'`, `'Too heavy'`), rarely no ped / failed drop.
- No metadata and a generator: generator runs with `ctx = { source, charId, reason = 'given' }`. A dropped give of at most one slot's worth gets its metadata made for the recipient; a bigger bare pile gets it per slot at pickup (for the finder).
- `'ground'` counts as given: `if not where then` never refunds an existing item. `whip_core:item:added` does not fire for a ground drop.
```lua
local where, err = exports.whip_core:AddItem(source, 'drink', 2, nil, 'quest reward')
if not where then print('nothing was given: ' .. err) end
exports.whip_core:AddItem(source, 'cash', 100, nil, { pocket = 'accessory', noDrop = true })
```

### RemoveItem(source, item, amount?, metadata?, opts?) — SERVER, WAITS
Takes from the pockets (in order, highest slot first). All or nothing.
- `metadata` table?: only stacks whose metadata carries every one of these values (`{ serial = 'AB12' }`). A non-table here is refused: `'metadata is a table or nil: the reason goes in opts (...)'`.
- `opts`: `{ reason }` or a reason string.
- Returns `true` or `false, reason`: `'Not enough items (have N, need M)'`, `'Player not loaded'`, `'Paying — wait a moment'` (bank payment hold), amount error.
- Logged as lost (`Log.lost`) with the reason; fires `whip_core:item:removed`.

### HasItem(source, item, amount?) — SERVER
At least `amount` (default 1) across all pockets. Returns `bool` or `false, 'Player not loaded'` / amount error. No metadata filter (use `FindAllItems`).

### GetItemCount(source, item) — SERVER
Total across pockets, in-slot only. Returns `number`, or `0, 'Player not loaded'`.

### CanFitItem(source, item, amount?, metadata?) — SERVER
Fits in pockets by slots and weight (shared weight counted once). Pass `metadata` for an instance with contents, or it is weighed empty (optimistic).
Returns `true` or `false, reason`: `'Only N fit'`, `'No room'`, `'Unknown item "x"'`, amount error, `'Player not loaded'`.

### GiveOnLogin(who, item, amount?, metadata?, opts?) — SERVER, WAITS
An item for a person now if playing, else kept in `pending_gives` and handed over at next login (at their feet if full; a deleted character takes theirs with it). (server/pending_gives.lua)
- `who`: server id or `{ charId = n }`. `opts`: reason string or `{ reason }` (≤ 120 chars).
- Returns `'now'` | `'login'` | `false, why` (`'Unknown item "x"'`, amount error, `'metadata must be a table or nil'`, `'metadata cannot be saved: ...'`, WhoIs refusal, DB error).
- Logged as `'<reason> (from <resource>, while away)'`. A give that fails at login stays queued for the next login.

## Server exports: finding and reading

### FindItem(source, item, pocket?) — SERVER
First stack, lowest slot first, pockets in order. `pocket` `'player'|'accessory'`; a pocket that doesn't exist finds nothing. Item key sanitized (≤ 60).
Returns `{ item, amount, metadata, addr }` (metadata is a JSON-round-trip copy; `addr = { kind = 'player', id = source, sub = pocket, slot }`) or `nil` (also when not loaded).
```lua
local found = exports.whip_core:FindItem(source, 'jerry_can')
if found then exports.whip_core:SetItemMetadata(found.addr, { fuel = 50 }) end   -- changes fuel only
```

### FindAllItems(source, item, pocket?) — SERVER
Every stack as `FindItem` entries, same order. Returns array (empty if none), or `{}, 'Player not loaded'`.

### GetInventory(source) — SERVER
Deep copy of the pockets: `{ player = { [slot] = { item, amount, metadata } }, accessory = {...} }` (metadata copied one level deep). `{}, 'Player not loaded'` before load. Slot keys are numbers.

### GetItemAt(addr) — SERVER, WAITS
Any store's slot: `{ item, amount, metadata }` (copy), `nil` when empty, `false, reason` for a bad address (`'Invalid slot'`, ...). Details in stores file.

### SetItemMetadata(addr, metadata, opts?) — SERVER, WAITS
Change the metadata of the item at an address (any store). (stores.lua:5016, rules `Inventory.buildMetadata` inventory.lua:2893)
- MERGES: only passed keys change. `opts.replace = true`: the table becomes the whole metadata (nil with it clears all). `opts.remove = { 'key', ... }`: keys taken away (cannot remove `uid`). `opts.quiet = true`: pockets only, save without pushing the inventory to the client (for values changed many times a second; anything the player should see must not be quiet).
- `uid` is kept unless you pass `uid = false`.
- `metadata = nil` without `replace` or `remove` is refused: `'metadata must be a table — to clear it all, pass nil with { replace = true }'`. Non-table: `'metadata must be a table'`. Bad `remove`: `"remove is a list of keys: { remove = { 'ammo' } }"`. Unsaveable: `'metadata cannot be saved: ...'`. Empty slot: `'Empty slot'`. Heavier metadata over a pocket limit: `'Too heavy'` (lighter never refused). Non-player kind write failure: `'That slot could not be written'`.
- Returns `true` once memory changed (save may retry). Not blocked by a bank-payment freeze.

## Server exports: registering items

Registration rule (shared/registry.lua): declare in `Whip.register(function() ... end)`; the same registration again is a no-op; a key held by another running resource is refused naming it; a stopped resource's keys are free to take.

### RegisterItem(key, definition) — SERVER
- Validation in order: key string/≤ 50/pattern; definition table; `name`; `weight`; panel item with `stack`; `maxStack` rule; `contextOptions`, `images`, `groundOptions` cleaned; `settings` and `pictureFields` cleaned; retirement check; registry ownership.
- Returns `true` or `false, reason`, e.g. `'an item needs a string key'`, `'item "x": a key is 50 characters at most (this one is N)'`, `'item "x": expected a definition table'`, `'item "x": a key is letters, digits, _ and - only (no colons or spaces)'`, `'item "x": needs a name (what players see)'`, `'item "x": needs a weight (kg, 0 or more)'`, `'item "x": it holds a panel (RegisterPanelItem), so it cannot stack — ...'`, `'item "x": stack = false with maxStack N — ...'`, `'item "x": maxStack N — a whole number, 1 or more (leave it out for 100)'`, option/image/setting errors, `'item "x" is retired by <res> (<reason>): give yours another key, such as "<res>_x"'`, `'item "x" is retired (<reason>)'`. A refusal is also printed (`Registry.sayRefused`).
- The definition is changed in place (cleaned lists, settled `maxStack`, admin-saved name/desc/weight/grab/playerWalk written on).
- Items are never swept: they stay in `Config.Items` when your resource stops (players carry them); the key stops being yours. Clients are told definitions are stale (one `whip_core:client:itemDefsStale` per burst).
```lua
Whip.register(function()
  Whip.core:RegisterItem('myems_medkit', { name = 'Medical Kit', desc = 'Heals injuries', weight = 0.5,
    type = 'medical', stack = true, maxStack = 5, usable = true, cooldown = 10, prop = 'prop_ld_health_pack' })
end)
```

### RegisterItemDefaultMetadata(itemKey, generator, opts?) — SERVER
Metadata for a new instance created without any: given (`AddItem`, `StoreGive`), picked up from a bare pile, shown on an infinite shop's shelf, bought.
- `generator(itemKey, ctx) → table`. `ctx = { source, charId, reason }`; `source`/`charId` nil into a stash/boot; `reason` `'given'|'pickup'|'shelf'|'bought'`; `ctx` itself may be nil (Director rewards) — runner passes `{ reason = 'given' }` when nil internally, but cope with nil. Errors or non-table results = no generator (item gets no metadata).
- `opts.forBuyer = true`: bought off an infinite shelf, it runs again for the buyer. Stocked shops sell real items, which keep their metadata.
- Returns `true` or `false, reason` (another resource has a generator for that item; no key; no handler). Owned: gone when your resource stops.
```lua
exports.whip_core:RegisterItemDefaultMetadata('sim_card', function(itemKey, ctx)
  if not (ctx and ctx.charId) then return {} end
  return { phoneNumber = NewNumber(), owner = ctx.charId }
end, { forBuyer = true })
```

## Server exports: use handlers and options

### RegisterUseHandler(itemKey, handler) — SERVER
`handler`: `function(source, player, slotData, addr) → boolean?, string?` (see Use pipeline) or a timed-use table.
- Returns `true` or `false, reason`: `'a use handler needs a string key'`, `'use handler "x": no handler given'`, a key another resource handles, `'use of "x": duration must be a positive number of milliseconds'`, `'use of "x": a table needs a duration in milliseconds (or pass a function)'` (a plain table without `duration`), a bad `notWhile` state.
- Registering before the item is fine. Registered for an item without `usable = true` → console WARNING; players only ever see "Item not usable".
```lua
exports.whip_core:RegisterUseHandler('pickaxe', function(source, player, slotData, addr)
  local left = (slotData.metadata and slotData.metadata.durability or 100) - 1
  exports.whip_core:SetItemMetadata(addr, { durability = left })
  return false   -- keep it
end)
```

#### Timed use (table form, `WhipTimedUse`)
Order: `canUse` → server-timed bar (`Progress`) → item still at `addr` (same item and same `uid`) → item TAKEN (`StoreTake`-equivalent, logged with `reason`) → `onComplete`. One timed use at a time per player.

| Key | Type | Default / meaning |
|---|---|---|
| `duration` | number | REQUIRED, ms, > 0, finite |
| `label` | string? | `'Using <item name>...'` |
| `icon` | string? | Glyph for the bar's disc when the item has no picture (`'eat'`, `'fuel'`, ...). The disc shows the item's picture by state otherwise |
| `anim` | table? | `{ dict, clip, ... }` as client Progress |
| `prop` | table? | `{ model, bone?, offset?, rot? }`; bone default 18905; made and removed by the server (HeldProps tag `'bar'`) |
| `disable` | table? | `{ move?: bool|'walk', combat?, car? }`. Progress default: move and combat off, driving allowed |
| `canCancel` | boolean? | Default `true` here (X stops it; item kept) |
| `cancelOnDeath` | boolean? | Default true |
| `cancelOnExit` | boolean? | Work from a seat: must be in a vehicle to start; leaving the seat stops it |
| `notWhile` | string[]? | `'swimming'`, `'underwater'`, `'falling'`: won't start or go on; validated at registration |
| `consume` | boolean? | Default `true`; `false` keeps the item (a tool) |
| `reason` | string? | Item-log reason, default `'used'` |
| `canUse` | function? | `(source, player, slotData, addr) → true | false, 'why'` before the bar. Error → `'You cannot use that right now'`; bare false → same text |
| `onComplete` | function? | `(source, player, item, addr)` after the take; `item` = `{ item, amount, metadata }` read after the bar. Returning `false` (bare or with why) or erroring GIVES IT BACK (to the same character via give-or-drop, reason `'use undone'`; logged lost if they left). Error → `'That did not work'`. Anything else = success |

- Not passed through: `near`, `tag` (Progress-only options).
- Bar not completed (cancelled, busy, dead, timeout, too fast...) → silent refusal, item kept, no cooldown.
- Item moved/dropped during the bar → `'You no longer have it'`. Take failed → `'Could not use it'`.
- Success: cooldown starts, `whip_core:item:used` fires, use not double-logged. Note bare `false` from `onComplete` gives the item back (unlike the function form, where bare `false` is a use that keeps it).
```lua
exports.whip_core:RegisterUseHandler('field_dressing', {
  label = 'Bandaging...', duration = 4000,
  anim = { dict = 'missheistdockssetup1clipboard@idle_a', clip = 'idle_a' },
  canUse = function(source)
    if exports.whip_core:GetStat(source, 'health') >= 200 then return false, 'You are not hurt' end
    return true
  end,
  onComplete = function(source) return exports.whip_core:AddStat(source, 'health', 25) end,  -- RETURN it
})
```
Not an item? Use the server `Progress(source, opts)` export (WAITS; reasons `'busy' | 'cancelled' | 'refused' | 'timeout' | 'too fast' | 'too far' | 'dead' | 'not in a vehicle' | 'left the vehicle' | 'player left' | 'run ended'`; finish accepted from 90% of duration, timeout at duration + 15 s).

### RegisterContextAction(actionKey, handler) — SERVER
Handler for a right-click option / `defaultAction`. `handler(source, player, slotData, addr, how)`; `how` nil from the inventory, `{ from = 'ground' }` after a ground option's pickup (skip your draw animation). Return `false, 'why'` to refuse (player sees why).
- `actionKey` ≤ 32 chars (`'context action "x" is longer than 32 characters'`); server-wide names, prefix with your resource (`'my_bows:equip'`; unprefixed warned). WHIP's own (`open_wallet`, `open_duffle`, panel dispatchers) are held by whip_core and refused.
- Returns `true` or `false, reason`.
- Server checks before running (`whip_core:server:customContextAction`, rate 500 ms): the action must be the item's `defaultAction` or one of its options (own or added); `when` + `require` re-checked; no handler → `"<label> isn't available right now"`. Logged as `ctx_<action>`. Thrown error → filed under the owner.
```lua
exports.whip_core:RegisterContextAction('my_resource:inspect_serial', function(source, player, slotData, addr)
  local serial = slotData.metadata and slotData.metadata.serial
  if not serial then return false, 'No serial' end
  exports.whip_core:NotifyPlayer(source, 'Serial: ' .. serial)
end)
```

### AddItemOption(itemKey, option) — SERVER
Adds a right-click option to any item (yours or another's); item need not be registered yet. `option` = a `contextOptions` entry `{ action, label, order?, when?, whyNot?, require?, anywhere? }` with your own action.
- Returns `true` or `false, reason`: `'AddItemOption needs an item key'`, malformed option, `'item "x" already has an option "y" of its own'`, same item+action added by another resource.
- Added options sort after the item's own, by action name; the item's own win a clash. Gone when your resource stops.
```lua
exports.whip_core:AddItemOption('gunny_pistol', { action = 'my_cops:prints', label = 'Check for prints',
  require = { job = 'police', onDuty = true } })
```

### RemoveItemOption(itemKey, action) — SERVER
Takes back an option you added (only your own). Returns `true` or `false, reason`.

## Server exports: item settings

`settings` entries (item_settings.lua:126): `{ key, type, default, label?, min?, max?, step?, unit?, maxLen?, nullable?, options?, help? }`.
- `key` `^[%a_][%w_]*$`, ≤ 40; not `name`, `desc`, `weight`, `grab`, `playerWalk` or `pictures`; unique.
- `type`: `'int'`, `'number'`, `'bool'`, `'string'`, `'enum'`. `min`/`max`/`step`/`maxLen` must be numbers. `enum` needs `options = { { value, label? }, ... }`. `label` truncated to 60 (default the key), `help` to 400.
- `default` must pass its own check, else the item is refused (`'item "x" settings N (key): its default ...'`). At most 20.
- Every item also has `name`, `desc`, `weight`, `grab`, `playerWalk` as admin settings (defaults = definition). Config.lua items: also stacking, cooldown and kind, under Config (`Items.<key>.<field>`). Only a permanent admin applies; saved in `whip_settings` (owner `item:<key>`), history `whip_settings_log`; Reset restores the definition value.
- Keep your own default: save your config's value for `default` before an `OnItemSettingChanged` hook overwrites it, or the next registration declares the admin's value as default.

### GetItemSetting(item, key) — SERVER, CLIENT
Server: own setting in force (saved or default), or `'name'`, `'desc'`, `'weight'` (also `'grab'`, `'playerWalk'`) from the definition. Client: own settings only; `nil` until whip_core sends values at join. Returns a copy, or `nil`.

### OnItemSettingChanged(item, key, fn) — SERVER, CLIENT
`fn(value, old, item, key)` after a change (Reset too; on a client also when values first arrive). One per resource per setting (calling again replaces); gone when your resource stops. Returns `true` or `false, 'OnItemSettingChanged(item, key, function(value, old, item, key) end)'` / registry reason.
```lua
Whip.core:OnItemSettingChanged('my_guns_mag', 'capacity', function(value) Config.Magazines.my_guns_mag.capacity = value end)
```

## Server exports: retiring items

### RetireItem(key, reason?) — SERVER
Takes one of your items out of the game: definition removed (nothing can create one: AddItem, shops, drops refuse an unknown item), `RegisterItem` refuses the key, every existing one taken away and logged `lost` with the reason, not refunded.
- When: at once from online pockets, open stashes/boots and the ground; elsewhere as each loads (character pockets at login and offline admin views, a stash when opened, a car's trunk/glovebox/ignition when loaded). Inside bags and wallets (plain slot arrays at `metadata[storageKey]`) at every level. Not inside panels with their own shape (`read`/`write` hooks, e.g. a magazine) or satellite store kinds: yours to clear. Nothing is read from the DB to find them: an unopened stash keeps its rows.
- Ownership: refused for a key a running resource holds (`'item "x" belongs to <res>: only it can retire it'`) or that another resource registered last, even stopped (`'item "x" was registered by <res>: only it can retire it'`; remembered across restarts).
- `reason` ≤ 120 chars, default `'no longer in the game'`. Key must match `^[%w_%-]+$`, ≤ 50.
- Returns `true` or `false, reason`. Asking again with the same reason changes nothing.
- The retirement belongs to your resource and is given up when it stops (items still in unopened stashes become "unknown items" until it starts and retires them again).

### UnretireItem(key) — SERVER
Gives up your own retirement; the key is free (re-register to bring the item back). What was taken stays taken. Returns `true` or `false, reason`.

## Server exports: lookups, pockets, accessory strip

### GetItemDef(key) — SERVER, CLIENT
Server: `Config.Items[key]` (the registry entry) or nil. Client: see Client exports.

### GetItemDefs() — SERVER, CLIENT
`{ [key] = definition }` (server: `Config.Items` itself).

### GetPockets() — SERVER
`{ 'player', 'accessory' }` (copy), in fallback order. For a client-named slot use the SecureEvent param type `'slot'` (`{'name', 'slot', { item = 'key'|{...}, allowEmpty = true }}`): the client sends a slot number or `{ sub, slot }`; the handler gets `{ addr, item, amount, metadata }` (copy); empty/wrong item refused with `'That item is not there any more'` / `'That slot holds something else now'` (secure.lua:221).

### GetPocketSlots(pocket?) — SERVER
A pocket's slot count, or the whole `Config.ContainerSlots` table.

### GetPocketMaxWeight(pocket?) — SERVER
A pocket's limit, or the whole `Config.MaxWeight` table. `'player'` covers everything carried incl. strip; `'accessory'` is the strip's own, inside it.

### RegisterAccessorySlot(def) — SERVER
Reshapes one strip slot until your resource stops (or `ReleaseTag(def.tag)`); WHIP's default comes back then.

| Field | Rule |
|---|---|
| `slot` | REQUIRED whole number 1..`Config.ContainerSlots.accessory` |
| `accepts` | item key or list of keys (empty strings dropped). With neither this nor `keys`: anything |
| `keys` | `true`: also any ignition key |
| `label` | default `'Accessory'` |
| `icon` | `'accessory'` (pouch), `'plus'`, `'phone'`, `'vehicle_key'`, `'cash'`; default: the accepted item's, or the pouch |
| `iconSvg` | inline SVG, wins over `icon`. Never from player input |
| `tag` | run tag (`'run:42'`); new tag each run |

Returns `ok, err`: `'def.slot (number) is required'`, `'this server has no accessory strip (Config.AccessoryStrip is off)'`, `'slot must be a whole number 1..N (Config.ContainerSlots.accessory)'`, a slot another resource registered. WHIP's five are defaults any resource may replace. Broadcasts `whip_core:client:invSlotDefs`.
```lua
Whip.register(function() Whip.core:RegisterAccessorySlot({ slot = 4, accepts = 'bandage', label = 'Medkit' }) end)
```

### GetAccessorySlots() — SERVER
`{ [slot] = { slot, accepts (list|nil), keys, label, icon } }`, a copy (no `iconSvg`).

### RegisterIgnitionKey(itemName) — SERVER
Makes an item an ignition key (ignition slot, key checks, key sweeps, Key strip slots). Its `metadata.vehicleId` must still match the car. Shared registry: stays a key until the last registering resource stops. Returns `ok, err` (`'itemName (string) is required'`). Declare in `Whip.register`.

## Server exports: hands and held item

### SetHeldItem(source, addr) — SERVER, WAITS
Records the item your resource just put in the player's hand (`addr` = one of their pocket slots `{ kind = 'player', id = source, sub, slot }`), or `nil` when put away. Others act on that exact item (whip_fuel uses the jerry can in hand). Record tracks item key and `metadata.serial`; an item moved/swapped out of the slot stops counting. Cleared when your resource stops, at logout, on leaving. The client learns it (`whip_core:client:heldItem`) for `GetHeldItem()` and `require = { held = ... }`.
Returns `true` or `false, reason`: `'Player not loaded'`, `"the hand holds one of the player's own pocket slots"`, `'That slot is empty'`, another resource's record.

### GetHeldItem(source) — SERVER
`{ addr, item, amount, metadata }` (metadata copy) or `nil` (nothing held, or item left its slot).
```lua
local held = exports.whip_core:GetHeldItem(source)
if held and held.item == 'jerry_can' then print('fuel:', held.metadata.fuel) end
```

### BlockHands(source, id, opts?) / UnblockHands(source, id) — SERVER
Server-side block for one online player (jail, arrest), kept server-side for `AreHandsBlocked` and sent to the client. `source` = server id or `{ charId }` (must be online). `id` string or number, non-empty. `opts`: `{ label?, only? = 'weapons' }`; default label `'Your hands are busy'` / `'You cannot use a weapon here'` with `only`. Cleared at logout/drop or when your resource stops. Returns `true` or `false, reason` (`'No player with that server id is online'`, `'a hands block needs an id'`, `"only is 'weapons', or nothing for everything"`, `'label is the words the player is shown'`).
```lua
exports.whip_core:BlockHands(target, 'cuffed', { label = 'You are handcuffed' })
```

### AreHandsBlocked(source, what?) — SERVER
`what = 'weapon'` (any block covers a draw) or nil (only a block of everything). Server blocks only (not ones the client set itself). Returns `true, label` or `false`.

### FreeHands(source) — SERVER
Tells the player's game to empty the hands now (runs the client `freeHands` hook) without blocking. Returns `true` or `false, reason` (not online).

## Server exports: another player's pockets

### OpenPlayerInventory(source, target, opts?) — SERVER, WAITS
Opens the target's pockets as a second panel beside the viewer's (admin tools, robberies).
- `target`: server id or `{ charId = n }` (offline too). `opts.range`: metres from an online target, default `5.0`; `false` for none; otherwise must be a positive number (`'range must be a number of metres, or false'`).
- Online target: their own inventory screen is locked meanwhile. Offline: loaded from DB (after settling owed saves) and saved on close.
- With a range (online only): moves out of range refused; a 1 s watcher closes it when the viewer leaves range+1 m (`'Too far away — closed'`), the target leaves (`'They are gone'`), or after 5 minutes (`'Closed — that took too long'`). Without a range it lasts until closed.
- Only the ACE-gated /whip admin tool may destroy the target's items; this export never can.
- Returns `true` or `false, reason`: `'Not loaded'`, `'You already have a player inventory open'`, `'Another player is already viewing this inventory'`, `'That character is logging in right now — try again in a moment'`, `'Target inventory not loaded'`, `'They are too far away'`, `"Their last save has not landed yet — try again in a moment"`, `"Could not read that character's inventory"`, `'Character not found'`, `'That character just logged in — open their inventory again'`, WhoIs refusal.

### ClosePlayerInventory(source) — SERVER, WAITS
Ends the viewer's inspection: unlocks/saves the target, saves the viewer. Returns `true` or `false, 'Player not loaded' | 'They have no player inventory open'`.

### IsCharacterBeingInspected(charId) — SERVER
Whether someone else has this character's pockets open (not whether they have their own inventory open). Returns boolean.

### ThrowGroundItem({ item, amount?, from, target, power?, by?, metadata?, reason? }) — SERVER (1.3.0)
Throws an item from one point at another as a player's throw does: a ground item from the moment it leaves `from` (anyone in reach can grab it in the air), on the arc that lands on `target` at that `power` (none: the gentlest that reaches). A player's game flies it: `by` when within 50 m of `from`, else the nearest player who is. It knocks over whoever it hits hard enough for its weight (`Config.ThrowKnockdown`; cash never does). Read its docs.html card for the returns before using it.

### Item notices (1.3.0)
`Config.ItemNotices = { enabled = true, removed = true, position = 'right' }`: a box with the item's picture, name and amount whenever a player gains (green) or loses (red) an item, any way (from `whip_core:item:added` / `:removed`). `removed = false` shows gains only; `position` `'right'`, `'left'` or `'bottom'`. A repeat adds to the box still up; at most 5 at once. Don't add your own "you received" toast on top.

### Fixed in 1.3.0
- A timed use that errors no longer locks that player out of every timed item until a restart.

## Client exports

### HasItem(itemKey, filter?) — CLIENT
Either pocket, from the cached inventory. `filter`: `function(metadata) → bool` or a number = minimum count (`HasItem('bandage', 3)`). Returns bool (false before the first sync). A function filter is not pcall'd.

### GetItemCount(itemKey, filter?) — CLIENT
Count across pockets. `filter`: `function(metadata) → bool`; a number/string/boolean is ignored. Returns number.

### GetHeldItem() — CLIENT
`{ item, pocket, slot }` (copy) or nil, as the server last said. No metadata (use the server's). For a prompt, `require = { held = 'jerry_can' }` is cheaper.

### SetInventoryLocked(locked) — CLIENT (whip_core 1.2.0+)
Blocks the inventory screen for your resource (`true`; also closes it if open) or releases YOUR lock (`false`; other
resources' locks and the database lock still apply). Cleared when your resource stops. A client UI lock only: it is
not server authorisation for inventory writes. Returns `false` for a non-boolean or without a calling resource.
Use: a minigame, a cutscene, a handcuffed state your resource owns.

### IsInventoryOpen() — CLIENT
Whether the plain inventory screen is open. For "is the player busy", use `IsGameInputFree`.

### CloseInventory() — CLIENT
Closes the inventory with any open container, vehicle storage or panel.

### GetInventory() — CLIENT
Deep copy (metadata one level): `{ [container] = { [slot] = { item, amount, metadata } } }`, or `{}, 'Player not loaded'`. Slot keys are STRINGS (`'1'`), as the server serializes them. To move items, use the renderer contract / `whip_core:server:storeMove` (server validates).

### GetItemDef(key) / GetItemDefs() — CLIENT
Client `Config.Items`: config.lua items as in the client config, plus server-registered items merged in when the server sends definitions (login sync / inventory open) with the NUI fields only: `name, desc, weight, type, stack, maxStack, css, usable, contextOptions, groundOptions, grab, playerWalk, metaFields, defaultAction, img, images, imgRoot, prop`. No `cooldown`, `settings`, `fuelCapacity`. A registered item is `nil` before the first sync.

### FreeHands() — CLIENT, WAITS
Call before putting something in the player's hands. Runs the `freeHands` hook (whip_gunny holsters, whip_fuel drops the nozzle). Call from a thread / via `Whip.core`. Returns `true` when free, `false` while a weapon is still drawn, `false, label` while blocked.
```lua
local free = Whip.core:FreeHands()
if not free then return end
Whip.core:PlayEmote('clipboard')
```

### BlockHands(id, opts?) / UnblockHands(id) — CLIENT
Block this player's hands (`opts = { label?, only? = 'weapons' }`; without `only`: everything). The same id replaces. A block of everything empties the hands at once (runs `freeHands`) and makes `FreeHands` return false (phone, tools, give mode won't start). Every block holsters a gun and stops a draw. Yours go when your resource stops. Fires `whip_core:hands:blocked { label, only }` / `whip_core:hands:unblocked {}` when none is left. Returns `true` or `false, reason`.

### AreHandsBlocked(what?) — CLIENT
This game's blocks and the server's (server's first). `'weapon'`: any block; nil: a block of everything. Returns `true, label` or `false`.

### RegisterClientHook(hookName, handler, id?) — CLIENT
Hooks: `'beforeGiveMode'`, `'beforePlaceMode'` (placing an item or an emote), `'freeHands'`. Handler may return a delay in ms; whip waits for the longest, clamped to 1000 ms. A handler that itself waits is abandoned after 1000 ms (console warns once). Key `<resource>:<id or hookName>`; same id replaces; gone when your resource stops; errors are pcall'd and reported. Returns `true` or `false, reason` (no handler; unknown hook).
```lua
exports.whip_core:RegisterClientHook('beforeGiveMode', function()
  if MyWeaponEquipped() then Holster() return 200 end
end)
```

### SetGiveModeStyle(style) — CLIENT
How the player moves while holding an item out to give. `style = { walk?, speed? }`: `walk` a /walk name or clipset; `speed` `'jog'` (no sprint) or `'walk'` (no running). `nil`/`false` clears yours. Latest registration wins while its resource runs. Default `Config.GiveModeStyle = { walk = 'trash', speed = 'jog' }`; items with `playerWalk` keep their own walk. Returns `true` or `false, reason`.

### RegisterItemFlag(flagName, itemOrFilter?, filter?) — CLIENT
A cached "carries this" flag, recomputed on every inventory change. `flagName` is also the item key unless `itemOrFilter` is a string key; `itemOrFilter` may instead be a metadata filter function. Filter errors count as "no" (reported once). Declare in `Whip.register`; yours go when your resource stops. Returns `true` or `false, reason` (non-string name; a name another resource holds — whip_core's `lockpick` included).

### HasItemFlag(flagName) — CLIENT
Returns bool. Use in `canInteract` for metadata rules; for a plain "carries one" use `require = { item = 'crowbar' }`.
```lua
exports.whip_core:RegisterItemFlag('my_valet_key', 'vehicle_key', function(meta) return meta and meta.plate == 'ABC123' end)
```

## Events

| Side | Event | Payload |
|---|---|---|
| S | `whip_core:item:added` / `whip_core:item:removed` | `{ source, item, amount (delta), count (now), reason?, by? }`. Fired by comparing per-item counts at each push; pockets only (moving cash into a wallet is a "removed"). `reason`/`by` only for export-made changes (`by = 'by <resource>'`, reason with the `· by` tail stripped) |
| S | `whip_core:inventory:changed` | `{ source }`: anything in the pockets changed, slot moves included; once per change |
| S | `whip_core:item:used` | `{ source, item, slot = slotData, addr }` |
| S | `whip_core:item:given` | `{ source, target, item, amount }` (player-to-player give) |
| C | `whip_core:hotbar:slotUsed` | `{ slot }` 1-5 |
| C | `whip_core:hands:blocked` / `whip_core:hands:unblocked` | `{ label, only }` / `{}` |

Listen with `AddEventHandler` (WhipEmit). Internal client events: `whip_core:client:inventoryUpdate` (`{ inventory, weights, unsolicited }`), `whip_core:client:itemDefsStale`, `whip_core:client:invSlotDefs`, `whip_core:client:heldItem`, `whip_core:client:handsBlocks`.

## Built-in items (Config.Items)

| Key | Name | kg | Stack (max) | Usable / cooldown | Behaviour (server/items/*.lua) |
|---|---|---|---|---|---|
| `food` | Burger | 0.3 | yes (20) | yes / 3 s | +25 hunger |
| `drink` | Water Bottle | 0.4 | yes (15) | yes / 3 s | +25 thirst |
| `bandage` | Bandage | 0.2 | yes (10) | yes / 5 s | `healing` effect: +5 health/s for 10 s |
| `package` | Package | 1.0 | no | no | plain item |
| `id_card` | ID Card | 0.1 | no | no | plain (wallet accepts it) |
| `cash` | Cash | 0.0001 | yes (999999) | no | currency; `image = '@whip_core/html/img/items/cash_3_stack.webp'`, 7 `amount` pictures (below 100 ... atLeast 500000) |
| `vehicle_key` | Vehicle Key | 0.1 | no | no | ignition key; metaFields model (uppercase), plate; `images` `keys/{make}.webp` |
| `lockpick` | Lockpick | 0.3 | no | no | client item flag `lockpick`; vehicle/door prompts (server-run skill check) |
| `camera` | Camera | 1.2 | no | yes / 0 | viewfinder; returns false (kept); HeldProps tag `'camera'` |
| `hacked_vehicle_key` | Hacked Vehicle Key | 0.1 | no | no | ignition key; metaFields model, plate, status |
| `duffle_bag` | Duffle Bag | 1.5 | no | no | panel item, 25 slots, `storageKey = 'slots'`; `defaultAction`/option `open_duffle`; full picture when `slots` not empty |
| `wallet` | Wallet | 0.2 | no | no | panel item, 3 slots, accepts `cash`, `id_card`; `open_wallet` |
| `armour` | Body Armour | 3.0 | yes (3) | yes / 10 s | timed use 5000 ms 'Equipping armour...', sets armour 100 |
| `damage_reducer` | Damage Reducer | 0.2 | yes (5) | yes / 25 s | 95% damage reduction for 20 s |

`jerry_can` is whip_gunny's. Do not redefine whip_core's keys (refused).

## Config keys

| Key | Default | Meaning |
|---|---|---|
| `Config.ContainerSlots` | `{ player = 30, accessory = 5 }` | Pocket slot counts |
| `Config.MaxWeight` | `{ player = 80.0, accessory = 10.0 }` | kg; player covers the strip |
| `Config.WeightUnit` | `'kg'` | Display default (`'lb'`) |
| `Config.AccessoryStrip` | `true` | false = no strip (applies at restart) |
| `Config.DropOnFullInventory` | `true` | false = a give that won't fit is refused |
| `Config.MaxGroundPilesPerDrop` | `50` | Pile cap per dropped give |
| `Config.EnableInventoryUI` | `true` | false = no inventory screen at all |
| `Config.Items` | (table above) | whip_core's items |
| `Config.DefaultGroundProp` | `'prop_cs_cardbox_01'` | Model for items without a usable prop |
| `Config.GroundItemPickupRange` | `2.0` | Nearby panel range |
| `Config.PlaceItemRange` | `10.5` | Place range from the camera |
| `Config.GiveModeStyle` | `{ walk = 'trash', speed = 'jog' }` | Give-mode walk |
| `Config.FlushInterval` | `1000` | ms between batched DB writes |
| `Config.InventoryRenderer` | `nil` | Resource providing `renderer.js`; convar `setr whip_inventory_renderer <res>` wins |
| `Config.Theme` | `nil` | Resource with `theme.css` (reskin only) |

## Replacing the inventory UI

- Set `Config.InventoryRenderer = 'my_inventory_ui'` (or `setr whip_inventory_renderer my_inventory_ui`); players get it on rejoin. Try live: `/whip_inventory_ui <res>` (developer mode), `/whip_inventory_ui none` back to whip's, `/whip_inventory_ui` alone reloads. Preview in a browser: `node whip_core/dev/inventory-preview/preview.js my_inventory_ui` (Node 18+).
- Your resource lists `renderer.js` (and assets) in `files{}`; whip imports `https://cfx-nui-<res>/renderer.js` and calls `export default function createRenderer({ api, mount, close, addStylesheet, signal })` which must return an object with `render()`. Missing resource, failed import or no `render` → whip's own UI, error in F8.
- Don't import whip's own JS modules (you get an empty second state). Read `api.inv` fresh every render. Close via `close`, never by hiding DOM. Pass `signal` to listeners outside `mount`.
- `api.actions`: `move`, `moveOne`, `quickMove`, `split`, `destroy` (dev mode), `use`, `give`, `place`, `menuFor`, `runOption`, `refused`, `slotAt`, `describe`, `weightOf`, `stackWeight`, `isPocketGrid`, `accessoryTakes`, `groundShowing`; each answers `{ ok }` or `{ ok: false, reason }`. Addresses are `{ container, slot }` with container `'player'`, `'accessory'`, `'ground'`, `'container'`, `'ignition'`, a panel key `'panel:<id>'`, `'targetPlayer'`.
- Optional renderer members: `showOverlay/hideOverlay`, `notify`, `flashPanels`, `isMidDrag`, `cancelInteractions`, `destroy`, `onKey`, `onNav`, `onAnalog`, `padHints`, `drawsShop: true`, plus per-part methods (`api.RENDERER_METHODS`). Events via `api.events.on`: `open`, `close`, `panel-swap`, `external-open`, `external-close`, `op-reverted`, `slot-defs`, `renderer-changed`. Raw ops: `api.ops.beginOp/extendOp/emit/commitOp` (unanswered ops swept after 15 s). Full contract: `whip_core/docs/nui-inventory.md`.

## Gotchas

1. `AddItem` returning `'ground'` is success. Only `false` means nothing was created; never refund on `'ground'`. Use `noDrop = true` (or `CanFitItem` first) when you must charge only if it lands in the pockets.
2. `AddItem(src, item, n, 'reason')` (reason in the metadata slot) is refused; the reason goes fifth. Same for `RemoveItem` (reason in opts).
3. `RemoveItem`'s 4th argument is a metadata FILTER, not metadata to match exactly: stacks carrying every given key/value match, other keys ignored.
4. A use handler returning nothing consumes one. Return `false` to keep a tool; return `false, 'why'` to refuse without a cooldown.
5. Timed use: bare `false` from `onComplete` gives the item BACK (opposite of the function form). Return the effect's result (`return exports.whip_core:AddStat(...)`) so a failed effect refunds. Use `consume = false` for tools.
6. An item without `usable = true` never reaches its use handler; Use runs `defaultAction` instead.
7. Cooldowns are per player per item key (not per slot) in whole seconds, cleared on disconnect.
8. Use handlers and context actions from other resources get the data sheet, not the live player; don't keep it or write to it.
9. `stack = false` with `maxStack > 1` is refused (config items are clamped with a warning). `stack = true` without `maxStack` = 100, not unlimited.
10. Different metadata never stacks (except top-level `uid`). Giving 10 items with a per-instance generator fills 10 slots for non-stackables.
11. `SetItemMetadata` merges. `nil` alone is refused; clearing is `SetItemMetadata(addr, nil, { replace = true })`. `remove` can't remove `uid`; pass `uid = false`.
12. Metadata must be JSON-saveable: functions, NaN, infinities and non-string/number keys are refused (on AddItem too).
13. Item keys: ≤ 50 chars, `[A-Za-z0-9_-]` only (no colon); prefix with your resource name. Context action keys ≤ 32 chars (and may contain `:`).
14. Items are never unregistered when a resource stops; another resource may take a stopped resource's key. `RetireItem` is only for keys you registered last.
15. Icons need `files { 'html/img/items/*.webp', 'html/img/items/*.png' }` in your fxmanifest, and a restart of your resource to show a new picture.
16. `contextOptions[].icon` is silently dropped; options in the menu are words only.
17. Options appear only on carried items unless `anywhere = true`; then the handler can get a non-player `addr` (trunk, stash, panel) — never assume `addr.kind == 'player'`.
18. Client `GetInventory()` slot keys are strings; server `GetInventory(source)` slot keys are numbers.
19. Client `GetItemDef` for a registered item lacks server-only fields (cooldown, settings, fuelCapacity) and is nil until definitions are synced.
20. Client `HasItem(key, n)` takes a count; `GetItemCount(key, n)` ignores a number filter.
21. `RemoveItem`, timed uses and item uses are refused while a bank payment holds the pockets (`'Paying — wait a moment'`); `SetItemMetadata` is not.
22. A `true` from an inventory change means queued for the next flush (≤ 1 s), not on disk.
23. `RegisterAccessorySlot` fails with the strip off; check its return. Strip slot rules are server-enforced: `AddItem` will not overflow an item into a slot that doesn't take it.
24. `OpenPlayerInventory` defaults to a 5 m leash; pass `{ range = false }` for admin tools. An online target cannot open their own inventory while inspected.

## Docs vs code

- Item settings reserved keys: docs say `name`, `desc` and `weight` are taken; code also reserves `grab`, `playerWalk` and `pictures` (whip_core/server/item_settings.lua:54, :139-140). Server `GetItemSetting` also answers `'grab'` and `'playerWalk'` (item_settings.lua:599).
- RetireItem: docs say "for good"; code ties the retirement to the calling resource and gives it up when that resource stops (whip_core/server/retired_items.lua:27-29, :352 registry default sweep). The stub agrees with the code ("Yours while your resource runs").
- `require` words: docs list `job, onDuty, jobPermission, item, zone, charId, ace, vehicle, alive`; code also accepts `held` (whip_core/server/item_options.lua:36).
- Timed use `canCancel`: `WhipProgressOptions` says default false for Progress; the timed use defaults it to `true` (whip_core/server/inventory.lua:2497). Docs agree with the code.
- `metaFields[].format` (`'uppercase'`, `'percent'`, `'phone'`) is in the stub and NUI (html/js/core/inv-actions.js:926) but not the docs.
- `GiveOnLogin` is in the stubs and `#how-whip-thinks` but not on the Inventory API page (whip_core/server/pending_gives.lua:39).
- Docs say `RegisterItem` keys must avoid colons and suggest an underscore prefix; code additionally warns (does not refuse) when a key does not start with the resource name followed by `_ : . -` (whip_core/shared/registry.lua:221).
