"""Populate the database with sample DJs, venues, and bookings on first run."""

import json
from datetime import datetime, timedelta

import aiosqlite

from backend.config import settings

DATABASE_PATH = settings.DATABASE_PATH


def _j(obj) -> str:
    """Serialise a Python object to a JSON string for SQLite TEXT columns."""
    return json.dumps(obj)


# ── Sample DJs ───────────────────────────────────────────────────────────────

SEED_DJS = [
    {
        "id": "amara-voss",
        "name": "AMARA VOSS",
        "email": "amara.voss@nocturne.test",
        "tagline": "Melodic Techno / Berlin",
        "genres": _j(["Melodic Techno", "Deep House"]),
        "bio": (
            "Redefining the festival landscape with cinematic soundscapes that blur "
            "the lines between reality and simulation. Amara Voss creates immersive "
            "sonic journeys that have headlined at Tomorrowland, Berghain, and "
            "Movement Detroit."
        ),
        "image_url": "https://lh3.googleusercontent.com/aida-public/AB6AXuAF2SegbBrIoE668MsEhgP7RODYhXx7fUehCaMfQI_ULvVn8MktyKlUp4txpJ9espNr5rhlg_NEd5kn3efCL21z_tQDZ-SQPxkzu8k6fiK1cijX67Ne9FcY_44pAjpxhvfLF_aGirjNLL41mlk3-4rweXkA_78HtIESUJezu_irQ76JguApXUhHu0kp0TorNVN_GJflPqwP5SD2F2LASjummJuTw-Fy7sFsV6vztrY2a37LUwAJOU6qSRuUm9dW9UzhBjoat9ILtFU",
        "bpm_low": 126,
        "bpm_high": 134,
        "setup": "hybrid",
        "fee_tier": "elite",
        "fee_from": 3500,
        "badge": "Featured Artist",
        "vibe_keywords": _j(["ethereal", "cinematic", "festival-headliner"]),
        "tech_rider": _j({
            "mixer": "Pioneer DJM-V10",
            "players": "4x Pioneer CDJ-3000",
            "monitoring": "2x d&b Audiotechnik M4",
            "external_fx": "Eventide H9 Max",
        }),
        "availability": _j(["2026-04-12", "2026-04-19", "2026-05-03"]),
        "soundcloud_url": "https://soundcloud.com/example/amara-voss",
    },
    {
        "id": "kaleidos",
        "name": "KALEIDOS",
        "email": "kaleidos@nocturne.test",
        "tagline": "Minimal / Dub",
        "genres": _j(["Minimal Techno", "Dub Techno"]),
        "bio": (
            "Kaleidos weaves hypnotic layers of stripped-back rhythm and deep "
            "sub-bass, crafting sets that unfold like slow-burning narratives on "
            "underground dance floors across Europe and South America."
        ),
        "image_url": "https://lh3.googleusercontent.com/aida-public/AB6AXuA1tdJm3Nn3Gv_pBO8i7sRmEK_8K3AyJ-6Z26WUqlWBxaer4_KpYMn6-BrOU05Apbt5JDvtAjaOyGbOem1aaH6O63YVb5s2bKqPvf6HnmuvlQgntXuyiJIH9HGpSz3wpuYLsAWagGPKotedw4xxHyRUoVgbvRuC1a22Ibb7kE3n21jynikuCnD1M21HTaCjNV9kq_sWQEyj5dFV1MwN6nTFMKjJIcouiHBMb5tDgP_GCwCrAK6Y3It-ky5TA8XUcHV7_5F66gWnCAM",
        "bpm_low": 118,
        "bpm_high": 126,
        "setup": "vinyl",
        "fee_tier": "premium",
        "fee_from": 1800,
        "badge": None,
        "vibe_keywords": _j(["hypnotic", "stripped-back", "underground"]),
        "tech_rider": _j({
            "mixer": "Allen & Heath Xone:96",
            "players": "2x Technics SL-1210MK7",
            "monitoring": "1x Pioneer RM-07",
            "external_fx": "None required",
        }),
        "availability": _j(["2026-04-18", "2026-04-25"]),
        "soundcloud_url": None,
    },
    {
        "id": "synesthesia",
        "name": "SYNESTHESIA",
        "email": "synesthesia@nocturne.test",
        "tagline": "House / Groove",
        "genres": _j(["House", "Deep Groove", "Soulful House"]),
        "bio": (
            "Synesthesia believes in the raw power of groove. With roots in the "
            "Chicago house tradition, their sets are warm, rhythmic, and deeply "
            "connected to the dance floor."
        ),
        "image_url": "https://lh3.googleusercontent.com/aida-public/AB6AXuDHXJiNUjdi6NXS8scELN_SeYYrJb6O1fRYOlzKodPLz1fGj0qAS6Ebn8YwPfOwbQbA5Os7wRDLoCPoyVfm9ygK2auy22aL8JlJOiVlLj-yN3MLN-Lxtdw6jgWIX0uz53GhXRhhLu4eeWIzql_SQdLm0f1F4D-fL-rl8Ag6Qxe4lGqgFTpYql_vhCcQJPTogxjfkUPB4ddr9Q1Gh14i91_1ZLQBvbNsMBt2uWJ6OXS4trnqCvBxuOHfp7gdZGPKvy96Snb2xZYk6j8",
        "bpm_low": 120,
        "bpm_high": 128,
        "setup": "digital",
        "fee_tier": "premium",
        "fee_from": 2000,
        "badge": None,
        "vibe_keywords": _j(["warm", "groove", "soulful"]),
        "tech_rider": _j({
            "mixer": "Pioneer DJM-900NXS2",
            "players": "2x Pioneer CDJ-3000",
            "monitoring": "1x Pioneer RM-07",
            "external_fx": "None required",
        }),
        "availability": _j(["2026-04-11", "2026-04-26"]),
        "soundcloud_url": None,
    },
    {
        "id": "soren-orsk",
        "name": "SOREN ORSK",
        "email": "soren.orsk@nocturne.test",
        "tagline": "Deep Melodic / Industrial",
        "genres": _j(["Deep Melodic", "Industrial Techno"]),
        "bio": (
            "Soren Orsk's sound is forged in the crucible of Berlin's industrial "
            "underground — a relentless collision of percussive force and haunting "
            "melodic fragments that commands attention."
        ),
        "image_url": "https://lh3.googleusercontent.com/aida-public/AB6AXuCOIrh7IfYfaqEXKQrW4kqKR2KEbAH6KOA9zb2OsyCXqal9IycJ1kv8nqpbZoi6HK9uiZQc0_Xx7HeH6ZoPVMEntTI0R2osLuM4kU2p1WT7rRwkNnoonk6zuNZHjorFYHLCLK5XZ1-wXYVeZJ2X6oR2lzzy98OKIkZLFjH0F6sJJdwQ3YuwmOFcnFf_1lh87RVg-jvtaH65QNVTSvplCy0MCBJvTZVPRnFV9KTc5vr0lQop4dNc3eaXmc5S3ydneU1VbHYUkgGeMX8",
        "bpm_low": 128,
        "bpm_high": 136,
        "setup": "hybrid",
        "fee_tier": "premium",
        "fee_from": 2400,
        "badge": "PRO",
        "vibe_keywords": _j(["dark", "driving", "industrial"]),
        "tech_rider": _j({
            "mixer": "Pioneer DJM-V10",
            "players": "4x Pioneer CDJ-3000",
            "monitoring": "2x Pioneer RM-07",
            "external_fx": "Strymon BigSky",
        }),
        "availability": _j(["2026-04-17", "2026-05-01"]),
        "soundcloud_url": None,
    },
    {
        "id": "evelina-voss",
        "name": "EVELINA VOSS",
        "email": "evelina.voss@nocturne.test",
        "tagline": "Progressive House / Peak Time",
        "genres": _j(["Progressive House", "Peak Time Techno"]),
        "bio": (
            "Evelina Voss builds emotional arcs that explode into euphoric peak-time "
            "moments. Known for vinyl-only sets that showcase an impeccable ear for "
            "selection and an unwavering connection to the crowd."
        ),
        "image_url": "https://lh3.googleusercontent.com/aida-public/AB6AXuDAXkAQmR0tnBmd1WyBdbigiRtK70NMvHSgKNpCLfTZLwxEk_u_IEQM75msCQMayHo0WkNh5b26qVQNG_psq5ZHPG2LBcRdboD73rzChyRXGsYynLh0-n4quKn81QbvKmcSPdkQUggVE6b1yrmfyZyyHGXA-JeUKFG9GuoK1Ws_bPXQHWOV5EYZD63xSXbnptNQq-TQkE5jPyUmK89RkvUhBcO36Zl7OA96G_jEldyqV7zSYToj9anzyxeIQRcW_Y3M0MpYrlCinD0",
        "bpm_low": 126,
        "bpm_high": 132,
        "setup": "vinyl",
        "fee_tier": "premium",
        "fee_from": 1850,
        "badge": None,
        "vibe_keywords": _j(["uplifting", "peak-time", "emotional"]),
        "tech_rider": _j({
            "mixer": "Allen & Heath Xone:96",
            "players": "3x Technics SL-1210MK7",
            "monitoring": "1x d&b Audiotechnik M4",
            "external_fx": "None required",
        }),
        "availability": _j(["2026-04-20", "2026-05-10"]),
        "soundcloud_url": None,
    },
    {
        "id": "modular-mantra",
        "name": "MODULAR MANTRA",
        "email": "modular.mantra@nocturne.test",
        "tagline": "Experimental / Ambient Techno",
        "genres": _j(["Experimental Techno", "Ambient", "Modular Synthesis"]),
        "bio": (
            "Modular Mantra constructs entire sonic universes from analog signals "
            "in real time. Each performance is a one-of-a-kind experiment in texture, "
            "rhythm, and controlled chaos."
        ),
        "image_url": "https://lh3.googleusercontent.com/aida-public/AB6AXuCWtRc8CV1igJn7YHD26N_aU1U7q-TaONsbGEVT7PyoW7fPQJVRUhVxPDEYVHUsAjbt2ZSCQdPmdsLxcXcxKUQEge1gFOmEoPYTKYuLbiP07brxjlbO19tmyg15SbiaDZM4lVdY-yRgxcYcWbkdEtpEbwpD3GdKJNGqHQY7MQzNjCDuCpOhwOJ9JkyWs1-W_gFoRqDSp2HABO1kt6V8jsvVjeY3GU9Kc4azK_A2ciILrssYx1NpQq36ae2f8wl64Yjbt0Rl2cq2EQE",
        "bpm_low": 110,
        "bpm_high": 140,
        "setup": "hybrid",
        "fee_tier": "elite",
        "fee_from": 3200,
        "badge": "HOT",
        "vibe_keywords": _j(["experimental", "avant-garde", "modular"]),
        "tech_rider": _j({
            "mixer": "Mackie 1202VLZ4 (custom)",
            "players": "Eurorack system (artist provides)",
            "monitoring": "2x Genelec 8040B",
            "external_fx": "Eventide Space + OTO BAM",
        }),
        "availability": _j(["2026-04-15", "2026-05-08"]),
        "soundcloud_url": None,
    },
    {
        "id": "aelxis-vox",
        "name": "AELXIS VOX",
        "email": "aelxis.vox@nocturne.test",
        "tagline": "Techno & Experimental / Berlin",
        "genres": _j(["Techno", "Experimental", "Industrial"]),
        "bio": (
            "Redefining the festival landscape with cinematic soundscapes that blur "
            "the lines between reality and simulation. Aelxis Vox creates immersive "
            "sonic journeys that have headlined at Tomorrowland, Berghain, and "
            "Movement Detroit."
        ),
        "image_url": "https://lh3.googleusercontent.com/aida-public/AB6AXuDNjbb0O6diyoOmpaFWEoBALIXCWgpxdP5AswCbGAd6bOpzqmKPxt8gpsW4qHi3Jo_Kn0NRSAzaoqpaJf_lbE2i0TKvCygCZrMHDHB2sSDN-nHCnq6lQvo4Viqj2e6KAQotpCRo6zNhxbz5EUzPV8o8ZigQ49Z42wz6r3mS-sJhNO0Rqc0TPTXpGheQOKrLuyX6ZoB31vOMWGvkJQt31xPQtsSDZVsxNUU-LPsaKgNpE3v2PUdfcWXSQNz2cUy7ezuZGIY_pQ-rK6g",
        "bpm_low": 130,
        "bpm_high": 142,
        "setup": "digital",
        "fee_tier": "elite",
        "fee_from": 4000,
        "badge": "PRO",
        "vibe_keywords": _j(["raw", "immersive", "festival-headliner"]),
        "tech_rider": _j({
            "mixer": "Pioneer DJM-V10",
            "players": "4x Pioneer CDJ-3000",
            "monitoring": "2x d&b Audiotechnik M4",
            "external_fx": "Eventide H9 Max",
        }),
        "availability": _j(["2026-04-01", "2026-04-06", "2026-04-07"]),
        "soundcloud_url": "https://soundcloud.com/example/aelxis-vox",
    },
    {
        "id": "lumina-pulse",
        "name": "LUMINA PULSE",
        "email": "lumina.pulse@nocturne.test",
        "tagline": "Electronic / Melodic Techno",
        "genres": _j(["Melodic Techno", "Electronic"]),
        "bio": (
            "Lumina Pulse is an emerging talent whose ethereal, sunrise-ready sets "
            "have quickly garnered a loyal following across Ibiza's afterhours circuit "
            "and Berlin's intimate club scene."
        ),
        "image_url": "https://lh3.googleusercontent.com/aida-public/AB6AXuDwFfxUml-45T0WRIf-2ZZw35bGcCwbWkUz3Yh3UWdziD288LKmf77f8twh0e1dhcWuP1inMwFfp76zx6JzbE_vUdO1YtJL_-3aWpNE2deLGo3GFeJ7ugCzwhzI7KbKR-dq48zw0LtNzL0nO0251SBgwAxltlNmxUnohC563pVKrhaigNl_9Er33fZvn1a2JtUcZis8A2nLdz3Dm2AnTWbDzSyKloGc1px6SR_F3T2CLcryeKmJ_9cu-2IPCpGoYG4jaQ3Ythhmcf4",
        "bpm_low": 124,
        "bpm_high": 132,
        "setup": "digital",
        "fee_tier": "boutique",
        "fee_from": 1200,
        "badge": None,
        "vibe_keywords": _j(["melodic", "atmospheric", "sunrise"]),
        "tech_rider": _j({
            "mixer": "Pioneer DJM-900NXS2",
            "players": "2x Pioneer CDJ-3000",
            "monitoring": "1x Pioneer RM-07",
            "external_fx": "None required",
        }),
        "availability": _j(["2026-04-13", "2026-04-27"]),
        "soundcloud_url": None,
    },
    {
        "id": "dj-spinn",
        "name": "DJ SPINN",
        "email": "dj.spinn@nocturne.test",
        "tagline": "Hard Techno / Rave",
        "genres": _j(["Hard Techno", "Rave", "Acid"]),
        "bio": (
            "DJ Spinn is pure adrenaline — relentless kicks, distorted acid lines, "
            "and the kind of raw energy that turns any warehouse into a sweat-soaked "
            "rave. Not for the faint-hearted."
        ),
        "image_url": "https://lh3.googleusercontent.com/aida-public/AB6AXuAyAlZzD8NM3kOXSLgV5YfDiW9YmjWSzys2Zh0ZK9vmAcmliAbMd9jPFDHYB0lvFEEvAD4z19zOrtYgU6b6ZnY1kq_Y4OLxlUUpXwVChTQe1ZqLYYdSs9Je1ZZgy1Gazy679Gzo8u3FGAORo8Ra_w7LgQU3BBE44e_TN5g9rnEE1NuiFaQivq6eGyUJ3MmZE8eePJRYSzA_LAsafwqYk1_4y2ljS7-tqL5qv7YCTiobqx6hCnT7xUnpnXvHHFc7CORPlGFZEOT_3hI",
        "bpm_low": 140,
        "bpm_high": 150,
        "setup": "digital",
        "fee_tier": "premium",
        "fee_from": 2200,
        "badge": None,
        "vibe_keywords": _j(["rave", "high-energy", "relentless"]),
        "tech_rider": _j({
            "mixer": "Pioneer DJM-900NXS2",
            "players": "2x Pioneer CDJ-3000",
            "monitoring": "2x Pioneer RM-07",
            "external_fx": "Pioneer RMX-1000",
        }),
        "availability": _j(["2026-04-10", "2026-04-24"]),
        "soundcloud_url": None,
    },
    {
        "id": "sama",
        "name": "SAMA'",
        "email": "sama@nocturne.test",
        "tagline": "Afro House / Organic",
        "genres": _j(["Afro House", "Organic House", "World Electronic"]),
        "bio": (
            "SAMA' channels the rhythmic traditions of North Africa and the Middle East "
            "through a contemporary electronic lens, creating sets that are both deeply "
            "rooted and effortlessly modern."
        ),
        "image_url": "https://lh3.googleusercontent.com/aida-public/AB6AXuD5MmsQTXXCD7R9fSAvQS61Y1EB87Msz-3kSWX0hN17GEPKbFljwNMsJzhB2AGNtsrsyY-JIjTm6xyugwbZiVzfH2Rw3uHyHxlQuQyoooHUk3Ub81_a0o2IakgQv6cLRlwJDIYEbgncLgLUkrSU0I8lK0MBspjAcMNMF6bKfQAOEBQTxgnX1ry7RwxsCctDnxJcwhNz37JBBTB0aw6yC7hZAdpR2U7crGjIv77rJAzlmMRfAFu8fz3WRaBhLAPlpVT4bNzZhTFSn3s",
        "bpm_low": 118,
        "bpm_high": 126,
        "setup": "hybrid",
        "fee_tier": "boutique",
        "fee_from": 1500,
        "badge": None,
        "vibe_keywords": _j(["organic", "tribal", "warm"]),
        "tech_rider": _j({
            "mixer": "Pioneer DJM-900NXS2",
            "players": "2x Pioneer CDJ-3000 + 1x Technics SL-1210",
            "monitoring": "1x d&b Audiotechnik M4",
            "external_fx": "Hand drums (artist provides)",
        }),
        "availability": _j(["2026-04-14", "2026-04-21"]),
        "soundcloud_url": None,
    },
]

