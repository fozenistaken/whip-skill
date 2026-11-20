# Money, Payments and Banks

Covers cash (banknote items), charging and paying players (receipts, refunds), money holds for metered services, bank accounts (kinds, roles, permissions, transactions, freezing, closing), ATMs, the own-character transfer block, bank events, and the `/whip` Banks admin page. Built from doc anchors `guide-bank`, `guide-payments`, `bank`, `guide-banks`, verified against `whip_core/server/{money,money_holds,bank,bank_admin,atm,cash_marks,prices,sanitize}.lua`, `server/items/{cash,wallet}.lua`, `client/atm.lua`, `config.lua`, `types/{server,classes,events}.lua`.

## Contents
- Conventions
- Config keys
- Cash: the banknote item
- ChargePlayer
- RefundPlayer and receipts
- PayPlayer
- Money holds (HoldMoney, SpendMoneyHold, SettleMoneyHold, GetMoneyHold)
- Accounts: kinds, numbers, roles
- Reading accounts
- A player's moves (permission-checked)
- System moves (no permission check)
- Opening, sharing, closing, freezing
- SetVehiclePrices
- Own-character transfer block
- ATMs
- Events
- Database tables
- Failure strings
- Banks admin page
- Gotchas
- Docs vs code

## Conventions

- Every bank export has "Bank" in its name. All are SERVER and all but `SetVehiclePrices`, `SpendMoneyHold` and `GetMoneyHold` WAIT (database).
- A person (`who`, `actor`, `owner`, `grantedBy`, `revokedBy`) is a server id (online) or `{ charId = n }` (online or not). A bare number is never a charId. Failures from that lookup: `'No player with that server id is online (for a character, pass { charId = n })'`, `'A character is { charId = n }'`.
- Bank amounts: whole numbers of 1 or more. A fraction, 0, a non-numeric string, NaN or infinity is refused (never rounded) with `'Amount must be a whole number of 1 or more'` (`server/sanitize.lua:120`). Numeric strings are accepted.
- Charge/Pay amounts: whole numbers of 0 or more; refusal `'Amount must be a whole number of 0 or more'` (`server/money.lua:36`).
- Exports return `false` (never `nil`) on failure so the reason survives the export boundary.

## Config keys

| Key | Default | Meaning |
|---|---|---|
| `Config.DefaultCash` | 500 | banknotes placed in a new character's pockets (pocket slot 1) |
| `Config.StartingBalance` | 1000 | paid into a character's default account when it is created (with a `'Starting balance'` ledger row) |
| `Config.DefaultAccountLabel` | `'Personal Account'` | label of default accounts and of `CreateBankAccount` without a label |
| `Config.MaxExtraAccounts` | 5 | savings + shared accounts one character may own; 0 = none. Personal and job accounts do not count; admins are not limited |
| `Config.BlockOwnCharacterTransfers` | `true` | no money between characters of the same player account (see below) |
| `Config.AtmProps` | `prop_atm_01`, `prop_atm_02`, `prop_atm_03`, `prop_fleeca_atm` | models that become ATMs (no location list) |
| `Config.AtmSearchRange` | 30.0 | m, how far ATMs are looked for |
| `Config.AtmVisibleRange` / `Config.AtmActiveRange` | 3.0 / 1.4 | m, prompt appears / usable |
| `Config.AtmBadgeOffset` | per model + `default` | `{ side, out, up, yaw }` badge placement |
| `Config.AtmMaxDigits` | 9 | max digits typed at an ATM ($999,999,999) |

## Cash: the banknote item

- Cash is ONE stackable item, key `cash` (`config.lua:174`): name `'Cash'`, `type = 'currency'`, `weight = 0.0001` (800,000 notes fill an 80 kg inventory), `stack = true`, `maxStack = 999999`, not usable, prop `prop_cash_pile_01`. The item amount is dollars. There are **no denominations**; only the inventory picture changes with the stack size: `< 100` broke, `< 1000` notes, `< 10000` fan, `< 50000` stack, `< 100000` stacks, `< 500000` tower, `>= 500000` pile.
- There is no cash column on the character. `cash` on the player sheet and `GetPlayerCash(source)` count `cash` items in the slots of the player's pocket containers (`PlayerContainers`: main pockets and the accessory strip, whose slot 2 is "Money (cash or a wallet)"). Counting is in-slot only (`server/inventory.lua:1019`): notes inside a wallet item are not counted.
- `wallet` item: not stackable, 3 slots accepting `cash` and `id_card` (`server/items/wallet.lua`); no per-slot cap.
- Internal cash methods (`WhipPlayer:addCash/removeCash`, not exports) write at once and push `whip_core:client:updateCash`. `addCash` never drops at the feet: if notes do not fit it fails (`'No room for the cash'`). `PayPlayer` falls back to dropping (see below).
- Cash moving in or out logs on the activity log (`Log.gained` / `Log.lost`) with the reason and the calling resource.
- Cash is a normal item for inventory exports (`AddItem(source, 'cash', n)` etc.), but use `PayPlayer` / `ChargePlayer` for money so it is logged and refundable.
- Cash marks (`server/cash_marks.lua`, table `cash_marks`): with `BlockOwnCharacterTransfers` on, cash left in a boot, glovebox, stash or wallet (tallied per character, by wallet uid for wallets) cannot be taken out by another character of the same player beyond what others left there, and a ground cash pile dropped by another character of the same player cannot be picked up. Refusal: `'Your other character is linked to this item'`. Tallies expire after 30 days untouched. Third-player collusion is not covered.

