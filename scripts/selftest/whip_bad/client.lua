CreateThread(function()
    while true do
        Wait(0)
        DisableControlAction(0, 24, true)
    end
end)
RegisterCommand('buy', function() TriggerServerEvent('bad:buy', price) SetNuiFocus(true, true) end)
exports.whip_core:AddAction({ id = 'bad', at = { coords = vector3(0, 0, 0) }, distance = 2.0,
    options = { { id = 'a', label = 'A', job = 'police', onSelect = function() local ok, why = 1, 2 end } } })
