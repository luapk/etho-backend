# Social Cognition & Emotional Communication

## Core References

**Emotional contagion:** Andics, A., Gácsi, M., Faragó, T., Kis, A., & Miklósi, Á. (2014).
Voice-sensitive regions in the dog and human brain are revealed by comparative fMRI.
*Current Biology*, 24(6), 574–580. https://doi.org/10.1016/j.cub.2014.01.058

**Human vocal processing:** Andics, A., Miklósi, Á., Gácsi, M., Faragó, T., Kubinyi, E., & Topál, J. (2016).
Neural mechanisms for lexical processing in dogs.
*Science*, 353(6303), 1030–1032. https://doi.org/10.1126/science.aaf3777

**Referential gestures:** Kaminski, J., Call, J., & Fischer, J. (2004).
Word learning in a domestic dog: evidence for fast mapping.
*Science*, 304(5677), 1682–1683.

**Social attachment:** Rehn, T., & Keeling, L. J. (2011).
The effect of time left alone at home on dog welfare.
*Applied Animal Behaviour Science*, 129(2–4), 129–135.

**Social learning:** Duranton, C., & Horowitz, A. (2019).
Let me sniff! Nosework tasks independent from the owner elicit positive judgement bias in pet dogs.
*Applied Animal Behaviour Science*, 211, 61–66.

**Separation distress:** Lund, J. D., & Jørgensen, M. C. (1999).
Behaviour patterns and time course of activity in dogs with separation problems.
*Applied Animal Behaviour Science*, 63(3), 219–236.

---

## Expectation → Outcome → Response Loop

Every behavioural moment follows this framework. Animals are **prediction machines**:
they constantly model their environment and react to confirmation or violation of predictions.

```
EXPECTATION  →  OUTCOME  →  RESPONSE
(what the pet predicted)  (what happened)  (how they reacted)
```

### Match Types

| Type | Trigger | Emotional Response | Zone |
|------|---------|-------------------|------|
| `exceeded` | Outcome better than expected | Joy, excitement, positive arousal | GREEN |
| `met` | Outcome matches expectation | Satisfaction, contentment, relaxation | GREEN |
| `fell_short` | Outcome worse than expected | Frustration, disappointment | YELLOW–RED |
| `unexpected_negative` | Unplanned negative event | Fear, startle, distress | RED |

### Examples

- Owner returns earlier than usual → **exceeded** → excited greeting, zoomies
- Treat given at regular time → **met** → calm receipt, wagging
- One treat given instead of usual three → **fell_short** → pawing, frustration vocalization
- Loud unexpected noise → **unexpected_negative** → startle, flight response

---

## Umwelt Theory — Von Uexküll (1934)

Uexküll, J. von (1934/2010). *A Foray into the Worlds of Animals and Humans.*
University of Minnesota Press. (Original: Streifzüge durch die Umwelten von Tieren und Menschen)

**Core principle:** Every animal lives in a perceptual world (Umwelt) shaped by its species-specific sensory apparatus and motivational systems. Human frames of reference systematically misread animal experience.

### Dog Umwelt — Perceptual Priority Order

1. **Olfaction** — smell is the primary channel; nose carries more information than eyes
2. **Movement patterns** — direction, speed, and destination of all movement
3. **Learned sequences** — keys+shoes=walk; crinkle=treat; specific human posture=specific action
4. **Social hierarchy** — resource ownership, spatial proximity rules, attention control
5. **Emotional contagion** — human vocal prosody (Andics et al., 2016): dogs respond to emotional tone even when words are changed

### Cat Umwelt — Perceptual Priority Order

1. **Movement / prey potential** — anything that moves is processed as potential prey or threat
2. **Territorial relevance** — is this space safe? owned? invaded? scent-marked by self?
3. **Safety geometry** — enclosed spaces = refuge; open exposure = vulnerability
4. **Resource control** — food, resting spots, vertical territory, human attention (on cat's terms)
5. **Autonomy** — cats choose engagement; forced interaction = stress

### Applying Umwelt in Etho

**interpret_lines must be written from this sensory world**, never from a human frame:

❌ "The dog seems happy to see its owner" (human frame)
✅ "My human's scent + those familiar footstep rhythms = good things happen" (olfactory-primary Umwelt)

❌ "The cat looks scared" (observer frame)
✅ "This open space has no exit behind me — that unknown shape could be a threat" (territorial-geometry Umwelt)

---

## Social Attachment & Separation Distress

### Dog Attachment (Rehn & Keeling, 2011)

- Dogs show physiological and behavioural stress when alone (elevated cortisol, increased vocalisation)
- Stress response elevated significantly after 2+ hours alone
- Behavioural indicators: destruction, vocalisation, elimination, pacing, salivation
- Greeting intensity on return correlates with duration of separation

### Dog Nosework & Autonomy (Duranton & Horowitz, 2019)

- Dogs allowed to sniff freely (sniff-walks, nosework tasks) show positive cognitive bias
- Autonomy and olfactory enrichment reduce frustration and anxiety
- Recommend: "Allow sniff-led exploration" in relevant advisories

### Cat Social Independence

- Cats are facultatively social — not obligately so
- Cat-to-cat relationships are volatile; cohabitation can be chronic low-grade stress
- Signs of inter-cat tension: blocking, staring, resource guarding, reduced eating/drinking
- Vertical space, multiple resources (litter, food, water at separate locations) reduce conflict

---

## Predator-Prey Context Rule

When the analysed video contains both the target pet AND a prey species (rodents, birds, reptiles, fish):

**Apply automatic floor on distress score:**
- Cat detecting prey species → minimum YELLOW (predatory arousal is not distress but warrants monitoring)
- Dog detecting prey species → context-dependent: usually YELLOW if controlled, RED if uncontrolled chase

This rule is enforced in `validate_and_enrich_response()` in `gemini_service.py`.

---

## How to Apply in Etho

1. For every key moment in `timeline`, map it to the expectation→outcome→response structure
2. Write `expectation_analysis` as a single narrative arc covering the whole video
3. Write `interpret_lines` in first-person from the pet's Umwelt — never human frame
4. Cite Andics et al. (2016) when reporting emotional contagion from human vocal tone
5. Cite Quaranta 2007 when reporting tail lateralisation
6. When separation behaviour is visible: reference Rehn & Keeling 2011
