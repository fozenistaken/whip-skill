# Stores, containers, ground items and panels

The store model (`{ kind, id, sub, slot }` addresses) and every store export, custom store kinds, ground items, world containers (stashes) and panels. Built from doc anchors `#guide-stores` (`#store-addresses`, `#storemove`, `#storetake`, `#setitemmetadata`, `#finditembymetadata`), `#guide-ground` (`#ground-items`), `#guide-containers` (`#containers`, `#ensurecontainer`), `#store-kinds`, `#guide-panels` (`#panel-hooks`, `#panel-gunny-example`), `#server-panels`; verified against `whip_core/server/stores.lua`, `server/ground.lua`, `server/containers.lua`, `server/events_containers.lua`, `server/panels.lua`, `client/containers.lua`, `client/ground.lua`, `server/events_inventory.lua` (ground events), `types/server.lua`, `types/classes.lua`, `types/events.lua`. Player-pocket exports (`AddItem`, `RemoveItem`, `GetItemCount`, item definitions, use handlers): see inventory-items.md.

## Contents
- Store model and addresses
- Built-in store kinds
- Rules every move and write obeys
- Reading: StoreRead, StoreCount, GetItemAt
- Creating and destroying: StoreGive, StoreTake
- Moving: StoreMove
- Metadata: SetItemMetadata
- Finding one item: FindItemByUid, FindItemByMetadata
- Putting stores on a player's screen: GetOpenStores, OpenStore, CloseStore
- Item in hand: SetHeldItem, GetHeldItem
- CommitWithAction
- Persistence, saving and holds
- Custom store kinds: RegisterStoreKind
- Ground items
- Containers (world stashes)
- Panels: OpenPanel, ClosePanel and the hooks
- Items that hold items: RegisterPanelItem
- Events, client messages, DB tables, config
- Gotchas
- Docs vs code

## Store model and addresses

- A store is anything that holds items: pockets, the accessory strip, a stash, a boot/glovebox/ignition, a panel, a shop shelf, a shop basket, or a kind you register. Every kind is driven by the same mover, so weight, stacking, filters, transactions, saving and viewer sync are one rule set.
- Address: `{ kind, id, sub, slot }` (`WhipStoreAddr`). `slot` is 1-based; leave it out where the call can choose (StoreGive, StoreRead, StoreCount, StoreMove's destination, StoreTake with `opts.item`, OpenStore). Extra fields: `owner` (panel only: the player whose session to go through), `label` (filled in on addresses whip hands you; ignored on input).
- Ground items are NOT a store. `StoreRead({ kind = 'ground' })` answers `false, 'a ground item is not a store address — read it with GetGroundItem(id); a player picks it up'` (stores.lua:4104).
- Slots are addresses, never clamped: a non-integer or `< 1` slot is `false, 'slot must be a positive integer'` (stores.lua:4036-4041).
- `kind` is passed through `Sanitize.key(kind, 20)`: characters other than letters, digits, `_` and `-` are stripped and it is cut to 20 characters (stores.lua:4030). Keep custom kind names short and plain.

### Server-side address per kind (Stores.fromAddr, stores.lua:4027-4148)

| kind | address | notes |
|---|---|---|
| `player` | `{ kind = 'player', id = source, sub = 'player' }` | `sub` defaults to `'player'`; `'accessory'` is the strip (only when `Config.AccessoryStrip` is on). `id` must be a whole-number server id: `'player address needs the server id in \`id\`'`. Player must be loaded. |
| `container` | `{ kind = 'container', id = containerId }` | Whole-number id. Loaded on demand if nobody has it open; errors `'No such container'`, `'could not read that container'`. |
| `vehicle` | `{ kind = 'vehicle', id = vehicleId, sub = 'trunk' }` | `sub` must be `'trunk'`, `'glovebox'` or `'key'` (ignition): `"vehicle address needs sub = 'trunk', 'glovebox' or 'key'"`. `id` may be a vehicle reference `{ plate = '...' }`, `{ entity = ... }` or `{ netId = ... }`. Loaded on demand; `'Vehicle not found'`, `"could not read that vehicle's storage"`. |
| `panel` | `{ kind = 'panel', id = panelId, owner = source? }` | Only while open. Without `owner`, any viewer's session is used. `'panel address needs the panel id in \`id\`'`, `'that panel is not open'`. A RegisterPanelItem panel is re-read from its host item first. |
| your kind | `{ kind = 'mykind', id = ..., sub = ... }` | Opened with `resolve({ id = addr.id, sub = addr.sub })`. Unknown kind: `'Unknown store kind "x"'`. |
| `shop`, `basket` | none | Refused: `'"shop" is a per-player session store and has no server-side address'`. Use the shop exports. |
| `rawInventory`, `target` | not for resources | `rawInventory` is the admin viewer's handle on a character's cache; `target` is the client-side name for the admin/robbery inspect session. |

Stashes and boots loaded by an address export with nobody looking are unloaded by a sweep 2 minutes after an export last touched them (`ADDR_IDLE_MS = 120000`, sweep every 60 s; a car in the world keeps its storage) (stores.lua:3988-4015).

## Built-in store kinds

| kind | instanceId / persistence unit | slots / maxWeight | durability | client may name it |
|---|---|---|---|---|
| `player` | `player:<charId>:<container>` / unit `player:<charId>` (pockets + strip + character row are one unit) | `Config.ContainerSlots[c]` / `Config.MaxWeight[c]` or 9999 | writeBehind | as `player` / `accessory`, own only |
| `rawInventory` | `raw:<charId>:<container>`; unit is the live player's unit when the cache is live | as player | writeThrough | no (`target` instead, session-authorised) |
| `container` | `container:<id>` | `def.slots` or `Config.ContainerDefaultSlots` (20) / `def.maxWeight` or `Config.ContainerDefaultWeight` (100.0) | writeBehind | yes, while a viewer |
| `vehicle` | `vehicle:<id>:<trunk|glovebox|key>` (unit per compartment) | `Vehicles.getStorageConfig` | writeBehind | yes (trunk/glovebox as viewer; ignition by driver seat) |
| `panel` | `panel:<panelId>` | `config.slots` or 10 / `config.maxWeight` or `math.huge` | none (no persist) | yes, own sessions |
| `basket` | `basket:<source>` | session slots or 10 / `math.huge` | none | no; every move refused `'Use the shop screen'` |
| `shop` | `shop:<shopId>` | one row per catalog item (sorted) / `math.huge` | none | no; infinite/NPC shops only, writes are no-ops, `'This shop does not buy items'` |

Kind-specific rules:
- Accessory strip: per-slot typed (`allowsAt` / `beforeMove` use `Inventory.slotTakes`); refusal text from `Inventory.slotRefusal(slot)`.
- Container `allows`: a key named in its `requirements.items` can never go in (every path: drag, swap, quick-move, StoreGive); then `allowedItems`.
- Vehicle: `allows` = `Vehicles.isItemAllowed` (the ignition takes only a key for that vehicle). The ignition refuses an incoming move while a key is in it (no swap). Key in/out tells the driver (`afterMove` for drags, `afterWrite` for StoreGive/StoreTake). A key cannot be destroyed in the ignition: `'Take the key out first'`.
- `allowedItems` (containers and panels) accepts a list `{ 'food', 'drink' }` or a set `{ food = true }`; an empty table means no restriction (stores.lua:1192-1207).
- Every kind's `allows` first asks the Director/Systems stamp vetoes (`metadata.director`, `metadata.systest`, …) so test-run items cannot be stashed; a veto that errors refuses (stores.lua:182-202).

## Rules every move and write obeys

- Same address on both ends: success, nothing happens.
- Source slot empty: `'No item in source slot'`. Out-of-range slot: `'Invalid slot number'`.
- An item with no definition (its resource restarting) is never moved: `'Unknown item "x" — its resource may be restarting'`; for weight `'Unknown item weight'`.
- Filters: destination `allows` then `allowsAt`; on a swap the returning item must pass the source's `allows`/`allowsAt`. Refusal text is the hook's reason or `'That item does not go there'`.
- Merge: same item, `stack` with `maxStack > 1`, metadata equal ignoring top-level `uid`. Partial merge fills the stack and leaves the rest. A full destination stack falls through to a swap.
- Weight: only what crosses stores is weighed (`'Too heavy'`). Pockets are one weight: main grid plus strip together are capped by `Inventory.pocketsMaxWeight` (`Stores.pocketsOver`). Moving between a bag panel and the container it sits in is not re-weighed. A store with `maxWeight = math.huge` is not weighed.
- Partial amount (split): whole numbers only (`'Invalid amount'`), item must stack (`'That does not stack'`), destination empty or same item with room (`'Slot occupied'`, `'Different item state'`, `'Stack is full'`). A partial move never swaps.
- `mode = 'one'`: moves one unit; non-stackable multi-amount slot refused.
- Write order: destination first, source second, undo with a plain `set` if the second end refuses (`'Store is not available'`). This is why kind `get`/`set`/`clear` must not yield.
- Hooks: `beforeMove` on both ends (one `'within'` event for a move inside one store), then the returning half of a swap is asked again with `swap = true`. After the hooks the source and destination are re-read; a change in item or metadata: `'That changed while it was being checked. Try again.'`. A panel whose host item went: `'That item is no longer there'`.
- A unit held by a bank payment (`Stores.freeze`, ATM/sell card) refuses moves and StoreTake: `'Paying — wait a moment'` (holds lapse after 660 s max).
- Self-containment: a bag into its own open panel: `'that cannot hold itself'`.
- Bag nesting: weight is followed `Inventory.MAX_NESTING` (4) levels; deeper packing into a hosted panel: `'That is packed too deep to fit in there'`; weight into a hosted panel is checked against the host's pocket: `'Too heavy to carry'`.
- After the write: save (one transaction for both ends, see Persistence), then viewers get `whip_core:client:storeDelta`, then `afterMove` hooks (errors logged, never undo).

## Reading: StoreRead, StoreCount, GetItemAt

### StoreRead(addr) — SERVER, WAITS
- `addr`: any address; a slot in it is ignored. Loads a stash/boot if needed.
- Returns a copy: `{ kind, id, sub, label, slots, maxWeight, weight, items = { [slot] = { item, amount, metadata } } }` (`WhipStoreContents`), keys are slot numbers. Empty open panel: `items = {}`. `maxWeight` is `math.huge` for an unlimited panel.
- Failure: `false, reason` (`'No such container'`, `'Vehicle not found'`, `'that panel is not open'`, `'Unknown store kind "x"'`, address errors).

```lua
local stash = exports.whip_core:StoreRead({ kind = 'container', id = 12 })
if not stash then return end
for slot, it in pairs(stash.items) do print(slot, it.item, it.amount) end
```

### StoreCount(addr, item) — SERVER, WAITS
- Returns `number` (sum of `amount` in matching slots), or `false, reason` when the store cannot be reached. Not `0, reason` like `GetItemCount`: write `local n = StoreCount(a, 'x'); if n and n >= 5 then`.

### GetItemAt(addr) — SERVER, WAITS
- `addr` must have a slot. Returns a copy `{ item, amount, metadata }`; `nil` when empty; `false, reason` for a bad address or a slot past the store's size (`'Invalid slot'`). `if not item then` covers both.

```lua
local it = exports.whip_core:GetItemAt(addr)   -- still there?
if not it or it.item ~= 'alcohol' then return end
```

## Creating and destroying: StoreGive, StoreTake

### StoreGive(addr, item, amount?, metadata?, reason?) — SERVER, WAITS
| Param | Type | Meaning |
|---|---|---|
| addr | table | Address; `slot` optional |
| item | string | Registered item key, else `'Unknown item "x"'` |
| amount | number? | Whole number >= 1, default 1, else `'Amount must be a whole number of 1 or more'` |
| metadata | table? | Non-table: `'metadata must be a table'`; unsaveable: `'metadata cannot be saved: …'`. Omitted: the item's default-metadata generator runs once per slot (a gun's serial). |
| reason | string \| `{ reason = '...' }` ? | Activity log, appended with ` · by <resource>`; clipped to 120 chars |

