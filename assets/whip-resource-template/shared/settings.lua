-- Config as a settings page in /whip. Each key is a path into Config; config.lua's value is the default.
Whip.configPage({
    label = 'My Resource',
    settings = {
        { key = 'Price', type = 'int', min = 0, max = 10000, unit = '$', label = 'Price',
          help = 'What one costs.' },
        { key = 'Counter', type = 'vec3', here = true, label = 'Counter',
          help = 'Where the counter is. Use where I stand sets it to your position.' },
        { key = 'Range', type = 'number', min = 1, max = 10, step = 0.5, unit = 'm', label = 'Reach',
          apply = 'restart', why = 'The prompt is placed when the resource starts' },
    },
})
