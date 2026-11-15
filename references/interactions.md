# Interactions: AddAction, prompts, the F1 wheel, server points, conversations

WHIP's single interaction system (it replaces ox_target / qb-target / qb-radialmenu / ox_lib textUI): client `AddAction` (world prompts, car parts, model props, aim boxes, the F1 wheel), server `AddPoint` (prompts whose press runs on the server), `StartConversation` (NPC dialog capsule), held props and the hand press, prompt styles, glyphs, and item right-click options. Built from doc anchor `#interactions` (063-interactions: `#guide-interactions`, `#interactions-at`, `#interactions-require`, `#interactions-ctx`, `#interactions-options`, `#interactions-menus`, `#interactions-held`, `#interactions-press`, `#interactions-input`, `#interactions-style`, `#interactions-glyphs`, `#interactions-runtime`, `#interactions-conversations`) and source `whip_core/client/actions.lua`, `client/interact.lua`, `client/interact_press.lua`, `client/interact_style.lua`, `client/prop_prompts.lua`, `client/vehicle_prompts.lua`, `client/aim_box.lua`, `client/prompt_typing.lua`, `client/radial.lua`, `client/runtime_points.lua`, `client/aim_dot.lua`, `client/ui.lua`, `shared/interact_spec.lua`, `server/runtime_points.lua`, `server/audience.lua`, `server/conversations.lua`, `server/held_props.lua`, `server/item_options.lua`, `server/inventory.lua`, `config.lua`, `types/client.lua`, `types/server.lua`, `types/events.lua`.

## Contents
- Model and rules of thumb
- Config keys that matter
- AddAction(def) — CLIENT
- at: where an action lives
- require: who may use it
- ctx: what your callbacks get
- options and menus
- Typing into a prompt (ctx.beginInput)
- Styles (style field, SetActionStyle, Config.Interact3D)
- Glyphs (icon names)
- UpdateAction / SetActionStyle / RemoveAction / RemoveActionGroup / GetAction — CLIENT
- The F1 radial wheel
- Car parts (at.vehiclePart)
- Props of a model (at.model)
- Aim boxes (at.aimBox)
- The hand: PlayPress, HoldProps and friends, AimDot
- Server points: AddPoint / UpdatePoint / RemovePoint / GetPoints — SERVER
- Audiences
- Conversations: StartConversation / UpdateConversation / EndConversation / GetConversation — SERVER
- Item right-click options (contextOptions, AddItemOption, RemoveItemOption)
- Porting from ox_target / qb-target
- Gotchas
- Docs vs code

## Model and rules of thumb

- One client call, `AddAction(def)`, puts "the player can do X" anywhere: a prompt at a point, riding an entity/netId, on every prop of a model, where the player aims on a box, on a car part's prompt stack, or on the F1 wheel. `at` says where; every other field reads the same.
- Declare actions inside `Whip.register(function() ... end)` so they come back when whip_core restarts. An action is yours by `id`: the same id again replaces it (scoped per resource: two resources can both have `'bench'`). Everything you added goes when your resource stops.
- Internally each action is mounted as engine entry `act:<resource>:<id>` (one per option `act:<resource>:<id>#<optionId>` on car parts / the wheel when there are several options) (`client/actions.lua:503`).
- Server-side prompts use `AddPoint`; the press is re-checked on the server (distance, audience, requirements) and `onUse(source, use)` runs there. On clients a point is mounted as core action `rpoint:<pointId>` (`client/runtime_points.lua:22`).
- E (A on a pad) acts on the focused prompt. Prompts hide while a screen/bar holds input, while the player is dead (unless `require.alive = false`), and while in a vehicle (unless `require.vehicle = 'in'`). Ground items, containers, doors make their own prompts.
- `onSelect` runs in its own thread (it may Wait). `label` / `icon` / `image` functions and `canInteract` are called every draw/pass and must not wait.
- **Many prompts: use plain text, not functions.** A function field is called every frame for every prompt in view,
  and each call crosses from whip_core into your resource. Measured on a store with ~90 product prompts:
  function labels cost about 0.7 ms on the resource and pushed whip_core from about 0.3 to 0.9 ms. When the text
  changes rarely (a price), give a string and `UpdateAction` it (or remove and add again) when it changes.
- Validation is lenient except `require`: unknown fields, wrong types, out-of-range numbers are warned (F8 + third return) and dropped or clamped; an unknown `require` word refuses the whole action (an ignored requirement would open it to everyone).

## Config keys that matter

| Key | Default | Meaning |
|---|---|---|
| `Config.InteractVisibleRange` | `5.0` | Metres a prompt fades in (default `seeFrom`) |
| `Config.InteractActiveRange` | `2.0` | Metres the key works (default `reach`) |
| `Config.InteractFocusCone` | `40.0` | Half-angle (deg) of the aim cone for `focusMode = 'aim'` |
| `Config.InteractFocusConeNear` | `100.0` | Cone for `focusMode = 'near'` (doors) |
| `Config.InteractFocusNearWeight` | `0.85` | How far `'near'` weights proximity over aim (1.0 ignores aim) |
| `Config.InteractRenderer` | `'world'` | `'world'` (3D, hidden by walls) or `'nui'`; doors exist only in `'world'`; `/interactrenderer` swaps live |
| `Config.Interact3D` | table | The `'default'` style + `styles` + `groupStyles` (see Styles). Notable: `badgePx = 68`, `labelPx = 98`, `gap = 0.35`, `fadeMs = 100`, `labelRows = 8`, `cullBehind = true`, `flashMs = 900`, `depthBias = 0.30`, `stackGap = 0.25`, `stackAlpha = 0.45`, `previewScale = 3.4`, `theme = 'keycap'`, `dark = false`. `/i3d <px>` retunes badge size live |
| `Config.InteractPress` | `{ enabled = true, maxDistance = 2.5, followHand = true }` | The hand press (also `/whip` → Settings → Config, "Hand press") |
| `Config.AimDot` | `true` | Aim dot for weapons |
| `Config.Controller.RadialHoldMs` | `500` | Default D-pad-down hold to open the wheel on a pad (player pref `pad.radialHoldMs`, 150–2000) |
| `Config.Conversations` | table | Dialog capsule: `size 1.0`, `height 0.375`, `minSizeFrom 4.0`, `maxGrow 1.75`, `margin 0.12`, `swing 10.0`, `range 6.0` (walk further and it ends), `speakingText`, `busyText`, `watcherBubbles = true`, `npcLines = 4`, `noAnswerHalfText`, `noAnswerText` |

## AddAction(def) — CLIENT

### AddAction(def) — CLIENT
Puts an action in the world. "World prompts" below = every `at` except `radial` and `vehiclePart` (i.e. coords, entity, netId, model, aimBox).

