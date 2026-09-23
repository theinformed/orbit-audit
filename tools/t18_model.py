#!/usr/bin/env python3
"""T18 learned model: the small causal sequence model, the cadence-only
variant that fixes the artefact floor, and the geometry probe.

Registered in `docs/t18-preregistration-20260922.md` (2618343), committed alone
before this file existed. Section numbers below are that document's.

The model predicts the DISTRIBUTION of the next SGP4 residual, never the raw
state: with a zero head it IS SGP4, so the failure mode is bounded by
construction. The head is Student-t of learned degrees of freedom, because the
archive's element scatter has p99/sigma = 116 at GEO and 3,558 below 500 km and
a Gaussian likelihood is mis-specified by orders of magnitude exactly where a
manoeuvre lives. The detection statistic that falls out is the surprisal of the
observed residual under the model's own predicted distribution -- a proper
score whose threshold is set by a MEASURED false-flag rate on a control
population, never by a chosen multiple of a standard deviation.

Two variants, identical in depth, width, heads, loss, optimiser and seed:

  cadence  reads the TIMING channels alone (registration 2.1 group C)
  full     additionally reads the residual and fit channels (groups A and B)

A floor measured with a different architecture would not be a floor, so the
only difference permitted is the input projection.

GPU discipline (registration 5): one card, peak <= 4,096 MiB, through
`gpu-run --estimate-mib 4096 --class standard`. CUDA_VISIBLE_DEVICES arrives
as a UUID and is never parsed as an index. The in-process peak is read while
the batch is live and the run aborts if it exceeds the claim.

Usage:
  t18_model.py train   --variant cadence --train <npz> --validation <npz> --out <ckpt>
  t18_model.py score   --checkpoint <ckpt> --data <npz> --out <npz>
  t18_model.py probe   --checkpoint <ckpt> --train <npz> --test <npz> --out <json>
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import t18_data as td                                          # noqa: E402

SEED = td.SEED
SECOND_SEED = 20260923

# registration 4: fixed before the model was built
D_MODEL = 128
LAYERS = 6
KERNEL = 3
DILATIONS = (1, 2, 4, 8, 16, 32)
BATCH_SEQUENCES = 64
SEQUENCE_STEPS = 512
LEARNING_RATE = 3e-4
WEIGHT_DECAY = 0.01
GRAD_CLIP = 1.0
EVAL_EVERY = 2000
PATIENCE = 3
PEAK_MIB_CLAIM = 4096

N_TARGETS = len(td.TARGET_CHANNELS)
CADENCE_INPUTS = len(td.CADENCE_CHANNELS)
FULL_INPUTS = CADENCE_INPUTS + len(td.FIT_CHANNELS) + N_TARGETS

# amendment 2 A2.5: the registered no-B* ablation. Identical in depth, width,
# heads, loss, optimiser, seed, split and training budget -- the ONLY
# difference permitted is that the B* column is absent from the input
# projection. B* is both a drag/attitude channel and a known carrier of fit
# artefacts, which is why the registration made it a channel AND a named
# ablation (registration 2.1).
BSTAR_COLUMN = td.FIT_CHANNELS.index("bstar")
FULL_NOBSTAR_INPUTS = FULL_INPUTS - 1
VARIANTS = ("cadence", "full", "full-nobstar")

# registration 5: the budget, the re-price mark and the stop rule, as numbers
# rather than as prose, so that the rule can be exercised instead of asserted.
GPU_BUDGET_HOURS = 120.0
STOP_RULE_MULTIPLE = 2.0
CAMPAIGN_RUNS = 12          # the upper end of the registered 8-12
CAMPAIGN_INFERENCE_HOURS = 2.0
RATE_MARK_SECONDS = 1800.0  # the registered 30-minute mark

USAGE_LEDGER = REPO / "state" / "space-t18-learned-model-usage.jsonl"


# --------------------------------------------------------------------------
# The model
# --------------------------------------------------------------------------
def _torch():
    import torch                                               # noqa: PLC0415
    return torch


def build_model(variant: str, seed: int = SEED):
    torch = _torch()
    import torch.nn as nn                                      # noqa: PLC0415

    torch.manual_seed(seed)
    if variant == "cadence":
        in_channels = CADENCE_INPUTS
    elif variant == "full-nobstar":
        in_channels = FULL_NOBSTAR_INPUTS
    else:
        in_channels = FULL_INPUTS

    class CausalBlock(nn.Module):
        """One dilated causal convolution with a gated activation.

        Causal by left-padding only: output step k reads inputs at or before k
        and never after. A block that padded symmetrically would let the
        detection statistic read its own future, which is not a detector.
        """

        def __init__(self, width: int, dilation: int):
            super().__init__()
            self.pad = (KERNEL - 1) * dilation
            self.conv = nn.Conv1d(width, 2 * width, KERNEL, dilation=dilation)
            self.out = nn.Conv1d(width, width, 1)
            self.norm = nn.LayerNorm(width)

        def forward(self, x):
            h = self.norm(x.transpose(1, 2)).transpose(1, 2)
            h = nn.functional.pad(h, (self.pad, 0))
            a, b = self.conv(h).chunk(2, dim=1)
            return x + self.out(a * torch.sigmoid(b))

    class SequenceModel(nn.Module):
        def __init__(self):
            super().__init__()
            self.variant = variant
            self.inp = nn.Conv1d(in_channels, D_MODEL, 1)
            self.blocks = nn.ModuleList(
                [CausalBlock(D_MODEL, d) for d in DILATIONS[:LAYERS]])
            self.final = nn.LayerNorm(D_MODEL)
            # location, log scale, log(df - 2) per target channel
            self.head = nn.Conv1d(D_MODEL, 3 * N_TARGETS, 1)
            nn.init.zeros_(self.head.weight)
            nn.init.zeros_(self.head.bias)

        def hidden(self, x):
            h = self.inp(x.transpose(1, 2))
            for block in self.blocks:
                h = block(h)
            return self.final(h.transpose(1, 2))

        def forward(self, x):
            h = self.hidden(x)
            params = self.head(h.transpose(1, 2)).transpose(1, 2)
            loc, log_scale, log_df2 = params.chunk(3, dim=-1)
            return loc, log_scale.clamp(-8.0, 8.0), log_df2.clamp(-6.0, 6.0)

        def embed(self, x, mask=None):
            """The frozen per-window representation: the mean-pooled last-layer
            state, L2-normalised (registration 3.6)."""
            h = self.hidden(x)
            if mask is None:
                pooled = h.mean(dim=1)
            else:
                weight = mask.unsqueeze(-1).to(h.dtype)
                pooled = (h * weight).sum(dim=1) / weight.sum(dim=1).clamp(min=1.0)
            return pooled / pooled.norm(dim=-1, keepdim=True).clamp(min=1e-8)

    return SequenceModel()


def student_t_nll(y, loc, log_scale, log_df2):
    """Negative log-likelihood of a Student-t with learned degrees of freedom.

    df = 2 + exp(log_df2), so df > 2 always and the variance exists; a df
    drifting toward the Gaussian limit is itself a finding about the channel
    and is published rather than clipped away.
    """
    torch = _torch()
    df = 2.0 + torch.exp(log_df2)
    scale = torch.exp(log_scale)
    z = (y - loc) / scale
    return (log_scale
            + torch.lgamma(df / 2.0)
            - torch.lgamma((df + 1.0) / 2.0)
            + 0.5 * torch.log(math.pi * df)
            + (df + 1.0) / 2.0 * torch.log1p(z * z / df))


def surprisal(y, loc, log_scale, log_df2):
    """-log p of the observed residual under the model's own prediction."""
    return student_t_nll(y, loc, log_scale, log_df2)


