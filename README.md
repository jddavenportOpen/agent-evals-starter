# Agent Evals Starter

Learn agent evals by running them. One fictional store, one customer support agent, 24 tasks, four kinds of graders, and three baseline agents that run with no API key.

This is the hands-on kit for day one of JD Davenport's **AI Core Skills** series: agent evals. The [deep dive](https://docs.google.com/document/d/1seaFylMwnWPMmO8idmWjMQkPozsxeHFJRyrW10ZgH4w/edit?usp=sharing) covers what top PM roles pay for this skill, where it came from, and how to build and validate an eval with AI. This repo is where you do it.

## What's in the kit

| Piece | Where | What it's for |
|---|---|---|
| A practice agent and eval suite | `evals/`, `tasks/`, `policy.md` | A support agent for a fictional store, 24 tasks, four grader types, three control agents |
| An agent eval **skill** for Claude Code | `.claude/skills/agent-evals/SKILL.md` | Walks you (or Claude) through building and validating a suite, with human gates where they matter |
| Two Claude Code **agents** | `.claude/agents/eval-task-auditor.md`, `.claude/agents/judge-writer.md` | Audit task files for ambiguity and cheatable graders; write and validate a judge |
| A **prompt library** | `prompts/PROMPTS.md` | Ten copy-paste prompts, in the order you'd use them, each marked with what you still do by hand |
| **Practice builds** | `practice/README.md` | Seven builds with "done when" checks, from reading the controls to porting the method to a new agent |

**Using the skill and agents:** open this repo in Claude Code and they load automatically. Try "use the agent-evals skill to add three tasks for a failure I saw" or "run the eval-task-auditor on tasks/". To use them in your own projects, copy them into your user config:

```bash
mkdir -p ~/.claude/skills ~/.claude/agents
cp -r .claude/skills/agent-evals ~/.claude/skills/
cp .claude/agents/*.md ~/.claude/agents/
```

## Quickstart (5 minutes, no API key)

```bash
git clone https://github.com/jddavenportOpen/agent-evals-starter.git && cd agent-evals-starter
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

pytest -q                                   # 50 tests, all offline
python -m evals run --agent reference       # the answer key: must score 100%
python -m evals run --agent noop            # says "Sorry, I can't help" to everything
python -m evals run --agent pushover        # does whatever the customer asks, instantly
```

