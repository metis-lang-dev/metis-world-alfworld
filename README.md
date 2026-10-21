# metis-world-alfworld — a small world for learning

[ALFWorld](https://github.com/alfworld/alfworld) (text-mode, TextWorld over ALFRED's
household tasks) under the metis agentic loop: the kernel's program acts through a host,
the domain agent scores every beat and records the surprises, the agentic loop proposes
rules from them, an experimental gate accepts a rule only if held-out configurations get
more predictable, the domain reloads, the agent runs again. No small model in this loop:
the approach is **design the domain first, add the interface later**. The program and its
measures: `metis-agentic-loop/docs/LEARNING.md`.

Grounding: ALFWorld's text environment carries the underlying PDDL facts, so the world's
state is atoms without a perception model — the host is the RDDL host's shape
(`metis-catalog tools/rddl_host.py`): a beat is one step of the environment, the facts
become `+atom` / `-atom` lines, the program's actions become the environment's commands.

## Layout (step 1)

| path | what |
|---|---|
| `setup.sh` | the world's venv (`.venv/`, Python 3.12): `alfworld[full]` pinned, its game data under `data/` (`ALFWORLD_DATA`) |
| `world/alf_host.py` | the host: `make(case)` → tick / on_event / observe / snapshot / restore over one ALFWorld game; the facts ↔ atoms mapping |
| `world/families.py` | the configuration families (task types × scenes) and the splits (discovery / held-out) |
| `domains/<task>/` | the packages the loop learns: a baseline program per task type, its manifest naming this host |
| `experiments/` | the runs: baseline, the closed loop, the held-out measure; their records |

## Not here
The closure (surprise → proposal → gate → reload), the gate policy and the metrics: the
metis side, in metis-agentic-loop / the loop SDK / metis-agent.
