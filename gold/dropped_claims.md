# Claims dropped from the registry

Removed 2026-08-31 because neither is falsifiable as written: no population, no
measurable outcome, and a verb ("supports", "predicts") that names no effect. A
labeller could not decide them, so no evaluator could either, and their gold
rows were generating noise that read as model failure.

Their collected papers are LEFT IN claims.db. The registry is what the exporter
iterates, so the claims no longer reach the map, but the OpenAlex work is not
thrown away — a rewritten claim on the same subject can reuse it. Restoring one
means pasting the block back into CLAIMS and rewording `claim`.

See BACKLOG item 11 (claims not comprehensible) and the new item on adding
claims to the map.

## `responsive_interaction`

```python
"responsive_interaction": {
        "topic": "play", "group": "Interaction",
        "claim": "Responsive serve-and-return interaction supports infant brain development",
        "query": "responsive caregiving contingent interaction infant brain development",
        "age_range": "0-24 months",
        "keyword_hints": ["responsive", "contingent", "serve and return", "caregiver interaction", "synchrony"],
    },
```

## `motor_cognitive_link`

```python
"motor_cognitive_link": {
        "topic": "motor", "group": "Milestones",
        "claim": "Early motor development predicts later cognitive outcomes",
        "query": "early motor development later cognitive language outcomes longitudinal",
        "age_range": "0-36 months",
        "keyword_hints": ["motor development", "cognitive outcome", "longitudinal", "predict", "milestone", "language"],
    },
```

## Gold rows removed with them

| n | claim | labelled_by | gold stance |
|---|---|---|---|
| 7 | `responsive_interaction` | fable | supports |
| 46 | `motor_cognitive_link` | fable | does not test |
| 52 | `responsive_interaction` | fable | supports |

The labels are kept here because they are real work; if a rewritten claim covers the same ground the pairs can be re-added.