# --------------------------------------------------------------------------
# Data assembly
# --------------------------------------------------------------------------
class Corpus:
    """Sequences from an extraction, concatenated with per-object offsets."""

    def __init__(self, path: Path):
        blob = np.load(path, allow_pickle=True)
        self.path = Path(path)
        self.norads = [int(k.split("_")[1]) for k in blob.files
                       if k.startswith("targets_")]
        self.norads.sort()
        self.targets, self.cadence, self.fit = {}, {}, {}
        self.valid, self.epoch, self.windows = {}, {}, {}
        for norad in self.norads:
            self.targets[norad] = blob[f"targets_{norad}"]
            self.cadence[norad] = blob[f"cadence_{norad}"]
            self.fit[norad] = blob[f"fit_{norad}"]
            self.valid[norad] = blob[f"valid_{norad}"]
            self.epoch[norad] = blob[f"epoch_{norad}"]
            self.windows[norad] = blob[f"windows_{norad}"]

    def __len__(self):
        return len(self.norads)

    def steps(self) -> int:
        return int(sum(int(v.sum()) for v in self.valid.values()))


def normalisation(corpus: Corpus, variant: str) -> dict:
    """Standardisation statistics from the TRAINING partition alone
    (registration 2.3). Robust centre and scale, because these channels have
    p99/sigma in the hundreds and a mean/std would be set by the tail."""
    stats = {}
    for name, store in (("targets", corpus.targets),
                        ("cadence", corpus.cadence),
                        ("fit", corpus.fit)):
        pieces = []
        for norad in corpus.norads:
            arr = store[norad]
            ok = corpus.valid[norad]
            if arr.shape[0] and ok.size == arr.shape[0]:
                arr = arr[ok]
            if arr.shape[0]:
                pieces.append(arr[::max(1, arr.shape[0] // 512)])
        if not pieces:
            continue
        block = np.concatenate(pieces, axis=0).astype(np.float64)
        centre = np.median(block, axis=0)
        spread = np.median(np.abs(block - centre), axis=0) * 1.4826
        spread = np.where(spread > 1e-12, spread, 1.0)
        stats[name] = {"centre": centre.tolist(), "scale": spread.tolist()}
    stats["variant"] = variant
    return stats


def inputs_for(corpus: Corpus, norad: int, variant: str, stats: dict):
    cad = (corpus.cadence[norad].astype(np.float64)
           - np.asarray(stats["cadence"]["centre"])) / np.asarray(stats["cadence"]["scale"])
    if variant == "cadence":
        return cad.astype(np.float32)
    fit = (corpus.fit[norad].astype(np.float64)
           - np.asarray(stats["fit"]["centre"])) / np.asarray(stats["fit"]["scale"])
    if variant == "full-nobstar":
        # the ablation removes the column and nothing else; the normalisation
        # of the surviving columns is the SAME training-partition statistic,
        # so the two variants differ in one column and not in a scale
        fit = np.delete(fit, BSTAR_COLUMN, axis=1)
    tgt = (corpus.targets[norad].astype(np.float64)
           - np.asarray(stats["targets"]["centre"])) / np.asarray(stats["targets"]["scale"])
    # the residual channels enter SHIFTED BY ONE STEP: step k may read the
    # residual observed up to k-1 and never the one it is asked to predict.
    lagged = np.zeros_like(tgt)
    lagged[1:] = tgt[:-1]
    return np.concatenate([cad, fit, lagged], axis=1).astype(np.float32)


def targets_for(corpus: Corpus, norad: int, stats: dict):
    tgt = (corpus.targets[norad].astype(np.float64)
           - np.asarray(stats["targets"]["centre"])) / np.asarray(stats["targets"]["scale"])
    return tgt.astype(np.float32)


def sample_batch(corpus: Corpus, variant: str, stats: dict, rng, device):
    torch = _torch()
    xs, ys, ms = [], [], []
    pool = [n for n in corpus.norads if corpus.targets[n].shape[0] >= 32]
    if not pool:
        raise RuntimeError("no object carries enough steps to train on")
    for _ in range(BATCH_SEQUENCES):
        norad = pool[int(rng.integers(len(pool)))]
        total = corpus.targets[norad].shape[0]
        if total <= SEQUENCE_STEPS:
            start = 0
            length = total
        else:
            start = int(rng.integers(total - SEQUENCE_STEPS + 1))
            length = SEQUENCE_STEPS
        x = inputs_for(corpus, norad, variant, stats)[start:start + length]
        y = targets_for(corpus, norad, stats)[start:start + length]
        m = corpus.valid[norad][start:start + length]
        pad = SEQUENCE_STEPS - length
        if pad > 0:
            x = np.pad(x, ((0, pad), (0, 0)))
            y = np.pad(y, ((0, pad), (0, 0)))
            m = np.pad(m, (0, pad))
        xs.append(x)
        ys.append(y)
        ms.append(m)
    return (torch.from_numpy(np.stack(xs)).to(device),
            torch.from_numpy(np.stack(ys)).to(device),
            torch.from_numpy(np.stack(ms)).to(device))


def reprice(steps_per_second: float, steps_per_run: int,
            runs: int = CAMPAIGN_RUNS,
            inference_hours: float = CAMPAIGN_INFERENCE_HOURS,
            budget_hours: float = GPU_BUDGET_HOURS,
            multiple: float = STOP_RULE_MULTIPLE) -> dict:
    """Registration 5's stop rule, computed rather than asserted.

    The achieved step rate re-prices the whole campaign. If the re-priced total
    exceeds `multiple` x the budget the campaign STOPS and the registration is
    amended before any further run. T5a's prototype found its real sweep cost
    ~9x the design estimate, so this programme has re-priced compute upward
    before and the rule is not decoration.
    """
    if not (steps_per_second and steps_per_second > 0):
        return {"measured": False,
                "reason": "a non-positive step rate cannot re-price anything; "
                          "UNMEASURED, never zero"}
    run_hours = steps_per_run / steps_per_second / 3600.0
    total = runs * run_hours + inference_hours
    threshold = multiple * budget_hours
    return {
        "measured": True,
        "stepsPerSecond": float(steps_per_second),
        "stepsPerRun": int(steps_per_run),
        "runs": int(runs),
        "hoursPerRun": run_hours,
        "inferenceHours": float(inference_hours),
        "repricedCampaignGpuHours": total,
        "budgetGpuHours": float(budget_hours),
        "fractionOfBudget": total / budget_hours,
        "stopThresholdGpuHours": threshold,
        "stop": bool(total > threshold),
        "verdict": ("STOP: the campaign is re-priced above 2x the registered "
                    "budget and the registration is amended before any further "
                    "run" if total > threshold else
                    "CONTINUE: the re-priced campaign is inside the registered "
                    "budget"),
    }


# --------------------------------------------------------------------------
# Device discipline (registration 5, extended to the Apple-silicon lane by
# amendment 4). The registration fixes ONE card and a peak ceiling; it does not
# fix a vendor, and the model, the loss, the optimiser, the seeds, the split
# and the batch order are identical on either device. What is NOT identical is
# floating-point association order, so a run that crosses devices owes the
# cross-check of amendment 4 before its numbers are pooled with a run that did
# not.
# --------------------------------------------------------------------------
def pick_device(requested: str = "auto") -> str:
    torch = _torch()
    if requested not in ("auto", None, ""):
        return requested
    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def device_report(device: str | None = None) -> dict:
    torch = _torch()
    visible = os.environ.get("CUDA_VISIBLE_DEVICES", "")
    device = device or pick_device()
    # The broker grants a card by UUID. It is passed through untouched and is
    # NEVER parsed as an index; an index parsed from a UUID would silently
    # select the wrong card.
    if device == "cuda":
        return {
            "device": "cuda",
            "cudaVisibleDevices": visible,
            "name": torch.cuda.get_device_name(0),
            "totalMiB": torch.cuda.get_device_properties(0).total_memory / 1048576.0,
        }
    if device == "mps":
        return {
            "device": "mps",
            "cudaVisibleDevices": visible,
            "name": "Apple silicon unified memory (MPS)",
            "totalMiB": torch.mps.recommended_max_memory() / 1048576.0
            if hasattr(torch.mps, "recommended_max_memory") else None,
            "note": "unified memory: there is no separate card and no broker. "
                    "Admission, the single-job lock and the usage row are the "
                    "wrapper's, not this process's.",
        }
    return {"device": "cpu", "cudaVisibleDevices": visible}


def peak_mib(device: str | None = None) -> float:
    torch = _torch()
    device = device or pick_device()
    if device == "cuda":
        return torch.cuda.max_memory_reserved() / 1048576.0
    if device == "mps":
        # driver_allocated_memory is the whole process's MPS footprint, which is
        # the honest analogue of the reserved pool; current_allocated_memory
        # would report live tensors only and would under-read the peak exactly
        # the way the prototype's 900 MiB claim under-read its 1,601 MiB truth.
        if hasattr(torch.mps, "driver_allocated_memory"):
            return torch.mps.driver_allocated_memory() / 1048576.0
        return torch.mps.current_allocated_memory() / 1048576.0
    return 0.0


def assert_within_claim(claim_mib: int = PEAK_MIB_CLAIM,
                        device: str | None = None) -> float:
    """Read the pool WHILE the batch is live and abort if it exceeds the claim.

    The prototype's 900 MiB claim against a 1,601 MiB truth was caused by
    reading the pool after freeing it, so this is read at the top of a step and
    never after a cache empty.
    """
    peak = peak_mib(device)
    if peak > claim_mib:
        raise RuntimeError(
            f"measured peak {peak:.1f} MiB exceeds the registered claim of "
            f"{claim_mib} MiB; the run aborts rather than overrun a grant")
    return peak


def write_usage(record: dict, path: Path = USAGE_LEDGER) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")


def resident_processes(device: str | None = None) -> list[dict]:
    """What else was on the card, recorded so a timing reading that shared the
    card is reported as CO-TENANTED and is not used as a clean rate."""
    import subprocess                                          # noqa: PLC0415
    if (device or pick_device()) == "mps":
        # There is no per-process GPU accounting on this lane. The wrapper's
        # lock is what makes the run exclusive, and "no resident list" is
        # reported as UNMEASURED rather than as an empty card.
        return [{"raw": "UNMEASURED: the Apple-silicon lane exposes no "
                        "per-process GPU accounting; exclusivity comes from "
                        "the wrapper's single-job lock, not from this reading"}]
    for binary in ("nvidia-smi", "/usr/lib/wsl/lib/nvidia-smi"):
        try:
            out = subprocess.run(
                [binary, "--query-compute-apps=pid,used_memory,name",
                 "--format=csv,noheader"],
                capture_output=True, timeout=20)
        except (OSError, subprocess.SubprocessError):
            continue
        lines = [ln.strip() for ln in out.stdout.decode().splitlines() if ln.strip()]
        return [{"raw": ln} for ln in lines]
    return []


# --------------------------------------------------------------------------
# Training
# --------------------------------------------------------------------------
def bound_pool(claim_mib: int, device: str | None = None) -> dict:
    """Bind the process to its own claim, in-process, rather than trusting it.

    The broker grants spare memory beside other sessions' residents; a job that
    merely intends to stay inside its estimate can still take a card down. The
    allocator is capped at the claim, so an overrun fails THIS process and
    nothing else on the card.
    """
    torch = _torch()
    device = device or pick_device()
    if device == "mps":
        return {"bounded": False,
                "reason": "MPS has no per-process allocator cap. The claim is "
                          "still asserted against the measured peak every "
                          "step, so an overrun aborts this run -- but it "
                          "aborts it AFTER the allocation, not instead of it, "
                          "and that difference is recorded rather than "
                          "glossed."}
    if device != "cuda":
        return {"bounded": False, "reason": "no card"}
    total = torch.cuda.get_device_properties(0).total_memory / 1048576.0
    fraction = min(1.0, claim_mib / total)
    torch.cuda.set_per_process_memory_fraction(fraction, 0)
    return {"bounded": True, "claimMiB": claim_mib, "totalMiB": total,
            "fraction": fraction}


def train(variant: str, train_path: Path, validation_path: Path,
          out_path: Path, max_steps: int, seed: int = SEED,
          claim_mib: int = PEAK_MIB_CLAIM,
          rate_mark_seconds: float = RATE_MARK_SECONDS,
          device_request: str = "auto", say=print) -> dict:
    torch = _torch()
    started = time.time()
    started_utc = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    corpus = Corpus(train_path)
    valid_corpus = Corpus(validation_path)
    say(f"train corpus: {len(corpus)} objects, {corpus.steps()} valid steps")
    say(f"validation:   {len(valid_corpus)} objects, {valid_corpus.steps()} valid steps")

    stats = normalisation(corpus, variant)
    device = pick_device(device_request)
    report = device_report(device)
    say(f"device: {json.dumps(report)}")
    residents_before = resident_processes(device)

    bound = bound_pool(claim_mib, device)
    say(f"pool bound: {json.dumps(bound)}")
    model = build_model(variant, seed).to(device)
    params = sum(p.numel() for p in model.parameters())
    say(f"variant {variant}: {params} parameters")
    opt = torch.optim.AdamW(model.parameters(), lr=LEARNING_RATE,
                            weight_decay=WEIGHT_DECAY)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=max_steps)
    rng = np.random.default_rng(seed)
    eval_rng = np.random.default_rng(seed + 1)

    best = math.inf
    best_state = None
    stale = 0
    peak = 0.0
    rate_mark = None
    history = []
    step = 0
    while step < max_steps:
        model.train()
        x, y, m = sample_batch(corpus, variant, stats, rng, device)
        loc, log_scale, log_df2 = model(x)
        nll = student_t_nll(y, loc, log_scale, log_df2)
        weight = m.unsqueeze(-1).to(nll.dtype)
        loss = (nll * weight).sum() / weight.sum().clamp(min=1.0) / N_TARGETS
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), GRAD_CLIP)
        opt.step()
        sched.step()
        step += 1
        peak = max(peak, assert_within_claim(claim_mib, device))

        # registration 5: the step rate is measured at 30 minutes and the
        # campaign re-priced from it. Recorded here, not asserted later.
        elapsed = time.time() - started
        if rate_mark is None and elapsed >= rate_mark_seconds:
            rate_mark = {"atSeconds": elapsed, "steps": step,
                         "stepsPerSecond": step / elapsed,
                         "markSeconds": rate_mark_seconds,
                         "registeredMarkSeconds": RATE_MARK_SECONDS,
                         "injectedClock": rate_mark_seconds != RATE_MARK_SECONDS}
            rate_mark["reprice"] = reprice(step / elapsed, max_steps)
            say(f"re-price mark FIRED: {json.dumps(rate_mark)}")
            if rate_mark["reprice"].get("stop"):
                raise RuntimeError(
                    "registration 5 stop rule: the campaign re-prices to "
                    f"{rate_mark['reprice']['repricedCampaignGpuHours']:.1f} "
                    "GPU-hours, above 2x the registered 120; the campaign "
                    "STOPS and the registration is amended before any further "
                    "run")

        if step % EVAL_EVERY == 0 or step == max_steps:
            model.eval()
            with torch.no_grad():
                losses = []
                for _ in range(8):
                    vx, vy, vm = sample_batch(valid_corpus, variant, stats,
                                              eval_rng, device)
                    vloc, vls, vdf = model(vx)
                    vnll = student_t_nll(vy, vloc, vls, vdf)
                    w = vm.unsqueeze(-1).to(vnll.dtype)
                    losses.append(float((vnll * w).sum() / w.sum().clamp(min=1.0)
                                        / N_TARGETS))
            v = float(np.mean(losses))
            history.append({"step": step, "train": float(loss.item()),
                            "validation": v,
                            "elapsedS": time.time() - started})
            say(f"  step {step}: train {loss.item():.5f} validation {v:.5f} "
                f"peak {peak:.0f} MiB {time.time() - started:.0f}s")
            if v < best - 1e-5:
                best = v
                best_state = {k: t.detach().cpu().clone()
                              for k, t in model.state_dict().items()}
                stale = 0
            else:
                stale += 1
                if stale >= PATIENCE:
                    say(f"  early stop at step {step} (patience {PATIENCE})")
                    break

    if best_state is None:
        best_state = {k: t.detach().cpu().clone()
                      for k, t in model.state_dict().items()}
    duration = time.time() - started
    residents_after = resident_processes(device)
    co_tenanted = max(len(residents_before), len(residents_after)) > 1

    learned_df = None
    model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        x, y, m = sample_batch(valid_corpus, variant, stats, eval_rng, device)
        _, _, log_df2 = model(x)
        learned_df = (2.0 + torch.exp(log_df2)).mean(dim=(0, 1)).cpu().numpy().tolist()

    payload = {
        "variant": variant,
        "seed": seed,
        "registration": "docs/t18-preregistration-20260922.md",
        "registrationCommit": "2618343",
        "parameters": params,
        "normalisation": stats,
        "history": history,
        "bestValidationNll": best,
        "learnedDegreesOfFreedom": dict(zip(td.TARGET_CHANNELS, learned_df)),
        "device": report,
        "peakMiB": peak,
        "claimMiB": claim_mib,
        "registeredCeilingMiB": PEAK_MIB_CLAIM,
        "poolBound": bound,
        "stepRateMark": rate_mark,
        "rateMarkSeconds": rate_mark_seconds,
        "wholeRunReprice": reprice(
            (step / duration) if duration > 0 else 0.0, max_steps),
        "measuredStepRate": {
            "steps": step,
            "elapsedS": duration,
            "stepsPerSecond": (step / duration) if duration > 0 else None,
            "note": "the run's own measured rate. The registered 30-minute "
                    "mark is `stepRateMark`; when a run finishes inside 30 "
                    "minutes that mark is null and this rate -- measured over "
                    "the whole run rather than its first half hour -- is what "
                    "the campaign is re-priced from.",
        },
        "steps": step,
        "durationS": duration,
        "startedUtc": started_utc,
        "deviceKind": device,
        "residentsBefore": residents_before,
        "residentsAfter": residents_after,
        "coTenanted": co_tenanted,
        "trainCorpus": {"path": str(train_path), "objects": len(corpus),
                        "validSteps": corpus.steps()},
        "validationCorpus": {"path": str(validation_path),
                             "objects": len(valid_corpus),
                             "validSteps": valid_corpus.steps()},
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"state": best_state, "meta": payload}, out_path)
    payload["checkpointSha256"] = hashlib.sha256(out_path.read_bytes()).hexdigest()
    (out_path.parent / f"{out_path.stem}-meta.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n")

    write_usage({
        "ts": started_utc,
        "consumer": "space-t18-learned-model",
        "job": f"t18_train_{variant}",
        "resource": "gpu-direct",
        "durationMs": int(duration * 1000),
        "outcome": "ok",
        "steps": step,
        "peakMiB": round(peak, 1),
        "claimMiB": claim_mib,
        "card": report.get("cudaVisibleDevices", ""),
        "cardName": report.get("name", ""),
        "deviceKind": device,
        "coTenanted": co_tenanted,
        "brokerRequestId": os.environ.get("GPU_BROKER_REQUEST_ID", ""),
    })
    # the Apple-silicon wrapper reads this line to fill its own ledger row's
    # peakBytes; absent it the wrapper records null rather than guessing.
    say(f"PEAK_BYTES={int(peak * 1048576)}")
    say(f"-> {out_path} (peak {peak:.1f} MiB, {duration:.0f}s, "
        f"device={device}, co-tenanted={co_tenanted})")
    return payload


