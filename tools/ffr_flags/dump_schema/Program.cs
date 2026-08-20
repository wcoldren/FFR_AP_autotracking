// Emits the Flags encoding schema for whichever FF1Randomizer checkout this is
// built against. It walks the property list exactly the way
// Flags.EncodeFlagsText does -- public instance properties that can be written
// and are not [FlagIsAllClasses], ordered by name and reversed, which is decode
// order -- and records each one's radix.
//
// Reflecting is the point: transcribing 570 properties and their enum ranges by
// hand would be a second implementation to keep in step with FFR's.
//
//   dotnet run --project tools/ffr_flags/dump_schema \
//       -p:FF1LibPath=/path/to/FF1Randomizer/FF1Lib > schema.json
using System.Reflection;
using System.Text.Json;
using FF1Lib;

var flagproperties = typeof(Flags)
    .GetProperties(BindingFlags.Instance | BindingFlags.Public)
    .Where(p => p.CanWrite && !Attribute.IsDefined(p, typeof(FlagIsAllClasses)))
    .OrderBy(p => p.Name)
    .Reverse()
    .ToList();

var encoded = new List<object>();
var skipped = new List<string>();
foreach (var p in flagproperties)
{
    if (Nullable.GetUnderlyingType(p.PropertyType) == typeof(bool))
        encoded.Add(new { name = p.Name, kind = "tristate", radix = 3 });
    else if (p.PropertyType == typeof(bool))
        encoded.Add(new { name = p.Name, kind = "bool", radix = 2 });
    else if (p.PropertyType.IsEnum)
        encoded.Add(new
        {
            name = p.Name,
            kind = "enum",
            radix = Enum.GetValues(p.PropertyType).Cast<int>().Max() + 1,
            type = p.PropertyType.Name,
            names = Enum.GetValues(p.PropertyType).Cast<int>()
                .Distinct().OrderBy(v => v)
                .ToDictionary(v => v.ToString(), v => Enum.GetName(p.PropertyType, v)),
        });
    else if (p.PropertyType == typeof(int))
    {
        var ia = p.GetCustomAttribute<IntegerFlagAttribute>();
        encoded.Add(new
        {
            name = p.Name,
            kind = "int",
            radix = (ia.Max - ia.Min) / ia.Step + 1,
            min = ia.Min,
            step = ia.Step,
        });
    }
    else if (p.PropertyType == typeof(double))
    {
        var ia = p.GetCustomAttribute<DoubleFlagAttribute>();
        encoded.Add(new
        {
            name = p.Name,
            kind = "double",
            radix = (int)Math.Ceiling((ia.Max - ia.Min) / ia.Step) + 1,
            min = ia.Min,
            step = ia.Step,
        });
    }
    else
    {
        // EncodeFlagsText has no branch for these, so they contribute nothing.
        skipped.Add($"{p.Name}:{p.PropertyType.Name}");
    }
}

Console.Error.WriteLine($"FFR version {FFRVersion.Version}");
Console.Error.WriteLine($"properties considered: {flagproperties.Count}, encoded: {encoded.Count}");
Console.Error.WriteLine($"not encoded: {string.Join(", ", skipped)}");

Console.WriteLine(JsonSerializer.Serialize(new
{
    version = FFRVersion.Version.Replace('.', '-'),
    build_sha = (string)null,   // filled in by gen_schema.py from the checkout
    not_encoded = skipped,
    properties = encoded,
}, new JsonSerializerOptions { WriteIndented = true }));
