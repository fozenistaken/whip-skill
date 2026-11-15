-- Server: everything declared lives in Whip.register, which runs once whip_core is ready and again after
-- every whip_core restart (whip_core forgets declarations when it restarts).
local ITEM = 'myres_snack'

Whip.register(function()
    Whip.core:RegisterItem(ITEM, {
        name     = 'Snack',
        desc     = 'Fills you up a little.',
        weight   = 0.2,
        type     = 'consumable',
        stack    = true,
        maxStack = 10,
        usable   = true,
    })

    -- A table makes a timed use: WHIP shows the bar, plays the anim/prop, times it on the server,
    -- takes the item when the bar ends and runs onComplete. Return false (and why) to give it back.
    Whip.core:RegisterUseHandler(ITEM, {
        label      = 'Eating...',
        duration   = 3000,
        anim       = { dict = 'mp_player_inteat@burger', clip = 'mp_player_int_eat_burger' },
        prop       = { model = 'prop_cs_burger_01', bone = 18905 },
        disable    = { move = false },
        onComplete = function(source)
            return exports.whip_core:AddStat(source, 'hunger', 15, 'item:' .. ITEM)
        end,
    })

    -- The client sends nothing: not the price, not the item. near refuses anyone away from the counter.
    Whip.core:SecureEvent('myres:buy', {
        rateLimit = 1000,
        near = { at = function() return Config.Counter end, range = Config.Range, message = 'Walk up to the counter' },
    }, function(source, player)
        local receipt, err = exports.whip_core:ChargePlayer(source, Config.Price, { reason = 'Snack' })
        if not receipt then return false, err end           -- the player sees why

        local given, why = exports.whip_core:AddItem(source, ITEM, 1)
        if not given then
            exports.whip_core:RefundPlayer(receipt)          -- paid, got nothing: money back
            return false, why
        end
        exports.whip_core:NotifyPlayer(source, 'Enjoy', 'success')
    end)
end)

-- A command behind Whip.command's gate (rate limit, refused while down, ace/dev); dev = true: the console, or
-- whip.devtools with developer mode on.
Whip.command('myres_give', { dev = true }, function(source, args)
    local target = tonumber(args[1]) or source
    local ok, why = Whip.core:AddItem(target, ITEM, 1, nil, 'admin command')
    if not ok and source > 0 then Whip.core:NotifyPlayer(source, why, 'error') end
end)

Whip.sayStarted()   -- one "started successfully" line, or the problems
