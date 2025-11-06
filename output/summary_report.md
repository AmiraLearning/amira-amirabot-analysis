# Conversation Quality Analysis Report

**Total Conversations Analyzed:** 1001
**First Date:** 2025-11-05
**Latest Date:** 2025-11-06

---

## Executive Summary

- **Overall Pass Rate:** 83.7% (838 PASS / 163 FAIL)
- **Average Quality Score:** 87.6/100
- **Prize Candidates (High-Impact Issues):** 152 (15.2%)

---

## Key Performance Indicators

### Health Metrics

| Metric | Value | Target |
|--------|-------|--------|
| Obvious Answer Resolution (≤1 turn) | 86.1% | ≥80% |
| Good Escalation Quality | 79.9% | ≥90% |
| Clear Next Step (final turn) | 71.7% | 100% |
| Avg Cycles Without Progress | 0.25 | <1.0 |

---

## Priority Triage

### FIX NOW (Critical Issues)

**196 conversations require immediate attention**

- **.json**
  - Score: 0/100
  - Reason: High-severity MISSED_ESCALATION or DEAD_END
  - Issues: DEAD_END

- **82e25ff7-3ee0-4782-9987-d609fd468078**
  - Score: 10/100
  - Reason: High-severity MISSED_ESCALATION or DEAD_END
  - Issues: MISSED_ESCALATION, DEAD_END, LACK_OF_ENCOURAGEMENT

- **1c271241-7779-44dd-9d95-6f37b55c5254**
  - Score: 15/100
  - Reason: High-severity MISSED_ESCALATION or DEAD_END
  - Issues: REPETITIVE, DEAD_END, LACK_OF_ENCOURAGEMENT

- **0cbc2a75-2ddf-4fe4-95f2-7f25bbd5d592**
  - Score: 16/100
  - Reason: High-severity MISSED_ESCALATION or DEAD_END
  - Issues: DEAD_END, LACK_OF_ENCOURAGEMENT

- **25037dc8-8802-4b29-b0ef-28a05f5c30e4**
  - Score: 18/100
  - Reason: Futile loop: 3 cycles without progress
  - Issues: DUMB_QUESTION, REPETITIVE, MISSED_ESCALATION

- **d2eec253-5862-4247-a9fb-4ee59eaebc81**
  - Score: 19/100
  - Reason: High-severity MISSED_ESCALATION or DEAD_END
  - Issues: OBVIOUS_WRONG_ANSWER, DEAD_END, LACK_OF_ENCOURAGEMENT

- **10b46ea7-e0e3-4631-9047-83a206598e7a**
  - Score: 20/100
  - Reason: High-severity MISSED_ESCALATION or DEAD_END
  - Issues: OBVIOUS_WRONG_ANSWER, DEAD_END, LACK_OF_ENCOURAGEMENT

- **6ceb0b11-3b50-4c36-b853-c71ceca3d19c**
  - Score: 20/100
  - Reason: High-severity MISSED_ESCALATION or DEAD_END
  - Issues: OBVIOUS_WRONG_ANSWER, DEAD_END, LACK_OF_ENCOURAGEMENT

- **766e7cd4-df53-4711-b75b-597514244258**
  - Score: 23/100
  - Reason: Futile loop: 3 cycles without progress
  - Issues: REPETITIVE, DUMB_QUESTION, LACK_OF_ENCOURAGEMENT, DEAD_END

- **6667cde3-3e2a-4ddd-9714-6222319b9fed**
  - Score: 24/100
  - Reason: High-severity MISSED_ESCALATION or DEAD_END
  - Issues: MISSED_ESCALATION, REPETITIVE, OBVIOUS_WRONG_ANSWER, DEAD_END

### HIGH Priority

**2 conversations** need attention soon

---

## Pattern Analysis

### Issues by Type

| Issue Type | Count | Coverage % | Density | High | Med | Low |
|------------|-------|------------|---------|------|-----|-----|
| DEAD_END | 165 | 16.5% | 1.00 | 75 | 69 | 21 |
| MISSED_ESCALATION | 118 | 11.8% | 1.00 | 57 | 56 | 5 |
| REPETITIVE | 98 | 9.8% | 1.00 | 41 | 44 | 13 |
| OBVIOUS_WRONG_ANSWER | 76 | 7.5% | 1.01 | 27 | 39 | 10 |
| LACK_OF_ENCOURAGEMENT | 68 | 6.8% | 1.00 | 0 | 21 | 47 |
| DUMB_QUESTION | 37 | 3.7% | 1.00 | 1 | 18 | 18 |

---

## Actionable Fixes

### CRITICAL Priority Fixes

#### DEAD_END

**Occurrences:** 165 (16.5% of conversations)