# --------------------------------------------------------------------------
# Scoring: the detection statistic, with the shipped detector's own rule
# --------------------------------------------------------------------------
def load_checkpoint(path: Path):
    torch = _torch()
    blob = torch.load(path, map_location="cpu", weights_only=False)
    meta = blob["meta"]
    model = build_model(meta["variant"], meta["seed"])
    model.load_state_dict(blob["state"])
    model.eval()
    return model, meta


def score_corpus(model, meta: dict, corpus: Corpus, device: str = "cpu") -> dict:
    """Per-step surprisal on the dA channel, and the summed 9-channel score."""
    torch = _torch()
    stats = meta["normalisation"]
    variant = meta["variant"]
    model = model.to(device)
    out = {}
    with torch.no_grad():
        for norad in corpus.norads:
            x = inputs_for(corpus, norad, variant, stats)
            y = targets_for(corpus, norad, stats)
            if x.shape[0] == 0:
                continue
            xb = torch.from_numpy(x[None, ...]).to(device)
            yb = torch.from_numpy(y[None, ...]).to(device)
            loc, log_scale, log_df2 = model(xb)
            s = surprisal(yb, loc, log_scale, log_df2)[0].cpu().numpy()
            out[norad] = {
                "dA": s[:, 0].astype(np.float64),
                "pooled": s.sum(axis=1).astype(np.float64),
                "sign": np.sign(corpus.targets[norad][:, 0]).astype(np.float64),
                "epoch_ms": corpus.epoch[norad],
                "valid": corpus.valid[norad],
            }
    return out


