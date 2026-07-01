# Learnings

## Verify existing branch state before implementing a "continue" story
**Date**: 2026-06-20
**Area**: workflow
**What happened**: When asked to continue story 001, the branch already contained a complete implementation and tests from a prior commit. Reading the files first avoided redundant work and revealed that the remaining task was verification and review-fixes rather than fresh implementation.
**Takeaway**: On a "continue <story>" request, start with `git log --oneline -5`, `git status`, and a quick read of the story files before writing new code. The prior work may already be committed and only need validation or reviewer feedback fixes.

## Structurally identical tests must be parametrized
**Date**: 2026-06-20
**Area**: testing
**What happened**: The code reviewer failed the first pass because four invalid-timezone tests had identical body structure and differed only in the input string. Collapsing them into one `@pytest.mark.parametrize` test was the required fix to pass review.
**Takeaway**: In this repo, 3+ tests that share the same setup/assertions and vary only in inputs should be written as a single parametrized test. The code reviewer treats this as a blocking simplicity issue.

## Mock Spot-Hinta API calls at the urllib layer for real-stack integration tests
**Date**: 2026-06-20
**Area**: testing
**What happened**: The timezone tests used `monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)` to return Spot-Hinta-shaped JSON, which exercises the real `CachedPriceProvider` → `SpotHintaPriceProvider` → `to_utc_if_naive` path rather than mocking the provider itself.
**Takeaway**: For price-provider behavior tests, patch `urllib.request.urlopen` with a minimal `MockResponse` returning the expected Spot-Hinta JSON. This validates the full provider stack and matches the existing regression-test pattern.

## Construct the next calendar midnight explicitly for timezone-aware day buckets
**Date**: 2026-07-01
**Area**: architecture
**What happened**: `CachedPriceProvider` originally computed the end of a Helsinki-day bucket with `start_local + timedelta(days=1)`. While this happened to produce the right wall-clock span on 2026 DST days, it relies on subtle `zoneinfo` + `timedelta` behavior and was flagged as fragile in code review.
**Takeaway**: When bucketing by a source-local calendar day, build the next local midnight with `datetime.combine(local_date + timedelta(days=1), datetime.min.time(), tzinfo=source_tz)` instead of adding a timedelta to an aware datetime. It is clearer and robust across DST transitions.
