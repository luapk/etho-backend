# Bio-Acoustics — Morton's Rules + Species-Specific Vocalisations

## Core References

**Morton's Rules:** Morton, E. S. (1977).
On the occurrence and significance of motivation-structural rules in some bird and mammal sounds.
*The American Naturalist*, 111(981), 855–869.

**Dog bark classification:** Pongrácz, P., Molnár, C., Miklósi, Á., & Csányi, V. (2005).
Human listeners are able to classify dog (Canis familiaris) barks recorded in different situations.
*Journal of Comparative Psychology*, 119(2), 136–144.

**Bark acoustics:** Faragó, T., Pongrácz, P., Miklósi, Á., Huber, L., Virányi, Z., & Range, F. (2010).
The bone is mine: Affective and referential aspects of dog growls.
*Animal Behaviour*, 79(4), 917–925.

**Growl semantics:** Faragó, T., Miklósi, Á., Korcsok, B., Száraz, J., & Pongrácz, P. (2014).
Social behaviours in dog-owner interactions can provide dogs with complex yet tractable information.
*Applied Animal Behaviour Science*, 153, 90–99.

**Cat vocalisations:** Schötz, S., van de Weijer, J., & Eklund, R. (2016–2022).
Meowsic project — Melody in Human-Cat Communication.
Lund University. https://meowsic.info/

**Solicitation purr:** McComb, K., Taylor, A. M., Wilson, C., & Charlton, B. D. (2009).
The cry embedded within the purr.
*Current Biology*, 19(13), R507–R508. https://doi.org/10.1016/j.cub.2009.05.033

---

## Morton's Motivation-Structural Rules (Cross-Species)

All vertebrates follow this pattern:

| Acoustic Quality | State | Meaning |
|-----------------|-------|---------|
| **Low pitch + rough/noisy** | Aggressive, dominant | Threat, warning, resource guard |
| **High pitch + tonal/smooth** | Fearful, submissive | Appeasement, distress, request |
| **Mid pitch + rhythmic** | Neutral to positive | Contact call, play solicitation, greeting |

**Key principle:** Never interpret a vocalisation in isolation from simultaneous body posture.

---

## Dog Vocalisations

### Barks (Pongrácz et al., 2005; Faragó et al., 2010)

| Pattern | Interpretation | Zone |
|---------|---------------|------|
| Rapid, low-pitched bursts | Alarm / threat | RED |
| Spaced, higher-pitched | Play solicitation / contact | GREEN |
| Pitch rises within sequence | Increasing urgency | YELLOW → RED |
| Single mid-pitch bark | Greeting | GREEN |
| Repetitive, monotone | Boredom / frustration | YELLOW |

### Growls (Faragó et al., 2014)

| Pattern | Interpretation | Zone |
|---------|---------------|------|
| Long duration + lowest pitch | Food/resource guarding (most serious) | RED |
| Shorter + higher pitch | Play growl | GREEN |
| Sustained + mid-pitch | Warning | YELLOW |

**Rule:** Grow context is determined by body posture, not growl alone.
- Growl + play bow + loose body = play growl (GREEN)
- Growl + stiff body + stare = threat (RED)

### Whines

| Pattern | Interpretation | Zone |
|---------|---------------|------|
| Rising pitch | Request ("I want this") | GREEN–YELLOW |
| Sustained constant pitch | Active distress ("I can't cope") | YELLOW–RED |
| Falling pitch | Giving up ("I've stopped trying") | YELLOW |
| Whine + EAD103 + whale eye | Genuine distress | RED |
| Whine + relaxed body | Low-level request | GREEN–YELLOW |

### Howls
- Conspecific contact call (most common)
- Separation anxiety (sustained, high pitch, no response received)
- Environmental trigger (sirens, music) — usually harmless

---

## Cat Vocalisations

### Meow Contour Interpretation (Schötz Meowsic 2016–2022)

| Contour | Interpretation | Zone |
|---------|---------------|------|
| **Rising** | Request ("open this door") | GREEN–YELLOW |
| **Falling** | Complaint ("that was wrong") | YELLOW |
| **Flat / level** | Demand ("now, not later") | YELLOW |
| **Rising-falling** | Solicitation with urgency | YELLOW |

### Purring (McComb et al., 2009)

| Type | Frequency Profile | Interpretation |
|------|------------------|----------------|
| Content purr | 25–50 Hz, smooth waveform | Relaxation, self-soothing | GREEN |
| Solicitation purr | 25–50 Hz **+ embedded 220–520 Hz cry** | Urgent request; triggers human urgency response | YELLOW |

**Detect solicitation purr:** If a cat appears to be purring but is also clearly soliciting (approaching, making contact, persistent), flag `solicitation_purr_detected: true`.

### Hiss / Growl
- **Always defensive** — never classify as neutral or relaxed
- Minimum zone: RED
- Hiss = immediate threat response or pain response
- Growl (cat) = escalation warning before strike

### Chirp / Chatter
- **Predatory arousal** — directed at prey stimuli (birds, insects, moving toys)
- NOT distress; high arousal state
- Zone: YELLOW (aroused, not distressed)

### Trill / Chirrup
- Affiliative greeting between cats or cat-to-human
- Zone: GREEN
- Contact signal: "I see you, I'm friendly"

---

## Audio-Visual Alignment (PettiChat Principle)

**MANDATORY:** Always validate vocalisations against simultaneous body posture.

| Vocal | Posture | Interpretation | Zone |
|-------|---------|----------------|------|
| Whine | Relaxed body | Low-level request | GREEN–YELLOW |
| Whine | EAD103 + whale eye | Genuine distress | RED |
| Purr | Relaxed, slow blink | Contentment | GREEN |
| Purr | Tense body + flattened ears | Stress purr (NOT contentment) | YELLOW–RED |
| Bark | Play bow, loose body | Play | GREEN |
| Bark | Stiff, forward lean | Threat/alarm | RED |
| Growl | Play posture | Play growl | GREEN |
| Growl | Stiff body + stare | Threat | RED |

**Report discrepancies explicitly** when audio and visual signals conflict.
Example: "Purring vocalisation detected but simultaneous ear flattening (EAC103) and tense posture indicate stress purr rather than contentment."

---

## How to Apply in Etho

1. Each vocalisation → entry in `audio_analysis.vocalizations_detected`
2. Required fields: `timestamp_start`, `timestamp_end`, `type`, `subtype`, `interpretation`, `visual_alignment`
3. `visual_alignment` must reference the simultaneous body state observed
4. Environmental sounds → `audio_analysis.environmental_sounds` with `pet_reaction`
5. `solicitation_purr_detected` boolean at top level of `audio_analysis`
6. Cite Morton 1977 for cross-species acoustic rules; cite Pongrácz 2005 for bark classification
