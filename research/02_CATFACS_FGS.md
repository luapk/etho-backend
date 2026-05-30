# CatFACS + Feline Grimace Scale

## Core References

**CatFACS:** Caeiro, C. C., Guo, K., & Mills, D. S. (2013).
*The development and application of CatFACS: A feline facial action coding system.*
Presented at the 2013 ISAE Conference.

**FGS Primary:** Evangelista, M. C., Watanabe, R., Leung, V. S. Y., Monteiro, B. P., O'Toole, E., Pang, D. S. J., & Steagall, P. V. (2019).
Facial expressions of pain in cats: The development and validation of a Feline Grimace Scale.
*Scientific Reports*, 9, 19128. https://doi.org/10.1038/s41598-019-55693-8

**FGS reliability:** Watanabe, R., Doodnaught, G., Prout, R., Auger, M., Leroux, E., Pascoe, P. J., & Steagall, P. V. (2020).
A multidisciplinary study of pain in cats undergoing dental extractions.
*PLOS ONE*, 15(3), e0228194.

---

## CatFACS Action Unit Table

| Code | Name | Signal |
|------|------|--------|
| EAC101 | Ears Forward | Alert, comfortable, engaged — positive context |
| EAC102 | Ears Lateral (sideways) | Mild unease, uncertain about stimulus |
| EAC103 | Ears Flattened / Rotated Back | Fear, defensive aggression, pain |
| AU101 | Inner Brow Raise | Communicative — affiliative toward trusted humans |
| AU145 | Blink / Slow Blink | Affiliative trust signal — cat-directed equivalent of a smile; triggers reciprocal blink |
| AU46 | Wink | Social signal — less reliable than slow blink |
| — | Whisker Forward | Investigative, positive arousal |
| — | Whisker Flattened | Fear, pain, submission |
| — | Muzzle Round/Relaxed | Comfortable, pain-free |
| — | Muzzle Elliptical/Tense | Pain, stress — key FGS indicator |
| — | Orbital Tightening | Squinting = pain or stress response |
| — | Head Below Shoulders | Withdrawal, pain, severe stress |

---

## Feline Grimace Scale (FGS) — Scoring Protocol

### Score each of 5 dimensions: 0 (absent) / 1 (moderate) / 2 (obvious)

| Dimension | 0 — Absent | 1 — Moderate | 2 — Obvious |
|-----------|-----------|--------------|-------------|
| **Ear position** | Forward, upright | Slightly rotated / asymmetric | Flattened, rotated outward/back |
| **Orbital tightening** | Eyes open | Partial squint | Eyes closed or narrow squint |
| **Muzzle tension** | Round, relaxed | Mildly tense | Elliptical, tense chin, whisker bump visible |
| **Whisker position** | Forward or sideways | Slightly retracted | Flattened against face |
| **Head position** | Above or at shoulder line | At or slightly below | Well below shoulder line |

### Scoring Thresholds

**Mean score = sum of 5 dimensions / 5**

| Mean Score | Interpretation | Action |
|------------|----------------|--------|
| 0.00–0.38 | No pain indicator | Routine |
| **≥ 0.39** | **Pain indicator** | **Veterinary attention required** |
| ≥ 1.0 | Moderate pain | Elevated advisory urgency |
| ≥ 1.5 | Significant pain | Critical advisory urgency |

### Etho Integration Rule

When FGS mean ≥ 0.39:
1. Set `pain_assessment` behavioral marker with code "FGS-PAIN"
2. Minimum zone = RED (distress_score ≥ 67)
3. Advisory urgency = "elevated" or "critical" depending on score
4. Cite: Evangelista et al., 2019

---

## Slow Blink — McComb et al., 2020

McComb, K., et al. (2020). Humans attribute slow blink as a positive cat signal.
*Scientific Reports*, 10, 21566.

- Cats slow-blink at humans in response to human slow-blinking
- Signal = **trust, relaxed affect, positive social bond**
- Valence: positive. Do NOT score as stress AU.
- Note: can occur alongside mild environmental vigilance — this is not contradictory

---

## Scottish Fold Adjustment

- Ears **permanently folded** — ear position AUs are **completely unreliable**
- Use **ear base rotation** only (tilt/rotation at base, not pinnae shape)
- Increase orbital tightening and muzzle tension weight to compensate
- FGS scoring: skip ear position dimension; adjust denominator to 4

---

## Persian / Brachycephalic Cat Adjustment

- Flat face makes **muzzle tension unreadable** (EAC anatomy compressed)
- Skip muzzle tension dimension in FGS; adjust denominator to 4
- Rely on: orbital tightening, ear signals, head position, whisker position
- Reference: Farnworth, M. J., et al. (2018). Flat feline faces: Is brachycephaly associated with respiratory abnormalities in the domestic cat?. *PLOS ONE*, 13(1), e0191895.

---

## Siamese / Oriental Adjustment

- Extreme vocalisers by breed — "screaming" may be baseline communication
- Do not raise distress score based on vocal volume alone
- Cross-check vocalization with simultaneous body posture and context
- Reference: Schötz Meowsic Project data (2016–2022)

---

## How to Apply in Etho

1. CatFACS AUs → `facs_codes_detected` entries, same format as DogFACS
2. FGS scoring → `behavioral_markers` entry with marker="FGS-pain-assessment", code="FGS-PAIN"
3. Evidence field must include the individual dimension scores and mean
4. `solicitation_purr_detected` = true if purr embeds high-frequency 220–520 Hz cry component
5. Slow blink → positive behavioral marker, valence="positive"
