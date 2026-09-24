# How to engage external reviewers

Operational procedure. Templates are verbatim — copy them as they are.

---

## What to send, to whom

| Track | Reviewer | Attach | Prompt |
|---|---|---|---|
| A — method | AI model, fresh session, no prior context | `05-external-review-dossier.md` | §1 below |
| B — estimator | Same session, as a follow-up | nothing new | §2 |
| C — scale | Same session, as a follow-up | nothing new | §3 |
| D — second opinion | AI model from a **different vendor** | `05-external-review-dossier.md` | §1, unchanged |
| E — human | Statistician | dossier + `review-data/` | §5 |

**Attach the dossier as a file. Do not paste it into the chat.** Pasted, it
gets treated as conversation and skimmed; attached, it gets treated as a
document and read.

Tracks A-C are one session. D is a separate session with a different
vendor's model — the point is not that one is better, it is that the blind
spots of two families do not coincide.

**Do not tell the reviewer what you hope to hear.** No "we think the method
is solid, can you confirm". That single sentence is enough to turn a review
into an endorsement.

---

## §1 — Opening prompt (tracks A and D)

> I'm asking you to review the methodology of a statistical index before it
> goes public. The attached dossier describes what it measures, how the data
> is collected, and what we already know is wrong with it.
>
> I am not asking whether the project is a good idea. I'm asking whether the
> number we publish means what we say it means.
>
> Please:
>
> 1. List, in order of severity, the defects that invalidate or weaken the
>    interpretation of the metric. For each, explain the mechanism — not
>    just the name of the problem.
> 2. Say whether each defect is correctable within the stated constraints
>    (10,000 API calls per day, one reading per day, no budget) or whether
>    it can only be disclosed.
> 3. Flag any claim in the document that isn't supported by the data
>    presented.
> 4. Specify which control analyses should be run on the data once
>    collected, to verify that the disclosed defects are actually under
>    control.
>
> Don't soften anything. If the method doesn't hold up, say so and explain
> why.

## §2 — Follow-up on the estimator

> The metric is a ratio: video views divided by the median views of the
> channel's recent videos in the same format. On historical data the median
> VPI is strongly associated with the size of its own denominator — 6,103x
> for baselines under 100 views, 3.7x for baselines over 100,000 — instead
> of staying flat. (Two bands establish the association, not a functional
> law.)
>
> - Is the ratio the right functional form, or should it be a log transform,
>   a within-channel standardised score, or the video's percentile rank
>   within its own channel's distribution?
> - Is the small-denominator behaviour a defect to fix in the formula, or
>   something to manage with a publication criterion?
> - Is a median over 5-20 observations stable enough to assign a level on a
>   10-step scale?
> - The denominator is computed once, at the moment the video enters the
>   chart, and frozen. Our reasoning is that the measured event can itself
>   lift the channel's other videos, which would enter the baseline window
>   days later. Is freezing the right answer, and what design would test it
>   empirically?

## §3 — Follow-up on the scale

> The ratio is classified on a 10-level scale with absolute, a priori
> thresholds. On our data the top level holds 16.8% of observations, and the
> percentiles are p50 = 7.0, p90 = 89.7, p95 = 196.8, p99 = 879.
>
> - Should the thresholds be recalibrated on observed percentiles, or does a
>   percentile-anchored scale introduce a worse defect — an observation's
>   level depending on which other observations are present?
> - Our argument for absolute thresholds is a product argument: we issue a
>   dated plaque with a frozen number, and a level that drifts over time
>   would make it worthless. Does that argument survive statistical
>   scrutiny, or are we protecting a product feature at the expense of the
>   metric?
> - Does a single scale make sense for a distribution this skewed, or are
>   separate scales needed per format, baseline band, or category?

## §4 — Follow-up on the population (optional, high value)

> Our population is videos that YouTube placed in "trending". YouTube's
> documentation says trending ranking considers how well a video performs
> compared to other recent uploads from the same channel — which is what we
> measure. The population is therefore selected on a variable correlated
> with the outcome. We cannot sample randomly: the API doesn't allow it and
> the quota wouldn't sustain it.
>
> Is disclosing this enough, or does it invalidate any distributional claim
> we make? If some claims survive and others don't, draw the line.

