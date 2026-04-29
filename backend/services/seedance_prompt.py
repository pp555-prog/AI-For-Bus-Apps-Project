"""Seedance 2.0 video prompt builder.

The prompt structure follows the Seedance 2.0 AI Handbook (the official
ByteDance/Higgsfield reference for prompt design). Treating Seedance as
"a controlled directing system, not a poetic toy" (handbook p.2):

- Single-Shot Skeleton (handbook p.7): Format / Asset Roles / Subject /
  Environment / Main action / Camera / Lighting / Style / Sound /
  Constraints. Each section has one job.
- References need roles (handbook p.5): R1 = Environment Sheet (venue
  photo, used only for architecture/materials/scale/lighting), R2+ =
  Identity Sheet (performer photos, used only for face/build/hair/
  clothing). Every reference has ONE job (handbook p.9).
- One dominant readable action (handbook p.4 principle 1).
- Camera serves story (handbook p.4 principle 2). One move only.
- Action must be physical (handbook p.4 principle 3).
- Environment is active, not wallpaper (handbook p.5 principle 4).
- Concrete vocabulary (handbook p.16): "dolly-in" not "premium editorial",
  "rim light" not "venue-specific lighting", "preserve/avoid" not
  free-form constraints.

Avoids the named anti-patterns (handbook p.14): adjective soup,
too many camera moves, unassigned reference stacks, controlling
everything equally, contradictory identity descriptions, literary
emotion instead of visible behavior.

Tested by `evals/seedance_prompt_eval.py` (deterministic structure
linter — no API spend).
"""

from __future__ import annotations

from backend.models import Venue


def build_seedance_prompt(
    *,
    performer_name: str,
    venue: Venue,
    style_text: str,
    has_venue_ref: bool,
    performer_ref_count: int,
) -> str:
    """Build a Seedance 2.0 video prompt for the personalized demo flow.

    See module docstring for handbook citations and design rationale.
    """
    refs_lines: list[str] = []
    if has_venue_ref:
        refs_lines.append(
            "R1 = Environment Sheet (the matched venue): use only for "
            "architecture, materials, scale, color palette, and lighting language."
        )
    if performer_ref_count > 0:
        slot = 2 if has_venue_ref else 1
        plural = "+" if performer_ref_count > 1 else ""
        refs_lines.append(
            f"R{slot}{plural} = Identity Sheet ({performer_name}): use only for "
            "face, build, hair, and clothing. Do not redesign the performer."
        )
    asset_roles = " ".join(refs_lines) or "References: identity only."

    venue_vibe_phrase = ", ".join(venue.vibe_tags) or "club"
    venue_location = venue.city or "the city"
    env_anchor = "matching R1 exactly" if has_venue_ref else f"a {venue_vibe_phrase} club interior"

    lighting_anchor = (
        f"Lighting: match the lighting language of R1 ({venue_vibe_phrase}); "
        if has_venue_ref
        else f"Lighting: {venue_vibe_phrase} club aesthetic; "
    )

    return (
        # Format/Goal
        "Format: one continuous 10-second photoreal music-performance shot, "
        "single take, no edits, no graphic overlays. "
        # Asset Roles (handbook principle 5)
        f"Asset roles: {asset_roles} "
        # Subject
        f"Subject: {performer_name}, identity locked to the Identity Sheet references. "
        # Environment (handbook principle 4)
        f"Environment: interior of {venue.name} in {venue_location}, "
        f"{env_anchor}; small audience visible in the foreground as silhouettes. "
        # Main action (handbook principles 1 + 3)
        f"Main action: {performer_name} stands behind the DJ booth, both hands working the mixer, "
        "head nodding to the beat. "
        # Camera (handbook principle 2 + concrete vocabulary p.16)
        "Camera: slow dolly-in from the back of the room toward the booth, "
        f"ending in a medium close-up of {performer_name}; shallow focus on the performer throughout. "
        # Lighting (concrete vocabulary p.16)
        f"{lighting_anchor}"
        "soft haze in the air, rim light behind the performer, single key light from above the booth. "
        # Sound
        "Sound: silent. "
        # Style
        f"Style: photoreal documentary; the musical style being performed is {style_text}. "
        # Constraints (handbook p.16 vocabulary)
        f"Preserve {performer_name}'s exact face, hair, and clothing from the Identity Sheet. "
        "Avoid: text overlays, logos, watermarks, brand names, captions, on-screen graphics, "
        "celebrity likenesses."
    )
