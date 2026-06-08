# Breed Morphology & Signal Normalisation

## Core References

**Skull morphology:** McGreevy, P. D., Grassi, T. D., & Harman, A. M. (2004).
A strong correlation exists between the distribution of retinal ganglion cells and nose length in the dog.
*Brain, Behavior and Evolution*, 63(1), 13–22.

**Paedomorphosis:** Goodwin, D., Bradshaw, J. W. S., & Wickens, S. M. (1997).
Paedomorphosis affects agonistic visual signals of domestic dogs.
*Animal Behaviour*, 53(2), 297–304. https://doi.org/10.1006/anbe.1996.0284

**Brachycephalic AU adjustment:** Referenced in DogFACS literature (Waller et al., 2013).

**Breed temperament variation:** Turcsán, B., Miklósi, Á., & Kubinyi, E. (2017).
Owner perceived differences between mixed-breed and purebred dogs.
*PLOS ONE*, 12(2), e0172720.

---

## Dog Skull Type Classification (McGreevy et al., 2004)

### Brachycephalic (Short-faced)

**Breeds:** Pug, English Bulldog, French Bulldog, Boxer, Boston Terrier, Shih Tzu, Pekingese, Chow Chow, Brussels Griffon, Cavalier King Charles Spaniel (partially)

**Anatomical effects:**
- Compressed facial musculature → AU range reduced
- Brachycephalic Airway Syndrome → audible breathing is baseline
- Dental malocclusion → tooth visibility is structural
- Narrow nostrils and elongated soft palate → increased respiratory effort

**Adjustments:**
| Signal | Adjustment |
|--------|-----------|
| Facial AUs (EAD103, AU101, AU145, etc.) | Weight −40% |
| Body postural signals | Weight +40% |
| Audible breathing / snoring | Ignore as stress indicator |
| Visible teeth at rest | Ignore as threat indicator |
| Overall distress threshold | Slightly lower — these breeds often mask discomfort |

---

### Dolichocephalic (Long-faced)

**Breeds:** Greyhound, Whippet, Borzoi, Saluki, Afghan Hound, Irish Wolfhound, Scottish Deerhound, Collie, Dobermann, Dachshund

**Anatomical effects:**
- Extended muzzle allows broader facial muscle expression
- Wider visual field with enhanced motion sensitivity
- "Hard stare" is visual prey/movement tracking, not threat
- Naturally longer ears may appear more mobile

**Adjustments:**
| Signal | Adjustment |
|--------|-----------|
| Facial AUs | Weight +20% |
| Hard gaze / stare | Contextualise as visual tracking — not automatically aggressive |
| Motion sensitivity | Normal arousal at fast-moving objects |

---

### Spitz-type

**Breeds:** Akita, Siberian Husky, Shiba Inu, Pomeranian, Samoyed, Alaskan Malamute, Finnish Spitz, Norwegian Elkhound, Chow Chow (shared with brachycephalic)

**Anatomical effects:**
- Tails **anatomically curled** over back — baseline, not indicator
- Erect ears are **anatomical baseline** — only rotation backward signals negative valence
- Dense double coat may obscure piloerection

**Adjustments:**
| Signal | Adjustment |
|--------|-----------|
| Tail position (curled over back) | Ignore — structural baseline |
| Erect ears | Neutral — only ear rotation backward is meaningful |
| Piloerection | Interpret with caution (coat thickness reduces visibility) |

---

### Paedomorphic (Neoteny / Juvenile-retained features)

**Breeds:** Cavalier King Charles Spaniel, Cocker Spaniel, Beagle, Labrador Retriever, Golden Retriever, Maltese, Bichon Frise

Per Goodwin et al. (1997): These breeds retain juvenile morphological features (large eyes, rounded skull, floppy ears) that suppress agonistic visual signals.

**Key consequence:** These breeds **mask distress** — negative AU expression is suppressed by their anatomy even when they are genuinely distressed.

**Adjustments:**
| Signal | Adjustment |
|--------|-----------|
| All distress thresholds | Lower by one zone — if you'd say yellow, consider red |
| Micro-signals (brief AU101 flicker, subtle EAD103) | Weight heavily |
| Postural and biomechanical data | Prioritise over facial signals |
| "Friendly face" appearance | Do not let it override other signals |

---

## Cat Morphology

### Scottish Fold

- Ear pinnae permanently folded forward and down — **anatomical baseline**
- All ear-position AUs are unreliable indicators
- Use **ear base rotation** only (visible tilt/twist at cartilage base)
- FGS: skip ear dimension; score out of 4

### Persian / Himalayan (Brachycephalic Cat)

- Flat face = muzzle tension AUs unreliable
- Reliance signals: orbital tightening (squinting), ear signals, head position, whisker position
- FGS: weight remaining 4 dimensions more heavily
- Reference: Farnworth et al., 2018

### Siamese / Oriental Shorthair / Burmese

- Extreme vocalisers by breed — high-volume, raspy calls are baseline
- Do not raise distress zone based on vocal volume alone
- Always cross-reference with body posture and facial signals

### Maine Coon / Norwegian Forest Cat / Siberian

- Dense coats may obscure piloerection
- Large body size normalises — weight proportionally, not absolutely

---

## Normalisation Workflow

Apply before scoring, in this order:

1. **Identify species and breed** (or best estimate)
2. **Classify skull/morphology type**
3. **Note adjustments required** → populate `morphology_adjustments_applied` array
4. **Reduce or increase AU weights** as specified
5. **Adjust thresholds** (paedomorphic breeds: lower; brachycephalic: be wary of under-reading pain)
6. **Score distress** using adjusted signal weights

### Output Fields

```json
{
  "breed_detected": "French Bulldog",
  "morphology_type": "brachycephalic",
  "morphology_adjustments_applied": [
    "Facial AU weight reduced 40% (brachycephalic anatomy reduces reliable expression)",
    "Body postural signal weight increased 40%",
    "Audible breathing not treated as stress indicator (Brachycephalic Airway Syndrome baseline)",
    "Visible teeth at rest not treated as threat (dental malocclusion structural)"
  ]
}
```
