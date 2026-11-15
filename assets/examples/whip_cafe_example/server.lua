-- server.lua
Whip.register(function()
    Whip.core:RegisterItem('mycafe_coffee', {
        name     = 'Coffee',
        desc     = 'Hot and black. Quenches thirst.',
        weight   = 0.3,
        type     = 'consumable',
        stack    = true,
        maxStack = 10,
        usable   = true,
    })

    -- Drinking it: a 4-second bar, a cup in the right hand, and they can walk meanwhile
    Whip.core:RegisterUseHandler('mycafe_coffee', {
        label    = 'Drinking coffee...',
        duration = 4000,
        anim     = { dict = 'amb@world_human_drinking@coffee@male@idle_a', clip = 'idle_c' },
        prop     = { model = 'p_amb_coffeecup_01', bone = 28422 },
        disable  = { move = false },

        -- The bar finished and the coffee is gone. Return AddStat's answer:
        -- if it fails, whip gives the coffee back.
        onComplete = function(source)
            return exports.whip_core:AddStat(source, 'thirst', 20, 'item:mycafe_coffee')
        end,
    })

    -- Buying one. The client sends nothing: not the price, not the item.
    Whip.core:SecureEvent('mycafe:buy', {
        rateLimit = 1000,   -- one purchase a second per player
        near = { at = Config.Counter, range = 3.0, message = 'Walk up to the counter' },
    }, function(source)
        local receipt, err = exports.whip_core:ChargePlayer(source, Config.Price, { reason = 'Coffee' })
        if not receipt then
            return false, err   -- could not pay: whip shows them why
        end

        local given, why = exports.whip_core:AddItem(source, 'mycafe_coffee', 1)
        if not given then
            exports.whip_core:RefundPlayer(receipt)   -- paid, got nothing: money back
            return false, why
        end

        exports.whip_core:NotifyPlayer(source, 'Enjoy your coffee', 'success')
    end)

    -- The stand is a job: an owner and baristas
    Whip.core:EnsureJob('mycafe', {
        name  = 'Bean Machine',
        roles = {
            { name = 'Owner',   level = 100 },
            { name = 'Barista', level = 1 },
        },
    })

    -- Brewing: staff on duty, at the counter, under a bar the server times; then a coffee, and their pay
    Whip.core:SecureEvent('mycafe:brew', {
        rateLimit = 2000,
        near = { at = Config.Counter, range = 3.0, message = 'Stand at the counter' },
    }, function(source, player)
        if not exports.whip_core:IsPlayerClockedOn(source, 'mycafe') then
            return false, 'Clock on first'
        end

        local done, reason = exports.whip_core:Progress(source, {
            label    = 'Brewing...',
            duration = 6000,
            near     = { coords = Config.Counter, range = 3.0 },   -- still at the counter when it ends
        })
        if not done then return false, reason end

        -- Six seconds went by: still the same character? (they may have logged out)
        if not exports.whip_core:IsSessionCurrent(source, player.session) then return end

        local given, gwhy = exports.whip_core:AddItem(source, 'mycafe_coffee', 1, nil, 'brewed')
        if not given then return false, gwhy end
        exports.whip_core:PayPlayer(source, Config.BrewPay, { reason = 'Brewed a coffee' })
    end)
end)
