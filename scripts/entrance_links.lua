-- Which entrance pin stands on which tile. Empty here on purpose.
--
-- The entrance pins are drawn from the cartridge and exist only in the
-- regenerated user-override, so the table that resolves a tile to one of them
-- is written there too, by tools/regen_maps.py. This copy is what the base pack
-- ships: it keeps the load in scripts/init.lua honest on a tracker with no
-- override installed, and leaves the door-marking inert there, which is already
-- what happens to the pins.
--
-- scripts/autotracking/mapValues.lua is the same arrangement for the same
-- reason. PopTracker serves an override copy ahead of this one because
-- ScriptHost:LoadScript reads through Pack::ReadFile, which consults the
-- override -- unlike Pack::hasFile, which does not and which is why the door
-- icons had to be committed instead.
ENTRANCE_LINKS = {}

-- The other direction, and empty here for the same reason: one row per pin,
-- carrying the item its section hosts and the map it stands on.
-- scripts/entrance_items.lua builds the badge items from this, so a pack with
-- no override creates none -- which is right, because it has no pins to hang
-- them on either.
ENTRANCE_PINS = {}
