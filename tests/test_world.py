"""The world under test (world-alfworld step 1): the grounding, the host, the generated
package, the program. Runs under the world's venv with ALFWORLD_DATA set; the program
checks need METISC (metis-lang's compiler) and are skipped without it."""
import json, os, subprocess, sys
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "world"))
from alf_gym import Game  # noqa: E402
from alf_host import AlfHost, bindings  # noqa: E402
from ground import Handles, STATIC, DYNAMIC  # noqa: E402
import families  # noqa: E402
import gen_instance  # noqa: E402

pytestmark = pytest.mark.skipif(not os.environ.get("ALFWORLD_DATA"), reason="ALFWORLD_DATA is not set")
GAME = "pick_and_place_simple-Tomato-None-DiningTable-26/trial_T20190908_010907_122466"


def game_dir():
    return os.path.join(families.data_root(), "train", GAME)


def test_grounding_is_deterministic_across_opens():
    a = Game().open(os.path.join(game_dir(), "game.tw-pddl"))
    b = Game().open(os.path.join(game_dir(), "game.tw-pddl"))
    assert a["handles"] == b["handles"] and a["static"] == b["static"] and a["init"] == b["init"]
    assert a["task_type"] == "pick_and_place_simple"
    kinds = {k for k in a["handles"]["kind"].values()}
    assert kinds == {"location", "receptacle", "object", "otype", "rtype"}
    assert all(a_.split("(")[0] in STATIC for a_ in a["static"]) and all(a_.split("(")[0] in DYNAMIC for a_ in a["init"])


def test_handles_round_trip():
    a = Game().open(os.path.join(game_dir(), "game.tw-pddl"))
    h = Handles.from_json(a["handles"])
    assert h.to_name == a["handles"]["to_name"]
    assert all(h.to_handle[n] == k for k, n in h.to_name.items())


def test_bindings():
    assert bindings("go_obj[O=tomato2,L=loc1,L2=loc4]") == ("go_obj", {"O": "tomato2", "L": "loc1", "L2": "loc4"})
    assert bindings("choose") == ("choose", {})


def test_splits_and_families():
    c = families.counts()
    # each task directory holds its trials (two per task in train): 790 games of the first family
    assert c["train"]["pick_and_place_simple"] == 790 and c["valid_unseen"]["pick_and_place_simple"] == 24
    assert len(families.sample("valid_seen", "pick_and_place_simple", 3, seed=7)) == 3


@pytest.fixture
def package(tmp_path):
    path, nd, ns = gen_instance.generate(game_dir(), str(tmp_path))
    pkg = os.path.dirname(path)
    assert os.path.exists(os.path.join(pkg, "domain.yaml")) and os.path.exists(os.path.join(pkg, "game.json"))
    # the package includes the lifted domain by a relative path: copy it beside, as the real tree has it
    import shutil
    shutil.copy(os.path.join(ROOT, "domains", "alfred_domain.llp"), os.path.join(str(tmp_path), "alfred_domain.llp"))
    return pkg, path


def plan(h):
    """A plan from the game's own facts: the first target object, its receptacle, the first destination."""
    ot, rt = h.params["object_target"].lower() + "_t", h.params["parent_target"].lower() + "_t"
    targets = sorted(a[6:-1].split(",")[0] for a in h.static if a.startswith("otype(") and a.endswith("," + ot + ")")
                     and "pickupable(" + a[6:-1].split(",")[0] + ")" in h.static)
    dests = sorted(a[6:-1].split(",")[0] for a in h.static if a.startswith("rtype(") and a.endswith("," + rt + ")"))
    r = h.reading()
    at = next(a for a in r if a.startswith("at("))[3:-1]
    o = targets[0]
    rec = next(a for a in r if a.startswith("inrecep(%s," % o))[8:-1].split(",")[1]
    loc = next(a for a in h.static if a.startswith("recat(%s," % rec))[6:-1].split(",")[1]
    d = dests[0]
    dloc = next(a for a in h.static if a.startswith("recat(%s," % d))[6:-1].split(",")[1]
    ev = [("choose[O=%s]" % o, ()), ("go_obj[O=%s,L=%s,L2=%s]" % (o, at, loc), ())]
    if rec in h.openable:
        ev += [("open_obj[O=%s,L=%s,R=%s]" % (o, loc, rec), ()), ("take_open[O=%s,L=%s,R=%s]" % (o, loc, rec), ())]
    else:
        ev += [("take_plain[O=%s,L=%s,R=%s]" % (o, loc, rec), ())]
    ev += [("go_target[L=%s,R=%s,L2=%s]" % (loc, d, dloc), ())]
    ev += [("open_target[L=%s,R=%s]" % (dloc, d), ())] if d in h.openable else []
    ev += [("put_%s[O=%s,L=%s,R=%s]" % ("open" if d in h.openable else "plain", o, dloc, d), ())]
    return ev


def test_host_runs_the_plan_to_a_win(package):
    pkg, _ = package
    h = AlfHost(pkg)
    try:
        counts = {a: 1 for a in h.reading()}
        assert h.tick(counts) == []                     # the program at the game's state: nothing to sync
        for name, args in plan(h):
            h.on_event(name, args)
        assert all(adm for _, _, _, adm, _ in h.commands), [c for c in h.commands if not c[3]]
        assert h.won
        snap = h.snapshot()
        h.restore(snap)
        assert h.won and len(h.commands) == len(snap["commands"])
    finally:
        h.gym.close()


def test_host_refusal_leaves_the_facts(package):
    pkg, _ = package
    h = AlfHost(pkg)
    try:
        before = set(h.dyn)
        r = h.reading()
        o = next(a for a in h.static if a.startswith("target(") or a.startswith("otype("))  # any object
        h.on_event("put_plain[O=%s,L=loc1,R=sink1]" % next(a[6:-1].split(",")[0] for a in h.static if a.startswith("otype(")), ())
        assert h.commands and not h.commands[-1][3] and not h.commands[-1][4]
        assert set(h.dyn) == before
    finally:
        h.gym.close()


@pytest.mark.skipif(not os.environ.get("METISC"), reason="METISC is not set")
def test_program_reaches_placed_alone(package):
    _, path = package
    out = subprocess.run([os.environ["METISC"], "--run", path], capture_output=True, text=True, timeout=600)
    assert "Q placed 1/1" in out.stdout, out.stdout[-500:] + out.stderr[-300:]