# ── Sample Venues ────────────────────────────────────────────────────────────

SEED_VENUES = [
    {
        "id": "berghain-berlin",
        "name": "BERGHAIN",
        "email": "bookings.berghain@nocturne.test",
        "city": "Berlin",
        "capacity": 1500,
        "vibe_tags": _j(["industrial", "underground", "legendary"]),
        "image_url": "https://lh3.googleusercontent.com/aida-public/AB6AXuDo7S4SzT5cYMLvzMqRQasmD5UCVOy6OSOimxeNYM0ln662P45jC-RLq22rMyFAaCss0vwQc8UYaypkiGKXB4OPbK0MtLHRcX1mCVf6YM_yHJJncJXTlikydZSLUgcSGKuz_z1MZyuVUCj_rQXOM5uymLqRPjfv2pqICri1RokBJeTNuZeV1DuFmtXpkx7H_KlfjzqmNJxYQREsFwsQOMqV9pOksjzo_oCN0rmdTB_zFELCSKOwj8Le257wkNEucnTmmJpcyRvfOUk",
        "description": "The legendary institution of Berlin techno culture.",
    },
    {
        "id": "the-nest",
        "name": "THE NEST",
        "email": "bookings.the.nest@nocturne.test",
        "city": "London",
        "capacity": 300,
        "vibe_tags": _j(["intimate", "underground", "velvet"]),
        "image_url": "https://lh3.googleusercontent.com/aida-public/AB6AXuAp6dU4NFVvDCFemgdtB43lY3QM3kTLIZCDwmUlJ4IL40BDWjLSt6xeKwqPwZzhnQU0VCw0A6cdE-ifFNKM4cbpV_QSlM-o8GPlyYZvNWf1iWG54LpqB_0esFB8CbP22Z1J4seY_OCVSlcAoXlnU9jqMMZitppmb2cQR6EmIgzy8mnTmy2dcyZT_j31zpodJl1Ma4Rh9Wm_9wmwjMAdQ7PmxKdweu_ktHNYPEDcJqKGcI_TgixhMajeWMMIqk6t_QMWKSby1lZgk90",
        "description": "Warmly lit underground jazz and electronic club.",
    },
    {
        "id": "basement",
        "name": "BASEMENT",
        "email": "bookings.basement@nocturne.test",
        "city": "New York",
        "capacity": 600,
        "vibe_tags": _j(["industrial", "raw", "concrete"]),
        "image_url": "https://lh3.googleusercontent.com/aida-public/AB6AXuBGasg60UfKZj9hZkwCsQgoyORMTptYwxmq1msCwcMPl92Zg1vNeJ2jtnzaYCFCVegxgYhDeJnr-kvRys_1qkc0b90WaOPz8Kjeso6SnTJip7X1BT0GpPmSSaxu-rwCApzkFRpU_ZmKmDKygxenkWia6B1ROVgXVXqDDlSkiD44FkOhx8yGCNF4FXknxjKNPObxGr_geI9wNEXvwsR3ipT6xsdu0zClehX7RG99zlZqrEtE1GICtV3sXiXjY1PIS_0hDI_THo671cI",
        "description": "Minimalist industrial event space with raw concrete walls.",
    },
    {
        "id": "the-archive-ibiza",
        "name": "THE ARCHIVE",
        "email": "bookings.the.archive@nocturne.test",
        "city": "Ibiza",
        "capacity": 2000,
        "vibe_tags": _j(["immersive", "cinematic", "island"]),
        "image_url": "https://lh3.googleusercontent.com/aida-public/AB6AXuChMjl1ayDdwtPUhn-SSxf6UtA2GHBVA6hMpnZiBUZ-IzB1IUb_3eR-e5_wry1mawVXt2GOkXeJiR5ZFsvaKsLGDLujLXRo4CNYlp6r6q8VZJKcMpfPXzrm4fBDWEYcglnURh4m6EKN_Yh5-YptmWvrx-KETeIHuTVCCS5jFNPf5K10Jl8ruE8KFpwz4fOvlUTpo4tJHcvrHaGi5o8o9sWU6UyNHW65Qu2ZxJC_RRYTz73oy2N26uO6ZARvSkeUeUtAQWAAH3opRH8",
        "description": "A cinematic immersive venue on the White Isle.",
    },
    {
        "id": "fabric-london",
        "name": "FABRIC LONDON",
        "email": "bookings.fabric@nocturne.test",
        "city": "London",
        "capacity": 1600,
        "vibe_tags": _j(["underground", "institution", "bass"]),
        "image_url": None,
        "description": "London's defining nightclub — bass-driven and uncompromising.",
    },
    {
        "id": "amnesia-ibiza",
        "name": "AMNESIA IBIZA",
        "email": "bookings.amnesia@nocturne.test",
        "city": "Ibiza",
        "capacity": 5000,
        "vibe_tags": _j(["massive", "festival", "ibiza"]),
        "image_url": None,
        "description": "One of the most famous super-clubs in the world.",
    },
    {
        "id": "printworks",
        "name": "PRINTWORKS",
        "email": "bookings.printworks@nocturne.test",
        "city": "London",
        "capacity": 3000,
        "vibe_tags": _j(["warehouse", "daylight", "industrial"]),
        "image_url": None,
        "description": "Iconic daylight raving in a former printing press.",
    },
]

