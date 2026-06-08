# DogFACS — Dog Facial Action Coding System

## Core References

**Primary:** Waller, B. M., Peirce, K., Caeiro, C. C., Scheider, L., Burrows, A. M., McCune, S., & Bhatt, M. (2013).
Paedomorphic facial expressions give dogs a selective advantage.
*PLOS ONE*, 8(12), e82686. https://doi.org/10.1371/journal.pone.0082686

**Extended coding:** Caeiro, C. C., Burrows, A. M., & Waller, B. M. (2017).
Development and application of CatFACS: Are human cats more expressive than their wild relatives?
*Behavioural Processes*, 141, 2–12.

**Communicative AU101:** Kaminski, J., Waller, B. M., Diogo, R., Hartstone-Rose, A., & Burrows, A. M. (2019).
Evolution of facial muscle anatomy in dogs.
*PNAS*, 116(29), 14677–14681. https://doi.org/10.1073/pnas.1820653116

---

## Action Unit Reference Table

| Code | Name | Muscle | Signal |
|------|------|--------|--------|
| EAD101 | Ears Forward | Auriculares | Alert attention, engagement — neutral to positive |
| EAD102 | Ear Adductor | Auricularis anterior | Positive anticipation, social eagerness |
| EAD103 | Ears Flattened / Back | Caudal auriculares | Fear, frustration, pain, appeasement |
| AU101 | Inner Brow Raise | Levator anguli oculi medialis (LAOM) | Communicative signal — shown selectively toward humans; triggers caregiving response |
| AU145 | Blink / Rapid Blinking | Orbicularis oculi | Mild stress, internal conflict, avoidance of direct gaze |
| AD137 | Nose Lick | Tongue / nasal musculature | Displacement behaviour, anxiety, uncertainty |
| AD19 | Tongue Show | Hyoid / tongue | Mild stress, appeasement, uncertainty |
| — | Whale Eye | Scleral exposure (non-muscular) | Visible white of eye — fear, threat monitoring, anxiety without head turn |
| — | Piloerection | Arrector pili | Arousal (valence context-dependent — can be play or threat) |
| AU143 | Nose Wrinkle | Levator labii | Offensive threat or pain |
| AU200 | Lip Corner Pull | Zygomaticus major | Appeasement grin; NOT smiling — often mis-read by owners |

---

## Brachycephalic Morphological Adjustment

Breeds affected: **Pug, English Bulldog, French Bulldog, Boxer, Boston Terrier, Shih Tzu, Pekingese, Chow Chow**

- Facial AU weight **−40%** — compressed anatomy reduces muscle range and signal clarity
- Body postural signal weight **+40%** to compensate
- Ignore: audible breathing sounds (Brachycephalic Airway Syndrome baseline)
- Ignore: tooth visibility in relaxed state (dental malocclusion is structural, not threatening)

Reference: McGreevy, P. D., Grassi, T. D., & Harman, A. M. (2004). A strong correlation exists between the distribution of retinal ganglion cells and nose length in the dog. *Brain, Behavior and Evolution*, 63(1), 13–22.

---

## Dolichocephalic Adjustment

Breeds: **Greyhound, Whippet, Borzoi, Saluki, Afghan Hound, Collie, Doberman**

- Facial AU weight **+20%** — longer muzzle allows fuller muscle expression
- "Hard stare" = visual prey tracking, NOT aggression — context-dependent
- These breeds have higher visual acuity and wider visual field

---

## Paedomorphic Mask Adjustment

Breeds: **Cavalier King Charles Spaniel, Cocker Spaniel, Beagle, Labrador Retriever, Golden Retriever**

Per Goodwin, D., Bradshaw, J. W. S., & Wickens, S. M. (1997). Paedomorphosis affects agonistic visual signals of domestic dogs. *Animal Behaviour*, 53(2), 297–304.

- These breeds **mask distress** — neotenised features suppress negative AU expression
- **Lower all thresholds by one zone** when assessing borderline cases
- Weight micro-signals (brief AU101, subtle EAD103 flicker) heavily
- Rely more on postural and biomechanical data than facial signals

---

## Inner Brow Raise — Kaminski 2019 Special Note

AU101 (inner brow raise) is produced far more frequently by domestic dogs than wolves.
- Dogs have a dedicated LAOM muscle that wolves lack or have only in a thin slip.
- This is an *evolved communicative signal*, not a stress sign.
- Dogs show it **selectively toward humans** — almost absent when alone.
- It triggers the human parental caregiving response.
- Report AU101 in `facs_codes_detected` with valence "communicative" not "negative."

---

## How to Apply in Etho

1. Only report AUs you **clearly observe** — do not infer from context
2. Each AU observation = one entry in `facs_codes_detected` with `timestamp`, `code`, `description`, `valence`, `confidence`
3. Apply morphological adjustment BEFORE assigning weight to the AU observation
4. AU103 (ears flattened) + whale eye + body low posture = minimum RED zone
5. AU101 alone does not raise distress score — it's communicative

---

## Confidence Guidelines

| Confidence | Criteria |
|------------|----------|
| high | AU clearly visible, unobstructed, held for ≥0.5s |
| medium | Brief flash, partially visible, or single frame |
| low | Inferred from context, obstructed, or breed makes signal unreliable |
