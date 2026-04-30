"""Seedance 2.0 video prompt builder.

The prompt structure follows the Seedance 2.0 AI Handbook (the official
ByteDance/Higgsfield reference for prompt design). Treating Seedance as
"a controlled directing system, not a poetic toy" (handbook p.2):

- Multi-Shot Mode (handbook p.8): three linked beats across time —
  Establish → Develop → Payoff. Best for "event highlights, chronological
  flow". For our afterparty-recap clip, the beats are:
    Beat 1 (~3s) — Establish: wide push-in into the venue.
    Beat 2 (~4s) — Develop: medium hold on the DJ + crowd cutaways.
    Beat 3 (~3s) — Payoff: wide reveal, peak energy.
- Single-Shot Skeleton sections (handbook p.7) still apply within the
  multi-shot frame: Format / Asset Roles / Subject / Environment / Main
  action / Camera / Lighting / Style / Sound / Constraints. Each section
  has one job.
- References need roles (handbook p.5): R1 = Environment Sheet (venue
  photo, used only for architecture/materials/scale/lighting), R2+ =
  Identity Sheet (performer photos, used only for face/build/hair/
  clothing). Every reference has ONE job (handbook p.9). The role is
  preserved across all three beats (handbook p.5 principle 6: continuity
  must be seamless, not just linked).
- Each beat carries one dominant readable action (handbook p.4 #1).
- Each beat carries one dominant camera move; transitions between beats
  are crossfades, not hard cuts (handbook p.4 #2: camera serves story).
- Action must be physical (handbook p.4 #3).
- Environment is active, not wallpaper (handbook p.5 #4); the venue is
  the second protagonist alongside the DJ.
- Concrete vocabulary (handbook p.16): "dolly-in" not "premium editorial",
  "rim light" not "venue-specific lighting", "preserve/avoid" not
  free-form constraints.

Avoids the named anti-patterns (handbook p.14): adjective soup,
unassigned reference stacks, controlling everything equally,
contradictory identity descriptions, literary emotion instead of visible
behavior, changing too many variables at once across beats.

Tested by `evals/seedance_prompt_eval.py` (deterministic structure
linter — no API spend) which detects single-shot vs multi-shot mode
and applies the appropriate camera-structure check.
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
            "architecture, materials, scale, color palette, and lighting language across all three beats."
        )
    if performer_ref_count > 0:
        slot = 2 if has_venue_ref else 1
        plural = "+" if performer_ref_count > 1 else ""
        refs_lines.append(
            f"R{slot}{plural} = Identity Sheet ({performer_name}): use only for "
            "face, build, hair, and clothing across all three beats. Do not redesign the performer."
        )
    asset_roles = " ".join(refs_lines) or "References: identity only."

    venue_vibe_phrase = ", ".join(venue.vibe_tags) or "club"
    venue_location = venue.city or "the city"
    env_anchor = "matching R1 exactly" if has_venue_ref else f"a {venue_vibe_phrase} club interior"

    if has_venue_ref:
        lighting_section = (
            f"Lighting: match the lighting language of R1 ({venue_vibe_phrase}) across all three beats; "
            "soft haze in the air throughout, rim light behind the performer, "
            "key light from above the booth; lighting energy escalates from Beat 1 to Beat 3 "
            "(peak strobes/lasers on Beat 3). "
        )
    else:
        lighting_section = (
            f"Lighting: {venue_vibe_phrase} club aesthetic across all three beats; "
            "soft haze, rim light behind the performer, key light from above the booth; "
            "energy escalates Beat 1 -> Beat 3. "
        )

    # Identity handling. WITH photos: lock the rendered face to the references
    # (handbook p.9). WITHOUT photos (current default; Seedance content
    # moderation blocks real-person photos — see SPEC §9.6): let the model
    # render a plausible generic adult DJ.
    has_identity_sheet = performer_ref_count > 0
    if has_identity_sheet:
        subject_line = (
            f"Subject: {performer_name}, a DJ performing live, identity locked to the Identity Sheet "
            "references; the venue and crowd are the second protagonist. "
        )
        identity_constraint = (
            f"Preserve {performer_name}'s exact face, hair, and clothing from the Identity Sheet "
            "across all three beats. "
        )
    else:
        subject_line = (
            f"Subject: {performer_name}, a single adult DJ performing live; the venue and crowd are the "
            "second protagonist. "
        )
        identity_constraint = (
            "Render the DJ with a single, consistent, plausible adult appearance throughout all three "
            "beats; no identity references provided. "
        )

    # Multi-Shot Main action: three explicit beats with one dominant action each
    # (handbook p.4 #1 applied per beat, p.8 Multi-Shot mode).
    main_action = (
        f"Main action: three-beat afterparty arc. "
        f"Beat 1 (Establish, ~3s): wide shot of the venue, camera dollies in slowly through silhouetted "
        "crowd toward the DJ booth; haze drifts, lights pulse to the beat; the room reads as alive. "
        f"Beat 2 (Develop, ~4s): medium shot of {performer_name} at the booth, both hands working the "
        "mixer, head nodding; brief cutaways to dancers reacting in the crowd (hands rising, faces lit "
        "in flashes of color). "
        f"Beat 3 (Payoff, ~3s): wide reveal from behind the booth looking out across the room as the "
        "crowd erupts -- hands up, lights peak, the venue's signature energy at its fullest; hold the "
        "frame as the beat lands. "
    )
    # Multi-Shot Camera: one dominant move per beat, crossfade transitions.
    camera_section = (
        "Camera: three linked moves -- slow dolly-in (Beat 1), medium hold with brief handheld cutaways "
        "(Beat 2), wide reveal looking outward (Beat 3). Each beat has one dominant move; transitions "
        "between beats are crossfades, not hard cuts. "
    )

    sections = [
        # Format/Goal
        "Format: 10-second photoreal three-beat afterparty sequence (Establish -> Develop -> Payoff), "
        "single take with embedded shot transitions, no graphic overlays. ",
        # Asset Roles (handbook principle 5)
        f"Asset roles: {asset_roles} ",
        # Subject
        subject_line,
        # Environment (handbook principle 4)
        f"Environment: interior of {venue.name} in {venue_location}, "
        f"{env_anchor}; populated dance floor with audience silhouettes in motion across all three beats. ",
        # Main action (handbook p.8 Multi-Shot)
        main_action,
        # Camera (handbook p.4 #2 + p.16 vocabulary; p.8 Multi-Shot)
        camera_section,
        # Lighting (concrete vocabulary p.16)
        lighting_section,
        # Sound
        "Sound: silent. ",
        # Style
        f"Style: photoreal documentary; afterparty highlight-reel energy; "
        f"the musical style being performed is {style_text}. ",
        # Constraints (handbook p.16 vocabulary)
        identity_constraint
        + "Avoid: text overlays, logos, watermarks, brand names, captions, "
          "on-screen graphics, celebrity likenesses.",
    ]
    return "".join(sections)
