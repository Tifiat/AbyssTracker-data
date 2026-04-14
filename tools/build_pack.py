import json
import os
from datetime import datetime, timezone

import cv2
import numpy as np

from build_common import (
    http_get_json,
    http_get_bytes,
    save_json,
    sha256_file,
    dhash_hex,
    to_bgr,
)
from build_characters import build_skill_maps, build_characters
from build_weapons import build_weapons

# ====== CONFIG ======
N_CHARACTERS = int(os.environ.get("N_CHARACTERS", "300"))

ANIMEGAMEDATA_BASE = "https://raw.githubusercontent.com/DimbreathBot/AnimeGameData/master"
URL_AVATARS = f"{ANIMEGAMEDATA_BASE}/ExcelBinOutput/AvatarExcelConfigData.json"
URL_AVATAR_SKILL_DEPOTS = f"{ANIMEGAMEDATA_BASE}/ExcelBinOutput/AvatarSkillDepotExcelConfigData.json"
URL_AVATAR_SKILLS = f"{ANIMEGAMEDATA_BASE}/ExcelBinOutput/AvatarSkillExcelConfigData.json"
URL_WEAPONS = f"{ANIMEGAMEDATA_BASE}/ExcelBinOutput/WeaponExcelConfigData.json"
URL_TEXTMAP_EN = f"{ANIMEGAMEDATA_BASE}/TextMap/TextMapEN.json"

ENKA_UI = "https://enka.network/ui"

OUT_DIR = "."
OUT_CHAR = os.path.join(OUT_DIR, "characters.json")
OUT_WEAP = os.path.join(OUT_DIR, "weapons.json")
OUT_HIDX_CHAR = os.path.join(OUT_DIR, "hash_index_characters.json")
OUT_HIDX_WEAP = os.path.join(OUT_DIR, "hash_index_weapons.json")
OUT_MANIFEST = os.path.join(OUT_DIR, "manifest.json")
OUT_ENKA_ICON_STATUS = os.path.join(OUT_DIR, "enka_icon_status.json")


def load_json_or_default(path: str, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def fetch_enka_icon_image(icon_name: str):
    url = f"{ENKA_UI}/{icon_name}.png"
    png = http_get_bytes(url)
    img = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_UNCHANGED)
    if img is None:
        return None
    return to_bgr(img)


def get_enka_icon_status(icon_name: str, status_cache: dict) -> str:
    cached = status_cache.get(icon_name)
    if cached in ("exists", "missing"):
        return cached

    try:
        img = fetch_enka_icon_image(icon_name)
        status = "exists" if img is not None else "missing"
    except Exception:
        status = "missing"

    status_cache[icon_name] = status
    return status


def filter_items_by_enka_icon(items: dict, status_cache: dict, label: str) -> dict:
    out = {}
    total = len(items)

    for i, (_id, meta) in enumerate(items.items(), start=1):
        icon_name = meta.get("icon_name")
        if not icon_name:
            continue

        status = get_enka_icon_status(str(icon_name), status_cache)
        if status == "exists":
            out[str(_id)] = meta

        if i % 50 == 0 or i == total:
            print(f"[{label}] Enka checked: {i}/{total}, kept={len(out)}")

    return out


def build_hash_index(items: dict) -> dict:
    idx = {}
    total = len(items)

    for i, (_id, meta) in enumerate(items.items(), start=1):
        icon_name = meta.get("icon_name")
        if not icon_name:
            continue

        try:
            img = fetch_enka_icon_image(str(icon_name))
            if img is None:
                continue
            idx[str(_id)] = dhash_hex(img)
        except Exception:
            continue

        if i % 50 == 0 or i == total:
            print(f"[hash] processed: {i}/{total}, built={len(idx)}")

    return idx


def main():
    print("Downloading AnimeGameData JSON...")
    avatars = http_get_json(URL_AVATARS)
    avatar_skill_depots = http_get_json(URL_AVATAR_SKILL_DEPOTS)
    avatar_skills = http_get_json(URL_AVATAR_SKILLS)
    weapons = http_get_json(URL_WEAPONS)
    textmap = http_get_json(URL_TEXTMAP_EN)

    depot_map, skill_map = build_skill_maps(avatar_skill_depots, avatar_skills)

    print("Building characters pack...")
    chars = build_characters(avatars, textmap, depot_map, skill_map)

    print("Building raw weapons candidates...")
    weaps = build_weapons(weapons, textmap)
    print(f"Raw weapons candidates: {len(weaps)}")

    status_cache = load_json_or_default(OUT_ENKA_ICON_STATUS, {})

    print("Filtering weapons by Enka icon availability...")
    weaps = filter_items_by_enka_icon(weaps, status_cache, label="weapons")
    print(f"Weapons after Enka filter: {len(weaps)}")

    print(f"Characters selected: {len(chars)} / N={N_CHARACTERS}")
    print(f"Weapons selected:    {len(weaps)}")

    print("Building hash indexes via Enka icons...")
    hidx_char = build_hash_index(chars)
    hidx_weap = build_hash_index(weaps)

    print(f"HashIndex characters: {len(hidx_char)}")
    print(f"HashIndex weapons:    {len(hidx_weap)}")

    save_json(OUT_CHAR, chars)
    save_json(OUT_WEAP, weaps)
    save_json(OUT_HIDX_CHAR, hidx_char)
    save_json(OUT_HIDX_WEAP, hidx_weap)
    save_json(OUT_ENKA_ICON_STATUS, status_cache)

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    manifest = {
        "version": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "generated_at": now,
        "source": {
            "repo": "DimbreathBot/AnimeGameData",
            "avatars": URL_AVATARS,
            "avatar_skill_depots": URL_AVATAR_SKILL_DEPOTS,
            "avatar_skills": URL_AVATAR_SKILLS,
            "weapons": URL_WEAPONS,
            "textmap_en": URL_TEXTMAP_EN,
        },
        "counts": {
            "characters": len(chars),
            "weapons": len(weaps),
            "hash_characters": len(hidx_char),
            "hash_weapons": len(hidx_weap),
        },
        "files": {},
    }

    for p in [OUT_CHAR, OUT_WEAP, OUT_HIDX_CHAR, OUT_HIDX_WEAP, OUT_ENKA_ICON_STATUS]:
        manifest["files"][os.path.basename(p)] = {
            "sha256": sha256_file(p)
        }

    save_json(OUT_MANIFEST, manifest)
    print("Done. Wrote:", OUT_MANIFEST)


if __name__ == "__main__":
    main()