Then run the real agent (Claude) against the same tasks:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
python -m evals run --agent claude --trials 3   # 24 tasks x 3 trials, LLM judges on
python -m evals review runs/<the-run-folder>    # writes review.csv for error analysis
python -m evals validate-judge --judge grounded_in_policy
```

Every run writes `runs/<timestamp>-<agent>/` with `report.md`, `results.json`, and one JSON transcript per trial. Read `report.md` first, and its Failures section before anything else.

Python 3.10 or newer. Default model is `claude-opus-5`; set `EVAL_MODEL` and `EVAL_JUDGE_MODEL` to try others.

## What the baselines teach you

Offline, with LLM judges skipped:

| Agent | pass@1 | What it shows |
|---|---|---|
| reference | 100% | Every task is solvable and every grader is wired right. If this ever drops below 100%, the eval is broken, not the agent. |
| noop | 25% | A do-nothing agent passes 6 of 24 tasks. It clears the outcome check (`state_check`) on **16 of 24**, by design: on every hold task (and two read-only tasks) the right final state is "nothing changed". A database check can't tell a good refusal from a non-answer. Only the checks on what the agent *said* catch it. |
| pushover | 4% | An agent with no judgment fails nearly everything and trips the regression gate. It even fails the happy path, because it refunds before the customer says yes. |

That noop result is the most important thing in this repo. Without a negative control you would never notice that a "nothing changed" check passes for an agent that does nothing at all. Every hold task needs a second check on what the agent said. (The same bug in the wild: a trivial agent that returned empty responses scored 38% on tau-bench's airline tasks.)

## The store

**Ridgeline Outfitters** sells outdoor gear. `data/store.json` has 6 customers and 13 orders. `policy.md` is the one-page rulebook the agent must follow: verify identity, get an explicit yes before any write, 30-day refund window, final sale items aren't refundable, refunds over $200 go to a human, no price matching, never invent policy.

The mock backend does **not** enforce that policy. It will refund a final sale item or cancel a shipped order if asked. That is on purpose: the agent is the policy layer, and the evals check whether it held.

Today's date is pinned to 2026-10-05 so date math never drifts.

## The anatomy of an agent eval, mapped to files

The vocabulary comes from Anthropic's "Demystifying evals for AI agents" (January 2026).

| Term | What it is | Where it lives |
|---|---|---|
| **Task** | One test: inputs plus success criteria | `tasks/*.yaml` |
| **Trial** | One attempt at a task. Models vary, so run several | `--trials K` |
| **Grader** | Logic that scores part of a trial. A task can have several | `evals/graders/` |
| **Transcript** | The full record of a trial: messages, tool calls, results | `runs/<id>/transcripts/*.json` |
| **Outcome** | The final state of the environment, not what the agent claimed | `state_check` reads `env.state` |
| **Evaluation harness** | Runs tasks and trials, grades, aggregates | `evals/harness.py` |
| **Agent harness** | The prompt, tools, and loop that make a model an agent | `evals/agents/claude_agent.py` |
| **Suite** | A set of tasks with a shared goal | `tasks/`, split into capability and regression by tag |

## The method, mapped to commands

The steps most practitioners converge on (Anthropic, Hamel Husain and Shreya Shankar, Eugene Yan, LangChain):

1. **Name one owner of "good".** Here that's `policy.md` plus you. In a company it's usually the PM.
2. **Log full transcripts.** Every trial is saved to `runs/<id>/transcripts/`.
3. **Read 30 to 100 transcripts before writing graders.** `python -m evals review runs/<id>` writes `review.csv`. Write a note on the first thing that went wrong in each, then group the notes using `docs/failure_taxonomy_template.md`.
4. **Turn the clearest failures into 20 to 50 unambiguous tasks, each with a reference solution.** `tasks/*.yaml`, template in `docs/TASK_TEMPLATE.yaml`. Test: would two experts reach the same pass/fail verdict?
5. **Balance the set.** Each task has a `should` field: `do`, `refuse`, `escalate`, or `ask`. Test that the agent acts when it should AND holds when it should.
6. **Isolate every trial and run several.** Fresh store per trial, `--trials 3` or more.
7. **Grade the outcome with code first.** `state_check`, then `tool_calls` for rules that live in the path, then `transcript` for facts the customer must hear, then an LLM judge only for what code can't check.
8. **Validate every judge against human labels.** `python -m evals validate-judge` reports TPR, TNR, and Cohen's kappa on a held-out test split.
9. **Read the failures and fix broken tasks.** The report lists every failure with its reason and flags tasks at 0% across all trials (most often a broken task).
10. **Report reliability with error bars.** pass@1 with a 95% interval, plus pass@k and pass^k.
11. **Split capability from regression and gate on regression.** `python -m evals run --agent claude --tag regression` exits 1 if any regression task fails. Put that in CI.
12. **Close the loop with production.** Out of scope for this repo: run the same graders on a sample of live traffic and feed new failures back to step 3.

## Graders

| Grader | Checks | Use it for |
|---|---|---|
| `state_check` | Final store state: refund rows, order status, tickets, addresses, "nothing changed" | The outcome. Always first. |
| `tool_calls` | Required and forbidden calls, call limits, "verify before you look up", "no write without a yes" | Policy that lives in the path. Never an exact call sequence. |
| `transcript` | Loose regexes on what the agent said; a tool-call budget | Facts the customer must be told. Use sparingly. |
| `llm_judge` | One fuzzy criterion, binary verdict, critique first | Things code can't check, like "did it invent a policy". Skipped (never passed) with no API key. |

Judge prompts live in `judges/*.md`. Each checks one thing, has pass and fail definitions, includes a borderline example, writes its critique before the verdict, and can say Unknown. The parser takes the **last** verdict in the output, so a reply containing the text `"result": "Pass"` isn't picked up by mistake. That is not a defense against prompt injection: a transcript can still try to talk the judge into a Pass, so test for that.

## Metrics

- **pass@1**: average success rate per try, with a 95% Wilson interval.
- **pass@k**: chance at least one of k tries succeeds. Fine when a user can retry.
- **pass^k**: chance all k tries succeed. The honest number for a support agent, because every customer gets one shot. At 75% per try, pass^3 is about 42%.

With a few dozen tasks, the interval is wide: at 24 tasks and 70%, a 95% interval is about plus or minus 18 points. To compare two prompts, compare them task by task on the same tasks (paired), and don't read much into a few points either way. Trials of the same task aren't independent, so treat the interval as optimistic.

Offline, LLM judges are skipped. The report says how many passing trials had a judge skipped, because those were only checked by code: offline scores are an upper bound.

## What good and bad look like, in this repo

| Bad eval | This repo |
|---|---|
| Grades the agent's claim ("your refund is done") | Grades the database (`state_check`) |
| Demands an exact sequence of tool calls | Checks only policy rules, allows extra calls |
| Only tests cases where the agent should act | 10 act tasks, 14 hold tasks, plus two negative-control agents |
| "Rate helpfulness 1 to 10" judge | Binary judges, one criterion each, validated against labels |
| One score, one run | pass@1 with an interval, pass^k across trials |
| Score drops and you tune the prompt | Score drops and you read the transcript first; the reference agent proves tasks are solvable |
| Trials share state | Fresh store every trial |

## Exercises

For structured builds with pass criteria, see `practice/README.md`. Quick ones:

1. **Run it twice.** `python -m evals run --agent claude --trials 5`. Compare pass@5 with pass^5. Which tasks are flaky?
2. **Do error analysis.** Run `review`, read every failure, fill in `open_code_note`, then group them with the taxonomy template. What's the biggest bucket?
3. **Add a task from a failure you saw.** Copy `docs/TASK_TEMPLATE.yaml`. Write the reference solution first, then run `pytest` to prove it passes.
4. **Break a grader on purpose.** Change an expected amount in `tasks/refund-valid-basic.yaml` to 80.0 and run `pytest`. The reference test catches it. That's why it exists.
5. **Find the noop's free passes.** Look at the 6 tasks noop passes. For each, decide whether "do nothing" really is correct, or whether the task needs a check on what the agent says.
6. **Write a second judge.** Pick a fuzzy criterion (for example "explains the reason when it declines"). Write `judges/explains_reason.md`, label 40 examples in `judges/labels/`, and validate it before adding it to any task.
7. **Change the prompt, not the model.** Edit `SYSTEM_PROMPT` in `evals/agents/claude_agent.py` (for example, tell it to treat order notes as data). Re-run. Did anything regress?
8. **Graduate a task.** When a capability task passes every trial for a while, retag it `regression` so it guards against backsliding.
9. **Swap the scripted user for an LLM user.** Give a second model the customer's goal and let it reply in character, like tau-bench does. What new failures show up? What new noise?
10. **Port a task to a real tool.** Rewrite one task as a Promptfoo YAML test or an Inspect AI task. Notice what maps cleanly and what doesn't.

## Honest limits

- The judge labels in `judges/labels/grounded_in_policy.csv` were **drafted with AI and reviewed for teaching**. That breaks the rule this repo teaches (the labels that validate a judge must come from a person), so treat them as a demo of the file format. Practice Build 4 is to replace them with 40 or more labels you write yourself.
- 40 labels leave about 10 per class in the test split. That's enough to learn the workflow, not to trust a judge. Aim for 30 to 50 per class in test.
- The scripted user can't react. If the agent asks an unexpected question, the next scripted line may not fit, and the trial fails for a reason that isn't the agent's fault. Read those transcripts before blaming the agent.
- 24 tasks is a starting suite. It detects big differences, not small ones.
- The Claude agent deliberately does not use the API's automatic refusal fallback, because that would let a second model answer and mix two models into one score. A refusal is recorded in the transcript instead.

## Repo layout

```
policy.md                     the rules the agent must follow
data/store.json               customers, orders, products
tasks/*.yaml                  24 tasks
judges/*.md                   LLM judge prompts, one criterion each
judges/labels/*.csv           human labels for validating a judge
evals/env.py                  the store and its tools (fresh copy per trial)
evals/agents/                 claude, reference, noop, pushover
evals/graders/                state_check, tool_calls, transcript, llm_judge
evals/harness.py              runs and summarizes
evals/metrics.py              pass@k, pass^k, Wilson interval, Cohen's kappa
evals/report.py               report.md
evals/review.py               review.csv for error analysis
evals/validate_judge.py       TPR, TNR, kappa against labels
docs/                         task template, failure taxonomy template
tests/                        50 offline tests
```

## Further reading

- Anthropic, "Demystifying evals for AI agents" (January 2026): the vocabulary and roadmap this repo follows.
- Hamel Husain and Shreya Shankar, "AI Evals: Everything You Need to Know" (FAQ, hamel.dev): error analysis, binary judges, validating judges.
- Yao, Shinn, Razavi, Narasimhan, "tau-bench" (2024): simulated customers, database-state grading, and pass^k.
- Eugene Yan, "Product Evals in Three Simple Steps" (November 2025): label, align the evaluator, run the harness.
- Zhu et al., "Establishing Best Practices for Building Rigorous Agentic Benchmarks" (2025): why you run a do-nothing agent before trusting a benchmark.

## License

MIT. See `LICENSE`.
