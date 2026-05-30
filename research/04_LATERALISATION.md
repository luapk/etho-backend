# Tail Wag Lateralisation & Hemispheric Asymmetry

## Core References

**Primary:** Quaranta, A., Siniscalchi, M., & Vallortigara, G. (2007).
Asymmetric tail-wagging responses by dogs to different emotive stimuli.
*Current Biology*, 17(6), R199–R201. https://doi.org/10.1016/j.cub.2007.02.008

**Observer response:** Siniscalchi, M., d'Ingeo, S., Minunno, M., & Quaranta, A. (2013).
Communication in dogs: Is tail asymmetry a loaded message?
*Animals*, 3(4), 1006–1021.

**Hemispheric basis:** Vallortigara, G., & Rogers, L. J. (2005).
Survival with an asymmetrical brain: Advantages and disadvantages of cerebral lateralization.
*Behavioral and Brain Sciences*, 28(4), 575–588.

**Dog response to lateralised wags:** Siniscalchi, M., Lusito, R., Vallortigara, G., & Quaranta, A. (2013).
Seeing left- or right-asymmetric tail wagging produces different emotional responses in dogs.
*Current Biology*, 23(22), 2279–2282. https://doi.org/10.1016/j.cub.2013.09.027

---

## The Lateralisation Signal

### Mechanism

The **tip of the tail** deviates left or right of the body's vertical midline during wagging.
This asymmetry reflects hemispheric activation:

| Wag Direction | Hemisphere Activated | Emotional Valence |
|--------------|---------------------|------------------|
| **Right-biased** (tip moves to animal's right) | Left hemisphere | Positive, approach motivation, engagement |
| **Left-biased** (tip moves to animal's left) | Right hemisphere | Negative, withdrawal motivation, stress or threat |
| Centre | Balanced activation | Neutral or ambivalent |

### What Triggers Each Direction

**Right-biased (positive):**
- Owner approaching
- Familiar person
- Positive social interaction
- Play invitation

**Left-biased (negative):**
- Unfamiliar dominant dog
- Perceived threat
- Negative emotional arousal
- Separation-related stress

---

## How to Measure

1. Observe tail tip position relative to the **animal's** midline (not the camera's left/right)
2. Track through ≥3 wag cycles to establish consistent pattern
3. Record as:
   - `"right_biased"` — tip consistently moves further to animal's right
   - `"left_biased"` — tip consistently moves further to animal's left
   - `"centre"` — approximately symmetrical, ±5° of midline
   - `"not_visible"` — tail obscured, absent, or not wagging

---

## Breed Morphological Considerations

### Spitz-type breeds
Breeds: **Akita, Husky, Shiba Inu, Pomeranian, Samoyed, Alaskan Malamute**

- Tails are **anatomically curled** — do NOT flag curled tail as stress indicator
- Baseline = tightly curled over back
- Only flag when tail drops **below baseline anatomical curl** or goes between legs
- Lateralisation still observable in the direction of the curl lean

### Docked tails
- Lateralisation signal unreliable if tail is docked
- Report as `"not_visible"` with note: "tail docked — lateralisation not assessable"

### Low-set / pendulous tails
- Breeds like Bassett Hound, Bloodhound — naturally carry tail lower
- Establish individual baseline before interpreting position

---

## Other Animals — Lateralisation Generalises

Vallortigara & Rogers (2005) demonstrate functional hemispheric asymmetry across vertebrates:
- **Cats** also show lateralised approach/withdrawal (though less studied than dogs)
- Generalise cautiously for cats — cite data gap if reporting

---

## Integration with Distress Score

| Observation | Impact on Score |
|-------------|----------------|
| Right-biased wag + relaxed posture | Supports GREEN zone |
| Left-biased wag + stiff posture | Supports YELLOW–RED zone |
| Left-biased wag + EAD103 + whale eye | Confirms RED zone |
| Tail between legs | Minimum YELLOW regardless of wag direction |

---

## How to Apply in Etho

1. Report in `visual_analysis.tail_lateralisation` field
2. When tail is visible and wagging: always attempt to classify
3. When lateralisation is detected: cite Quaranta et al., 2007 in `behavioral_markers`
4. Entry format:
   ```json
   {
     "marker": "left-biased tail wag",
     "code": "TAIL-LAT",
     "timestamp": "0:12",
     "zone": "yellow",
     "evidence": "Tail tip consistently deviating to animal's left across 4 wag cycles — right hemisphere activation consistent with withdrawal motivation (Quaranta et al., 2007)",
     "verified": true
   }
   ```
5. Combine with body posture for complete assessment — lateralisation alone is not decisive
