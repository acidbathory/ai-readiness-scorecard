"""NerdGraph client seam: live HTTP client, mock/fixture client, and
entitySearch pagination. Every check goes through the `gql` callable
returned by make_live_client()/make_mock_client() -- never urllib directly.
"""

import json
import urllib.error
import urllib.request

# Ported verbatim from SAP-DEMO/workflow-demo/nr/lib/nerdgraph.js:5-8 --
# the only precedent for US/EU region switching in either reference repo.
REGION_ENDPOINTS = {
    "us": "https://api.newrelic.com/graphql",
    "eu": "https://api.eu.newrelic.com/graphql",
}


class NerdGraphError(Exception):
    pass


def resolve_endpoint(region):
    endpoint = REGION_ENDPOINTS.get((region or "us").lower())
    if not endpoint:
        raise NerdGraphError(
            f"Unknown region {region!r}, expected one of {sorted(REGION_ENDPOINTS)}"
        )
    return endpoint


def make_live_client(api_key, region="us", timeout=30):
    """Adapted from continental-demo/scripts/bootstrap.py:76-94. Departure
    from that precedent: raises NerdGraphError instead of print-and-continue,
    so checks/base.py can catch failures generically per-check.
    """
    endpoint = resolve_endpoint(region)

    def gql(query, variables=None, fixture_key=None):
        # fixture_key is accepted (and ignored) so check code doesn't need
        # to branch on live vs mock mode when calling gql().
        body = {"query": query, "variables": variables or {}}
        req = urllib.request.Request(
            endpoint,
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "API-Key": api_key},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                out = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            raise NerdGraphError(f"HTTP {e.code}: {e.read().decode()[:300]}")
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


def paginated_entity_search(gql, query, fixture_key=None, max_pages=10):
    """Follows entitySearch results.nextCursor across pages, returning the
    combined list of entities. New code with no precedent in either
    reference repo -- both only ever fetched a single page.

    `query` must be a GraphQL document accepting an optional $cursor
    variable and returning `actor.entitySearch.results { entities nextCursor }`.
    In mock mode, `fixture_key` should point at a *list* of page payloads
    (one per simulated page); each is returned in turn regardless of the
    cursor value.
    """
    entities = []
    cursor = None
    for page_num in range(max_pages):
        if fixture_key is not None:
            pages = gql(query, {"cursor": cursor}, fixture_key=fixture_key)
            page = pages[page_num] if isinstance(pages, list) else pages
        else:
            page = gql(query, {"cursor": cursor})
        results = page.get("actor", {}).get("entitySearch", {}).get("results", {})
        entities.extend(results.get("entities", []))
        cursor = results.get("nextCursor")
        if not cursor:
            break
    else:
        raise NerdGraphError(f"entitySearch pagination exceeded max_pages={max_pages}")
    return entities
