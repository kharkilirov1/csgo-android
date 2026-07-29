# CS:GO 2018 → portable Source Engine audit

## Inputs

- Portable engine: `C:\Users\Kharki\Desktop\source-engine`
- CS:GO donor: `C:\Users\Kharki\Downloads\csgo-2018-source-main\csgo-2018-source-main`

## Inventory

| Metric | Count |
|---|---:|
| Portable tree files | 21700 |
| Donor tree files | 13847 |
| Same relative paths | 5907 |
| Donor-only paths | 7940 |
| Portable-only paths | 15793 |
| CS:GO client code files | 300 |
| CS:GO server code files | 110 |
| CS:GO shared code files | 120 |

## Build and API gates

- Donor VPC literal `$File` references: **5759**
- Missing literal VPC references inside donor: **1068**
- Unique includes used by CS:GO gameplay: **782**
- Includes not resolvable in donor: **68**
- Includes not resolvable in portable tree: **244**

The portable engine cannot compile the donor gameplay by copying only
`game/*/cstrike15`: the missing include count is the measurable compatibility
boundary. See the JSON output for the ranked missing-header list.

## Ordered implementation gates

1. Import gameplay plus generated protobuf headers into an isolated `csgo` path.
2. Port required `CSTRIKE15` engine/public interfaces.
3. Build an offline dedicated server with Steam/GC/economy/UI excluded.
4. Build the client with a minimal VGUI/touch shell instead of Scaleform.
5. Prove Android ARM64 map load, spawn, movement, shooting and round restart.
