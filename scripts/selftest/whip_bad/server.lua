exports.whip_core:RegisterItem('coffee', { name = 'Coffee' })
RegisterNetEvent('bad:buy', function(price)
    local src = source
    exports.whip_core:ChargePlayer(src, price)
    Wait(1000)
    exports.whip_core:AddItem(src, 'coffee', 1)
    MySQL.insert('INSERT INTO log (src) VALUES (?)', { source })
end)
RegisterCommand('givecoffee', function(src) end)
