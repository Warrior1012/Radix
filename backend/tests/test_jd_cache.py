from radix_jd.jd_cache import JDExtractionCache, make_cache_key


def test_cache_key_normalizes_whitespace_and_tracks_model_config():
    targets = [{"provider": "gemini", "model": "test-model"}]
    assert make_cache_key("Python  SQL\nGit", targets) == make_cache_key("Python SQL Git", targets)
    assert make_cache_key("Python SQL Git", targets) != make_cache_key(
        "Python SQL Git", [{"provider": "gemini", "model": "other-model"}]
    )


def test_cache_roundtrip_and_demo_fallback_is_never_cached(tmp_path):
    cache = JDExtractionCache(tmp_path / "cache.json")
    key = make_cache_key("same JD", [{"provider": "groq", "model": "test"}])
    valid = {"extraction_method": "llm", "skills": [{"skill_name": "Python"}], "analysis_meta": {"models_invoked": ["groq:test"]}}
    cache.put(key, valid)
    assert cache.get(key) == valid

    fallback_key = make_cache_key("fallback JD", [{"provider": "groq", "model": "test"}])
    cache.put(fallback_key, {"extraction_method": "demo_keyword_fallback", "skills": [], "analysis_meta": {}})
    assert cache.get(fallback_key) is None