## ChargePlayer(source, amount, opts?) — SERVER, WAITS

Takes a payment in cash or from the bank; returns a receipt `RefundPlayer` can undo. The one way WHIP charges anyone (shops, pumps, ATMs, whip_autos use it).

| Param | Type | Default | Meaning |
|---|---|---|---|
| `source` | number | | player server id (must be loaded) |
| `amount` | number | | whole, >= 0. `0` takes nothing and still returns a receipt (method `'cash'` under auto) |
| `opts.method` | string | `'auto'` | `'cash'`, `'bank'`, or `'auto'` (cash if they carry enough of `currency`, else the bank; an item currency always resolves to cash) |
| `opts.accountId` | number | default account | bank: which account; the player's own `withdraw` role on it is checked |
| `opts.currency` | string | `'cash'` | cash: the item key that counts as money (must exist in `Config.Items`). A refund returns the very stacks taken (serials, durability, metadata kept) |
| `opts.reason` | string | `'Payment'` | bank statement message and activity log (truncated to 120) |

Returns: `receipt` or `false, err` (err is a sentence the player can read).

Receipt (`WhipReceipt`, a copy; the real record stays on the server):
| Field | Meaning |
|---|---|
| `id` | what `RefundPlayer` needs |
| `amount` | amount charged |
| `method` | `'cash'` or `'bank'` (resolved) |
| `accountId` | bank: account debited; nil for cash |
| `currency` | cash: item paid in (`'cash'` for banknotes); nil for bank |
| `refunded` | amount refunded at the time of the receipt (a snapshot; editing it changes nothing) |

Behaviour:
- Bank path = `Bank.Withdraw` on the player's own permission (ledger type `'withdraw'`, message = reason, `actorCharId` = payer). Frozen account, insufficient funds, own-other-character account and missing role all refuse.
- Inside a SecureEvent/SecureCallback (exactly one running player action) the payment is taken at once (cannot be spent twice) but WRITTEN in the same transaction as the action's next WHIP write (`CreateOwnedVehicle`, `SetVehicleData`, `SetVehicleAppearance`, ...) or the handler's end. If that write fails, nothing was taken and a later `RefundPlayer` simply lets the payment go. Outside an action (your own thread) it is written at once.
- Cash is refused while the pockets are frozen for an in-flight bank write: `'Paying — wait a moment'`.
```lua
local receipt, err = exports.whip_core:ChargePlayer(source, 500, { method = 'auto', reason = 'Car wash' })
if not receipt then return exports.whip_core:NotifyPlayer(source, err, 'error') end
if not washTheCar() then exports.whip_core:RefundPlayer(receipt) end   -- or RefundPlayer(receipt, 200)
```

Failure strings: `'Amount must be a whole number of 0 or more'`, `'Player not loaded'`, `"method must be 'cash', 'bank' or 'auto'"`, `'Unknown currency item "x"'`, `'a bank payment is in dollars — currency is for a cash payment'`, `'Not enough cash (have $20, need $500)'` (item currency: `'Not enough Gold Bar (have 3 Gold Bar, need 5 Gold Bar)'`), `'Could not take the cash'`, `'Paying — wait a moment'`, `'No such account'` (bad `accountId`), `'The bank could not be reached — try again'`, `'You have no bank account'`, auto fallbacks `'Not enough cash (have $X, need $Y), and no bank account'` / `'Not enough cash (have $X, need $Y), and the bank said: <why>'`, and the bank's own (`'No withdraw permission on this account'`, `'Account is frozen'`, `'Insufficient funds'`, `'Account not found'`, the own-character sentence).

## RefundPlayer(receipt, amount?) — SERVER, WAITS