| Field | Type | Where read | Notes / default |
|---|---|---|---|
| `id` | string? | all | Yours. Omitted: a stable auto id `auto:%08x` hashed from group, label (string only; a function label gives `<function>`), part, model, bone, radial, entity/netId, coords, offset and option ids (`client/actions.lua:1452`). Give your own id when the label is a function |
| `at` | table | all | Required. Exactly one place (see `at`) |
| `label` | string \| fn(ctx) | all | Function asked every draw, must not wait. The wheel requires one |
| `icon` | string \| fn(ctx)? | all | A glyph name, or text drawn as is. World prompt default `'E'` (shows the player's Interact key, `A` on a pad). On the wheel: no icon, or text over 3 letters, draws the label's first letter |
| `image` | string \| fn(ctx)? | prompt, car part | Picture above the label: path under whip_core's `html/` (`'img/vehicles/<model>.webp'`) or a `https://cfx-nui-<resource>/…` URL |
| `description` | string \| fn(ctx)? | wheel only | Pill text beside the name while aimed; a function is asked as the wheel opens |
| `require` | table? | all | See `require`. Strict |
| `canInteract` | fn(ctx)? | all | Your rule on top of `require`; return truthy to offer. May return `false, 'reason'` (the reason shows in `GetAction().options[i].why`). FiveM-truthy: `false`, `nil`, `0` are no |
| `onSelect` | fn(ctx) | all | Required here or on options (an option inherits the nearest one above it). Own thread |
| `options` | table? | all | See options. Menus (nested `options`) only on world prompts |
| `reach` | number? | world prompts | 0.5–25, default `Config.InteractActiveRange`. Match your server's distance check. `distance` (ox/qb spelling) is read as `reach` with a warning |
| `seeFrom` | number? | world prompts | Spec range 1–1000, default `Config.InteractVisibleRange`; then capped by the grid (see Docs vs code) |
| `scale` | number? | world prompts | 0.25–4, relative size |
| `sizeRange` | number? | world prompts | 0.5–25; distance the size is designed at (default its `reach`, so changing reach resizes it) |
| `focusMode` | `'aim'` \| `'near'` | world prompts | `'aim'` (default) the one looked at; `'near'` the closest in a wide cone (doors, counters) |
| `onBlur` | fn()? | world prompts | Called when it stops being the focused one (menus also fold back automatically) |
| `style` | string \| table? | world prompts | See Styles |
| `holdMs` | number? | world prompts | 0–10000. Hold E/A this long (ring fills); release, looking away or scrolling cancels. Per option too (`0` = press). Menu entries are always a press. The server must still check |
| `press` | `true` \| vector3 \| `{ coords?, offset?, normal? }` | world prompts, car parts | Hand reaches out (looks only; `onSelect` runs at once). Per option (`false` for one with its own anim). Not read on the wheel |
| `first` | boolean? | car parts | Put above the part's own options (Open Door, Lock) while `canInteract` says yes. Per option too |
| `onGone` | fn(ctx)? | `at.entity` | Once the entity and the action are gone: `ctx = { id, owner }`; re-add from here |
| `onFound`, `onLost` | fn(ctx)? | `at.model` | Each prop of the model within 50 m / leaving (60 m, or gone): `ctx = { id, owner, entity, model, prop, coords }`, each in its own thread. In `onLost` use `ctx.coords` (entity may be gone) |
| `group` | string? | all | For `RemoveActionGroup` |
| `enabled` | boolean? | all | `false` hides it without removing it |

A field not read on the chosen place (e.g. `scale` on the wheel, `description` on a prompt) is warned "`x` is not read on the F1 wheel. It was ignored" (`client/actions.lua:1340`).

Returns: `id, false, warnings` on success, or `false, reason, warnings`. `warnings` is a list of strings or `nil`. The second value is literally `false` on success so the third survives the export boundary (a `nil` would truncate). Refusal reasons include: not a table; no `at` / an `at` naming nothing or several places (`'at names 2 places (coords, entity) — an action is in one: ...'`); `at.coords must be a vector3 (or { x, y, z })`; `at.entity does not exist`; bad `at.netId`; `at.model` not a string/list of strings; bad `at.aimBox`; `onSelect is required`; `the wheel needs a label`; two options with the same id in one menu; an unknown/ill-typed `require` word; `a vehiclePart action is used standing at the car, alive — drop alive = false / vehicle = 'in'`; `no vehicle part called "x"`; or a mount failure (`'action "x": <why>'`, the action is not kept).

```lua
exports.whip_core:AddAction({
    id = 'bench', at = { coords = vector3(12.1, -1105.3, 29.8), heading = 90.0 },
    label = 'Weapon Bench', icon = 'store',
    require = { job = 'gunsmith', item = 'toolkit' },
    onSelect = function(ctx) TriggerServerEvent('mygunsmith:openBench') end,
})
```

Warning texts look like `lable is not a field — use 'label'. It was ignored`, `reach is a number from 0.5 to 25 — got 40, so 25 is used`; printed once per resource+text as `[whip_core:actions] <owner>, action "<id>": <warning>` (`shared/interact_spec.lua:549`). Common hint mappings (`shared/interact_spec.lua:176`): `distance/radius/activeRange/useRange` → `reach`; `range` → `reach` or `seeFrom`; `visibleRange/drawDistance/viewDistance` → `seeFrom`; `callback/action/onPress/onClick/event/serverEvent/onUse` → `onSelect`; `condition/canUse/canSee` → `canInteract`; `name/text/title` → `id`/`label`; `desc` → `description`; `img/picture` → `image`; `size` → `scale`; `requires` → `require`; `disabled` → `enabled = false`; top-level `coords/entity/heading/offset/bone/model/vehiclePart` → inside `at`; top-level `job/item/zone/ace/groups/items/gang/citizenid` → inside `require`; `tint/color/opacity/badgeScale/...` → `style = { ... }`; `hold/holdTime/holdDuration/duration` → `holdMs`; `touch/pressAnim/handPress` → `press`.

## at: where an action lives

Exactly one "place" key: `coords`, `entity`, `netId`, `model`, `vehiclePart`, `aimBox`, `radial`. Modifier keys are only valid with certain places (`shared/interact_spec.lua:135`); used elsewhere they are warned and ignored.

| at | Kind (`GetAction().mounted`) | Notes |
|---|---|---|
| `{ coords = vector3, heading?, follow? }` | `'prompt'` | With `heading` it stands like a sign (not drawn from behind unless style `cullBehind = false`); without, it billboards. A `vector4`'s `w` (or a table's `w`/`heading`/`[4]`) is also read as heading. `follow = function() return x, y, z, heading end` moves it (called only while in range) |
| `{ entity = handle, offset?, bone?, heading? }` | `'prompt'` | Local entity. Must exist when added. Removed ~3 s (6 × 500 ms ticks) after the entity disappears; `onGone` then called, or a console line says so. `offset` in entity frame; `bone` is a bone NAME (`GetEntityBoneIndexByName`); with `heading` it is a sign at that yaw from the entity's facing, turning with it (`180` = on its back) |
| `{ netId = n, offset?, bone?, heading? }` | `'prompt'` | Networked NPC/car. Suspended while not streamed in, re-registered when it streams back (any handle). The id may come from the server before it streams in. Use this for anything networked |
| `{ model = 'prop_x' \| {list}, offset?, heading?, faces?, perModel? }` | `'props'` | Every prop of the model(s) nearby, offered on the nearest one, never from inside a car. Names only (hash refused). `offset`: x across, y out of its face, z up. `heading`: sign at that turn from the prop's facing (try 0/90/180); none = faces the player. `faces = 2` for two-sided props. `perModel = { ['prop_x'] = { offset, heading } }` overrides one model (what it leaves out comes from the action's). `/actionplace <id>` aims it and copies the line |
| `{ vehiclePart = 'hood' }` | `'part'` | See Car parts |
| `{ radial = true }` | `'radial'` | F1 wheel entry, sorted by label |
| `{ aimBox = 'vehicle' \| 'object' \| 'ped' \| 'world' \| {list} }` | `'aimbox'` | See Aim boxes. Casts a ray every frame: add only while meaningful |

