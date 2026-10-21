# world-alfworld — step 1 report (the architect, 2026-10-21)

## What is built
The world repository runs ALFWorld's text games under a catalog host with the kernel's
program acting (README: the layout, the findings). A game becomes a PACKAGE
(`world/gen_instance.py`): its types, static facts and task over the lifted base
`domains/alfred_domain.llp` (ALFRED's actions as the agent's beliefs, a greedy
pick-and-place policy, 11 rules). The host (`world/alf_host.py`) turns a fired rule into
the game's command, reads the facts back, syncs the program, replays for restore and
logs every command with the game's verdict. Seven tests (`tests/`), green; the package's
case runs identically in metisc and metispy.

## The baseline (no loop): the faithful beliefs
`experiments/baseline.py`, the first family (`pick_and_place_simple`), seed 1:

| split | games | won | commands per game | refused |
|---|---|---|---|---|
| train (discovery) | 10 | **10** | 4–5 | 0 |
| valid_unseen (held-out scenes) | 10 | **10** | 4–6 | 0 |

A first run won 9/10: with several receptacles of the destination type (four drawers) the
greedy policy wandered between them (29 commands) because "open this one" and "go to
another" were both enabled; the base gained `arrived(R)` / `seeking` (one destination once
reached) and the loss went away. Records: `experiments/records/baseline-*.json`.

**Reading.** With the PDDL's own preconditions as beliefs, the world never refuses and the
task is won: this is the CONTROL. Learning needs beliefs with gaps — the learning runs
(step 3) start from ABLATED bases and the loop must recover each gap from the refusals:

| ablation | what the beliefs lack | what the world does | what the loop must learn |
|---|---|---|---|
| `no-open` | the open rules and the openable guards on take/put | a take from a closed fridge / a put into a closed cabinet: "Nothing happens." (the facts stay; the rule said it happened) | "a closed receptacle must be opened first" — one rule and two guards |
| `no-type` | `dest(R)` resolved to any receptacle (no parent type) | a put where the task wants another receptacle: the game accepts the move but never wins | the task's type condition (a goal, not a precondition: the signal is "no win", the records show where it put things) |
| `no-contain` | `cancontain` ignored (a later family: movable receptacles) | the put refused | the containment table |
| `no-hands` | `handsfree` ignored on take | a second take while holding: refused | "one thing in hand" |

Each ablation is a flag of the generator (what it leaves out of the instance) or a variant
of the base (what rules it omits), so the learning run's starting point is reproducible
and the recovered rule can be compared with the faithful one, token for token.

## The complexity vector (first family, 3 games, 15-step random walks)
`experiments/records/complexity-train-pick_and_place_simple.json`: ~190 facts per state
(~50 dynamic); 13 distinct states per 15-step walk; action branching mean 19, p95 26
(admissible commands per state); outcome branching 1 and conditional entropy 0 (the text
game is deterministic: every surprise is a missing rule, the reading the research note asks
for); horizon 5–7 (the greedy plan); 11 base rules; distribution: train 790 / valid_seen 35
/ valid_unseen 24 games of this family (the seven families: 3,553 train games); partial
observability 0.94 — the text names 6% of the placement and open facts, the host reads them
all (a later experiment can give the program only what the text names).

## Findings for the metis side (step 2)
1. The host's command log (`$METIS_ALF_LOG`) is the surprise record's raw material: the
   rule, the command, admissible or not, what changed, what the game offered instead. The
   domain agent's own record (the watch's surprise) is the one the loop should read; the
   log is the cross-check.
2. The REPL's `run N` fires every enabled rule before the first tick (all six commands in
   beat 0); the domain agent's clock (one beat, one pass) is the shape the learning runs
   need, so the closure drives the domain agent, not the REPL.
3. A refused command leaves the program's effect in place until the next sync retracts it:
   the watch sees the disagreement at the beat's end — that is the surprise. For a put
   that the game accepts but that does not win (the `no-type` ablation), the signal is the
   episode's outcome, not a surprise: the gate policy must read both.
4. `world(lines)` is unsupported (the game is the world); a scenario is another game.
5. The rule count regex in `complexity.py` counts `[dyn]` rules: 11 after `arrived`.

## Next
Step 2 (opus, nina): the closure on this world — the domain agent over a package, the
surprise record into the agentic loop with the record as the seed, the experimental gate
policy (accept iff the held-out split improves), the reload, the metrics; the ablations as
generator flags. Step 3 (the architect): the measured runs.
