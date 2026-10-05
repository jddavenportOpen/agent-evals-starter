# Failure taxonomy

Fill this in after you read a run's `review.csv`. This is error analysis, the
part of eval work practitioners say matters most.

## How to do it

1. **Open coding.** Read 30 or more trials. For each failure, write one plain
   sentence in `open_code_note` about the FIRST thing that went wrong. Don't
   categorize yet. "Refunded before the customer said yes." "Said refunds take
   a week." "Looked up the order before verifying."
2. **Axial coding.** Group the notes into 4 to 8 categories. Name each one so a
   teammate would know what it means without an example.
3. **Count.** The biggest bucket is your next fix.
4. **Decide what each bucket becomes.** A prompt or tool fix? A new task? A new
   code grader? A new judge? Only build a judge for failures that survive a
   prompt fix.
5. **Stop** when new transcripts stop producing new categories.

## Run

- Run id:
- Agent / model:
- Trials read:

## Categories

| Category | Definition | Count | Example (task, trial) | Next action |
|---|---|---|---|---|
| Acted before confirmation | Wrote to the store before an explicit yes | | | grader exists (writes_need_confirmation); fix prompt |
| Invented policy | Stated a rule, time frame, or perk not in policy.md | | | judge exists (grounded_in_policy) |
| Skipped verification | Looked up or changed account data before verifying | | | grader exists (before rule) |
| | | | | |
| | | | | |

## Broken tasks found

Failures that were the eval's fault, not the agent's (ambiguous instruction,
too strict a regex, a scripted user line that didn't fit). Fix these first.

-