## require: who may use it

Every key given must pass. Checked first (cheap), before `canInteract`. The client uses it to decide what to offer; re-check on the server. Allowed words (`InteractSpec.REQUIRE`): `alive, vehicle, job, onDuty, jobPermission, item, held, zone, charId, ace`. Any other word refuses the whole action (`require.jobs is not a requirement — use 'job'`).

| Key | Example | Passes when | `why` when it fails |
|---|---|---|---|
| `alive` | `alive = false` | Also offered to the downed (default: nobody downed) | `downed` |
| `vehicle` | `'in'` / `'out'` | In a vehicle / on foot. World prompts default to on foot; the wheel to either | `not in a vehicle` / `in a vehicle` |
| `job` | `'police'`, `{ 'police', 'ems' }` | Has a role at one of these jobs (key or jobId) | `job` |
| `onDuty` | `true` | ...and is clocked on there; with no `job`, on duty anywhere | `off duty` |
| `jobPermission` | `'canManage'` | ...and that role has this permission; with no `job`, any job granting it | `job permission` |
| `item` | `'toolkit'`, `{ item = 'lockpick', count = 2 }`, `{ 'toolkit', 'gloves' }` | Carries ALL of them (count default 1). A table with an `item` field is one entry; otherwise a list | `item <key>` |
| `held` | `'jerry_can'` or a list | The item in hand (`SetHeldItem`) is one of these | `held` |
| `zone` | `'mrpd'` or a list | Standing inside one of these zones (client zone id or saved zone key) | `zone` |
| `charId` | `12` or a list | One of these characters | `character` |
| `ace` | `'whip.devtools'` | Holds this ACE. Asked of the server once (`whip_core:checkAcePermission`) and cached; the first ask answers "no" until the reply; failed asks retry after 2 s (`client/actions.lua:144`) | `permission` |

Type rules (`shared/interact_spec.lua:509`): `alive` boolean; `vehicle` `'in'|'out'`; `onDuty` boolean; `jobPermission` string; `item` entries a key or `{ item = 'key', count = n }`; `held` key or list of keys.

- `vehiclePart` actions refuse `alive = false` and `vehicle = 'in'` (always used on foot, alive).
- Options: an option's `require`/`canInteract` add to the action's (can only narrow). Exception: `alive` and `vehicle` resolve option-first, else the action's (`requireField`, `client/actions.lua:291`) — an option can say `alive = false` alone.
- Cost: `require` is free; `canInteract` crosses into your resource on every pass (about 95×/s per option near a car). For state only you know, add the action while it holds and remove it after.
- Doors read rules the other way round (any one passes) — a door's `jobs` key is NOT an action `require` word.

## ctx: what your callbacks get

`label`, `icon`, `image`, `description` functions and `canInteract` get a reused ctx without functions; `onSelect` gets a fresh ctx with the verbs.

| Field | Description |
|---|---|
| `id`, `owner`, `option` | Your action id, your resource, the option id (`'default'` for an action without options, `'opt<n>'` when an option has no id) |
| `under` | `onSelect` in a menu: id of the menu option it was chosen under; `nil` at top level |
| `entity` | Entity aimed at / ridden / the part's car (`nil` for `aimBox = 'world'` and plain coords) |
| `coords` | The prompt's point now (vector3); car parts: the car's coords |
| `model`, `face`, `prop` | `at.model`: model name, face (1 or 2), the prop's stable id |
| `world`, `normal` | `aimBox` with `'world'`: `world = true` when the map itself was hit; `normal` the surface facing (vector3) or `false` |
| `player` | Prompt on a real player's ped: `{ serverId, playerIdx, activeJob, isDead }` (from that player's state bags); `nil` for NPCs. Name: `GetPlayerFullName(ctx.player.serverId)` |
| `typed` | World prompts: text typed so far with a blinking caret, else `false` (a value, use it in your label) |
| `flash(r, g, b)` | onSelect only. Tint the prompt for a moment (no-op on the wheel) |
| `status(text, ms?)` | onSelect only. Text on the prompt; on the wheel an `info` notification (default 2500 ms) |
| `refuse(why?)` | onSelect only. Amber flash (255,170,60) + reason for 2500 ms; on the wheel an `error` notification (3000 ms) |
| `beginInput(opts)`, `cancelInput()`, `inputText()` | onSelect only. See Typing. On the wheel `beginInput` returns `false` |

```lua
exports.whip_core:AddAction({
    id = 'frisk', at = { aimBox = 'ped' }, label = 'Frisk', reach = 2.0,
    require = { job = 'police', onDuty = true },
    canInteract = function(ctx) return ctx.player ~= nil and not ctx.player.isDead end,
    onSelect = function(ctx) TriggerServerEvent('police:frisk', ctx.player.serverId) end,
})
```

`onSelect` is re-checked (`check`) right before it runs; if anything stopped passing, it silently doesn't run. Errors in callbacks are printed once per action+field: `[whip_core:actions] onSelect of "<key>" threw (reported once): ...`.

## options and menus

Each option: `id`, `label`, `icon`, `image`, `description`, `require`, `canInteract`, `onSelect`, `enabled`, `holdMs`, `press`, `first`, `options`, `stay` (`InteractSpec.ACTION_OPTION`). Text fields and `onSelect`/`press` fall back: option → menus above it (nearest first) → action. Option ids default `'opt<n>'`; must be unique within one menu level. A world prompt shows options as a scrollable stack; the wheel shows each as its own entry; a car part adds each to the part's stack.

```lua
options = {
  { id = 'buy', label = 'Buy', onSelect = function() TriggerServerEvent('shop:buy') end },
  { id = 'stock', label = 'Restock', require = { job = 'shopkeep', onDuty = true },
    onSelect = function() TriggerServerEvent('shop:restock') end },
}
```

Menus (world prompts only; on car parts and the wheel a nested `options` is warned and dropped):
- An option with its own `options` (any depth) gets `  ›` after its label; choosing it shows its children on the same prompt with a `Back` (glyph `back`) first. Pressing a leaf, or looking away (onBlur), folds back to the top.
- A nested option must also pass every option above it (`require`, `canInteract`, `enabled`) and inherits what it leaves out.
- Filled menu: `options = function(ctx) return { ... } end` is called each time the menu opens, in its own thread, with the onSelect-style ctx (without verbs; `ctx.option`, `ctx.under` set). Shows "One moment…" (glyph `timer`) until it returns, "Nothing here" (glyph `info`) for an empty list, "Not available" (glyph `warning`) if it throws. The answer is validated like any options (bad `require` or duplicate id: that row is dropped with a warning). Going Back to a filled menu shows the list it had without asking again. A late answer from an older open is dropped.
- `stay = true` on an option down a menu keeps the prompt on that menu after `onSelect`; a filled menu is refilled after `onSelect` finishes (the old list stays shown meanwhile).

```lua
{ id = 'orders', label = 'My orders', options = function(ctx)
    local list = {}
    for _, o in ipairs(exports.whip_core:Callback('mycafe:myOrders') or {}) do
      list[#list + 1] = { id = 'o' .. o.id, label = o.name, stay = true,
        onSelect = function() exports.whip_core:Callback('mycafe:collect', o.id) end }
    end
    return list
end }
```