- With a slot: exactly that slot, onto the same item if it stacks; refusals `'Slot occupied'`, `'Different item state'`, `'Stack is full'`, `'Too heavy'`, `'Invalid slot'`, filter reasons, and `amount > maxStack` → `'only N item fit in one slot'`.
- Without a slot: fills partial stacks first then empty slots, chunked by `maxStack`, across several slots; all or nothing (`'No room there'`). An item the store never takes says the filter reason instead.
- Returns the first slot landed in (number), or `false, reason`.
- Panels: your writes skip `onValidate`/`onChange` but slots, `maxWeight`, `allowedItems` and stack sizes apply; a RegisterPanelItem panel folds into its item. Pockets are pushed to the client and saved (fires `whip_core:item:added`). Other stores save and publish changed slots to viewers, then run the kind's `afterWrite`.
- For a player's reward use `AddItem` (drops at their feet when full) — see inventory-items.md.

```lua
exports.whip_core:StoreGive({ kind = 'vehicle', id = vanId, sub = 'trunk' }, 'delivery_package', 20, nil, 'delivery shift')
```

### StoreTake(addr, amount?, opts?) — SERVER, WAITS
- With a slot: from that slot; `amount` nil = the whole stack. Errors: `'Empty slot'`, `'Not enough items'`, `'Invalid amount'`, `'Invalid slot'`.
- Without a slot: `opts.item` required (`'name the slot in the address, or the item in opts.item'`); `amount` default 1; counted first, so a short store changes nothing: `'Not enough drink there (3 of 5)'` (held of wanted). Taken from the last slots first. If a custom kind refuses a write mid-way, what came out is put back: `'Could not take all of the <item> (the store refused a write)'`.
- `opts`: `{ item?, metadata?, reason? }` or a plain reason string. `metadata` (whip_core 1.2.0+) is a recursive partial
  match: the stack must carry every key given with that value; extra keys are allowed. `item` and `metadata` filter a
  given slot too: `{ item = 'drink', metadata = { quality = 'fresh' } }`.
- Frozen unit (bank payment hold): `'Paying — wait a moment'`.
- Returns `{ item, amount, metadata }` (metadata only when taken from one slot), or `false, reason`. The items are destroyed (logged 'lost'); to relocate use StoreMove.

```lua
local taken, err = exports.whip_core:StoreTake({ kind = 'container', id = 12 }, 5, { item = 'drink' })
```

## Moving: StoreMove

### StoreMove(fromAddr, toAddr, opts?) — SERVER, WAITS
| Param | Type | Meaning |
|---|---|---|
| fromAddr | table | Source, with its slot |
| toAddr | table | Destination; without a slot it goes to `Stores.slotAccepting` (a mergeable partial stack, else the first empty accepting slot) or `'No room there'` |
| opts.amount | number? | Whole number >= 1; omitted = whole slot. More than the stack moves the whole stack. **0 is refused** (`'Amount must be a whole number of 1 or more'`), despite the docs |
| opts.mode | `'move'` \| `'one'` \| `'split'` | Default `'move'`. `'split'` needs an amount (`'Split needs an amount'`) |
| opts.reason | string? | Activity log |

