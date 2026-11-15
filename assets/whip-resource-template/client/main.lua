-- Client: a prompt at the counter. Press E to ask the server; the server decides.
Whip.register(function()
    Whip.core:AddAction({
        id       = 'counter',
        at       = { coords = Config.Counter },
        reach    = Config.Range,
        label    = function() return ('Buy a snack ($%d)'):format(Config.Price) end,
        icon     = 'cash',
        onSelect = function()
            TriggerServerEvent('myres:buy')
        end,
    })
end)
