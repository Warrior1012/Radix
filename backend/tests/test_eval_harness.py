from eval.run_eval import _metric


def test_precision_recall_metrics_use_unique_skill_sets_and_explicit_aliases():
    predicted = [
        {"skill_name": "PostgreSQL", "requirement_type": "required"},
        {"skill_name": "Python", "requirement_type": "preferred"},
        {"skill_name": "Made-up Skill", "requirement_type": "required"},
    ]
    gold = [
        {"skill_name": "Postgres", "requirement_type": "required"},
        {"skill_name": "Python", "requirement_type": "required"},
        {"skill_name": "Git", "requirement_type": "preferred"},
    ]
    result = _metric(predicted, gold)
    assert result["true_positive"] == 2
    assert result["false_positive"] == 1
    assert result["false_negative"] == 1
    assert result["precision"] == 0.6667
    assert result["recall"] == 0.6667
    assert result["f1"] == 0.6667
    assert result["requirement_type_accuracy"] == 0.5


def test_partial_dataset_can_never_be_marked_final():
    from eval.run_eval import _dataset_completeness
    manifest = {"documents": [{"document_id": "jd1"}, {"document_id": "resume1"}]}
    annotations = {
        "jd1": {"approved": True, "skills": [{"skill_name": "Python", "requirement_type": "required"}]},
        "resume1": {"approved": True, "skills": [{"skill_name": "Python"}]},
    }
    variants = [
        {"document_id": "jd1", "format": "pdf", "approved_ground_truth": True, "metrics": {"precision": 1.0}},
        {"document_id": "jd1", "format": "docx", "approved_ground_truth": True, "metrics": {"precision": 1.0}},
    ]
    complete, coverage = _dataset_completeness(manifest, annotations, variants)
    assert complete is False
    assert coverage["logical_documents_expected"] == 2
    assert coverage["document_variants_expected"] == 4
    assert coverage["document_variants_scored"] == 2
    assert coverage["missing_or_unapproved_variants"] == ["resume1:docx", "resume1:pdf"]


def test_unconfigured_official_manifest_reports_blocked_not_fake_zero_metrics(tmp_path, monkeypatch):
    import json
    from pathlib import Path
    from eval import run_eval

    manifest_path = tmp_path / "manifest.json"
    annotations_path = tmp_path / "annotations.json"
    report_path = tmp_path / "latest.json"
    manifest_path.write_text(json.dumps({"documents": [
        {"document_id": "official_jd", "kind": "jd", "pdf_path": "", "docx_path": ""},
        {"document_id": "official_resume", "kind": "resume", "pdf_path": "", "docx_path": ""},
    ]}), encoding="utf-8")
    annotations_path.write_text(json.dumps({"documents": []}), encoding="utf-8")
    monkeypatch.setattr(run_eval, "MANIFEST_PATH", manifest_path)
    monkeypatch.setattr(run_eval, "ANNOTATIONS_PATH", annotations_path)
    monkeypatch.setattr(run_eval, "REPORT_PATH", report_path)

    report = run_eval.run("http://127.0.0.1:8000")
    assert report["status"] == "blocked"
    assert report["metrics"] is None
    assert report["documents_scored"] == 0
    assert report["coverage"]["document_variants_scored"] == 0
    saved = json.loads(report_path.read_text(encoding="utf-8"))
    assert saved["status"] == "blocked"
    assert "not zero" in saved["reason"]