# ── Sample Bookings (for Live Radar) ─────────────────────────────────────────

def _seed_bookings() -> list[dict]:
    now = datetime.utcnow()
    return [
        {
            "dj_id": "dj-spinn",
            "venue_id": "fabric-london",
            "date": "2026-04-25",
            "start_time": "23:00",
            "set_length": "3 Hours (Extended)",
            "offered_fee": 2400,
            "message": "Seed booking for the live radar feed.",
            "status": "confirmed",
            "created_at": (now - timedelta(minutes=2)).isoformat(),
        },
        {
            "dj_id": "amara-voss",
            "venue_id": "amnesia-ibiza",
            "date": "2026-05-03",
            "start_time": "01:00",
            "set_length": "3 Hours (Extended)",
            "offered_fee": 4500,
            "message": "Seed booking for the live radar feed.",
            "status": "confirmed",
            "created_at": (now - timedelta(minutes=12)).isoformat(),
        },
        {
            "dj_id": "sama",
            "venue_id": "printworks",
            "date": "2026-04-26",
            "start_time": "14:00",
            "set_length": "2 Hours",
            "offered_fee": 1800,
            "message": "Seed booking for the live radar feed.",
            "status": "confirmed",
            "created_at": (now - timedelta(hours=1)).isoformat(),
        },
    ]


