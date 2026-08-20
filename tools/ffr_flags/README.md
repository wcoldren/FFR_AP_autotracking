# Reading a seed's flags out of the cartridge

FFR stamps the flag string it was rolled with into the ROM, in plain ASCII.
`FF1Rom.WriteSeedAndFlags` puts it in bank `0x1E` at `0xBE00` -- file offset
`0x7BE10` once the 16-byte iNES header is counted:

```
FFRInfo|Seed: D0E0CDBF|OW Seed: none|Res. Pack Hash: none|Flags: g5jrLtd...|Version: 4-9-7
```

That is the whole reason the tracker can configure itself. Neither of the other
two feeds carries the seed's settings: the Archipelago FF1 world's
`fill_slot_data` returns an empty dict, and cart RAM at `$6000-$62FF` holds
progress, not settings.

## Using it

```
python3 tools/ffr_flags/decode.py seed.nes --logic     # the flags that move logic
python3 tools/ffr_flags/decode.py seed.nes             # all 568
python3 tools/ffr_flags/decode.py seed.nes --json
python3 tools/ffr_flags/decode.py --flags 4-9-7 "https://4-9-7.finalfantasyrandomizer.com/?s=..&f=.."
```

`--flags` also takes a bare flag string, so a permalink someone pasted works
without a ROM.

## How the encoding works

The flag string is one BigInteger written in FFR's own base-64 alphabet
(`A-Za-z0-9.-`), least significant digit first. Encoding multiplies the running
total by each property's radix and adds the value, walking the `Flags` class's
public writable properties in alphabetical order; decoding is the same list in
reverse with repeated `divmod`. Radixes are 3 for a tri-state (`false`, `true`,
`random`), 2 for a bool, `max + 1` for an enum, and the step count for an int or
a double.

FF1Lib mixes the seven-character build SHA in *first*, so it comes out *last*.
That is the checksum: decode with the wrong version's property list and the
trailing characters are garbage rather than a SHA, and there is usually a
remainder left over. Both tools refuse the decode in that case instead of
reporting flags that are quietly shifted by one property.

## Adding a new FFR version

The property list changes whenever FFR adds a flag, so each version needs its
own schema. Generating one needs the .NET SDK and a checkout of
[FF1Randomizer](https://github.com/FiendsOfTheElements/FF1Randomizer) at the
commit that built the ROM -- `master` is the released version, `dev` is ahead.

```
git clone --depth 1 -b master https://github.com/FiendsOfTheElements/FF1Randomizer.git
python3 tools/ffr_flags/gen_schema.py \
    --ff1lib FF1Randomizer/FF1Lib \
    --rom "~/Library/Application Support/Archipelago/output/FFR_D0E0CDBF_TFXhhTGS.nes"
```

`dump_schema/` reflects over `FF1Lib.Flags` the same way `EncodeFlagsText` does,
rather than transcribing 568 properties and their enum ranges by hand. The build
SHA comes from the checkout's git HEAD, because `FFRVersion.Sha` is a
placeholder in source and only gets substituted during FFR's own build. Every
`--rom` given then has to decode down to exactly that SHA with nothing left
over; that is what says the schema is right and not merely plausible.

It writes two files:

- `tools/ffr_flags/schemas/<version>.json` -- for these tools and for
  `tools/check_logic.py`. Carries enum member names too, so a dump reads
  `ToFRMode: Mid (1)` rather than `1`.
- `scripts/flags/schema_<version>.lua` -- for the pack. Radixes and names only.

Neither is edited by hand.
