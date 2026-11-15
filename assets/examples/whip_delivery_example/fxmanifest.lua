-- A delivery job on whip, the way a qb-style delivery job is usually built, call by call
-- (docs.html: Coming from QBCore, ESX or ox -> A qb delivery job, call by call).
-- Sign on at the depot, clock on, take a van for a deposit, carry each package from the boot to the door
-- on your map, get paid at the door, bring the van back for the deposit.

fx_version 'cerulean'
game 'gta5'
lua54 'yes'

name 'whip_delivery_example'
description 'A delivery job: van, deposit, packages, drop-offs, pay (whip example)'
version '1.0.0'

dependency 'whip_core'

shared_scripts {
    '@whip_core/lib/satellite.lua',
    'shared.lua',
}
server_script 'server.lua'
client_script 'client.lua'

files {
    'html/img/items/*.webp',   -- the package's picture
}
