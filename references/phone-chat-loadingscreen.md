# whip_phone, whip_chat and whip_loadingscreen

The Duo phone (architecture, app/module API, NUI messaging, items, DB, every export, callback, push and event, config), the chat (stock-chat-compatible API, commands, suggestions, modes, hooks) and the loading screen (shutdown). Built from `whip_phone` v1.1.0 (README.md, docs/FRAMEWORK.md, docs/MODULES.md, config.lua, fxmanifest.lua, client/main.lua, server/*.lua, shared/skillgames.lua, html/core/*.js, html/modules/*/module.js), `whip_chat` v1.1.0 (README, client/main.lua, server/main.lua, html/js/chat.js), `whip_loadingscreen` v1.6.2 (README, fxmanifest, html/), whip_core integration points (client/spawn.lua, server/ask.lua, server/jobs.lua, server/setup_report.lua, server/devtools.lua, types/*.lua), and doc anchors `voice-lore-calls`, `ui-library`, `guide-jobs`, `inventory`, `configuration`, `what-you-can-change`, `quickstart`, `resource-settings`.

## Contents
- Phone: architecture
- Phone: install, manifest, load order
- Phone: numbers, SIM cards, and whose data is whose
- Phone: items (phone, sim_card)
- Phone: database tables
- Phone: server exports
- Phone: client exports
- Phone: writing an app from another resource
- Phone: module definition (every field)
- Phone: the app object
- Phone: notifications (capsules)
- Phone: mount mode, CSS scoping, fold snapshots
- Phone: UI kit
- Phone: NUI structure and messaging
- Phone: request path, server callbacks, rate limits
- Phone: core callbacks
- Phone: Phone module (calls) callbacks and pushes
- Phone: Messages callbacks and pushes
- Phone: block list callbacks
- Phone: Bank callbacks and pushes
- Phone: Business callbacks, pushes, and clock-on
- Phone: skill check games and the Skill Check Tester
- Phone: events (net, local, whip_core events it listens to)
- Phone: calls and voice
- Phone: lore characters and Director cards
- Phone: client behaviour (focus, controls, keys, emotes, death)
- Phone: config.lua keys and defaults
- Phone: admin tools
- Chat: overview and install
- Chat: commands, keys, player settings, convars
- Chat: client events and exports
- Chat: server exports, hooks and modes
- Chat: routing and inbound events
- Chat: suggestions
- Chat: NUI and message format
- Loading screen
- whip_core integration summary
- Gotchas
- Docs vs code

---

## Phone: architecture

- The phone core (shell, home screen, lock screen, control centre, notifications, 3D Duo model) has **no apps**. Every app is a **module**: one JS file calling `WhipPhone.module({...})`. With none installed the home screen says "No apps installed".
- Built-in modules (`html/modules/<id>/module.js`): `phone` (order 10, dock), `messages` (20, dock), `bank` (30), `business` (35), `settings` (90), `skillcheck` (999, hidden), developer app `skilltest` (95).
- A module is UI only. Data comes from the server via `app.request(action, args)` (a whip_core SecureCallback) and live updates arrive as pushes (`on[event]`).
- whip_phone is the only WHIP satellite that talks to the database directly (its own tables, made by `server/schema.lua`). Everything else (bank, jobs, items, names) goes through whip_core exports.
- The server works out the phone and SIM on **every** request from the items the player carries (`server/sim.lua`); the page never names the number.
- Sides: `client/main.lua` owns NUI focus, opening/closing, the module list, and forwards page requests to `Whip.core:Callback`. Server files: `numbers.lua` (numbers in memory), `schema.lua`, `sim.lua`, `items.lua`, `main.lua` (exports), `contract.lua` (session, settings, contacts, messages, SIM page), `calls.lua`, `blocks.lua`, `lore.lua`, `card.lua`, `people.lua`, `bank.lua`, `business.lua`, `skillgames.lua`, `skilltest.lua`.
- Page: `html/index.html` boots `core/main.js` (importmap maps `three` and `three/addons/` to the vendored three.js 0.170). It also loads `https://cfx-nui-whip_core/html/js/page-tools.js`.
- Three display "views": `phone` (folded, bottom-right), `tablet` (unfolded, centre), `tabletP` (tablet portrait). State reported to Lua: `hidden` / `peek` / `phone` / `tablet`.

## Phone: install, manifest, load order

- Requires `whip_core` and `oxmysql`. A voice system (whip_voice, or another resource registered as WHIP's voice system) is required to *use* the phone; whip_voice is **not** a manifest dependency. Without one every phone shows `Config.VoiceDownText` over everything and dialling is refused.
- `server.cfg`: `ensure whip_phone` after `ensure whip_core`. No SQL to import: tables are created/migrated on start.
- fxmanifest: `shared_scripts { '@whip_core/lib/satellite.lua', 'config.lua', 'shared/skillgames.lua' }`; server scripts start with `'@oxmysql/lib/MySQL.lua'`, `'@whip_core/server/db_guard.lua'` (a DB that does not answer becomes an error after a limit), then numbers, schema, sim, items, main, contract, calls, blocks, lore, card, people, bank, business, skillgames, skilltest. `ui_page 'html/index.html'`, `nui_callback_strict_mode 'true'`, `dependency 'whip_core'`, `dependency 'oxmysql'`, `whip_requires '1.0'`, `whip_updates 'WHIPFX/whip_phone'`.
- `files {}` lists **one line per built-in module folder** (`'html/modules/phone/module.js'` etc.). A `*` in a folder name matches nothing there (`'html/modules/*/module.js'` shipped no apps and the phone opened empty). A new built-in app needs its own line.
- `html/preview.html` and `html/dev/` (mock.js, example/app.js Preact Garage, example_3d/app.js three.js Atlas) are not shipped to players. Serve `html/` (e.g. `python -m http.server`) and open `preview.html` to run the real phone on a mock server; `?modules=` picks built-ins.
- Schema runs in `MySQL.ready` after `Whip.ready()` (so whip_core's `characters` table exists). If the tables fail, the phone is off (`PhoneDB.ready` stays false; requests answer "The phone network is starting, try again"). If `Numbers.load()` or `Blocks.load()` fails, the phone also stays off (`server/schema.lua:194-214`).

## Phone: numbers, SIM cards, and whose data is whose

- A number belongs to a **character** (`phone_numbers.charId`); a character may own several and lock any of them. A locked number works in no phone.
- A SIM card (`sim_card`) carries one number: metadata `{ phoneNumber, owner }`. Any phone takes any SIM (right-click phone > **SIM tray**). Whoever holds the phone **is** that number: calls/texts as it, sees its contacts, messages, calls, block list.
- Numbers: 10 digits, a prefix from `Config.NumberPrefixes` + 7 random digits. Formatted `xxx-xxx-xxxx` in UI and inventory (`format = 'phone'`). Server cleans any input with `Numbers.clean` (strips non-digits, must be exactly 10).
- Minting (`server/numbers.lua`): a number is *reserved in memory* when the card is made and the row is written only the first time the SIM is used in a phone (`Numbers.activate`). After a restart an unused reserved number can be minted again; whichever card is used second gets a new number (`server/sim.lua:151-190`). Retired numbers are never minted again. Up to 200 tries per mint, nil if none found.
- Where a SIM's number comes from: given to or bought by a player → new number for them (`RegisterItemDefaultMetadata(..., { forBuyer = true })`); made for nobody (stash, Director reward) → blank `{}`, given a number the first time it is put in a phone, owned by whoever does.
- **Phone in use** (`Sim.phoneOf`): the phone opened by its own Use (by `metadata.uid`) while still carried; else the phone in accessory strip slot 1 (`{ kind='player', id=src, sub='accessory', slot=1 }`); else the first phone found (`FindItem`). The hotkey, F1 wheel and `Open` export send `first = true` and forget a Use-chosen phone.
- **SIM state** (session `sim`): `ok` (number works, `session.number` set), `nosim` (empty tray), `locked` (owner locked it), `blank` (no number could be minted, or an admin deleted its number: "SIM not working"). Server `Sim.numberOf` maps them to refusals `'No SIM card'`, `'SIM locked'`, `'This SIM does not work'`; no phone at all → `'You need a phone'`.
- Scope of data:
  - **SIM-scoped** (`phone_numbers.prefs` JSON or number-keyed tables): contacts, messages, calls, block list, home arrangement (`prefs.home`), wallpaper (`prefs.wallpaper`), sounds (`prefs.ringtone`, `messageTone`, `notifyTone`, `soundVolume`), contact card (`prefs.card`). Someone using your SIM sees your wallpaper and hears your ringtone.
  - **Device-scoped** (phone item metadata): `sim` (the tray), `settings` (DND, `theme`, and the wallpaper/sounds used while no SIM is in), `home` (arrangement while no SIM).
  - **Character-scoped**: Bank and Business always act as the character holding the phone, whatever SIM is in it (need a phone item).
- A SIM with no wallpaper shows the phone's; the owner's old phone wallpaper is moved onto their SIM once (`contract.lua:105-124`). Missing keys fall back to `Config.Defaults`.
- Prefs JSON is capped at 16000 bytes ("Too much to keep on a SIM"); one write per SIM at a time, waiting up to 5 s ("Busy, try again") (`numbers.lua:104-123`).
- Retired numbers: the admin Phones panel never deletes a number row; it sets `retiredAt` (and `renamedTo` for a change). A changed number's cards are rewritten with the new number on next resolve (forwarding follows up to 8 renames); a deleted number's cards go `blank`.
- Session `name` is the **SIM owner's** character name (not the holder's); no SIM → nil (page shows "Your phone").

## Phone: items (phone, sim_card)

Registered in `server/items.lua` inside `Whip.register` (re-run after a whip_core restart):

| Item | Registration |
|---|---|
| `phone` | `RegisterItem('phone', { name='Phone', desc='Also folds into a tablet.', weight=0.2, type='electronics', stack=false, usable=true, image='html/img/items/phone.webp', prop='prop_npc_phone_02', contextOptions={ { action='phone_sim_tray', label='SIM tray' } } })` |
| `sim_card` | `RegisterItem('sim_card', { name='SIM Card', desc='A phone number. Put it in a phone.', weight=0.01, type='electronics', stack=false, image='html/img/items/sim_card.webp', metaFields={ { key='phoneNumber', label='Number', format='phone' } } })` |

- `RegisterItemDefaultMetadata('sim_card', newCard, { forBuyer = true })`: `newCard(_, ctx)` returns `{ phoneNumber = Numbers.mint(), owner = ctx.charId }`, or `{}` when no `ctx.charId`.
- `RegisterPanelItem('phone', { action='phone_sim_tray', label='SIM tray', slots=1, storageKey='sim', allowedItems={ 'sim_card' }, onChange=simChanged })`. The card lives in `metadata.sim[1]` (a JSON round-trip may make the key `'1'`). `onChange` sends `whip_phone:client:refresh` to the holder and ends a call on a number that left (`Calls.recheck`).
- If the accessory strip exists: `RegisterAccessorySlot({ slot=1, label='Phone', accepts='phone', icon='phone' })`: slot 1 takes phones only while whip_phone runs.
- `RegisterUseHandler('phone', fn)` returns **`false`** (item kept; `true`/nothing would consume it). It calls `Sim.choose(source, metadata.uid)` and `TriggerClientEvent('whip_phone:client:open', source, 'phone', true)`.
- Item names `phone` and `sim_card` are reserved by WHIP (doc `patterns-registering`).
- Getting a phone: sell both in a shop or take them from `/whip` → Economy → Items, put the SIM in the tray, press F3.

## Phone: database tables

All `ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci`, created by `server/schema.lua`.

| Table | Columns | Notes |
|---|---|---|
| `phone_numbers` | `phoneNumber CHAR(10) PK`, `charId INT UNSIGNED NULL` (FK `characters.charId` ON DELETE CASCADE, index `idx_charId`), `loreKey VARCHAR(64) NULL` (UNIQUE `uk_loreKey`), `locked TINYINT(1) DEFAULT 0`, `prefs TEXT NULL` (JSON), `retiredAt TIMESTAMP NULL`, `renamedTo CHAR(10) NULL`, `createdAt` | Old `uk_charId` unique key is dropped on migrate (several numbers per character). `charId` NULL + `loreKey` = a lore character's number. |
| `phone_contacts` | `contactId PK AI`, `phoneNumber` (FK, `idx_phone`), `contactName VARCHAR(50)`, `contactNumber CHAR(10)` (`idx_contact`), `createdAt` | The SIM's contacts; max 500 per SIM. |
| `phone_messages` | `messageId PK AI`, `senderNumber`, `receiverNumber` (both FK), `content VARCHAR(500)`, `readAt TIMESTAMP NULL`, `blocked TINYINT(1)`, `createdAt` | Indexes `idx_sender`, `idx_receiver`, `idx_pair`, `idx_pair_in`, `idx_shown_in`. |
| `phone_calls` | `callId PK AI`, `callerNumber`, `calleeNumber` (FK), `status VARCHAR(12)` default `'ringing'` (`ringing|answered|missed|declined|unavailable`), `startedAt`, `answeredAt`, `endedAt`, `blocked` | Indexes `idx_caller`, `idx_callee`, `idx_caller_id`, `idx_callee_id`, `idx_callee_shown`. |
| `phone_blocks` | `phoneNumber`, `blockedNumber` (PK both; both FK; `idx_blocked`), `createdAt` | Collation copied from `phone_numbers.phoneNumber` so the FK matches on older DBs. |

- Numbers and block lists are held **in memory** (loaded at start, written through); reloads build on the side and swap only on success.
- Lore migration is separate: if it fails, only lore numbers are off (`PhoneDB.lore = false`).
- whip_core's admin Phones panel (`server/devtools.lua`) reads/writes these tables by number (not `phone_blocks`) and then calls `exports.whip_phone:ReloadCache()`.

## Phone: server exports

All in `server/main.lua`. None wait.

### Notify(src, n) — SERVER
- `n`: `{ app, title, text, kind, args, ... }` (fields under "Phone: notifications"). Sends `whip_phone:client:notify`.
- Returns `false` if `n` is not a table, else `true`.

### Push(src, module, event, data) — SERVER
- Runs `on[event](app, data)` of module `module` on that player's page. Same as `TriggerClientEvent('whip_phone:client:push', src, module, event, data)`. Module `'contacts'` is special: any event reloads shared contacts (e.g. `Push(src, 'contacts', 'changed')`).
- Returns `true`.

### Open(src, mode) — SERVER
- `mode`: `'phone'` (folded) or `'tablet'` (straight into tablet). Anything else is treated as `'phone'`. Triggers `whip_phone:client:open` (fromItem false, so the first phone is used). Returns `true`.

### Close(src) — SERVER
- Triggers `whip_phone:client:close`. Returns `true`.

### SetSession(src, session) — SERVER
- Replaces the page's session (`{ number, name, sim, settings, home, card, mine }`) at once (forced resend), via `whip_phone:client:session`. Returns `true`.

### ReloadCache() — SERVER
- For the admin panel after changing `phone_numbers`/contacts. In a thread: reloads numbers, then block lists (3 tries, 2 s apart; follows retired numbers), then `Sim.recheckRetired()` (fixes online players' retired cards now), then `TriggerClientEvent('whip_phone:client:refresh', -1)` (open phones refetch their session). Returns `true` immediately.

## Phone: client exports

All in `client/main.lua`.

### Open(mode?) — CLIENT
- `'phone'` or `'tablet'`. Runs `openPhone(mode)` in a new thread, as the hotkey does (first phone). Returns nothing. Refused (notification) when dead ("You can't use your phone right now") or when the server refuses the session ("You need a phone").

### Close() — CLIENT
- Puts the phone away (also gives up a held `RunApp` with `{ passed=false, why='cancelled' }`). Returns nothing.

### IsOpen() — CLIENT
- `true` while the player is using the phone (it has NUI focus).

### GetState() — CLIENT
- `'hidden'`, `'peek'`, `'phone'` or `'tablet'` (what the page shows).

### Notify(n) — CLIENT
- Local version of the server export (no return value; ignored unless `n` is a table).

### Push(module, event, data) — CLIENT
- Local version of the server export.

### RegisterModule(def) — CLIENT
- `def = { id, script?, ns? }`. Must be called from another resource (`GetInvokingResource()`; else `false, 'call RegisterModule from your own resource'`).
- `id`: string, `#id <= 32`, matching `^[a-z][a-z0-9_%-]*$` (first char a letter). Else `false, 'id must be lowercase letters, digits, _ or -'`.
- An id in `Config.Modules` or `Config.DeveloperApps` → `false, 'that id is a built-in module'`.
- An id held by another **running** resource → `false, 'the phone app "<id>" belongs to <res>'`. Same resource again replaces its own.
- `script`: path inside the calling resource (default `'html/module.js'`, leading `/` stripped); loaded as `https://cfx-nui-<res>/<script>` with a `?t=<now>` cache-buster. List it in your own `files {}`.
- `ns`: request namespace prefix, default the calling resource's name. `app.request('cars')` calls `<ns>:cars`.
- Returns `true`, or `false, why`. Sends the module to an already-loaded page at once; otherwise it goes out with the page's `init` list.
- Removed automatically when the registering resource stops (`onResourceStop`). Re-register on `onResourceStart` of `whip_phone` (the list is in whip_phone's memory and resets on its restart).

### UnregisterModule(id) — CLIENT
- Only the caller's own: `false, 'there is no phone app "<id>"'` / `false, 'the phone app "<id>" belongs to <res>'`; else `true`.

### RunApp(id, args?) — CLIENT, WAITS
- Opens the phone **held to one app** and blocks (`Citizen.Await`) until it answers. Call from a thread.
- The phone comes out unfolded to a tablet (or unfolds if out); no home, no folding, no other app, no control centre; Back is the app's own `back()`; all game controls blocked (`BlockControls('whip_phone:forced', { all = true })`).
- `args` table goes to the module's `open(app, args)`.
- Returns the app's `app.done(result)` table (non-table → `{}`); or `{ passed = false, why = 'cancelled' }` when put away (key, death, logout, ragdoll, page close) or Back is not handled (`back()` returns anything but `true`); or `nil, why` when it cannot start: `'busy'` (already held), `'no app'` (not a built-in in `Config.Modules`, not a dev app with dev mode on, not registered), `'not ready'` (page not loaded), `'dead'`.
- Afterwards the phone returns to its previous state (put away, or back to the folded phone).

### IsHeld() — CLIENT
- `true` while a `RunApp` hold is active.

## Phone: writing an app from another resource

```lua
-- fxmanifest.lua
files { 'html/phone_app.js' }
dependency 'whip_phone'

-- client.lua
local function register()
    if GetResourceState('whip_phone') ~= 'started' then return end
    exports.whip_phone:RegisterModule({ id = 'garage', script = 'html/phone_app.js' })  -- ns = resource name
end
CreateThread(register)
AddEventHandler('onResourceStart', function(res) if res == 'whip_phone' then register() end end)

-- server.lua: answer app.request('cars')
exports.whip_core:SecureCallback('my_garage:cars', { rateLimit = 250, params = { { 'args', 'any' } } },
    function(source, player, args) --[[ validate every field of args ]] return {} end)
```

- **Keep `params = { { 'args', 'any' } }`**: whip_core passes the handler only params the schema names; without it every request arrives as `{}`.
- Answer data (any value; `nil` = nothing), or `false, 'reason'` to refuse (the module gets `err.reason`).
- `Whip.core:Callback` times out after 10 s; a timeout is a refusal.
- Built-in modules use namespace `whip_phone:<id>:<action>`; built-ins go in `Config.Modules` plus a `files {}` line.
- Developer apps: list in `Config.DeveloperApps`; shown only while that player's developer mode is on (`/w`); come and go live (`whip_core:devtools:modeChanged`). Their requests still reach the server: check `exports.whip_core:HasDevTools(source)` in every handler.
- Times may be `os.time()` seconds or ms (UI's `toMs` treats `< 1e12` as seconds). Numbers are digit strings like `'6895550142'`.

Minimal module:
```js
(() => {
  const { kit: K, icons: I } = window.WhipPhone;
  WhipPhone.module({
    id: 'notes', name: 'Notes', version: '1.0.0', order: 50, icon: I.compose,
    state: () => ({ list: [], loaded: false }),
    async open(app) { app.state.list = await app.request('list').catch(() => []); app.state.loaded = true; },
    render(app, view) {
      const rows = app.state.list.map((n) => K.row({ label: n.title, sub: n.preview, act: 'openNote', d: { id: n.id } }));
      return K.screen('list', K.title('Notes') + K.scroll(rows.length ? K.list(rows) : K.empty({ title: 'No notes' })));
    },
    actions: { openNote(app, d) { app.toast('Note ' + d.id); } },
  });
})();
```

- **Own namespace:** pass `ns` when your resource already has SecureCallbacks named `<res>:state` etc. for its
  own UI: `RegisterModule({ id = 'courier', script = 'web/phone/courier.js', ns = 'my-res:phone' })` makes
  `app.request('state')` call `my-res:phone:state`.
- **Buttons on a server notification:** `exports.whip_phone:Notify(src, { app = '<your module id>', key = 'offer',
  actions = { { act = 'accept', label = 'Accept', tone = 'accept' } }, data = { id = 'f12' } })` runs your module's
  `actions.accept(app, data)`; `Push(src, '<id>', 'gone', {})` + `app.dismiss('offer')` in `on.gone` takes it down.
- **Try it in a browser:** copy `whip_phone/html` somewhere, add your module to `dev/mock.js` the way it adds
  the `example` app (`{ id, script, ns, external = true }` in the `init` list, your request names in `handlers`),
  serve the folder and open `preview.html?modules=<id>`. `window.whipPhone.os.openApp('<id>')` opens it.

`window.WhipPhone` (frozen): `{ version, module(def), kit, icons }`. `module(def)` → `os.register(def, meta)`; returns `false` (console warning) when the id fails `/^[a-z][a-z0-9_-]{0,31}$/` or the def has neither `render` nor `mount`. Registering an id again unregisters the old one first. A script that loads but never calls `WhipPhone.module` with its id logs a warning.

## Phone: module definition (every field)

| Field | Meaning |
|---|---|
| `id` | `^[a-z][a-z0-9_-]{0,31}$`, unique. |
| `name` | Home-screen label (also Settings > Apps). |
| `icon` | SVG string drawn in `currentColor` inside the phone's icon capsule. Unknown/missing → bell. |
| `order` | Home sort (default 100), then by name. |
| `dock` | `true` pins to the dock (phone shows 4, tablet 6). |
| `hidden` | Kept off the home screen (e.g. `skillcheck`). |
| `version` | Shown in Settings > Apps. |
| `css` | CSS text, auto-scoped to the app (see CSS). Also embedded in fold snapshots. |
| `globalCss` | Unscoped CSS (urls resolved), e.g. `.banner[data-app="<id>"]`. |
| `statusBar` | `'dark'`, `'light'`, or `(app) => 'dark'|'light'`; default white. Home bar and controller highlight follow it. |
| `state()` | Returns initial state (`app.state`). |
| `init(app)` | Once, on load. |
| `session(app, session)` | A session arrived (also called on register if one already exists). Reload data. |
| `open(app, args)` / `close(app)` | App opened (args from a notification tap, `app.open`, or `RunApp`) / left. |
| `render(app, view)` | Returns HTML. `view = { size: 'phone'|'tablet', portrait, console }`. Every display renders at once, so must be side-effect free. A module needs `render` **or** `mount`. A throw shows an error screen for that app only. |
| `mount(app, el, view)` / `update(app, el, view, changed)` / `unmount(app, el)` | Mount mode (own DOM, any library). |
| `overlay(app, view)` | HTML over everything, even other apps (Phone's call screen). Return `''` for none. |
| `presence(app, now, before)` | Visibility changed; both `{ visible, app, locked }`. |
| `actions` | `{ name(app, data, el, view) }`, run by `data-act="name"` elements in the app; `data` is the element's `data-*` attributes. |
| `bind` | `{ name(app, value) }` for `data-bind="name"` inputs; `data-enter="action"` runs an action on Enter. |
| `on` | `{ event(app, data) }`: pushes. |
| `back(app)` | Return `true` if handled; otherwise the app closes to home (or, held by RunApp, gives up). |
| `route(app)` | Short sub-screen name; keeps the controller highlight per screen. |
| `tab(app, dir)` / `tabLabel(app)` | LB/RB (`dir` -1/1). Return `true` if handled. |
| `input(app, cmd, down, info)` | Raw buttons first: `cmd` in `up down left right a b x y lb rb menu home`; `down` false on release; `info = { repeat, from: 'pad'|'keys' }`. Return `true` to take it. LB arrives as a press only, on its release. |
| `keys` | `'all'`: while open, W/A/S/D, Space, Q, E reach the app as up/left/down/right, A, LB, RB, and Lua blocks the `move` control group (`whip_phone:keys`). |
| `x(app)` | Controller X: `{ label, run }` or `null`. |
| `badge(app)` | Number on the icon. |
| `info(app)` | One line under the tile in the controller layout. |
| `destroy(app)` | (code only, `os.js:300`) called when the module is unregistered. |

- After every action, binding, push and resolved request the phone re-renders. Mutate `app.state` and return; call `app.render()` only from timers. `app.render()` inside `mount`/`update` is ignored.
- Use `os:` actions for the shell (`os:back`, `os:home`, `os:open` with `data-app`); never reuse `os:` names.
- `data-act` elements are clickable and controller-reachable; `data-hint="Call"` labels the A button.
- No iframes (the fold snapshot cannot copy them).

## Phone: the app object

| Member | Meaning |
|---|---|
| `app.id`, `app.esc` | (code) the module id; HTML escape helper. |
| `app.state` | Module state (assigning it re-renders). |
| `app.request(action, args)` | Promise of `<ns>:<action>`. Rejects with `err.reason` (`'not allowed'`, `'refused'`, `'no response'`, `'unavailable'`, or the server's reason). Re-renders after. |
| `app.notify(n)` | Capsule from this app (`app` forced to the module id). Returns capsule id, or `false` when DND held it back. |
| `app.dismiss(key)` | Takes down this app's capsule by `key` or by id. |
| `app.toast(text)` | Short message at the bottom. |
| `app.open(id = self, args)` | Open another (or own) app. |
| `app.close()` / `app.back()` | Home / same as Back. |
| `app.attention(on = true)` | Raise a put-away phone into view; `false` lets it drop again (unless the player opened it). |
| `app.ring(kind)` | `'ring'` (SIM ringtone, looping), `'back'` (ringback), `null` (quiet). |
| `app.fold()` | (code) fold/unfold the Duo. |
| `app.contacts` | Shared: `list`, `sorted`, `loaded`, `load()`, `find(number)`, `name(number)`, `save(c)`, `remove(id)`. |
| `app.blocks` | SIM block list: `list` (`{ number, time }`), `loaded`, `load()`, `has(number)`, `add(number)`, `remove(number)` (reject with `err.reason`). |
| `app.settings` | `get(key)`/`set(key, value)` for `wallpaper`, `dnd`, `ringtone`, `messageTone`, `notifyTone`, `soundVolume`; `wallpapers()`; `sounds('ringtone'|'alert')`; `preview(kind, id)`; `stopPreview()`; `isConsole()`. `get('layout')` is always `'auto'`. |
| `app.callVolume(value?)` | (code) reads/sets the voice system's "Phone call volume" (`voice.callVolume` player setting); resolves number or `null`. |
| `app.session` | Current session (`{ number, name, sim, settings, home, card, mine }`). |
| `app.console` | `true` in controller layout. |
| `app.active` / `app.visible` | This app is open / the phone is out. |
| `app.presence` | `{ visible, app (id or null), locked }`. |
| `app.asset(path)` | Absolute URL of a file next to the module script. Use for every file referenced from JS. |
| `app.modules()` | `[{ id, name, version, external, ns }]`. |
| `app.forced` | Phone is held to this app (RunApp). No hint bar/home bar is drawn: draw your own hints. |
| `app.done(result)` | Held app's answer; RunApp returns it. Nothing if not held. |
| `app.rumble(ms = 150, strength = 0.6)` | Controller shake (Lua clamps ms 30-1000, strength 0-1; only while open and on a pad). |
| `app.kit`, `app.icons` | UI kit and icon set. |

## Phone: notifications (capsules)

Fields for `app.notify`, server/client `Notify`, and `whip_phone:client:notify` (`os.js:728-763`):

| Field | Meaning |
|---|---|
| `app` | Module id (icon). Unknown → bell. Default `'system'`. `app.notify` sets it to the module. |
| `title`, `text` | Strings. |
| `kind` | `chat` (white, default), `command` (Signal Blue, "needs you"), `success`, `error`, `warning`, `call` (green). `call` gets through Do Not Disturb and plays no alert. |
| `args` | Passed to that module's `open` when tapped. |
| `key` | Same app+key updates the capsule in place (no pop-in, no sound); `app.dismiss(key)` removes it. |
| `persist` | Stays until dismissed; never pushed out. Update with `persist:false` to let it time out. |
| `life` | ms before it goes (default 5000). |
| `actions` | Up to 3 round buttons `[{ act, label, tone, icon }]`; `act` is the module's action; `tone` `accept` (green) / `reject` (red) / `on` (white) / none (glass). Module notifications only. |
| `data` | What actions and `tap` receive. |
| `tap` | `{ act, label }` (or a string act): tap (or X) runs that action instead of opening the app. |
| `sound` | `false` = silent. Otherwise a new capsule plays the SIM's notify tone (Messages: message tone), unless DND or `call`. |
| `sounds` | `{ ringtone, messageTone, notifyTone, soundVolume }` to use for a page not yet given that SIM's session (`PhoneDB.sounds(number)` server-side). |
| `force` | (code) shows through DND, quietly. |
| `icon` | (code) SVG glyph replacing the app icon. |
| `pic`, `frame` | (code) https picture shown round over the icon, framed `{ x, y, z }`. |

- Stack max 3 visible (oldest non-persistent makes way). On the lock screen, capsules also go into its list (max 4).
- A put-away phone peeks up to show them; in game it has no cursor, so capsule buttons are clickable only once the phone is out (calls can be answered with keys Y/U).

## Phone: mount mode, CSS scoping, fold snapshots

Mount mode (`mount` instead of `render`):
- `mount(app, el, view)` on open (`el` empty, covers the display; may be async). `update(app, el, view, changed)` after every phone render; `changed = true` when the box moved display (fold/unfold) or layout switched. `unmount(app, el)` on close or removal.
- One live instance: the box moves between displays on fold, so component state survives.
- The whole display is the app's, under status bar and home bar: keep content inside `var(--safe-top)` / `var(--safe-bottom)` (grows in controller layout).
- Starts from browser defaults: no phone fonts, resets or kit classes reach in; only CSS variables (`--accent`, `--safe-top`, `--text`, ...) inherit.
- `request`, `notify`, `toast`, `on`, `back`, `x`, `badge`, `statusBar`, and `data-act` actions still work. Controller reaches `<button>`, links, `role="button"`, `tabindex` elements; A clicks them; `data-hint` labels A.
- WebGL: resize in `update` when `changed`; pause the loop in `presence` when `now.visible` is false; dispose in `unmount`; create the renderer with `preserveDrawingBuffer: true` (else blank in the fold). `await import('three')` works (phone maps three 0.170). It is a second WebGL context; cap frame rate.

CSS rewriting (on register):

| Written | Becomes |
|---|---|
| `button {}` | `:where(.m-<id>) button {}` (no added specificity) |
| `.tablet .grid {}` | `.tablet :where(.m-<id>) .grid {}`; display classes kept in front: `.phone .tablet .portrait .console .mk .in-pad .in-keys .in-mouse .sb-dark .sb-light` |
| `:host`, `body`, `html`, `:root` | the app's own box (mount: the box you draw into) |
| `@keyframes spin` | `@keyframes <id>--spin` (animations renamed to match) |
| `url(img/bg.png)` | absolute URL next to the module script (fonts in `@font-face` too) |
| `.m-<id> .x {}` | left alone |

- `@import` is dropped with a warning. Render-mode apps inherit the phone look and kit classes.
- Fold snapshots: `<img>`, SVG `<image>`, `url()` in inline styles and `css` are inlined as data URLs (cached). Cross-resource files the page cannot fetch are read by Lua (`asset` NUI callback: png, jpg, jpeg, gif, webp, svg, avif, woff2, woff, ttf, otf; ≤ 3 MB; no `..`; resource must be started). Canvases/videos show their current frame; cross-origin-tainted canvases stay blank. Mount apps appear on both displays during a fold.

## Phone: UI kit

`WhipPhone.kit` (`html/core/kit.js`); all builders return HTML strings.

| Builder | Signature |
|---|---|
| `screen` | `(key, inner, { slide = false, cls = '' })` — page; unique key per sub-screen |
| `nav` | `({ back = null, title = '', right = '', act = 'os:back', d = {} })` |
| `navBtn` | `(icon, act, d = {}, hint = '')` |
| `title` | `(text)` |
| `search` | `({ bind, value = '', placeholder = 'Search' })` |
| `scroll` | `(inner, { bottom = false, pad = true })` — `bottom` pins to newest |
| `list` | `(rows, { header = '', footer = '', inset = null })` |
| `row` | `({ icon, av, label, sub, value, act, d, chev = !!act, toggle, sel, hint, tone, html })` — `tone: 'danger'` red; pressable with `act`; `html: true` = label/sub not escaped |
| `button` | `({ label, act, d, kind, icon, hint, block })` — `kind`: `gray`, `red`, `green`, `ghost` |
| `field` | `({ label, bind, value, placeholder, type = 'text', enter, mode })` |
| `seg` | `(options [[value,label]], value, act)` |
| `tabs` | `(tabs [[value,label,icon,badge]], value, act)` |
| `empty` | `({ icon, title, text, action })` |
| `avatar` | `({ name, size = 44, pic, frame })` |
| `bubble` | `({ me, text, fresh, failed })`; `day(text)`; `composer({ bind, value, placeholder = 'Message', send = 'send' })` |
| `sheet` | `({ title, body, close })` |
| `split` | `(side, main, key)` — tablet two-column |

Helpers: `esc`, `data(obj)` (→ `data-*` attrs, kebab-cased, skips null/false), `digits`, `fmtNumber` (`xxx-xxx-xxxx`), `toMs`, `fmtTime`, `fmtWhen`, `fmtDuration`, `initials`, `picUrl` (only `https://host/path` with safe chars), `frameStyle(frame)`, `icons`. Always `esc` data you put in HTML.

Picture frame `{ x, y, z }`: `x`,`y` 0-100 (the point kept in view; 50,50 middle), `z` zoom 1-3; drawn as `object-position: x% y%` + `scale(z)`.

## Phone: NUI structure and messaging

Page → Lua (`fetch('https://whip_phone/<name>')`, strict mode):

| Callback | Body → reply |
|---|---|
| `ready` | `{ version, error? }` → `{}`. Lua replies with `init`, flushes queued messages, sends `status`. `error`: the 3D model failed. |
| `request` | `{ name, args }` → `{ ok: true, data }` or `{ ok: false, reason }`. `name` must be ≤ 96 chars and start `whip_phone:` or `<registered ns>:`, else `'not allowed'`. |
| `close` | Player put it away from the phone (Back at top) → `{}`; gives up a RunApp hold. |
| `state` | `{ state }` (`hidden|peek|phone|tablet`) → `{}`; swaps the held emote; fires local `whip_phone:client:state`. |
| `typing` | `{ on }` → `{}`; padScreen typing mode. |
| `asset` | `{ url }` → `{ data: 'data:<mime>;base64,...' }` or `{}`. |
| `callVolume` | `{ value? }` → `{ value }` (nil when no voice system offers it). |
| `forcedDone` | `{ app, result }` → `{}`; ends a RunApp hold if `app` matches. |
| `rumble` | `{ ms, strength }` → `{}`. |
| `keys` | `{ on }` → `{}`; blocks/unblocks group `move` as `whip_phone:keys`. |
| `area` | `{ area: { left, top, right, bottom } | null }` (screen fractions) → `{}`; passed to `Whip.core:SetScreenArea(area or false, 'phone')`, re-sent after a whip_core restart. |

Lua → page (`SendNUIMessage({ type, ... })`; queued until `ready`):

| type | Fields |
|---|---|
| `init` | `modules: [{ id, script, ns?, external? }]`, `config: { phoneScale = Config.PhoneSize, defaults = Config.Defaults, clock = 'game'|'real' }` |
| `session` | `session` (sent only when its JSON changed, or forced) |
| `open` | `mode: 'phone'|'tablet'`, `pad` (opened from a controller) |
| `close` | — |
| `push` | `module, event, data` |
| `notify` | `notification` |
| `cmd` | `cmd, down, rep` (controller buttons from `Whip.padScreen`) |
| `time` | `h, m` (game clock, every 2 s while visible and changed, when `Config.GameClock`) |
| `status` | `voiceDown, voiceDownText` (page also accepts `battery`, `signal`) |
| `module` / `unmodule` | `module` / `id` |
| `force` / `unforce` | `app, args, pad` / — |

- Built-in module scripts are `modules/<id>/module.js` relative to the page; a listed built-in whose file is missing is skipped (debug log).
- Page keyboard: arrows, Enter (A), Escape/Backspace (B), Home; Y (controller) folds. With `keys: 'all'` also WASD/Space/Q/E. Keys typed into inputs are ignored.

## Phone: request path, server callbacks, rate limits

```
module  app.request('send', { number, text })
page    bridge.request('whip_phone:messages:send', args)  -> NUI 'request'
client  Whip.core:Callback(name, args)                     (10 s timeout)
server  exports.whip_core:SecureCallback(name, PhoneSchema(schema), fn(source, player, args))
```

- `PhoneSchema(schema)` = the schema plus `params = { { 'args', 'any' } }` (`server/main.lua:13-19`). Global function usable by whip_phone files only.
- Rate limits used: `LIGHT = { rateLimit = 250, burst = 6 }` (reads), `WRITE = { rateLimit = 500, burst = 3 }` (writes); `WRITE_DOWNED` adds `whileDead = true`; `session` `{ 1000, burst 3 }`; `settings:card` `{ 1000, burst 3 }`.
- contract/calls/blocks/card handlers refuse with `'The phone network is starting, try again'` until `PhoneDB.ready`. DB errors answer `'The phone network is not answering, try again'` (`PhoneDB.NET_DOWN`).
- Bank and Business handlers (except `unwatch`) refuse `'Your character is not loaded'` and `'You need a phone'` first; they do not wait for `PhoneDB.ready`.

## Phone: core callbacks

| Name | args | Returns / refusals |
|---|---|---|
| `whip_phone:session` (1000/3) | `{ first }` | `{ number (only when sim='ok'), name (SIM owner's), sim, settings, home, card, mine }`; `false, 'You need a phone'` (no phone item keeps it shut). No/locked SIM still opens. `first == true` forgets the Use-chosen phone. |
| `whip_phone:home:save` (WRITE) | `{ home = { phone = { [appId] = slot }, tablet = {...} } }` | `true`. On the SIM (`prefs.home`) or the phone item when no SIM. Slots `page × perPage + place`; phone 16/page, tablet 24/page; slot `0 ≤ s < 192`; ≤ 96 apps per grid; ids match `^[a-z][a-z0-9_%-]*$`, ≤ 32. |
| `whip_phone:settings:save` (WRITE) | `{ wallpaper, dnd, ringtone, messageTone, notifyTone, soundVolume }` (also `theme`) | `true`. SIM keys (wallpaper, the 4 sound keys) go on the SIM, each only when changed; the rest (dnd, theme) on the phone item; no SIM → all on the phone. Ids ≤ 32 chars `[%w_-]`; `soundVolume` integer 0-100. Refusal `'Your phone moved while that saved — try again'`. |
| `whip_phone:settings:numbers` (LIGHT) | — | `{ current, state ('ok'|'nosim'|'locked'|'blank'|'nophone'), currentMine, currentLocked, numbers = { { number, locked } } }` (character's own, sorted). |
| `whip_phone:settings:lock` (WRITE) | `{ number, locked }` | `true`, or `false, 'Which number?'` / `'That is not your number'` / `'Could not save that'`. Holder refreshed at once; locking ends calls on it ("Number locked"). |
| `whip_phone:settings:card` (1000/3) | `{ name, picture, frame = { x, y, z } }` | Card as kept `{ name, picture, frame }` or `{}`. Only the number's owner with its SIM in their phone (`'Put your SIM card in the phone first'`, `'Only this number\'s owner can change its card'`). Name ≤ 50 (`'A name of up to 50 characters'`). `picture` must pass `exports.whip_core:CheckPicture` (`Config.LorePictureLinks`, Fivemanage default). Picture/frame change pushes `contacts changed` to every online holder of a SIM that saved this number. |
| `whip_phone:contacts:list` (LIGHT) | — | `{ { id, name, number, picture, pictureFrame, noBlock } }`, by name, max 500. `picture`: lore character's, else the number's card picture. `noBlock` true for lore numbers. No SIM → `{}`. |
| `whip_phone:contacts:save` (WRITE) | `{ id? , name, number }` | `{ id, name, number }`. Name 1-50 (trimmed): `'A name of 1 to 50 characters'`; `'A phone number is 10 digits'`; `'That contact is gone'`; `'This SIM holds 500 contacts at most: delete one first'`. |
| `whip_phone:contacts:delete` (WRITE) | `{ id }` | `true`. |

- The page reloads contacts/app data only when the session it gets differs from the last (JSON compare in Lua), so keep `SetSession` payloads stable.
- After changing contacts outside the phone, `Push(src, 'contacts', 'changed')`.

## Phone: Phone module (calls) callbacks and pushes

`whip_phone:phone:*`:

| Name | args | Returns / refusals |
|---|---|---|
| `recents` (LIGHT) | — | `{ { id, number, dir = 'in'|'out'|'missed', time, duration, noBlock } }`, newest first, `Config.RecentCalls` max. Incoming rows marked `blocked` are excluded forever. |
| `dial` (WRITE) | `{ number }` | `{ callId, state = 'dialing' }`. Refusals: SIM reasons; `'A phone number is 10 digits'`; `'You cannot call yourself'`; `'Number not in service'` (unknown or locked); `'You are already in a call'`; `Config.VoiceDownText` (no voice system; not checked for lore numbers); `'The number you called is unavailable'` (nobody holds the SIM, or holder is dead); `'Busy'`; `'That call has ended'`. |
| `answer` (WRITE) | `{ callId }` | `{ state = 'active', startedAt }`; `'That call has ended'`, or the voice line's error. |
| `decline` (WRITE) | `{ callId }` | `true` (always). |
| `end` (WRITE, whileDead) | `{ callId }` (none = the player's one call) | `true`. |
| `mute` / `speaker` (WRITE, whileDead) | `{ callId, on }` | voice `SetLineMuted` / `SetLineSpeaker` result; `'Not in a call'`. Page applies at once and reverts on refusal. |
| `dtmf` (LIGHT) | `{ callId, key }` | `true` (no-op). |
| `inviteAnswer` (WRITE, whileDead) | `{ token, yes }` | `true`; `'That invite is gone'` or `AnswerAsk`'s reason. |

Pushes to `phone`:
- `incoming` `{ callId, number, sounds }` — phone away or in an app: call capsule (Decline/Answer), stays until answered/declined/missed; home/lock screen: full screen. A second incoming during a call shows "Call waiting" only.
- `state` `{ callId, state, startedAt?, reason? }` — `ringing`, `active` (with `startedAt`), `ended`, `declined`, `busy`, `unavailable`, `missed`.
- `recents` `[...]` replaces the list.
- `invite` `{ token, title, message, yes, no }` — whip_core yes/no question (Director job invite) via ask channel `'phone'`; generic capsule (`?` icon, cross Decline, tick Accept) through DND; not a call.
- `inviteGone` `{ token }` — whip_core stopped waiting.
- `callKey` `{ key = 'answer'|'decline' }` — from the Y/U key mappings; acts only on a call ringing in.

A call end to end: A dials → A gets `{ callId }`, B gets `incoming`; both get `state ringing`; B answers (both must still hold the numbers; voice line opens first, else the call ends with the reason) → B's `answer` returns `active`, A gets `state active`; either `end` → other side gets `state ended` (or `missed` if still ringing). Rings out after `Config.RingSeconds`: caller `unavailable` "No answer", callee `missed`.

A call also ends on: logout ("Call ended"), disconnect/voice leave ("Call dropped"), death ("Call ended"), the SIM or phone leaving them (any pocket change, SIM tray), the number being locked ("Number locked"), the voice system resource stopping (reason `Config.VoiceDownText`).

## Phone: Messages callbacks and pushes

| Name | args | Returns / refusals |
|---|---|---|
| `messages:threads` (LIGHT) | — | `{ { number, unread, last = { text, time, me }, noBlock } }`, newest first, max 200 conversations. Texts received while blocked are excluded. |
| `messages:thread` (LIGHT) | `{ number }` | `{ { id, me, text, time } }` oldest first, max `Config.MessageHistory` (each direction fetched separately). |
| `messages:send` (WRITE) | `{ number, text }` | `{ id, time }`. `'A phone number is 10 digits'`, `'Number not in service'`, `'Nothing to send'`, `'A message is 500 characters at most'` (bytes, after trim), `'Could not send that'`. To a SIM that blocked the sender: same answer, stored `blocked = 1`, never pushed. |
| `messages:read` (LIGHT) | `{ number }` | `true` (marks that conversation read). |

Pushes to `messages`: `incoming` `{ id, number, text, time, sounds }` (to whoever holds the receiving SIM now; module adds it, bumps unread and notifies unless viewing that chat), `threads` `[...]`, `thread` `{ number, messages }`.

## Phone: block list callbacks

`whip_phone:blocks:*`, the SIM's list, held in memory, max **100** per SIM.

| Name | args | Returns / refusals |
|---|---|---|
| `list` (LIGHT) | — | `{ { number, time } }` latest first (`time` seconds). |
| `add` (WRITE) | `{ number }` | `true` (also if already blocked). `'A phone number is 10 digits'`, `'You cannot block your own number'`, `'Number not in service'`, `'This number cannot be blocked'` (lore), `'This SIM blocks 100 numbers at most: unblock one first'`. A call from that number ringing this SIM stops (callee gets `state declined`; caller rings out). |
| `remove` (WRITE) | `{ number }` | `true`. Texts/calls received while blocked stay hidden. |

- One-way: the blocker can still call/text. Nothing tells the blocked number: texts show sent; calls get unavailable/Busy/ring out "No answer"; the callee's line stays free; rows marked `blocked` stay out of the callee's Recents.
- Lore numbers can never be blocked (`Blocks.has` ignores a block on a number that is now a lore character's).

## Phone: Bank callbacks and pushes

`whip_phone:bank:*`, always the character holding the phone, via whip_core bank exports with the player as actor (bank's own rules apply; `Config.MaxExtraAccounts` in whip_core limits savings/shared).

| Name | args | Returns |
|---|---|---|
| `accounts` (LIGHT) | `{ watch? }` | `{ { id, number, label, type, balance, role, default, frozen, job } }`, default first; watches them unless `watch == false`. `'The bank is not answering, try again'`. |
| `unwatch` (LIGHT, no phone needed) | — | `true`. |
| `account` (LIGHT) | `{ id }` | `{ account, can = { transfer (role ≥ withdraw), share (≥ manager), close }, history = { { id, amount, dir = 'in'|'out', text, time, balance, party } } }` (last 30). `party` names the other side of a transfer only when no character owns it. `'That account is not yours'`. |
| `transfer` (WRITE) | `{ from, to }` or `{ from, number }` (`WB-000000` or 6 digits), `amount`, `message?` (≤ 100, default `'Phone transfer'`) | `true`. `'Enter a whole number of dollars'`, `'An account number looks like WB-000000'`, `'There is no account WB-...'`, `'Pick one of your accounts'`, `'Pick the account to send from'`, `'That is the same account'`, `BankTransfer`'s reason. |
| `access` (LIGHT) | `{ id }` | Members `{ charId, name, role, me }` then pending invites `{ invite, charId, name, role, pending = true }` (`name` = `#<charId>` unless sender could see it). Owner/managers only. |
| `share` (WRITE) | `{ id, role, src }` (nearby) or `{ id, role, charId }` | `{ name, invited }`. `role` in `view|deposit|withdraw|manager`, below your own. Existing member: role changed (`GrantBankAccess`, returns `{ name }`). Others get an **invite** (checked with `CanGrantBankAccess`). Max 10 waiting per account, one per person, 24 h TTL (memory only, lost on restart), 10 s cool-down after a decline/take-back for the same sender→target. |
| `invites` (LIGHT) | — | `{ { invite, account, role, from } }` for this character. |
| `answer` (WRITE) | `{ invite, accept }` | `{ id }` accepted / `true` declined. Accepted → `GrantBankAccess(..., { charId = sender })` re-checked. Sender notified "Invite declined" / "<Name> accepted: they can use it now". |
| `uninvite` (WRITE) | `{ invite }` | `true` (owner/manager). |
| `unshare` (WRITE) | `{ id, charId }` | `true` (`RevokeBankAccess`). |
| `nearby` (LIGHT) | — | `{ { src, name, dist } }`: within 15 m, same routing bucket, `CanSeePlayerName`, nearest first, max 10. |
| `open` (WRITE) | `{ label (≤ 50), type = 'savings'|'shared' }` | `{ id, number }`. |
| `close` (WRITE) | `{ id }` | `true` (owner; empty savings/shared; bank checks). |

Pushes to `bank`: `changed { ids }` (only while watching: the app sends `unwatch` when it leaves the screen or the phone is put away; driven by `whip_core:bank:balanceChanged` / `accountChanged`), `invite { invite, account, role, from }` (capsule with Decline/Accept, life 20 s), `inviteGone { invite }`, `shared { id }`. Money arriving in a character's own non-business account that they did not move shows a `success` notification "Received $250 · <message>" (message omitted when `'Phone transfer'`), which opens that account.

Person picking (`People.picked`): `{ src }` must still be within 20 m (15 + 5 slack) and visible by name rule: `'They are not near you any more: type their character ID'`; `{ charId }` must exist: `'No character has the ID %d'`; a typed ID never reveals a hidden name.

## Phone: Business callbacks, pushes, and clock-on

`whip_phone:business:*`, the character holding the phone, whip_core job exports with `{ by = source }` so the jobs system's rules apply (permissions `canHire`, `canFire`, `canPromote`, `canDemote`, `canManage`; nothing at or above your own level except at level 100; a job's `selfClockOn = false`).

| Name | args | Returns |
|---|---|---|
| `jobs` (LIGHT) | `{ watch? }` | `{ { id, name, icon, role, level, onDuty } }` by name; watches unless `watch == false`. |
| `unwatch` (LIGHT, no phone needed) | — | `true`. |
| `job` (LIGHT) | `{ id, watch? }` | `{ job = { id, name, icon, role, level, onDuty, selfClock }, can = { hire, fire, promote, demote, manage }, staff?, roles?, offers? }`. `staff` `{ charId, name, roleId, role, level, onDuty, me, owner, unhired }` highest first (owner off payroll appended as `unhired`); `roles` `{ roleId, name, level, give }`; `offers` `{ offer, charId, name, role }` — only when the rank has any manage permission. `'You do not work there'`. |
| `clockOn` (WRITE) | `{ id }` | `true`. Calls `exports.whip_core:ClockOn(source, id, { by = source })`. Refusals: `'No such job'`, `'They do not work there'`, `'This job puts people on duty itself'` (job `selfClockOn = false`), `'Could not clock on'`. `Config.JobDutyOneAtATime` (whip_core, default `false`) clocks off other jobs first. |
| `clockOff` (500/3, whileDead) | `{ id }` | `true`. Always one job (`ClockOff(source, id)`); works while down. |
| `setRole` (WRITE) | `{ id, charId, roleId }` | `true` (`SetPlayerRole`). `'Who?'`, `'No such role at that job'`. |
| `fire` (WRITE) | `{ id, charId }` | `true` (`FirePlayer`). `'You cannot fire yourself'`. |
| `hire` (WRITE) | `{ id, roleId?, src }` or `{ id, roleId?, charId }` | `{ name, offered }`: a **job offer**. `CanHirePlayer` checked now and `HirePlayer` (by the sender's charId) on accept. One offer per person per job, max 10 waiting per job, 24 h TTL, 10 s cool-down. No `roleId` = lowest role. `'That is you'`, `'Already offered: waiting for their answer'`, `'Too many job offers waiting at this business'`, `'Wait a few seconds before offering them a job again'`. |
| `offers` (LIGHT) | — | `{ { offer, job, role, from } }` for this character. |
| `answerOffer` (WRITE) | `{ offer, accept }` | `{ id }` / `true`. Sender notified "Job offer declined" / "<Name> accepted: hired as <Rank>". `'That job offer is gone'`. |
| `unoffer` (WRITE) | `{ offer }` | `true` (anyone at that job with `canHire`). |
| `nearby` (LIGHT) | — | as Bank's. |
| `roles` (LIGHT) | `{ id }` | `{ roles = GetJobRoles(id), perms = { { key, label, custom } }, level, have = { perms, bank } }` (`canManage` only). Built-in perms: canHire Hire, canFire Fire, canPromote Promote, canDemote Demote, canManage Manage the business; then the job's own (`job.settings.permissions`, sorted). |
| `saveRole` (WRITE) | `{ id, roleId?, name, level, permissions = { [key] = bool, bankAccess } }` | `{ roleId }`. No `roleId` = new (`CreateJobRole`; needs name `'A role name is 1 to 60 characters'` and level `'A role\'s level is a whole number from 1 to 100'`), else `UpdateJobRole`. Keys ≤ 40 chars, boolean values; `bankAccess` in `none|view|deposit|withdraw|manager`. |
| `deleteRole` (WRITE) | `{ id, roleId }` | `true` (refused while anyone holds it). |

Pushes to `business`: `changed { id }` to watchers of that job and to the affected player (from `whip_core:job:hired|fired|roleChanged|clockedOn|clockedOff|updated|deleted`), `offer { offer, job, role, from }` (capsule, life 20 s), `offerGone { offer }`.

Clock-on UI: the job page shows "Tap to clock on" only when `job.selfClock`; otherwise "This job puts you on duty itself". X on a controller clocks on/off. Doc `guide-jobs`: for station-only duty declare `selfClockOn = false` and call `ClockOn` from your server code (without `by`).

## Phone: skill check games and the Skill Check Tester

- Seven games in hidden module `skillcheck`, registered with whip_core as skill check games `phone.bruteforce`, `phone.coderecall`, `phone.fragmentmatch`, `phone.override`, `phone.reroute`, `phone.safecrack`, `phone.stabilise` (label `<Name> (phone)`), only those whose `Config.SkillGames[key].enabled ~= false`.
- Use: `exports.whip_core:SkillCheck(source, 'hard', { game = 'phone.reroute' })`, client `SkillCheck({ game })`, or the Director's Skill Check card (Game field).
- Server half (`server/skillgames.lua`): `Whip.skillCheckGame(id, { label, desc, levels, canStart })`; `canStart` refuses with `Config.SkillGameNoPhone` when `Sim.phoneOf` finds no phone (not a fail: "not started"). `levels[level] = { minMs, timeoutMs }` from `PhoneSkillGames.timing` (intro 1800 ms + result 1300 ms; timeout = clock + 3.1 s + 5 s slack, capped 120 s; a pass faster than `minMs` is refused).
- Client half: `canStart` checks `GetItemCount('phone') > 0`; `run(difficulty)` calls `runApp('skillcheck', { game, level, cfg, label, goal })`; returns `true` or `false, 'busy'|'cancelled'|'timeout'|'failed'`; `cancel` ends the hold. The game answers `app.done({ passed, why, ms, reason })`.
- Every input is a single press (controller and keyboard play the same difficulty). Module uses `keys: 'all'`.
- Skill Check Tester (`skilltest`, developer app): callbacks `whip_phone:skilltest:settings` (LIGHT) → `{ ring = GetSkillCheckSettings(), games = { { key, name, goal, enabled, levels } } }` and `whip_phone:skilltest:run` (WRITE) `{ game ('ring' or key), level ('easy'|'medium'|'hard'), settings }` → `true`; both refuse non-developers ("The Skill Check Tester is for developers: turn developer mode on in /w"). The server sends net event `whip_phone:client:skilltest` `{ game, level, settings }`; the result returns to the app as push `skilltest result { game, level, passed, why, ms, reason }`. Test numbers are never saved.

## Phone: events (net, local, whip_core events it listens to)

Client net events (server → client; all in `client/main.lua`):

| Event | Payload | Effect |
|---|---|---|
| `whip_phone:client:push` | `module, event, data` | page push |
| `whip_phone:client:notify` | `n` (table) | capsule |
| `whip_phone:client:session` | `session` | forced session replace |
| `whip_phone:client:open` | `mode, fromItem` | open (`fromItem == true`: keep Use-chosen phone; if already open, reload that phone's session) |
| `whip_phone:client:close` | — | put away |
| `whip_phone:client:refresh` | — | if open, refetch session (sent on SIM tray change, lock change, ReloadCache) |
| `whip_phone:client:skilltest` | `{ game, level, settings }` | developer test run |

Client local events fired by whip_phone:
- `whip_phone:client:opened` (bool): took/released the phone (NUI focus). Not for animations: the phone plays its own emote.
- `whip_phone:client:state` (`'hidden'|'peek'|'phone'|'tablet'`): what is on screen.

whip_core events whip_phone listens to:
- Client: `whip_core:devtools:modeChanged { on }` (dev apps), `whip_core:voice:systemChanged` (voice-down screen), `whip_core:ask:cancelled { token }` (only from whip_core → `inviteGone`), `whip_core:player:logout` (close, forget session), `whip_core:player:died` (close).
- Server: `whip_core:inventory:changed { source }` (SIM index, call recheck), `whip_core:player:loaded`, `whip_core:player:logout`, `whip_core:player:died` (hang up), `playerDropped`, `whip_core:character:renamed`, `whip_core:job:*`, `whip_core:bank:balanceChanged`, `whip_core:bank:accountChanged`, `whip_core:lore:changed` (only from whip_core: gives the lore character a number), `onResourceStop` (voice resource stop ends its calls).

No server net events are registered by whip_phone: every page→server path is a SecureCallback.

## Phone: calls and voice

- Sound is the voice system's; no phone code is in it. On answer `server/calls.lua` calls `Whip.voice('OpenLine', { members = { caller, callee }, track = 'voice', pickup = true, minMembers = 2, recipe = Config.CallSound, speakerRange = Config.SpeakerRange or 8, onLeave, onEnd })`, closed with `CloseLine` when the call ends. Mute/speaker: `SetLineMuted` / `SetLineSpeaker`.
- On speaker, people near the phone hear the other side, and the other side hears them (each within their voice range of the phone).
- No voice system (`Whip.voiceSystem()` false): dial refused with `Config.VoiceDownText`; every phone shows it over everything (status message) and B puts it away; the ask channel declines invites.
- Call volume = voice system's "Phone call volume" (`voice.callVolume` player setting, pause menu Server Settings and phone Settings > Sounds > Call volume).
- Invites: whip_phone registers ask channel `'phone'` (`RegisterAskChannel`). `deliver` takes only `kind == 'confirm'` questions, and only when the `phone` module is in `Config.Modules`, a voice system runs, and the player carries a phone; otherwise whip_core asks on screen. Answers go back through `AnswerAsk(source, token, yes)`.
- The Phone module plays ringtones via Web Audio (`html/core/sounds.js`, no files); the SIM's sounds ride with `incoming` pushes so a never-opened phone rings right.

## Phone: lore characters and Director cards

- Each Director lore character gets a number (no charId, `loreKey` = its key), made on first need, synced on start (`LorePhones.syncAll`) and on `whip_core:lore:changed`.
- A text to one is kept, never answered; a call to one rings and is never answered ("No answer" after `Config.RingSeconds`), needs no voice system.
- A lore text/contact goes to the SIM in the player's phone, else to an unlocked number they own.
- Director cards (category `lore`, green):
  - `phone.giveContact` — props `lore` (Whose), `who` (players). Outputs `given`, `had`, `nophone`. Adds a contact (name ≤ 50) and notifies "New contact".
  - `phone.sendText` — props `lore`, `text` (≤ 500, default "Change of plan. Check your map."), `who`. Outputs `sent`, `nophone`.
  - `phone.call` — props `lore`, `recording` (required, ≤ 255: `@resource/folder/file.ogg` (mp3/ogg/wav) or a plain https link), `who`. Outputs `answered` (Heard it all), `hungup`, `declined`, `missed`, `busy`, `nophone`; bad: declined, missed, busy, nophone. `timeout = 300`, `test = 'run'` (a builder test rings only the tester). A dead player or one on a call is `busy`. Needs whip_voice's voice bot (`CreateVoiceBot`, `PutVoiceBotOnLine`, `PlayVoiceBot`); the call hangs up when the recording ends. Multiple players: best outcome wins; nobody rung and a failure → card error.
- `/lorecall <recording> [loreKey]` (dev: `Whip.command` with `dev = true`, not console): a lore character phones you; chat reports the outcome.
- Doc `voice-lore-calls`: recordings mp3/ogg/wav up to 2 minutes and 15 MB; Fivemanage links accepted by default (`Config.VoiceBot.audioLinks` in whip_voice adds sites); `@` files are read by the voice bot server-side, so do not list them in `files {}`.
- Lore caller pictures come from the Director's lore character picture (checked again as plain https).

## Phone: client behaviour (focus, controls, keys, emotes, death)

- Keys (`RegisterKeyMapping`, rebindable in Settings > Key Bindings > FiveM): `+whip_phone` "Phone: open / close" (`Config.OpenKey`, F3); `whip_phone_answer` "Phone: answer a call" (`Config.AnswerKey`, Y); `whip_phone_decline` "Phone: decline a call" (`Config.DeclineKey`, U). New defaults only reach players who have not bound the key. Open is ignored while `IsGameInputFree() == false` (typing elsewhere).
- F1 wheel action `phone` (`AddAction({ id='phone', at={ radial=true }, label='Phone', icon='phone', require={ item='phone' } })`) and controller pad action `RegisterPadAction('phone', { label='Phone', command='+whip_phone', slot='dpad_up' })`.
- Focus: whip_core `Whip.padScreen` with `keepInput = 'always'` (the player can walk with the phone out); pad buttons that act in the world (controls 21-25, 37, 44, 45, 140-143, 257, 263, 264) blocked; typing in a field drops keep-input.
- On open: `SetScreenOpen(true, 'phone', { keepHud = true })` (chat and prompts make way; HUD, minimap and dial stay) and `BlockControls('whip_phone', { groups = Config.BlockControls, controls = { 199, 200 } })` (pause menu stays shut; phone owns Esc). A wrong group name refuses the whole block: a warning prints once and only 199/200 are blocked.
- The page reports its screen area; whip_core's vehicle dial moves out of its way (`SetScreenArea`).
- In hand: `Config.Emotes.phone` while out, `Config.Emotes.tablet` while unfolded, via `PlayEmote`; a player already in another emote is left alone; on coming out a drawn weapon is put away first (`FreeHands`, waits; if put away meanwhile, no emote).
- Opening from the inventory closes the inventory first.
- Put away by: the key again, Back at top level, death (`whip_core:player:died`; also refused to open while dead), logout, being ragdolled (checked every 200 ms while out). Death also hangs up the call server-side. On the voice-down screen only B works (it puts the phone away).
- Status bar clock: game time (`Config.GameClock = true`) or the player's real clock.

## Phone: config.lua keys and defaults

| Key | Default | Meaning |
|---|---|---|
| `OpenKey` | `'F3'` | open/close key |
| `AnswerKey` | `'Y'` | answer a ringing call |
| `DeclineKey` | `'U'` | decline a ringing call |
| `PhoneSize` | `0.5` | folded phone height as a share of screen height |
| `Modules` | `{ 'phone','messages','bank','business','settings','skillcheck' }` | built-in apps (each also needs a `files {}` line) |
| `DeveloperApps` | `{ 'skilltest' }` | built-ins only for developer mode |
| `RequireSession` | `true` | `false` lets the phone open without a session answer (dev) |
| `GameClock` | `true` | game time vs real clock |
| `BlockControls` | `{ 'combat','look','vehicleCombat','weaponWheel' }` | whip_core control groups held while focused |
| `Emotes` | `{ phone = 'phone', tablet = 'tablet' }` | `/e` names from whip_core's emote list; `''` plays nothing |
| `Defaults` | `{ wallpaper='dusk', ringtone='marimba', messageTone='note', notifyTone='ding', soundVolume=75 }` | fresh phone look/sound |
| `NumberPrefixes` | `{ '689','041','227','869','915' }` | new number prefix + 7 digits |
| `RingSeconds` | `30` | ring before missed |
| `MessageHistory` | `300` | messages loaded per conversation |
| `RecentCalls` | `50` | Recents rows |
| `CallSound` | band 300-3400, drive k 1.5, compress -24/4, pink noise 0.008, gain -2 dB | whip_voice sound-block recipe |
| `SpeakerRange` | `8` | metres (1-30) |
| `VoiceDownText` | `'Voice connection failed, is the voice resource started?'` | shown when no voice system |
| `SkillGameNoPhone` | `'You need a phone!'` | skill game without phone |
| `SkillGames` | per game `easy/medium/hard` tables (+ `enabled`) | levels; `seconds` is each level's clock (Override's clock is its track length) |
| `Debug` | `false` | client debug prints |

Option values: wallpapers `dusk, aurora, ocean, sunset, berry, lagoon, citrus, neon, ember, glacier, orchid, midnight`; ringtones `marimba, classic, oldphone, digital, chimes, pulse, arcade, vibrate, silent`; message/notify tones `note, tritone, ding, glass, pop, blip, knock, chord, vibrate, none`; `soundVolume` 0-100 (Settings offers 25/50/75/100).

SkillGames keys per game: bruteforce `reels, speed, letters, window, missCost, set ('clear'|'mixed'|'all'), lookalikes, bothWays, seconds`; coderecall `rounds{}, flashMs, gapMs, mistakes, newCode, lastBackwards, seconds`; fragmentmatch `columns, letters, afterWrong ('columns'|'count'|'nothing'), lookalikes, wrongCost, seconds`; override `lanes (3|4), arrows, fallSeconds, windowMs, gapMs{min,max}, misses`; reroute `grid (3-6), keepRight, decoys{straight,elbow,tee,dead}, seconds`; safecrack `numbers, hint, wrongCost, wrongRestarts, seconds`; stabilise `band, bandSpeed, drillSeconds, leaving, overheatSeconds, seconds`.

Related whip_core config: `Config.LorePictureLinks` (`{ 'https://r2.fivemanage.com/' }`) for card pictures; `Config.ShowPlayerNames` (`'nearby'`) for names in nearby lists; `Config.AccessoryStrip` (slot 1 = Phone); `Config.Controller.Layout` `dpad_up = 'phone'`.

## Phone: admin tools

- `/whip` → Phones: every number; open one for owner, SIM state, contents (contacts, messages, calls, blocks); change, give yourself its SIM, delete, give a character a number; read conversations and calls. Changes call `exports.whip_phone:ReloadCache()`.
- Director Lore cards (above); `/lorecall` (dev).
- Skill Check Tester app appears for admins with developer mode on (`/w`).

---

## Chat: overview and install

- `whip_chat` replaces FiveM's stock `chat`: same events, exports, modes, templates and `^N` colour codes. Requires `whip_core`. `ensure whip_chat` after whip_core; remove `ensure chat` (or `stop chat` after `ensure whip_chat`). Two chats → every line twice, T opens both; whip_chat prints a red console warning (and F8 warning) naming the other chat and the fix. "Another chat" = resource named `chat` or any with `provide 'chat'` metadata.
- whip_chat does **not** `provide 'chat'`: `exports.chat:...` calls and `dependency 'chat'` must be changed to `whip_chat`. Event-only resources need no change.
- No `config.lua`. fxmanifest: `shared_script '@whip_core/lib/satellite.lua'`, `ui_page 'html/index.html'`, `nui_callback_strict_mode 'true'`, `dependency 'whip_core'`, `whip_requires '1.0'`.
- The text field is **whip_core's composer** (the player capsule turns into it, `OpenComposer`); whip_chat's page is only the message log. Players can look around while typing.

## Chat: commands, keys, player settings, convars

| Command / key | Side | Does |
|---|---|---|
| `T` (`+whip_chat`, "Open Chat") | client | Opens the composer on press, gives it keyboard focus on release (`-whip_chat` → `FocusComposer`). Not over a whip screen, the pause menu or a fade. |
| F1 wheel "Chat" (`id='chat'`, icon `talk`, `require={ alive=false }`) | client | Only while a controller is active: whip's pad keyboard. |
| `/toggleChat [whenactive|visible|hidden]`, `F6` ("Toggle chat visibility") | client | Sets or cycles visibility (0 fade away, 1 always on screen, 2 hidden); saved in KVP `whip_chat:hideState`; announces with `Whip.core:Notify(..., 'info', 5000)`. F6, not stock's L (L is vehicle lock). |
| `/clearchat` | client | Empties only your own log (same as `chat:clear`). |
| `/resetchat` | client | Failsafe: `CloseComposer`, `SetNuiFocus(false,false)`. (`/resetcomposer` is whip_core's own.) |
| `/global <message>` | server | To everyone, author prefixed `[Global] `. Needs a loaded character ("Pick a character first: /global goes out under their name"); rate 3 burst then 1/400 ms; cut to 256. |
| `/say <message>` | server | Server notice to everyone (no author prefix when from console). `Whip.command('say', { dev = true, whileDead = true })`: console or developer mode on. |
| PageUp/PageDown | client | Scroll the log while typing (forwarded by whip_core). Tab/arrows pick suggestions. |

- Player setting `chat.visibility` (group `'Chat & voice'`, type `choice`, options 0 Fade away / 1 Stay on screen / 2 Hidden, default 0) on the pause menu's Server Settings page.
- Convars: `chat_showJoins` (default 1; `0` hides "* Name joined.") and `chat_showQuits` (default 1; `0` hides "* Name left (reason)").
- `Config.NetworkRange` (whip_core, `424.0`) is how far a normal message reaches.
- Chat is force-hidden while a whip screen is open (`whip_core:ui:stateChanged` / `IsAnyScreenOpen`), the pause menu is open or the screen is faded out, then restored.
- Message cap 256 characters (server `MAX_MESSAGE_LEN`, page and composer `maxLength`).

## Chat: client events and exports

Client net events (server can `TriggerClientEvent` them; local `TriggerEvent` works too):

| Event | Args | Effect |
|---|---|---|
| `chat:addMessage` | `message` (table, or string → `{ args = { s } }`) | adds a line |
| `chat:addSuggestion` | `name, help, params` | records a suggestion |
| `chat:addSuggestions` | list of `{ name, help, params }`, or one such table | records them |
| `chat:removeSuggestion` | `name` | removes it |
| `chat:addTemplate` | `id, html` | registers a template |
| `chat:addMode` | `{ name, displayName, color, isChannel, isGlobal }` | adds/replaces a composer mode |
| `chat:removeMode` | `name` or `{ name }` | removes it |
| `chat:clear` | — | clears the log |
| `chatMessage` | `author, color, text` | deprecated stock form; `author ~= ''` becomes `args[1]` |
| `__cfx_internal:serverPrint` | `msg` | prints and shows it with `templateId = 'print'` |

Client exports:

### addMessage(message) — CLIENT
- `message` table or string. Sends `ON_MESSAGE` to the page.

### addSuggestion(name, help, params?) — CLIENT
- `name` like `'/mycmd'`; `params = { { name, help }, ... }`. Names starting `+`, `-` or `~!` (with or without `/`) are ignored. Re-adding a name replaces it in place.

### SetChatScale(scale) — CLIENT
- Multiplier on top of resolution scaling (page scales to `innerHeight / 1440`); `1` = same size as WHIP's other panels.

## Chat: server exports, hooks and modes

### addMessage(target?, message) — SERVER
- `addMessage(message)` broadcasts (-1); `addMessage(target, message)` to one player. Triggers `chat:addMessage`. Returns nothing.

### registerMessageHook(hook, id?) — SERVER
- `hook(source, outMessage, ref)` sees every routed message. Keyed `<invokingResource>:<id or 'default'>`; same key replaces (safe to call from `Whip.register`). Returns `true` or `false, 'registerMessageHook needs a function'`. Removed when the resource stops. Hooks run in `pcall` (errors printed).
- `ref.updateMessage(patch)`: merges keys into `outMessage`; `template` replaces `{}` with the current template (or `'@default'`); `params` merges.
- `ref.cancel()`; `ref.setRouting(target)` (a server id, -1 or a list); `ref.setSeObject(ace)` (recipients = players allowed that ACE).

### registerMode(modeData) — SERVER
- `modeData = { name, displayName, cb, seObject?, color?, isChannel?, isGlobal? }`. Refusals: `'registerMode takes a table: { name, displayName, cb }'`, `'a chat mode needs a name'`, `'chat mode "%s" needs a displayName'`, `'chat mode "%s" needs a cb'`, `'chat mode "%s" belongs to <res>'` (held by another running resource). Same resource re-registering replaces. Returns `true`.
- Clients receive `{ name, displayName, color (default '#fff'), isChannel, isGlobal }` — all players, or only those allowed `seObject`. Sent again to each player on `whip_chat:init`. Removed (and `chat:removeMode` broadcast) when the owning resource stops.
- `cb(source, outMessage, ref)` runs after the hooks, with the same `ref`. A sender not allowed the mode's `seObject` is dropped silently, before hooks.

### routeMessage(source, message, mode?, fromConsole?, global?) — SERVER
- Routes as if typed. `source = 0` is console (author `'console'`, to everyone). `global = true` sends to -1 and prefixes `[Global] ` (not for console). Logs one console line unless `fromConsole`.

Server local event `chatMessage(source, author, text)`: fired before delivery; `CancelEvent()` stops it.

## Chat: routing and inbound events

- Author: `Whip.core:GetPlayerFullName(source)` (character), else `GetPlayerName` (account name).
- Out message: `{ color = { 255, 255, 255 }, multiline = true, args = { author, message }, mode }`.
- Default recipients: players from `Whip.core:GetPlayersInRange(GetEntityCoords(ped))` (whip_core `Config.NetworkRange`) in the speaker's routing bucket (the character screen is its own bucket). Speaker with no ped → only themselves. whip_core not answering → everyone. Lists are sent with one msgpack pack (`TriggerClientEventInternal`).
- Order: mode permission check → hooks → mode `cb` (an error drops the message) → `cancel` check → `chatMessage` event → delivery → console log (newlines replaced).
- Inbound SecureEvents (registered in `Whip.register`):
  - `whip_chat:messageEntered` — `params = { { 'message', 'string', 256 }, { 'mode', 'string', 32, '' } }`, `rateLimit = 400`, `burst = 3`, `whileDead = true`, `requirePlayer = false` (works at the character screen). Client sends only message and mode; the server sets the author.
  - `whip_chat:init` — `rateLimit = 1000`, `whileDead`, `requirePlayer = false`; sends the player's allowed modes.
- Composer submit: a line starting `/` runs `ExecuteCommand(line:sub(2))` on the client; anything unhandled reaches `__cfx_internal:commandFallback` on the server, which is echoed as chat (same 3-burst / 400 ms limit, cleaned, cut to 256).
- Line cleaning (`cleanLine`): control chars stripped, cut to 256 bytes without splitting UTF-8; whitespace-only → nothing.

## Chat: suggestions

- Server-side suggestion sweep is **off** (`local SUGGESTIONS = false` in `server/main.lua`; a code constant, not config). When on it would send `chat:addSuggestions` per player for every command they pass `IsPlayerAceAllowed('command.<name>')` (whip_core commands checked via `exports.whip_core:GetCommandAce`).
- Client: on page `loaded` and (debounced 1 s) on every client resource start/stop, every registered command the client `IsAceAllowed('command.<name>')` is offered with empty help, never overwriting an entry that has help. Built-ins added: `/toggleChat` (param `state`), `/clearchat`, `/global` (param `message`).
- To offer your command with help: `TriggerEvent('chat:addSuggestion', '/mycmd', 'What it does', { { name = 'id', help = 'player id' } })` (client) or `TriggerClientEvent('chat:addSuggestion', src, ...)`.
- Suggestions and modes are snapshotted into `OpenComposer({ placeholder = 'Say something, or / for a command', maxLength = 256, modes, suggestions, deferFocus, pad, title, onSubmit, onCancel, onScroll })` at open.

## Chat: NUI and message format

- NUI callback: `loaded` (page → Lua) → triggers `whip_chat:init`, refreshes command suggestions, sends saved hide state. If it never arrives in 15 s, F8 warns that NUI callbacks are broken.
- Lua → page: `ON_MESSAGE { message }`, `ON_CLEAR`, `ON_TEMPLATE_ADD { template = { id, html } }`, `ON_SET_ACTIVE { active }`, `ON_SCROLL { delta }`, `ON_SCREEN_STATE_CHANGE { hideState, fromUserInteraction }`, `ON_SET_SCALE { scale }`.
- Message fields: `args` (array), `color` (`{ r, g, b }` or CSS string), `template` (HTML string), `templateId` (from `chat:addTemplate`; `'print'` styles as console print), `params` (`{name}` placeholders), `multiline` (`false` clips to one line), `mode`, `whipKind = 'command'` (styled as command).
- Templates: `{0}`, `{1}`... and `{name}` (from `params`) are replaced with escaped, colour-coded values; the template HTML itself is trusted. No template: 1 arg → the bare line; 2+ → `<span class="chat-author">{0}</span>: {1} {2}...`.
- Colour codes in args: `^0` default, `^1` red `#f87171`, `^2` green `#4ade80`, `^3` amber `#fbbf24`, `^4` blue `#60a5fa`, `^5` cyan `#22d3ee`, `^6` purple `#c084fc`, `^7` white (reset), `^8` orange `#fb923c`, `^9` dim. Text is HTML-escaped before codes apply.
- Log keeps 150 rows; each message is fully opaque for 8 s; in fade mode the list shows for 8 s after the last message.

---

## Loading screen

- `whip_loadingscreen` (v1.6.2): `loadscreen 'html/index.html'`, **no** `loadscreen_manual_shutdown`, **no Lua**, no config, no convars. `fx_version 'cerulean'`, `whip_updates 'WHIPFX/whip_loadingscreen'`.
- Shows the WHIP logo (SVG shapes; the I's four circles light one at a time with random interaction icons; the W's circle wears `pickup`, the P's `store`) over a three.js blueprint (`html/bp/bp.js`, `scene.json`, `atlas-*.webp`). Needs WebGL 2 (probed first); without it, or if a file fails, the logo shows on black.
- Shutdown: whip_core's `client/spawn.lua` `CompleteJoinSpawn` (no spawnmanager) does `NetworkResurrectLocalPlayer`, waits up to 5 s for collision, `DoScreenFadeOut(0)` and waits until faded (≤ 30 frames + 1), then `ShutdownLoadingScreen()` and `TriggerEvent('playerSpawned', { x, y, z, heading })`. Black is under the loading screen before it goes, so the spawn point never flashes.
- whip_core closes **any** loading screen this way (doc `what-you-can-change`): to use another, remove this one and ensure yours. whip_core only ever calls `ShutdownLoadingScreen()`; nothing in WHIP calls `ShutdownLoadingScreenNui`, so a replacement that sets `loadscreen_manual_shutdown 'yes'` must dismiss itself.
- Run one loading screen: the setup report (`whipsetup` in the server console, `server/setup_report.lua:203-208`) flags any other running resource with `loadscreen` metadata as "a second loading screen beside whip_loadingscreen: take one out".
- Preview: `node dev/bp/serve.js` (preview.html with logo variants from `css/variants.css`, `?variant=...&bg=white|black`). Edit `dev/blueprint.js` and run `node dev/blueprint.js` (Node + Chrome; `CHROME` env var) to regenerate. `dev/`, `preview.html` and `variants.css` are not shipped.

## whip_core integration summary

- Phone uses whip_core: `SecureCallback`, `Callback`, `RegisterItem`, `RegisterItemDefaultMetadata`, `RegisterPanelItem`, `RegisterAccessorySlot`, `GetAccessorySlots`, `RegisterUseHandler`, `FindItem`, `FindAllItems`, `GetItemAt`, `SetItemMetadata`, `GetItemCount`, `GetPlayer`, `GetPlayers({ light = true })`, `GetCharacterNames`, `CanSeePlayerName`, `CheckPicture`, `HasDevTools`, bank exports (`GetCharacterBankAccounts`, `GetBankAccount`, `GetBankTransactions`, `BankTransfer`, `GetBankAccessList`, `GrantBankAccess`, `CanGrantBankAccess`, `RevokeBankAccess`, `CreateBankAccount`, `CloseBankAccount`), job exports (`GetPlayerJobs`, `GetJob`, `GetJobEmployees`, `GetJobRoles`, `ClockOn`, `ClockOff`, `SetPlayerRole`, `FirePlayer`, `CanHirePlayer`, `HirePlayer`, `CreateJobRole`, `UpdateJobRole`, `DeleteJobRole`), `RegisterAskChannel`/`AnswerAsk`, `GetSkillCheckSettings`, `SkillCheck`, `AddAction`, `RegisterPadAction`, `SetScreenOpen`, `SetScreenArea`, `BlockControls`/`UnblockControls`, `PlayEmote`/`CancelEmote`/`IsEmoting`, `FreeHands`, `IsPlayerDead`, `IsGameInputFree`, `IsInventoryOpen`/`CloseInventory`, `Notify`, `Get/SetPlayerSetting('voice.callVolume')`, `GetLoreCharacters`/`GetLoreCharacter`; satellite helpers `Whip.register`, `Whip.ready`, `Whip.core`, `Whip.voice`, `Whip.voiceSystem`, `Whip.padScreen`, `Whip.skillCheckGame`, `Whip.card`, `Whip.command`.
- whip_core calls into the phone only via `exports.whip_phone:ReloadCache()` (admin panel, `pcall`, only when started). whip_core "does not know the phone exists" otherwise: invites go through the ask channel; skill games through `Whip.skillCheckGame`.
- Replacing the phone (doc `what-you-can-change`): stop `whip_phone` and run your own using `SetScreenOpen`, `SetScreenArea` and `FreeHands`. A phone-like ask channel: `RegisterAskChannel('phone', deliver)` (another running resource's name is refused).
- Chat uses whip_core: `SecureEvent`, `OpenComposer`/`FocusComposer`/`CloseComposer`/`IsComposerOpen`, `IsAnyScreenOpen` + `whip_core:ui:stateChanged`, `GetPlayerFullName`, `GetPlayersInRange`, `IsPlayerLoaded`, `NotifyPlayer`, `GetCommandAce`, `AddAction`, `IsControllerActive`, `Whip.playerSetting`, `Whip.command`. Replacing chat: any resource handling stock chat events.

## Gotchas

1. A SecureCallback for a phone app must declare `params = { { 'args', 'any' } }`, or `args` is always `{}`.
2. A built-in module needs both a `Config.Modules` entry and its own `files {}` line in whip_phone's fxmanifest; globs in folder names ship nothing.
3. `RegisterModule` lives in whip_phone's client memory: re-register on `onResourceStart('whip_phone')`. It must be called from your resource (not the F8 console), the id must start with a letter, and built-in/dev-app ids are refused.
4. `RegisterModule`'s `ns` is not validated: the page may call any `<ns>:*` callback for every registered ns, so every handler must validate `source`/args itself. Pick a unique `ns` (default: your resource name).
5. Phone module `render` runs for every display at once: never change state inside it. Use `app.asset()` for files; bare relative paths resolve against whip_phone's page.
6. Session `name` is the SIM owner's, not the holder's. Bank and Business are the holder's character regardless of SIM.
7. `RunApp` blocks: call from a thread. It returns `nil, why` (not a table) when it cannot start; `{ passed = false, why = 'cancelled' }` on give-up.
8. Client `Open`/`Close` exports return nothing; server ones return `true` without confirming anything opened.
9. Server `Push`/`Notify` reach the player's page even if the phone is away; Bank/Business pushes from whip_phone itself are only sent when the target carries a phone.
10. Business clock-on through the phone passes `by = source`: whip_core refuses with "This job puts people on duty itself" on `selfClockOn = false` jobs. Your own server `ClockOn(src, job)` without `by` bypasses that. Clock-off always works, even downed.
11. Bank invites and job offers are in memory only: lost on whip_phone restart, 24 h TTL, max 10 per account/job, 10 s cool-down after decline/take-back.
12. A blocked sender is never told: messages "send", calls ring out. Lore numbers can't be blocked; texts received while blocked stay hidden after unblock.
13. Voice is mandatory to use the phone: no voice system → the phone shows `VoiceDownText` and only B works; invites fall back to whip_core's on-screen dialog.
14. `whip_phone:client:opened` is not for animations: the phone plays `Config.Emotes` itself; a second animation fights it.
15. whip_chat does not `provide 'chat'`: `exports.chat:addMessage` errors; use `exports.whip_chat:addMessage` or the events.
16. Chat routing is local (network range, same routing bucket) by default; use `/global`, `routeMessage(..., true)` or `ref.setRouting(-1)` in a hook or mode `cb` for server-wide lines. Players at the character screen only reach their own bucket.
17. Server-side command suggestions are off; give help text yourself with `chat:addSuggestion`.
18. Do not add `loadscreen_manual_shutdown` to a loading screen on WHIP: whip_core only calls `ShutdownLoadingScreen()`.
19. `Config.BlockControls` with a misspelt group makes whip_core refuse the whole block (only Start/Esc stay blocked; one console warning).
20. The phone's `phone_numbers` FK targets whip_core's `characters`; deleting a character cascades its numbers' contacts/messages/calls (lore numbers have NULL charId).

## Docs vs code

- FRAMEWORK.md says `inviteGone` is sent from whip_core's `whip_core:client:serverAskCancel`; code listens to the local `whip_core:ask:cancelled` and only from whip_core (`whip_phone/client/main.lua:641-644`; emitted by `whip_core/client/ui.lua:1164-1167`).
- FRAMEWORK.md session return `{ number, name, sim, settings, card, mine }` omits `home` (`whip_phone/server/contract.lua:170`).
- FRAMEWORK.md `settings:numbers` returns `{ current, state, numbers }`; code also returns `currentMine`, `currentLocked`, and `state = 'nophone'` (`server/contract.lua:412-418`).
- FRAMEWORK.md lists dial refusals "Number not in service", "Busy" only; code also refuses 'A phone number is 10 digits', 'You cannot call yourself', 'You are already in a call', 'The number you called is unavailable', `Config.VoiceDownText`, 'That call has ended' (`server/calls.lua:372-444`).
- FRAMEWORK.md bank `account` history omits `party` (`server/bank.lua:221`).
- MODULES.md id rule "lowercase a-z 0-9 _ -, up to 32"; code also requires the first character to be a letter (`client/main.lua:61`, `html/core/os.js:22`).
- Undocumented in MODULES.md: notification fields `force`, `icon`, `pic`, `frame`, `sounds` (`os.js:728-743`); app members `id`, `esc`, `fold()`, `callVolume()` and hook `destroy` (`os.js:300`, `os.js:331-380`); `theme` setting (`contract.lua:57`).
- README's server export list omits `ReloadCache` (`server/main.lua:45`).
- Rate limits not in docs: `session` and `settings:card` are 1000 ms / burst 3 (`server/contract.lua:153`, `server/card.lua:13`).
- `html/core/main.js:133` handles a `focus` page message that `client/main.lua` never sends; `bridge.js` header omits it.
- Open question: whip_chat's hook `updateMessage({ template = ... })` substitutes `'@default'` (`whip_chat/server/main.lua:222`) but `html/js/chat.js` has no `@default` expansion, so such a template would render the literal text.
- Open question: chat `mode` and client mode `isChannel`/`isGlobal` are forwarded but chat.js does not display or act on them; routing for a mode is whatever its `cb`/hooks set.