def confirmed_flags(statistic: np.ndarray, sign: np.ndarray,
                    epoch_ms: np.ndarray, valid: np.ndarray,
                    threshold: float) -> np.ndarray:
    """The SHIPPED detector's confirmation rule, unchanged (registration 3.1).

    Two consecutive element sets over the bar AND agreeing in sign; the flag
    epoch is the SECOND set's, because that is the first instant a causal
    observer possessed the evidence. Adopting the baseline's own rule is what
    makes the comparison a comparison.
    """
    hit = (statistic > threshold) & valid
    if hit.size < 2:
        return np.asarray([], dtype=np.int64)
    confirmed = np.zeros(hit.size, dtype=bool)
    confirmed[1:] = hit[1:] & hit[:-1] & (sign[1:] == sign[:-1]) & (sign[1:] != 0)
    return epoch_ms[confirmed]


# --------------------------------------------------------------------------
# The geometry probe (registration 3.6)
# --------------------------------------------------------------------------
def window_embeddings(model, meta: dict, corpus: Corpus, device: str = "cpu"):
    """One frozen embedding per (object, geometry window)."""
    torch = _torch()
    stats = meta["normalisation"]
    variant = meta["variant"]
    model = model.to(device)
    rows = []
    with torch.no_grad():
        for norad in corpus.norads:
            x = inputs_for(corpus, norad, variant, stats)
            if x.shape[0] == 0:
                continue
            epochs = corpus.epoch[norad].astype(np.float64)
            t_days = (epochs - epochs[0]) / td.DAY_MS
            xb = torch.from_numpy(x[None, ...]).to(device)
            hidden = model.hidden(xb)[0]
            for lo, hi, key in corpus.windows[norad]:
                lo, hi = float(lo), float(hi)
                inside = (t_days >= lo) & (t_days < hi)
                if not inside.any():
                    continue
                sel = torch.from_numpy(np.nonzero(inside)[0]).to(device)
                pooled = hidden.index_select(0, sel).mean(dim=0)
                pooled = pooled / pooled.norm().clamp(min=1e-8)
                rows.append({
                    "norad": int(norad),
                    "windowStartDays": lo,
                    "samplingClass": str(key) if key else "",
                    "embedding": pooled.cpu().numpy().astype(np.float32),
                })
    return rows


