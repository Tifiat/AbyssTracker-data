import os
import json
import hashlib
from datetime import datetime, timezone
from urllib.request import urlopen, Request

import cv2
import numpy as np

# ====== CONFIG ======
N_CHARACTERS = int(os.environ.get("N_CHARACTERS", "30"))
N_WEAPONS = int(os.environ.get("N_WEAPONS", "30"))

ANIMEGAMEDATA_BASE = "https://raw.githubusercontent.com/DimbreathBot/AnimeGameData/master"
URL_AVATARS = f"{ANIMEGAMEDATA_BASE}/ExcelBinOutput/AvatarExcelConfigData.json"
URL_WEAPONS = f"{ANIMEGAMEDATA_BASE}/ExcelBinOutput/WeaponExcelConfigData.json"
URL_TEXTMAP_EN = f"{ANIMEGAMEDATA_BASE}/TextMap/TextMapEN.json"

ENKA_UI = "https://enka.network/ui"

OUT_DIR = "."  # root of repo
OUT_CHAR = os.path.join(OUT_DIR, "characters.json")
OUT_WEAP = os.path.join(OUT_DIR, "weapons.json")
OUT_HIDX_CHAR = os.path.join(OUT_DIR, "hash_index_characters.json")
OUT_HIDX_WEAP = os.path.join(OUT_DIR, "hash_index_weapons.json")
OUT_MANIFEST = os.path.join(OUT_DIR, "manifest.json")


# ====== UTILS ======
def http_get_json(url: str) -> object:
    req = Request(url, headers={"User-Agent": "AbyssTracker-data-bot/1.0"})
    with urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def http_get_bytes(url: str) -> bytes:
    req = Request(url, headers={"User-Agent": "AbyssTracker-data-bot/1.0"})
    with urlopen(req, timeout=60) as r:
        return r.read()


def dhash_hex(img_bgr: np.ndarray, hash_size: int = 8) -> str:
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    resized = cv2.resize(gray, (hash_size + 1, hash_size), interpolation=cv2.INTER_AREA)
    diff = resized[:, 1:] > resized[:, :-1]
    bits = diff.flatten()
    val = 0
    for b in bits:
        val = (val << 1) | int(bool(b))
    width = (hash_size * hash_size + 3) // 4
    return f"{val:0{width}x}"


def rarity_from_quality(q: str) -> int | None:
    # встречается в данных как QUALITY_ORANGE / QUALITY_PURPLE / QUALITY_BLUE / etc.
    m = {
        "QUALITY_ORANGE": 5,
        "QUALITY_PURPLE": 4,
        "QUALITY_BLUE": 3,
        "QUALITY_GREEN": 2,
        "QUALITY_WHITE": 1,
    }
    return m.get(q)


def weapon_type_short(wt: str) -> str:
    # WEAPON_SWORD_ONE_HAND -> Sword, etc.
    m = {
        "WEAPON_SWORD_ONE_HAND": "Sword",
        "WEAPON_CLAYMORE": "Claymore",
        "WEAPON_POLE": "Polearm",
        "WEAPON_CATALYST": "Catalyst",
        "WEAPON_BOW": "Bow",
    }
    return m.get(wt, wt or "Unknown")


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def save_json(path: str, obj: object):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


# ====== BUILDERS ======
def build_characters(avatars: list, textmap: dict) -> dict:
    out = {}
    # сортируем по id для стабильности
    avatars_sorted = sorted(avatars, key=lambda x: int(x.get("id", 0)))

    for a in avatars_sorted:
        if len(out) >= N_CHARACTERS:
            break

        _id = a.get("id")
        icon = a.get("iconName")  # важно!
        q = a.get("qualityType")
        wt = a.get("weaponType")
        name_hash = str(a.get("nameTextMapHash", ""))

        if not _id or not icon:
            continue

        # фильтр: берём только тех, у кого есть нормальная иконка персонажа
        if not str(icon).startswith("UI_AvatarIcon_"):
            continue

        rarity = rarity_from_quality(str(q))
        if rarity is None:
            continue

        name = textmap.get(name_hash, f"#{_id}")

        out[str(_id)] = {
            "name": name,
            "rarity": rarity,
            "element": None,  # добавим позже (через SkillDepot mapping)
            "weapon_type": weapon_type_short(str(wt)),
            "icon_name": str(icon),
        }

    return out


