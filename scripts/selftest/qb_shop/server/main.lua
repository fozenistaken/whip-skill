local QBCore = exports['qb-core']:GetCoreObject()
RegisterNetEvent('qb_shop:buy', function(item, price, amount)
    local src = source
    local Player = QBCore.Functions.GetPlayer(src)
    if Player.Functions.RemoveMoney('cash', price * amount) then
        Player.Functions.AddItem(item, amount)
        TriggerClientEvent('inventory:client:ItemBox', src, QBCore.Shared.Items[item], 'add')
    end
end)
QBCore.Functions.CreateCallback('qb_shop:stock', function(source, cb) cb({}) end)
QBCore.Functions.CreateUseableItem('sandwich', function(source, item) end)
local xPlayer = ESX.GetPlayerFromId(1); xPlayer.addMoney(5)
local p = exports.qbx_core:GetPlayer(1)
