# YOLO11-Pose Measurement Framework

## Core References

**YOLO11 architecture:** Jocher, G., & Qiu, J. (2024).
Ultralytics YOLO11. https://github.com/ultralytics/ultralytics
DOI: https://doi.org/10.5281/zenodo.10950141

**COCO keypoints:** Lin, T.-Y., Maire, M., Belongie, S., Hays, J., Perona, P., Ramanan, D., Dollár, P., & Zitnick, C. L. (2014).
Microsoft COCO: Common objects in context.
*ECCV 2014*, 740–755. https://doi.org/10.1007/978-3-319-10602-1_48

**AP-10K animal pose benchmark:** Hang, S., et al. (2022).
AP-10K: A benchmark for animal pose estimation in the wild.
*NeurIPS 2021 Track on Datasets and Benchmarks.*
https://arxiv.org/abs/2108.12617

**Spinal biomechanics in quadrupeds:** Fischer, M. S., & Blickhan, R. (2006).
The tri-segmented limbs of therian mammals: How do they affect locomotion?
*Journal of Human Evolution*, 51(4), 415–428.

---

## COCO-17 Keypoint Schema (Applied to Pets)

The YOLO11-pose model was trained on human COCO-17 keypoints. When applied to pets,
these keypoints map approximately as follows:

| COCO Index | Human | Dog / Cat Approximation |
|-----------|-------|------------------------|
| 0 | Nose | Nose / muzzle tip |
| 1 | Left Eye | Left eye |
| 2 | Right Eye | Right eye |
| 3 | Left Ear | Left ear base |
| 4 | Right Ear | Right ear base |
| 5 | Left Shoulder | Left shoulder |
| 6 | Right Shoulder | Right shoulder |
| 7 | Left Elbow | Left elbow / mid-forelimb |
| 8 | Right Elbow | Right elbow / mid-forelimb |
| 9 | Left Wrist | Left paw / carpus |
| 10 | Right Wrist | Right paw / carpus |
| 11 | Left Hip | Left hip |
| 12 | Right Hip | Right hip |
| 13 | Left Knee | Left stifle |
| 14 | Right Knee | Right stifle |
| 15 | Left Ankle | Left hock |
| 16 | Right Ankle | Right hock |

**Important caveat:** Human pose model is a proxy for animal pose. Accuracy is approximate.
Confidence-weighted keypoints are used; low-confidence detections are discarded.
Treat measurements as indicative trends, not clinical-grade biomechanics.

---

## Spinal Curvature Calculation

### Method

Using keypoints: `nose` (0), `mid-shoulder` (mean of 5+6), `mid-hip` (mean of 11+12)

1. Construct vector A: nose → mid-shoulder
2. Construct vector B: mid-shoulder → mid-hip
3. Angle between A and B = deviation from straight spinal axis
4. Filter to keypoints with confidence ≥ 0.4

### Thresholds

| Range | Interpretation | Etho Zone |
|-------|---------------|-----------|
| 0–5° | Normal relaxed posture | GREEN |
| 5–15° | Alert or mildly tense — investigate context | GREEN–YELLOW |
| 15–30° | Submissive, fearful, or pain posture — flag | YELLOW–RED |
| > 30° | Extreme fear crouch, severe pain, or active submission | RED |

### Sustained vs. Momentary

- **Sustained** (> 50% of frames above threshold): diagnostic weight HIGH
- **Momentary** (brief excursion, returns to baseline): diagnostic weight LOW
- Report `mean_deg`, `max_deg`, and distribution across clip

---

## Head Tilt Calculation

### Method

Using keypoints: `left-ear` (3), `right-ear` (4), horizontal reference

1. Vector from left ear to right ear
2. Angle of this vector from horizontal (0° = level)
3. Absolute value = head tilt magnitude

### Thresholds

| Range | Interpretation |
|-------|---------------|
| < 5° | Normal, centred posture |
| 5–20° | Curiosity, movement tracking, attentive listening |
| > 20° | Strong appeasement signal, vestibular sign, or extreme solicitation |
| Asymmetric persistent | Possible vestibular disorder — flag for vet review |

---

## Detection Coverage

```
detection_coverage = (frames_with_pet_detected) / (total_frames_sampled)
```

| Coverage | Confidence |
|----------|-----------|
| ≥ 0.85 | High confidence — measurements reliable |
| 0.60–0.84 | Medium confidence — note in output |
| < 0.60 | Low confidence — measurements may be unreliable; note in output |

---

## IoU Skeleton-to-Pet Matching

YOLO detection (classes 15=cat, 16=dog) and YOLO pose run separately.
Skeletons are matched to pet bounding boxes by Intersection over Union (IoU):

- IoU ≥ 0.3: skeleton assigned to pet bounding box
- IoU < 0.3: skeleton discarded (belongs to human or background)

---

## Pose Metrics Output Schema

```json
{
  "_pose_metrics": {
    "detection_coverage": 0.92,
    "frames_analyzed": 46,
    "spinal_curvature": {
      "mean_deg": 18.4,
      "max_deg": 27.1,
      "interpretation": "moderate concern — pain or fear posture range"
    },
    "head_tilt": {
      "mean_deg": 8.2,
      "interpretation": "attentive, mild curiosity"
    }
  }
}
```

---

## Mandatory Citation Rule

When making any posture claim, cite the measurement.

✅ "Shows 22° mean spinal curvature (YOLO11-Pose, sampled at 5 fps), consistent with fearful crouching per MODEL_GUIDE Step 9 thresholds."

❌ "Appears to be hunching slightly." (ungrounded — do not use)

---

## Future Improvement: AP-10K Animal Pose

The current model (COCO-17 human pose) is a proxy. For higher accuracy, the AP-10K animal pose dataset provides:
- 10,015 images across 54 animal categories
- 17 animal-specific keypoints
- Pretrained checkpoints for ViTPose, HRNet, Swin

Replacing YOLO11-pose with an AP-10K fine-tuned model would improve keypoint localisation,
particularly for tail, spine, and limb endpoints.

---

## How to Apply in Etho

1. All posture claims in `body_language` and `behavioral_markers.evidence` must cite measurement
2. If `_pose_metrics.detection_coverage < 0.6`, add caveat: "Low detection coverage — measurements indicative only"
3. Spinal curvature > 15° → trigger pain_assessment (see 05_PAIN_WELFARE.md)
4. Head tilt > 20° → flag in behavioral_markers with head_tilt code
5. Include `pose_evidence` in `key_behavioral_moments` entries when relevant
