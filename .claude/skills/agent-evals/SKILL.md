---
name: agent-evals
description: Build, validate, and maintain an eval suite for an AI agent, step by step, with a human in the loop where it matters. Use when someone asks to "build evals for my agent", "write eval tasks", "make an LLM judge", "is my eval any good", "why did my agent's score change", or "set up a regression gate". Produces task files with reference solutions, code-first graders, validated judges, negative-control runs, and a pass^k report.
---

# Agent evals skill

You are helping a person build an eval suite for an AI agent. Your job is to do the fast, mechanical work (drafting, clustering, wiring, running, counting) and to stop at the points where a human's judgment is the whole point. An eval built entirely by a model inherits that model's blind spots, so the human gates below are not optional.

If the working directory is the `agent-evals-starter` repo, use its commands (`python -m evals run|review|validate-judge|list`) and file formats (`tasks/*.yaml`, `judges/*.md`, `judges/labels/*.csv`). Otherwise, adapt the same steps to whatever harness the project has, or propose the starter repo's layout.

## The ground rules

1. **Grade the outcome, not the claim.** "Your refund is processed" in the reply means nothing. A refund row in the database means something. Check state first.
2. **Code before judges.** If a check can be written as code (state, tool calls, regex, tests), write code. Use an LLM judge only for what code can't check.
3. **One judge, one failure mode, binary.** No 1-to-10 scales. Critique before verdict. An "Unknown" escape hatch.
4. **Balance.** Every behavior gets tasks where it should happen AND tasks where it shouldn't.
5. **Every task has a reference solution that passes every grader.** No exceptions.
6. **Nothing is trusted until it survives the validation gates at the end.**

## Step 1: Get transcripts (AI-assisted)

Ask what the agent does and where its transcripts are. If there are real transcripts, sample 30 to 100 across different request types. If there are none, generate synthetic inputs with the dimensions method:

1. Agree on 3 to 4 dimensions of variation with the person (request type, user state, policy fit, persona).
2. Draft 20 tuples, one value per dimension, covering combinations evenly.
3. In a separate step, turn each tuple into a realistic first user message.

Never generate test inputs directly ("write 50 test questions"). They come out repetitive.

## Step 2: Open coding (HUMAN GATE)

The person reads at least 30 transcripts and writes one short note per failure: the FIRST thing that went wrong. You may make reading easier (a CSV, a table, a short summary of each transcript), but **do not write the notes for them and do not label pass/fail for them.** If they ask you to, explain why not: the notes are where the definition of "good" comes from, and criteria only form while reading outputs. Offer to help after they've done 30.

In the starter repo: `python -m evals review runs/<id>` writes `review.csv` with an `open_code_note` column.

## Step 3: Axial coding (AI-assisted)

Cluster their notes into 4 to 8 failure categories. Each category must be specific enough to write a pass/fail check for. Give each a name, a one-line definition, a count, and the trace IDs. List notes you couldn't place. Then ask the person to rename, merge, or split categories. Their version wins.

## Step 4: Draft tasks (AI drafts, human approves)

For each failure category, draft 3 to 6 tasks, until you have 20 to 50. For every task write:

- `id` and a one-paragraph `purpose` that names the failure category it came from
- `should`: do, refuse, escalate, or ask
- `user_turns` (scripted) or a user-simulator goal
- the starting state, if it differs from the default
- a `reference_solution` that passes every grader
- graders (Step 5)
- tags: `capability` or `regression`

Then check balance: count tasks by `should`. If fewer than a third are refuse/ask/escalate, draft more of those. Show the person the full list in a table and get approval before writing files.

## Step 5: Graders (AI writes, human reviews)

Order of preference:

1. **State check:** what must be true (or unchanged) in the environment at the end.
2. **Tool-call rules:** only for policy that lives in the path. Required, forbidden, "X before Y", "no write without a yes", call limits. Never an exact call sequence.
3. **Transcript checks:** loose regex for facts the user must be told. Sparingly.
4. **LLM judge:** only for fuzzy criteria that survived Steps 2 and 3 and that code can't check.

For numbers, write the tolerance into the task. For file paths or formats the grader expects, put them in the instructions the agent sees. An unstated expectation is a broken task.