def normalised_probe(train_rows, test_rows, label_key: str, seed: int = SEED):
    """A LINEAR probe, chance-corrected against its own majority-class rate.

    (accuracy - majority rate) / (1 - majority rate). Reported raw as well,
    because a normalised number without its majority rate hides how easy the
    task was.
    """
    from sklearn.linear_model import LogisticRegression        # noqa: PLC0415

    def pack(rows):
        keep = [r for r in rows if r.get(label_key)]
        if not keep:
            return None, None, None
        x = np.stack([r["embedding"] for r in keep])
        y = np.asarray([r[label_key] for r in keep])
        g = np.asarray([r["norad"] for r in keep])
        return x, y, g

    xtr, ytr, _ = pack(train_rows)
    xte, yte, gte = pack(test_rows)
    if xtr is None or xte is None:
        return {"measured": False,
                "reason": f"no window carries a {label_key} label"}
    shared = set(np.unique(ytr))
    keep = np.asarray([v in shared for v in yte])
    if keep.sum() == 0:
        return {"measured": False,
                "reason": "no test label class appears in training"}
    xte, yte, gte = xte[keep], yte[keep], gte[keep]
    clf = LogisticRegression(max_iter=2000, C=1.0)
    clf.fit(xtr, ytr)
    pred = clf.predict(xte)
    correct = (pred == yte).astype(np.float64)
    values, counts = np.unique(yte, return_counts=True)
    majority = float(counts.max() / counts.sum())
    accuracy = float(correct.mean())

    rng = np.random.default_rng(seed)
    objects = np.unique(gte)
    draws = []
    for _ in range(2000):
        pick = rng.choice(objects, size=objects.size, replace=True)
        mask = np.concatenate([np.nonzero(gte == o)[0] for o in pick])
        acc = float(correct[mask].mean())
        draws.append((acc - majority) / max(1e-9, 1.0 - majority))
    lo, hi = np.percentile(draws, [2.5, 97.5])
    return {
        "measured": True,
        "n": int(yte.size),
        "objects": int(objects.size),
        "classes": int(values.size),
        "accuracy": accuracy,
        "majorityRate": majority,
        "normalised": (accuracy - majority) / max(1e-9, 1.0 - majority),
        "normalisedClustered95": [float(lo), float(hi)],
        "bootstrapDraws": 2000,
        "seed": seed,
    }