## Typing into a prompt (ctx.beginInput)

From a world prompt's `onSelect`: `ctx.beginInput(opts)`. The prompt steps aside; on keyboard a chat-capsule-style field ("Start typing", Enter gives, Esc or Backspace on empty leaves; mouse still looks around); on a pad WHIP's 3D on-screen keyboard (left stick moves a circle, D-pad steps keys, A types, X deletes, Y space, LT symbols, RB or Done gives, B or Cancel leaves; walking held off; numeric gets a number pad). Swapping input device mid-typing keeps the text. Starting a new input cancels the running one (its `onCancel` fires).

| opts | Type | Default / meaning |
|---|---|---|
| `max` | number? | Max characters: 9 for a number, 64 for text (min 1) |
| `numeric` | boolean? | `true` (default): digits only, no leading zero, number pad. `false`: any text |
| `title` | string? | What is being typed; default the option's own words |
| `prefix` | string? | Shown before the text (`'$'`) |
| `commas` | boolean? | Show a number grouped (1,250); `onSubmit` still gets digits |
| `placeholder` | string? | Default `'Start typing'` |
| `value` | string? | Starting text |
| `icon` | string? | Glyph; default the option's (accepted by `Interactions.beginInput`, `client/interact.lua:651`; not in the docs) |
| `onSubmit` | fn(text) | Required; value given |
| `onCancel` | fn()? | Left, walked off, or replaced by another input |
| `onChange` | fn(text)? | Every change |

`ctx.typed` (string with caret, or `false`) lets your `label` function show progress; `ctx.inputText()` returns the current text or `nil`; `ctx.cancelInput()` ends it.

## Styles (style field, SetActionStyle, Config.Interact3D)

A style sets a world prompt's size, colour, visibility, motion. Resolution: the prompt's own `style` → its group's `Config.Interact3D.groupStyles[group]` → `'default'` (= `Config.Interact3D` itself). A named style or table inherits gaps from its `base`, then `'default'`. WHIP ships `subtle` (`badgeScale 0.85`, `labelScale 0.9`, `opacity { seen = 0.0, inReach = 0.6, focused = 0.95 }`: hidden until in reach) and `lively` (`appear/focus/press = 'pop'`, `easing = 'out'`). Server owners add names in `Config.Interact3D.styles` and change `default` by editing the top-level `Config.Interact3D` values. `groupStyles` keys (WHIP's own prompt families): `doors`, `vehicles`, `ground_items`, `garages`, `containers`, `properties`, `conversation`, `atm`, `actions` (every `AddAction` and `AddPoint`).

```lua
style = 'subtle'
style = { base = 'subtle', badgeScale = 1.3, tint = '#ffc850', fadeMs = 250 }
```

| Field | Range / values | Notes |
|---|---|---|
| `base` | style name | Unknown name warned |
| `badgeScale`, `labelScale` | 0.25–4 | On top of the action's `scale` |
| `opacity` | `{ seen, inReach, focused }`, each 0–1 | Default 0.35 / 0.85 / 1.0; `seen = 0` hides until in reach |
| `tint`, `labelTint` | `'#ffc850'`, `{ 255, 200, 80 }`, `{ r, g, b }` | White = no change |
| `fadeMs`, `crossfadeMs`, `slideMs`, `appearMs` | 0–2000 | Fades (100), ring→key, stack slide, arrival (220) |
| `flash` | `'blink'` (default, twice) \| `'fade'` (once) | The `ctx.flash` answer |
| `flashMs` | 100–3000 | Default `Config.Interact3D.flashMs` (900) |
| `gap`, `stackGap`, `stackAlpha` | 0–1 | Spacing, stack spacing, unselected option alpha |
| `previewScale` | 0.5–6 | Picture size |
| `cullBehind` | boolean | `false` draws a sign-like prompt from behind too |
| `easing`, `fadeEasing`, `crossfadeEasing`, `slideEasing` | `'smooth'` (default), `'linear'`, `'out'`, `'inOut'`, `'back'` | `easing` sets all three |
| `appear` | `'fade'` (default), `'pop'`, `'slide'`, `'none'` | |
| `focus` | `'none'`, `'pop'`, `'pulse'` | Becoming the focused one |
| `idle` | `'none'`, `'pulse'`, `'bob'` | While not focused |
| `press` | `'none'`, `'pop'` | When used |
| `labelWeight` | 400–800 (700) | |
| `labelOutline` | 0–8 (3) | Outline width |
| `labelOutlineColour` | colour (black) | British spelling |
| `labelCase` | `'upper'` \| `'none'` | |
| `labelShadow` | boolean | `false` removes it |
| `theme` | `'keycap'`, `'classic'`, `'glass'`, `'rim'`, `'dot'` | Left out: the player's "Prompt shape" setting (pause menu → Map & HUD), default `Config.Interact3D.theme` (`'keycap'`) |
| `dark` | boolean | Black/white swapped; left out: player's "Dark prompts" setting (default `Config.Interact3D.dark`) |

Font cannot be changed (Plus Jakarta Sans). A misspelt style name or field is warned in F8 and left out. `UpdateAction(id, { style = ... })` with only `style` in the patch is the same as `SetActionStyle` (in place, no fade).

## Glyphs (icon names)

From `html/js/glyphs.js`: `lock` `unlock` `lockpick` `door` `house_door` `hood_closed` `hood_open` `trunk_closed` `trunk_open` `trunk_lid` `garage` `car` `store` `turbo` `furnish` `theme` `house` `pickup` `bank` `deposit` `withdraw` `back` `fuel` `nozzle` `cash` `dollar` `talk` `phone` `bag` `emote` `id` `power` `headlights` `seat` `devtools` `place` `give` `eat` `respawn` `objective` `target` `pin` `star` `timer` `fail` `success` `info` `warning` `object` `ped` `camera`, plus `mfr_<brand>` for a car maker's badge. Other text is drawn as is (`'$'`); the default `'E'` shows the player's Interact key (or `A` on a pad). On the F1 wheel, text longer than 3 letters draws the label's first letter instead. `AddPoint` icons must be glyph-like names (`^[%w_]+$`, ≤ 40 chars).

## UpdateAction / SetActionStyle / RemoveAction / RemoveActionGroup / GetAction — CLIENT

### UpdateAction(id, patch) — CLIENT
Lays `patch` over one of your actions (shallow merge; an `at` in it replaces the old `at` whole) and re-adds it. A refused change leaves the old action in place.
Returns: `true, false, warnings` or `false, reason, warnings`. `no action "x" of yours`; `a patch is a table of the fields to change`.

### SetActionStyle(id, style) — CLIENT
Restyles one of your world prompts in place (no fade, keeps its place: e.g. turn red as a timer runs out). `style`: name, table, or `nil` for the default. On a wheel/part action: warned "style is not read on ...". On `at.model`, every prop prompt found so far is restyled; later ones read the action's style.
Returns: `true, false, warnings` or `false, reason`.

