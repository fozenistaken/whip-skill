# Setting up a WHIP server: the field-tested procedure

How to set up a WHIP server for a user, end to end, by both routes (txAdmin recipe and manual), on Legacy or
Enhanced. Learned from real installs on Windows (FXServer 38435, txAdmin 8.1.2, MariaDB 11.4, November 2026);
every error below was met and fixed. Background facts (recipe contents, the setup report's checks, packs) are in
`install-packs-testing.md`; this file is the procedure and the troubleshooting.

## Contents
- The flow: scan, ask, set up
- Step 1: scan the machine
- Step 2: ask once
- Step 3a: the txAdmin route
- Step 3b: the manual route (no txAdmin)
- Step 3c: manual files, run by txAdmin (when the recipe times out)
- The database
- Enhanced instead of Legacy
- Two WHIP servers on one machine
- First start: what the console says and what to do
- Troubleshooting table
- What the user does, what you do

## The flow: scan, ask, set up

Always in this order. Never start downloading before you have asked, and never ask before you have
scanned: the questions depend on what is there.

1. **Scan.** Run `python -I scripts/whip_host.py scan <folders where servers live>`. It reports:
   - the OS and free disk
   - the ports in use (30120, 40120, 3306/3307, the voice ports)
   - every MySQL/MariaDB binary, with its version and whether WHIP accepts it
   - existing FXServer artifacts, WHIP installs and txAdmin data folders
   - the current recommended FXServer build
   - whether GitHub is reachable
2. **Ask once.** One question set (see Step 2), with a recommended option for each, built from the scan.
3. **Set up everything you can yourself:**
   - artifact
   - resources
   - database
   - `server.cfg`
   - start script
   - port separation from other servers
   Leave the user only what only they can do (see the last section).
4. **Verify.** Run `python -I scripts/whip_host.py check <server-data>`, then read the first start's console
   and the WHIP setup report with the user.

## Step 1: scan the machine

`whip_host.py scan` is read-only. Read its output for:

| Look at | Why |
|---|---|
| Database binaries and versions | MariaDB 10.2.3+ or MySQL 8.0.16+. Older versions ignore the CHECK that stops bank balances going negative. A running server on 3306/3307 can be reused with a new database. |
| Ports in use | A busy 30120 or 40120 means another FiveM server or txAdmin: pick other ports. A busy 7880-7893 means another whip_voice: move the voice ports. |
| Existing artifacts | Reuse one if its build is ≥ 38435 (Legacy). Otherwise download the recommended build. |
| Existing WHIP installs and txData | Do not overwrite them. Choose a new folder. |
| GitHub reachability | Both routes download about 830 MB from github.com, codeload.github.com and objects/CDN. |

## Step 2: ask once

Use one multiple-choice question set, recommended option first:
- **Route:**
  - txAdmin recipe (the official way)
  - manual (no txAdmin; scripted)
  - manual files run by txAdmin (Step 3c): txAdmin's panel without its deploy timeouts. Recommend this one
    on Windows, where the recipe's unzip steps can hit the 180 s limit.
- **Game:** Legacy (normal FiveM) or GTA V Enhanced.
- **Database:** which server the scan found (recommended: an existing MariaDB/MySQL that meets the version),
  or install one.
- **Folder:** default, a new folder beside existing servers.
- **Ports:** only when the scan found a clash.

Never ask the user for their licence key or password in chat: they type those into txAdmin or `server.cfg`
themselves.

## Step 3a: the txAdmin route

1. **Artifact.**
   - The recommended Windows build is at `https://changelogs-live.fivem.net/api/changelog/versions/win32/server` →
     `recommended_download`. Use `linux` instead of `win32` for Linux.
   - Legacy needs build 38435+. In Nov 2026, "recommended" was exactly 38435 (about 64 MB zip).
   - Extract it to `<root>/server`.
2. **Start script.** txAdmin 8 reads its data folder and port from environment variables:
   ```bat
   set TXHOST_DATA_PATH=%~dp0txData
   set TXHOST_TXA_PORT=40121      & rem only when 40120 is taken
   cd /d "%~dp0server"
   FXServer.exe
   ```
3. **The user's part.**
   1. Run the script. Open `http://localhost:<port>` and enter the PIN from the console.
   2. Link a Cfx.re account and set the txAdmin password.
   3. On the setup page choose **Remote URL Template** and paste
      `https://raw.githubusercontent.com/WHIPFX/txAdmin-recipe/main/whip-legacy.yaml` (or `whip-enhanced.yaml`).
   4. Enter the registration (licence) key, then the database host, port, user, password and name.
4. **Deploy.**
   - txAdmin deploys into `txData/<DEPLOY_ID>.base/` (for example `txData/WHIP_F950B8.base`); `server.cfg` is
     there.
   - Each `download_github` asks GitHub to build a zip on request. whip_core took about 1 min 40 s.
   - The biggest resources come as release zips (≤ 40 MiB each) so they fit txAdmin's 150 s limit per download.
5. **"Configure server.cfg".** Change nothing there. Save and start.

## Step 3b: the manual route (no txAdmin)

`scripts/install_whip.py` runs WHIP's own recipe without txAdmin. It fetches the live YAML and performs every
task in order: GitHub zips at the tags, release zips, oxmysql, `server.cfg`.

```bash
python -I scripts/install_whip.py <root>/server-data --game legacy --port 30120 \
       --db "mysql://user:pass@127.0.0.1:3306/whip" --create-db
```

What it does that txAdmin would otherwise do:

| txAdmin does | Without txAdmin |
|---|---|
| Applies `$onesync: on` outside `server.cfg` | The installer writes `set onesync on` into `server.cfg`. Without it OneSync is off, and WHIP requires it |
| `connect_database` creates the database | `--create-db` creates it with the mysql/mariadb client. oxmysql never creates a database (`ER_BAD_DB_ERROR` 1049 "Unknown database") |
| Fills `{{svLicense}}`, endpoints, connection string, admin principal | `--port`, `--maxclients`, `--db` fill them. The licence stays `CHANGE_ME` for the user to paste. The first admin types `/w` and copies the `add_ace` line the console prints |
| Starts FXServer under txAdmin | Start script: `cd server-data` then `..\server\FXServer.exe +exec server.cfg`. Stop it with `quit` in that console |

Then copy or extract the artifact to `<root>/server`, run `whip_host.py check <root>/server-data`, and hand over.

Notes:
- `download_github` goes through `codeload.github.com/<repo>/zip/refs/tags/<tag>`, so it makes no GitHub API calls
  and is not subject to the 60/hour limit. The zip's top folder is stripped. Release zips have no top folder.
- Python's TLS sometimes fails on Windows with `CERTIFICATE_VERIFY_FAILED ... unable to get issuer certificate`.
  It is intermittent. The installer then retries through `curl`, which uses the Windows certificate store.
- Category folders such as `[ox]` and `[assets]` are kept. Resource folders are replaced on re-run.

## Step 3c: manual files, run by txAdmin (when the recipe times out)

txAdmin gives every recipe task 180 s, including `unzip`. On Windows, unzipping a media-pack part (about 3,500
small files; antivirus scans each new file) can take longer. The deploy then stops with:
```
Running [task20:unzip]... ❌  Task Failed: timed out after 180s.   (src ./tmp/whip_media_clothing_male-1.zip)
```
A retry starts the whole deploy again and can fail the same way. Instead, install the files yourself and let
txAdmin run them:

1. `python -I scripts/install_whip.py <root>/server-data --for-txadmin --port 30120 --db "mysql://…/whip" --create-db`
   - It writes `server.cfg` without `set onesync`, because txAdmin starts FXServer with OneSync from its own
     settings.
   - It creates the database.
   - When another install of the same recipe is already on this machine, copying its `resources/` is faster
     than downloading again.
2. In txAdmin: on the failed deploy screen, choose **Cancel and Return to Setup**. On the setup page choose
   **Existing Server Data**, give the `server-data` folder, then select its `server.cfg`.
3. txAdmin → **Settings → FXServer**: OneSync **On**.
4. The user pastes their key into `sv_licenseKey` (in the file, or in txAdmin's CFG Editor), then starts.
5. The admin line: txAdmin's recipe writes `{{addPrincipalsMaster}}`, but this route does not. The first admin
   types `/w`, and the console prints the `add_ace` line to add.

The aborted deploy leaves `txData/<DEPLOY_ID>.base/` half filled. Ask the user before deleting it.

## The database

- **Version:** MariaDB 10.2.3+ or MySQL 8.0.16+.
- **What WHIP needs:** an empty database. whip_core creates every table on first start and migrates on later
  starts. There is no SQL to import.
- **Creating it:** do it yourself when the user asks you to set the server up. Use the login they gave or the one in
  `server.cfg`'s `mysql_connection_string`, with the password passed in `MYSQL_PWD`, never echoed:
  ```sql
  CREATE DATABASE IF NOT EXISTS whip CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
  ```
  A separate login (optional; root works for a local sandbox):
  ```sql
  CREATE USER 'whip'@'localhost' IDENTIFIED VIA mysql_native_password USING PASSWORD('…');
  CREATE USER 'whip'@'127.0.0.1' IDENTIFIED VIA mysql_native_password USING PASSWORD('…');
  GRANT ALL PRIVILEGES ON whip.* TO 'whip'@'localhost', 'whip'@'127.0.0.1';
  ```
  - MariaDB matches a TCP connection from 127.0.0.1 to the `'user'@'localhost'` account, so that account must
    exist with the right password. Otherwise: `Access denied for user 'whip'@'localhost'` (1045).
  - Use `mysql_native_password`. txAdmin's driver cannot use some authentication plugins, and says "Your database
    does not accept the required authentication method". A blank password field for an account that has a
    password is the other common cause of a failed txAdmin database step.
- **Waiting:** whip_core waits for the database without crashing. It prints `[whip_core:db] waited 10 s for the
  database: oxmysql cannot connect…`, and oxmysql retries every 30 s. Fix the database or the string and it
  carries on; no restart is needed.

## Enhanced instead of Legacy

| | Legacy | Enhanced |
|---|---|---|
| Recipe | `whip-legacy.yaml` | `whip-enhanced.yaml` |
| Server | FXServer artifact 38435+ | cfx-server (Enhanced build) |
| `server.cfg` | `sv_enforceGameBuild 3889` (the setup report accepts 3407+) | `setr whip_platform enhanced` (must be `setr`); `set sv_resourceFileDownloadTimeout 600000`; the `increase_pool_size` block; `stop chat` |
| Mumble | `set mumble_disableServer true` | — |
| Asset folders | `stream/` | `stream_enhanced/` (the same resources carry both) |

`install_whip.py --game enhanced` writes the Enhanced `server.cfg` from its recipe. The setup report flags a
platform mismatch: a server whose version string looks like the other platform. More is in
`install-packs-testing.md` → "Legacy vs Enhanced".

## Two WHIP servers on one machine

They can share the database server (one database each). Everything else needs its own value:

| What | First server | Second server |
|---|---|---|
| Game port | 30120 | `endpoint_add_tcp/udp "0.0.0.0:30122"` (manual), or the txAdmin deploy's port field |
| txAdmin web | 40120 | `TXHOST_TXA_PORT=40121` (or no txAdmin) |
| whip_voice (its own LiveKit) | defaults 7880-7893 | in `server.cfg`, before `ensure whip_voice`: `set whip_voice_udp "7982-7993"`, `set whip_voice_tcp "7981"`, `set whip_voice_api "http://127.0.0.1:7980"`, `set whip_voicebot_url "http://127.0.0.1:7999"` |

The voice ports clash even on a purely local setup: each whip_voice starts its own voice server on this
machine. Without separate ports the second one fails with "something already answers on 127.0.0.1:7880".

## First start: what the console says and what to do

1. oxmysql connects. Errors are in the troubleshooting table.
2. whip_core creates its tables (first start) and starts.
3. About 5 s after the last resource starts, the **WHIP setup** report prints. Fix every `FIX` line;
   `Framework loaded successfully!` follows when nothing is left. `whipsetup` reprints it, and `whipsupport`
   prints a block to paste for help.
4. The user joins (Steam must be linked to their Cfx.re account), makes a character, then types `/w`.
   - The console prints the `add_ace … whip.devtools allow` line. Add it to `server.cfg`, or it is already there
     through txAdmin's `group.admin`.
   - Turn developer mode on in `/w`.

## Troubleshooting table

| Symptom | Cause | Fix |
|---|---|---|
| Fatal dialog "Could not authenticate server license key. Invalid key format specified." | `sv_licenseKey` is still a placeholder | The user pastes their key from portal.cfx.re |
| txAdmin "Database connection failed: Your database does not accept the required authentication method" | Blank password for an account that has one, or an auth plugin the driver lacks | Enter the password; or create a `mysql_native_password` login |
| `ER_ACCESS_DENIED_ERROR` 1045 `Access denied for user 'x'@'localhost'` | No such account for localhost, or wrong password | Create `'x'@'localhost'` (and `@'127.0.0.1'`), or use the right login |
| `ER_BAD_DB_ERROR` 1049 `Unknown database` | Manual route: nobody created it | `CREATE DATABASE … utf8mb4_unicode_ci` (`install_whip.py --create-db`) |
| `[whip_core:db] waited 10 s for the database` | Any database error above | Read oxmysql's lines above it; no restart needed after the fix |
| Setup report: OneSync FIX | Manual route without `set onesync on` | Add it |
| "something already answers on 127.0.0.1:7880" | A second whip_voice on the same machine | Move this server's voice ports |
| `CERTIFICATE_VERIFY_FAILED` in the installer | Python TLS on Windows (intermittent) | Rerun; the installer falls back to curl |
| A txAdmin download times out | A GitHub zip built too slowly (150 s limit) | Retry the deploy; the big resources are already release zips |
| `Running [taskN:unzip]... ❌ Task Failed: timed out after 180s` | A media-pack part with thousands of files unzips too slowly on Windows (antivirus) | Step 3c: install with `install_whip.py --for-txadmin`, then use txAdmin's "Existing Server Data" |

## What the user does, what you do

| You (agent) | The user |
|---|---|
| Scan, ask, download and extract the artifact, install resources (manual route), create the database, write `server.cfg` and start scripts, separate ports, run `whip_host.py check`, read logs | Type the licence key and database passwords (txAdmin form or `server.cfg`); txAdmin's PIN and Cfx.re login; start and stop the server unless they ask you to; join the game and type `/w` |
