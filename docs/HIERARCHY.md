# ALFWorld as a hierarchy of domains (alf-hierarchy, the architect, 2026-10-22)

The user: "split ALFWorld into hierarchical domains to reduce complexity — first with a
manual switch and domain activation; add an LLM agent and intents per domain; add an
orchestrator domain and find the way to activate domains automatically."

## Why split

The flat `alfred_domain.llp` (step 1) holds the whole household in one program: 11 rules,
31 predicates, every static fact of the game (~500) and every dynamic fact (~30) in one
grounding, and one policy token set (`want`, `carrying`, `arrived`, `seeking`) threaded
through all of it. It wins 20/20, and it is the wrong shape for learning: a rule the loop
proposes about opening a fridge is grounded against tomatoes and countertops; the surprise
"the drawer would not open" lands in a program where going, taking and putting share the
state; and a person's "open the fridge" has no domain of its own to be typed into.

A hierarchy puts each activity in a domain that sees only what the activity needs. The
complexity vector (LEARNING.md) is measured PER DOMAIN, and the claim is that every
specialist's vector is a fraction of the flat one while the task still wins.

## The specialists (`domains/hier/*_domain.llp`, lifted; instances generated per game)

| domain | goal in (its port) | result out | world facts it sees | rules |
|---|---|---|---|---|
| `nav` | `goto(R)` | `reached(R)` | `at(L)`; `recat(R, L)` | go, here |
| `access` | `open(R)` | `accessible(R)` / `refused(R)` | `at`, `opened`, `closed`; `recat`, `openable`, `notopenable` | open_closed, already_open, no_door, not_here |
| `grasp` | `take(O)` | `taken(O)` / `refused(O)` | `at`, `objat`, `inrecep`, `opened`, `closed`, `holds`, `holding`, `handsfree`; `recat`, `openable`, `notopenable` | take_open, take_plain, not_here, shut, hands_full |
| `place` | `put(O, R)` | `placed(O, R)` / `refused(R)` | `at`, `opened`, `closed`, `holds`, `holding`, `handsfree`; `recat`, `openable`, `notopenable` | put_open, put_plain, not_here, shut, empty_handed |
| `task` | `fetch(O, R)` — the one way in: the FETCH intent a person types, or the driver's seed (first target, first destination); the task's facts `target(O)`, `dest(R)`, `notdest(R)`; the results above | `goto`, `open`, `take`, `put` (the sub-goals), `done`, `stuck(X)`, `wrong_dest(R)` | `inrecep(O, R)` | fetch, not_dest, go_for, open_for, take_for, go_dest, open_dest, put_dest, finish, stuck_fetch, stuck_carry |

Conventions, the same as console-nav's ui base:
- a goal atom is consumed by exactly one rule per state (the explorer's check), and every
  non-acting outcome has a `%%` line — `already_open` ("{R} is already open"), `no_door`
  ("{R} has nothing to open"), `not_here` ("I am not at {R}") are rules, not silences;
- a REFUSAL is a result (`refused(R)` with its reason line), never a stall: the task's
  `stuck(X)` rule turns it into the episode's end, and in task 2's policy that is the
  disengagement point;
- the acting rules keep the names the host's command table knows (`go`, `open_closed`,
  `take_open`/`take_plain`, `put_open`/`put_plain`); the rest send no command;
- LL has no negation: the instance supplies `closed(R)`, `notopenable(R)`, `handsfree`.

The task domain is the planner: it emits one sub-goal at a time and waits for the result
atom; it never acts in the world itself. Its policy is the flat domain's greedy one,
re-stated as sub-goals: fetch the target where it is (go, open, take), carry it to the
destination (go, open, put). It does not know whether a receptacle is openable — it always
asks `access`, which answers at once when there is nothing to open. That is the point of
the split: the task knows WHAT, the specialists know HOW.

## Step 1 — the manual switch (the architect; this step)

`experiments/hier.py` runs one game as a sequence of kernel runs, one per activation:

1. the `task` instance runs until a sub-goal atom appears (the host sees it in the
   counts and ends the episode: tick → None);
2. the driver activates the specialist that HANDLES that atom — a table in the driver,
   `{goto: nav, open: access, take: grasp, put: place}`, written by hand (this is the
   manual switch);
3. the specialist's instance is generated with the game's CURRENT facts (the driver mirrors
   every command onto its own copy of the game; the specialist's host replays the same
   commands, `game.json: replay`) and the sub-goal as its `#init`; it runs until a result
   atom appears;
4. the result goes into the task's next `#init` with the task's own tokens carried over
   (the host logs the program's own tokens at each tick); back to 1 until `done` or
   `stuck`.

What is measured: per game the activations, the commands, the win; per domain the vector
(rules, predicates, declared types' sizes, `#init` facts) against the flat domain's. The
record: `experiments/records/hier-<split>-<task>-<seed>.json`, the report in
`experiments/REPORT.md` §hierarchy.

## Step 2 — the agent and the intents per domain (opus, nina)

Each specialist gets an `intent.yaml` (nav: GO(receptacle); access: OPEN(receptacle);
grasp: TAKE(object); place: PUT(object, receptacle); task: FETCH(object, receptacle) over
the game's words) and a card checked on Gemma E2B with `metis_agent.intent_check` per
domain AND on the union — the union's miss rate is the number the director then removes
(it serves two cards, not five). The domain agent (metis-agent) over a specialist package
runs the kernel as the flat one did, with the person's words typed into the ATTENDED
specialist's card. Nothing of the flat domain changes; the hierarchy is a second tree under
`domains/hier/`.

## Step 3 — the orchestrator domain (the architect writes the base and the instance; opus
the orchestrator; nina the generator)

The director (metis-agent `docs/DIRECTOR.md`) replaces the driver's table with rules:
`handles(nav, goto)`, `handles(access, open)`, … are the instance's facts, GENERATED from
the specialists' declared ports (decision 1); `+seen(goto(R))` from the task wakes `nav`
and forwards the goal; a `refused(R)` from a specialist re-routes once (to `nav` when the
reason is `not_here`), then escalates; `attention` follows the last routed goal (decision
2); `linger` is a manifest key, 1 beat here (decision 3); the orchestrator serves the
director's card and the attended specialist's only (decision 4). Automatic activation has
two sources, and both are `seen/1`: the task's sub-goals (goal-driven) and the world's facts
a specialist handles (`holding` makes `place` relevant, `closed(R)` at `R` makes `access`
relevant) — the second source is what makes the director more than a dispatcher, and it is
measured by the same driver: the task domain's sub-goals switched OFF, the world's facts
alone waking specialists (a weaker policy, the gap recorded).

## What it gives the agent paper

The same family, three programs: flat (step 1 of world-alfworld), hierarchical by hand
(this subject), hierarchical by the loop (loop-policy's refactoring phase) — each with its
complexity vector and its held-out success. The reduction is the claim; the loop
reproducing the hand split is the result.
