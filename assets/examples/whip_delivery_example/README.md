# whip_delivery_example

A delivery job on whip: the job a qb-core server usually builds with qb-target, vehiclekeys, an ItemBox and a pay event, written with whip's calls. `docs.html` → **Coming from QBCore, ESX or ox** → *A qb delivery job, call by call* maps each step.

| The job | The call |
|---|---|
| A job, and anyone may sign on | `EnsureJob`, `HirePlayer` |
| The depot desk: sign on, clock on, take a van, return it | `AddAction` with `options`, each with its `require` |
| A $500 deposit for the van, from the bank | `ChargePlayer(source, 500, { method = 'bank' })`: keep the receipt |
| The van, with a key for the driver | `SpawnTempVehicle(..., { forSource = source, despawnAfter = 1500 })` |
| Packages in the van's boot | `StoreGive({ kind = 'vehicle', id = vanId, sub = 'trunk' }, ...)` |
| A route to the door | `ShowBlip({ people = { source } }, id, { coords, route = true })` |
| At the door: a bar, the package taken, pay | `SecureEvent` with `near` on that player's door, the server's `Progress`, `RemoveItem`, `PayPlayer` |
| The van back: the deposit back | `GetVehicle(vanId).coords`, `DespawnVehicle`, `RefundPlayer(receipt)` |
| They log out, or the van is taken back | `whip_core:player:logout`, `whip_core:vehicle:released` |

The `near` check on the door is the point: the pay event cannot be fired from anywhere on the map, only by the player standing at the door their run sends them to.

## Running it

It sits in `whip_core/docs/examples/` so it never starts by itself: FiveM does not look for resources inside another resource's folder.

1. Copy the `whip_delivery_example` folder into your resources folder.
2. In `server.cfg`, below WHIP's `ensure` lines: `ensure whip_delivery_example`. Restart the server.
3. At the depot desk (the van on the map, *Post Op depot*, beside the Public Garage): **Sign on as a driver**, **Clock on**, **Take a van**.
4. Open the van's boot, drag a package into your pockets, drive to the door on your map, **Deliver the package**. Back at the desk: **Return the van**.

Move any spot in `shared.lua`: `/w` → Coords, stand on it, press G, and paste.
