"""hier.py — the hierarchy with a MANUAL switch (alf-hierarchy step 1, docs/HIERARCHY.md):

    ALFWORLD_DATA=data METISC=… .venv/bin/python experiments/hier.py --split train --task pick_and_place_simple --n 10 --seed 1

One game = a sequence of kernel runs, one per activation: the task domain runs until it emits a
sub-goal (the host ends the run: the atom is a result of the task's); the driver's TABLE
(gen_hier.HANDLES, the manual switch) names the specialist; the specialist's instance is
generated over the game's current facts (the driver's mirror of the game) with the sub-goal
as its start and runs until its result atom appears; the result and the task's own tokens
go into the task's next start. Until `done` or `stuck`.

The record (experiments/records/hier-<split>-<task>-<seed>.json): per game the activations
(specialist, goal, result, commands), the win; the totals; the vector per specialist beside
the flat domain's.
"""
import argparse, json, os, shutil, subprocess, sys, tempfile, time
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "world"))
sys.path.insert(0, HERE)
import families  # noqa: E402
import gen_instance  # noqa: E402
import gen_hier  # noqa: E402
from alf_host import AlfHost  # noqa: E402
from baseline import metis_py  # noqa: E402


def run_package(path, steps=12):
    """One kernel run over a generated package; the host's log read back: the commands sent
    (rule records) and the last tick's out atoms and tokens."""
    pkg = os.path.dirname(path)
    log = os.path.join(pkg, "host.log")
    env = dict(os.environ, METIS_ALF_LOG=log, METIS_ALF_PY=os.environ.get("METIS_ALF_PY", sys.executable))
    p = subprocess.run([metis_py(), "--plugin", os.path.join(pkg, "alf_host.py:make"), path], input="run %d\n" % steps,
                       capture_output=True, text=True, env=env, timeout=600)
    recs = [json.loads(l) for l in open(log)] if os.path.exists(log) else []
    cmds = [r for r in recs if "rule" in r]
    ticks = [r for r in recs if r.get("tick")]
    last = ticks[-1] if ticks else {}
    err = None
    if p.returncode != 0 or "Traceback" in p.stderr:
        err = (p.stderr.strip().splitlines() or ["rc %d" % p.returncode])[-1]
    return {"commands": cmds, "out": last.get("out", []), "tokens": last.get("tokens", []), "error": err, "stderr": p.stderr[-400:]}


def run_game(game_dir, workdir, max_activations=16):
    """The flat package first (its game.json gives the handles and the mirror host its game)."""
    flat, _, _ = gen_instance.generate(game_dir, workdir)
    flat_pkg = os.path.dirname(flat)
    info = json.load(open(os.path.join(flat_pkg, "game.json")))
    out_dir = os.path.join(workdir, gen_instance.instance_id(game_dir))
    mirror = AlfHost(flat_pkg)                       # the driver's own copy of the game
    info = dict(info, static=sorted(mirror.static), task_type=mirror.task, params=mirror.params)
    t0 = time.time()
    commands, tokens, results, acts, error, outcome = [], gen_hier.seed(info), [], [], None, "running"
    try:
        for k in range(max_activations):
            # the task domain: until it asks for something, or is done, or stuck
            path = gen_hier.generate(game_dir, out_dir, "task", k, info, mirror.reading(), tokens + results, commands)
            r = run_package(path)
            if r["error"]:
                error, outcome = "task: " + r["error"], "error"
                break
            out = r["out"]
            if not out:
                outcome = "silent"                   # the task emitted nothing: a gap in its rules
                break
            goal = out[0]
            base = goal.split("(")[0]
            if base in ("done", "stuck", "wrong_dest"):
                outcome = base if base == "done" else "stuck: " + goal
                break
            spec = gen_hier.HANDLES[base]            # the manual switch
            tokens = r["tokens"]
            # the specialist: over the game as it is now, with the goal; until its result
            path = gen_hier.generate(game_dir, out_dir, spec, k, info, mirror.reading(), [goal], commands)
            s = run_package(path)
            if s["error"]:
                error, outcome = spec + ": " + s["error"], "error"
                break
            for c in s["commands"]:                  # mirror what the specialist did
                mirror.on_event(c["rule"], ())
                commands.append(c["command"])
            results = s["out"]
            acts.append({"k": k, "spec": spec, "goal": goal, "result": results, "commands": [c["command"] for c in s["commands"]],
                         "refused": [c["command"] for c in s["commands"] if not c["admissible"]]})
            if not results:
                outcome = spec + " silent on " + goal
                break
        else:
            outcome = "activations exhausted"
    finally:
        won = mirror.won
        mirror.gym.close()
    return {"game": game_dir, "won": won, "outcome": outcome, "activations": acts, "n_activations": len(acts),
            "commands": len(commands), "refused": sum(len(a["refused"]) for a in acts), "seconds": round(time.time() - t0, 1),
            "error": error}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="train")
    ap.add_argument("--task", default="pick_and_place_simple")
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--keep", help="keep the generated packages under this directory")
    a = ap.parse_args(argv)
    games = families.sample(a.split, a.task, a.n, a.seed)
    out = {"split": a.split, "task": a.task, "n": len(games), "seed": a.seed, "games": [],
           "vector": {s: gen_hier.vector(s) for s in gen_hier.SPECS},
           "flat": {"rules": __import__("complexity").rules_in_base(),
                    "preds": sum(1 for l in open(os.path.join(ROOT, "domains", "alfred_domain.llp")) if l.startswith(("pred ", "bwd ")))}}
    wd = a.keep or tempfile.mkdtemp(prefix="alf-hier-")
    os.makedirs(wd, exist_ok=True)
    shutil.copy(os.path.join(ROOT, "domains", "alfred_domain.llp"), os.path.join(wd, "alfred_domain.llp"))
    os.makedirs(os.path.join(wd, "hier"), exist_ok=True)
    for s in gen_hier.SPECS:
        shutil.copy(os.path.join(ROOT, "domains", "hier", s + "_domain.llp"), os.path.join(wd, "hier", s + "_domain.llp"))
    for i, g in enumerate(games):
        r = run_game(g, wd)
        out["games"].append(r)
        print("%2d %-56s %s  %d activations, %d commands, %d refused, %.0fs  %s" % (
            i + 1, g[-56:], "WON " if r["won"] else "lost", r["n_activations"], r["commands"], r["refused"], r["seconds"],
            r["outcome"] + ((" ERROR " + r["error"]) if r["error"] else "")), flush=True)
    out["won"] = sum(1 for r in out["games"] if r["won"])
    out["refusals"] = sum(r["refused"] for r in out["games"])
    os.makedirs(os.path.join(HERE, "records"), exist_ok=True)
    rp = os.path.join(HERE, "records", "hier-%s-%s-%d.json" % (a.split, a.task, a.seed))
    json.dump(out, open(rp, "w"), indent=1)
    print("won %d/%d, %d refusals; %s" % (out["won"], out["n"], out["refusals"], rp))
    return 0


if __name__ == "__main__":
    sys.exit(main())
