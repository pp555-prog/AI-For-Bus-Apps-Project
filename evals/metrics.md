# NOCTURNE Eval Results

- Pairs rated: **21** of 21
- Venues with comparable rankings: **7**

## Match Precision

- Score: **3.71 / 5.00**
- Target: ≥ 4.00
- Result: ❌ MISS

## Rank Accuracy

- Score: **28.6%** (2 of 7 venues)
- Target: ≥ 70%
- Result: ❌ MISS

## Per-venue agreement

| Venue | Claude top-1 | Human top-1 | Agreement |
|---|---|---|---|
| amnesia-ibiza | evelina-voss | amara-voss | ❌ |
| basement | soren-orsk | kaleidos | ❌ |
| berghain-berlin | aelxis-vox | soren-orsk | ❌ |
| fabric-london | dj-spinn | dj-spinn | ✅ |
| printworks | aelxis-vox | soren-orsk | ❌ |
| the-archive-ibiza | amara-voss | lumina-pulse | ❌ |
| the-nest | lumina-pulse | lumina-pulse | ✅ |

## Failure-mode candidates (rated ≤ 2)

- **pair 20** (rating 1): THE NEST → AMARA VOSS (Claude score 90). Reasoning: Berlin‑style melodic techno and deep house deliver a warm, underground atmosphere perfect for a small, lit venue.
- **pair 1** (rating 2): AMNESIA IBIZA → EVELINA VOSS (Claude score 96). Reasoning: Progressive House and Peak Time Techno are tailor‑made for massive Ibiza super‑clubs and large festival crowds.
- **pair 5** (rating 2): BASEMENT → AELXIS VOX (Claude score 88). Reasoning: Techno plus Experimental and Industrial genres provide the gritty, avant‑garde feel ideal for an industrial space.
- **pair 11** (rating 2): FABRIC LONDON → AELXIS VOX (Claude score 89). Reasoning: Techno with experimental and industrial edges provides a dark, bass‑driven underground atmosphere.
- **pair 13** (rating 2): PRINTWORKS → AELXIS VOX (Claude score 95). Reasoning: Combines techno with experimental and industrial elements, perfect for an industrial daylight rave.

## Notes

- Run from: evals/run_eval.py + evals/compute_metrics.py
- See SPEC.docx Section 9 for the eval plan and target rationale.