- Any other opts key is dropped (the internal `source` is whip_core's only), so custom kinds' `afterMove` see `ctx.source = nil` for a resource move.
- Same path as a player's drag: hooks on both ends, merge/partial merge/swap, one transaction, viewers updated, then `afterMove`. A kind answering `'handled'` counts as success.
- Logged: one "moved" row per character touched (one row when neither end is a character), naming your resource and reason. Pockets that changed are pushed to their owner (`whip_core:item:added` / `item:removed`).
- Returns `true` or `false, reason`. Bad input: `'StoreMove takes two addresses: { kind, id, sub, slot }'`, `'StoreMove options must be a table: { amount, mode, reason }'`, `'Empty slot'`.
- Use it instead of StoreTake + StoreGive, which can fail half way.

```lua
local ok, err = exports.whip_core:StoreMove(
  { kind = 'container', id = 12, slot = 3 },
  { kind = 'player', id = source, sub = 'player', slot = 1 }, { amount = 2 })
```

## Metadata: SetItemMetadata

### SetItemMetadata(addr, metadata, opts?) — SERVER, WAITS
- `addr` with a slot; `'Empty slot'` when nothing is there.
- Merges: only the passed keys change. `opts.replace = true`: the table becomes the whole metadata (`nil` with replace clears it). `opts.remove = { 'key', ... }` deletes keys (`uid` can never be removed this way). A bare `nil` without replace/remove: `false, 'metadata must be a table — to clear it all, pass nil with { replace = true }'`. `remove` not a table: `"remove is a list of keys: { remove = { 'ammo' } }"`.
- `uid` survives even `replace`; pass `uid = false` in `metadata` to clear it.
- Anything `json.encode` cannot write: `false, 'metadata cannot be saved: …'` before anything changes.
- Pockets: if the new metadata makes the item heavier (a filled bag, a loaded gun) it is held to the container's and the pockets' weight: `'Too heavy'`. Lighter is never refused. Written in place (a running use handler holds that table). `opts.quiet = true` (pockets only): saves without pushing the inventory to the client, for a value that changes many times a second.
- Other kinds: written through the kind's `set`; a refusal is `'That slot could not be written'`.
- Not refused during a bank hold (by design, for undo paths).
- Returns `true` once the slot changed (even if the save is retried later), or `false, reason`.
- Metadata goes whole to anyone who sees the item: keep secrets server-side and store an id.

```lua
exports.whip_core:SetItemMetadata({ kind = 'container', id = 12, slot = 3 }, { evidence = true }, { remove = { 'label' } })
```

## Finding one item: FindItemByUid, FindItemByMetadata

### FindItemByUid(uid) — SERVER
- Searches loaded places only, in this order: online players' pockets (`{ kind = 'player', id, sub, slot }`), stashes in memory, vehicle storage in memory (`{ kind = 'vehicle', id, sub, slot }`), open panels (`{ kind = 'panel', id, slot }`, no owner), the ground (`{ kind = 'ground', id }`, no slot).
- Not found: a stash untouched since restart, an item inside a bag/wallet (it lives in the host's metadata). `nil`/`''` uid returns nil.

### FindItemByMetadata(key, value) — SERVER
- First item whose `metadata[key] == value` (plain `==`), same places and shapes. `key` must be a non-empty string and `value` non-nil, else nil.

```lua
local at = exports.whip_core:FindItemByMetadata('serial', 'AB12CD34EF56')
if at and at.kind ~= 'ground' then local it = exports.whip_core:GetItemAt(at) end
```

## Putting stores on a player's screen: GetOpenStores, OpenStore, CloseStore

### GetOpenStores(source) — SERVER
- Every store the player is a viewer of, sorted by kind then id/sub. Pockets never listed. Stash `{ kind = 'container', id }`, boot `{ kind = 'vehicle', id, sub }`, panel `{ kind = 'panel', id, owner = source, label }`, a kind opened with OpenStore `{ kind, id, sub }` (the address it was opened with), a shop being browsed `{ kind = 'shop' }`. Empty table when nothing is open.
- This is how you learn the internal id of a panel an item opened (match its `label`).

### OpenStore(source, addr, opts?) — SERVER, WAITS
| opts | Applies to | Meaning |
|---|---|---|
| `skipDistance` | stash | No need to stand at it (otherwise within `Config.ContainerInteractRange + 2.0` = 4.5 m, and the player is then held to twice that, 9 m, on every move) |
| `skipAccess` | stash, boot | Ignore a stash's lock, `accessCharId` and `requirements`, or a boot's lock. Recorded on the viewer, so it is not re-asked on later moves |
| `coords`, `range` | your kind | Player must stay within `range` (default 3.0 m) of `coords` (vector3/vector4/table) for every move |
| `readOnly` | your kind | Viewer may look; every move refused (`'You can only look at that'`) |

- Stash: same path as pressing E (`Containers.openFor`): `'Container not found'`, `'This container is locked'`, `'You do not have access to this container'`, a requirements reason, `'Too far away'`, `'Could not read this container'`. Fires `whip_core:container:opened`.
- Boot: `sub` must be `'trunk'` (`"only a vehicle's 'trunk' opens this way; the glovebox and ignition open from its seat"`); always distance-checked against the trunk open range (`'Too far away'`), `'Vehicle is locked'` unless `skipAccess`, `'Vehicle not found'`.
- Refused kinds: `player` (`"a player's pockets open with OpenPlayerInventory"`), `panel` (`'a panel opens with OpenPanel'`), core kinds other than container/vehicle (`'"x" cannot be opened with OpenStore'`). Player not loaded: `'Player not loaded'`.
- Your kind: its `instanceId` must start with `"<kind>:"` or `'store kind "k" gave the id "…" — an instanceId must start with "k:"'`. Sent to the client as `whip_core:client:openStore` (stash-shaped payload; an unlimited weight shows as 9999).
- Returns `true` or `false, reason`. `true` means the server opened it; if the player's game already has another screen up it declines and sends the close back, so the view is released (client/containers.lua:395-401).
- Several players share one stash; the loser of a race finds the slot empty.
- The player stays a viewer (their drags count) until CloseStore or their own close. Inside a `SecureEvent` handler that errors before returning, the view is released automatically; elsewhere you must close it.

```lua
local ok, reason = exports.whip_core:OpenStore(source, { kind = 'container', id = containerId }, { skipAccess = true })
if not ok then exports.whip_core:NotifyPlayer(source, reason, 'error') end
```

### CloseStore(source, addr) — SERVER, WAITS
- Works even after the player disconnected. Other viewers keep it.
- Stash: save, release, unload if nobody else uses it. Boot: same with its compartment (`sub` needed). Your kind: matched by the address OpenStore kept (kind, `tostring(id)`, `tostring(sub)`), view dropped.
- Refused: `panel` (`'a panel closes with ClosePanel'`), `player` (`"a player's pockets close with ClosePlayerInventory"`). Not a viewer: `'That is not open'`. Sends `whip_core:client:storeClosed` to the player.
- Returns `true` or `false, reason`.

## Item in hand: SetHeldItem, GetHeldItem

(Belongs with the hand/weapon systems; summarised here because it is a store-address export.)
- `SetHeldItem(source, addr|nil)` — SERVER, WAITS. `addr` must be one of that player's own pocket slots (`{ kind = 'player', id = source, sub, slot }`), else `"the hand holds one of the player's own pocket slots"`; empty slot `'That slot is empty'`; `'Player not loaded'`. `nil` puts it away. The record belongs to the calling resource (another running resource is refused), is cleared when that resource stops, at logout and when the player leaves. Notes item and serial; the player's game gets `whip_core:client:heldItem` `{ item, sub, slot }` or `false`.
- `GetHeldItem(source)` — SERVER. `{ addr, item, amount, metadata }` (copy), or nil when nothing is held or the slot no longer holds that item/serial.

## CommitWithAction

### CommitWithAction(queries, opts?) — SERVER, WAITS
- Your own SQL in ONE transaction with whatever the player's current SecureEvent/SecureCallback action changed and whip has not yet written (an item you took and the row you wrote for it land together). Outside an action: the queries alone.
- `queries`: non-empty list of `{ query = 'INSERT …', values = { … } }` (`'queries is a list of { query = "...", values = { ... } }'`, `'query N is …'`, `'query N: values is a list'`).
- `opts`: `{ source?, vehicleId? }` — whose action, when your code runs outside the handler that started it.
- Returns `true`, or `false, 'Could not save that (database error)'` (console names the caller and the real error).

## Persistence, saving and holds

- Durability per kind: `writeBehind` units are marked dirty and written by the flush thread every `Config.FlushInterval` (1000 ms); `writeThrough` commits immediately. A move touching any write-through store commits all participants at once; between two deferred stores both units are linked and written in one transaction later (a trade never half-persists). A move into a hosted panel (bag/wallet) defers and links with the pockets.
- Memory is authoritative. A failed commit is not a failed move: units stay owed and linked; retried with backoff `FlushInterval × 2^fails` up to 60 s; after 5 failures a unit is "stuck", reported every minute to console and admins with `whip.devtools`; `/whipsaves` lists stuck saves, `/whipsaves drop` gives one up (and its whole group).
- A database write pending more than 30 s triggers a stall warning (console and devtools admins, once a minute).
- Saves made during a SecureEvent/SecureCallback handler are tied to that action and held from the background flush until it ends (max 30 s), so one player action is one transaction.
- Final save on stop/shutdown: force-flush of every owed unit (steps 10 and 52), run containers written down as lost (step 5/8), opened panels' deposits returned (step 20).
- Persist of a custom kind's queries runs under pcall; returning `nil` from `persist` means "cannot persist right now" and fails the commit (retried); `{}` means nothing to write.

## Custom store kinds: RegisterStoreKind

Use one for storage that persists and authorises itself and should behave like a first-class container. For a one-session grid use `OpenPanel`; for an item that holds items use `RegisterPanelItem`.

### RegisterStoreKind(kindId, kindDef) — SERVER
- Once per kind, never per instance. Re-registering your own kind swaps the definition quietly (queued writes are re-pointed at it). Another running resource's kind: `'store kind "k" belongs to <res>'`. The kind is removed when your resource stops; its queued writes are dispatched first (lost ones are warned about).
- Reserved names (`'"x" is reserved by whip_core and cannot be redefined'`): `player`, `rawInventory`, `container`, `vehicle`, `panel`, `basket`, `shop`, `target`, and each pocket name (`accessory`) (stores.lua:3734-3747).
- Returns `true` or `false, err`; never throws (malformed definitions answer with the assert text). Validation errors: `'kindId must be a non-empty string'`, `'kindDef must be a table'`, `'missing required function "x"'`, `'authorize must be a function when provided'`, `'durability must be "writeThrough" or "writeBehind"'`.
- Console: `<res> defined store kind "k" (client-addressable)` when `authorize` is given, else `(server-only)`.

| Field | Signature | Req | Meaning |
|---|---|---|---|
| `resolve` | `(key) → handle\|nil` | yes | `key` is `{ id, sub }` (from server calls and from a client drag alike). `nil` = cannot proceed (never "empty"). Must look ids up and return nil for unknown ones |
| `instanceId` | `(key, handle) → string` | yes | Stable identity; must start with `'<kindId>:'` for OpenStore. Viewer records are keyed on it |
| `unitKey` | `(key, handle) → string` | no | What persists together; default `instanceId` |
| `slots` | `(handle) → number` | yes | Capacity |
| `maxWeight` | `(handle) → number` | yes | Weight cap (`math.huge` = unlimited, not weighed on partial moves) |
| `get` | `(handle, slot) → { item, amount, metadata }\|nil` | yes | |
| `set` | `(handle, slot, item, amount, metadata) → boolean` | yes | Return truthy when written; falsy refuses. An error is treated as refused and logged |
| `clear` | `(handle, slot)` | yes | Return `false` to refuse; error = refused |
| `allows` | `(handle, itemKey, metadata) → boolean, reason?` | no | Whole-store filter (reason shown to the player) |
| `allowsAt` | `(handle, slot, itemKey, metadata) → boolean, reason?` | no | Per-slot filter, checked wherever an item lands (moves, swaps, StoreGive, split targets) |
| `persist` | `(handle) → queries[]\|nil, confirm?` | no | Queries `{ query, values }`; `nil` = cannot persist now; optional confirm callback runs after commit. Absent: never saved |
| `durability` | `'writeThrough'` \| `'writeBehind'` | no | Default `'writeThrough'` |
| `authorize` | `(src, addr) → boolean` | no | Lets clients address the kind without OpenStore; only a literal `true` allows, an error refuses |
| `beforeMove` | `(handle, ctx) → false, reason \| 'handled' \| other` | no | Veto before anything changes. `false` refuses (`reason` or `'Move rejected'`); `'handled'` = you did the move yourself (whip does nothing and reverts nothing); anything else allows. An error refuses: `'The <kind> could not verify this move'` |
| `afterMove` | `(handle, ctx)` | no | Side effect after the commit; errors logged |
| `label` | `(key, handle) → string` | no | Code-only: label in StoreRead, logs, OpenStore header (default instanceId) |
| `afterWrite` | `(handle, slots)` | no | Code-only: side effect of a direct write (StoreGive/StoreTake/SetItemMetadata), which run no move hooks |
| `weight` | `(handle) → number` | no | Code-only: overrides the summed weight |

Hook `ctx` (a satellite kind gets `other` as an address, internal payload removed):
- `direction` `'in'|'out'|'within'`, `slot` (this store's), `otherSlot`, `other` (`{ kind, id, sub, slot, label }`, nil when destroying), `otherName` (client-facing name of the other store: `'player'`, `'accessory'`, `'container'` for stash/vehicle, else the kind), `item`, `amount`, `metadata`.
- beforeMove only: `swap` (true on the returning half of a swap), `replacing` (forward half: what is in the destination and goes back), `destroyed` (developer Destroy: direction `'out'`, no `other`).
- afterMove only: `source` (the player for a drag; nil for StoreMove/StoreGive from a resource), `destroyed`.
- `beforeMove` has no `source` (stores.lua:1892-1908).

Access: players can move items in your kind only while it is open on their screen via OpenStore (held to `coords`/`range`, never if `readOnly`), or when `authorize(src, addr)` returns literal `true`. Without either: `'store kind "k" is server-only'` / `'you do not have that k open'`. Your resource can always move items. Client closes send `whip_core:server:closeStore` (only drops the view).

```lua
local lockers = { [3] = { slots = {} } }   -- yours, in memory; save it from persist
Whip.register(function()
  Whip.core:RegisterStoreKind('my_locker', {
    resolve    = function(key) return lockers[key.id] and { id = key.id } or nil end,
    instanceId = function(key, h) return 'my_locker:' .. h.id end,
    slots      = function(h) return 20 end,
    maxWeight  = function(h) return 100.0 end,
    get   = function(h, slot) return lockers[h.id].slots[slot] end,
    set   = function(h, slot, item, amount, metadata)
      lockers[h.id].slots[slot] = { item = item, amount = amount, metadata = metadata }; return true end,
    clear = function(h, slot) lockers[h.id].slots[slot] = nil; return true end,
  })
end)
exports.whip_core:OpenStore(source, { kind = 'my_locker', id = 3 })
```

Rules:
- Handles carry an id, never live data: values crossing an export are copied, so a `set` on `{ id = id, rows = myRows }` writes into a copy (the item leaves the player and never arrives). Return `{ id = id }` and look storage up in `get`/`set`/`clear`.
- `resolve`, `get`, `set`, `clear` must not yield (no `Wait`, no `MySQL … .await`). Keep storage in memory; write from `persist`.
- `id`/`sub` come from the client on a drag: validate them in `resolve`.
- Every store export works with it (`StoreRead`, `StoreGive`, `StoreTake`, `StoreMove`, `GetItemAt`, `SetItemMetadata`, `OpenStore`, `CloseStore`).

## Ground items

Items lying in the world, in table `ground_items`, loaded at start and kept until picked up or deleted. There is no despawn timer; admins clear them (`/whip_clearground [radius]` default 10 m, `/whip_clearallground`, Ground panel of the dev tools).

Player side:
- Drop: drag to the Ground panel; it lands where the player's game found a spot within `Config.GroundItemPickupRange` (2.0 m) horizontally and 3 m vertically, random resting angle. Pockets lose the item only as the ground row is made (no loss or copy). One drop is split into proper stacks, capped at `Config.MaxGroundPilesPerDrop` (50) piles (shared out evenly past that).
- Throw (give mode, aim, release): the pile exists at once as a flying networked object; anyone in reach can grab it from the air; it settles where it lands (watchdog settles it after 15 s, or when the object/thrower is gone). Hits knock people over (`Config.ThrowKnockdown`).
- Place: set down exactly with surface tilt, within `Config.PlaceItemRange` (10.5 m from the camera).
- Pick up: E takes as many as fit (the rest stays on the ground); the server is asked first (`groundPickupRoom`) so a full pocket shows the reason with no grab animation. Two players grabbing at once: one wins (`'Someone else is picking this up'`, lock with 10 s TTL). Reach: pickup range plus a buffer, server checks `GroundItemPickupRange + 5.0` on the screen pickup. Items may declare `groundOptions` (e.g. Equip) that run right after the pickup (see inventory-items.md).
- Streaming: players are sent piles in `Config.GroundItemCellSize` (50 m) grid cells around them (re-checked every `Config.GroundSyncInterval` s, default 1); props drawn within `Config.GroundItemStreamRange` (100 m, keep >= 50, door lock sync rides it). Props default to `Config.DefaultGroundProp` (`prop_cs_cardbox_01`) when the item has no `prop`. A pile that was not placed is snapped with `PlaceObjectOnGroundProperly` on each client (`client/ground.lua:597`), so `CreateGroundItem` at a ped's position (about 1 m up) lands on the floor; there is no tilt, so a flat prop must be modelled flat (GTA has no small flat blood prop: `p_bloodsplat_s` and `m25_1_prop_m51_blood_smear_01b` stand upright).
- Rate limits (SecureEvent): drop/drop-one/pickup/throw/place 200 ms; split and destroy also burst 3; destroy needs `whip.devtools` with developer mode.

### CreateGroundItem(def) — SERVER, WAITS
| Field | Type | Meaning |
|---|---|---|
| item | string | Registered item, else `'Unknown item "x"'` |
| amount | number? | Whole number >= 1, default 1 |
| coords | vector3 \| vector4 \| `{x,y,z}` | Required (`'CreateGroundItem needs coords'`); a vector4's `w` is the heading when `heading` is absent |
| metadata | table? | Stored as JSON (`'{}'` when nil) |
| heading | number? | Degrees, default 0 |
| reason | string? | Activity log ('gained … on the ground'), beside your resource name |
| createdBy | number? | Code/stub only: the charId the row is logged against |

- Returns the cached row `{ id, item, amount, metadata, x, y, z, heading, createdAt, createdBy }` (`createdAt` epoch seconds; `placed`, `rx`, `ry` only on placed piles), or `false, reason`: `'CreateGroundItem takes one table: …'`, `'Amount must be a whole number of 1 or more'`, `'Invalid coordinates'`, `'Database error'`.
- Check the return: a discarded failure is silent item destruction. Synced to nearby players automatically.

### DeleteGroundItem(id) — SERVER, WAITS
- Returns `true`, or `false, 'Item not found'` / `'Database error'`. Only the DELETE that actually removed the row counts (a racing pickup loses with `'Item not found'`). Logged 'lost'. Pass the numeric id exactly (no string coercion).

### GetGroundItemsNearby(x, y, z, range?) / GetGroundItemsNearby(coords, range?) — SERVER
- 3D radius, default 10 m; `range <= 0` or bad coords returns `{}`. Returns rows `{ id, item, amount, metadata, x, y, z, heading, … }` (stored position, not a flying pile's live position).

```lua
for _, row in ipairs(exports.whip_core:GetGroundItemsNearby(vector3(x, y, z), 5.0)) do
  exports.whip_core:DeleteGroundItem(row.id)
end
```

### GetGroundItem(id) — SERVER
- One row, or nil once picked up or deleted (id passed through `Sanitize.id`).

## Containers (world stashes)

- A container is a prop (or no prop) with an E prompt; opened in place of the Ground panel beside the pockets. Prop streams within `Config.ContainerStreamRange` (100 m); E works when not locked, the player may open it, no other UI is open, and they stand within `Config.ContainerInteractRange + 2.0` (4.5 m, server check). Since 1.1.0 that distance counts from the prop's edge, where its prompt stands, not its middle: each container stores how far its prop reaches (column `reach`, migration 045), measured by an admin's game when it is made or changed in `/whip` → Containers (an older container is measured the first time an admin opens that page). The `/whip` container wizard makes stashes only. A property's stash prompt shows only to people who live there. Prompt placement `Config.ContainerPrompt` = `'middle'|'side'|'face'` (default `'face'`, player-overridable).
- Contents are loaded on open and unloaded on the last close/disconnect (saved first), so thousands of containers cost little. Several players share one; `allowedItems` and `requirements` hold on every move.
- As a store: `{ kind = 'container', id = containerId }` — `StoreRead`, `StoreGive`, `StoreTake`, `StoreMove`, `OpenStore`, `CloseStore`. Nobody needs it open.

### Who may open it (Containers.canAccess, containers.lua:996)
Each set field must pass, in order:
| Field | Effect | Refusal |
|---|---|---|
| `locked = true` | Nobody (admin Container Manager, or OpenStore `skipAccess`) | `'This container is locked'` |
| `accessCharId` | Only that character | `'You do not have access to this container'` |
| `requirements` | Any ONE rule lets in: `jobs` (with `onDuty`, on duty there; `onDuty` alone = on duty at any job), `charIds` (empty list = nobody), `items` (carried, e.g. a keycard; `{ key, count }`), `ace`, `property` (propertyId or property key: owner and keyholders) | rule's own reason |
| none | Anyone | |

- `requirements` shape: `job`/`jobs` (string or list), `charId`/`charIds`, `item`/`items` (key, `{ key = }`/`{ item = }`, `count` >= 1, or a list), `ace`, `onDuty` (only `true` kept), `property`. `lockpick` is refused (`'requirements.lockpick is for doors — a container takes jobs, onDuty, charIds, items, ace, property'`); unknown keys refused; an unknown property refused (`'requirements.property: there is no property "x"'`). `false` or `{}` = none.
- `require` (the actions' word) is accepted instead of `requirements` only when it names ONE rule; two or more rules refused (actions read `require` as ALL, containers read rules as ANY ONE). Giving both is refused.
- A required item can never be put into the container it opens; UpdateContainer refuses a new rule naming an item already inside (`'it holds X, which it would then need to be opened: take it out first'`).
- An access-checked open is re-checked on every move (locked since, off duty, key lost: the next move is refused). `skipAccess` and admin opens are not re-checked.
- A deleted character's stashes lose `ownerCharId`/`accessCharId` (contents kept, `locked` kept).

### EnsureContainer(key, data) — SERVER, WAITS
- Declared by key (the EnsureShop/EnsureZone rule). New key: created. Same declaration again: nothing changes (an admin's edits stand). Changed declaration: every declared field applied, an `allowedItems` or `requirements` you stopped declaring is cleared, fewer `slots` refused while an item sits above the new count. A key declared by another running resource: `'container "k" is declared by <res>'`.
- `key`: letters, digits, `_ - . :`, at most 100 (`'a container key is letters, digits, _ - . and :, at most 100'`). Prefix it: `'pd:weapon_locker'`.
- `data`: `x, y, z` required (`'a container needs x, y and z'`), `heading?`, `name?`, `type?`, `prop?` (non-empty text; `false` is not accepted here), `slots?` (integer >= 1), `maxWeight?` (> 0), `locked?`, `allowedItems?` (table), `requirements?` / `require?`. Numbers compared to the millimetre. `ownerCharId`/`accessCharId` are not declared (use UpdateContainer). An unread field is reported in the console once.
- While whip_core starts it waits up to 60 s, then `false, 'whip_core has not finished starting (see its console)'`.
- Returns the container def (`WhipContainerDef`, with `containerId`, `key`, `declared = { by, decl }`), or `false, why` (also printed as a refusal in your console).

```lua
Whip.register(function()
  Whip.core:EnsureContainer('pd:weapon_locker', {
    name = 'Weapon Locker', slots = 30, maxWeight = 200.0,
    x = 441.5, y = -982.3, z = 30.7, heading = 90.0,
    allowedItems = { gunny_pistol = true, gunny_mag_pistol = true },
    requirements = { jobs = 'police', onDuty = true },   -- without it anyone could loot it
  })
end)
```

### CreateContainer(data) — SERVER, WAITS
- Makes a NEW container every call (in resource start that is a twin per restart: use EnsureContainer for permanent ones).
- Persistent fields: `x, y, z` (required), `name` ('Stash'), `type` ('stash'), `slots` (20), `maxWeight` (100.0), `heading` (0), `prop` (`Config.ContainerDefaultProp`; `false` = no prop, prompt only), `locked`, `ownerCharId`, `accessCharId` (one character's), `allowedItems`, `requirements`/`require`, `key` (must be free: `'the key "k" is already a container\'s'`), `propertyId`, `createdBy`.
- `persist = false` (run container, resource-only): never saved, no row, id above 2^32; contents in memory only and never unloaded. Only your resource can change or delete it. Extra fields: `tag` (released with `ReleaseTag`; a tag whose run has ended refuses creation), `items` (starting contents `{ { item, amount, metadata, slot? } }`, made like StoreGive, all or nothing: `'items N (item): reason'`), `prop = false`, `placed = true` with `rx`/`ry` (exact pose, no ground snap), `interior = true` (prop waits for the MLO), `reason` (log). `slots` 1..65535, `maxWeight` > 0 checked. No `key` allowed (`'a container with persist = false has no key: it is never saved'`). It goes when your resource stops, its tag is released or the server stops: open screens close, leftovers are logged lost.
- Returns the def table (with `containerId`), or `false, reason` (no x/y/z, key taken, a requirements shape refused, an item that cannot go in, ended tag, `'Could not save that (database error)'`).

```lua
local safe = exports.whip_core:CreateContainer({
  persist = false, tag = 'heist:' .. jobId, name = 'Safe',
  x = 255.1, y = 225.4, z = 101.9, prop = false,
  items = { { item = 'cash', amount = 5000 } },
  requirements = { charIds = crewCharIds },
})
```

### GetContainer(ref) — SERVER
- `ref`: container id, `{ id = n }` or `{ key = 'k' }`. Returns the cached definition (`containerId, name, type, slots, maxWeight, ownerCharId, accessCharId, locked, x, y, z, heading, prop, allowedItems, createdAt, createdBy, key, declared, requirements, propertyId`; run containers also `persist = false, owner, tag`) or nil. Contents: StoreRead.

### UpdateContainer(containerId, data) — SERVER, WAITS
- Changes only the given fields: `name, type, slots, maxWeight, ownerCharId, accessCharId, locked, x, y, z, heading, prop, allowedItems, requirements, key` (`propertyId` is not updatable). Saved, re-sent to every client; viewers are held to the change on their next move.
- `accessCharId` / `ownerCharId`: `0` clears (public / unowned); omitted leaves it. The only way to change the one-character lock after creation.
- `allowedItems = {}` clears the whitelist. `requirements = false` (or `{}`) clears. `key = false` removes the key; a key held by another container: `'the key "k" is already container #N\'s'`; key format as EnsureContainer.
- Fewer `slots`: `'slot N still holds something — empty the slots above M first'`.
- One change at a time per container; a second waits up to 5 s: `'that container is being changed — try again in a moment'`.
- Another resource's run container: `'container #N is <res>\'s'`. Returns `true` or `false, reason` (`'Container not found'`, `'Could not save that (database error)'`).

```lua
exports.whip_core:UpdateContainer(containerId, { accessCharId = player.charId, locked = false })
```

### DeleteContainer(containerId) — SERVER, WAITS
- Deletes the definition, contents and its shop prices in one transaction; contents logged lost; viewers dropped; clients told.
- Refused while a shop sells from it: `'Shop #N (name) uses this container for its stock. Unlink it from the shop first.'`; owed write not settled: `'Its contents could not be saved first. Try again in a moment.'`; another resource's run container. Returns `true` or `false, reason`.

## Panels: OpenPanel, ClosePanel and the hooks

A panel is a server-held slot grid opened beside the player's inventory, with drag and drop and no NUI of your own. Its contents are in memory until you take them. Address: `{ kind = 'panel', id = id, slot = n }`.

### OpenPanel(source, config) — SERVER
| Field | Type | Default | Meaning |
|---|---|---|---|
| `id` | string \| number | required | 1-80 characters (`'a panel id is a string or number of 1 to 80 characters'`). Ids are global: another resource's open id is refused `'Panel id "x" is already open by <res>. Pick an id only your resource uses, like "<you>:x"'`. Same player + same id again: no-op `true` |
| `label` | string | `'Panel'` | Header |
| `slots` | number | 10 | UI shows at most 5 per row |
| `items` | `{ [slot] = { item, amount, metadata } }` | | Initial contents, copied in; ignored when the panel is already open |
| `maxWeight` | number | nil = unlimited | kg; client gets `panelWeightInfo` |
| `allowedItems` | list or keyed table | nil = any | Only keys count (no per-item caps) |
| `readOnly` | boolean | | Look only; every move refused including rearranging (`'that panel is read-only'`) |
| `onValidate` | `(ctx) → ok, reason` | | Before a player's move |
| `onChange` | `(ctx)` | | After a player's move landed |
| `onClose` | `(ctx)` | | Once, when the last viewer leaves: `ctx = { panel, source, items }` |

- Returns `true` or `false, reason` (`'a panel needs a config with an id'`, `'Player not loaded'`).
- Several players can share one id (same resource): they share ONE items table. Hooks belong to the panel: the first OpenPanel for the id that brings any hook sets them for all viewers; later openers' hooks are ignored while open.
- Contents live in memory: whip saves the player's side of a move, not the panel's. A crash before `onChange`/`onClose` hands them to you loses them. Save in `onChange`, or use a store kind with `persist`.

### The three hooks
| Hook | When | Contract |
|---|---|---|
| `onValidate(ctx)` | Before a player's move into, out of or within the panel, a Split, or a developer Destroy | Only a literal `false` refuses (`false, 'reason'` shows the reason, default `'Not allowed'`). An error refuses (`'The panel could not verify this move'`). Anything else allows |
| `onChange(ctx)` | After the move/Split/Destroy landed and was saved | React (pay, start a machine). `ctx.items` = what the panel holds now (copy). Errors are logged; nothing rolls back |
| `onClose(ctx)` | Once, last viewer gone (ClosePanel, disconnect, resource stop) | Save what was left: `ctx.items`. Without one, or if it errors: each character gets back what they put in and did not take out (at their feet if pockets are full, unless dropping is off); the resource's own stock goes, logged lost. A `readOnly` panel with no onClose gives nothing back |

`ctx` for onValidate/onChange (`WhipPanelHookCtx`):
| Field | Meaning |
|---|---|
| `source` | The player moving |
| `panel` | The panel id |
| `direction` | `'in'`, `'out'`, `'within'` (panel to panel slot; a Split is one) |
| `slot`, `otherSlot` | Panel slot, and the slot at the other end |
| `other` | The other store as an address, e.g. `{ kind = 'player', id = src, sub = 'player', slot = 4, label = … }`; nil when destroying |
| `otherName` | Client-facing name of the other store |
| `destroyed` | true for a developer Destroy (direction `'out'`, no `other`) |
| `item`, `amount`, `metadata` | What moves |
| `swap` | onValidate: true on the returning half of a swap (also inside one panel) |
| `replacing` | onValidate: forward half of a swap, `{ item, amount, metadata }` going back; nil when nothing is displaced |
| `items` | onChange only |
| `host` | RegisterPanelItem only: the item the panel belongs to |

- Your own StoreGive/StoreTake/SetItemMetadata into a panel skip onValidate/onChange; slots, maxWeight, allowedItems and stack sizes still apply. Every viewer is repainted (`whip_core:client:updateExternalPanelSlot`).
- Act on what a player drags in from `onChange`, never `onValidate`: by then it has arrived.

```lua
local PRICES = { gold_ring = 150, old_watch = 80 }
exports.whip_core:OpenPanel(source, {
  id = 'pawn:' .. source, label = 'Sell to the pawn shop', slots = 1,
  allowedItems = { 'gold_ring', 'old_watch' },
  onChange = function(ctx)
    if ctx.direction ~= 'in' then return end
    local taken = exports.whip_core:StoreTake({ kind = 'panel', id = ctx.panel, slot = ctx.slot })
    if taken then exports.whip_core:PayPlayer(ctx.source, PRICES[taken.item] * taken.amount, { method = 'cash', reason = 'pawn shop' }) end
  end,
})
```

Output-only tray: `onValidate = function(ctx) if ctx.direction == 'in' then return false, 'This tray is output only' end end`.

### ClosePanel(source, panelId?) — SERVER, WAITS
- Closes one panel for one player (id matched directly, then by `tostring`), or every panel they hold when `panelId` is omitted. If they were the last viewer, `onClose` runs and the panel is gone (a re-open starts a fresh instance).
- Returns `true`, or `false, 'No such panel open'`.

Cleanup: panels close on disconnect and when the opening resource stops (its hooks are dropped; contents of an opened panel go back to depositors). When whip_core stops, deposits go back to pockets only (anything that does not fit is lost and said). A player may hold several panels at once; name the one to close.

## Items that hold items: RegisterPanelItem

### RegisterPanelItem(itemKey, config) — SERVER
- Makes an item open a panel from its `defaultAction` or the context action named in `config.action` (registered for you; several items may share one action, the handler dispatches by item). Contents live in the item's metadata (`metadata[storageKey]`, default `metadata.slots`) and are folded back on every change, so they travel with the item. whip_core's `wallet` (3 slots, `allowedItems = { 'cash', 'id_card' }`) and `duffle_bag` (25 slots) are declared this way.
- Register the item first (RegisterItem) and with `stack = false`.

| Field | Type | Default | Meaning |
|---|---|---|---|
| `slots` | number | 3 | |
| `label` | string \| `(host) → string` | item name | A function that errors or returns a non-string falls back to the item name |
| `storageKey` | string | `'slots'` | Metadata key for a plain slot list |
| `allowedItems` | list or keyed table | any | Fixed at registration; only keys count |
| `action` | string | item's `defaultAction` | Context action that opens it |
| `canOpen` | `(host) → ok, reason` | | Runs before `read`; only `false` refuses (`reason` or `'You cannot open that.'`); an error refuses (`'You cannot open that right now.'`) |
| `read` | `(host) → items` | `metadata[storageKey]` | Project the item's own shape into `{ [slot] = { item, amount, metadata } }`; an error opens nothing |
| `write` | `(host, items) → metadata` | sets `metadata[storageKey] = items` | Fold slots back; must ONLY build and return a metadata table (also run on a copy to check each move). Error or non-table result refuses the move (`'The <label> could not take that'`). `uid` is restored if you drop it |
| `onValidate` | `(ctx) → ok, reason` | | OpenPanel's ctx plus `ctx.host` |
| `onChange` | `(ctx)` | | After the move landed and was folded; `ctx.host` read after the fold, `ctx.items` |

- Not taken (silently ignored): `maxWeight`, `readOnly`, `onClose`, per-item caps such as `maxPerSlot` in `allowedItems`. Enforce caps and read-only views in `onValidate`.
- With neither `read` nor `write`, an empty-slots metadata generator `{ [storageKey] = {} }` is registered for the item unless it already has one of its own.
- `host` = `{ source, container, slot, addr, item, amount, metadata }`, re-read fresh each time (follows the item if it moves within the pockets by `uid`). `container` is the pocket; `addr` (`{ kind = 'player', id, sub, slot }`) is ready for GetItemAt, SetItemMetadata, StoreTake. If the host leaves the pockets the panel closes (`'That item is no longer in your inventory'`).
- If the host changed outside the panel (a shot, a reload), the panel is re-read and the move refused: `'That changed while it was open. Try again.'`.
- Panel id is made up by WHIP (`<action>_<source>_<uid>` or `<action>_<source>_<container>_<slot>`); treat it as opaque and find it with `GetOpenStores(source)` by `label`.
- Last-resort failure: a fold that fails after the move landed logs the move, shuts the panel and blocks that item (by uid) from opening until whip_core restarts.
- Returns `true`, or `false, reason` with nothing changed: config not a table, item key not a string, `'item "x" is not registered'`, `'item "x" has no defaultAction and the registration named no action'`, `'item "x" stacks, and a panel item cannot: …'`, `'panel item "x" belongs to <res>'`, `'panel item "x" cannot use action "a": …'` (another resource holds the action). Removed when your resource stops; re-register from `whip_core:onReady` / `Whip.register`.

```lua
Whip.register(function()
  Whip.core:RegisterItem('mymech_toolbox', {
    name = 'Toolbox', weight = 2.0, stack = false,
    defaultAction  = 'mytools:open_toolbox',
    contextOptions = { { action = 'mytools:open_toolbox', label = 'Open' } },
  })
  Whip.core:RegisterPanelItem('mymech_toolbox', { slots = 6, label = 'Toolbox', allowedItems = { 'wrench', 'screwdriver' } })
end)
```

Custom shape (whip_gunny magazine slot, condensed):
```lua
exports.whip_core:RegisterPanelItem(weaponItem, {
  action = 'whip_gunny:open_weapon', slots = 1, label = cfg.label .. ' Mag',
  read  = function(host) local m = host.metadata.magazine; if not m then return {} end
            local item, md = GunnyMagazineOut(m); return { [1] = { item = item, amount = 1, metadata = md } } end,
  onValidate = function(ctx)
    if ctx.direction ~= 'in' then return true end
    if not Config.IsMagCompatible(ctx.host.item, ctx.item) then return false, 'That magazine does not fit this weapon' end
    if ctx.host.metadata.magazine and not ctx.swap and not ctx.replacing then return false, 'Remove the current magazine first' end
    return true
  end,
  write = function(host, items) local held = items[1]
            host.metadata.magazine = held and GunnyMagazineIn(held.item, held.metadata) or nil; return host.metadata end,
  onChange = function(ctx) --[[ post-commit only: touch the ped here ]] end,
})
```

## Events, client messages, DB tables, config

Public server events (any resource can fire these; ask the API for truth):
- `whip_core:container:opened` `{ containerId, source, charId }` — server opened a stash on someone's screen (E, OpenStore); their game may still decline it.
- `whip_core:item:added` / `whip_core:item:removed` `{ source, item, amount, count, reason?, by? }` and `whip_core:inventory:changed` `{ source }` — pocket changes from any store call (see inventory-items.md).

Internal net events (whip_core's own; do not call): server `whip_core:server:storeMove`, `quickMove`, `openContainer` (rate 500 ms, burst 3), `closeContainer` (250 ms, burst 5), `closeStore` (250 ms, burst 5), `closePanelSession` (500 ms, burst 3; `''` = all), `dropToGround`, `dropOneToGround`, `pickupGroundItem`, `quickPickupGroundItem`, `groundPickupRoom` (callback), `splitGroundItem`, `destroyGroundItem`, `throwStarted`, `throwLaunched`, `throwItemLanded`, `throwSettled`, `placeItem`; admin (`whip.devtools`): `cmGetAll`, `cmOpenContainer`, `createContainer`, `updateContainer`, `deleteContainer`. Client: `whip_core:client:storeDelta` `{ storeId, slots = { ['n'] = slot|false }, weight }`, `openStore`, `storeClosed`, `openContainer`, `openContainerDenied`, `containersSync`, `containerCreated`, `containerUpdated`, `containerDeleted`, `openPanel`, `closeExternalPanel`, `updateExternalPanelSlot`, `panelWeightInfo`, `panelReadOnly`, `groundItemCreated`, `groundItemUpdated`, `groundItemDeleted`, `groundItemSettled`, `groundItemsSync`, `groundItemsBatchAdd`, `heldItem`, `ignitionState`, `updateIgnitionSlot`.

DB tables:
- `ground_items` (`id, item, amount, metadata JSON, x, y, z, heading, placed, rx, ry, createdAt, createdBy` FK characters SET NULL).
- `containers` (`containerId, name, type, slots SMALLINT, maxWeight, ownerCharId, accessCharId, locked, x, y, z, heading, prop` ('' = none), `allowedItems JSON, createdAt, createdBy, key` UNIQUE VARCHAR(100), `declared JSON, requirements JSON, propertyId`).
- `container_inventory` (`containerId, slot, item, amount, metadata`; PK containerId+slot; CASCADE).

Config: `Config.ContainerInteractRange` 2.5, `ContainerStreamRange` 100.0, `ContainerPrompt` `'face'`, `ContainerDefaultSlots` 20, `ContainerDefaultWeight` 100.0, `ContainerDefaultProp` `'prop_cs_cardbox_01'`, `GroundItemPickupRange` 2.0, `GroundItemStreamRange` 100.0, `GroundItemCellSize` 50, `GroundSyncInterval` 1, `DefaultGroundProp`, `PlaceItemRange` 10.5, `MaxGroundPilesPerDrop` 50, `DropOnFullInventory` true, `ThrowKnockdown { Enabled, MinSpeed 8.0, RagdollMs 2500, Npcs }`, `VehicleStorageKeepRange` 5.5, `FlushInterval` 1000.

## Gotchas

1. `StoreCount` returns `false` (not 0) for an unreachable store: `StoreCount(a, 'x') >= 5` throws. Check `n and n >= 5`.
2. `GetItemAt` answers `nil` for empty and `false, reason` for a bad address; `if not item` covers both, but only `false` carries a reason.
3. `StoreMove` with `amount = 0` is refused; leave `amount` out for the whole stack.
4. `StoreTake` destroys. To relocate an item use `StoreMove`; a take-then-give pair can fail halfway and lose it.
5. `StoreGive` into pockets refuses when full; rewards should use `AddItem` (drops at the feet). See inventory-items.md.
6. A custom kind handle must be `{ id = ... }`: a handle carrying your live table is copied across the export boundary and `set` writes into the copy (item vanishes).
7. Custom kind `resolve/get/set/clear` must not yield; storage in memory, DB only from `persist`.
8. Custom kind names: keep to letters, digits, `_`, `-`, at most 20 chars. `RegisterStoreKind` accepts anything, but addresses sanitise the kind (strip, cut to 20), so a longer or punctuated name registers and is then unreachable.
9. A custom kind's `beforeMove` gets no `ctx.source`; `afterMove` gets it only for player drags (StoreMove/StoreGive from a resource leave it nil).
10. `authorize` must return a literal `true`; `1` or `'yes'` refuses. `instanceId` must start with `'<kind>:'` or `OpenStore` refuses it.
11. `OpenStore` returning `true` does not prove the screen opened: the player's game declines when another UI is up and releases the view itself.
12. Always pair `OpenStore` with `CloseStore` outside SecureEvent handlers; the player stays a viewer (drags count) until then.
13. `skipAccess` opens are never re-checked on later moves; access-checked opens are re-checked every move (lock, owner, duty, keycard).
14. `CreateContainer` in resource start makes a twin each restart; use `EnsureContainer`. EnsureContainer does not take `ownerCharId`/`accessCharId` (UpdateContainer) and does not take `prop = false`.
15. Container `requirements` mean ANY ONE rule; an action's `require` means ALL. `require` with two rules on a container is refused.
16. A keycard named in `requirements.items` can never be stored in the container it opens.
17. Without `requirements`, `accessCharId` or `locked`, anyone can loot a container.
18. A `persist = false` container is only its creator's to update/delete and disappears with the resource, the tag or the server (contents logged lost).
19. Panel ids are one global namespace: prefix them (`'myres:bench_' .. src`). An id longer than 80 chars is refused.
20. Panel hooks are set by the first opener that brings any; a later `OpenPanel` with different hooks for the same open id is ignored.
21. Panel contents are in memory: without `onClose` (or with one that errors) depositors get their items back and your stock is destroyed; save in `onChange` if a crash must not lose them.
22. `onValidate`/`canOpen` only refuse on a literal `false`; returning `nil` allows. Errors refuse.
23. RegisterPanelItem `write` must be pure (it is run on copies to test moves); side effects belong in `onChange`. Touch the ped only in `onChange`.
24. RegisterPanelItem ignores `maxWeight`, `readOnly`, `onClose` and `maxPerSlot`; the item must be registered and non-stacking before you call it.
25. Ground items never expire; anything a resource drops stays until picked up or deleted. Always check `CreateGroundItem`'s return.
26. `GetGroundItemsNearby` uses stored coordinates; a thrown pile still flying is reported at its launch point.
27. `FindItemByUid`/`FindItemByMetadata` only see loaded places: an untouched stash or an item inside a bag/wallet is not found.
28. Metadata is sent whole to every viewer: never store secrets in it. `SetItemMetadata` merges by default; `replace` is needed to drop keys you do not name (`uid` survives unless `uid = false`).
29. During a bank payment hold (`'Paying — wait a moment'`) moves and StoreTake on that unit are refused; SetItemMetadata is not.

## Docs vs code

- StoreMove `opts.amount = 0`: docs (#storemove) and the stub say 0 means the whole slot; the export runs `Sanitize.amount`, which rejects 0 with `'Amount must be a whole number of 1 or more'` (`whip_core/server/stores.lua:1703-1706`, `server/sanitize.lua:132`).
- Reserved store-kind names: docs list `player, rawInventory, container, vehicle, panel, target, accessory`; code also reserves `basket` and `shop` (all kinds defined in stores.lua) (`server/stores.lua:3746-3747`).
- Store kind hooks: docs omit that `beforeMove` may return `'handled'` (whip then neither moves nor reverts), that `ctx` also carries `replacing`, `otherName` and `destroyed`, and that `beforeMove` ctx has no `source` while `afterMove` has one (`server/stores.lua:1886-1929`, `1992-2017`).
- Undocumented optional kind fields `label`, `afterWrite`, `weight` exist and are honoured (`server/stores.lua:102-106`, `530`, `4629-4634`).
- Kind names are sanitised on every address (`Sanitize.key(kind, 20)`) but not at registration, so a kind longer than 20 chars or with other punctuation is unaddressable (`server/stores.lua:4030`, `254-320`).
- OpenStore: docs say a player with a screen already open is refused; the server returns `true` and the client declines and releases (`client/containers.lua:386-403`).
- EnsureContainer rejects `prop = false` (`'prop must be text'`) although CreateContainer/UpdateContainer accept it (`server/containers.lua:878-882`).
- CreateGroundItem also accepts `createdBy` (charId), listed in the stub but not in the docs (`server/ground.lua:806`).
- Persistent CreateContainer and UpdateContainer do not validate `slots`/`maxWeight` ranges; only run containers (1..65535, > 0) and EnsureContainer (>= 1, > 0) do (`server/containers.lua:337-340`, `438-458`, `534-535`).
