"""Example: ML training run report.

Mirrors the handoff §3.1 scenario. Run it directly:

    pip install "runscroll[matplotlib]" numpy
    python examples/ml_training_run.py

Output: examples/out/ml_training_run.html — open it in a browser. The whole
report (metrics, loss curves, confusion matrix, sample worst predictions)
is in that one self-contained file.
"""
from __future__ import annotations

import io
import math
import random
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from runscroll import Collector


def _train_one_epoch(epoch: int, history: dict) -> tuple[float, float, float]:
    """Mock training step — returns (train_loss, val_loss, val_acc)."""
    train_loss = 1.5 * math.exp(-0.4 * epoch) + random.uniform(-0.05, 0.05)
    val_loss = 1.7 * math.exp(-0.35 * epoch) + random.uniform(-0.05, 0.08)
    val_acc = 1 - val_loss / 2 + random.uniform(-0.02, 0.02)
    history["train_loss"].append(train_loss)
    history["val_loss"].append(val_loss)
    history["val_acc"].append(val_acc)
    return train_loss, val_loss, val_acc


def _plot_loss_curves(history: dict) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(history["train_loss"], label="train")
    ax.plot(history["val_loss"], label="val")
    ax.set_xlabel("epoch")
    ax.set_ylabel("loss")
    ax.set_title("Training / Validation loss")
    ax.legend()
    ax.grid(alpha=0.3)
    return fig


def _plot_confusion(num_classes: int, rng: np.random.Generator) -> plt.Figure:
    """Mock confusion matrix with strong diagonal."""
    cm = rng.integers(0, 8, size=(num_classes, num_classes))
    cm = cm + np.diag(rng.integers(60, 100, size=num_classes))
    fig, ax = plt.subplots(figsize=(6, 5))
    im = ax.imshow(cm, cmap="Blues")
    ax.set_title("Confusion matrix")
    ax.set_xlabel("predicted")
    ax.set_ylabel("true")
    fig.colorbar(im, ax=ax)
    return fig


def _make_sample_image(class_id: int, rng: np.random.Generator) -> bytes:
    """Mock failure image — a colored 32x32 block as a PNG byte string."""
    arr = rng.integers(0, 255, size=(32, 32, 3), dtype=np.uint8)
    arr[:, :, class_id % 3] = 200  # tint by class
    from PIL import Image  # required by numpy adapter under the hood

    img = Image.fromarray(arr, mode="RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def main() -> Path:
    rng = np.random.default_rng(seed=42)
    random.seed(42)

    out_dir = Path(__file__).parent / "out"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "ml_training_run.html"

    run_id = "20260505_train_42"
    epochs = 12
    num_classes = 5

    with Collector(out_path, title=f"Train run {run_id}") as report:
        report.add_kv(
            {
                "run_id": run_id,
                "model": "resnet50",
                "lr": 3e-4,
                "batch_size": 64,
                "seed": 42,
                "epochs": epochs,
            },
            title="Run config",
        )

        history = {"train_loss": [], "val_loss": [], "val_acc": []}

        with report.section("Training"):
            for epoch in range(epochs):
                train_loss, val_loss, val_acc = _train_one_epoch(epoch, history)
                report.add_text(
                    f"epoch={epoch:02d}  train={train_loss:.4f}  "
                    f"val={val_loss:.4f}  acc={val_acc:.3f}"
                )
            report.add_figure(
                _plot_loss_curves(history),
                title="Loss curves",
                description="train/val loss over epochs",
            )

        with report.section("Holdout evaluation"):
            report.add_figure(
                _plot_confusion(num_classes, rng),
                title="Confusion matrix",
            )
            per_class = [
                {
                    "class": f"c{i}",
                    "precision": round(0.8 + rng.random() * 0.15, 3),
                    "recall": round(0.78 + rng.random() * 0.18, 3),
                    "support": int(rng.integers(80, 200)),
                }
                for i in range(num_classes)
            ]
            report.add_table(per_class, title="Per-class metrics")

            with report.section("Top worst predictions"):
                report.add_text(
                    f"sampling {min(6, num_classes * 2)} worst (mocked)",
                    level="debug",
                )
                for k in range(6):
                    img_bytes = _make_sample_image(k, rng)
                    report.add_image(
                        img_bytes,
                        caption=(
                            f"true=c{k % num_classes}  "
                            f"pred=c{(k + 1) % num_classes}  "
                            f"prob={rng.random():.2f}"
                        ),
                    )

        report.add_text("training complete", level="success")

    return out_path


if __name__ == "__main__":
    out = main()
    size_mb = out.stat().st_size / 1024 / 1024
    print(f"wrote {out} ({size_mb:.2f} MiB)")
