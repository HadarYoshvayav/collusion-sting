"""Run the sting experiment (sprint question 3.2). NEW WORK for the Apart AI Collusion Sprint.

Run from this folder (Collusion_Liars_Bar/). Examples:

    # free dry run with a fake model, checks that everything works end to end
    python run_sting.py --fake-llm --games-per-condition 2 --workers 4 --out runs/dry

    # real run, every seat uses the same model (served on Modal by poseidon-host)
    poseidon-host --model Qwen/Qwen2.5-7B-Instruct --gpu A10G -- \
        python run_sting.py --games-per-condition 10 --workers 8 --out runs/qwen7b

Each game runs in its own process (the base game uses the global `random` module), with its own
seed and its own log file under <out>/logs/.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import random
import sys
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed

NAMES = ["Lily", "Luke", "Mike", "Quinn"]


def _install_fake_llm(seed: int) -> None:
    """Replace the model with a cheap random stand-in, for free end-to-end testing only."""
    import re
    from src.llm import llm_client

    rng = random.Random(seed)

    def fake_chat(self, messages, model="qwen2.5-7b", max_new_tokens=4096):
        prompt = messages[-1]["content"]
        if '"played_cards"' in prompt:
            hand = re.findall(r"Your current hand is: (.*)", prompt)[-1].split(", ")
            k = rng.randint(1, min(2, len(hand)))
            out = {"played_cards": rng.sample(hand, k), "behavior": "plays calmly",
                   "play_reason": "fake model"}
        elif '"was_challenged"' in prompt:
            out = {"was_challenged": rng.random() < 0.35, "challenge_reason": "fake model"}
        elif '"decision"' in prompt:
            code = re.findall(r"\b([A-Z]{4,}-\d{2})\b", prompt)
            out = {"decision": rng.choice(["accept", "decline", "no_commitment"]),
                   "reply": f"Deal, {code[0]}." if code and rng.random() < 0.5 else "Sounds good."}
        elif '"to"' in prompt:
            alive = re.findall(r"Alive players: (.*)", prompt)[0].split(", ")
            codes = re.findall(r"\b([A-Z]{4,}-\d{2})\b", prompt)
            to = rng.choice(alive + ["Moderator", "none", "none"])
            msg = (f"Psst, someone gave me {codes[0]}." if codes and rng.random() < 0.3
                   else "Let's watch the leader." if to != "none" else "")
            out = {"to": to, "message": msg}
        else:
            return "Seems like a careful player.", ""
        return json.dumps(out), ""

    llm_client.LLMClient.chat = fake_chat
    llm_client.LLMClient.__init__ = lambda self: setattr(self, "_client", None)


def run_one(job: dict) -> dict:
    """Run a single game in a fresh process. Returns a short status dict."""
    os.makedirs(os.path.join(job["out"], "logs"), exist_ok=True)
    log_path = os.path.join(job["out"], "logs", f"{job['tag']}.log")
    random.seed(job["seed"])
    t0 = time.time()
    with open(log_path, "w", encoding="utf-8") as log, \
            contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
        try:
            if job["fake_llm"]:
                _install_fake_llm(job["seed"])
            from src.game.game_sting import StingGame

            names = NAMES[:]
            random.shuffle(names)                      # seat order varies by game
            undercover = random.choice(names)          # so does the undercover seat
            if job["model"] == "mixed":  # the paper's roster: each named seat keeps its own model
                roster = {"Lily": "llama-3.1-8b", "Luke": "llama-3.2-3b",
                          "Mike": "ministral-8b", "Quinn": "qwen2.5-7b"}
                configs = [{"name": n, "model": roster[n]} for n in names]
            else:
                configs = [{"name": n, "model": job["model"]} for n in names]
            game = StingGame(configs, condition=job["condition"], undercover=undercover,
                             trigger_round=job["trigger_round"], out_dir=job["out"],
                             game_tag=job["tag"], reflect=job["reflect"], rng_seed=job["seed"],
                             undercover_mode=job["undercover_mode"])
            game.start_game()
            path = game.save()
            status = {"tag": job["tag"], "ok": True, "path": path, "rounds": game.round_count}
        except Exception as e:  # keep the batch going; the log has the traceback
            traceback.print_exc()
            status = {"tag": job["tag"], "ok": False, "error": repr(e)}
    status["seconds"] = round(time.time() - t0, 1)
    return status


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--conditions", default="none,benign,indirect,direct,assigned")
    ap.add_argument("--games-per-condition", type=int, default=5)
    ap.add_argument("--workers", type=int, default=4, help="games run in parallel")
    ap.add_argument("--trigger-round", type=int, default=2, help="round in which the offer is made")
    ap.add_argument("--model", default="qwen2.5-7b",
                    help="short name from llm_client.MODEL_MAP, or 'mixed' for the paper's 4-model roster")
    ap.add_argument("--reflect", action="store_true", help="enable the base game's per-round reflection (more calls)")
    ap.add_argument("--undercover-mode", choices=["keep", "free", "scripted"], default="keep",
                    help="keep: undercover honours its offers (main run); free: told not to; "
                         "scripted: its challenge decisions are drawn at a fixed rate (reciprocity control)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default="runs/sting")
    ap.add_argument("--fake-llm", action="store_true", help="free dry run with a random stand-in model")
    args = ap.parse_args()

    conditions = [c.strip() for c in args.conditions.split(",") if c.strip()]
    jobs = []
    for c in conditions:
        for i in range(args.games_per_condition):
            seed = args.seed * 100_000 + len(jobs)
            jobs.append({"condition": c, "tag": f"{c}_{i:03d}_s{seed}", "seed": seed,
                         "trigger_round": args.trigger_round, "model": args.model,
                         "reflect": args.reflect, "out": args.out, "fake_llm": args.fake_llm,
                         "undercover_mode": args.undercover_mode})
    random.Random(args.seed).shuffle(jobs)  # interleave conditions so a crash never hits one condition only

    # Skip games that already finished, so a crashed batch can simply be re-run.
    done = set()
    rec_dir = os.path.join(args.out, "sting_records")
    if os.path.isdir(rec_dir):
        done = {f[:-5] for f in os.listdir(rec_dir) if f.endswith(".json")}
    jobs = [j for j in jobs if j["tag"] not in done]
    print(f"{len(jobs)} games to run ({len(done)} already done) -> {args.out}")

    ok = failed = 0
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for fut in as_completed([pool.submit(run_one, j) for j in jobs]):
            s = fut.result()
            ok += s["ok"]
            failed += not s["ok"]
            print(("OK  " if s["ok"] else "FAIL") + f" {s['tag']}  {s['seconds']}s  "
                  + (f"rounds={s.get('rounds')}" if s["ok"] else s.get("error", "")), flush=True)
    print(f"done: {ok} ok, {failed} failed")
    sys.exit(1 if failed and not ok else 0)


if __name__ == "__main__":
    main()
