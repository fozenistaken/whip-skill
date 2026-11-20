# Contributing to WHIP (pull requests)

## Contents

- The official rules
- What the maintainer changed or asked for (reviews of 2026-11-17/18)
- Checklist before opening a PR

## The official rules

From [WHIPFX/.github CONTRIBUTING.md](https://github.com/WHIPFX/.github/blob/main/CONTRIBUTING.md):

1. Fork, branch from `main`, one change per PR. Large or new features: open an issue first.
2. Test on a server installed with WHIP's txAdmin recipe.
3. Lua adds no new LuaLS warnings; `whip_core/types/` describes the API.
4. **Every commit** is a conventional commit (`fix:`, `feat:`, `chore:`, `docs:`), follow-up commits included.
5. The PR says what it changes and how it was tested.
6. PRs are rebased or squashed on merge: keep the branch current by **rebasing** on `main`, never by merging `main` in.

## What the maintainer changed or asked for

WLVF reviewed 25 PRs by fozenistaken (whip_core #62–#96, whip_chat #13, oxmysql #4, txAdmin-recipe #33). He
approved most as they were. Where he commented or pushed his own commit, the lesson is below, with the PR.

**Comments describe the code as it is. No history.** His most repeated fix.
- [#79](https://github.com/WHIPFX/whip_core/pull/79), changes requested: "There's some small things noted here that
  occur from AI." On a comment explaining what used to go wrong: "Comment contains 'implementation rot'. Please keep
  them concise and explanatory. We don't need to know about the code's history."
- [#75](https://github.com/WHIPFX/whip_core/pull/75), [#77](https://github.com/WHIPFX/whip_core/pull/77) and
  [#81](https://github.com/WHIPFX/whip_core/pull/81): he deleted or cut comments saying what the code "used to" do,
  "no longer" does, or what it "replaced". The PR description holds the before and after; the code comment holds
  only what the code does now.

**FiveM event handlers are already async.**
- [#79](https://github.com/WHIPFX/whip_core/pull/79): "There's no need for a CreateThread here, event handlers are
  already async." `Wait` works directly inside `AddEventHandler` / `RegisterNetEvent` handlers.

**Use whip_core's own hooks inside whip_core.**
- [#77](https://github.com/WHIPFX/whip_core/pull/77): `AddEventHandler('whip_core:player:loaded', ...)` with a
  `phantom` check became `Character.onLife('loaded', fn)`. Before listening to WHIP's public event from inside
  whip_core, look for the internal hook the event comes from.

**A refusal says the real reason.**
- [#77](https://github.com/WHIPFX/whip_core/pull/77): a dev command refused only "needs whip.devtools". He made it
  say `DevTools.OFF_REASON` when the player holds the permission but developer mode is off
  (`DevTools.isEligible(source)`).

**Don't add what the framework already has.**
- [#76](https://github.com/WHIPFX/whip_core/pull/76), not merged: "the commands that you're adding aside from /kill
  already exist in the framework. Your AI agent even pointed out /whip_revive." He liked the new Player Manager
  buttons. Before adding a command, export or alias, search whip_core for the same job (`devCommand(`,
  `RegisterCommand(`, `exports(`); convenience aliases for existing commands are refused.

**Widening one range: check the ranges that go with it.**
- [#88](https://github.com/WHIPFX/whip_core/pull/88): an option's own reach widened the prompt (`promptReach`) but
  not the distance the point is seen from, so it could be in reach and not shown. He set
  `out.seeFrom = math.max(seeFrom or Config.InteractVisibleRange or 5.0, far)` (`server/runtime_points.lua`).

**UI: Enter belongs to the form; `background` resets the image.**
- [#81](https://github.com/WHIPFX/whip_core/pull/81): Enter on a select opened the list, so a dialog whose first
  field is a select no longer submitted on Enter. Space, F4 and Alt+Down open it; Enter stays the form's
  (`html/js/ui-controls.js`).
- Same PR: a `background:` shorthand on the Bank picker wiped its `background-image` chevron. Set
  `background-color` when only the colour changes.

**A new export comes with its docs.**
- [#90](https://github.com/WHIPFX/whip_core/pull/90): he added `docs.html` export cards for `IsNearAtm` and
  `GetNearestAtm` (`<div class="export-card" id="..." data-search="...">`, side badge, param table, returns).
- [#87](https://github.com/WHIPFX/whip_core/pull/87): a new export that waits goes in the WAITS lists. Run
  `node dev/waits.js --write` (it writes `docs.html`'s WAITS and `lib/satellite.lua`'s from the `---@async` marks in
  `types/`); `--check` verifies them.
- [#86](https://github.com/WHIPFX/whip_core/pull/86) + [#90](https://github.com/WHIPFX/whip_core/pull/90): when one PR
  changes a fact another PR's docs or comments state ("there's no list of machines"), update both.

## WHIP's house style (measured 2026-11-18)

From the maintainers' own commits (WLVF `a5d94c0`, Whippy `70bec4a`, `5f59a68`) set against our merged ones:

- **Comments are welcome, narration is not.** WHIP's code is comment-heavy: 15–35% of added Lua/JS lines, blocks up
  to 25 lines, `-- ====` section banners, `---@param` / `---@return` with what each value means. Ours sat in the same
  range and passed. What got cut was content: what used to break, what a line replaced.
- **What a WHIP comment says:** what this does and why it must (the constraint), with the file that explains the rest
  (`(client/inventory.lua)`, `(tools/ov_move.lua)`). Plain English, present tense.
- **Say an aside once, where the thing is defined.** #80 repeated "(a bank card in a wallet:
  shared/inventory_shape.lua)" on five functions. Explain it at the definition; at each use the name is enough.
- **A config comment is not a manual.** What the setting does, its default, where it also shows in /whip. #91's
  six-line `GtaStores` comment told the whole on/off story; that belongs in `docs.html`.

**PR descriptions.** The maintainers write 100–1,300 characters; ours ran 1,000–5,200 and said things twice
(#86: a Before/Now, then the same in prose). Use WLVF's shape ([#71](https://github.com/WHIPFX/whip_core/pull/71)):
1. The problem, with the evidence (a repro, a version, what was seen).
2. One line per changed file: what changed in it.
3. "Behaviour is otherwise unchanged" when true; what stays the same if anyone could worry.
4. "Checked: ..." with what was really run, and plainly what was not ("Not run in game").
5. A UI change: before and after screenshots. Nothing said twice.

**Own every line.** Reviewers of AI-made PRs (Godot, tldraw, 2026) object to PRs that look generated from one prompt,
read confidently but don't work, or that the sender can't explain. If research finds the framework already does it
(#76: `/whip_revive`), drop that part instead of noting it and adding it anyway.

## Checklist before opening a PR

`scripts/pr_check.py` checks 1–4, 7 and 8 from the branch's diff and commits. Tested 2026-11-18 on the merged PRs
at our last commit before the maintainer's changes: it flags #75, #76, #77, #79, #81 (the comment), #87 and #90, and
nothing on #85, #92 and #96. It can't see #88's missing `seeFrom`, #81's Enter key or the chevron, or a refusal's
wording: check those by hand.

1. Search whip_core for an existing command, export or option doing the same job.
2. Comments: present tense, what the code does; no "used to", "no longer", "now", "replaced". The before and after
   go in the PR description.
3. No `CreateThread` just to `Wait` inside an event handler.
4. Inside whip_core, use its internal hooks (`Character.onLife`, ...) rather than its public events.
5. Every refusal says the real reason.
6. A changed range, size or key: check the ranges, styles and keys that pair with it.
7. New export: `docs.html` card, `types/` stub, and `node dev/waits.js --write` if it can wait.
8. Every commit message is a conventional commit; rebase on `main`, never merge it in.
9. UI change: before and after screenshots in the description.
10. Description in WLVF's shape, under ~1,300 characters, nothing said twice, "Checked:" honest.
11. Each aside explained once, at its definition.
