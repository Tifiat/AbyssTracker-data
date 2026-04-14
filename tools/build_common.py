import json
import hashlib
from typing import Optional

import cv2
import numpy as np
from urllib.request import urlopen, Request


def http_get_json(url: str) -> object:
    req = Request(url, headers={"User-Agent": "AbyssTracker-data-bot/1.0"})
    with urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def http_get_bytes(url: str) -> bytes:
    req = Request(url, headers={"User-Agent": "AbyssTracker-data-bot/1.0"})
    with urlopen(req, timeout=60) as r:
        return r.read()


def save_json(path: str, obj: object):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def rarity_from_quality(q: str) -> Optional[int]:
    m = {
        "QUALITY_ORANGE": 5,
        "QUALITY_PURPLE": 4,
        "QUALITY_BLUE": 3,
        "QUALITY_GREEN": 2,
        "QUALITY_WHITE": 1,
    }
    return m.get(q)


def weapon_type_short(wt: str) -> Optional[str]:
    m = {
        "WEAPON_SWORD_ONE_HAND": "Sword",
        "WEAPON_CLAYMORE": "Claymore",
        "WEAPON_POLE": "Polearm",
        "WEAPON_CATALYST": "Catalyst",
        "WEAPON_BOW": "Bow",
    }
    return m.get(wt)


def normalize_element(elem: Optional[str]) -> Optional[str]:
    m = {
        "Fire": "Pyro",
        "Water": "Hydro",
        "Wind": "Anemo",
        "Electric": "Electro",
        "Grass": "Dendro",
        "Rock": "Geo",
        "Ice": "Cryo",
    }
    if not elem:
        return None
    return m.get(str(elem))


def textmap_lookup(textmap: dict, key) -> Optional[str]:
    if key is None:
        return None

    value = textmap.get(str(key))
    if value is None:
        value = textmap.get(key)

    if value is None:
        return None

    value = str(value).strip()
    if not value:
        return None
    if value.startswith("#"):
        return None

    return value


def fallback_name_from_avatar_icon(icon_name: str) -> str:
    prefix = "UI_AvatarIcon_"
    name = str(icon_name)
    if name.startswith(prefix):
        name = name[len(prefix):]
    return name.replace("_", " ").strip() or str(icon_name)


def fallback_name_from_weapon_icon(icon_name: str) -> str:
    prefix = "UI_EquipIcon_"
    name = str(icon_name)
    if name.startswith(prefix):
        name = name[len(prefix):]
    return name.replace("_", " ").strip() or str(icon_name)


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


def to_bgr(img):
    if img is None:
        return None

    if len(img.shape) == 3 and img.shape[2] == 4:
        b, g, r, a = cv2.split(img)
        alpha = a.astype(np.float32) / 255.0
        bg = np.full_like(b, 180, dtype=np.uint8)

        def comp(ch):
            return (
                ch.astype(np.float32) * alpha
                + bg.astype(np.float32) * (1 - alpha)
            ).astype(np.uint8)

        return cv2.merge([comp(b), comp(g), comp(r)])

    if len(img.shape) == 2:
        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

    return img
