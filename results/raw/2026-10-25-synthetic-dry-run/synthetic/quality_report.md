# MemGym-IR Quality Report

## Pipeline Summary

| Stage | Count |
|-------|-------|
| Raw Loaded | 2 |
| After Filter | 2 |
| After Prescreen | 2 |
| After Extract | 2 |
| After Craft | 2 |
| After Verify | 2 |
| After Harden | 2 |
| Final Count | 2 |

## Dataset Statistics

| Metric | Value |
|--------|-------|
| Count | 2 |
| Avg Hops | 3.0 |
| Avg Grounding Facts | 3.0 |
| Avg Distractors | 4.0 |
| Avg Turns | 4.0 |
| Avg Total Tokens | 90.0 |
| Difficulty Distribution | {'medium': 2} |

## Ablation Gap Analysis

| Metric | Value |
|--------|-------|
| Total Verified | 2 |
| Accepted | 2 |
| Rejected | 0 |
| Avg Score A | 1.0 |
| Avg Score B | 0.0 |
| Avg Score C | 0.0 |
| Avg Gap Ab | 1.0 |
| Avg Gap Ac | 1.0 |
| Min Gap Ab | 1.0 |
| Max Gap Ab | 1.0 |

## Quality Gates

| Gate | Rate |
|------|------|
| Filter Rate | 2/2 (100%) |
| Prescreen Rejection Rate | 0/2 (0%) |
| Extract Quality Gate Rate | 2/2 (100%) |
| Verification Acceptance Rate | 2/2 (100%) |

## Distractor Composition (Avg Tokens)

| Source | Avg Tokens |
|--------|-----------|
| Supporting | 45 |
| Cross Instance | 45 |
| Same Topic | 0 |
| Adversarial | 0 |
| Contradictions | 0 |
| Filler | 0 |

## Per-Instance Breakdown

| ID | Hops | Facts | Distractors | Tokens | Difficulty |
|----|------|-------|-------------|--------|------------|
| memgym_ir__synthetic__synthetic_00000 | 3 | 3 | 4 | 90 | medium |
| memgym_ir__synthetic__synthetic_00001 | 3 | 3 | 4 | 90 | medium |
