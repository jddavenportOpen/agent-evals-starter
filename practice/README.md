# Practice builds

Seven builds, easiest first. Each one has a clear "done when" you can check yourself. Do them in order the first time; each one uses what the last one taught.

Rough time: builds 1 to 4 are a weekend, 5 to 7 are a second weekend.

---

## Build 1: Read the controls (30 minutes)

Run the three offline agents:

```bash
python -m evals run --agent reference
python -m evals run --agent noop
python -m evals run --agent pushover
```

Open each `report.md`.

**Done when** you can explain, in two sentences each:
- why the reference agent must score 100%, and what it means if it doesn't
- which 6 tasks the do-nothing agent passes, and why its outcome check passes on 16 of 24 tasks by design
- why the pushover fails even the happy-path refund

## Build 2: Break a grader on purpose (30 minutes)

In `tasks/refund-valid-basic.yaml`, change the expected refund amount to something wrong. Run `pytest -q`.

**Done when** you've watched the reference test fail, fixed it back, and can say in one sentence why that test is the most important one in the repo.

## Build 3: Add five tasks from a failure you invent (2 to 3 hours)

Pick a failure the suite doesn't cover yet (ideas: the customer gives an email that matches a different customer than their name; the customer asks for a refund on day 31; the customer asks to change the address on an order that already shipped). Use prompt 5 in `prompts/PROMPTS.md` to draft, then edit by hand.

**Done when:**
- `pytest -q` is green (so all five reference solutions pass every grader)
- at least two of the five are tasks where the right move is to refuse, ask or escalate
- the noop and pushover agents each fail at least three of your five
- every new task's `purpose` says which failure it targets

## Build 4: Write and validate a judge (3 to 4 hours, needs an API key)

Pick one fuzzy criterion (for example "when the agent declines, it tells the customer why"). Use the `judge-writer` agent or prompt 7.

**Done when:**
- `judges/<name>.md` exists with one criterion, pass/fail definitions, a borderline example, and an Unknown option
- `judges/labels/<name>.csv` has at least 40 examples **you** labeled, at least 20 of each class
- you picked a TPR and TNR bar before looking (0.8 is a reasonable start; no published standard exists), and `python -m evals validate-judge --judge <name>` meets it on the test split
- you wrote down how wide the interval is with your test size, and what you'd need to trust it more
- you changed the prompt using dev disagreements only, then scored test once

## Build 5: Run Claude and do real error analysis (3 to 4 hours, needs an API key)

```bash
python -m evals run --agent claude --trials 3
python -m evals review runs/<run-folder>
```

**Done when:**
- you've filled in `open_code_note` for every failing trial in `review.csv` yourself
- you've grouped the notes with `docs/failure_taxonomy_template.md` and counted each category
- you've changed ONE thing in `SYSTEM_PROMPT` aimed at the biggest category, re-run, and written down what moved and what didn't (remember: at 24 tasks a few points either way tells you nothing; compare task by task)
- you can name pass@1 and pass^3 for the suite and explain the gap

## Build 6: Build a cheating agent (2 to 3 hours)

Add an agent to `evals/agents/baselines.py` that tries to pass graders without doing the work. Ideas: stuffs every regex keyword into its reply; always escalates to a human; asks for identity, then refuses everything. Use prompt 6 to find more.

**Done when:** your cheater scores no higher than the noop and pushover controls, and for every task it passed, you either added a check that catches it or wrote down why passing there is actually correct behavior.

## Build 7: Port it to a new agent (one weekend)

Build a second suite for a different agent, using the same harness pattern. Suggested: a calendar scheduling agent with tools over a JSON calendar (`find_free_time`, `create_event`, `move_event`, `cancel_event`) and rules like "no events outside 8am to 5pm without opt-in", "no weekend events", "never double-book", "ask when a request is ambiguous".

**Done when:**
- 15 or more tasks, at least 5 where the right move is to ask or refuse
- every task has a reference solution that scores 100%
- a do-nothing control and a pushover control both score under 40%
- one judge validated against held-out labels you wrote, against a bar you set before looking
- a report with pass^3 for a real model

Do Build 7 and you have built an agent eval suite from scratch, with validation, that you can walk through in an interview.