Gives back a `ChargePlayer` payment the way it came, with no permission check.
- `receipt`: the receipt table or its `id` (only `id` is read; a forged table is useless).
- `amount`: whole >= 0; default everything not yet refunded. `0` returns `true`.
- Only the resource that charged may refund, only up to what is left, only within **30 minutes** of the charge (Systems Creator receipts, owner `system:<id>`: 70 min). Receipts are in memory: dropped when the charging resource stops and lost on a whip_core restart.
- Delivery: bank → `SystemDeposit` back to the same account (`'Refund: <reason>'`); if that fails (frozen meanwhile) it comes back as cash. Cash → pockets, dropped at their feet if full; item currency → the very stacks taken. Cash for a player who has left (or switched character) → their default account (`'Refund: <reason> (you had left)'`). Item currency has no bank fallback.
- Undeliverable: returns `false, 'The refund could not be delivered'`, prints `CRITICAL`, writes a `refund_failed` activity row; the undelivered part stays refundable.
- A held payment (not yet written) is cancelled or shrunk instead of paid back; if the write carrying it is in flight: `'That payment is still being written — try again in a moment'`.
- Returns `true` or `false, err`: `'No such payment to refund (a receipt lasts 30 minutes)'`, `'That payment was taken by <resource>'`, `'Only $X of that payment is left to refund'`, amount error.

## PayPlayer(who, amount, opts?) — SERVER, WAITS

Pays a player (wage, reward, sale). Logged on the activity log with your resource's name.

| Param | Type | Default | Meaning |
|---|---|---|---|
| `who` | number\|table | | server id (online) or `{ charId = n }` (may be offline) |
| `amount` | number | | whole, >= 0; `0` pays nothing and returns `{ method, amount = 0 }` |
| `opts.method` | string | `'auto'` | `'cash'`, `'bank'`, `'auto'` (cash while online, else bank; an item currency always resolves to cash) |
| `opts.accountId` | number | default account | bank: account paid into (no permission check: `SystemDeposit`) |
| `opts.currency` | string | `'cash'` | cash: item paid (must exist in `Config.Items`) |
| `opts.reason` | string | `'Payment'` | statement and activity log (truncated to 120) |

Returns: `WhipPayResult { method, amount, currency?, placement?, accountId? }` — `placement` `'inventory'` (pockets) or `'ground'` (at their feet when full); `accountId` for bank — or `false, reason`.

Failures: amount error, `WhoIs` errors, `"method must be 'cash', 'bank' or 'auto'"`, `'Unknown currency item "x"'`, `'a bank payment is in dollars — currency is for a cash payment'`, `'They are not online: pay a character who is away into the bank'` (cash to an offline character, including auto with a non-cash currency), `'Could not pay them'`, `'No such account'`, `'The bank could not be reached — try again'`, `'They have no bank account'`, `'The bank refused it'`, and `SystemDeposit`'s (`'Account is frozen'`, `'Account is closed'`, `'Account not found'`).
```lua
exports.whip_core:PayPlayer(source, 250, { reason = 'Courier job' })
exports.whip_core:PayPlayer({ charId = 12 }, 250, { method = 'bank', reason = 'Wages' })
```

## Money holds

For metered services (fuel, a taxi fare, a car wash cycle): hold the most it could cost, report usage as it runs, settle; the rest comes back. whip_fuel's pumps use this. Do not charge-then-refund the change for metered services: the change is lost if your resource or the server stops in between.

Safety model (`server/money_holds.lua`): the refund owed for the whole hold is noted on the character (metadata `moneyHeldOwed`) in the SAME write as the payment. A crash before settle leaves the note and the next login pays it back (toast `'$N refunded for <reason> you paid for and did not get'`). The payer leaving (logout/disconnect, settled before their save), your resource stopping, or whip_core stopping settles for what was used so far. Cash change goes to the pockets (the bank if it does not fit); a bank refund that cannot be made now is owed and paid at next login. Only the resource that opened a hold can spend, settle or read it.

### HoldMoney(source, amount, opts?) — SERVER, WAITS
- `amount`: whole >= 0.
- `opts.method`: `'bank'` → bank (always the default account), anything else → `'cash'` (no `'auto'`, no `accountId`).
- `opts.reason`: string, truncated to 60, default `'Payment'`.
- `opts.vehicle`: a vehicleId; that car's DB row is held unwritten until the settle, so fuel not yet paid for is never saved (hold renewed every 5 s).
- Returns the hold id (integer), or `false, why`: `'amount is a whole number of 0 or more'`, `'Player not loaded'`, `'You have no bank account'`, `'The bank could not be reached — try again'`, `'You left before the payment finished'`, `'Payment failed'`, or the charge's own (`'Not enough cash (have $X, need $Y)'`, `'Insufficient funds'`...).
```lua
local holdId, why = exports.whip_core:HoldMoney(source, 100, { method = 'cash', reason = 'Car wash' })
if not holdId then return false, why end
-- each cycle: SpendMoneyHold(holdId, usedSoFar); at the end: SettleMoneyHold(holdId)
```

