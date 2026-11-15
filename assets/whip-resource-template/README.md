# myres (WHIP starter)

A minimal resource that follows the WHIP way: declarations in `Whip.register`, a `SecureEvent` that accepts
nothing from the client and checks distance, a charge with a refund on failure, a timed use the server
times, a prompt with `AddAction`, a `/whip` settings page and a dev command.

1. Copy this folder into your resources and rename `myres` everywhere (folder, item key, event, command).
2. `server.cfg`, below WHIP's lines: `ensure myres`.
3. Put a picture at `html/img/items/myres_snack.webp` (optional).
4. Open the folder in VS Code with the Lua extension (sumneko): `.luarc.json` finds `../whip_core/types`.
5. In game: `/whip` -> Settings -> My Resource to move the counter or change the price.

Check: `python <skill>/scripts/whip_scan.py <this folder>` should report nothing above LOW.
