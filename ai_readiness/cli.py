import argparse
import datetime
import json
import os
import sys

from . import config as config_module
from .checks import ALL_CHECKS, CHECKS_BY_DIMENSION
from .checks.base import Context, run_check
from .nerdgraph import make_live_client, make_mock_client
from .report import render_html, render_json, render_table
from .scoring import aggregate


def build_arg_parser():
    p = argparse.ArgumentParser(
        prog="ai-readiness",
        description="Score a New Relic account's AI readiness across 10 dimensions.",
        epilog="Run with --mock first if you don't have credentials handy yet.",
    )

    account = p.add_argument_group("account")
    account.add_argument("--account-id", type=int, default=None,
                          help="New Relic account to score (default: $NEW_RELIC_ACCOUNT_ID)")
    account.add_argument("--region", default=None, choices=["us", "eu"],
                          help="New Relic datacenter region (default: $NEW_RELIC_REGION or 'us')")
    account.add_argument("--api-key", default=None,
                          help="User API key, NRAK-... (default: $NEW_RELIC_USER_KEY)")
    account.add_argument("--lookback-days", type=int, default=None,
                          help="NRQL time window for all checks (default: 30)")

    scope = p.add_argument_group("scope")
    scope.add_argument("--only", default=None, metavar="DIM[,DIM...]",
                        help="run just these dimensions, e.g. workflow_automation,alerting_anomaly "
                             "(see --list-dimensions)")
    scope.add_argument("--list-dimensions", action="store_true",
                        help="print all dimensions with their confidence level and exit")
    scope.add_argument("--config", default=None, metavar="PATH",
                        help="JSON file of scoring-threshold overrides, deep-merged onto the defaults")

    mock = p.add_argument_group("mock mode (no credentials needed)")
    mock.add_argument("--mock", action="store_true",
                       help="use canned fixture data instead of a live account")
    mock.add_argument("--mock-scenario", choices=["none", "partial", "mature"], default="partial",
                       help="which canned scenario --mock uses")

    output = p.add_argument_group("output")
    output.add_argument("--output", choices=["table", "json", "both"], default="table",
                         help="how to print results to stdout")
    output.add_argument("--out-file", default=None, metavar="PATH",
                         help="also write the JSON output to this file")
    output.add_argument("--report", choices=["html", "none"], default="none",
                         help="generate a CIS-benchmark-style HTML leave-behind")
    output.add_argument("--report-file", default="ai_readiness_report.html", metavar="PATH",
                         help="where to write the HTML report")

    dashboard = p.add_argument_group("New Relic dashboard")
    dashboard.add_argument("--dashboard-dry-run", action="store_true",
                            help="print the dashboard payload; no network call, works with --mock")
    dashboard.add_argument("--deploy-dashboard", action="store_true",
                            help="deploy/upsert the live dashboard into the target account "
                                 "(requires a live account, not --mock)")
    dashboard.add_argument("--dashboard-name", default=None, metavar="NAME",
                            help="override the dashboard's name (default: includes the account id)")
    return p


def _int_keys_where_possible(value):
    """JSON object keys are always strings, but THRESHOLDS' tier dicts use
    int keys ({1: ..., 2: ..., 3: ...}) so tier_from_count's sorted(dict) work
    correctly. Recursively convert any digit-string key back to int after
    loading a --config overrides file, so overrides actually merge onto the
    right keys instead of sitting alongside them unused."""
    if not isinstance(value, dict):
        return value
    return {
        (int(k) if isinstance(k, str) and k.isdigit() else k): _int_keys_where_possible(v)
        for k, v in value.items()
    }


def load_config_overrides(path):
    if not path:
        return config_module.THRESHOLDS
    with open(path) as f:
        overrides = json.load(f)
    return config_module.deep_merge(config_module.THRESHOLDS, _int_keys_where_possible(overrides))


def select_checks(only):
    if not only:
        return ALL_CHECKS
    names = [n.strip() for n in only.split(",") if n.strip()]
    unknown = [n for n in names if n not in CHECKS_BY_DIMENSION]
    if unknown:
        sys.exit(f"Unknown dimension(s): {', '.join(unknown)} -- see --list-dimensions")
    return [CHECKS_BY_DIMENSION[n] for n in names]


def main(argv=None):
    args = build_arg_parser().parse_args(argv)

    if args.list_dimensions:
        for c in ALL_CHECKS:
            print(f"{c.DIMENSION:22s} [{c.CONFIDENCE:10s}] {c.LABEL}")
        return 0

    account_id = args.account_id or int(os.environ.get("NEW_RELIC_ACCOUNT_ID", "0") or 0)
    region = args.region or os.environ.get("NEW_RELIC_REGION", "us")
    lookback_days = args.lookback_days or int(
        os.environ.get("AI_READINESS_LOOKBACK_DAYS", config_module.LOOKBACK_DAYS_DEFAULT)
    )

    if args.mock:
        gql = make_mock_client(args.mock_scenario)
    else:
        api_key = args.api_key or os.environ.get("NEW_RELIC_USER_KEY")
        if not api_key:
            sys.exit("NEW_RELIC_USER_KEY not set (or pass --api-key). Use --mock to run without a live account.")
        if not account_id:
            sys.exit("NEW_RELIC_ACCOUNT_ID not set (or pass --account-id).")
        gql = make_live_client(api_key, region)

    thresholds = load_config_overrides(args.config)
    ctx = Context(gql=gql, account_id=account_id, lookback_days=lookback_days, config=thresholds)

    checks = select_checks(args.only)
    results = [run_check(c, ctx) for c in checks]
    agg = aggregate(results)
    meta = {
        "account_id": account_id,
        "region": region,
        "lookback_days": lookback_days,
        "mock": args.mock,
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
    }

    if args.output in ("table", "both"):
        print(render_table(results, agg, meta))
    if args.output in ("json", "both"):
        json_text = render_json(results, agg, meta)
        print(json_text)
        if args.out_file:
            with open(args.out_file, "w") as f:
                f.write(json_text)

    if args.report == "html":
        with open(args.report_file, "w") as f:
            f.write(render_html(results, agg, meta))
        print(f"HTML report written to {args.report_file}")

    if args.dashboard_dry_run:
        from .dashboard import build_dashboard_payload

        payload = build_dashboard_payload(results, agg, meta, name=args.dashboard_name)
        print(json.dumps(payload, indent=2))

    if args.deploy_dashboard:
        if args.mock:
            sys.exit(
                "--deploy-dashboard requires a live account (not --mock); "
                "use --dashboard-dry-run to preview the payload instead."
            )
        from .dashboard import deploy as deploy_dashboard

        entity = deploy_dashboard(gql, account_id, results, agg, meta, name=args.dashboard_name)
        print(f"Dashboard deployed: {entity['name']}")
        print(f"  GUID: {entity['guid']}")
        print(f"  Link: https://one.newrelic.com/redirect/entity/{entity['guid']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
