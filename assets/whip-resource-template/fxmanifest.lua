-- myres: a starter resource built the WHIP way. Rename every "myres" (folder, item keys, event names).
fx_version 'cerulean'
game 'gta5'
lua54 'yes'

name 'myres'
description 'A WHIP resource'
version '1.0.0'

dependency 'whip_core'      -- starts whip_core first; a whip_core restart restarts this resource too
whip_requires '1.0'         -- the setup report flags an older whip_core
-- whip_updates 'you/myres' -- tell server owners when your GitHub repository has a newer release

shared_scripts {
    '@whip_core/lib/satellite.lua',   -- Whip.register, Whip.core, Whip.command, Whip.configPage
    'config.lua',
    'shared/settings.lua',            -- Config as a page in /whip -> Settings
}
server_script 'server/main.lua'
client_script 'client/main.lua'

-- Item pictures: html/img/items/<item key>.webp in the resource that registers the item
files {
    'html/img/items/*.webp',
}
