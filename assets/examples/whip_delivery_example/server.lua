-- server.lua
local PACKAGE = 'mydelivery_package'

-- One run per player: [source] = { vanId, receipt, stops = { index, ... }, done }
local runs = {}

local function blipId(source) return 'mydelivery_' .. source end

local function currentStop(run)
    return run and run.stops and Config.Drops[run.stops[run.done + 1]]
end

-- Point the map at the next door, or back to the depot when the van is empty
local function showNext(source, run)
    local stop = currentStop(run)
    if stop then
        exports.whip_core:ShowBlip({ people = { source } }, blipId(source),
            { coords = stop.coords, label = 'Drop-off: ' .. stop.label, route = true })
    else
        exports.whip_core:ShowBlip({ people = { source } }, blipId(source),
            { coords = Config.Depot, label = 'Return the van', route = true, color = 2 })
        exports.whip_core:NotifyPlayer(source, 'All delivered. Take the van back for your deposit', 'success')
    end
end

-- Packages still in their pockets go back when the run ends
local function takeBackPackages(source)
    local left = exports.whip_core:GetItemCount(source, PACKAGE) or 0
    if left > 0 then exports.whip_core:RemoveItem(source, PACKAGE, left, nil, { reason = 'delivery run ended' }) end
end

local function pickStops(n)
    local order = {}
    for i = 1, #Config.Drops do order[i] = i end
    for i = #order, 2, -1 do
        local j = math.random(i)
        order[i], order[j] = order[j], order[i]
    end
    local stops = {}
    for i = 1, math.min(n, #order) do stops[i] = order[i] end
    return stops
end

Whip.register(function()
    runs = {}   -- whip_core (re)started: every van and blip went with it

    Whip.core:RegisterItem(PACKAGE, {
        name     = 'Package',
        desc     = 'Addressed and taped. Take it to the door on your map.',
        weight   = 2.0,
        stack    = true,
        maxStack = 5,
    })

    local job, why = Whip.core:EnsureJob('mydelivery', {
        name  = 'Post Op',
        roles = {
            { name = 'Manager', level = 100 },
            { name = 'Driver',  level = 1 },
        },
    })
    if not job then print('[mydelivery] no job: ' .. tostring(why)) end

    -- The depot on everyone's map (67 is GTA's van icon)
    Whip.core:ShowBlip('everyone', 'mydelivery_depot',
        { coords = Config.Depot, label = 'Post Op depot', sprite = 67, color = 5, shortRange = true })

    local atDepot = { at = Config.Depot, range = 3.0, message = 'Go to the depot desk' }

    -- Anyone may sign on as a driver
    Whip.core:SecureEvent('mydelivery:signon', { rateLimit = 3000, near = atDepot }, function(source)
        if exports.whip_core:GetPlayerRole(source, 'mydelivery') then
            return false, 'You already drive for us: clock on'
        end
        local ok, err = exports.whip_core:HirePlayer(source, 'mydelivery', 'Driver')
        if not ok then return false, err end
        exports.whip_core:NotifyPlayer(source, 'Signed on. Clock on to take a van', 'success')
    end)

    -- A van for a deposit, its boot loaded with packages, and a route to the first door
    Whip.core:SecureEvent('mydelivery:start', { rateLimit = 3000, near = atDepot }, function(source, player)
        if not exports.whip_core:IsPlayerClockedOn(source, 'mydelivery') then return false, 'Clock on first' end
        if runs[source] then return false, 'You already have a van out' end

        local run = { done = 0 }
        runs[source] = run   -- held now, so a second press is refused while the van is made
        local function undo(reason, receipt, vanId)
            if runs[source] == run then runs[source] = nil end
            if vanId then exports.whip_core:DespawnVehicle(vanId) end
            if receipt then exports.whip_core:RefundPlayer(receipt) end
            return false, reason
        end

        local receipt, err = exports.whip_core:ChargePlayer(source, Config.Deposit, { method = 'bank', reason = 'Van deposit' })
        if not receipt then return undo(err) end

        -- 25 minutes: the deposit can be refunded for 30
        local vanId, verr = exports.whip_core:SpawnTempVehicle(Config.VanModel, Config.VanSpawn, {
            forSource = source, despawnAfter = 1500,
        })
        if not vanId then return undo(verr, receipt) end

        local slot, gerr = exports.whip_core:StoreGive({ kind = 'vehicle', id = vanId, sub = 'trunk' },
            PACKAGE, Config.Packages, nil, 'delivery run')
        if not slot then return undo(gerr, receipt, vanId) end

        -- The waits above took time: still the same character, and still this run?
        if runs[source] ~= run or not exports.whip_core:IsSessionCurrent(source, player.session) then
            return undo(nil, receipt, vanId)
        end

        run.vanId, run.receipt, run.stops = vanId, receipt, pickStops(Config.Packages)
        exports.whip_core:NotifyPlayer(source, 'The van is outside. Take a package from the boot and follow the route', 'success')
        showNext(source, run)
    end)

    -- At the door: the server times the bar, takes the package and pays
    Whip.core:SecureEvent('mydelivery:drop', {
        rateLimit = 2000,
        near = {
            at = function(source)
                local stop = currentStop(runs[source])
                return stop and stop.coords   -- nil: no package due here, refused as too far
            end,
            range   = 3.0,
            message = 'Not this door: follow the route on your map',
        },
    }, function(source, player)
        local run = runs[source]
        local stop = currentStop(run)
        if not exports.whip_core:HasItem(source, PACKAGE) then return false, 'Take a package from the van first' end

        local done, reason = exports.whip_core:Progress(source, {
            label    = 'Delivering...',
            duration = 4000,
            near     = { coords = stop.coords, range = 3.0 },
        })
        if not done then return false, reason end
        if runs[source] ~= run or not exports.whip_core:IsSessionCurrent(source, player.session) then return end

        local taken, terr = exports.whip_core:RemoveItem(source, PACKAGE, 1, nil, { reason = 'delivered' })
        if not taken then return false, terr end
        run.done = run.done + 1
        exports.whip_core:PayPlayer(source, Config.Pay, { reason = 'Delivery: ' .. stop.label })
        showNext(source, run)
    end)

    -- The van back at the depot: it goes, and so does the deposit, back to them
    Whip.core:SecureEvent('mydelivery:finish', { rateLimit = 3000, near = atDepot }, function(source)
        local run = runs[source]
        if not run or not run.vanId then return false, 'You have no van out' end

        local van = exports.whip_core:GetVehicle(run.vanId)
        if not van or not van.coords or #(van.coords - Config.Depot) > Config.VanBack then
            return false, 'Park the van at the depot first'
        end

        runs[source] = nil
        exports.whip_core:HideBlip(blipId(source))
        exports.whip_core:DespawnVehicle(run.vanId)
        exports.whip_core:RefundPlayer(run.receipt)
        takeBackPackages(source)
        exports.whip_core:NotifyPlayer(source, ('Van returned. $%d deposit back'):format(Config.Deposit), 'success')
    end)
end)

-- Leaving ends the run: the van goes, the deposit stays with the depot
AddEventHandler('whip_core:player:logout', function(e)
    if GetInvokingResource() ~= 'whip_core' or type(e) ~= 'table' then return end
    local run = runs[e.source]
    if not run then return end
    runs[e.source] = nil
    exports.whip_core:HideBlip(blipId(e.source))
    if run.vanId then exports.whip_core:DespawnVehicle(run.vanId) end
    takeBackPackages(e.source)
end)

-- The van went without being returned: its time ran out, or it sat alone for ten minutes
AddEventHandler('whip_core:vehicle:released', function(e)
    if GetInvokingResource() ~= 'whip_core' or type(e) ~= 'table' or e.reason == 'despawned' then return end
    for source, run in pairs(runs) do
        if run.vanId == e.vehicleId then
            runs[source] = nil
            exports.whip_core:HideBlip(blipId(source))
            takeBackPackages(source)
            exports.whip_core:NotifyPlayer(source, 'The depot took the van back. Your deposit is kept', 'error')
            return
        end
    end
end)
