"""Command-line entry point: `regintel <command>`."""

from __future__ import annotations

import argparse
import dataclasses
import json
import logging
import sys
from collections.abc import Callable, Sequence

from regintel.collect.http import BlockedError, FetchFailed, FetchPolicy, PoliteClient
from regintel.collect.listing import ListingSchemaError
from regintel.config import Settings, load_dotenv
from regintel.store.base import ConcurrentWriteError, Store

log = logging.getLogger("regintel")

ROBOTS_CRAWL_DELAY_S = 30.0
EXIT_OK, EXIT_ERROR, EXIT_BLOCKED, EXIT_CONCURRENT = 0, 1, 2, 3


def _make_client(settings: Settings, min_interval_s: float) -> PoliteClient:
    return PoliteClient(FetchPolicy(min_interval_s=min_interval_s), settings.user_agent)


def _make_store(settings: Settings, *, push: bool) -> Store:
    if not push:
        from regintel.store.local import LocalStore

        return LocalStore(settings.cache_dir / "local-dataset")
    if not settings.hf_token:
        raise SystemExit("HF_TOKEN is not set; use --no-push for a local dry run")
    from regintel.store.hub import HubStore

    return HubStore(settings.dataset_repo, settings.hf_token)


def _int_at_least(minimum: int) -> Callable[[str], int]:
    def parse(text: str) -> int:
        value = int(text)
        if value < minimum:
            raise argparse.ArgumentTypeError(f"must be >= {minimum}")
        return value

    return parse


def _emit(payload: object) -> None:
    sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n")


def cmd_collect(args: argparse.Namespace) -> int:
    from regintel.collect.run import collect

    if args.min_interval < ROBOTS_CRAWL_DELAY_S:
        log.error(
            "--min-interval below %.0f s is refused (fda.gov robots.txt)", ROBOTS_CRAWL_DELAY_S
        )
        return EXIT_ERROR
    settings = Settings.from_env()
    store = _make_store(settings, push=not args.no_push)
    client = _make_client(settings, args.min_interval)
    try:
        summary = collect(
            settings, client, store, max_fetches=args.max_fetches, batch_size=args.batch_size
        )
    except BlockedError as exc:
        log.error("blocked before any letter was fetched: %s", exc)
        return EXIT_BLOCKED
    except ConcurrentWriteError as exc:
        log.error("%s", exc)
        return EXIT_CONCURRENT
    except (ListingSchemaError, FetchFailed) as exc:
        log.error("%s", exc)
        return EXIT_ERROR
    finally:
        client.close()
    _emit(dataclasses.asdict(summary))
    return EXIT_BLOCKED if summary.blocked else EXIT_OK


def cmd_store_init(args: argparse.Namespace) -> int:
    from huggingface_hub import HfApi

    from regintel.store.hub import init_dataset

    settings = Settings.from_env()
    if not settings.hf_token:
        log.error("HF_TOKEN is not set")
        return EXIT_ERROR
    created = init_dataset(HfApi(token=settings.hf_token), settings.dataset_repo)
    sys.stdout.write(("created" if created else "exists") + f" {settings.dataset_repo}\n")
    return EXIT_OK


def cmd_probe(args: argparse.Namespace) -> int:
    from regintel.probe import probe
    from regintel.store.base import guarded_commit

    settings = Settings.from_env()
    client = _make_client(settings, ROBOTS_CRAWL_DELAY_S)
    try:
        record = probe(client, args.url)
    finally:
        client.close()
    payload = record.model_dump_json(indent=2) + "\n"
    sys.stdout.write(payload)
    if args.push:
        store = _make_store(settings, push=True)
        try:
            head = store.head_revision()
            guarded_commit(
                store,
                {f"probe/{record.run_id}.json": payload.encode()},
                f"probe {record.run_id}",
                head,
            )
        except ConcurrentWriteError as exc:
            log.error("probe record not pushed: %s", exc)
            return EXIT_CONCURRENT
        except OSError as exc:  # includes Hub HTTP errors
            log.error("probe record not pushed: %s", exc)
            return EXIT_ERROR
    return EXIT_OK if record.ok else EXIT_BLOCKED


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="regintel")
    commands = parser.add_subparsers(dest="command", required=True)

    collect = commands.add_parser("collect", help="fetch new in-scope letters into raw/")
    collect.add_argument("--max-fetches", type=_int_at_least(0), default=None)
    collect.add_argument("--batch-size", type=_int_at_least(1), default=50)
    collect.add_argument("--min-interval", type=float, default=ROBOTS_CRAWL_DELAY_S)
    collect.add_argument("--no-push", action="store_true", help="write to a local store instead")
    collect.set_defaults(func=cmd_collect)

    store = commands.add_parser("store", help="dataset repo management")
    store_commands = store.add_subparsers(dest="store_command", required=True)
    init = store_commands.add_parser("init", help="create the public dataset if missing")
    init.set_defaults(func=cmd_store_init)
    from regintel.probe import DEFAULT_PROBE_URL

    probe = commands.add_parser("probe", help="check that fda.gov is reachable from here")
    probe.add_argument("--url", default=DEFAULT_PROBE_URL)
    probe.add_argument("--push", action="store_true", help="commit probe/<run_id>.json")
    probe.set_defaults(func=cmd_probe)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    loaded = load_dotenv()  # local convenience; exported variables (Action secrets) win
    if loaded:
        log.info("loaded %s from .env", ", ".join(sorted(loaded)))
    args = build_parser().parse_args(argv)
    code: int = args.func(args)
    return code