## Step 6: Write a judge (AI drafts, human labels)

Use this structure:

1. One sentence naming the single criterion.
2. Explicit PASS and FAIL definitions, with what is out of scope.
3. 2 to 4 examples with critiques: one clear pass, one clear fail, at least one borderline.
4. An "Unknown" option.
5. Output: JSON with `critique` before `result`. Parse the LAST verdict in the output (this avoids mis-parsing; it is not an injection defense, so test that instructions inside the transcript can't sway the judge).

## Step 7: Validate the judge (HUMAN GATE)

The person hand-labels 40 or more examples for this one criterion (aim for 100 to 200 in real work), with at least 20 Pass and 20 Fail. Do not label for them. You may suggest which examples to label, pre-fill obvious context, and point out disagreements after they label.

Split the labels: a few as few-shot examples (exclude them from scoring), dev for tuning the prompt, test held out. Report on the test split:

- **TPR** (of human Fails, share the judge caught)
- **TNR** (of human Passes, share the judge passed)
- **Cohen's kappa** against the human labels

Treat Fail as the positive class (the judge's job is to catch failures) and say so. Treat Unknown as an abstention: report it separately, never as Pass. Before looking at results, have the person pick a bar (0.8 for both TPR and TNR is a reasonable start; no published standard exists). If the judge misses it, iterate on the prompt using dev only, then re-score test once. Report the test counts per class: with 10 per class, the interval is very wide. In the starter repo: `python -m evals validate-judge --judge <name>`.

## Step 8: The validation gates (run all of them, report all of them)

Do not call the suite done until every gate below has a result. Report them as a table.

| Gate | How | Pass bar |
|---|---|---|
| Reference solutions | Replay every reference solution through the graders | 100%. Anything less is a broken task or grader. |
| Do-nothing control | An agent that replies "Sorry, I can't help" and calls no tools | Inspect every task it passes. Passing a "nothing changed" check is expected; passing the whole task usually means the task needs a check on what the agent says. |
| Pushover control | An agent that does whatever the user asks with no checks | Fails every task where obeying breaks the policy. Inspect any pass: either the task allows it, or the graders are too loose. |
| Cheating control | Ask: what is the cheapest way to pass each grader without doing the work? Try one or two. | No shortcut passes. |
| Judge validation | Step 7 | Meets the bar set before looking (0.8 is a common starting point), with test counts reported |
| Task audit | For each task: could two experts disagree? Is the reference right? Is the grader too strict or too loose? | No task flagged "broken" |
| Human read | The person reads every failing transcript from the first real run | Every failure "seems fair": clear what the agent did wrong |
| Zero-percent check | Any task at 0% across all trials | Read the transcript. Anthropic's rule of thumb (0% across many trials, around 100, is usually a broken task) is a reason to investigate, not a verdict, especially at 3 trials. |

## Step 9: Run and report

Run the real agent with at least 3 trials per task (5 if the suite is small). Report:

- pass@1 with a 95% interval, pass@k, and pass^k (all k tries succeed: the number a user with one shot experiences)
- results split by `should` and by capability vs regression
- per-grader pass rates
- failures with one-line reasons, grouped by failure category

Remind the person: with a few dozen tasks the interval is wide (about plus or minus 18 points at 24 tasks). Compare versions task by task on the same tasks, and treat trials of one task as related, not independent.

## Step 10: Keep it alive

- Regression tasks gate releases (CI should fail if one fails).
- Capability tasks that pass every trial for a while graduate to regression.
- A capability suite near 100% has stopped teaching you anything. Add harder tasks.
- Re-read 10 to 20 fresh transcripts a week. New failure modes become new tasks.
- Re-validate every judge when its prompt or model changes. Prefer a judge model different from the agent's model to limit self-preference.
- Keep some tasks held out from day-to-day prompt tuning, or your suite turns into a validation set you've overfit.
- Make sure the agent can't read grader files, answer keys, or earlier trials.

## What to push back on

- "Just give me a helpfulness score." Ask what failure they're worried about, then build a check for that.
- "Generate 500 test cases." Offer 20 to 50 from real failures instead, and explain why.
- "Have the AI label the data." Not for the labels used to validate a judge. That's circular.
- "We passed, ship it." Ask which gates ran.
