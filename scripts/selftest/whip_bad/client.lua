CreateThread(function()
    while true do
        Wait(0)
        DisableControlAction(0, 24, true)
    end
end)
RegisterCommand('buy', function() TriggerServerEvent('bad:buy', price) SetNuiFocus(true, true) end)
