exports.whip_core:RegisterItem('coffee', { name = 'Coffee' })
RegisterNetEvent('bad:buy', function(price)
    local src = source
    exports.whip_core:ChargePlayer(src, price)
    Wait(1000)
    exports.whip_core:AddItem(src, 'coffee', 1)
    MySQL.insert('INSERT INTO log (src) VALUES (?)', { source })
end)
RegisterCommand('givecoffee', function(src) end)
-- invented names (QBCore habits): the scanner must catch these
AddEventHandler('whip_core:player:joined', function() end)
RegisterCommand('cash', function(src) exports.whip_core:GivePlayerMoney(src, 5) end)