def gate_g(sampling: dict, behaviour: dict) -> dict:
    """Registration 3.6: if the normalised sampling-class probe exceeds the
    normalised behaviour-class probe, the embedding FAILS and is not published.
    Evaluated once. No tuning, no second attempt on the same split."""
    if not (sampling.get("measured") and behaviour.get("measured")):
        return {"verdict": "UNMEASURED",
                "reason": "a probe could not be fitted; a gate that cannot be "
                          "evaluated is UNMEASURED, never a pass"}
    fails = sampling["normalised"] > behaviour["normalised"]
    return {
        "verdict": "FAIL" if fails else "PASS",
        "samplingNormalised": sampling["normalised"],
        "behaviourNormalised": behaviour["normalised"],
        "margin": behaviour["normalised"] - sampling["normalised"],
    }


def synthetic_probe_rows(kind: str, seed: int = SEED, objects: int = 40,
                         per_object: int = 6, dims: int = 16):
    """The probe's own positive control (registration 3.6, gate 'every control
    is a positive control or it is not a test').

    `kind='sampling'` builds embeddings that carry the sampling class and
    nothing else; `kind='behaviour'` the reverse. The probe machinery must fire
    on the first and not on the second, in both target columns.
    """
    rng = np.random.default_rng(seed)
    rows = []
    for obj in range(objects):
        sampling = f"g1:{obj % 4}"
        behaviour = f"LEO|{2000 + 10 * (obj % 3)}s"
        for _ in range(per_object):
            vec = rng.normal(0.0, 0.05, size=dims)
            if kind == "sampling":
                vec[obj % 4] += 3.0
            else:
                vec[8 + (obj % 3)] += 3.0
            vec = vec / np.linalg.norm(vec)
            rows.append({"norad": 10000 + obj,
                         "samplingClass": sampling,
                         "behaviourClass": behaviour,
                         "embedding": vec.astype(np.float32)})
    return rows


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)

    tr = sub.add_parser("train")
    tr.add_argument("--variant", choices=VARIANTS, required=True)
    tr.add_argument("--train", type=Path, required=True)
    tr.add_argument("--validation", type=Path, required=True)
    tr.add_argument("--out", type=Path, required=True)
    tr.add_argument("--max-steps", type=int, default=20000)
    tr.add_argument("--seed", type=int, default=SEED)
    tr.add_argument("--claim-mib", type=int, default=PEAK_MIB_CLAIM,
                    help="the broker claim this run is bound to; the "
                         "registered ceiling is 4096 and a smaller claim is "
                         "inside it")
    tr.add_argument("--device", default="auto",
                    help="auto picks cuda, then the Apple-silicon MPS lane, "
                         "then cpu. A run that crosses devices owes amendment "
                         "4's cross-check before its numbers are pooled.")
    tr.add_argument("--rate-mark-seconds", type=float, default=RATE_MARK_SECONDS,
                    help="the registered re-price mark is 1800 s. A smaller "
                         "value is an INJECTED CLOCK that exercises the mark "
                         "on a run shorter than half an hour; the receipt "
                         "records it as injected and the headline re-price is "
                         "never taken from an injected mark")

    sc = sub.add_parser("score")
    sc.add_argument("--checkpoint", type=Path, required=True)
    sc.add_argument("--data", type=Path, required=True)
    sc.add_argument("--out", type=Path, required=True)
    sc.add_argument("--device", default="cpu")

    pr = sub.add_parser("probe")
    pr.add_argument("--checkpoint", type=Path, required=True)
    pr.add_argument("--train", type=Path, required=True)
    pr.add_argument("--test", type=Path, required=True)
    pr.add_argument("--out", type=Path, required=True)
    pr.add_argument("--device", default="cpu")

    args = ap.parse_args(argv)

    if args.command == "train":
        train(args.variant, args.train, args.validation, args.out,
              args.max_steps, args.seed, args.claim_mib,
              args.rate_mark_seconds, args.device)
        return 0

    if args.command == "score":
        model, meta = load_checkpoint(args.checkpoint)
        corpus = Corpus(args.data)
        scored = score_corpus(model, meta, corpus, args.device)
        blocks = {}
        for norad, row in scored.items():
            for key, value in row.items():
                blocks[f"{key}_{norad}"] = value
        np.savez_compressed(args.out, **blocks)
        print(f"-> {args.out} ({len(scored)} objects)")
        return 0

    model, meta = load_checkpoint(args.checkpoint)
    train_rows = window_embeddings(model, meta, Corpus(args.train), args.device)
    test_rows = window_embeddings(model, meta, Corpus(args.test), args.device)
    print(f"embeddings: {len(train_rows)} train windows, {len(test_rows)} test")
    out = {"trainWindows": len(train_rows), "testWindows": len(test_rows)}
    out["samplingProbe"] = normalised_probe(train_rows, test_rows, "samplingClass")
    out["behaviourProbe"] = {"measured": False,
                             "reason": "behaviour labels are attached by the "
                                       "caller; see the floor measurement"}
    args.out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print(f"-> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
