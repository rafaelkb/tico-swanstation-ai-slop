# Cores

Copies of the ticohq modules, one folder each, next to the PlayStation module
(SwanStation) at the root of the repository.

| Folder | Module | Copied from | Build script |
|---|---|---|---|
| `snes` | SNES (Snes9x) | ticohq/tico-snes9x `f820018` | `build_snes9x_nro.sh` |
| `nes` | NES (FCEUmm) | ticohq/tico-fceumm `79e965c` | `build_fceumm_nro.sh` |
| `megadrive` | Mega Drive (Genesis Plus GX) | ticohq/tico-genesisplusgx `c0e0d83` | `build_genesis_plus_gx_nro.sh` |
| `n64` | Nintendo 64 (Mupen64Plus) | ticohq/tico-mupen64plus `a2278c7` | `build_mupen64plus_nro.sh` |
| `saturn` | Sega Saturn (YabaSanshiro) | ticohq/tico-yabasanshiro `56f8fd4` | `build_yabasanshiro_nro.sh` |

Each script runs from its own folder, in the `danfromtico/switch-dev` image;
`.github/workflows/build.yml` builds all of them on every push.

What differs from the copies:

- The shader presets are in `shared/shaders` at the root (see its README), for
  every module but Saturn, which has no slang shader chain.
- The cores' own TV filters (`snes9x_blargg`, `fceumm_ntsc_filter`,
  `genesis_plus_gx_blargg_ntsc_filter`) are no longer settings: they are
  shaders, under Shaders, and the core's filter stays off. A saved setting
  that had one on picks the matching shader the first time the module runs.
- The submodules of each copy are submodules of this repository
  (`.gitmodules` at the root).
- `saturn` leaves out Windows libraries (`*.lib`, `*.pdb`) and the iOS
  MetalANGLE framework, 385 MB the Switch build does not use.
- `.gitattributes` here keeps every file byte for byte.
