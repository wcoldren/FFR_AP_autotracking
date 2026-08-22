ITEM_MAPPING = {
  [257] = {"lute", "toggle"},
  [258] = {"crown", "progressive"},
  [259] = {"crystal", "progressive"},
  [260] = {"herb", "progressive"},
  [261] = {"key", "toggle"},
  [262] = {"tnt", "progressive"},
  [263] = {"adamant", "progressive"},
  [264] = {"slab", "progressive"},
  [265] = {"ruby", "progressive"},
  [266] = {"rod", "toggle"},
  [267] = {"floater", "progressive"},
  [268] = {"chime", "toggle"},
  [269] = {"tail", "progressive"},
  [270] = {"cube", "toggle"},
  [271] = {"bottle", "progressive"},
  [272] = {"oxyale", "toggle"},
  -- Not "progressive": Shards is the pack's only allow_disabled:false
  -- progressive, so Active is not a separate off state and the first grant has
  -- to advance the stage like every other one. See onItem.
  [277] = {"shards", "count"},
  [480] = {"ship", "toggle"},
  [488] = {"bridge", "toggle"},
  [492] = {"canal", "toggle"},
  [498] = {"canoe", "toggle"},
  [499] = {"sigil", "toggle"},
  [500] = {"mark", "toggle"},
}