### RemoveAction(id) — CLIENT
Removes one of your actions (another resource's same id is a different action, never touched). Not needed on resource stop.
Returns: `true` or `false, reason`.

### RemoveActionGroup(group) — CLIENT
Removes all YOUR actions with that `group`.
Returns: `true, count` or `false, 'a group name is required'`.

### GetAction(id) — CLIENT
Your action as plain data plus, per option, whether it would be offered to this player now and why not. First thing to check when an action never shows.
Returns: `{ id, owner, key = '<owner>:<id>', group, reach, seeFrom, enabled, at (plain values; vectors as {x,y,z[,w]}), label (if string), icon (if string), style, mounted, engineIds, options = { { id, label, offered, why } } }` or `nil`. `mounted`: `'prompt'`, `'aimbox'`, `'props'`, `'radial'`, `'part'`, or `false` (F8 says why). `why` values: `switched off`, `entity gone`, `its entity is not streamed in here`, `downed`, `in a vehicle`, `not in a vehicle`, `job`, `job permission`, `off duty`, `item <key>`, `held`, `zone`, `character`, `permission`, `canInteract threw`, `canInteract said no`, or `canInteract`'s second return.

```lua
for _, o in ipairs((exports.whip_core:GetAction('bench') or {}).options or {}) do print(o.id, o.offered, o.why) end
```

## The F1 radial wheel

- `AddAction({ at = { radial = true }, label = ..., icon?, description?, onSelect })`. Label required (string or function). One wheel entry per option. Entries sorted alphabetically by label (ties by internal id), stable across openings. Registered internally under group `'actions'` with `allowDowned = (option/action require.alive == false)`.
- Opens with key mapping `whip_radial` ("Radial Menu", keyboard default `F1`, rebindable in FiveM Key Bindings; the default applies only on first load). Pad: hold D-pad down `pad.radialHoldMs` (default `Config.Controller.RadialHoldMs` or 500 ms); opened from a pad, a second "hotkeys" wheel (pocket slots 1–5) appears too (not while downed). Aim with mouse/stick; click or A to choose; B/right-click/Backspace back; Esc or F1 closes.
- It refuses to open while another screen, bar, dialog or focus holder is up (`MayOpenScreen('radial')`). With nothing to offer it shows a placeholder "No actions available / Nothing to do here right now"; a downed player with nothing opted in sees nothing.
- While open it re-runs every condition every 250 ms and redraws when the SET of entries changes (getting in/out of a car); a wheel that had entries and lost them all closes. A label that changes on its own does not cause a redraw.
- Conditions on the wheel: `require` and `canInteract` apply, but NOT the "on foot" default (the wheel is used in cars too). `press` is not read. `ctx` verbs: `status` and `refuse` become notifications; `flash` no-op; `beginInput` returns `false`.
- Wheel entries have no menus (nested options warned and dropped). `description` (string or function, asked as the wheel opens) is shown in the pill.
- `IsRadialOpen()` — CLIENT. Returns `boolean`.
- Other F-keys: F2 inventory, F3 phone (whip_phone; the emote menu is on the wheel), F6 chat, F7 debug overlays, F8 console.

```lua
exports.whip_core:AddAction({ id = 'engine', at = { radial = true }, icon = 'power',
    label = 'Engine', description = 'Start or stop the engine', require = { vehicle = 'in' },
    onSelect = function() TriggerServerEvent('mycar:toggleEngine') end })
```

## Car parts (at.vehiclePart)

- Adds a choice to WHIP's own car-part prompt stack. Valid part keys (`client/vehicle_prompts.lua:219-337`): `'hood'` (only while the bonnet is open; engine work goes here), `'trunk'`, `'door_dside_f'`, `'door_pside_f'`, `'door_dside_r'`, `'door_pside_r'`, the inside-of-door prompts while open `'door_dside_f_in'`, `'door_pside_f_in'`, `'door_dside_r_in'`, `'door_pside_r_in'`, the single prompt of `'bike'` ("Get On"), `'bicycle'` ("Get On"), `'boat'` ("Board"), and `'fuel'` (the filler; no own options, shows only while a resource's option is on offer — whip_fuel's nozzle). Unknown key: `no vehicle part called "x"`.
- `ctx.entity` = the car, `ctx.coords` = the car's coords. `first = true` (action or option) puts it above the part's own options (Open Door, Lock) while it passes — e.g. a nozzle in hand at the filler.
- Read on parts: `id, label, icon, image, require, canInteract, onSelect, options (no menus), enabled, group, press, first`. Not read: `reach`, `seeFrom`, `scale`, `style`, `holdMs`, `description` (warned).
- Always on foot and alive: `require.alive = false` or `vehicle = 'in'` refuses the action.

## Props of a model (at.model)

- A prompt on each prop of the model(s) near the player (found by `client/prop_prompts.lua`), offered on the nearest of each model; never from a car. Prompts come and go per prop (no engine ids; `GetAction().engineIds` is empty).
- `onFound` / `onLost` watch every prop of the models within 50 m (seated too), separately from the nearest-only prompt sweep; lost at 60 m or when gone. Each runs in its own thread.
- Every option's ctx has `model`, `face`, `prop`.

```lua
exports.whip_core:AddAction({ id = 'soda', at = { model = { 'prop_vend_soda_01', 'prop_vend_soda_02' },
    offset = vector3(0.0, 0.6, 1.0), heading = 0.0 }, icon = 'cash', label = 'Buy soda',
    onSelect = function(ctx) TriggerServerEvent('vend:buy', ctx.prop) end })
```

## Aim boxes (at.aimBox)

- `'vehicle'`, `'object'`, `'ped'`, `'world'` or a list. The prompt sits where the player's look meets the bounding box of the thing aimed at (a helicopter's rotor span included), flat on that side wrapped round corners or over its top; a wall in front hides it. Offered only while the look meets one within `reach` (ray length `reach + 6` from the camera; reach measured from the player).
- `'world'`: the map itself (ground, walls): `ctx.entity = nil`, `ctx.world = true`, `ctx.normal` = surface facing. A car or prop in front wins.
- Looking away folds a menu back. Positions refresh every 100 ms by a driver thread plus per-frame `follow`.
- Costs a ray every frame: add it only while it means something (a rope in hand, an officer on duty) and remove it after.

## The hand: PlayPress, HoldProps and friends, AimDot

### PlayPress(target, opts) — CLIENT
The player's hand reaches out to a point and back, looks only (never moves/turns the player or takes control). Returns at once; do the real thing yourself before or after. Safe inside any callback. `AddAction`'s `press` does this alongside `onSelect`.

| Param | Type | Description |
|---|---|---|
| `target` | vector3 \| `{ entity, offset?, bone? }` | Point, or on an entity (offset in its frame) |
| `opts.normal` | vector3? | Surface facing (either way round): a press pushing into it is preferred, the hand stops where it meets it. Pass one for walls, doors, panels |
| `opts.onContact` | function? | Runs exactly once for a press that went out: as the hand arrives, or as a cut-short press ends (ragdoll, car, emote). Never when it returned `false` |

Returns: `true`, or `false, why`: `'off'` (presses disabled or not installed, no target, further than `Config.InteractPress.maxDistance` (2.5 m), seated, ragdolled, falling, swimming, aiming, already against the surface, no clip reaches), `'busy'` (one going out), `'dead'`.

`press` on an action: `true` → toward the prompt's point (normal from its heading if it has one); a vector3; or `{ coords | offset (entity frame), normal }`; `{ normal }` alone = prompt point facing that way. A `press` with no usable point is reported once and skipped. Picking up from the ground always plays GTA's own grab.

### HoldProps(source, props, tag?) — SERVER
Puts props in a player's hand for everyone (server makes the objects, the owning client attaches). Never use your own `CreateObject` + attach.

