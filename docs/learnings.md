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
