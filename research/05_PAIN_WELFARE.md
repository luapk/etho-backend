# Pain Assessment & Welfare Scales

## Core References

**Glasgow CMPS:** Reid, J., Nolan, A. M., Hughes, J. M. L., Lascelles, D., Pawson, P., & Scott, E. M. (2007).
Development of the short-form Glasgow Composite Measure Pain Scale (CMPS-SF) and
derivation of an analgesic intervention score.
*Animal Welfare*, 16(S), 97–104.

**WSAVA Pain Guidelines:** Mathews, K., Kronen, P. W., Lascelles, D., Nolan, A., Robertson, S., Steagall, P. V., & Yamashita, K. (2014).
WSAVA Guidelines for Recognition, Assessment and Treatment of Pain.
*Journal of Small Animal Practice*, 55(6), E10–E68. https://doi.org/10.1111/jsap.12200

**CSU Feline Pain Scale:** Hellyer, P., Rodan, I., Brunt, J., Downing, R., Hagedorn, J. E., & Robertson, S. A. (2007).
AAHA/AAFP pain management guidelines for dogs and cats.
*Journal of Feline Medicine and Surgery*, 9(6), 466–480.

**Feline Grimace Scale:** Evangelista, M. C., et al. (2019). See 02_CATFACS_FGS.md.

---

## Glasgow Composite Measure Pain Scale — Short Form (CMPS-SF)

Validated for dogs. Assesses 6 dimensions, each scored 0–3 or 0–4.

### Dimensions

| Dimension | Indicators |
|-----------|-----------|
| **Vocalization** | Quiet / moaning / crying / screaming |
| **Attention to wound** | Ignore / look / lick / rub / guard |
| **Mobility** | Normal / hesitant / reduced / refuses |
| **Response to touch** | Normal / nervous / cry / snap |
| **Demeanor** | Happy / depressed / aggressive |
| **Posture & activity** | Normal / guarding / hunched |

### Score Thresholds

| CMPS-SF Score | Action |
|--------------|--------|
| ≤ 5/24 | No pain intervention required |
| ≥ 6/24 | Analgesic intervention recommended |

**In Etho:** Use CMPS-SF as a reference framework, not a scored output — note which dimensions are elevated.

---

## Biomechanical Pain Indicators (YOLO-Measurable)

When YOLO11-Pose data is available, biomechanics are objective measurements:

| Indicator | Threshold | Interpretation |
|-----------|-----------|---------------|
| **Spinal curvature** | > 15° sustained | Submissive, fearful, or pain posture |
| **Spinal curvature** | > 30° | Extreme fear crouch, severe pain, or active submission |
| **Head below shoulder line** | Head position < 0 relative to shoulder | Withdrawal, pain (matches FGS head position dim.) |
| **Weight shifting** | Asymmetric stance distribution | Limb guarding — localised pain |
| **Gait abnormality** | Irregular stride pattern across frames | Lameness — flag for vet review |

---

## Pain Assessment Trigger Rules

Trigger a `pain_assessment` behavioral marker when ANY of the following are observed:

1. Spinal curvature > 15° sustained throughout the clip (YOLO-measured)
2. FGS mean ≥ 0.39 (cats)
3. Dog actively guarding a body part (licking one area repeatedly, flinching on contact)
4. Abnormal weight distribution visible across multiple frames
5. CMPS-SF dimension "attention to wound" elevated (licking/guarding specific area)
6. Vocalisation consistent with pain: sustained whine + physical stiffening, or cry on movement

### Pain Marker Entry Format
```json
{
  "marker": "pain_assessment",
  "code": "PAIN-ASSESS",
  "timestamp": "0:00",
  "zone": "red",
  "evidence": "Spinal curvature mean 22.3° (YOLO-measured) sustained throughout clip, consistent with pain posture. FGS orbital tightening score 1. Recommend veterinary assessment (Glasgow CMPS Reid et al., 2007; WSAVA Pain Guidelines 2014).",
  "verified": true
}
```

---

## WSAVA Five Freedoms (Context Frame)

All welfare assessment grounds in the Five Freedoms (Farm Animal Welfare Council, 1979 / WSAVA 2014):

1. **Freedom from hunger and thirst**
2. **Freedom from discomfort** (appropriate environment)
3. **Freedom from pain, injury, or disease**
4. **Freedom to express normal behaviour**
5. **Freedom from fear and distress**

Use these as reference points when writing the `advisory.insight` field.

---

## Advisory Urgency Mapping

| Observation | Urgency |
|-------------|---------|
| No pain indicators, green zone | routine |
| FGS mean 0.39–0.79 OR spinal > 15° without other signs | elevated |
| FGS mean ≥ 0.8 OR spinal > 30° OR multiple pain signals | critical |
| Active injury visible OR seizure-like activity | critical |

---

## How to Apply in Etho

1. Scan all YOLO measurements first — if spinal > 15° sustained, trigger pain_assessment
2. For cats: always attempt FGS scoring — 5 dimensions, 0–2 each
3. Pain marker = RED zone minimum
4. Advisory urgency must be "elevated" or "critical" — never "routine" when pain_assessment triggered
5. Recommendation must include: "Recommend veterinary assessment"
6. Cite Reid et al. (2007) and/or WSAVA 2014 in evidence field