| Param | Type | Description |
|---|---|---|
| `source` | number | Player |
| `props` | table[] | 1 or 2 (`MAX_PROPS = 2`) of `{ model, bone?, offset? = { x, y, z }, rot? = { x, y, z } }`; `bone` default 18905 (SKEL_L_Hand); offset/rot accept `{x,y,z}` or `{1,2,3}` |
| `tag` | string? | Default `'held'`, cut to 40 chars, stored as `'<resource>:<tag>'` |

Returns: `true`, or `false, why` (`'no such player'`, `'props is a list of { model, bone, offset, rot }'`, ...). Rate: at most one new set per player per second (`SET_GAP_MS = 1000`); faster calls wait and only the newest is made, intermediate ones forgotten. The hand holds one set shared with WHIP's own (`'emote'`, `'bar'`, `'give'`, `'take'`, `'camera'`): a new set replaces the old. Your props go when your resource stops.

- **Other bones:** `bone` may be any ped bone. A bag on the back is bone 24818 (SKEL_Spine3).
- **Still the same slot:** an emote, a progress bar, a give or a take replaces a worn bag as well. To keep one worn:
  1. Watch `whip_core:heldProps:lost` for your tag, or poll `GetHeldPropsTag(src) == nil`.
  2. When the hands are free again, call `HoldProps` again.
- **Custom models:** a streamed prop needs its `.ytyp` as `data_file 'DLC_ITYP_REQUEST'`.

```lua
exports.whip_core:HoldProps(source, { { model = 'prop_cs_police_torch', offset = { 0.1, 0.0, 0.0 } } }, 'torch')
```

### DropHeldProps(source, tag?) — SERVER
Removes your props of `tag`, or with no tag whatever of yours they hold. Never anyone else's.
Returns: `true`, or `false, why` (`'they hold none of your props tagged "x"'`, `'they hold none of your props'`, `'source is a server id'`).

### GetHeldPropsTag(source) — SERVER
What the hands hold or are about to: `'<resource>:<tag>'`, or WHIP's `'emote'`, `'bar'`, `'give'`, `'take'` (also `'camera'`), or `nil`.

