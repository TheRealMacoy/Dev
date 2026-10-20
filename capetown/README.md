# Orbit to Cape Town

A 24-second, 1080p60 reel that starts in orbit, circles the night side of Earth
into an orbital sunrise, locks onto Cape Town and spirals down through the
atmosphere. It lands at the exact spot the drone footage was shot from, then
dissolves into that footage with tracked motion graphics.

**Watch:** [`orbit_to_cape_town.mp4`](orbit_to_cape_town.mp4)

| Time | What happens |
| --- | --- |
| 0:00 | Earth's night side, ringed by the atmosphere with the sun behind it; city lights across the Americas |
| 0:02 | Orbital sunrise: the sun breaks the limb with a lens-flare burst |
| 0:03 | Graticule and scan line as the HUD surveys Africa |
| 0:05 | Reticle locks onto Cape Town, 33.9249° S 18.4241° E |
| 0:07 | Spiral descent: the heading turns 169° as altitude drops from 15,500 km |
| 0:09 | Punch through the cloud deck |
| 0:10 | 10 m Sentinel-2 imagery draped over real elevation; Table Mountain rises out of the ground |
| 0:13 | Lands at the drone's real position over Green Point, then dissolves into the footage |
| 0:14 | Tracked callouts: Table Mountain, Lion's Head, Devil's Peak, Signal Hill, the stadium, the Waterfront |
| 0:19 | "CAPE TOWN" set into the sky, tucked behind Table Mountain |

## How it's made

- **Globe**: three.js on a 1024×512 sphere with a custom shader: day/night
  textures, city lights, ocean specular, drifting clouds, terminator glow, a
  graticule, aerial haze. The atmosphere shell is a scattering-style shader that
  turns into a blue sky once the camera is inside it.
- **Real imagery**: a Sentinel-2 L2A true-colour scene (30 March 2024, 0.004%
  cloud) reprojected from UTM 34S to lat/lon at two levels of detail (about
  30 m and 6 m per pixel) and blended into the globe.
- **Terrain**: AWS Terrarium elevation tiles become a curvature-correct
  900×700 mesh of the Cape Town bowl, textured with the same imagery.
- **The landing**: the drone's position (33.8865° S, 18.4035° E, about 540 m
  up, heading 168.75°) was solved from the bearings of Lion's Head, Devil's Peak
  and the stadium in the first video frame. The camera ends exactly there.
- **Motion graphics**: a HUD (altitude ladder, heading tape, nadir
  coordinates, status), a lock-on reticle, a lens flare with ghosts,
  cloud puffs, landmark callouts pinned with patch phase-correlation tracking,
  and a sky-keyed title.
- **Sound**: synthesized from scratch: space drone, sunrise swell, lock-on
  beeps, wind and rumble on the dive, then a 122 BPM afro-house groove.

## Build

Needs Node with Playwright (Chromium), Python 3 with NumPy, Pillow, tifffile,
imagecodecs and pyproj, and ffmpeg.

```sh
./build.sh path/to/cape-town-drone.mov
```

- `prepare.py`: downloads and preprocesses the textures, imagery and elevation into `data/`
- `track.py`: tracks landmark anchors through the footage
- `reel.js` / `index.html`: the renderer (`renderFrame(frame)`)
- `render.mjs`: serves the page and renders frames across headless Chromium workers
- `audio.py`: the soundtrack

Imagery: contains modified Copernicus Sentinel data 2024. Elevation: Mapzen
Terrarium tiles (AWS Open Data). Globe textures: three.js examples (NASA Blue Marble).