### SpendMoneyHold(id, spent) — SERVER
Reports money used so far (rounded, clamped to 0..held amount): what a settle keeps if your resource or the server stops first. Returns `true`, or `false, why` when gone (`'No such hold: it is settled already (by you, the payer leaving, or a restart)'`) or not yours (`'That hold is not yours: only the resource that opened it can spend or settle it'`): stop the service then.

### SettleMoneyHold(id, spent?) — SERVER, WAITS
Ends the hold: `spent` (default: the last `SpendMoneyHold` value, else 0) kept, the rest refunded, the note cleared and a held vehicle's row written, together. Returns `{ spent, refunded, paidNow }` (`paidNow = false`: the change is owed and paid at next login, or the payer had already gone), or `false, why` (settled already / not yours).

### GetMoneyHold(id) — SERVER
`{ source, amount, spent, method }`, or `nil` (over, or not yours). Ask before giving more of the service.

## Accounts: kinds, numbers, roles

- `type`: `'personal'`, `'savings'`, `'business'`, `'shared'`.
- Every character gets a personal default account (`isDefault`, label `Config.DefaultAccountLabel`, `Config.StartingBalance`) at creation; a login that finds no default account at all creates one (paying the starting balance again).
- A character's default ("main") account is always personal and owned by them; wages and default payments use it; it cannot be closed by players.
- Business accounts: linked to a job (`jobId`); staff access follows their job rank (`bankAccess` on the role: Owner `'manager'`, Manager `'withdraw'`, Employee `'view'` by default, `Config.JobDefaultRoles`). A business account follows the business owner. `GetJobBankAccounts` returning none means the job has no owner/account.
- Account numbers: `WB-` + 6 random digits (`'WB-%06d'`), unique.
- Roles and levels: `view (1) < deposit (2) < withdraw (3) < manager (4) < owner (5)`; each includes the ones before it.
  - deposit: pay in. withdraw: take out, transfer out, pay from it (`ChargePlayer`). manager/owner: grant/revoke roles below their own.
  - Owner access cannot be revoked; an owner's access cannot be changed by grants.

## Reading accounts

`WhipBankAccount` (every account read): `{ accountId, accountNumber, label, type, ownerCharId, jobId, balance, isDefault (bool), frozen (bool), createdAt (epoch s), closedAt (epoch s|nil) }`; `GetCharacterBankAccounts` rows add `role`. Reads only return open accounts (`closedAt IS NULL`).

### GetBalance(who) — SERVER, WAITS (first read only)
- `who`: a person (their default account) or `{ accountId = n }`.
- From memory after the first read of each account; every bank write keeps it true. Fine for HUDs, phone apps and prompts to call often.
- Returns `integer`, or `false, why`: `'They have no bank account'`, `'accountId is a number'`, `'No such account'` (also for a closed account), DB error, `WhoIs` errors.

### GetBankAccount(ref) — SERVER, WAITS
`ref`: accountId number, `{ number = 'WB-123456' }`, `{ accountId = n }` or `{ id = n }`. Returns `WhipBankAccount|nil`.

### GetDefaultBankAccount(who) — SERVER, WAITS
Person's default account (a DB read every call; use `GetBalance` for balances). `table|nil`.

### GetCharacterBankAccounts(charId) — SERVER, WAITS
Every open account the character can use (owned, shared, job), default first, each with `role`. To offer accounts to pay from, keep `withdraw`, `manager`, `owner`. Returns `table[]` (`{}, err` on DB error). Fills the permission cache.

### GetJobBankAccounts(job) — SERVER, WAITS
`job`: jobId or key (`'police'`). Returns accounts, or `{}, 'No such job'`.