Event (server, local): `whip_core:heldProps:lost { source, tag, reason, by }` — your props left without you asking: `reason = 'replaced'` (`by` = the new set's tag) or `'world'` (player moved to another routing bucket). Not fired for your own drop, a new set of the same tag, logout or disconnect.

### GetOwnHeldProp(model, tag) · DropOwnHeldProp(model, tag) · SetOwnHeldPropPose(model, tag, pose) — CLIENT
Your held prop (your resource's `tag`, default `'held'`; `model` name or hash) on this player's game while held. `GetOwnHeldProp` → entity or `nil`. `DropOwnHeldProp` lets go locally at once (still call server `DropHeldProps`) → boolean. `SetOwnHeldPropPose(model, tag, pose)` sets another grip for a while: `pose = { bone?, offset = { x, y, z }, rot = { x, y, z } }`, or `nil` to restore the server's → boolean.

### AimDot(on) — CLIENT
`true` shows the aim dot while you aim something that is not a weapon; `false` releases your hold. Held per resource; removed when your resource stops. Weapons get it from `Config.AimDot`. Returns nothing.

## Server points: AddPoint / UpdatePoint / RemovePoint / GetPoints — SERVER

A prompt the server adds while it runs (a Talk on an NPC, a hand-in spot, a job board), for everyone or named players. Same prompt and E key as `AddAction`; pressing runs `onUse` on the server after WHIP checks distance, audience and requirements. In memory only (not saved): add again when your resource starts. Gone when your resource stops or with `ReleaseTag(tag)`. Point ids are numbers above 2^32 (`RUNTIME_BASE = 4294967296`).

### AddPoint(def) — SERVER

| Field | Type | Description |
|---|---|---|
| `at` | table | Exactly one: `{ coords, heading? }` (vector3/vector4/table; x,y within ±10000, z −500..3000); `{ netId, offset?, bone? }` (a networked entity that must exist now; shown while each game has it); `{ vehicle = vehicleId \| { plate } \| ..., offset?, bone? }` (a WHIP car while it's out; nothing while garaged); `{ ground = groundItemId, offset? }` (until picked up); `{ container = containerId, offset? }`. `offset` within 10 m on each axis; `bone` a bone name (`'SKEL_Head'`, `^[%w_]+$`, ≤ 40) only with netId/vehicle. Default lift above a car 1.1 m, a pile 0.5 m, a container 0.6 m (sits above their own prompts) |
| `label` | string? | ≤ 80 chars (sanitised) |
| `icon` | string? | Glyph name; `false` clears on update. `talk = true` with no icon gives `'talk'` |
| `options` | table? | Up to 6 per level `{ id, label?, icon?, require?, options? }`; ids `^[%w_-]+$` ≤ 40, unique per level. Nested `options` = a menu with Back: max 3 deep, 6 per level, 40 in all. Only a leaf can be pressed. None → one implicit option `'default'` |
| `require` | table? | `AddAction`'s words, checked again on the server. Unknown word refused. A `zone` must be a SAVED zone (EnsureZone / editor). `charId` and `ace` are decided on the server and never sent; a player who fails them is never sent the point/option at all |
| `audience` | audience \| `'everyone'`? | Who sees and may use it. Default `'everyone'`. Also takes `{ job = 'police', onDuty = true }` (followed as people clock on/off) |
| `reach` | number? | 0.5–25 (clamped, warned); not a number → 2.0 |
| `seeFrom` | number? | 1 to the grid ceiling (25 m by default, see Docs vs code); not a number → 5.0 |
| `focusMode` | `'aim'` \| `'near'` | Wrong value refused |
| `enabled` | boolean? | `false`: there but not offered (with `talk`: shows busyText) |
| `style` | string \| table? | As AddAction's; `false` clears |
| `holdMs` | number? | 0–10000; only leaves are held (Back stays a press); `false` clears. A hold is the player's game asking: `onUse` is still the check |
| `talk` | boolean? | A Talk on its NPC. While the NPC talks to someone else others see `Config.Conversations.speakingText`; while `enabled = false`, `busyText`. Pressing it then only repeats that |
| `quietFor` | audience? | With `talk`: who sees nothing (not "busy") while it's disabled (the run's own players) |
| `tag` | string? | Your run tag (`ReleaseTag`) |
| `onUse` | fn(source, use) | Required. `use = { pointId, option, path, useId, coords = {x,y,z}, netId }`. Return `false, 'why'` to refuse: the player is told why. Keep quick; start a thread for slow work. Runs inside `Actions.call` (what it saves through WHIP lands with this press) |

Returns: `pointId, false, warnings`, or `false, reason, warnings`. `warnings`: unknown fields (e.g. `onSelect` → "'onUse' (a point's press runs on the server: onUse(source, use))", `lable`) and clamped `reach`/`seeFrom`, also printed to the server console. A wrong VALUE is refused (`a point needs onUse, a function(source, use) — onSelect is AddAction's`, `at.netId names nothing in the world`, `at.vehicle names no car whip knows`, `at.ground names no ground pile`, `at.container names no container`, `at is one place, not coords and netId`, `a point has at most 6 options`, `a menu goes at most 3 deep ...`, `a menu has at most 40 options in all`, `zone "x" is not a saved zone: a point can only require one of those`, `focusMode is 'aim' (point at it) or 'near' (the closest wins)`).

Press flow (`whip_core:server:useRuntimePoint`, SecureEvent, `rateLimit = 500` ms, `whileDead = true`): point exists → talk busy check → `enabled` → `Audience.has` (`'That is not for you'`) → current position (`'That is not available'` if gone) → `IsPlayerNear` within `(reach or Config.InteractActiveRange) + 2.0` (`'Too far away'`) → path resolves to a leaf → `alive` from the nearest level that says (default: not while downed, `'Not while downed'`) → point `require` and every option's on the path (`Requirements.met`) → `onUse`. A throw in `onUse` prints `[whip_core:points] <owner>'s point <id> threw in onUse` and tells the player `'Something went wrong'`.

`use.path` is the ids from the top joined by `/` (`'tools/hack/firewall'`); `use.option` the leaf id (`'default'` without options). `use.useId` is what `StartConversation.fromUse` needs (valid 10 s).

```lua
local pointId = exports.whip_core:AddPoint({
    at = { netId = npcNetId, offset = vector3(0.0, 0.0, 0.3) }, label = 'Talk', talk = true,
    options = { { id = 'work', label = 'Got work?' }, { id = 'bye', label = 'Leave' } },
    audience = { people = { source } }, tag = 'run:42',
    onUse = function(source, use) if use.option == 'work' then StartJob(source) end end,
})
```

### UpdatePoint(pointId, patch) — SERVER
`patch` fields replace the point's (re-validated as a whole); `false` clears an optional field. The `tag` cannot change (`"a point's tag cannot change"`).
Returns: `true, false, warnings` or `false, reason, warnings` (`'no such point of yours'`).

### RemovePoint(pointId) — SERVER
Returns: `true` or `false, reason` (`'no such point of yours'`).

### GetPoints(filter?) — SERVER
`filter = { tag? }`. Your points (sorted by id) as `{ pointId, owner, tag, label, icon, coords = {x,y,z}|nil, heading, netId, vehicleId, groundId, containerId, enabled, options = { { id, label, icon, options } } }` (no `onUse`).

## Audiences

One shape for "these players" (`server/audience.lua`), used by points, blips, NPC hostility:
- `'everyone'` — every loaded player (not allowed for NPC `hostileTo`).
- `{ people = { 3, 7, { charId = 12 } } }` — server ids (count only while that id has a loaded character) or characters (whenever online; a charId follows them across relogs). At most 64 people.
- `{ job = 'police', onDuty = true }` — a job's people (on duty, or everyone employed). Only points and blips; followed live as people clock on/off, are hired/fired. Unknown job → `no job called x`.
- `{ except = { ... } }` — everyone but these; only NPC `hostileTo`, and only with a `range`.

## Conversations: StartConversation / UpdateConversation / EndConversation / GetConversation — SERVER

An NPC (or any networked entity) talks; the player picks one of up to 4 answers with the scroll wheel and E, in the dialog capsule beside the speaker. Not NUI focus. Opens only from a point's `onUse` (`fromUse = use.useId`, by this player, within 10 s, and on that point's NPC if the point rides one). The server holds what was offered and checks each answer before `onChoose`. Others nearby see it as `/me` bubbles (`Config.Conversations.watcherBubbles`).

Ends when: you end it; an `ends` answer is chosen; the player walks further than `Config.Conversations.range` (6 m), opens a screen, goes down, logs out or leaves; the speaker dies, goes or turns hostile; an answer with no `next` waits 15 s with no `UpdateConversation`; your run tag is released; your resource stops; another conversation replaces it.

### StartConversation(source, spec) — SERVER

| Field | Type | Description |
|---|---|---|
| `fromUse` | number | `use.useId` from your point's `onUse`, within 10 s |
| `npcId` / `netId` | number | Speaker: a living `SpawnNpc` NPC, or any networked entity |
| `speaker` | string? | Name shown above the line (≤ 40) |
| `line` | string | What they say, ≤ 440 characters (colour codes removed, /me cleaning) |
| `options` | table | 1–4 answers `{ id, label, ends?, input?, cost? }`. id `^[%w_-]+$` ≤ 40; label ≤ 60 |
| `options[].input` | `{ min?, max?, prefix? }` | A typed whole amount (digits; E gives it; Backspace on empty steps back). `min` default 0, `max` default 999999999, `prefix` ≤ 8 chars. `onChoose` gets `amount`. Out of range: `'Type an amount from $min to $max'` |
| `options[].cost` | `{ amount, currency?, method?, reason? }` | Charged like `ChargePlayer` before `onChoose`. `amount` whole ≥ 1; `currency` default `'cash'`, else an item key (paid from pockets, forces method cash); `method` `'auto'` (default) / `'cash'` / `'bank'`; `reason` ≤ 120. Unpaid: refused with reason, answers stay. Not with `input` |
| `next` | table? | `{ [answerId] = { line, options } }` replies sent ahead so the player sees them instantly. Without one the capsule dims until `UpdateConversation` (15 s, then it ends `'no answer'`). A costed or typed answer's reply waits for payment/server |
| `layout` | `'grid'` \| `'stack'` | 2×2 grid (default) or a column |
| `onChoose` | fn(source, answerId, convId, amount)? | A checked (and paid) answer |
| `canChoose` | fn(source, answerId, convId)? | Return `false, 'why'` to refuse before it's taken or paid |
| `onEnd` | fn(source, why)? | `'ended'`, `'chose'`, `'left'`, `'blocked'`, `'downed'`, `'logout'`, `'killed'`, `'gone'`, `'hostile'`, `'no answer'`, `'replaced'`, `'released'`, `'stopped'` |
| `tag` | string? | Run tag |

Returns: `convId`, or `false, reason` (`'no such player'`, `'they are down'`, `"not from an interaction: open it from a point's onUse, with fromUse = use.useId"`, `'no such NPC'`, `'that NPC is dead'`, `'a conversation needs its speaker: npcId or netId'`, `'not the one they spoke to'`, `'the speaker is not there'`, `'they are too far from the speaker'`, `'at most 4 answers'`, `'next.x: there is no answer "x"'`, ...). One per player: a new one replaces theirs (`onEnd 'replaced'`). Answer submissions are rate-limited (`rateLimit = 250, burst = 4`); `'Wait for an answer'` while one is pending/paying. Director-only extras on a line: `team = { max, slots }` and `haggle = { ... }` (internal).

```lua
onUse = function(source, use)
  exports.whip_core:StartConversation(source, {
    fromUse = use.useId, npcId = npcId, speaker = 'Fence', line = 'Got the goods?',
    options = { { id = 'yes', label = 'Here.' }, { id = 'bye', label = 'Leave', ends = true } },
    next = { yes = { line = 'Let me see.', options = { { id = 'deal', label = 'Deal?' } } } },
    onChoose = function(src, answer, convId)
      if answer == 'deal' then PayFor(src); exports.whip_core:EndConversation(convId) end
    end,
  })
end
```

### UpdateConversation(convId, patch) — SERVER
`patch`: `{ line, options, next, speaker, canChoose }` (`canChoose = false` removes it). Returns `true` or `false, reason` (`'no such conversation of yours'`).

### EndConversation(convId) — SERVER
`onEnd` hears `'ended'`. Returns `true` or `false, reason`.

### GetConversation(convId) — SERVER
Copy: `{ convId, owner, tag, source, npcId, netId, speaker, line, options = { { id, label, ends } }, waiting }` or `nil`.

## Item right-click options (contextOptions, AddItemOption, RemoveItemOption)

Right-click (context) actions on inventory items are defined on the item, not with `AddAction` (`server/item_options.lua`).

- Item definition `contextOptions = { { action, label, order?, when?, whyNot?, require?, anywhere? } }`: `action` (≤ 32 chars, registered with `RegisterContextAction`), `label` (≤ 40), `order` (lowest first; unordered after ordered, as listed), `when` (tests on the item's METADATA: `field = value`, `field = { 'a', 'b' }` (≤ 50 entries), `field = { above/below/atLeast/atMost = n, empty = bool, default = v }`; all must pass), `whyNot` (≤ 80, said when `when` fails on a double-click), `require` (the PLAYER: AddAction's words; a zone must be saved), `anywhere = true` (also offered in a boot/glovebox/stash/bag/panel — handler gets that store's address; default pockets only). `icon` is accepted and dropped. Two options with the same action are refused. Shown at the top under Use; Give, Place, Split, Destroy below.
- `groundOptions = { { action, label, icon? } }` (≤ 3): on a ground pile's prompt after Pick up; picks the item up then runs that option on the slot it landed in. Handler's 5th arg `how = { from = 'ground' }`.

### RegisterContextAction(actionKey, handler) — SERVER
`handler(source, player, slotData, addr, how)`. Prefix the key with your resource name (`'my_bows:equip'`): one server-wide list, first come first served, ≤ 32 chars; WHIP's own panel action names are refused. Returns `true` or `false, err`.

### AddItemOption(itemKey, option) — SERVER
Adds a right-click option to any item (yours or another resource's, e.g. "Check for prints" on whip_gunny guns). `option = { action, label, order?, when?, require? }` (same validation as contextOptions). Gone when your resource stops. Refused: invalid option, an action the item already has, the same item+action another resource added. Returns `true` or `false, err`.

### RemoveItemOption(itemKey, action) — SERVER
Removes one you added. Returns `true` or `false, err`.

## Porting from ox_target / qb-target

| ox_target / qb-target | WHIP |
|---|---|
| `addBoxZone` / `addSphereZone` / `AddCircleZone` at a spot | `AddAction({ at = { coords = vec3 }, ... })` (no box size: it is a point prompt; use `reach`) |
| `addLocalEntity` / `AddTargetEntity` (local) | `at = { entity = handle }`; networked: `at = { netId = n }` |
| `addModel` / `AddTargetModel` | `at = { model = 'prop' \| { ... } }` |
| `addGlobalVehicle` / `addGlobalPed` / `addGlobalObject` | `at = { aimBox = 'vehicle' \| 'ped' \| 'object' }` (or `vehiclePart` for doors/hood/trunk) |
| `distance` | `reach` (auto-mapped with a warning) |
| `groups` / `job` / `gang` | `require = { job = ... }` (no gangs: a gang is a job; grade → `jobPermission`) |
| `items` / `item` | `require = { item = ... }` (ALL required; for "any one" check in `canInteract`) |
| `canInteract(entity, distance, coords, name, bone)` | `canInteract(ctx)` (`ctx.entity`, `ctx.coords`, ...) |
| `onSelect(data)` / `event` / `serverEvent` / `action` | `onSelect(ctx)` and trigger your event inside it |
| `name` | `id` |
| `icon = 'fa-solid fa-x'` | a glyph name from the list (Font Awesome is not supported; other text is drawn literally) |
| radial menu `AddOption` | `at = { radial = true }` |
| server-trusted interaction | `AddPoint` (onUse runs on the server after checks) |

## Gotchas

1. `onSelect` runs in a new thread; the label/icon/canInteract functions do not and must never Wait or call a server callback.
2. `require` is strict: one unknown word (`jobs`, `groups`, `grade`, `items`) refuses the whole action — check the third return and F8. Everything else is only warned.
3. The second return value on success is `false`, not `nil` (`local id, why, warnings = AddAction(...)`): test `if not id`, never `if why`.
4. Auto ids hash the label only when it is a string; two actions with function labels at the same place collide — give an explicit `id`.
5. `at.entity` actions are removed (not suspended) ~3 s after the entity disappears, including a networked entity streaming out; use `at.netId` for anything networked.
6. `at.model` takes model names only; a hash is refused.
7. World prompts are offered on foot only unless `require.vehicle = 'in'`; the wheel ignores that default. `vehiclePart` actions refuse `alive = false`/`vehicle = 'in'`.
8. Menus exist only on world prompts; `options` with nested `options` on the wheel or a car part is dropped with a warning.
9. `require.zone` on `AddPoint` (and item options) must name a SAVED zone (EnsureZone/editor) because the server re-checks it with trusted zones; client-only zones are refused.
10. `AddPoint` uses `onUse(source, use)`, not `onSelect`; options inside a point have no callbacks of their own — branch on `use.option`/`use.path`.
11. A point on `at.netId` is refused if the entity does not exist on the server when added.
12. A conversation can only open from a fresh point press (`fromUse = use.useId`, ≤ 10 s); you cannot start one from a command or an event.
13. `HoldProps`: at most one new set per player per second, max 2 props, and any WHIP set (emote, progress bar, give) replaces yours — listen to `whip_core:heldProps:lost`.
14. `canInteract` costs roughly 95 calls/s per option near a car; prefer `require`, or add/remove the action as state changes.
15. Functions cross the export boundary as references: calling works, but `type(fn) == 'function'` is false on the other side.
16. `aimBox` casts a ray every frame; register it only while needed.
17. `seeFrom` beyond the grid ceiling is clamped with a console line; raise `Config.InteractVisibleRange` to allow larger.
18. The server re-checks a point press against `reach + 2 m`; an `AddAction`'s `reach` is only client-side — your own server handler must enforce distance itself.

## Docs vs code

- `seeFrom` clamp: docs say clamped to `Config.InteractVisibleRange` (5 m). Code clamps to the spatial grid search radius `max(1, ceil(InteractVisibleRange / 25)) * 25` = 25 m by default (`client/interact.lua:241-251`, `server/runtime_points.lua:104`), and the spec allows 1–1000 (`shared/interact_spec.lua:40`).
- Glyph list: docs omit `house_door`, `theme`, `dollar`, `fail`, `success`, `info`, `warning`, `object`, `ped`, `camera` which exist in `html/js/glyphs.js` (types stub also lists most of them, `types/client.lua:745`).
- `vehiclePart` keys: docs/types list hood, trunk, four doors, bike, bicycle, boat; code also accepts `door_*_in` (inside of an open door) and `fuel` (`client/vehicle_prompts.lua:325-337`).
- Prompt theme default: types say `'classic'` is default (`types/client.lua:843`); `config.lua` ships `Config.Interact3D.theme = 'keycap'` (docs agree with config).
- Conversation line length: types say 220 characters (`types/server.lua:3792`); code `LINE_MAX = 440` (`server/conversations.lua:63`), as the docs say.
- `canInteract` may return a second value (reason) that appears in `GetAction` `why` (`client/actions.lua:369-376`); not documented.
- `ctx.beginInput` also accepts `icon` (`client/interact.lua:665`); not documented.
- Audiences for `AddPoint` (and blips) also accept `{ job, onDuty }` (`server/runtime_points.lua:313`, `server/audience.lua:9`); docs only show `people`.
