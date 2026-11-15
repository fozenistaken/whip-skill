-- Read by both sides. To move a spot: /w -> Coords, stand on it, press G, paste.
Config = {
    Depot    = vector3(812.0, -806.3, 26.0),         -- the desk: sign on, clock on, take a van, return it
    VanSpawn = vector4(807.0, -820.0, 26.4, 90.0),   -- a clear parking bay beside it
    VanModel = 'speedo',
    VanBack  = 40.0,    -- metres from the desk the van must be parked to count as returned

    Deposit  = 500,     -- taken from the bank when the van goes out; back when it comes back
    Pay      = 120,     -- for each package delivered
    Packages = 3,       -- packages (and doors) in one run

    -- Where a package goes: the player stands here, at the door
    Drops = {
        { label = 'Mission Row Police Station', coords = vector3(433.5, -981.9, 30.8) },
        { label = 'Rockford Hills',             coords = vector3(-817.5, 177.9, 72.8) },
        { label = 'Mirror Park',                coords = vector3(965.4, -594.1, 60.4) },
        { label = 'Forum Drive',                coords = vector3(-14.1, -1441.9, 31.1) },
        { label = 'Strawberry',                 coords = vector3(128.5, -1298.5, 29.25) },
    },
}
