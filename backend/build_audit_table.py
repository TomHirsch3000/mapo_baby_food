#!/usr/bin/env python3
"""
build_audit_table.py — One row per claim, every field that needs a human eye.

The registry has accumulated five separate jobs: a testable wording, a polarity
sign, a shape, two decision-stakes fields, and official guidance. Reviewing
those as five sweeps means reading all 78 claims five times. This flattens them
into one table so the pass happens once.

Drafts are drafts. `claim_sign` in particular is mechanical and WILL be wrong
somewhere - one wrong sign inverts an entire claim on the map - which is why the
column sits next to the wording it was derived from rather than in a separate file.

Anything a human types into an extra column is carried forward on re-run, keyed
on claim_key.

    python backend/build_audit_table.py
"""

import argparse
import csv
import json
import os
import re
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import console
from claims import CLAIMS, tested_text

console.init()

ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, ".."))
DEFAULT_OUT = os.path.join(ROOT, "gold", "claim_audit.csv")

DOWN = r'reduces?|lowers?|prevents?|protects? against|decreases?|avoids?|limits?'
UP = r'increases?|raises?|causes?|improves?|supports?|predicts?|promotes?|delays?|harms?|worsens?'
VERB = re.compile(r'\b(%s|%s)\b' % (DOWN, UP), re.I)
IS_DOWN = re.compile(r'^(%s)$' % DOWN, re.I)

# "X is associated with worse health outcomes" carries its direction in the
# VALENCE WORD, not the verb - `associated with` is symmetric on its own. Most
# tested_as strings are phrased this way on purpose (a study measures an
# association, it does not measure a `reduces`), so a sign drafter that only
# reads verbs scores a third of the registry as directionless.
ASSOC = re.compile(r'\b(associated with|linked to|predicts?)\b', re.I)
WORSE = re.compile(r'\b(worse|poorer|higher|greater|increased|slower|later|delayed'
                   r'|reduced quality|lower quality|impaired)\b', re.I)
BETTER = re.compile(r'\b(better|improved|lower|reduced|fewer|richer|greater protection'
                    r'|healthier|earlier)\b', re.I)


def draft_sign(text):
    """+1 if the claim asserts its exposure RAISES its outcome, -1 if it lowers
    it, 0 if no direction can be read at all (a threshold claim, usually)."""
    m = VERB.search(text)
    if m:
        verb = m.group(0)
        outcome = re.sub(r'^(the )?risk of ', '', text[m.end():].strip(), flags=re.I)
        return (-1 if IS_DOWN.match(verb) else 1), verb, text[:m.start()].strip(), outcome

    a = ASSOC.search(text)
    if a:
        tail = text[a.end():]
        exposure = text[:a.start()].strip()
        outcome = re.sub(r'^(the )?risk of ', '', tail.strip(), flags=re.I)
        # A bare association with a named harm ("...associated with infant
        # botulism") asserts more of it, so it reads +1 unless a valence word
        # says otherwise.
        w, b = WORSE.search(tail), BETTER.search(tail)
        if w and (not b or w.start() < b.start()):
            return 1, a.group(0) + ' ' + w.group(0), exposure, outcome
        if b:
            return -1, a.group(0) + ' ' + b.group(0), exposure, outcome
        return 1, a.group(0), exposure, outcome

    return 0, '', '', ''


def load(path):
    return json.load(open(path, encoding='utf-8')) if os.path.exists(path) else []


def main():
    p = argparse.ArgumentParser(description="Flatten the registry for one review pass")
    p.add_argument("--scratch", required=True, help="dir holding the draft JSON files")
    p.add_argument("--out", default=DEFAULT_OUT)
    args = p.parse_args()

    stakes = {r['claim_key']: r for r in load(os.path.join(args.scratch, 'stakes_draft.json'))}
    guide = {r['claim_key']: r for r in load(os.path.join(args.scratch, 'guidance_pilot_out.json'))}

    rows = []
    for key, c in CLAIMS.items():
        tested = tested_text(key)
        sign, verb, exposure, outcome = draft_sign(tested)
        st = stakes.get(key, {})
        g = guide.get(key, {})
        nhs, aap = g.get('nhs', {}), g.get('aap', {})

        # A claim whose testable wording is just the display wording, and which
        # yields no sign from it, is the one that still needs writing.
        needs = 'YES' if (not c.get('tested_as') and sign == 0
                          and c['claim_type'] != 'threshold') else ''

        rows.append({
            'claim_key': key, 'topic': c['topic'], 'group': c['group'],
            'claim': c['claim'],
            'tested_as': c.get('tested_as', ''),
            'needs_tested_as': needs,
            'claim_type': c['claim_type'],
            'draft_sign': sign, 'sign_verb': verb,
            'draft_exposure': exposure, 'draft_outcome': outcome,
            'age_range': c['age_range'],
            'cost_to_follow': st.get('cost_to_follow', ''),
            'if_wrong': st.get('if_wrong', ''),
            'stakes_rationale': st.get('rationale', ''),
            'stakes_uncertain': 'YES' if st.get('uncertain') else '',
            'guidance_agreement': g.get('agreement', ''),
            'guidance_note': g.get('agreement_note', ''),
            'nhs_says': nhs.get('paraphrase', ''), 'nhs_url': nhs.get('url', ''),
            'aap_says': aap.get('paraphrase', ''), 'aap_url': aap.get('url', ''),
        })

    # Most-in-need-of-attention first, same principle as compare_runs.py.
    def urgency(r):
        return -sum((r['needs_tested_as'] == 'YES', r['stakes_uncertain'] == 'YES',
                     r['guidance_agreement'] == 'differ', r['draft_sign'] == 0,
                     r['if_wrong'] == 'serious'))
    rows.sort(key=lambda r: (urgency(r), r['topic'], r['claim_key']))

    carried = []
    if os.path.exists(args.out):
        with open(args.out, encoding='utf-8-sig', newline='') as f:
            prev = {r['claim_key']: r for r in csv.DictReader(f)}
        if prev:
            known = set(rows[0])
            carried = [c for c in next(iter(prev.values())) if c not in known]
            for r in rows:
                for col in carried:
                    r[col] = (prev.get(r['claim_key'], {}) or {}).get(col, '')
            if carried:
                print(f"carried forward {carried}")

    fields = list(rows[0])
    with open(args.out, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        w.writeheader(); w.writerows(rows)

    print(f"{args.out}  ({len(rows)} claims, {len(fields)} columns)\n")
    for label, n in (
            ('needs a tested_as written', sum(1 for r in rows if r['needs_tested_as'])),
            ('no sign derivable (threshold or unclear)', sum(1 for r in rows if r['draft_sign'] == 0)),
            ('stakes flagged uncertain', sum(1 for r in rows if r['stakes_uncertain'])),
            ('guidance sourced', sum(1 for r in rows if r['guidance_agreement'])),
            ('NHS and AAP differ', sum(1 for r in rows if r['guidance_agreement'] == 'differ')),
            ('if_wrong = serious', sum(1 for r in rows if r['if_wrong'] == 'serious'))):
        print(f"  {label:<42} {n:>3}")


if __name__ == "__main__":
    main()