### GetBankTransactions(accountId, limit?, offset?) — SERVER, WAITS
Newest first (by `txId`). `limit` default 50, clamped 1-500; `offset` default 0 (max 1,000,000). Rows `WhipBankTransaction`: `{ txId, fromAccountId, toAccountId, type, amount, fromBalance, toBalance, actorCharId, message, createdAt }`; `type` is `'deposit'|'withdraw'|'transfer'|'payment'`. A row is money OUT when `fromAccountId` equals your account (a transfer appears in both accounts' histories). `fromBalance`/`toBalance` are the balances after the transaction.

### GetBankAccessList(accountId) — SERVER, WAITS
Rows `{ charId, role, grantedAt, grantedBy }`, ordered owner, manager, withdraw, deposit, view.

### CanUseBankAccount(accountId, who, role) — SERVER, WAITS
Whether a person may act at `role` level (bank's own rule). Ask before offering accounts or menu options. Returns `true`, or `false, why`: `'Needs <role> access to this account'`, `'Account not found'`, `'unknown role "x" (view, deposit, withdraw, manager, owner)'`, `'a charId and an accountId are needed'`, `WhoIs` errors. Does not check frozen or own-character rules.

## A player's moves (permission-checked)

Bank money only: no cash moves. Pass the player's `source` or `{ charId = n }` as `actor`. Each fires `whip_core:bank:balanceChanged`.

### BankDeposit(accountId, amount, actor, opts?) — SERVER, WAITS
Actor needs `deposit` or higher. `opts.reason`: statement message (default `'Deposit'`). Returns `true` or `false, err` (`'No deposit permission on this account'`, `'Account not found'`, `'Account is frozen'`, own-character sentence, amount error, `'opts is { reason = ... }'`).
**No cash is taken.** For a cash deposit: `ChargePlayer(source, n, { method = 'cash' })` first, deposit only on a receipt, and `RefundPlayer` it if the deposit is refused. Otherwise a deposit creates money.

### BankWithdraw(accountId, amount, actor, opts?) — SERVER, WAITS
Actor needs `withdraw`. Default message `'Withdrawal'`. Failures: `'No withdraw permission on this account'`, `'Account not found'`, `'Account is frozen'`, `'Insufficient funds'`, own-character sentence. **No cash is given.** For a cash withdrawal, `PayPlayer(source, amount, { method = 'cash' })` once this returns `true`. To charge for something, use `ChargePlayer`.

### BankTransfer(fromId, toId, amount, actor, opts?) — SERVER, WAITS
Actor needs `withdraw` on the source. Default message `'Transfer'`. Failures: `'Cannot transfer to the same account'`, `'No withdraw permission on source account'`, `'Source account not found'`, `'Source account is frozen'`, `'Insufficient funds'`, `'Destination account not found'`, `'Destination account is frozen'`, own-character sentence (checked against both accounts' owners).

## System moves (no permission check)

Your resource decides who may. `opts = { reason?, actorCharId? }` (`reason` truncated to 120, shown on the statement; `actorCharId` recorded as who caused it). Each successful call from another resource writes a `bank_system` activity row with your resource's name. Not subject to the own-character block.

### BankSystemDeposit(accountId, amount, opts?) — SERVER, WAITS
Wages, takings, rewards. Default message `'System deposit'`. Failures: amount, `'Account not found'`, `'Account is frozen'`, `'Account is closed'`, `'opts is { reason?, actorCharId? }'`.

### BankSystemWithdraw(accountId, amount, opts?) — SERVER, WAITS
Fines, fees, bills. Default `'System withdrawal'`. Failures: `'Insufficient funds'`, `'Account is frozen'`, `'Account not found'`.
```lua
local account = exports.whip_core:GetDefaultBankAccount(source)
if account then
    local ok, why = exports.whip_core:BankSystemWithdraw(account.accountId, 250, { reason = 'Speeding fine' })
end
```

### BankSystemTransfer(fromId, toId, amount, opts?) — SERVER, WAITS
Payroll from a job account (`GetJobBankAccounts`) to an employee's default account. Default `'System transfer'`. Same refusals as `BankTransfer` minus permission/own-character.

## Opening, sharing, closing, freezing

### CreateBankAccount(owner, label?, opts?) — SERVER, WAITS
Opens an account at $0 (never `isDefault`, never the starting balance). Owner gets an `owner` access row.
- `label`: 1-50 chars (default `Config.DefaultAccountLabel`).
- `opts.type`: `'personal'` (default), `'savings'`, `'business'`, `'shared'`.
- `opts.job`: jobId or key for a job/business account; a missing job → `false, 'No such job'`. Job-linked accounts join that job's staff access sync.
- Limit: `Config.MaxExtraAccounts` savings+shared per owner (not counting job accounts).
- Returns the account table (`{ accountId, accountNumber, label, type, ownerCharId, jobId, balance, isDefault, frozen }`) or `false, why`: `'A character may have at most 5 savings and shared accounts'`, `'Savings and shared accounts are turned off'`, `'An account label is 1 to 50 characters'`, `'Unknown account type "x" (personal, savings, business or shared)'`, `'Failed to create bank account'`, `"opts is { type?, job? }: ..."`.

### GrantBankAccess(accountId, who, role, grantedBy) — SERVER, WAITS
- `role`: `'view'`, `'deposit'`, `'withdraw'`, `'manager'` (an upsert: replaces an existing lower role).
- Rules: the granter must have access; can only grant roles below their own; can only change people below their own level; never the owner. With `BlockOwnCharacterTransfers` on: not to another character of the granter's player, nor of the account owner's player.
- Returns `true` or `false, why`: `'Invalid role: x'`, `'Granter has no access to this account'`, `'Cannot grant a role equal to or higher than your own'`, `"Cannot change the owner's access"`, `'Cannot change the access of someone at or above your own level'`, `"That is another character of the account owner's player: they cannot be given access to this account"`, own-character sentence, `'Could not save the access change'`.

### CanGrantBankAccess(accountId, who, role, grantedBy) — SERVER, WAITS
Same checks as `GrantBankAccess`, writes nothing (the phone asks before sending an invite, then grants on acceptance). `true` or `false, why`.

### RevokeBankAccess(accountId, who, revokedBy) — SERVER, WAITS
Revoker must outrank the target. Failures: `'Target has no access to this account'`, `'Cannot revoke owner access'`, `'Revoker has no access to this account'`, `'Cannot revoke access for someone with equal or higher role'`.

### CloseBankAccount(accountId, who?) — SERVER, WAITS
Soft-closes (sets `closedAt`); everyone's access goes with it (rows kept, closed accounts are hidden from every read). Balance must be zero (checked again inside the write; a DB CHECK also forbids a closed account holding money).
- `who` given (a player closing it): must own it (`owner` role), not the default, not a job's, and type savings or shared.
- `who` omitted (your code or an admin decides): only the zero balance and not-default rules apply.
- Failures: `'Account must have zero balance'`, `'Cannot close default account'`, `'Only the owner can close this account'`, `"A job's account closes with the job"`, `'Only a savings or shared account can be closed'`, `'Account not found'`. Fires `whip_core:bank:accountChanged { what = 'closed' }`.

### SetBankAccountFrozen(accountId, frozen) — SERVER, WAITS
`true` freezes, `false` unfreezes (court order). Every move in or out is refused (`'Account is frozen'`, also at ATMs and the admin page); money and access stay. No permission check; the activity log records your resource. Returns `true` or `false, 'Account not found'|DB error`. Fires `accountChanged { what = 'frozen' }`.

## SetVehiclePrices(prices) — SERVER

What your resource charges for vehicles: `{ [model] = price }` (model lower-cased, price > 0, floored). The Banks page values an owned car at the average across all resources that declared that model. Declare in `Whip.register`; again replaces your list; removed when your resource stops. Returns `true` or `false, 'invalid price for <model>' | 'prices must map a vehicle model to its price, e.g. { adder = 1000000 }'`.

## Own-character transfer block

With `Config.BlockOwnCharacterTransfers = true` (default), money cannot pass between two characters of the same player account: `'That is another character of the same player: money cannot pass between them'`. Covers `BankTransfer` (both ends), `BankDeposit` (into a sibling's account), `BankWithdraw`, `ChargePlayer` bank payments from a sibling's account, `GrantBankAccess`/`CanGrantBankAccess`, ATMs, the phone, admin access grants, and cash left in containers or on the ground (cash marks). NOT covered: `BankSystem*` moves and cash handed over directly in the world. A failed userId read fails closed (refused with a DB error).

## ATMs

- WHIP's own ATMs need no location list: `client/atm.lua` finds `Config.AtmProps` models near the player (any MLO bank works). `AtmProps`, `AtmVisibleRange` and `AtmActiveRange` are also on /whip → Settings → Characters, money & jobs, live; an empty model list turns WHIP's ATMs off, for a server using another ATM resource (1.3.0).
- **Server-side ATM positions (1.3.0):** `IsNearAtm(source, range?)` → `true, at` (the machine's base) or `false, why`; range 0.5–10 m, default `AtmActiveRange` + 1, measured across the ground. `GetNearestAtm(coords)` → `at, distance` or `nil`, within 3 m of height. The list is GTA's own machines plus `Config.AtmExtraPositions`. For a resource that wants a standing-at-a-machine check (a robbery, a skimmer); WHIP's own ATM callbacks don't use it. The prompt is the whole interface: root "Check Balance" → account list (server asked on E) → Deposit / Withdraw (type amount into the badge, E submits) and Back. Looking away collapses to root.
- Server callbacks (`server/atm.lua`, not an API): `whip_core:atm:accounts` (rate 500 ms) returns `{ accountId, label, accountNumber, balance, frozen, canDeposit, canWithdraw }` rows plus cash on hand; `whip_core:atm:deposit` / `whip_core:atm:withdraw` (rate 1000 ms, amount `'amount'` param 1..999,999,999).
- Deposit: takes the notes first (`Money.charge` cash, reason `'ATM deposit'`), then `Bank.Deposit` (deposit permission); a refused deposit refunds the notes (dropped at the feet if pockets filled).
- Withdraw: capacity check first (`'No room — you can carry $N more'`), then `Bank.Withdraw` (withdraw permission) with the notes added and pockets frozen right before the debit commits, in one transaction; a failed commit takes them back. Messages `'ATM withdrawal'`.
- WHIP's ATM callbacks have no `near` clause (machines are client-found); money cannot be created through them because all checks run server-side. Your own ATM resource can add one with `IsNearAtm`.

## Events

| Event | Side | Payload |
|---|---|---|
| `whip_core:bank:balanceChanged` | S | any deposit, withdrawal or transfer. `{ type, accountId, amount, actorCharId, newBalance, message }`; deposits add `ownerCharId, accountType, label`; transfers use `fromAccountId, toAccountId, fromBalance, toBalance, fromOwnerCharId, fromAccountType, fromLabel, toOwnerCharId, toAccountType, toLabel` (no `accountId`/`newBalance`). `type` is `'deposit'`, `'withdraw'` or `'transfer'` |
| `whip_core:bank:accountChanged` | S | an account changed with no money moving: `{ accountId, what }`, `what` = `'label'\|'type'\|'owner'\|'frozen'\|'main'\|'closed'\|'access'` |

`balanceChanged.newBalance`/`fromBalance`/`toBalance` can be `nil` if the post-write read failed (the money still moved). Account creation fires no event. Listen to `balanceChanged` rather than polling; reads wait for the database.

## Database tables

- `bank_accounts`: `accountId`, `accountNumber` VARCHAR(12) unique, `label` VARCHAR(50), `type` ENUM, `ownerCharId` (FK characters, cascade), `jobId`, `balance` BIGINT, `isDefault`, `frozen`, `createdAt`, `closedAt`. CHECK `chk_balance_nonneg` (`balance >= 0`: the overdraft rule; a negative balance rolls the whole transaction back) and `chk_closed_empty` (`closedAt IS NULL OR balance = 0`). MariaDB >= 10.2.1 / MySQL >= 8.0.16 needed; a missing `chk_balance_nonneg` prints a loud warning 3 times at start.
- `bank_access`: PK (`accountId`, `charId`), `role` ENUM owner/manager/withdraw/deposit/view, `grantedAt`, `grantedBy`.
- `bank_transactions`: `txId`, `actorCharId`, `fromAccountId`, `toAccountId` (FK RESTRICT: ledger rows are never deleted), `amount` BIGINT UNSIGNED, `type` ENUM deposit/withdraw/transfer/payment, `message` VARCHAR(255), `fromBalance`, `toBalance`, `createdAt`.
- `cash_marks`: `markKey`, `charId`, `userId`, `amount`, `updatedAt`.
- Times are returned as epoch seconds; flags as booleans.

## Failure strings (bank, by exact text)

`'Amount must be a whole number of 1 or more'`, `'Account not found'`, `'Account is frozen'`, `'Account is closed'`, `'Insufficient funds'`, `'Cannot transfer to the same account'`, `'Source account not found'`, `'Source account is frozen'`, `'Destination account not found'`, `'Destination account is frozen'`, `'No deposit permission on this account'`, `'No withdraw permission on this account'`, `'No withdraw permission on source account'`, `'Needs <role> access to this account'`, `'That is another character of the same player: money cannot pass between them'`, `'Account must have zero balance'`, `'Cannot close default account'`, `'Only the owner can close this account'`, `'No such job'`, `'They have no bank account'`. DB failures answer the shared `DB_ERROR` text.

## Banks admin page

`/whip` → Economy → Banks (needs `whip.devtools`, re-checked per action; `server/bank_admin.lua`).
- Lists every player with a character, every business (job), every lore character, and accounts nobody holds. Search by name, licence or account number; "Most Money" sorts by balance. With nobody picked: whole-bank totals (deposits, cash on characters, last 24 h, frozen accounts).
- Holder page: Total money (bank + cash; per character or all), Net worth (assumed), Transactions (all-time count, 30-day in/out chart; moves between their own accounts excluded), Accounts (open, others' they can use, closed), Full log (filter in/out/account; Cash tab reads the activity log).
- Net worth: own accounts' balances; cash at face value anywhere; vehicles at the average `SetVehiclePrices` price (unsold models $0); properties at listed price; items at the average shop price (free and other-currency prices ignored) in pockets, boots, gloveboxes, stashes and inside items (unpriced named); owned businesses' accounts and shelves. A deleted character still counts while it has an open account (marked).
- Actions: New Account (optional opening amount with a required reason; no `StartingBalance`; `MaxExtraAccounts` does not apply; a lore character has one account named after its bank name), Name/Type/New owner (a main account stays personal and theirs; old owner keeps manager access until removed; business accounts follow the business owner set on the Jobs page), Freeze, Make Their Main Account, Add/Take/Move Money (reason required, statement shows `Admin: <reason>`; Add creates money, Take destroys it, Move needs the destination number), Who can use it (set/remove access; own-character rule applies; business staff access comes from ranks), Delete Account (asks where the money goes: move to a number or remove; then closes for good, kept under Closed with its log; a living character's main account cannot be deleted). Limit per admin money action: 1,000,000,000,000.
- Every action is logged as `bank_admin` on the admin's timeline and the owner's.

## Gotchas

1. `BankDeposit`/`BankWithdraw` move bank money only: pair them with `ChargePlayer` (cash in) / `PayPlayer` (cash out), or you create or destroy money.
2. A bare number is a server id. Pass `{ charId = n }` for characters; a charId as a number targets whoever has that server id.
3. Receipts live 30 minutes, in memory, and only the charging resource can refund. Keep the receipt; a restart of whip_core or of your resource loses refundability.
4. `ChargePlayer` inside a SecureEvent is written with the action's next write: if that write fails, the payment never happened; still call `RefundPlayer` on failure paths (it then just releases the hold).
5. After a wait between charging and delivering, check `IsSessionCurrent(source, player.session)` and refund if the player left or switched character.
6. Use money holds, not charge-and-refund, for metered services.
7. `PayPlayer` cash to an offline character fails; use `{ method = 'bank' }` or `'auto'` (auto picks bank when offline, except with an item `currency`).
8. `PayPlayer` cash that does not fit drops at their feet (`placement = 'ground'`).
9. `GetPlayerCash`/`ChargePlayer` count only banknotes in pocket slots, not notes inside a wallet item.
10. Bank amounts must be whole and >= 1 (charge/pay allow 0); strings like `'10.5'` or `0` are refused, never rounded.
11. Reads (`GetDefaultBankAccount`, `GetCharacterBankAccounts`, `GetBankTransactions`) hit the database every call: read when the player asks, not every frame. Use `GetBalance` (memory after first read) or `balanceChanged`.
12. `CanUseBankAccount` checks the role only; a frozen account or the own-character rule can still refuse the actual move.
13. `GetBankAccount` and every read return nothing for closed accounts; `GetBalance` on a closed account answers `'No such account'`.
14. Frozen accounts refuse system moves too, including `PayPlayer` bank payments and refunds (a bank refund then falls back to cash).
15. `BankSystem*` bypasses the own-character block and permissions: your code must authorize.
16. Closing a default account through the export is refused even without `who`; a login that finds no default account creates a new one with the starting balance (money farm risk if you close mains by other means).
17. Holds only accept `'cash'` or `'bank'` (default account); `'auto'` and `accountId` are ignored.

## Docs vs code

1. Transfer refusals: docs say frozen accounts refuse with `'Account is frozen'`; transfers use `'Source account is frozen'` / `'Destination account is frozen'` (`server/bank.lua:979`, `:984`).
2. `GetBankTransactions` type `'payment'`: docs list it, the schema has it, but no code path writes it; `ChargePlayer` bank payments are recorded as `'withdraw'` with the reason as message (`server/bank.lua:834`, `server/money.lua:204`).
3. `GetBankAccessList` rows also include `grantedAt` (`server/bank.lua:1154`); docs list `{ charId, role, grantedBy }`.
4. `CloseBankAccount(accountId, who)` has two refusals the docs omit: `"A job's account closes with the job"` and `'Only a savings or shared account can be closed'` (`server/bank.lua:1581-1583`).
5. `ChargePlayer`/`PayPlayer` amount refusal reads `'Amount must be a whole number of 0 or more'` (`server/money.lua:36`), unlike the bank's `'... of 1 or more'`.
6. `HoldMoney` opts: only `method` `'bank'` selects the bank; any other value (including `'auto'`) means cash; `reason` is cut to 60 chars (`server/money_holds.lua:137-138`).
7. `GetBalance` on a closed account: docs list "closed" as a reason; the code answers `'No such account'` because the account read already filters closed accounts (`server/bank.lua:1465-1467`).
8. Docs describe cash as "banknote items"; there are no denominations: one `cash` item whose amount is dollars (`config.lua:174`).