def build_weapons(weapons: list, textmap: dict) -> dict:
    out = {}
    weapons_sorted = sorted(weapons, key=lambda x: int(x.get("id", 0)))

    for w in weapons_sorted:
        if len(out) >= N_WEAPONS:
            break

        _id = w.get("id")
        icon = w.get("icon")  # UI_EquipIcon_...
        wt = w.get("weaponType")
        rank_level = w.get("rankLevel")  # 1..5 звёзд
        name_hash = str(w.get("nameTextMapHash", ""))

        if not _id or not icon:
            continue

        if not str(icon).startswith("UI_EquipIcon_"):
            continue

        try:
            rarity = int(rank_level)
        except Exception:
            continue

        name = textmap.get(name_hash, f"#{_id}")

        out[str(_id)] = {
            "name": name,
            "rarity": rarity,
            "type": weapon_type_short(str(wt)),
            "icon_name": str(icon),
        }

    return out

def to_bgr(img):
    if img is None:
        return None
    if len(img.shape) == 3 and img.shape[2] == 4:
        b, g, r, a = cv2.split(img)
        alpha = a.astype(np.float32) / 255.0
        bg = np.full_like(b, 180, dtype=np.uint8)  # серый фон
        # композит по каналу
        def comp(ch):
            return (ch.astype(np.float32) * alpha + bg.astype(np.float32) * (1 - alpha)).astype(np.uint8)
        return cv2.merge([comp(b), comp(g), comp(r)])
    if len(img.shape) == 2:
        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    return img

def build_hash_index(items: dict) -> dict:
    """
    items: {id: {"icon_name": "..."}}
    returns: {id: dhash_hex}
    """
    idx = {}
    for _id, meta in items.items():
        icon_name = meta.get("icon_name")
        if not icon_name:
            continue

        url = f"{ENKA_UI}/{icon_name}.png"
        try:
            png = http_get_bytes(url)
            img = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_UNCHANGED)
            if img is None:
                continue
            img = to_bgr(img)    
            idx[str(_id)] = dhash_hex(img)
        except Exception:
            # если какой-то конкретный ассет временно не доступен — просто пропускаем
            continue
    return idx


def main():
    print("Downloading AnimeGameData JSON...")
    avatars = http_get_json(URL_AVATARS)
    weapons = http_get_json(URL_WEAPONS)
    textmap = http_get_json(URL_TEXTMAP_EN)

    # textmap обычно {"123":"Name", ...} — оставляем как есть

    print("Building characters/weapons mini-pack...")
    chars = build_characters(avatars, textmap)
    weaps = build_weapons(weapons, textmap)

    print(f"Characters selected: {len(chars)} / N={N_CHARACTERS}")
    print(f"Weapons selected:    {len(weaps)} / N={N_WEAPONS}")

    print("Building hash indexes via Enka icons...")
    hidx_char = build_hash_index(chars)
    hidx_weap = build_hash_index(weaps)

    print(f"HashIndex characters: {len(hidx_char)}")
    print(f"HashIndex weapons:    {len(hidx_weap)}")

    save_json(OUT_CHAR, chars)
    save_json(OUT_WEAP, weaps)
    save_json(OUT_HIDX_CHAR, hidx_char)
    save_json(OUT_HIDX_WEAP, hidx_weap)

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    manifest = {
        "version": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "generated_at": now,
        "source": {
            "repo": "DimbreathBot/AnimeGameData",
            "avatars": URL_AVATARS,
            "weapons": URL_WEAPONS,
            "textmap_en": URL_TEXTMAP_EN,
        },
        "counts": {
            "characters": len(chars),
            "weapons": len(weaps),
            "hash_characters": len(hidx_char),
            "hash_weapons": len(hidx_weap),
        },
        "files": {},  # заполним после записи
    }

    for p in [OUT_CHAR, OUT_WEAP, OUT_HIDX_CHAR, OUT_HIDX_WEAP]:
        manifest["files"][os.path.basename(p)] = {
            "sha256": sha256_file(p)
        }

    save_json(OUT_MANIFEST, manifest)
    print("Done. Wrote:", OUT_MANIFEST)


if __name__ == "__main__":
    main()