**Likely Cause:** Final turn lacks link/step/timeline

**Recommended Fixes:**

1. Footer macro: one action, one link, one timeline—always
2. Guard: every final bot message must have actionable next step

**Sample Conversations:** .json, 82e25ff7-3ee0-4782-9987-d609fd468078, 1c271241-7779-44dd-9d95-6f37b55c5254

---

#### MISSED_ESCALATION

**Occurrences:** 118 (11.8% of conversations)

**Likely Cause:** Bot keeps trying despite permissions/limited access

**Recommended Fixes:**

1. Rule: "If blocked ≥1 turn by identity/billing/file access → escalate"
2. Add Handoff Macro with who/when/how + checklist
3. Instrument: flag any thread where same instruction is repeated twice

**Sample Conversations:** 82e25ff7-3ee0-4782-9987-d609fd468078, 25037dc8-8802-4b29-b0ef-28a05f5c30e4, 6667cde3-3e2a-4ddd-9714-6222319b9fed

---

### HIGH Priority Fixes

#### REPETITIVE

**Occurrences:** 98 (9.8% of conversations)

**Likely Cause:** No tactic switch after a failed step

**Recommended Fixes:**

1. "No-repeat" guard: after a repeat, switch to escalation or new path
2. Add "If X didn't work, try Y" playbooks (device, network, SSO, roster)

**Sample Conversations:** 1c271241-7779-44dd-9d95-6f37b55c5254, 25037dc8-8802-4b29-b0ef-28a05f5c30e4, 766e7cd4-df53-4711-b75b-597514244258

---

#### OBVIOUS_WRONG_ANSWER

**Occurrences:** 76 (7.5% of conversations)

**Likely Cause:** Missing/ambiguous FAQ, retrieval misses

**Recommended Fixes:**

1. Add/clarify FAQ snippet with canonical phrasing
2. Add deterministic pattern → answer rule for common questions
3. Retrieval tweak: boost exact-match titles/IDs for top intents

**Sample Conversations:** d2eec253-5862-4247-a9fb-4ee59eaebc81, 10b46ea7-e0e3-4631-9047-83a206598e7a, 6ceb0b11-3b50-4c36-b853-c71ceca3d19c

---

#### DUMB_QUESTION

**Occurrences:** 37 (3.7% of conversations)

**Likely Cause:** Bot not reading prior turns or metadata

**Recommended Fixes:**

1. Context-check rule: "Before asking, scan last 5 turns for the info"
2. Restrict clarifying questions to one specific ask with rationale
3. Auto-infer common fields (email, role, district) from header when present

**Sample Conversations:** 25037dc8-8802-4b29-b0ef-28a05f5c30e4, 766e7cd4-df53-4711-b75b-597514244258, bcd01249-0610-43aa-ac31-92af26748723

---

### MEDIUM Priority Fixes

#### LACK_OF_ENCOURAGEMENT

**Occurrences:** 68 (6.8% of conversations)

**Likely Cause:** Neutral/defensive tone, no path forward

**Recommended Fixes:**

1. Add tone snippet bank with encouraging language
2. Always pair an apology with a next step or reassuring path

**Sample Conversations:** 82e25ff7-3ee0-4782-9987-d609fd468078, 1c271241-7779-44dd-9d95-6f37b55c5254, 0cbc2a75-2ddf-4fe4-95f2-7f25bbd5d592

---

## Copy-Paste Snippet Bank

### Escalation Handoff (for MISSED_ESCALATION)

```
I'm limited by account permissions to proceed here. I'll loop in our Support team now.
What I'll send: your email, district, school, error time, and screenshot (if available).
What I need from you: student/teacher ID and exact class/section.
You'll hear from a human by today 5pm ET at this address.
```

### Dead-End Guard (for DEAD_END)

```
Next step: [Open the Guide]. If that doesn't work, reply 'human' and I'll hand this to an agent with your details.
```

### Encouragement Close (for LACK_OF_ENCOURAGEMENT)

```
You're close—we'll get this sorted. If the first step doesn't resolve it, try the next one or reply 'human' and I'll escalate.
```

### Smart Clarifying (for DUMB_QUESTION)

```
I can fix this if I know which SSO provider you use (Google | ClassLink | Clever). Which is it?
```

---

## Next Steps

1. **Address FIX NOW items** - Review critical conversations and apply fixes
2. **Implement top 3 actionable fixes** - Focus on critical and high priority
3. **Update bot prompts/policies** - Use snippet bank for consistent responses
4. **Re-run analysis** - Measure improvement after changes
5. **Set up monitoring** - Track KPIs weekly to ensure sustained quality

**Report Generated:** 1001 conversations analyzed