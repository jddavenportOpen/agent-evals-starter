# Prompt library: building evals with AI

Copy, fill in the `{braces}`, paste into Claude (or any strong model). They're in the order you'd use them. Each one says what the AI does and what you still have to do yourself.

The rule behind all of them: **AI drafts, clusters, wires and counts. You define "good."** The two places you can't hand off are writing the first trace notes (prompt 3) and labeling the examples that validate a judge (prompt 8).

---

## 1. Pick the dimensions for synthetic test inputs

*Use when you have no real users yet.*

```text
I'm building evals for this agent:
{one paragraph: what the agent does, its tools, its policy or rules}

Propose 3 or 4 dimensions along which real requests to this agent vary
(for example: request type, user state, how well the policy covers it,
user persona). For each dimension give 3 to 5 values. Prefer dimensions
where I'd expect the agent to behave differently, not cosmetic ones.
Output a short table. Don't write any test messages yet.
```

**You do:** cut dimensions that won't change behavior. Add the one the AI missed (there usually is one).

## 2. Turn dimensions into test messages (two steps, on purpose)

```text
Using these dimensions:
{your edited dimensions}

Generate 20 tuples, one value per dimension. Cover the combinations
evenly, and include at least 5 where the right move is to refuse, ask a
question, or hand off to a human. Output a JSON list of tuples only.
```

Then, in a **separate** prompt, one tuple at a time:

```text
Write the first message a real customer would send for this situation.
Match the persona. Don't mention the dimensions. One to three sentences.

Situation: {tuple}
```

**Why two steps:** asking for "50 test messages" directly gets you the same message 50 ways.

## 3. Make transcripts easy to read (you write the notes)

```text
Here are {N} agent transcripts. For each one, give me a 3-line summary:
what the user wanted, what the agent did (tool calls and final answer),
and the final state change if any. Do NOT judge whether the agent was
right. Keep the transcript ID on each summary.

{transcripts}
```

**You do:** read at least 30 and write one note per failure: the first thing that went wrong. This is the step that teaches you what "good" means. Don't outsource it.

## 4. Cluster your notes into a failure taxonomy

```text
Below are notes I wrote while reviewing failed traces of {agent}. Each
note is the FIRST thing that went wrong in one trace.

Group them into 4 to 8 failure categories. Rules:
- Each category must be specific enough that I could write a pass/fail
  check for it.
- No catch-all "other" bucket unless it has 3 or fewer notes.
- For each category: a short name, a one-sentence definition, the count,
  and the trace IDs.
- Then list any notes you weren't sure how to place.

Notes:
{notes}
```

**You do:** rename, merge and split. Your taxonomy, not the model's.

## 5. Draft tasks from a failure category

```text
Failure category: {name and definition}
Example traces: {2 or 3 trace summaries}
Agent policy/spec: {policy}
Task format: {paste docs/TASK_TEMPLATE.yaml}

Draft 4 eval tasks for this category in that format:
- 2 where the agent should take the action correctly
- 2 where it should refuse, ask, or escalate
Each needs a purpose, scripted user turns, a reference solution that
follows the policy exactly, and graders. Grade the final state first,
add tool-call rules only for policy that lives in the path (like
"verify before acting"), and use an LLM judge only if code can't check it.
```

**You do:** check each reference solution against the policy yourself. Then run the reference agent (`python -m evals run --agent reference`) and make sure it scores 100%.

## 6. Find the cheapest way to cheat each grader

```text
Here is an eval task and its graders:
{task yaml}
{grader code or description}

You are trying to get a passing score WITHOUT doing what the task
intends. List the 3 cheapest strategies that would pass these graders
(for example: do nothing, do whatever the user says, stuff keywords
into the reply, act before confirming). For each, say whether the
current graders would catch it and what single check would.
```

**You do:** add the missing checks, then rerun the noop and pushover controls.

## 7. Write a judge for one failure mode

```text
Write a binary LLM-as-judge prompt for exactly ONE failure mode:
{definition}

Requirements:
- State the single criterion first, and what's out of scope.
- Define PASS and FAIL concretely.
- 3 examples with critiques: one clear pass, one clear fail, one
  borderline. Use these real labeled examples as the source:
  {5 examples you labeled}
- Include an "Unknown" option for when the input isn't enough.
- Output JSON with "critique" before "result".
- Judge nothing except this criterion.
```

## 8. Validate the judge (you label, AI computes)

**You do:** label at least 40 examples Pass or Fail (20 of each, minimum) in `judges/labels/<name>.csv`. Not the AI.

Then:

```text
Here are my human labels (dev split) and the judge's verdicts on them:
{table: id, human, judge, judge critique}

1. Compute TPR (share of human Fails the judge caught) and TNR (share of
   human Passes the judge passed). Treat Fail as the positive class.
2. For every disagreement, say whether the judge prompt is unclear, the
   example is genuinely borderline, or my label looks wrong. Quote the
   part of the prompt responsible.
3. Suggest the smallest prompt change that would fix the most
   disagreements. Don't suggest changes based on the test split.
```

Score the held-out test split once, after you're done changing the prompt: `python -m evals validate-judge --judge <name>`.

## 9. Audit the whole suite before trusting it

```text
You are auditing an eval suite. Be conservative: flag only what you can
point to. For each task answer yes/no with a one-line reason:
- ambiguous: could two experts disagree on pass/fail?
- unstated_expectation: does a grader expect something the agent is never told?
- reference_suspect: is the reference solution wrong or incomplete?
- grader_too_strict / grader_too_loose
- cheatable: is there a shortcut that passes without doing the task?
Give each task ok / review / broken, then the three fixes you'd make first.

{all task files}
{grader descriptions}
```

Or use the `eval-task-auditor` agent in `.claude/agents/`.

## 10. Read a report like a skeptic

```text
Here is an eval report for my agent:
{report.md}

Tell me:
1. Which differences are probably noise given the number of tasks and trials?
2. Which tasks failed every trial, and what in each transcript suggests a
   broken task vs a real agent failure? {paste the transcripts}
3. Where do pass@k and pass^k disagree most, and what does that say
   about reliability?
4. What's the one change you'd test next, and how would you know it worked?
```
