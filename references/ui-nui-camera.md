# UI library, screens, controller, camera, theming, NUI pages and DUI

Covers WHIP's player-facing UI exports (toasts, bars, dialogs, skill checks, hint text, objectives, composer), screen and input ownership, controller support, the camera system, theming/skins, building a resource NUI page that fits WHIP, browser-capability detection and test tools, and DUI screens. Built from doc anchors `#ui-library`, `#guide-controller`, `#guide-camera`, `#client-camera`, `#guide-theming`, `#guide-nui-caps`, `#guide-dui`, verified against `whip_core/client/ui.lua`, `focus.lua`, `controls.lua`, `controller.lua`, `keyboard.lua`, `pad.lua`, `camera.lua`, `cam_shots.lua`, `freecam.lua`, `dui_page.lua`, `nui_caps.lua`, `hands.lua`, `clean_screen.lua`, `curtain.lua`, `inventory.lua` (screen state, client hooks), `composer.lua`, `placing.lua`, `streaming.lua`, `ped_hold.lua`, `hud.lua`, `server/skillcheck.lua`, `timed_action.lua`, `ask.lua`, `player_text.lua`, `held_props.lua`, `hands.lua`, `themes.lua`, `camera_sequences.lua`, `shared/skillcheck.lua`, `cam_math.lua`, `cam_sequence.lua`, `body_state.lua`, `lib/satellite.lua`, `docs/nui-architecture.md`, `docs/nui-theming.md`, `html/js/ui.js`, `theme.js`, `caps.js`, `page-tools.js`, `html/css/base.css`, `fonts.css`, `types/*.lua`.

## Contents
- Calling conventions and the shared rules of blocking components
- Messages and loading (Notify, NotifyPlayer, Load*)
- Progress bars (client and server)
- Dialogs: Input, Alert, Confirm; server-asked questions and ask channels
- Skill checks (client, server, custom games)
- Placing a prop (PlaceObject)
- On-screen text: ShowText / HideText / ShowPlayerText / objectives / interrupted
- Menus (there is no menu export)
- The composer (one line of text)
- Screen ownership and input: SetScreenOpen, IsAnyScreenOpen, IsGameInputFree, SetScreenArea, clean screen
- BlockControls, HoldPlayerPed, PermitNativeWeapon
- Hands: FreeHands, BlockHands, held props, body state
- Client hooks (RegisterClientHook)
- Controller support (pad actions, padScreen, OpenKeyboard, mode keys)
- Camera system (PlayCamera, paths, sequences, orbit, Creator, driving camera)
- Theming and skins
- Building your own NUI page that fits WHIP
- Browser capabilities (caps.js, GetNuiCaps) and test tools
- DUI screens in the world
- Client events emitted by these systems
- Config keys
- Gotchas
- Docs vs code

---

## Calling conventions and the shared rules of blocking components

