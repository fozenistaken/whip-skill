-- client.lua: the depot desk, and a prompt at every door (shown only while you carry a package)
Whip.register(function()
    local function offDuty() return LocalPlayer.state.whipJob ~= 'mydelivery' end

    Whip.core:AddAction({
        id      = 'depot',
        at      = { coords = Config.Depot },
        options = {
            { id = 'signon', label = 'Sign on as a driver', icon = 'id', canInteract = offDuty,
              onSelect = function() TriggerServerEvent('mydelivery:signon') end },

            { id = 'clockon', label = 'Clock on', require = { job = 'mydelivery' }, canInteract = offDuty,
              onSelect = function(ctx)
                  local ok, why = exports.whip_core:ClockOn('mydelivery')
                  if not ok then ctx.refuse(why) end
              end },

            { id = 'start', label = ('Take a van ($%d deposit)'):format(Config.Deposit), icon = 'car',
              require = { job = 'mydelivery', onDuty = true },
              onSelect = function() TriggerServerEvent('mydelivery:start') end },

            { id = 'finish', label = 'Return the van', icon = 'garage', require = { job = 'mydelivery', onDuty = true },
              onSelect = function() TriggerServerEvent('mydelivery:finish') end },

            { id = 'clockoff', label = 'Clock off', require = { job = 'mydelivery', onDuty = true },
              onSelect = function() exports.whip_core:ClockOff('mydelivery') end },
        },
    })

    -- The server decides which door is theirs; a prompt at the wrong one is told so
    for i, stop in ipairs(Config.Drops) do
        Whip.core:AddAction({
            id       = 'drop_' .. i,
            at       = { coords = stop.coords },
            label    = 'Deliver the package',
            icon     = 'give',
            require  = { job = 'mydelivery', onDuty = true, item = 'mydelivery_package' },
            onSelect = function() TriggerServerEvent('mydelivery:drop') end,
        })
    end
end)
