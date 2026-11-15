-- client.lua: one counter, three choices (anyone buys; staff clock on, brew and clock off)
Whip.register(function()
    Whip.core:AddAction({
        id      = 'counter',
        at      = { coords = Config.Counter },
        options = {
            { id = 'buy', label = ('Buy coffee ($%d)'):format(Config.Price), icon = 'cash',
              onSelect = function() TriggerServerEvent('mycafe:buy') end },

            -- Staff only. whipJob is the job they are on duty at (false when off duty)
            { id = 'clockon', label = 'Clock on', require = { job = 'mycafe' },
              canInteract = function() return LocalPlayer.state.whipJob ~= 'mycafe' end,
              onSelect = function(ctx)
                  local ok, why = exports.whip_core:ClockOn('mycafe')
                  if not ok then ctx.refuse(why) end
              end },

            { id = 'brew', label = 'Brew a coffee', require = { job = 'mycafe', onDuty = true },
              onSelect = function() TriggerServerEvent('mycafe:brew') end },

            { id = 'clockoff', label = 'Clock off', require = { job = 'mycafe', onDuty = true },
              onSelect = function() exports.whip_core:ClockOff('mycafe') end },
        },
    })
end)
