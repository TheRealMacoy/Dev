"""Downloads and preprocesses every asset the renderer needs into data/.

- Globe textures (day, night, clouds/roughness) from the three.js examples
- Sentinel-2 L2A true colour (10 m) of the Cape Peninsula, reprojected from
  UTM 34S to lat/lon at two levels of detail
- Terrarium elevation tiles (AWS open data) for Table Mountain's terrain mesh

Usage: python3 prepare.py [path/to/TCI.tif]
"""
import io
import json
import math
import os
import sys
import urllib.request

import numpy as np
import tifffile
from PIL import Image
from pyproj import Transformer

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
os.makedirs(DATA, exist_ok=True)

THREE_TEX = "https://raw.githubusercontent.com/mrdoob/three.js/dev/examples/textures/planets/"
S2_TCI = ("https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/"
          "34/H/BH/2024/3/S2B_34HBH_20240330_0_L2A/TCI.tif")
TERRARIUM = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"

# Regions, as (lon0, lon1, lat0 south, lat1 north)
REGIONAL = (17.80, 18.90, -34.38, -33.42)
CITY = (18.30, 18.56, -34.06, -33.86)


def fetch(url, path=None):
    if path and os.path.exists(path):
        return path
    print("fetch", url)
    with urllib.request.urlopen(url, timeout=600) as r:
        data = r.read()
    if path:
        with open(path, "wb") as f:
            f.write(data)
        return path
    return data


def globe_textures():
    for name in ("earth_day_4096.jpg", "earth_night_4096.jpg", "earth_bump_roughness_clouds_4096.jpg"):
        fetch(THREE_TEX + name, os.path.join(DATA, name))


def grade(rgb):
    """Lift the flat L2A true colour into something closer to the globe texture."""
    x = rgb.astype(np.float32) / 255
    x = np.clip((x - 0.02) / 0.9, 0, 1) ** 0.82
    lum = x @ np.array([0.299, 0.587, 0.114], np.float32)
    x = lum[..., None] + (x - lum[..., None]) * 1.25
    x = 0.5 + (x - 0.5) * 1.08
    return np.clip(x * 255, 0, 255).astype(np.uint8)


def reproject(tci, region, width, height, feather):
    lon0, lon1, lat0, lat1 = region
    lons = np.linspace(lon0, lon1, width)
    lats = np.linspace(lat1, lat0, height)  # north at the top
    LON, LAT = np.meshgrid(lons, lats)
    to_utm = Transformer.from_crs("EPSG:4326", "EPSG:32734", always_xy=True)
    E, N = to_utm.transform(LON, LAT)
    col = (E - 199980.0) / 10.0 - 0.5
    row = (6300040.0 - N) / 10.0 - 0.5
    c0 = np.clip(np.floor(col).astype(int), 0, tci.shape[1] - 2)
    r0 = np.clip(np.floor(row).astype(int), 0, tci.shape[0] - 2)
    fc = np.clip(col - c0, 0, 1)[..., None]
    fr = np.clip(row - r0, 0, 1)[..., None]
    out = np.zeros((height, width, 3), np.float32)
    for dr, dc, w in ((0, 0, (1 - fr) * (1 - fc)), (0, 1, (1 - fr) * fc), (1, 0, fr * (1 - fc)), (1, 1, fr * fc)):
        out += tci[r0 + dr, c0 + dc].astype(np.float32) * w
    valid = (tci[r0, c0].max(axis=-1) > 0) & (col >= 0) & (row >= 0)
    # feather the borders so the patch melts into whatever is beneath it
    u = np.minimum(np.arange(width), np.arange(width)[::-1]) / (width * feather)
    v = np.minimum(np.arange(height), np.arange(height)[::-1]) / (height * feather)
    edge = np.clip(np.minimum(u[None, :], v[:, None]), 0, 1)
    edge = edge * edge * (3 - 2 * edge)
    alpha = (valid * edge * 255).astype(np.uint8)
    rgb = grade(out.astype(np.uint8))
    return np.dstack([rgb, alpha])


def sentinel(tci_path):
    tci_path = tci_path or fetch(S2_TCI, os.path.join(DATA, "TCI.tif"))
    print("reading", tci_path)
    tci = tifffile.imread(tci_path)
    for name, region, w, h, feather in (("s2_regional.png", REGIONAL, 4096, 4096, 0.12),
                                        ("s2_city.png", CITY, 4096, 3200, 0.10)):
        img = reproject(tci, region, w, h, feather)
        Image.fromarray(img, "RGBA").save(os.path.join(DATA, name), optimize=False, compress_level=3)
        print("wrote", name)


def lonlat_to_tile(lon, lat, z):
    n = 2 ** z
    x = (lon + 180) / 360 * n
    y = (1 - np.arcsinh(np.tan(np.radians(lat))) / np.pi) / 2 * n
    return x, y


def elevation(z=13, out_w=1024, out_h=800):
    lon0, lon1, lat0, lat1 = CITY
    x0, y0 = lonlat_to_tile(lon0, lat1, z)
    x1, y1 = lonlat_to_tile(lon1, lat0, z)
    tx0, ty0, tx1, ty1 = int(x0), int(y0), int(x1), int(y1)
    mosaic = np.zeros(((ty1 - ty0 + 1) * 256, (tx1 - tx0 + 1) * 256), np.float32)
    for ty in range(ty0, ty1 + 1):
        for tx in range(tx0, tx1 + 1):
            png = fetch(TERRARIUM.format(z=z, x=tx, y=ty), os.path.join(DATA, f"terr_{z}_{tx}_{ty}.png"))
            a = np.asarray(Image.open(png).convert("RGB")).astype(np.float32)
            h = a[..., 0] * 256 + a[..., 1] + a[..., 2] / 256 - 32768
            mosaic[(ty - ty0) * 256:(ty - ty0 + 1) * 256, (tx - tx0) * 256:(tx - tx0 + 1) * 256] = h
    lons = np.linspace(lon0, lon1, out_w)
    lats = np.linspace(lat1, lat0, out_h)
    LON, LAT = np.meshgrid(lons, lats)
    X, Y = lonlat_to_tile(LON, LAT, z)
    px = (X - tx0) * 256 - 0.5
    py = (Y - ty0) * 256 - 0.5
    c0 = np.clip(np.floor(px).astype(int), 0, mosaic.shape[1] - 2)
    r0 = np.clip(np.floor(py).astype(int), 0, mosaic.shape[0] - 2)
    fc, fr = px - c0, py - r0
    hm = (mosaic[r0, c0] * (1 - fr) * (1 - fc) + mosaic[r0, c0 + 1] * (1 - fr) * fc
          + mosaic[r0 + 1, c0] * fr * (1 - fc) + mosaic[r0 + 1, c0 + 1] * fr * fc)
    hm = np.maximum(hm, 0).astype("<f4")
    hm.tofile(os.path.join(DATA, "height_city.bin"))
    with open(os.path.join(DATA, "meta.json"), "w") as f:
        json.dump({"regional": REGIONAL, "city": CITY, "height": {"w": out_w, "h": out_h, "max": float(hm.max())}}, f)
    print("wrote height_city.bin, max elevation", hm.max())


if __name__ == "__main__":
    globe_textures()
    elevation()
    sentinel(sys.argv[1] if len(sys.argv) > 1 else None)