---

## §5 — Approaching a human reviewer

Send the dossier plus the `review-data/` folder. Email template:

> Subject: Methodology review — an independent index of relative video
> performance
>
> Dear [name],
>
> I run IOSA, a non-profit index that measures how far a YouTube video
> outperforms the median of its own channel. It is a one-person,
> zero-budget project. Before publishing anything, I would like someone with
> statistical training to tell me where the method fails.
>
> The attached dossier is deliberately written against the project: it
> states the selection biases, the mis-calibrated scale, and the errors we
> already made and corrected. The data behind every figure is included.
>
> The specific questions I cannot answer myself:
>
> 1. Our population is pre-selected by YouTube on a variable correlated with
>    what we measure. Is disclosing that sufficient, or does it invalidate
>    the distributional claims?
> 2. The metric is a ratio whose median scales as 1/denominator instead of
>    staying flat. Should it be a ratio at all?
> 3. A 10-level scale with a priori thresholds puts 16.8% of observations in
>    the top level. Recalibrate on percentiles, or keep absolute thresholds?
>
> There is no fee and no deadline, and I am not asking for an endorsement —
> a short answer saying the method does not hold up would be more useful to
> me than a long one saying it does. The index and all documentation are and
> will remain open.
>
> Thank you for considering it,
> [signature]
> iosaresearch.org

**Where to look**, in order of likely response:

1. **Cross Validated** (stats.stackexchange.com) — post questions 1-3
   separately, as self-contained statistical questions, without the project
   framing. Highest hit rate, zero cost, public answers.
2. **University departments** — statistics, computational social science,
   media studies. Target PhD students and postdocs working on platform or
   creator-economy data, not professors. An open dataset with a real
   methodological question is something they can use.
3. **r/statistics, r/AskStatistics** — same questions, informal.
4. **Open-data and data-journalism communities** — the selection-bias
   problem is one they meet constantly.

Do not pay for a review at this stage. A paid reviewer has an incentive to
deliver something that looks like value; an unpaid one who answers at all is
answering because the problem is interesting.

---

## How to handle the answers

Three reviewers will produce three partly contradictory documents. Without a
method for processing them, the result is paralysis.

**Log every finding in one table**, one row per distinct claim:

| Field | Content |
|---|---|
| Finding | The defect, in one sentence |
| Source | Which reviewer |
| Mechanism | Why it breaks the metric, in their words |
| Our position | Agree / disagree / needs data |
| Action | Change the method / disclose it / test it on data / nothing |
| Status | Open / closed |

**Then apply three rules:**

1. **A finding raised independently by two reviewers is acted on**, even if
   we disagree — if two people reading the same document reach the same
   objection, the document is at best unclear.
2. **A finding raised by one reviewer with a mechanism we cannot refute is
   acted on.** The test is not authority, it is whether we can explain why
   it is wrong.
3. **A finding that contradicts a measurement we have is rejected, with the
   measurement cited.** Reviewers work from the dossier; we have the data.

**What is not allowed**: changing the method because a reviewer said so,
without a mechanism. That is how a protocol built on evidence turns back
into a protocol built on opinion.

When the round is closed, the surviving findings go into
`01-methodology-protocol.md`, the rejected ones stay in the log with the
reason. The dossier is then re-issued as version 2, with the review round
noted in it.

---

## Sequence and timing

1. **Now** — track A, then B and C as follow-ups in the same session.
2. **Same day** — track D with a different vendor's model, prompt §1
   unchanged.
3. **Compare A and D before doing anything.** Where they agree, that is the
   real list. Where they diverge, that is where a human is needed.
4. **Then** — track E, the human. Expect days or weeks, or silence.
5. **Do not wait for E to start implementing.** The implementation follows
   `02-technical-specification.md`, and none of the questions under review
   change the collection pipeline — they change the formula and the scale,
   both downstream of collection. Data collected under a neutral protocol
   stays valid whichever way the formula question is settled.

That last point is what makes it safe to proceed: **day 0 and day 1 can
start before the review comes back.**
