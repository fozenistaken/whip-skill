# AGENTS.md: WHIP (FiveM framework)

Instructions for coding agents other than Claude Code (Codex, Cursor, Gemini CLI, …) working on FiveM
resources for WHIP (https://whipfx.net/docs/, https://github.com/WHIPFX).

**Read `SKILL.md` in this folder first.** It holds the rules, the workflows and the map of `references/`.
This file only adds setup for agents that do not load skills by themselves.

## Using it from another project

Agents read `AGENTS.md` from the project they work in, not from this repository. Clone this repository once,
for example to `~/whip-skill`, then add these lines to your FiveM project's own `AGENTS.md`:

```
For anything on the WHIP framework (whip_core, exports.whip_core, Whip.register, SecureEvent, whip_*):
read ~/whip-skill/SKILL.md and follow it. Look up every WHIP export, event and option key in
~/whip-skill/references/ before using it, and run
python -I ~/whip-skill/scripts/whip_scan.py <resource> on the result.
```

## The three rules that matter most

1. WHIP is newer than your training data. Every WHIP name must come from `references/`; a name not in
   `references/export-index.md` (exports) or `references/events-and-data.md` (events) does not exist.
2. Run `scripts/whip_scan.py` on what you write. It reports invented exports and events (W070, W071), option
   keys a call does not read (W072), and breaches of WHIP's rules.
3. When porting from QBCore, Qbox, ESX or ox, rewrite with WHIP's features (`references/porting-playbooks.md`).
   A call-for-call translation is not a port.