- All exports are on `exports.whip_core`. From a satellite (fxmanifest `shared_script '@whip_core/lib/satellite.lua'`), call WAITING exports through `Whip.core:Name(...)` (or `Whip.call('Name', ...)`): if whip_core restarts mid-wait they return `false, 'whip_core stopped'`; a raw `exports.whip_core:Progress` would wait forever. Do this for Progress, SkillCheck, Input/Confirm/Alert, PlaceObject, OpenKeyboard, LoadModel, FreeHands, ChargePlayer, Callback, DB reads.
- The caller resource is captured at the export boundary (`GetInvokingResource()` / `Registry.caller()`), so ownership (who may cancel/hide/stop) is per resource.
- **Blocking components** (client `Progress`, `Input`, `Confirm`, `Alert`, `SkillCheck`, `PlaceObject`) wait: call from a command handler or `CreateThread`, never from a prompt/vehicle-part callback that must not wait (freezes every prompt).
  - One at a time (one slot, `client/ui.lua` `_activeBlockingId`). A second call answers `false, 'busy'` without showing anything.
  - Failure always returns a SECOND value (`false, why`), never `nil` (an export's return list stops at its first nil).
  - Reason words: `'busy'`, `'cancelled'`, `'timeout'`, `'failed'` (SkillCheck), `'refused'` (Progress notWhile).
  - They close the inventory first. They are `'busy'` while ANOTHER resource has a `SetScreenOpen` screen (your own screen does not block your dialogs). Dialogs (not bars) are also `'busy'` over focus-holding screens: composer, radial wheel, `/whip` panel, OpenKeyboard, character select, appearance creator, Director/Systems editors (`FocusScreenUp`, `client/inventory.lua:824`).
  - A dialog releases NUI focus when it closes: if your own screen is under it, call `SetNuiFocus(true, true)` again when it returns.
  - Owned: when your resource stops, whip_core cancels your bar/dialog and hides your text. A logout (`whip_core:client:playerLogout`) cancels whatever is up. A death (`whip_core:player:died`) cancels a dialog (a bar stops itself via cancelOnDeath).
  - Positional or one table: `Confirm('Sell?', 'Sure?')` == `Confirm({ title = 'Sell?', message = 'Sure?' })`.
  - While one is up, `IsGameInputFree()` is `false`.
- Backstop timeouts (`client/ui.lua`): dialogs (Input/Alert/Confirm) 300000 ms (5 min) -> `'timeout'`; ring skill check 60000 ms; another resource's game 125000 ms; a bar `duration + 10000` ms.

---

## Messages and loading

### Notify(text, type?, duration?) — CLIENT
- `text` string; `type` `'success'|'error'|'info'|'warning'` (default `'info'`); `duration` ms (default `3000`). Doesn't block; several queue.
- Surface is decided on arrival: the player capsule (bottom left) when free and on screen, else the top-right stack (a UI open, player dead). Bursts queue through the capsule one at a time.
- A screen that shows notices itself takes them first: the /whip panel's header, the pockets' header (`js/inv-notice.js`), a shop's talk row (`js/shop-talk.js`). The top-right stack (`#ui-notifications`, `renderToStack` in `html/js/ui.js`, styles `css/ui.css` §1) is only the last fallback: max 5, newest at the bottom, sits under objective cards (`--obj-n`). During a load notices wait; a queued one older than 8 s is dropped. Repeats are not merged.
- Top middle is not free: `UI.ShowText` at the top puts its capsule there (`.ui-drawtext-top .dt-cap`, top 36px at the 2560x1440 design). A top-middle notice must sit under it.
- No return value.
```lua
exports.whip_core:Notify('Inventory full', 'error', 5000)
```

### NotifyPlayer(source, text, kind?, duration?) — SERVER
- `source` a player or `-1` for everyone. `kind` `'info'` (default) | `'success'` | `'warning'` | `'error'` (anything else becomes info). `text` sanitized, cut to 300 chars. `duration` clamped 500–30000 ms (`server/player.lua:1009`).
- Returns `true`, or `false, 'They are not on the server'` / `false, 'Nothing to say: the text is empty'`.
- Same global is used by `SecureEvent` handlers: a handler's `return false, 'why'` is shown through it.

### LoadModel(model, timeoutMs?) · LoadAnimDict(dict, timeoutMs?) · LoadTextureDict(dict, timeoutMs?) · LoadAnimSet(set, timeoutMs?) · LoadPtfxAsset(asset, timeoutMs?) — CLIENT, WAITS
- Default timeout 5000 ms, polled every 10 ms (`client/streaming.lua`).
- `LoadModel` takes a name or hash; returns the hash, or `nil` (immediately when `IsModelInCdimage` is false, or on timeout). Release with `SetModelAsNoLongerNeeded`.
- Others return `boolean`. `LoadAnimSet` = movement clip set (walk style), `LoadPtfxAsset` = named particle asset, `LoadTextureDict` = streamed txd for DrawSprite.
- From a satellite, `Whip.core:LoadModel(...)` returns `false` if whip_core restarts.
```lua
local hash = Whip.core:LoadModel('prop_beer_bottle')
if not hash then return end
local obj = CreateObject(hash, x, y, z, true, true, false)
SetModelAsNoLongerNeeded(hash)
```

---

## Progress bars

### Progress(label, duration?, opts?) · Progress(opts) — CLIENT, WAITS
Shows the bar (drawn in the hint capsule, "drawtext band") and waits. No NUI focus is taken; the game keeps input.

| Option | Type | Default / meaning |
|---|---|---|
| `label` | string | Text above the bar |
| `duration` | number | ms, default `3000`; must be a positive finite number or returns `false, 'duration must be a positive number of milliseconds'` |
| `canCancel` | boolean | default `false`. X (control 73) cancels; read as a game control (not while LB is held: LB+A is talk) |
| `anim` | table | `{ dict, clip, flag }`, `flag` default `49` (upper body, looping); dict loaded with a 2 s limit. Or `{ scenario = 'WORLD_HUMAN_VEHICLE_MECHANIC' }` (TaskStartScenarioInPlace; stopped with ClearPedTasks) |
| `prop` | table | `{ model, bone, offset, rot }`; `bone` default `18905` (SKEL_L_Hand); `offset`/`rot` `{x,y,z}` or `{1,2,3}`. Made by the SERVER (`whip_core:server:barProp`), see gotchas |
| `disable` | table | `{ move, combat, car }`. Default: walking and fighting held off, driving allowed. `move = false` frees movement; `move = 'walk'` caps to a walk (jump/duck/cover held off, sprint left readable) and running/sprinting after the first 0.5 s interrupts ('You started running'). `combat = false` frees combat. `car = true` holds off the `driving` group |
| `cancelOnDeath` | boolean | default `true`: death or ragdoll (incl. a long fall) interrupts it (red capsule with why). `false`: a bar for the downed |
| `cancelOnExit` | boolean | default `false`. Cancels on the exit press (control 75) or leaving the vehicle it began in; not in a vehicle at start -> ends at once |
| `notWhile` | string[] | any of `'swimming'` (also covers underwater), `'underwater'`, `'falling'`. Already in one: returns `false, 'refused', words` (never starts). Becoming one: interrupted. Bad entry -> `false, "notWhile: no state 'x' (swimming, underwater, falling)"` |
| `icon` | string | glyph name for the capsule disc (`html/js/glyphs.js`: `'eat'`, `'fuel'`, `'place'`...). Default hourglass |
| `item` | string \| table | item key (`'jerry_can'`, ≤64 chars) or slot data `{ item, metadata, amount? }`: the disc shows the item's picture instead of filling |

- Returns `true`, or `false, why, words`: `why` is `'cancelled'`, `'busy'`, `'timeout'` or `'refused'`; `words` is what the capsule said (`'You went down'`, `'You were knocked down'`, `'You got out of the vehicle'`, `'You started running'`, `'You cannot do that while swimming'`, or your InterruptProgress text). Also `false, 'opts must be a table'` and the notWhile/duration refusals.
- Ends any running emote first (its props go with it). A ShowText shown during the bar appears when the bar ends; the text from before the bar comes back after.
- A client bar is the player's word. If finishing hands something out, use the server `Progress(source, opts)` or a declared timed use (`RegisterUseHandler` with a table, see items reference).
```lua
local ok, why = Whip.core:Progress({
    label = 'Drinking...', duration = 5000, canCancel = true,
    anim = { dict = 'mp_player_intdrink', clip = 'loop_bottle' },
    prop = { model = 'prop_amb_beer_bottle' },
    disable = { move = false },
})
```

### IsProgressActive() · CancelProgress() — CLIENT
- `IsProgressActive()` -> boolean: any bar running (anyone's).
- `CancelProgress()` -> boolean: cancels the bar YOUR resource started (its caller gets `false, 'cancelled'`); `false` when none or another's.

### InterruptProgress(why) · ShowInterrupted(why, what?) — CLIENT
- For a bar or mode stopped by something the player didn't choose: the capsule turns red (2600 ms, `INTERRUPT_MS`) with `why` as title.
- `InterruptProgress(why)` ends YOUR bar; its caller gets `false, 'cancelled', why`. Returns `false` if no bar or another's.
- `ShowInterrupted(why, what?)` for your own mode (placing, aiming): call it, then `HideText` (which won't cut it short). `what` = what it stopped (`'Placing the sign'`). Returns `false` when `why` is empty or a bar holds the band.
- For a long fall, use `GetBodyState`'s words.

### Progress(source, opts) — SERVER, WAITS
The bar on the player's screen with the server keeping the clock (`server/timed_action.lua`). Takes the client options as ONE table; `duration` REQUIRED. Plus:

| Option | Meaning |
|---|---|
| `near` | `{ coords = vector3, range = 3.0 }` or `{ vehicle = vehicleId, range = 5.0 }` (vehicle ref resolved by `Vehicles.idFromRef`). Checked at start and at finish -> `'too far'`. The SecureEvent spelling also works: `at = vector3` is coords; `at = 'vehicle'` needs `vehicle`. `range` must be positive |
| `tag` | your run tag (non-empty string). `ReleaseTag(tag)` ends it (`'cancelled'`, removed from screen); a tag already released -> `'run ended'` |
| `notWhile` | checked by the player's game; never started -> `'refused'` |
| `prop` | server makes and removes the prop (`HeldProps.give(source, {prop}, 'bar')`), and vouches the model so client bars may use it later |

- Anti-cheat: one-shot token; an answer before 90% of `duration` (`SLACK = 0.9`) is `'too fast'` and logged (`RecordEventRejection`); the server waits `duration + 15000` ms (`GRACE_MS`) then `'timeout'`. Answer must come from the same character session. A "done" while dead is `'dead'` unless `cancelOnDeath = false`. `cancelOnExit = true` requires being in a vehicle (`'not in a vehicle'`) and the same vehicle at finish (`'left the vehicle'`). One server bar per player (`'busy'`).
- Returns `true`, or `false, why`: `'cancelled'`, `'refused'`, `'busy'`, `'timeout'`, `'too fast'`, `'too far'`, `'dead'`, `'not in a vehicle'`, `'left the vehicle'`, `'player left'` (drop/logout), `'run ended'`, `'Player not loaded'`, or a refusal sentence (`'Progress needs an options table'`, bad duration, bad `near`, `'opts.tag is the run tag, a string'`).
- Client answer reasons accepted by the server are only `busy|cancelled|refused|timeout` (a client cannot claim `'dead'`).
- Call it from a `SecureEvent` or a use handler, NOT a `SecureCallback` (the client Callback gives up after 10 s).
```lua
local done = Whip.core:Progress(source, {
    label = 'Picking the lock...', duration = 8000,
    anim = { dict = 'mini@safe_cracking', clip = 'idle_base' },
    near = { coords = doorCoords, range = 3.0 },
})
if not done then return end
```
- Internal events: `whip_core:client:serverProgress (token, opts, owner)`, `whip_core:server:progressResult (token, completed, why)`, `whip_core:client:serverProgressCancel (token)` (shows "Called off").

---

## Dialogs

### Input(title, fields) · Input({ title, fields }) — CLIENT, WAITS
Centred form with mouse focus. Title default `'Input'`.

Field `{ label, type, ... }` (label default `'Field N'`):

| `type` | Returns | Keys |
|---|---|---|
| `text` (default) | string | `placeholder`, `default`, `required` |
| `number` | number | `placeholder`, `default`, `min`, `max`, `required`; empty optional -> `0` (`parseFloat(...) || 0`) |
| `select` | string (the option `value`) | `options = { { value = 'a', label = 'A' }, ... }`, `default` (matched by value). Native `<select>` |
| `checkbox` | boolean | `placeholder` (the text beside the box), `default` |
| `textarea` | string | `placeholder`, `default`, `rows` (1–12, default 3), `required` |
| `password`, `email`, `tel`, `url`, `date`, `time`, `color`, `range` | string | HTML input types also accepted (`html/js/ui.js:26`); `min`/`max` become attributes |

- Submit validates: `required` + empty -> "Required"; number not finite -> "Must be a number"; below `min` "At least N"; above `max` "At most N". The dialog stays open showing the problem under the field. Checkboxes are never required.
- Returns an ARRAY `{ [1] = v1, [2] = v2, ... }`, or `false, why` (`'busy'|'cancelled'|'timeout'`). Cancel button or Escape -> `'cancelled'`.
- Pad: the dialog reads the pad itself (a ring steps fields; text fields open the on-screen keyboard).
```lua
local r = Whip.core:Input('Create Report', {
    { label = 'Title', type = 'text', required = true },
    { label = 'Urgent', type = 'checkbox', placeholder = 'Mark as urgent' },
})
if r then TriggerServerEvent('reports:create', r[1], r[2]) end
```

### Alert(title, message, btnText?) · Alert({ title, message, button }) — CLIENT, WAITS
- One button, default `'OK'`; title default `'Alert'`. Returns `true` when pressed, or `false, why` (`'cancelled'` = Escape, `'busy'`, `'timeout'`).

### Confirm(title, message, confirmText?, cancelText?) · Confirm({ title, message, yes, no }) — CLIENT, WAITS
- Defaults `'Confirm'` / `'Cancel'`; title default `'Confirm'`. Returns `true`, or `false, why`: `'cancelled'` (said no OR Escape), `'busy'`, `'timeout'`.
```lua
local sell = Whip.core:Confirm({ title = 'Sell car', message = 'Sell it for $4,000?', yes = 'Sell', no = 'Keep it' })
```

### Server-asked questions (internal `Ask.run`) and ask channels
- whip_core has a server-side Ask (`server/ask.lua`) used by the Systems Creator's Ask cards and the Director; `Ask.run` is NOT exported. It sends `whip_core:client:serverAsk (token, kind, spec)`; kinds `'confirm'` (`title` ≤80, `message` ≤400, `yes`/`no` ≤24, defaults `'Question'`, `'Yes'`, `'No'`) and `'form'` (≤6 fields, types text/number/checkbox/select only, select ≤20 options, text `maxLen` default 100, max 500). Timeout default 30 s, clamped 5–120 s. The answer is validated server-side against the spec (`'bad answer'`).

### RegisterAskChannel(name, deliver) — SERVER
- Offer whip_core's yes/no questions asked with `via = '<name>'` (e.g. the Director's job invite) to your own screen first; whip_phone registers `'phone'`. Confirms only.
- `name`: letters, digits, `_`, `-`, up to 32 chars; not another running resource's (registry rule).
- `deliver(source, token, kind, payload)` -> return `true` when you showed it; must not wait. `payload`: `{ title, message, yes, no }`. Not `true` (or error, or channel resource dead) -> asked on screen as usual.
- If whip_core gives up (timeout, run end, player left) the local client event `whip_core:ask:cancelled` (`{ token }`) fires on the player's game: take your screen down. When your resource stops, its still-open questions are re-asked on screen with the same token.
- Returns `true`, or `false, why` (`'name is a short word: letters, digits, _ or -'`, `'deliver is the function that shows a question'`, or a taken-name refusal).

### AnswerAsk(source, token, yes) — SERVER
- Answer a question your channel showed. `yes` true = Accept, false = Decline. Only the resource that delivered it; same player; same character.
- Returns `true`, or `false, why`: `'That question is gone'`, `'That question was not asked through you'`, `'That question was for another character'`. A dead player's answer resolves the question as `'dead'` (still returns `true`).
```lua
exports.whip_core:RegisterAskChannel('phone', function(source, token, kind, payload)
    if not playerHasPhone(source) then return false end
    TriggerClientEvent('my_phone:invite', source, token, payload)
    return true
end)
exports.whip_core:AnswerAsk(source, token, true)
```

---

## Skill checks

### SkillCheck(difficulty?) · SkillCheck({ difficulty }) · SkillCheck({ difficulty, game }) · SkillCheck({ level }) — CLIENT, WAITS
The ring: a lit part of a ring; the player pushes the centre dot onto it and holds it there until it fills (`Config.SkillCheckHoldMs`, 196), part after narrower part. Touching the ring outside the lit part, or the clock running out, fails. Mouse (`Config.SkillCheckMouseSpeed`, 1.0; GTA sensitivity counts too) or a pad's right stick, never keyboard. No NUI focus; every control is held off (`skillCheck` block, `all = true`) and the hands are read through the game.

| Name | pieces | parts | widest -> narrowest | msPerPart | clock |
|---|---|---|---|---|---|
| `easy` | 4 | 6 | 3 -> 1 (3/4 to 1/4) | 650 | 3.9 s |
| `medium` (default) | 8 | 12 | 4 -> 1 (1/2 to 1/8) | 600 | 7.2 s |
| `hard` | 16 | 16 | 4 -> 1 (1/4 to 1/16) | 575 | 9.2 s |

- Server owners add names in `Config.SkillCheckDifficulty` (`{ pieces, parts, widest, narrowest, msPerPart }`; msPerPart default 600 if omitted).
- `{ level = { pieces, parts, widest, narrowest, msPerPart, holdMs?, mouseSpeed? } }`: the ring with your own numbers (`shared/skillcheck.lua`). Validation: pieces/parts whole ≥1; widths >0 and ≤ pieces, narrowest ≤ widest; msPerPart >0.
- A non-empty table without `difficulty` (old `{ checks = ... }` form) is refused: `"SkillCheck takes a difficulty now ('easy', 'medium' or 'hard'), not a list of checks"`.
- `game = 'ring'` means the ring. Another game: its client `canStart` is asked first.
- Returns `true`, or `false, why`: `'failed'`, `'cancelled'`, `'busy'`, `'timeout'`; with a game `'not started'` (canStart said no; the player was told; NOT a fail) or `'unavailable'` (no running resource has it); or a sentence for an unknown difficulty (`"no skill check difficulty called 'x' (...)"`).
- Client check = the player's word. Gate rewards behind the server SkillCheck.

### GetSkillCheckSettings() — BOTH
- Copy of the live ring settings: `{ holdMs, mouseSpeed, difficulties = { easy = { pieces, parts, widest, narrowest, msPerPart }, ... } }`.

### SkillCheck(source, difficulty?, opts?) — SERVER, WAITS
| opts | Meaning |
|---|---|
| `timeoutMs` | default: ring clock + 2000 ms (capped 60000); a game: its level's `timeoutMs`. A given value is clamped 1000–60000 (game 1000–120000) |
| `minMs` | fastest believable answer. Default `max(300, parts × holdMs)` for the ring; a game's level `minMs`. 0 allowed (no floor). Must be < timeout else refused: `'minMs (x) must be shorter than timeoutMs (y) — pass a longer opts.timeoutMs'` |
| `tag` | run tag: `ReleaseTag(tag)` -> `'cancelled'`; released -> `'run ended'` |
| `game` | another resource's game id; `difficulty` is then one of ITS levels (unknown level -> sentence listing them); unknown game -> `"no skill check game called 'x' (is the resource that adds it running?)"` |
| `quiet` | don't NotifyPlayer why a game couldn't start |

- Returns `true`, or `false, why`: `'failed'`, `'busy'`, `'cancelled'`, `'timeout'`, `'too fast'`, `'dead'` (asked of a downed player, or passed while dead), `'run ended'`, `'Player not loaded'` (also on logout/drop), `'not started'`, `'unavailable'`, or a sentence naming a bad argument.
- A failure from the client is accepted at any time (an instant `'busy'` is never `'too fast'`). Client why words accepted: `failed|busy|cancelled|timeout|unavailable`.
- Run medium/hard from a SecureEvent: they outlast a SecureCallback's 10 s.
- A patient cheater still passes by waiting the honest time; don't gate something that must be uncheatable on a minigame.
```lua
local passed, why = Whip.core:SkillCheck(source, 'medium')
if not passed then return false, why == 'busy' and 'Finish what you are doing first' or 'You slipped' end
local ok, why2 = Whip.core:SkillCheck(source, 'hard', { game = 'phone.reroute' })
if why2 == 'not started' then return end   -- told why, nothing happened
```
- `Config.LockpickGame` (`'ring'` default) picks the game whip's own lockpicks play (car/door lockpick medium, ignition hack hard; floor 1000 ms); a missing game falls back to the ring with one console line.

### Whip.skillCheckGame(id, def) · Whip.removeSkillCheckGame(id) · GetSkillCheckGames() — BOTH (helper) / SERVER (list)
Your own game for client and server `SkillCheck` and the Director's Skill Check card. whip_core keeps the token, timings, answer. Call `Whip.skillCheckGame` in a file both sides load (shared_script), or once per side with the same id.

| Field | Side | Rule |
|---|---|---|
| id | both | `'<yours>.<name>'`, lowercase `^[a-z][a-z0-9_]*%.[a-z][a-z0-9_]*$`, ≤48 chars (server) |
| `label` | server | required, ≤40 chars (Director name) |
| `desc` | server | optional, ≤200 chars |
| `levels` | server | `{ easy = { minMs, timeoutMs }, ... }`; level names lowercase words ≤24 chars; 1–8 levels; `minMs ≥ 0`; `timeoutMs` 1000–120000; `minMs < timeoutMs` |
| `canStart(source)` | server | optional; return `true` or `false, words` (≤120 chars told to player; check answers `'not started'`). May wait. Errors -> "That can't be done right now" |
| `canStart()` | client | optional, same for the client SkillCheck; no source; must not wait |
| `run(difficulty, token)` | client | REQUIRED on client; runs in its own thread, may wait; return `passed, why` (`why` in `'failed'|'cancelled'|'timeout'|'busy'`; else counted as failed). Holds WHIP's blocking slot. An error = failed |
| `cancel(token)` | client | optional: called off; make `run` return |

- Re-sent automatically on whip_core restart (`Whip.register`); removed when your resource stops (a running check -> `'cancelled'`) or by `Whip.removeSkillCheckGame(id)`.
- `GetSkillCheckGames()` (server) -> `{ { id, label, desc, levels = { names... }, needs, owner }, ... }` sorted by label (never the ring). `needs` = has a server canStart.
- whip_phone adds `phone.bruteforce`, `phone.coderecall`, `phone.fragmentmatch`, `phone.override`, `phone.reroute`, `phone.safecrack`, `phone.stabilise`.
```lua
Whip.skillCheckGame('mygame.wires', {
    label = 'Cut the Wires',
    levels = { easy = { minMs = 2000, timeoutMs = 30000 } },
    canStart = function(source) return HasCutters(source) or false, 'You need wire cutters' end,
    run = function(difficulty) return PlayWires(difficulty) end,
})
```
- Internal exports used by the helper: `__RegisterSkillCheckGame`, `__RemoveSkillCheckGame`, `__SkillCheckGameDone` (don't call directly).

---

## Placing a prop

### PlaceObject(model, opts?) — CLIENT, WAITS
The item placer for your prop: a see-through ghost follows where the player looks and sits on surfaces. Wheel rotates 15° a notch (2° with Ctrl) / triggers on a pad; arrow keys (D-pad) raise/lower; Ctrl = fine; E (Interact key, A on pad) places; C (B) cancels. Runs the `beforePlaceMode` client hook first. Nothing is created: you spawn the prop.

| opts | Meaning |
|---|---|
| `label` | what the hint calls it (≤40 chars), default `'it'` |
| `vehicles` | `true`: may go on a car (roof, bed); otherwise cars are refused |
| `reach` | metres from the camera, clamped 1–10; default `Config.PlaceItemRange` (10.5 -> 10) |

- Returns `{ coords, rot }` (`rot = vector3(tiltForward, tiltSideways, heading)`); on a car also `netId`, `offset`, `offsetRot` (the car's frame, as `attach`/`attachOffset`/`attachRot` take them). Or `false, why`: `'cancelled'`, `'busy'`, `'model'` (won't load / bad type), `'dead'`.
- Dying or ragdolling ends it (ShowInterrupted "Placing <label>"). The answer is the player's word: check on the server (near them, allowed spot).
```lua
CreateThread(function()
    local spot = Whip.core:PlaceObject('prop_speaker_06', { label = 'Speaker', vehicles = true })
    if not spot then return end
    TriggerServerEvent('myres:server:placed', spot.coords, spot.rot, spot.netId, spot.offset, spot.offsetRot)
end)
```

### PlacePoint(opts?) — CLIENT, WAITS (whip_core 1.2.0+)
A point (position and heading) placed with the Object Viewer's markers, for a spot rather than a prop: a see-through
ghost appears where the camera looks; the player drags the centre dot over the world, the arrows along X / Y / Z,
and the ring to turn it (R swaps). Place (A on a pad) takes it; Esc (B) leaves it. Source `client/place_point.lua`.

| opts | Meaning |
|---|---|
| `at` | `{ x, y, z, w? }`: start from this point, its heading kept (left out: on the surface looked at, facing the player) |
| `model` | the ghost: a prop, or a ped with `ped = true` (it stands and turns); default a small marker |
| `ped` | `true` when `model` is a ped |
| `label` | the bar's name for it |

- Returns `{ x, y, z, w }` (`w` = heading), or `false, why`: `'cancelled'`, `'busy'` (already placing, or the Object
  Viewer is moving something), `'model'` (not in the game files).
- The settings page uses it: a `vec3`/`vec4` entry with `place = true` or `place = { model, ped }` gets a Place
  button (server-ops-devtools.md, setting entry fields).
- The answer is the player's word: check it on the server (staff only, allowed area).
```lua
CreateThread(function()
    local spot = Whip.core:PlacePoint({ model = 's_f_y_shop_mid', ped = true, label = 'Shopkeeper' })
    if spot then TriggerServerEvent('mystore:server:clerk', spot.x, spot.y, spot.z, spot.w) end
end)
```

---

## On-screen text

### ShowText(text, position?, progress?) · ShowText(text, { position, progress, icon, tone }) — CLIENT
- The hint capsule; one slot, newest caller wins; doesn't block. Stays until `HideText()` or the next call.
- `text`: parts split by `|` (`'[E] Place | [C] Cancel'`): first part = title, the rest a row under it. `[Key]` draws a keycap; `{pad:a}` a pad button picture.
- `position` `'bottom'` (default) | `'top'`. `progress` 0–100: a fill you drive by calling again (never waits).
- Table form only: `icon` glyph name for the disc (`'place'`, `'give'`, `'fuel'`, `'talk'`, `'pickup'`...; default = first key); `tone = 'warn'` amber ring ("can't be done here").
- While a bar runs, text shown is held and appears when the bar ends.
```lua
exports.whip_core:ShowText('[E] Plant seed  |  [C] Cancel', { icon = 'place' })
```

### HideText() — CLIENT
- Hides the text only if it's yours. Returns `false` when another resource's text is up, else `true`.

### ShowPlayerText(source, text, opts?) · HidePlayerText(source) — SERVER
- The same band from server code (an objective step, a job instruction). One band per player; a new one replaces whoever had it. Yours: removed when your resource stops, your tag is released, or the player logs out/drops.
- `text` string, colour codes removed, ≤200 chars (`BubbleText.clean`). Page escapes it.
- opts: `position` `'bottom'|'top'`; `progress` 0–100 (clamped); `countdown` seconds (0–604800) puts `· m:ss` after the text, counted down by the player's game a second at a time with the fill draining; `countdownTotal` seconds (the fill's full length, default countdown); `tag` run tag. At 0:00 it stops and stays.
- Returns `true`, or `false, why`: `'no such player'`, `'text is text'`, `'text is empty'`, `"position is 'bottom' or 'top'"`, `'progress is a number, 0-100'`, countdown range sentences. `HidePlayerText` -> `false, 'nothing is shown'` or `false, "the text on screen is X's"`.
- Server text lives under its own owner on the client, so client `HideText` and server hides leave each other alone.
```lua
exports.whip_core:ShowPlayerText(source, 'Get out before the alarm', { countdown = 90, tag = 'run:42' })
```

### ShowObjective(id, text, opts?) · HideObjective(id) — CLIENT
- Director-style objective card, top right, for something your CLIENT runs (server-run work: the Director). Same `id` updates; cards stack newest on top. Removed when your resource stops.
- `id` ≤64 chars; `text` ≤200, colour codes removed; opts: `icon` glyph (≤32; default flag: `'target'`, `'star'`, `'car'`...), `name` (the line under, ≤60), `countdown` seconds (0–604800), `countdownTotal`, `film = true` (stays up on a clean screen).
- `ShowObjective` -> `true` or `false, why` (`'id is a name (64 letters at most)'`, `'text is empty'`, countdown range). `HideObjective` -> `true` (also when none).
- Server objective cards (`PlayerText.objective`) are not exported: Director only.

### IsRadialOpen() — CLIENT
- Is the F1 wheel up? Add wheel entries with `AddAction({ at = { radial = true }, label = ..., icon, description, onSelect })` (label required). Players open it with F1 or by holding D-pad down (`Config.Controller.RadialHoldMs`, 500).

---

## Menus (there is no menu export)
- `UI.ContextMenu` was removed. A "menu" in WHIP is a prompt with options: `AddAction({ at = ..., label, options = { {label, onSelect}, ... } })` (Interactions reference), or an entry on the F1 wheel (`at = { radial = true }`). For a form use `Input`; for yes/no `Confirm`; for a big custom screen, your own NUI page + `SetScreenOpen`.

---

## The composer (one line of text)

Turns the player capsule into a one-line field that takes the keyboard but NOT the mouse (the camera stays put). whip_chat uses it. Closes when its resource stops. `/resetcomposer` (F8, developer mode) frees a stuck keyboard (`Focus.releaseAll`).

| Which text input | Use |
|---|---|
| A form (fields, dropdown, limits), centred, waits | `Input` |
| One line without leaving the game view, keyboard only | `OpenComposer` |
| A code typed into a 3D prompt (keypad, safe) | `ctx.beginInput(opts)` (Interactions) |
| Text on a gamepad | `OpenKeyboard` |

### OpenComposer(opts) — CLIENT
| opts | Meaning |
|---|---|
| `onSubmit(text, mode)` | REQUIRED; `mode` = active mode name or nil |
| `placeholder`, `prefill` | ghost text, starting text |
| `maxLength` | default 256 |
| `modes` | `{ { name, displayName?, color? } }`, cycled with Tab |
| `suggestions` | `{ { name, help?, params? = { { name, help? } } } }`, filtered live |
| `onCancel()` | Escape, an empty line, or CloseComposer |
| `onScroll(delta)` | PageUp -1, PageDown 1 |
| `deferFocus` | don't take the keyboard yet (needed from a key binding, or the key gets typed in) |
| `pad` | type on WHIP's pad keyboard instead; Done submits, B cancels; no modes/suggestions |
| `title` | with `pad`: the keyboard's heading (≤80) |
- Returns `false` if one is already open (never replaces a half-typed line), `onSubmit` missing, a dialog is up (a bare bar is fine), another focus screen is up, or a prompt is being typed into.

### FocusComposer() · CloseComposer() · IsComposerOpen() — CLIENT
- `FocusComposer()` -> boolean: take the keyboard for a `deferFocus` composer (it takes it itself after ~250 ms anyway).
- `CloseComposer()` -> boolean: close YOUR composer without submitting (`onCancel` runs); `false` if none or another's.
- `IsComposerOpen()` -> boolean: any composer.
```lua
RegisterCommand('+myinput', function()
    exports.whip_core:OpenComposer({ placeholder = 'Say something', deferFocus = true,
        onSubmit = function(text, mode) print(text) end })
end, false)
RegisterCommand('-myinput', function() exports.whip_core:FocusComposer() end, false)
RegisterKeyMapping('+myinput', 'Type something', 'keyboard', 'T')
```

---

## Screen ownership and input

### SetScreenOpen(open, key?, opts?) — CLIENT
- Declare your NUI open/closed so the HUD and chat hide, prompts stop, hotkeys stand down, and nothing (WHIP dialogs, bars, other screens) opens on top. Other resources' dialogs/bars answer `'busy'` over it.
- `key` (default `'default'`): which of your screens, so closing one leaves another held. `opts.keepHud = true`: status HUD, minimap and vehicle dial stay (the phone); chat, prompts and hotkeys still make way.
- Returns `false` only with no calling resource (called from inside whip_core). A stopped resource's claims are dropped.
- It does NOT set NUI focus. Call `SetNuiFocus` yourself (or let `Whip.padScreen` do it).
```lua
SetNuiFocus(true, true)
exports.whip_core:SetScreenOpen(true)
-- on EVERY close path:
SetNuiFocus(false, false)
exports.whip_core:SetScreenOpen(false)
```
- Skip the open: HUD and prompts stay over your UI. Skip the close: they stay hidden.

### IsAnyScreenOpen() — CLIENT
- `true` while a screen or a dialog is up (WHIP's inventory/shop/stash/panel, creator, furnisher, emote menu, Director/Systems editors, in-world editors, pause menu, any `SetScreenOpen` screen, or a dialog). A bare progress bar does NOT count.
- Push form: `whip_core:ui:stateChanged` (`{ open }`), a polled (150 ms) local event. Seed once, then listen (calling the export every frame is costly).
```lua
local hidden = exports.whip_core:IsAnyScreenOpen()
AddEventHandler('whip_core:ui:stateChanged', function(e) hidden = e.open end)
```

### IsGameInputFree() — CLIENT
- May a hotkey act / the player start something? `false` while: any WHIP screen, `SetScreenOpen` screen, bar or dialog is up; typing into a prompt; placing/throw/give mode; an emote's placement; any `BlockControls` block with `mode = true`; a focus-holding screen (wheel, chat composer, `/whip`, keyboard, char select, creator, editors); or ANY resource holds NUI focus (`IsNuiFocused()`). E prompts close while it's false.
- Key mappings still fire under a screen (disabled controls don't stop them; `SetNuiFocusKeepInput` screens pass every key). Check it once per press in every world-acting key command.
```lua
RegisterCommand('+my_horn', function()
    if not exports.whip_core:IsGameInputFree() then return end
    -- act
end, false)
```

### SetScreenArea(area, key?) — CLIENT
- Says where your UI sits so the vehicle dial slides up/left out of it (or fades). Hides nothing, takes no keys.
- `area` `{ left, top, right, bottom }` fractions 0–1 from the top-left, `right > left`, `bottom > top`; `nil`/`false` removes. `key` default `'default'`.
- Returns `true`, or `false, why` (`'area.left must be a number from 0 to 1 (a fraction of the screen)'`, `'an area needs right > left and bottom > top'`). Send on change, not per frame; send from `Whip.register` (forgotten on whip_core restart). Removed when your resource stops.
```lua
Whip.register(function()
    exports.whip_core:SetScreenArea({ left = 0.78, top = 0.46, right = 0.98, bottom = 1.0 }, 'phone')
end)
```

### HoldCleanScreen(id?) · ReleaseCleanScreen(id?) — CLIENT
- Nothing on screen but the game, for filming: GTA HUD/radar hidden every frame, every layer of whip's page hidden (`html.whip-clean`), whip's world things (3D prompts, `/me` bubbles, bay decals) not drawn. Chat stays (whip_chat's own frame; F6 hides it). Hidden, not closed: screens opened meanwhile work unseen, so release soon.
- Holds keyed `'<resource>:<id>'` (id default `'default'`), released when your resource stops. Returns `false` only with no calling resource (`ReleaseCleanScreen` always `true` otherwise).
- Others hear `whip_core:ui:cleanScreen` (`{ on, world }`) to put their own UI away. An objective with `film = true` stays.

---

## BlockControls, HoldPlayerPed, PermitNativeWeapon

### BlockControls(id, spec) · UnblockControls(id) — CLIENT
Holds controls off in WHIP's ONE shared `Wait(0)` loop (instead of your own `DisableControlAction` loop). Same id replaces; swept when your resource stops; `UnblockControls` on an unheld id returns `true`. Read blocked controls with `IsDisabledControlPressed`/`IsDisabledControlJustPressed`/`GetDisabledControlNormal`. `/whipcontrols` prints who blocks what.

| spec | Meaning |
|---|---|
| `groups` | `move` {30,31,21,22,36,44} walk, sprint, jump, duck, cover; `combat` {24,25,37,140,141,142,257}; `driving` {59,60,63,64,71,72,75,76,106} steer/throttle/brake/handbrake/exit; `vehicleCombat` {68,69,70,91,92}; `look` {1,2}; `radio` {81..85} (also switches the radio off: `SetUserRadioControlEnabled`); `weaponWheel` {14,15,16,17,99,100}; switches `driveBy` (`SetPlayerCanDoDriveBy`) and `radioControls` |
| `controls` | GTA control ids (whole numbers 0–400). `200` keeps Esc from the pause menu |
| `all` / `except` | every control but the exceptions (`except` only with `all = true`); an exception never frees a control another block holds; `all` also turns the radio off unless 85 is excepted |
| `walk` | a walk at most (holds sprint 21, caps move blend 1.0) |
| `jog` | a jog at most (cap 2.0, sprint key left on); `walk` wins |
| `mode` | your own mode: E prompts, hotbar and wheels stand down (`IsGameInputFree` false) so E is yours. HUD stays |
| `hotbar` | with `mode`: the hotbar's number keys still work (see `whip_core:hotbar:slotUsed` `{ slot }`) |

- Returns `true`, or `false, why`: unknown group (lists the known ones), a bad control id, `` '`except` only goes with all = true' ``, `'nothing to block: name some groups or controls'`, a bad id.
```lua
exports.whip_core:BlockControls('shop', { groups = { 'move', 'combat', 'radio', 'driveBy' }, controls = { 75 } })
exports.whip_core:UnblockControls('shop')
```

### HoldPlayerPed(id, flags) · ReleasePlayerPed(id) — CLIENT
- Holds the player's ped `invincible`, `frozen`, `hidden` (to others too), `noCollision`. Every resource's holds combine (your release never reveals an invisible admin or thaws a downed one). Kept across death and ped changes; swept when your resource stops. Same id replaces.
- Returns `true`, or `false, why` (`'flags is a table: { invincible, frozen, hidden, noCollision }'`). Release of an unheld id -> `true`.
```lua
exports.whip_core:HoldPlayerPed('hang', { hidden = true, noCollision = true })
```

### PermitNativeWeapon(weapon, on) — CLIENT
- WHIP removes GTA weapons no resource permits (`Config.WeaponGuard`). Permit yours (hash or name) BEFORE giving it; permits go when you stop. Returns `false` for a bad weapon.
```lua
exports.whip_core:PermitNativeWeapon('WEAPON_PETROLCAN', true)
```

---

## Hands: FreeHands, BlockHands, held props, body state

### FreeHands() — CLIENT, WAITS
- Something is about to go in the player's hands (phone, tool): runs the `freeHands` client hook (whip_gunny holsters, whip_fuel drops the nozzle) and waits for it.
- Returns `true` when no weapon is in hand afterwards (`WEAPON_UNARMED`), `false` if one still is, or `false, label` while a hands block of everything is on.

### FreeHands(source) — SERVER
- Asks that player's game to empty the hands now. Returns `true` once asked, or `false, 'No player with that server id is online'`.

### BlockHands(id, opts?) · UnblockHands(id) · AreHandsBlocked(what?) — CLIENT
### BlockHands(source, id, opts?) · UnblockHands(source, id) · AreHandsBlocked(source, what?) — SERVER
- `opts = { label?, only? = 'weapons' }`. No `only`: everything (hands emptied at once, `FreeHands` false, default label `'Your hands are busy'`). `only = 'weapons'`: guns put away, none drawn (default `'You cannot use a weapon here'`). `only` other than `'weapons'` refused.
- `AreHandsBlocked('weapon')` true for any block; `AreHandsBlocked()` true only for a block of everything. Returns `true, label` or `false`. Server version sees only server blocks.
- Server blocks are sent to the player's game, gone at logout/drop or when the owner stops. Events `whip_core:hands:blocked` (`{ label, only }`) / `whip_core:hands:unblocked` (`{}`).

### GetBodyState() — CLIENT
- Returns `'underwater'|'swimming'|'falling'` and words (`'You cannot do that while swimming'`...), or `false`. Same states as `notWhile`.

### Held props (server-owned)
- `HoldProps(source, props, tag?)` — SERVER: put up to two props in a player's hand for everyone: `{ { model, bone? (18905), offset? {x,y,z}, rot? {x,y,z} } }`; tag becomes `'<resource>:<tag>'` (default `'held'`, ≤40). Any new set replaces the hand (`whip_core:heldProps:lost`, reason `'replaced'` / `'world'`). Returns `true` or `false, why`.
- `DropHeldProps(source, tag?)` — SERVER: drop your props (with no tag, whatever of yours they hold).
- `GetOwnHeldProp(model, tag?)` · `DropOwnHeldProp(model, tag?)` · `SetOwnHeldPropPose(model, tag?, pose)` — CLIENT: your resource's held prop in this player's hand on this game: find it (entity or nil), delete it at once (still tell your server), or re-pose it (`pose = { bone?, offset = {x,y,z}, rot = {x,y,z} }`, nil = the server's place) -> boolean.

---

## Client hooks (RegisterClientHook)

### RegisterClientHook(hookName, handler, id?) — CLIENT
- Subscribe to a whip_core client moment. Names (any other refused, F8 warning): `'beforeGiveMode'` (inventory give mode opening), `'beforePlaceMode'` (an emote or PlaceObject placing starts), `'freeHands'` (something is about to use the hands: put away what you hold).
- `handler` may return a number of ms for whip_core to wait afterwards (longest wins, clamped to 1000). Handlers are pcall'd, run in their own thread; a handler that itself waits past 1000 ms is abandoned (whip goes on, one F8 warning). Return a delay instead of waiting.
- Keyed `'<resource>:<id or hookName>'`; registering again replaces (safe in `Whip.register`); dropped when your resource stops. Returns `true` or `false, why`.
```lua
exports.whip_core:RegisterClientHook('freeHands', function()
    if phoneOut then putPhoneAway() return 300 end
end)
```

---

## Controller support

### What you get free
- Prompts (`AddAction`): A uses the one in view; D-pad up/down step its options.
- F1 wheel: hold D-pad down.
- `Progress`, `Input`, `Confirm`, `SkillCheck` and WHIP's panels read the pad themselves.
- Typing: `OpenKeyboard`.
- Hints: `{pad:a}` in `ShowText`. Names: `a`, `b`, `x`, `y`, `lb`, `rb`, `lt`, `rt`, `ls`, `rs`, `l3`, `r3`, `dpad`, `dpad_up`, `dpad_down`, `dpad_left`, `dpad_right`, `view`, `menu`; images at `https://cfx-nui-whip_core/html/img/pad/<name>.svg`.
- LB is WHIP's combo key: LB+A talk, LB+X radio, LB+B Gunny ammo check; players may put other actions on LB+button. Everything here leaves LB combos to WHIP.
- FiveM pad key bindings (`RegisterKeyMapping` with a pad) never fire: use `RegisterPadAction`.
- Under the hood: the browser can't read a gamepad (iframe Permissions-Policy), so whip_core reads frontend controls in Lua (`client/controller.lua`) while a panel with a nav scope is open, holding every gameplay control off (`padNav` block, `all = true`) with `SetNuiFocusKeepInput(true)`.

### RegisterPadAction(id, def) · RemovePadAction(id) — CLIENT
Puts your action on a WHIP button, shown on the pause menu's Controller screen where players can move it.

| def | Meaning |
|---|---|
| id | `^[%a][%w_]*$`, ≤32 chars; layouts save by it; not one of WHIP's (`engine`, `inventory`, `radial`, `sprint`) |
| `label` | required, ≤32 chars |
| `command` | a key command name (`'+my_action'`, its `-` half on release; pattern `^[%w_%+%-%.%:]+$`). Exactly one of `command` / `onPress` |
| `onPress` / `onRelease` | functions, must not wait; `onRelease` only with `onPress` |
| `slot` | `dpad_up`, `dpad_down`, `dpad_left`, `dpad_right`, `l3`, `veh_a` (A in a vehicle), `foot_b` (B on foot), `lb_a`, `lb_b`, `lb_x`, `lb_y`, `lb_dpad_up`, `lb_dpad_down`, `lb_dpad_left`, `lb_dpad_right`. None: players place it |
| `where` | `'car'` or `'foot'`. A ready `'car'` action shows over the dial (keep it not-ready where it does nothing) |
| `menus` | `true`: works with a screen open (talk). Otherwise waits for `IsGameInputFree` |
| `ready` | default `true`; see `SetPadActionReady` |
- Default layout (`Config.Controller.Layout`): `dpad_up` phone, `dpad_down` radial, `dpad_left` engine, `dpad_right` inventory, `l3` sprint, `veh_a` nitrous, `foot_b` gunny_reload, `lb_a` talk, `lb_b` gunny_check_ammo, `lb_x` radio; free: `lb_y`, `lb_dpad_*`. A slot already taken in the default -> action registered on NO button (F8 says once); two resources asking for one free button: the id first alphabetically wins.
- Registering again replaces; removed when your resource stops. Returns `true`, or `false, why` (bad field named, a WHIP id, an id another resource holds).
```lua
Whip.register(function()
    Whip.core:RegisterPadAction('mycafe_menu', { label = 'Cafe menu', command = 'mycafe_menu', slot = 'lb_y' })
end)
```

### SetPadActionReady(id, ready) — CLIENT
- Not ready: keeps its button but presses reach GTA (nitrous ready only with a bottle, so a motorbike keeps A for ducking). Returns `true`, or `false, 'pad action "x" is not one of yours'`.

### GetPadActionButton(id) — CLIENT
- Any action (yours, another's, WHIP's `'radial'`, `'inventory'`, `'engine'`, `'sprint'`) in this player's layout. Returns `slot` (`'lb_y'`), `pictures` for ShowText (`'{pad:lb}{pad:y}'`), `name` (`'LB+Y'`); `nil` when on no button or no such action. Ask each time you show a hint.
```lua
local slot, pictures = Whip.core:GetPadActionButton('mycafe_menu')
if type(slot) == 'string' then exports.whip_core:ShowText(pictures .. ' Cafe menu') end
```

### Whip.padScreen(def?) — CLIENT (satellite helper, `@whip_core/lib/satellite.lua`)
A pad on your own NUI screen. Make ONE at file scope; `screen:open()` when your screen opens, `screen:close()` on every close path. It reads the pad while open, sends presses to your page, OWNS your NUI focus (`SetNuiFocus(open, open and not pad)` and keep-input; no cursor while a pad drives; moving the mouse brings it back after 150 ms settle), and holds the pad's world actions off while a pad drives. Leaves LB combos to WHIP. Pauses itself while `OpenKeyboard` is up (`whip_core:keyboard:opened/closed`).

| def | Meaning |
|---|---|
| `buttons` | default `up, down, left, right, a, b, x, y`; also `lb` (sent on release only if no combo used), `rb`, `menu`. Unknown name printed and skipped |
| `stick` | `false`: the left stick doesn't step like the D-pad (threshold 0.6) |
| `releases` | `{ a = true }`: also send `down = false` on release |
| `keepInput` | `'always'`: game keeps input with the mouse too (an orbit camera). Default `'pad'` (only on a pad) |
| `block` | held off while a pad drives, BlockControls spec, or `false`. Default `{ groups = { 'move','look','combat','radio','weaponWheel' }, controls = { 22, 23, 36, 44, 45, 199, 200 } }` |
| `onButton(cmd, down, rep)` / `onDevice(pad)` | instead of the NUI messages |
| `onFrame()` | every frame a pad drives (your own stick reading) |
- Page messages: `{ action = 'pad', cmd, down, rep }` per press (`rep` = repeat count of a held direction: first after 380 ms, then every 110 ms) and `{ action = 'padDevice', pad }` on device swap. The press that opened the screen is not sent.
- Methods: `:open()` -> whether a pad is in use (tell your page for hints); `:close()`; `:typing(on)` (your text field has the keyboard: pad ignored, no game input); `:pause(on)` (another screen of yours has the pad); `:isPad()`.
- It does NOT call `SetScreenOpen`: do that yourself.
```lua
local screen = Whip.padScreen()
local function open()  exports.whip_core:SetScreenOpen(true); SendNUIMessage({ action = 'open', pad = screen:open() }) end
local function close() screen:close(); exports.whip_core:SetScreenOpen(false) end
```

### OpenKeyboard(opts?) — CLIENT, WAITS
- WHIP's on-screen keyboard for a pad player; open it only on a pad (`IsControllerActive`). Opens over any page; takes whip_core's focus (your resource's focus vote stands under it).
- opts: `title` (≤80), `value` (starting text), `placeholder` (≤120), `numeric` (digits, minus, point), `maxLength` (≤2000), `predict` (`false`: no suggestions/learning, for a plate or code). Suggestions in the player's language (`Config.Keyboard`), learned per PC; RT takes the first suggestion.
- Returns the string, or `nil` when left (B, Cancel), replaced by another `OpenKeyboard` (one at a time), the asking resource stopped, death, or logout.
- While up the pad is its alone: other pad readers wait between `whip_core:keyboard:opened` (`{ id, owner }`) and `whip_core:keyboard:closed` (`{ id }`).
```lua
local text = Whip.core:OpenKeyboard({ title = 'Search', value = current, maxLength = 40 })
```

### Mode keys: IsAcceptPressed() · IsAcceptHeld() · IsCancelPressed() · AcceptHint() · CancelHint() — CLIENT
- A mode of your own confirms with Interact (E, or wherever the player bound Interact) and cancels with C (control 26); on a pad A (201) and B (202), never with LB held. Read every frame; they follow the device in use and read through blocks (disabled readers). `IsAcceptPressed` ignores the press that started the mode.
- Hints: `'[E]'` / `'[C]'` or `'{pad:a}'` / `'{pad:b}'`.
- Hold a `BlockControls` block with `mode = true` naming what the keys also do in GTA: C look behind (26), B reload/melee (45, 140).
```lua
exports.whip_core:BlockControls('placing', { controls = { 26, 45, 140 }, mode = true })
while placing do
    if exports.whip_core:IsAcceptPressed() then place() end
    if exports.whip_core:IsCancelPressed() then placing = false end
    Wait(0)
end
exports.whip_core:UnblockControls('placing')
```

### IsKeyPressed(key, button) · IsKeyHeld(key, button) · KeyHint(keyText, button) — CLIENT
- Any other key by the same rules: `key` read on a keyboard, `button` on a pad, never both, never with LB; either may be nil. GTA control numbers; pad ones are frontend: 201 A, 202 B, 203 X, 204 Y, 206 RB, 199 Start, D-pad 187–190; never LB (205).
- `KeyHint(keyText, button)`: `'[Space]'` on keyboard, `'{pad:x}'` on pad, `''` if that side is nil; `button` may be a list `{ 'lt', 'rt' }`.
```lua
if exports.whip_core:IsKeyPressed(22, 203) then flip() end   -- Space, or X
local hint = exports.whip_core:KeyHint('Scroll', { 'lt', 'rt' }) .. ' Turn'
```

### IsControllerActive() — CLIENT
- `true` when the last input was a gamepad. For picking hint pictures, not changing controls. Ask once, then listen: `whip_core:pad:deviceChanged` (`{ pad }`).

### WHIP page-side pad API (for whip_core's own page modules)
- In whip_core's page, a key scope `NuiRouter.registerKeyScope({ name, priority, isOpen, onKey, onNav(nav, mods), analog, onAnalog(a), padHints })` takes pad intents `'up','down','left','right','select','back','buttonX','buttonY','tabPrev','tabNext'` (`mods.rb` when RB held). This is internal to whip_core's page; a separate resource's page uses `Whip.padScreen`.

---

## Camera system

One scripted camera at a time, owned by the resource that started it. Play exports return `false, 'busy'` while ANOTHER resource's camera is up (you may replace your own; whip_core may replace any). When the owner stops, WHIP hands the view back (no `onResourceStop` needed). A shot inside an MLO draws its interior (`ViewportRoom.follow`).

Three ways: a Camera Creator sequence (`PlayCameraSequence` by name or table), an orbit until stopped (`OrbitCamera`), or one fixed shot (`PlayCamera`) / a simple path (`PlayCameraPath`, played as a sequence).

### PlayCamera(opts) — CLIENT, WAITS (unless async)
| opts | Default |
|---|---|
| `pos` vector3 | the gameplay camera's position |
| `rot` vector3 (pitch, roll, yaw) | `0,0,0` |
| `fov` | `60` |
| `filter` | `'none'`; listed: `'scanline_cam'`, `'CAMERA_secuirity'`, `'CAMERA_secuirity_FUZZ'`, `'heliGunCam'`, `'NG_filmic04'`, `'NG_filmic08'`, `'cinema'`, `'underwater'`, `'Forest'`, `'Tunnel'`, `'phone_cam1'`, `'phone_cam2'` (any timecycle name is applied) |
| `canLook` | `false` (mouse look; pitch clamped ±89) |
| `canMove` | `false` (WASD, Space up, Ctrl down, 0.5 m/frame) |
| `exitKey` | `true`: Esc (control 200) ends it |
| `transitionIn` / `transitionOut` | `0` ms ease from/back to gameplay |
| `async` | `false` |
- Returns `true` (after it ended, or at once with `async`), `false, 'busy'`, or `false, why` (`'pos must be a vector3'`, `'rot must be a vector3'`, `'fov must be a number'`, transition not a number).
- Without `async` it waits; with `exitKey` (default), `canLook` or `canMove` its controls run in your thread until the camera ends. With none of those and no async it returns immediately but the camera stays up until `StopCamera`.
```lua
exports.whip_core:PlayCamera({ pos = vector3(-1042.0, -2745.0, 22.0), rot = vector3(-10.0, 0.0, 180.0),
    fov = 50.0, filter = 'cinema', async = true })
```

### PlayCameraPath(opts) — CLIENT, WAITS (unless async)
| opts | Default |
|---|---|
| `points` | required, ≥2 `{ pos, rot, fov?, filter? }` (pos/rot vector3) |
| `mode` | `'interpolate'` (smooth curve at constant speed: key times by distance) or `'cycle'` (cut and hold) |
| `duration` | `10000` ms (whole path, interpolate) |
| `easing` | `'smooth'`; `'linear'`, `'ease-in'`, `'ease-out'` (mapped to sequence eases `in`/`out`) |
| `loop` | `false` |
| `cycleDuration` | `3000` ms per point (cycle) |
| `transitionIn` / `transitionOut`, `async` | as PlayCamera |
- Returns `true`, or `false, why` before any camera goes up: `'a path needs at least 2 points'`, `'point N needs a pos and a rot (vector3)'`, `"mode is 'interpolate' or 'cycle'"`, duration/cycleDuration ≤ 0, `'busy'`. A failure mid-path hands back to gameplay.
- A `loop` path never ends: use `async = true` or the call never returns.

### PlayCameraSequence(sequence, opts?) — CLIENT, WAITS (unless async)
`sequence` = a saved name (fetched from the server the first time via callback `whip_core:camseq:fetch`, then cached; call from a thread) or the table (Creator's "Copy code").

| opts | Meaning |
|---|---|
| `subjects` | `{ [name] = entity | { x, y, z, h } }` (vector3/vector4 ok; `w` as heading). `'player'` and `'vehicle'` (the car the player is in, or last in) need nothing |
| `async` | return at once |
| `loop`, `letterbox` | override the sequence's own (letterbox = 2.39:1 bars, GTA HUD hidden) |
| `speed` | 1 as made; 0.05–20 |
| `startAt` | ms into it |
| `hold` | stay on the last moment until stopped |
| `control` | player turns/zooms its orbits (mouse + wheel, or right stick + LT/RT); holds `look` + 241, 242, 207, 208 |
| `exitKey` | Esc or B (200, 202) ends it. Default OFF |
| `transitionIn`, `transitionOut` | ms ease from/back (default 0) |
- Returns `true`, or `false, why` before any camera goes up: the key and field that's wrong, `'its anchor X is not there'`, `'none of its subjects is there'`, `'There is no camera sequence called X'`, `'speed must be between 0.05 and 20'`, `'subjects must be a table of names'`, `'busy'`. A subject that goes away mid-sequence holds the last picture.

**Sequence** `{ keys, length?, anchor?, loop?, letterbox?, ease?, name? }` (times in ms): `keys` 1–200; `length` default last key's `t`, max 30 min; `anchor` a subject name whose captured position (at start) fixed places are kept round; `ease` whole-timeline curve `'linear'` (default) | `'smooth'` | `'in'` | `'out'` | `'strong'` (the Creator doesn't use it); `name` ≤60.

**Key** `{ t, shot, move?, ease?, rate?, around?, coast?, shake?, filter?, punch?, label? }`:
- `t` required (0–30 min). Keys sorted by time (stable).
- `move` to the next key: `'cut'`, `'glide'` (default; consecutive glides are ONE flowing move through the keys; the first key's `ease` (default `'smooth'`) shapes its start/end), `'spring'` (`rate` 0.5–30; ~3 gentle to 8 brisk), `'orbit'` (between two orbits of one subject; `around` `'short'` default, `'left'`, `'right'`). A move between two shots looking at one subject keeps looking at it.
- `coast` 0.2–50: on a key the camera stops at (last key, or a `cut`), the camera carries on past with its speed, resistance = coast (10 m/s at 2 drifts 5 m).
- `shake = { amount 0–10 (deg), freq 0.2–40 (default 6) }` (a number = amount); blends key to key.
- `filter` timecycle name (`^[%w_%-]+$`, ≤48), from that key on.
- `punch = { fov -60..60, decay 0.2–30 (default 4) }` a lens kick at the key.
- `label` ≤40.

**Shot**: `kind` + `fov` (1–130, default 50) + `roll` (-180..180) + `subject` (all but fixed; `^[%w_]+$`, ≤32):

| kind | Fields (ranges, defaults) |
|---|---|
| `fixed` | `pos = {x,y,z}`, `rot = { x = pitch, y = roll, z = yaw }` (default 0s; kept round the anchor if any) |
| `orbit` | `yaw` (-720..720, 0 behind, 180 in front), `pitch` (-80..85, default 10, degrees above), `fit` (0.05–20; 1 fills the screen) or `dist` (0.3–500 m; neither -> fit 1), `aim = {x,y,z}` (share of the subject's box -1..1; +y front, +z top, +x right), `look = { pitch -90..90, yaw -180..180 }` off that point, `turn` (-180..180 deg/s drift), `clear` (-1..10 m above ground, default 0.35) |
| `chase` | `dist` (0.5–60, 5), `height` (-5..30, 1.8), `ahead` (0–30, 3.5 look-ahead), `slip` (0–1, 0.35: 0 nose, 1 travel direction), `stiff` (0.5–40, 7), `turnRate` (0.5–40, 7), `fovAdd` (-40..60, 8, at speed), `distAdd` (-10..20, 1), `collision` (pull in at walls, default on) |
| `mounted` | `offset = {x,y,z}` in the subject's metres (right, forward, up; ±200), `rot` relative (±720) |
| `track` | `pos`, plus orbit's `aim` and `look`: stands still, keeps the subject in frame |

A point subject has a 1 m box so `fit`/`aim` work round a place. Unknown fields are dropped by `CamSequence.clean` (same check on save, load and play).

```lua
exports.whip_core:PlayCameraSequence('car_reveal', { subjects = { target = veh }, async = true })
exports.whip_core:PlayCameraSequence({ letterbox = true, keys = {
    { t = 0, move = 'glide', ease = 'smooth',
      shot = { kind = 'fixed', pos = { x = -75.2, y = -819.4, z = 326.1 }, rot = { x = -12, y = 0, z = 140 }, fov = 50 } },
    { t = 4000, move = 'orbit', around = 'left',
      shot = { kind = 'orbit', subject = 'vehicle', yaw = 30, pitch = 8, fit = 1.2, fov = 40, turn = 6 } },
    { t = 9000, shot = { kind = 'orbit', subject = 'vehicle', yaw = 160, pitch = 4, fit = 0.9, fov = 36 },
      shake = { amount = 0.3, freq = 6 } },
} })
```

### OrbitCamera(target, opts?) — CLIENT (returns at once)
- An orbit round an entity or place `{ x, y, z, h }` until `StopCamera`. Implemented as a one-key sequence with `hold = true`, `async = true`.
- opts: `yaw` (35), `pitch` (12), `fit` (1.3) or `dist`, `aim`, `look`, `fov` (40), `turn`, `clear` (as an orbit shot); `control` (default ON: mouse/right stick turns (pitch -70..75), wheel/LT-RT zooms 0.35–3×); `exitKey` (default off: Esc/B); `letterbox`; `transitionIn`/`transitionOut` (default 500 each).
- Returns `true`, or `false, why` (`'orbit what? an entity, or a place { x, y, z }'`, `'busy'`, sequence errors).
```lua
exports.whip_core:OrbitCamera(veh, { yaw = 35, pitch = 12, fit = 1.3, fov = 40, turn = 6 })
exports.whip_core:StopCamera()
```

### StopCamera() · IsCameraActive() — CLIENT
- `StopCamera()` stops YOUR camera, easing back over its `transitionOut` (the cam is destroyed after the ease). Returns `false` when none is playing or it's another resource's.
- `IsCameraActive()` -> boolean: any scripted camera from this API is playing.

### Camera Creator (server owners)
- Turn on: `/whip` -> Settings -> Config -> Experimental features (`Config.Experimental.cameraCreator`, default `false`); a row at the end of the `/w` dev menu.
- Fly holding RMB + WASD/Space/Ctrl (pad: sticks). G adds a key at the playhead; Space plays. Shots Fixed/Orbit/Chase/Mounted/Track of you, your vehicle, or a picked thing (`'target'` subject); moves Cut/Glide/Spring/Orbit.
- Save keeps it on the server by name: DB table `whip_camera_sequences` (`name` VARCHAR(60) PK, `data` MEDIUMTEXT JSON, `updatedBy`, `updatedAt`). Name `^[%w_%-]+$` ≤60; JSON ≤256 KB. Saving/deleting needs ACE `whip.devtools` AND a permanent admin (`Settings.mayEdit`); playing/fetching is anyone's. Saved sequences failing `CamSequence.clean` at boot are skipped with a console line. Clients' cache is invalidated by `whip_core:client:camseqChanged (name)`. Server scripts can read one with `exports.whip_core:__GetCameraSequence(name)` (internal-style export: a copy or nil).
- Copy code copies the Lua call; the draft is kept on this PC.
- Cinematic: F9 plays in game as your character (record with OBS); F5 rolls the timeline live (again to cut back); Page Down/Page Up or Num 1–9 cut between cameras; F9 back to the editor. A rolling shot holds a clean screen (F6 hides chat). With "Plays round" set to your vehicle, cameras are placed round the car wherever it is.

### Driving camera (server owners)
- Smooth chase camera for cars, motorbikes, quads; each player switches it on in the pause menu (Server Settings -> Vehicles -> Smooth driving camera). Steps aside for aiming, GTA's cinematic camera, death, any other script camera. C looks behind; first person stays GTA's.
- `Config.DrivingCamera = { Enabled = true, Default = false, Shake = 1.0 (0–3), Style = 'consistent' | 'cinematic' }` (`/whip` -> Settings -> Config -> Vehicles). Cinematic frames by action: jump (back/up), drift (further back), burnout from stop (lower/closer/wider), nitrous (closer, much wider).

### Internal camera pieces (not exported)
- `FreeCam` (`client/freecam.lua`): the detached fly camera behind noclip and the furnisher. `Curtain` (`client/curtain.lua`): whip's own blackout that reports back when the screen is truly black (character screen, loads). Neither has an export; use `DoScreenFadeOut` / your own cameras.

---

## Theming and skins

- Every repeated visual value is a CSS custom property in `whip_core/html/css/base.css`. A skin is its own resource: `fxmanifest.lua` + `theme.css` that redeclares tokens on `:root`. whip_core's page injects `<link id="whip-theme" href="https://cfx-nui-<resource>/theme.css">` LAST in `<head>` (`html/js/theme.js`), so the theme wins at equal specificity. Resource name must match `^[A-Za-z0-9_-]{1,64}$`. Missing/stopped resource or missing `files{}` entry: the link 404s, is removed, base look survives, F8 names the resource.
- Standing theme: `Config.Theme = 'your_theme_resource'` (default `nil`; config §13; editable in `/whip` Settings, live). Dev: `/whip_theme <res>` (ACE `whip.devtools`) re-applies live; `/whip_theme none` base look; `/whip_theme` alone re-applies the server's current.
- Runtime skin: a resource calling `SetActiveTheme`; `start` reskins every client live, `stop` reverts to `Config.Theme`. Late joiners get it at login.
- The theme reaches whip_core's page only. Your own resource page does not get `theme.css` automatically.

```css
/* theme.css: override tokens, nothing else */
:root { --ui-accent: #fbbf24; --ui-surface: rgba(20, 15, 8, 0.78); --ui-radius-panel: 10px; }
```

### SetActiveTheme(resource) — SERVER
- Set (or clear with `nil`) the server-wide override over `Config.Theme`. Registry rule: owned by the setter; only it can change/clear it; a second resource is refused; when it stops the look reverts. Same owner, different theme: replaces. Clearing when nothing is set returns `true`.
- Returns `true`, or `false, err`: `'the active theme belongs to X — stop it first'`, `'resource must be a resource name (short string) or nil'` (≤64 chars).
- Call inside `Whip.register` (re-runs after a whip_core restart; the override dies with whip_core), not at file scope.
```lua
-- skin resource server.lua; fxmanifest: shared_script '@whip_core/lib/satellite.lua', files { 'theme.css' }
Whip.register(function() exports.whip_core:SetActiveTheme('my_skin') end)
```

### GetActiveTheme() — SERVER
- Returns `theme, owner`: the override's resource and its setter; with no override, `Config.Theme` (nil = stock) and no owner.

### Token catalog (`base.css`)
- Surfaces: `--ui-surface` rgba(10,12,18,.75), `--ui-surface-raised` (.9), `--ui-surface-solid` rgb(10,12,18), `--ui-surface-hover` (white .05), `--ui-surface-hover-strong` (.10), `--ui-surface-subtle` (.02), `--ui-surface-light` (.03), `--ui-surface-medium` (.04).
- Borders: `--ui-border` (white .08), `--ui-border-hover` (.12).
- Shadows: `--ui-shadow`, `--ui-shadow-lg`, `--ui-shadow-modal`, `--ui-shadow-text`, `--ui-rim` (world-facing text).
- Radius ladder: `--ui-radius-panel` 20px, `-pop` 12, `-row` 11, `-slot` 8, `-sm` 6, `-xs` 4, `-pill` 3, `-hair` 2 (bars, scrollbar thumb), `-capsule` 38 (HUD capsule, bubbles, NPC dialog).
- Text: `--ui-text` (white .93), `--ui-text-mid` (.5), `--ui-text-dim` (.25), `--ui-text-label` (.48).
- Semantic: `--ui-accent` #60a5fa + `-glow` .2, `-subtle` .07, `-light` .15, `-medium` .3; `--ui-on-accent` #fff; `--ui-success` #4ade80 + `-subtle`, `-light`, `-medium`; `--ui-error` #f87171 + `-subtle`, `-light`; `--ui-warning` #fbbf24 + `-light`; `--ui-info` #60a5fa.
- Death screen: `--ui-death-curtain`, `--ui-death-track`. Skill ring: `--ui-skill-target`, `-fill`, `-full`, `-done`, `-edge`, `-outline`, `-clock`.
- Slot tile: `--ui-slot-bg`, `-bg-filled`, `-bg-hover`, `-bg-chosen` (= accent-light), `-line-w` 1px, `-line-w-lg` 2px, `-line`, `-line-filled`, `-line-hover`, `-line-focus`, `-lift`, `-glow`; `--ui-ring` (white .65); `--ui-hotbar-scale` 1.5.
- Pill: `--ui-pill`, `--ui-pill-ink`, `--ui-pill-ink-mid`, `--ui-pill-hover`. `--ui-panel-glow` (radial accent glow; `none` = plain glass). `--ui-scrim` (inventory dim fallback). `--ui-item-shadow`, `--ui-item-shadow-lifted`. `--ui-zoom-inventory` 1.32 (tune with care).
- Type: `--ui-font` `'Barlow', 'Segoe UI', sans-serif`; `--ui-mono` (= font; pair with tabular-nums); `--ui-font-display` `'Bricolage Grotesque'`; `--ui-fw-display` 800; `--ui-fs-xs` 9, `-sm` 11, `-md` 13, `-lg` 16, `-xl` 20, `-caption` 12, `-body-lg` 14, `-display` 26; `--ui-fw-regular` 400, `-medium` 500, `-semibold` 600, `-bold` 700.
- Motion: `--ui-ease` cubic-bezier(0.16,1,0.3,1), `--ui-ease-bounce`.
- Spacing: `--ui-sp-1` 2px, `-2` 4, `-3` 6, `-4` 8, `-5` 10, `-6` 14, `-7` 20, `-8` 28.
- Scrollbars: `--ui-scrollbar-w` 3px, `-thumb`, `-thumb-hover`; reach bar `-w-reach` 6px, `-thumb-reach`, `-thumb-reach-hover`.
- Native options: `--ui-select-option-bg` #111, `--ui-select-option-fg` #ccc.
- LOCKED (mirrored in JS; never change): `--ui-fade` 0.18s, `--it-fade` 0.25s. NOT themeable: `--ui-scale` (JS writes it inline).
- Legacy `--inv-*` aliases (all `var(--ui-*)`): override `--ui-*` instead. Director `--dr-*` and Systems Creator `--sy-*` families also exist.
- Partial themes: scope selectors under one panel root (`#ui-notifications .ui-notif {}`); prefer token overrides (the contract) over selectors (class names not promised); avoid unscoped element selectors and `!important`. Layout is not themeable: replacing the inventory renderer is `Config.InventoryRenderer` / `docs/nui-inventory.md`.
- Own fonts: override `--ui-font`/`--ui-mono`, ship files in the theme resource's `files {}`, `@font-face { src: url('https://cfx-nui-<theme>/fonts/x.woff2') }`.

---

## Pictures of WHIP's real screens without the game (PR before/after)

Verified 2026-11-17 for WHIPFX/whip_core #62, #76, #81, #85, with local helper scripts (not in this repo):
- **Two versions side by side:** `git worktree add` each branch and the commit it grew from (`git merge-base origin/main <branch>`), not today's main, so only your change differs.
- **Serve them with `server.cjs`, not `python -m http.server`.** whip_core's page loads 100+ modules at once. Python's server refused some, and then the page never started, flakily. `server.cjs` also serves `/res/<resource>/...` from the sandbox's resources, so media packs load.
- **`shot.js` plays the game:**
  - It answers `https://whip_core/<callback>` with `{}` (or `__answers[name]`) and maps `cfx-nui-<pack>` script, image and fetch URLs to `/res/`.
  - Helpers: `send(msg)`, `openPanel(section)` (resends `openWhipPanel` until `wpSectionEnter` comes back), and `waitFor(sel)` (any visible match).
  - Feed data with `send({ action: 'wpSectionData', section, kind, payload })`.
- **`shoot.sh <name> <path> <x0,y0,x1,y1> '<setup js>'`:** renders 1920x1080 headless through ui-scaling's `rescheck.mjs` (`--eval` takes await; `MOUSE=x,y` hovers and `CLICK=x,y` presses with a real mouse) and crops with PIL. `probe.sh` prints what the setup passes to `probe(...)`, to find boxes first.
- **Messages that open screens:**
  - /whip panel: `openWhipPanel {section}`.
  - Pause menu: `pauseOpen`, then `pauseData {player, waypoint, blips, route}`; click the `[data-i]` row "Map".
  - `/w`: `devMenuShow {tools, index, title, view}`, rows as `BuildDevMenuPayload` in `tools/core.lua` makes them.
  - Player Manager: `kind: 'all' {users}`, click `[data-action=pmgSelect]`, then `kind: 'detail' {userId, online, source, ...}`. Its Actions group starts collapsed; click its header.
- **Limits:**
  - Headless Edge has no WebGL, so the 3D pause map stays black. Draw blip marks with the page's own `blipImage()`, inside an element that sets `--pmap-blip` (22px, as the map does).
  - A native `<select>` popup and CSS `:hover` without `MOUSE` never show in a page picture.
  - Pages whose data comes from the server's schema (Settings → Config) need that data faked; describe those in text.
- **Hosting the pictures:** an image-only `pr-assets` branch on the fork (`git init` in a temp folder, push to `pr-assets`), linked as `https://raw.githubusercontent.com/<fork>/whip_core/pr-assets/<file>.png`. Commit with the GitHub noreply address.

## Building your own NUI page that fits WHIP

Resource side:
1. fxmanifest: `ui_page 'html/index.html'`, `files { 'html/**' }`, `shared_script '@whip_core/lib/satellite.lua'` (needed for `Whip.*` helpers and for page-tools' probe/error bridge), `dependency 'whip_core'` if you hold flags across waits.
2. On open: `SetNuiFocus(true, true)` (or `Whip.padScreen():open()`), `exports.whip_core:SetScreenOpen(true[, key, { keepHud }])`; if it sits in the HUD's corner, `SetScreenArea`. On EVERY close path: focus off, `SetScreenOpen(false)`.
3. Before opening, check `IsGameInputFree()` / `IsAnyScreenOpen()`; after any WHIP dialog over your screen returns, `SetNuiFocus(true, true)` again.
4. Use WHIP dialogs (Confirm/Input) rather than in-page ones when they fit; they answer `'busy'` only over OTHER resources' screens.
5. Hide overlays via `whip_core:ui:stateChanged` / `whip_core:ui:cleanScreen`.

Pictures WHIP already ships (use them before making art; verified 2026-11-17):
- **Items:** the client `GetItemDef(key)` gives `name` (the label, not `label`), `weight` and `img` (an absolute URL when the owning resource ships one). With no `img`, the picture is `https://cfx-nui-whip_core/html/img/items/<key>.png`. Some gunny items (`gunny_smokegrenade`) have no picture at all: ship your own and fall back to it on the image's `error`.
- **Vehicles:** `https://cfx-nui-whip_media_previews/img/vehicles/<model lowercased>.webp` (all GTA police cars are there).
- **Clothing:** `https://cfx-nui-whip_media_clothing_<male|female>/img/clothing/<body>/<slot folder>/<body>_<comp>_<collection>_<NNN>_<TT>.webp`, for example `11_tops/male_11_base_000_00.webp`. The collection and NNN are not the global drawable: on the client, `GetPedCollectionNameFromDrawable(ped, comp, d)` and `GetPedCollectionLocalIndexFromDrawable(ped, comp, d)`, with `''` or `GetPedCollectionName(ped, 0)` written `base` (`whip_core/client/appearance.lua:663-704`).

Page side (all files are served cross-resource from `https://cfx-nui-whip_core/...`):
- Fonts: `<link rel="stylesheet" href="https://cfx-nui-whip_core/html/css/fonts.css">` (Barlow 400–800, Bricolage Grotesque 200–800; vendored woff2, `font-display: block`). whip_dealership `@import`s it from CSS.
- Tokens: `<link rel="stylesheet" href="https://cfx-nui-whip_core/html/css/base.css">` (whip_gunny does). Load fonts.css first. base.css also sets `* { margin:0; padding:0; box-sizing:border-box }`, transparent `body`, `user-select: none` (inputs selectable), the themed `::-webkit-scrollbar` rules, and `<option>` colours. Build everything from `var(--ui-*)`.
- Capability detector: `<script src="https://cfx-nui-whip_core/html/js/caps.js"></script>` in `<head>` before your scripts.
- Test tools: `<script src="https://cfx-nui-whip_core/html/js/page-tools.js"></script>` in `<head>`: your page becomes readable/pressable by `ReadScreen`/`PressScreen` and its errors go to `GetErrorLog`. Needs the satellite helper loaded client-side (it registers NUI callbacks `whipProbe`, `whipErrorTap` and handles message `action = 'whipProbe'`: don't reuse those names). Keyboard-only menus: mark rows `data-probe-press` and handle click.
- Pad pictures: `<img src="https://cfx-nui-whip_core/html/img/pad/a.svg">` (names above). Swap hints on `{ action = 'padDevice', pad }` from `Whip.padScreen`. Note (whip_autos): cross-origin cfx-nui images taint a canvas, so don't draw them into WebGL/canvas.
- Item pictures/vehicle images are under `html/img/items/*.webp|png`, `html/img/vehicles/*.png` (served).
- CSS age: WHIP's own CSS stays 2022-safe (Chromium 103: no `:has()`, nesting, `color-mix()`, container queries, `@layer` by default). Use newer features only behind `caps-*` classes or `@supports` for features 103 lacks entirely.
- Theme: your page does not receive the active skin automatically; base.css gives you the stock tokens.

### WHIP's 3D map inside your own page (verified 2026-11-17 in whip_phone)

- Data: `<script src="https://cfx-nui-whip_media_map/map/whip-map3d.js">` sets `window.WHIP_MAP3D` (about 2 MB). Renderer:
  `import('https://cfx-nui-whip_core/html/js/map3d/map3d.js')` exports `WhipMap3D` and `K0`. The page needs an import
  map for the bare `three` (r170 in both whip_core and whip_phone). The cross-resource module import works in game:
  FiveM serves every NUI file with `access-control-allow-origin: *` (`NUISchemeHandler.cpp`). A local test server
  must send that header too, or the import fails while the game works.
- Build once per page: `new WhipMap3D(document.createElement('canvas'), { data: window.WHIP_MAP3D, antialias: 2 })`,
  `await map.ready`, then `window.WHIP_MAP3D = null`. Per draw: `resize(W, H, dpr)` when the size changed,
  `setView({ x, y, pxPerMetre: K0 * 2 ** zoom, offsetX: 0, offsetY: 0, yaw: 0, pitch: 90 })`, `render()`, then copy
  `gl.canvas` into your own 2D canvas with `drawImage` (as `pause-map.js` does). The copy is what whip_phone's fold
  snapshot can see. When the map is hidden, `resize(1, 1, 1)` frees its buffers.
- Flat and north-up, world to screen is `sx = W/2 + (x - cx) * k`, `sy = H/2 - (y - cy) * k` with `k = K0 * 2 ** zoom`.
  Markers can be DOM over the canvas, placed with that line; no `project()` call is needed. WHIP's own zoom range is
  1.4 to 7.5.
- Don't import `pause-map.js` into another page: it pulls `pad-cursor.js`, `utils.js` and the router with side effects.

---

## Browser capabilities and test tools

FiveM's browser is moving from Chromium 103 to 144. Trust WHIP's flags, not `CSS.supports` (103 had experimental features on: `@supports selector(:has(a))` is true there; any test containing `var()` passes everywhere).

### caps.js (page)
- Classic script (not a module); sets `window.WhipCaps` and on `<html>` a class `caps-<kebab-flag>` per true flag plus `data-chrome="<ver>"`. Re-detects on DOMContentLoaded.

| Flag | True when (Chrome floor) |
|---|---|
| `chrome` | version number (0 unknown) |
| `has` | `:has()` (105) |
| `colorMix` / `relativeColor` | `color-mix()` (111) / `rgb(from var(--x) r g b / 50%)` (122) |
| `textBalance` | `text-wrap: balance`/`pretty` (114) |
| `startingStyle` | `@starting-style` + `transition-behavior: allow-discrete` (117) |
| `heightAuto` | `interpolate-size: allow-keywords` (129) |
| `anchor` | CSS anchor positioning (125) |
| `fieldSizing` | `field-sizing: content` (123) |
| `viewTransitions` | `document.startViewTransition` (111) |
| `schedulerYield` | `scheduler.yield()` (129) |
| `webgpu` | `navigator.gpu` exists (113; adapter may still fail) |
| `zoomScreenPx` | `getBoundingClientRect` in screen px inside CSS `zoom` (measured) |
| `gameView` | `CfxGameViewRenderer` / `gl.CFX_BIND_GAME_VIEW` (draw/read the game picture) |

- Helpers: `WhipCaps.transition(update)` (view transition where available; `update` always runs AFTER the call, promise has no value), `WhipCaps.yieldToBrowser()`, `WhipCaps.snapshot()`, `WhipCaps.refresh()`.
- `@supports` is safe only for what 103 lacks entirely (`text-wrap`, anchor positioning, `field-sizing`, `interpolate-size`, `@starting-style`); use classes for `:has()`, `zoomScreenPx`, `gameView`.
```css
.caps-has .panel:has(.slot.selected) { border-color: var(--ui-accent); }
```

### GetNuiCaps() — CLIENT
- A copy of whip_core's page's flags; `false, 'not_detected_yet'` before it reports. Event `whip_core:nui:capsDetected` (caps table) fires when reported/changed. `/nuicaps` prints them; `/nuicaps gameview` shows the game view for 8 s (solid blue = didn't bind).

### ReadScreen(opts?) · PressScreen(target, opts?) — CLIENT, WAITS (developer mode only, else `false, 'developer mode is off'`)
- Reach whip_core's page and any page loading `page-tools.js`.
- `ReadScreen({ text?, controls?, under?, pages? })` -> `{ view, focus, text, controls, pages }` or `false, why`; each control has `id`, label/words, `kind`, `near` (heading above), `row`, `state` (`disabled`, `on`, `selected`, `value`), `rect`. Waits up to 4 s for the page.
- `PressScreen(target, { button = 'left'|'right'|'double', text, enter, choose })`: `target` = id from the last read, or words (exact, starts-with, contains), or `{ id, label, near, kind, index, page }`. Several matches press nothing: `{ ambiguous = {...} }`. Returns `{ pressed, kind, chose, typed, covered }`. Re-read after a press (ids change).
```lua
exports.whip_core:PressScreen({ label = 'Change', near = 'Who can open it' })
exports.whip_core:PressScreen('Weather', { choose = 'Rain' })
```

### TakeScreenshot(opts?) — CLIENT, WAITS (≤15 s) · RequestScreenshot(source, opts?) — SERVER, WAITS (≤30 s)
- Replaces screenshot-basic (cost nothing until asked). The game picture incl. what it draws (DUI screens, 3D prompts); `ui = true` adds whip_core's screens/HUD (not other resources' pages).
- opts: `format` `'jpg'` (default) | `'png'` | `'webp'`; `quality` 0–1 (0.92); `width`/`height` (one keeps aspect); `ui`; `frames` 2–24 + `every` 33–1000 ms (a burst grid, 640 wide each, no ui); `upload = { url, field }` (client only: post to a helper on this PC; returns the reply text).
- Returns `dataUrl` or `false, why`. A game can fake its picture: tools only, not anti-cheat.

### GetErrorLog(opts?) — BOTH
- Last 200 errors on this side: threads, handlers, NUI callbacks, commands, statebag handlers of whip_core and every satellite (unless fxmanifest has `whip_error_tap 'no'`), whip_core's caught errors, red `^1` warnings, and (client) pages with page-tools. Repeats counted; an export's error goes to its caller.
- opts `{ since?, max? }`. Returns `{ entries = { { seq, at, side, resource, kind = 'error'|'warning'|'page', text, count } }, last, side }`.

### MeasureFrames(opts?) — CLIENT, WAITS
- `seconds` 1–30 (default 5). Returns `{ seconds, frames, fps, fpsWorst1, medianMs, worstMs, over33, over50 }`.

### RevivePlayer(source, reason?) — SERVER
- Revive a downed player where they lie (full health, no armour), as `/w` Restore. `reason` logged after `revive:` (default caller name). Returns `true`, or `false, 'Player not loaded' | 'not down'`.

---

## DUI screens in the world

A DUI is a page from your resource drawn by its OWN browser into a texture the game can draw (over a head, on a wall, the ground). WHIP draws prompts, `/me` bubbles, NPC conversations, garage bays and Director marks this way (internal `DuiPage` + `WorldQuad`, not exported). Each DUI keeps rendering whether or not anything draws it.

Rules (WHIP's own follow them):
1. One browser per system, not per thing: lay the page out as an atlas of cells (thirty bays = thirty quads from one texture).
2. A change is a message (or a UV swap), never a new browser; send only when a cell's content changes, never per frame.
3. Made on first use, given back when idle (create on first draw, destroy a while after the last).
4. A still page: animate only while something is happening.
- `CreateDui` throws for a page wider than the game allows: 8192 px on GTA V Enhanced ("Invalid Width [1, 8192]"). Pack cells into more rows, not one strip. Wrap `CreateDui` in `pcall`.
- Queue messages until `IsDuiAvailable` (WHIP waits up to 10 s, then treats it as up); a page made mid-game can miss its first message, so resend setup once or twice.
- Clean screen hides WHIP's world quads (`CleanScreen.world`); listen to `whip_core:ui:cleanScreen` (`{ on, world }`) and stop drawing yours when `world` is true. `TakeScreenshot` includes DUI draws.

Pattern (condensed from the docs):
```lua
local PAGE = ('nui://%s/html/signs.html'):format(GetCurrentResourceName())
local TXD, TEX, IDLE_MS = 'mysigns', 'signs', 60000
local dui, up, waiting, painted, lastUsed = nil, false, {}, {}, 0
local function release() if dui then DestroyDui(dui) end dui, up, waiting, painted = nil, false, {}, {} end
local function checkIdle()
    if not dui then return end
    local left = lastUsed + IDLE_MS - GetGameTimer()
    if left > 0 then SetTimeout(left, checkIdle) else release() end
end
local function ensure()
    lastUsed = GetGameTimer()
    if dui then return end
    dui = CreateDui(PAGE, 1024, 1024)
    CreateRuntimeTextureFromDuiHandle(CreateRuntimeTxd(TXD), TEX, GetDuiHandle(dui))
    local mine = dui
    CreateThread(function()
        while dui == mine and not IsDuiAvailable(mine) do Wait(50) end
        if dui ~= mine then return end
        up = true
        for _, m in ipairs(waiting) do SendDuiMessage(dui, json.encode(m)) end
        waiting = {}
    end)
    SetTimeout(IDLE_MS, checkIdle)
end
-- paint(cell, text): ensure(); skip if painted[cell] == text; send or queue { cell, text }
-- drawSign(cell, x,y,z): ensure(); if up: SetDrawOrigin; DrawSpriteUv(TXD, TEX, 0,0, .1,.1, col/4,row/4,(col+1)/4,(row+1)/4, 0, 255,255,255,255); ClearDrawOrigin()
```
Page: `window.addEventListener('message', e => { const d = typeof e.data === 'string' ? JSON.parse(e.data) : e.data; ... })` and paint only the named cell. Load `fonts.css` in the DUI page too (a DUI is its own document).

---

## Client events emitted by these systems
All local client events (`WhipEmit` = TriggerEvent on this client):
- `whip_core:ui:stateChanged` `{ open }` — IsAnyScreenOpen changed (polled 150 ms).
- `whip_core:ui:cleanScreen` `{ on, world }`.
- `whip_core:pad:deviceChanged` `{ pad }`.
- `whip_core:keyboard:opened` `{ id, owner }` / `whip_core:keyboard:closed` `{ id }`.
- `whip_core:nui:capsDetected` (caps table).
- `whip_core:ask:cancelled` `{ token }`.
- `whip_core:hands:blocked` `{ label, only }` / `whip_core:hands:unblocked` `{}`.
- `whip_core:hotbar:slotUsed` `{ slot }`.
- Net events (internal, from server): `whip_core:client:notify`, `:playerText`, `:objective`, `:serverSkillCheck`, `:serverSkillCheckCancel`, `:serverProgress`, `:serverProgressCancel`, `:serverAsk`, `:serverAskCancel`, `:applyTheme`, `:camseqChanged`, `:handsBlocks`, `:freeHands`, `:heldPropAttach`, `:heldPropDelete`.

## Config keys
- `Config.SkillCheckHoldMs = 196`, `Config.SkillCheckMouseSpeed = 1.0`, `Config.SkillCheckDifficulty = { easy, medium, hard }`, `Config.LockpickGame = 'ring'`.
- `Config.Controller = { RadialHoldMs = 500, SprintDoubleClickMs = 300, SprintOnA = false, VehicleControls = true, VehicleControlsMs = 5000, Layout = {...} }` (a slot set to `false` is open for a resource's action).
- `Config.Keyboard = { Languages = { 'en' }, Default = 'en' }` (packs in `html/keyboard/`; codes `^%l%l%l?$`; players pick in Settings -> Server -> Controller).
- `Config.DrivingCamera = { Enabled, Default, Shake, Style }`. `Config.Experimental.cameraCreator = false`.
- `Config.Theme = nil`. `Config.PlaceItemRange = 10.5`. `Config.WeaponGuard`. `Config.CameraHidesDui = false`.

---

## Gotchas
1. Every blocking export waits: never call from a prompt `onSelect` that must not wait, a `canInteract`, or a frame loop. Use a command or `CreateThread`.
2. Always read the second return value: `false, 'busy'` (something else is up) is not the player saying no. Confirm's No and Escape are both `'cancelled'`.
3. Call waiting exports through `Whip.core` / `Whip.call`, or a whip_core restart strands your coroutine (and any lock/flag it holds).
4. Client Progress/SkillCheck/Input/PlaceObject results are claims. Rewards go behind the server `Progress(source, opts)`, server `SkillCheck(source, ...)`, or a declared timed use; validate PlaceObject coords server-side.
5. Server Progress/SkillCheck from a `SecureCallback` breaks: the client Callback stops listening at 10 s while the server keeps going (the player sees failure, the server commits). Use a `SecureEvent`.
6. A client bar's `prop` only appears if `model` is a STRING the server has vouched for (an emote prop, or a model a server `Progress` used since start); otherwise the server silently refuses ('That prop cannot be held'). Offsets are limited to ±2 m, rotations ±360.
7. `SetScreenOpen` doesn't touch focus and `Whip.padScreen` doesn't call `SetScreenOpen`: do both, and undo both on every close path (Escape, death, resource stop, a server-forced close).
8. Your own `SetScreenOpen` screen blocks OTHER resources' dialogs/bars ('busy'), not yours. A WHIP dialog over your screen drops focus when it closes: re-`SetNuiFocus(true, true)`.
9. Key mappings fire under NUI and through disabled controls: gate every world-acting command on `IsGameInputFree()`.
10. `BlockControls { mode = true }` makes `IsGameInputFree()` false for everyone (including your own hotkeys and WHIP's E prompts) until you unblock: always `UnblockControls` when the mode ends.
11. `HideText` only hides your own text; a newer `ShowText` from another resource replaces yours silently. Text shown during a bar appears after it.
12. `RegisterPadAction` with a slot WHIP's default layout already uses lands on NO button (one F8 line). Use `lb_y` or `lb_dpad_*`, or let players place it, and always read `GetPadActionButton` before drawing a hint.
13. FiveM pad key bindings never fire; `IsControlJustPressed` stops working under `SetNuiFocus` (use the Disabled readers with keep-input). Never read LB (205) as your button.
14. `OpenKeyboard` only on a pad; a second call closes the first (which returns `nil`). It takes the pad from any `padScreen` until closed.
15. Camera exports wait by default. `PlayCameraPath { loop = true }` without `async` never returns. `PlayCamera` with `exitKey = false`, `canLook = false`, `canMove = false` returns at once but stays up until `StopCamera`.
16. `PlayCameraSequence('name')` fetches over a callback the first time: call from a thread; unknown names fail with `false, 'There is no camera sequence called X'`.
17. Another resource's (or whip_core's own, e.g. character screen) camera makes yours `'busy'`. `StopCamera` only stops yours.
18. `SetActiveTheme`/`SetScreenArea`/`RegisterPadAction` registrations die with whip_core: register inside `Whip.register` so they come back after `restart whip_core`.
19. A theme applies to whip_core's page only. Your page must link `base.css`/`fonts.css` itself and won't follow a skin automatically.
20. Don't trust `CSS.supports` or `@supports` with `var()` in FiveM's browser; use `WhipCaps` flags / `caps-*` classes. Keep base CSS 2022-safe.
21. DUI: one browser per system, an atlas under 8192 px wide, messages only on change, destroy when idle. A browser per sign, or a message per frame, costs every player.
22. `IsAnyScreenOpen` excludes a bare progress bar; `IsGameInputFree` includes it. Pick the right one (HUD hiding vs hotkeys).
23. `ShowPlayerText`/`ShowText` strip colour codes and cap at 200 chars; `NotifyPlayer` caps at 300 chars and clamps duration 500–30000 ms (client `Notify` doesn't clamp).
24. Client `Input` `select` options must be `{ value, label }` tables (plain strings render blank); the server-side Ask form accepts plain strings.
25. `RegisterClientHook` handlers should return a delay (ms, ≤1000) rather than `Wait`; one that waits past 1 s is abandoned.

## Docs vs code
1. Docs list `Input` field types text/number/select/checkbox/textarea; code also accepts `password`, `email`, `tel`, `url`, `date`, `time`, `color`, `range` (`whip_core/html/js/ui.js:26`, `types/classes.lua:528`).
2. Docs' client `SkillCheck` forms omit `{ level = { pieces, parts, widest, narrowest, msPerPart, holdMs?, mouseSpeed? } }`, which code accepts on client and server (`whip_core/shared/skillcheck.lua:85-97`).
3. Docs say `prop.model` for a client bar; code ignores a non-string model and the server only spawns vouched models (`whip_core/client/ui.lua:282`, `whip_core/server/held_props.lua:232,281`).
4. Docs' `BlockControls` group list omits the `radioControls` switch, which code accepts by name (`whip_core/client/controls.lua:42`).
5. Docs give `PlayCamera` a fixed filter list; code applies any timecycle name unchecked (`whip_core/client/camera.lua:55-66`).
6. `PlayCamera`'s `exitKey` reads only control 200 (Esc), not B; sequences/orbits read 200 and 202 (`whip_core/client/camera.lua:180`, `:457`).
7. `OrbitCamera` `exitKey` has no default in docs; code defaults it off (`whip_core/client/camera.lua:482`).
8. Docs: PlaceObject `reach` "default an item's"; code default is `Config.PlaceItemRange` (10.5) clamped to 1–10, so 10 (`whip_core/client/placing.lua:226`, `config.lua:1381`).
9. Docs: spring `rate` "3 gentle to 8 brisk"; code accepts 0.5–30 (`whip_core/shared/cam_sequence.lua:187`).
10. Docs: server SkillCheck `minMs` default "parts × fill time"; code floors it at 300 ms and clamps a caller `timeoutMs` to 1000–60000 (games 120000) (`whip_core/server/skillcheck.lua:202-204,316-324`).
11. Docs' server Progress reasons omit `'Player not loaded'` and the server timeout of `duration + 15000` ms (`whip_core/server/timed_action.lua:26,151`).
12. `RegisterAskChannel` name: docs say letters/digits/`_`/`-`; code also caps it at 32 chars (`whip_core/server/ask.lua:66`).
13. `docs/nui-theming.md:98` and `base.css` header say the browser is Chromium 103 (no `:has()`, `color-mix()`), while the caps guide and `caps.js` say it's moving to 144 with detection: treat 103 as the floor and gate newer CSS on `WhipCaps`.