# ── Seed function ────────────────────────────────────────────────────────────

async def seed_db():
    """Insert sample data if tables are empty."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        for dj in SEED_DJS:
            await db.execute(
                "UPDATE djs SET email = ? WHERE id = ? AND (email IS NULL OR email = '')",
                [dj["email"], dj["id"]],
            )
        for venue in SEED_VENUES:
            await db.execute(
                "UPDATE venues SET email = ? WHERE id = ? AND (email IS NULL OR email = '')",
                [venue["email"], venue["id"]],
            )
        await db.execute(
            """UPDATE bookings
               SET message = 'Seed booking for the live radar feed.'
               WHERE message IS NULL OR message = ''"""
        )
        await db.commit()

        row = await db.execute_fetchall("SELECT COUNT(*) as c FROM djs")
        if row[0][0] > 0:
            return  # already seeded

        # DJs
        for dj in SEED_DJS:
            cols = ", ".join(dj.keys())
            placeholders = ", ".join(["?"] * len(dj))
            await db.execute(
                f"INSERT INTO djs ({cols}) VALUES ({placeholders})",
                list(dj.values()),
            )

        # Venues
        for v in SEED_VENUES:
            cols = ", ".join(v.keys())
            placeholders = ", ".join(["?"] * len(v))
            await db.execute(
                f"INSERT INTO venues ({cols}) VALUES ({placeholders})",
                list(v.values()),
            )

        # Bookings
        for b in _seed_bookings():
            cols = ", ".join(b.keys())
            placeholders = ", ".join(["?"] * len(b))
            await db.execute(
                f"INSERT INTO bookings ({cols}) VALUES ({placeholders})",
                list(b.values()),
            )

        await db.commit()
        print("NOCTURNE: Database seeded with sample data.")
