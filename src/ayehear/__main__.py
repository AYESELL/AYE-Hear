from __future__ import annotations

import argparse
from pathlib import Path

from ayehear.app.main import main as app_main
from ayehear.services.protocol_replay import ProtocolReplayService
from ayehear.utils.config import load_runtime_config
from ayehear.utils.paths import exports_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aye-hear")
    subparsers = parser.add_subparsers(dest="command")

    replay_parser = subparsers.add_parser(
        "protocol-replay",
        help="Replay one persisted transcript baseline across Ollama models.",
    )
    replay_parser.add_argument("--baseline", required=True, help="Path to the persisted transcript baseline.")
    replay_parser.add_argument("--output-dir", help="Directory for replay artifacts.")
    replay_parser.add_argument("--title", default="Protocol Replay", help="Meeting title used in exports.")
    replay_parser.add_argument(
        "--language",
        default=None,
        help="Protocol language for all runs (default: value from config/default.yaml).",
    )
    replay_parser.add_argument(
        "--model",
        dest="models",
        action="append",
        default=None,
        help="Explicit model to replay. Repeat for multiple models.",
    )

    args = parser.parse_args(argv)
    if args.command != "protocol-replay":
        return app_main()

    config = load_runtime_config(Path("config/default.yaml"))
    configured_models = [config.models.ollama_model]
    # Prefer explicit --language flag; fall back to the value from runtime config
    # so that replay benchmarks use the same language as the running application.
    language = args.language or config.protocol.protocol_language
    output_dir = Path(args.output_dir) if args.output_dir else exports_dir() / "replays"
    service = ProtocolReplayService(language=language)
    results = service.replay_baseline(
        Path(args.baseline),
        output_dir,
        meeting_title=args.title,
        configured_models=configured_models,
        models=args.models,
    )
    for result in results:
        print(f"{result.model}: {result.status} ({result.duration_ms} ms) -> {result.output_path}")
    return 0 if all(result.status == "success" for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
