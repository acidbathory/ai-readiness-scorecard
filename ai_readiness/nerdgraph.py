"""NerdGraph client seam: live HTTP client, mock/fixture client, and
entitySearch pagination. Every check goes through the `gql` callable
returned by make_live_client()/make_mock_client() -- never urllib directly.
"""

import json
import time
import urllib.error
import urllib.request

# Ported verbatim from reference-repo-b/workflow-demo/nr/lib/nerdgraph.js:5-8 --
# the only precedent for US/EU region switching in either reference repo.
REGION_ENDPOINTS = {
    "us": "https://api.newrelic.com/graphql",
    "eu": "https://api.eu.newrelic.com/graphql",
}

# Eight check modules ran an NRQL query against a single account through the
# identical document -- worth being one shared constant rather than eight
# copies that would need to be kept in sync by hand as more dimensions land.
GENERIC_NRQL_QUERY = """
query($accountId: Int!, $nrql: Nrql!) {
  actor { account(id: $accountId) { nrql(query: $nrql) { results } } }
}
"""


class NerdGraphError(Exception):
    pass


def resolve_endpoint(region):
    endpoint = REGION_ENDPOINTS.get((region or "us").lower())
    if not endpoint:
        raise NerdGraphError(
            f"Unknown region {region!r}, expected one of {sorted(REGION_ENDPOINTS)}"
        )
    return endpoint


def make_live_client(
    api_key, region="us", timeout=30, max_attempts=3, retry_base_delay=1.0,
    _urlopen=urllib.request.urlopen, _sleep=time.sleep,
):
    """Adapted from reference-repo-a/scripts/bootstrap.py:76-94. Departure
    from that precedent: raises NerdGraphError instead of print-and-continue,
    so checks/base.py can catch failures generically per-check.

    Retries a transient HTTP 429/5xx with exponential backoff
    (retry_base_delay, then x2 each further attempt) before giving up. Some
    dimensions make 100+ sequential calls in a single run (one per Workflow
    Automation canvas on a workflow-heavy account, via fetch_workflow_yaml)
    -- without this, one rate-limit blip on call 80 of 100 would discard the
    whole dimension's result via checks/base.py's catch-all, not just retry
    the one call. `_urlopen`/`_sleep` are injectable seams for testing
    without real network calls or real delays.
    """
    endpoint = resolve_endpoint(region)
    headers = {"Content-Type": "application/json", "API-Key": api_key}

    def gql(query, variables=None, fixture_key=None):
        # fixture_key is accepted (and ignored) so check code doesn't need
        # to branch on live vs mock mode when calling gql().
        body = json.dumps({"query": query, "variables": variables or {}}).encode()

        for attempt in range(max_attempts):
            req = urllib.request.Request(endpoint, data=body, headers=headers, method="POST")
            try:
                with _urlopen(req, timeout=timeout) as resp:
                    out = json.loads(resp.read().decode())
                break
            except urllib.error.HTTPError as e:
                error_body = e.read().decode()[:300]
                retryable = e.code == 429 or e.code >= 500
                if retryable and attempt < max_attempts - 1:
                    _sleep(retry_base_delay * (2 ** attempt))
                    continue
                raise NerdGraphError(f"HTTP {e.code}: {error_body}")
            except urllib.error.URLError as e:
                raise NerdGraphError(str(e))
        if out.get("errors"):
            raise NerdGraphError(json.dumps(out["errors"]))
        return out.get("data") or {}

    return gql


def make_mock_client(scenario):
    from .fixtures.mock_responses import SCENARIOS

    if scenario not in SCENARIOS:
        raise NerdGraphError(
            f"Unknown mock scenario {scenario!r}, expected one of {sorted(SCENARIOS)}"
        )
    data = SCENARIOS[scenario]

    def gql(query, variables=None, fixture_key=None):
        if fixture_key is None:
            raise NerdGraphError(
                "mock client called without fixture_key -- the calling check "
                "forgot to pass one"
            )
        if fixture_key not in data:
            raise NerdGraphError(
                f"scenario {scenario!r} has no fixture for {fixture_key!r}"
            )
        return data[fixture_key]

    return gql


def paginated_entity_search(gql, query, variables=None, fixture_key=None, max_pages=10):
    """Follows entitySearch results.nextCursor across pages, returning the
    combined list of entities. New code with no precedent in either
    reference repo -- both only ever fetched a single page.

    `query` must be a GraphQL document accepting an optional $cursor
    variable (plus whatever else `variables` supplies -- e.g. a `$query`
    holding the account-scoped entitySearch filter string) and returning
    `actor.entitySearch.results { entities nextCursor }`. In mock mode,
    `fixture_key` should point at a *list* of page payloads (one per
    simulated page); each is returned in turn regardless of the cursor
    value.
    """
    entities = []
    cursor = None
    base_variables = variables or {}
    for page_num in range(max_pages):
        call_variables = {**base_variables, "cursor": cursor}
        if fixture_key is not None:
            pages = gql(query, call_variables, fixture_key=fixture_key)
            page = pages[page_num] if isinstance(pages, list) else pages
        else:
            page = gql(query, call_variables)
        results = page.get("actor", {}).get("entitySearch", {}).get("results", {})
        entities.extend(results.get("entities", []))
        cursor = results.get("nextCursor")
        if not cursor:
            break
    else:
        raise NerdGraphError(f"entitySearch pagination exceeded max_pages={max_pages}")
    return entities


def paginated_alert_conditions(gql, query, account_id, fixture_key=None, max_pages=10):
    """Follows alerts.nrqlConditionsSearch's nextCursor across pages,
    returning the combined list of conditions. Without this, an account with
    more conditions than fit in one page (alerting_anomaly/ai_cost_governance
    only ever requested page one) silently under-reports -- `totalCount`
    reflects every condition, but `nrqlConditions` only the first page.

    `query` must be a GraphQL document accepting $accountId and an optional
    $cursor, returning `actor.account.alerts.nrqlConditionsSearch { nextCursor
    nrqlConditions }`. In mock mode, `fixture_key` should point at a *list*
    of page payloads (one per simulated page) if pagination itself is under
    test; a single dict (the existing convention) is treated as one page.
    """
    conditions = []
    cursor = None
    for page_num in range(max_pages):
        variables = {"accountId": account_id, "cursor": cursor}
        if fixture_key is not None:
            pages = gql(query, variables, fixture_key=fixture_key)
            page = pages[page_num] if isinstance(pages, list) else pages
        else:
            page = gql(query, variables)
        search = page.get("actor", {}).get("account", {}).get("alerts", {}).get("nrqlConditionsSearch", {}) or {}
        conditions.extend(search.get("nrqlConditions", []) or [])
        cursor = search.get("nextCursor")
        if not cursor:
            break
    else:
        raise NerdGraphError(f"nrqlConditionsSearch pagination exceeded max_pages={max_pages}")
    return conditions
