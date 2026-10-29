"""Mock Gemini HTTP transport: exercises the REAL extractor/prompt/schema/grounding code without network."""
import json
import httpx

REQUIRED_LINES = [
    ("Python", "COD", "Strong proficiency in Python for backend services"),
    ("SQL", "SQL", "SQL and relational database design"),
    ("REST API design", "SWE", "REST API design and implementation"),
    ("Git", "SWE", "Git version control and code review"),
    ("Data Structures and Algorithms", "DSA", "Solid knowledge of data structures and algorithms"),
]
PREFERRED_LINES = [
    ("Docker", "CLOUD", "Hands-on experience with Docker containers"),
    ("Kubernetes", "CLOUD", "Kubernetes orchestration experience"),
    ("AWS", "CLOUD", "AWS cloud services familiarity"),
    ("System Design", "SYSD", "Experience with system design for scale"),
    ("Machine Learning", "AI", "Exposure to machine learning pipelines"),
]


def skills_payload(mode="correct"):
    """mode: correct | all_required (reproduces the live bug) | omitted (no requirement_type at all)."""
    out = []
    for name, cat, ev in REQUIRED_LINES + PREFERRED_LINES:
        item = {"skill_name": name, "category_code": cat, "evidence": ev, "confidence": "high"}
        is_pref = (name, cat, ev) in PREFERRED_LINES
        if mode == "correct":
            item["requirement_type"] = "preferred" if is_pref else "required"
        elif mode == "all_required":
            item["requirement_type"] = "required"
        out.append(item)
    return {"company": "Acme Corp", "role": "Senior Backend Engineer", "skills": out}


class GeminiMock:
    def __init__(self, mode="correct", fail_models=(), status=None, raw_text=None):
        self.mode, self.fail_models, self.status, self.raw_text = mode, set(fail_models), status, raw_text
        self.requests = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        model = request.url.path.split("/models/")[1].split(":")[0]
        self.requests.append({"model": model, "body": body, "params": dict(request.url.params)})
        if self.status:
            return httpx.Response(self.status, text="rate limited")
        if model in self.fail_models:
            return httpx.Response(404, text="model not found")
        text = self.raw_text if self.raw_text is not None else json.dumps(skills_payload(self.mode))
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": text}]}}]})

    def install(self, monkeypatch, models="gemini-test-1"):
        from radix_jd import extractor
        orig = httpx.AsyncClient
        monkeypatch.setattr(extractor.httpx, "AsyncClient", lambda **kw: orig(transport=httpx.MockTransport(self.handler), **kw))

        async def nosleep(*a, **k):
            return None
        monkeypatch.setattr(extractor.asyncio, "sleep", nosleep)
        monkeypatch.setenv("GEMINI_API_KEY", "fake-test-key")
        monkeypatch.setenv("GEMINI_MODELS", models)
        for k in ("GROQ_API_KEY", "OPENROUTER_API_KEY", "GOOGLE_API_KEY"):
            monkeypatch.delenv(k, raising=False)
        return self
