import os
import json
import hashlib
from datetime import datetime, timezone
from urllib.request import urlopen, Request

import cv2
import numpy as np

# ====== CONFIG ======
N_CHARACTERS = int(os.environ.get("N_CHARACTERS", "300"))
N_WEAPONS = int(os.environ.get("N_WEAPONS", "300"))

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
    m = {
        "QUALITY_ORANGE": 5,
        "QUALITY_PURPLE": 4,
        "QUALITY_BLUE": 3,
        "QUALITY_GREEN": 2,
        "QUALITY_WHITE": 1,
    }
    return m.get(q)


def weapon_type_short(wt: str) -> str | None:
    m = {
        "WEAPON_SWORD_ONE_HAND": "Sword",
        "WEAPON_CLAYMORE": "Claymore",
        "WEAPON_POLE": "Polearm",
        "WEAPON_CATALYST": "Catalyst",
        "WEAPON_BOW": "Bow",
    }
    return m.get(wt)


def normalize_element(elem: str | None) -> str | None:
    m = {
        "Fire": "Pyro",
        "Water": "Hydro",
        "Wind": "Anemo",
        "Electric": "Electro",
        "Grass": "Dendro",
        "Rock": "Geo",
        "Ice": "Cryo",
    }
    if elem is None:
        return None
    return m.get(str(elem), None)


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def save_json(path: str, obj: object):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def textmap_lookup(textmap: dict, key) -> str | None:
    if key is None:
        return None

    s = str(key)
    value = textmap.get(s)
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


def build_skill_maps(skill_depots: list, avatar_skills: list) -> tuple[dict, dict]:
    depot_map = {}
    skill_map = {}

    for d in skill_depots:
        depot_id = d.get("id")
        if depot_id:
            depot_map[int(depot_id)] = d

    for s in avatar_skills:
        skill_id = s.get("id")
        if skill_id:
            skill_map[int(skill_id)] = s

    return depot_map, skill_map


def infer_element_from_skill_depot(skill_depot_id, depot_map: dict, skill_map: dict) -> str | None:
    if not skill_depot_id:
        return None

    depot = depot_map.get(int(skill_depot_id))
    if not depot:
        return None

    energy_skill_id = depot.get("energySkill")
    if not energy_skill_id:
        return None

    skill = skill_map.get(int(energy_skill_id))
    if not skill:
        return None

    return normalize_element(skill.get("costElemType"))


def is_playable_avatar_record(a: dict) -> bool:
    icon = str(a.get("iconName", ""))
    use_type = str(a.get("useType", ""))
    avatar_identity_type = str(a.get("avatarIdentityType", ""))

    if not icon.startswith("UI_AvatarIcon_"):
        return False

    if "_Side_" in icon:
        return False

    if use_type != "AVATAR_FORMAL":
        return False

    if avatar_identity_type not in {"AVATAR_IDENTITY_NORMAL", "AVATAR_IDENTITY_MASTER"}:
        return False

    return True


def is_suspicious_avatar_id(_id: int) -> bool:
    return (
        10000900 <= _id <= 10000999
        or 11000000 <= _id <= 11999999
    )


def choose_best_character_candidate(candidates: list[dict]) -> dict:
    def score(item: dict):
        _id = int(item["id"])
        return (
            1 if item["name"] else 0,
            1 if item["element"] else 0,
            1 if item["weapon_type"] else 0,
            1 if item["rarity"] is not None else 0,
            0 if is_suspicious_avatar_id(_id) else 1,
            -_id,
        )

    return sorted(candidates, key=score, reverse=True)[0]


# ====== BUILDERS ======
def build_characters(avatars: list, textmap: dict, depot_map: dict, skill_map: dict) -> dict:
    prepared = []

    avatars_sorted = sorted(avatars, key=lambda x: int(x.get("id", 0)))

    for a in avatars_sorted:
        _id = a.get("id")
        icon = a.get("iconName")
        q = a.get("qualityType")
        wt = a.get("weaponType")
        name_hash = a.get("nameTextMapHash")
        skill_depot_id = a.get("skillDepotId")

        if not _id or not icon:
            continue

        if not is_playable_avatar_record(a):
            continue

        rarity = rarity_from_quality(str(q))
        weapon_type = weapon_type_short(str(wt))
        name = textmap_lookup(textmap, name_hash)
        element = infer_element_from_skill_depot(skill_depot_id, depot_map, skill_map)

        # Все поля обязательны
        if not name:
            continue
        if rarity is None:
            continue
        if not weapon_type:
            continue
        if not element:
            continue

        prepared.append({
            "id": int(_id),
            "name": name,
            "rarity": rarity,
            "element": element,
            "weapon_type": weapon_type,
            "icon_name": str(icon),
        })

    # Дедуп по icon_name
    grouped = {}
    for item in prepared:
        grouped.setdefault(item["icon_name"], []).append(item)

    deduped = []
    for icon_name, group in grouped.items():
        deduped.append(choose_best_character_candidate(group))

    deduped.sort(key=lambda x: x["id"])

    out = {}
    for item in deduped[:N_CHARACTERS]:
        _id = str(item["id"])
        out[_id] = {
            "name": item["name"],
            "rarity": item["rarity"],
            "element": item["element"],
            "weapon_type": item["weapon_type"],
            "icon_name": item["icon_name"],
        }

    return out


def build_weapons(weapons: list, textmap: dict) -> dict:
    out = {}
    weapons_sorted = sorted(weapons, key=lambda x: int(x.get("id", 0)))

    for w in weapons_sorted:
        if len(out) >= N_WEAPONS:
            break

        _id = w.get("id")
        icon = w.get("icon")
        wt = w.get("weaponType")
        rank_level = w.get("rankLevel")
        name_hash = w.get("nameTextMapHash")

        if not _id or not icon:
            continue

        if not str(icon).startswith("UI_EquipIcon_"):
            continue

        try:
            rarity = int(rank_level)
        except Exception:
            continue

        weapon_type = weapon_type_short(str(wt))
        name = textmap_lookup(textmap, name_hash)

        if not name:
            continue
        if not weapon_type:
            continue
        if rarity < 1 or rarity > 5:
            continue

        out[str(_id)] = {
            "name": name,
            "rarity": rarity,
            "type": weapon_type,
            "icon_name": str(icon),
        }

    return out


def build_hash_index(items: dict) -> dict:
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
            continue

    return idx


def main():
    print("Downloading AnimeGameData JSON...")
    avatars = http_get_json(URL_AVATARS)
    avatar_skill_depots = http_get_json(URL_AVATAR_SKILL_DEPOTS)
    avatar_skills = http_get_json(URL_AVATAR_SKILLS)
    weapons = http_get_json(URL_WEAPONS)
    textmap = http_get_json(URL_TEXTMAP_EN)

    depot_map, skill_map = build_skill_maps(avatar_skill_depots, avatar_skills)

    print("Building clean characters/weapons pack...")
    chars = build_characters(avatars, textmap, depot_map, skill_map)
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

    for p in [OUT_CHAR, OUT_WEAP, OUT_HIDX_CHAR, OUT_HIDX_WEAP]:
        manifest["files"][os.path.basename(p)] = {
            "sha256": sha256_file(p)
        }

    save_json(OUT_MANIFEST, manifest)
    print("Done. Wrote:", OUT_MANIFEST)


if __name__ == "__main__":
    main()
