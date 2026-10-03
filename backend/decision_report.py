"""Deterministic, downloadable evidence; no generated performance claims."""
import io
import json
import zipfile


def escaped(value):
    text = str(value).replace("\n", " ").replace("\r", " ")
    for token in ("\\", "`", "*", "_", "[", "]", "<", ">", "|", "#"):
        text = text.replace(token, "\\" + token)
    return text


def metric_table(metrics):
    rows = ["| Metric | Value |", "| --- | --- |"]
    rows.extend(f"| {escaped(key)} | {escaped(value)} |" for key, value in metrics.items() if isinstance(value, (int, float)))
    return "\n".join(rows)


def build_report(experiment, final=None):
    result = experiment["training_result"]
    config = result.get("training_config") or {}
    report = {"format_version": 1, "experiment_id": experiment["experiment_id"],
              "created_at": experiment["created_at"], "source_dataset_id": experiment["source_dataset_id"],
              "dataset_id": experiment["dataset_id"], "workflow_id": experiment["workflow_id"],
              "model_artifact": experiment.get("model_artifact"), "training": result,
              "pipeline": experiment.get("pipeline_context", {}), "final_evaluation": final,
              "assessment": "finalized" if final else "validation_only"}
    card = ["# DAISY model card", f"Experiment: {escaped(experiment['experiment_id'])}",
            f"Created: {escaped(experiment['created_at'])}",
            f"Target: {escaped(experiment['target_column'])}", f"Task: {escaped(result['problem_type'])}",
            f"Winner: {escaped(result['best_model'])}",
            f"Selection metric: {escaped(result['primary_metric'])} (validation only)",
            f"Split strategy: {escaped(result['split_strategy'])}",
            f"Rows: train {result['n_train']}, validation {result['n_validation']}, test {result['n_test']}",
            f"Seed: {result['random_state']}", f"Duplicate policy: {escaped(config.get('duplicate_policy', 'legacy drop'))}",
            "## Candidate validation results"]
    for candidate in result["results"]:
        card.extend([f"### {escaped(candidate['model'])}", f"Status: {escaped(candidate['status'])}",
                     metric_table(candidate.get("metrics", {})), f"Fit/evaluation seconds: {candidate['training_time_seconds']}"])
    card.append("## Final test")
    if final:
        card.extend([f"Finalized: {escaped(final['finalized_at'])}", metric_table(final["test_metrics"]),
                     "### Simple baseline on the same rows", metric_table(final["baseline_test_metrics"])])
        if final.get("gap_definition"):
            card.extend([f"Train/test gap metric: {escaped(final['primary_metric'])}",
                         f"Gap: {final['train_test_gap']} ({escaped(final['gap_definition'])}). Positive means worse test performance on this metric."])
    else:
        card.append("Not measured. Candidate scores are validation results. Finalize the saved winner to obtain a held-out test report.")
    card.extend(["## Reproducibility", f"Data fingerprint: {result['dataset_fingerprint']}",
                 f"Train fold hash: {result['train_index_hash']}", f"Validation fold hash: {result['validation_index_hash']}",
                 f"Test fold hash: {result['test_index_hash']}",
                 "The model ZIP contains the exact fitted winner, saved training-only preprocessing, dependency versions, parameters, schema and checksums.",
                 "report.json contains the recorded pipeline decisions and interpretation policy. Original CSV rows are not included.",
                 "## Limits and review requirements",
                 "This model card is assembled from measured records without an LLM. It is not a deployment certificate.",
                 "Validate the split against real deployment conditions. Grouped and temporal data require suitable splitting.",
                 "The holdout gate applies per source upload; re-uploading old data does not make it unseen.",
                 "Review target leakage, protected attributes, class imbalance, domain error costs, uncertainty, and future drift.",
                 "Unknown categories use the exported fallback; predictions may be unreliable for data outside the training distribution.",
                 "Generic good/moderate/poor labels do not establish domain-specific fitness."])
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("model_card.md", "\n\n".join(card) + "\n")
        archive.writestr("report.json", json.dumps(report, indent=2, allow_nan=False))
    return output.getvalue()
