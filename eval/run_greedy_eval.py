import argparse
import json
import sys
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import mean, median
from typing import Any, Optional

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import create_app
from app.api import predict_judgement_with_api
from app.database import Case
from eval.run_prompt_eval import (
    char_f1,
    key_element_recall,
    format_score,
    length_score,
    overall_score,
)


def infer_case_type(case: Case) -> str:
    explicit = (case.sort or "").strip()
    if explicit and explicit != "其他":
        return explicit

    text = f"{case.name or ''}\n{case.content or ''}"
    if any(keyword in text for keyword in ["刑事", "被告人", "公诉机关", "故意伤害罪", "有期徒刑"]):
        return "刑事案件"
    if any(keyword in text for keyword in ["民事", "原告", "被告", "合同", "侵权", "赔偿"]):
        return "民事案件"
    if any(keyword in text for keyword in ["行政", "行政机关", "撤销行政行为", "行政处罚"]):
        return "行政案件"
    return "其他"


@dataclass
class OneCaseScore:
    case_id: int
    prompt_name: str
    prediction: str
    success: bool
    similarity: float
    key_recall: float
    fmt: float
    length: float
    overall: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="单案件贪心提示词评测")
    parser.add_argument("--case-id", type=int, required=True, help="用于贪心评测的案件ID")
    parser.add_argument("--baseline-prompt-file", type=str, default="", help="当前基线提示词文件，留空=系统默认")
    parser.add_argument("--candidate-prompt-file", type=str, required=True, help="候选提示词文件")
    parser.add_argument("--method", type=str, default="official_step", help="预测方法，默认official_step")
    parser.add_argument("--max-content-len", type=int, default=1200, help="文书裁剪长度，默认1200（省token）")
    parser.add_argument("--repeats", type=int, default=1, help="同一提示词重复评测次数，默认1")
    parser.add_argument("--aggregate", choices=["mean", "median"], default="mean", help="多次评测聚合方式，默认mean")
    parser.add_argument("--min-delta", type=float, default=0.01, help="最小提升阈值，默认0.01")
    parser.add_argument("--min-win-rate", type=float, default=0.0, help="候选逐次胜率下限(0~1)，默认0")
    parser.add_argument("--no-regress-format", action="store_true", help="不允许候选格式分下降")
    parser.add_argument("--no-regress-key", action="store_true", help="不允许候选关键词召回分下降")
    parser.add_argument("--auto-adopt", action="store_true", help="若评测通过，自动将候选提示词采纳为基线")
    parser.add_argument("--adopt-to", type=str, default="", help="自动采纳目标文件路径；留空时使用 --baseline-prompt-file")
    parser.add_argument("--dry-run", action="store_true", help="仅模拟判定与采纳，不写入任何文件")
    parser.add_argument("--run-review-agent", action="store_true", help="评测后调用评审智能体，输出提示词优化建议")
    parser.add_argument("--decision-mode", choices=["review", "score", "hybrid"], default="review", help="最终采纳决策模式：review(默认，仅看评审) / score(仅看分数) / hybrid(分数+评审)")
    parser.add_argument("--require-review-acceptable", action="store_true", help="启用评审门禁：要求评审智能体给出 acceptable=true")
    parser.add_argument("--review-min-score", type=int, default=0, help="启用评审门禁：要求评审分不低于该值（0~100，默认0=不启用）")
    parser.add_argument("--output-dir", type=str, default="eval/results/greedy", help="输出目录")
    return parser.parse_args()


def load_prompt(path_str: str) -> Optional[str]:
    if not path_str.strip():
        return None
    path = resolve_existing_path(path_str)
    if not path:
        raw_path = Path(path_str)
        candidates = []
        if raw_path.is_absolute():
            candidates.append(raw_path)
        else:
            candidates.append(ROOT_DIR / raw_path)
            candidates.append(ROOT_DIR / "eval" / "prompts" / raw_path.name)
        raise FileNotFoundError(
            "提示词文件不存在。已尝试路径: " + ", ".join(str(item) for item in candidates)
        )
    return path.read_text(encoding="utf-8")


def resolve_existing_path(path_str: str) -> Optional[Path]:
    raw_path = Path(path_str)
    candidates = []

    if raw_path.is_absolute():
        candidates.append(raw_path)
    else:
        candidates.append(ROOT_DIR / raw_path)
        candidates.append(ROOT_DIR / "eval" / "prompts" / raw_path.name)

    return next((item for item in candidates if item.exists()), None)


def resolve_path(path_str: str) -> Path:
    path = Path(path_str)
    if not path.is_absolute():
        path = ROOT_DIR / path
    return path


def score_one(case: Case, prompt_name: str, prompt_template: Optional[str], method: str, max_content_len: int) -> OneCaseScore:
    reference = case.get_actual_result() or ""
    content = (case.content or "")[:max_content_len]

    case_type = infer_case_type(case)

    payload = predict_judgement_with_api(
        content=content,
        case_type=case_type,
        prompt_template=prompt_template,
        method=method,
    )
    prediction = (payload.get("prediction") or "").strip()
    success = bool(payload.get("success", False))

    sim = char_f1(reference, prediction)
    key = key_element_recall(reference, prediction)
    fmt = format_score(prediction)
    length = length_score(reference, prediction)
    total = overall_score(sim, key, fmt, length)

    return OneCaseScore(
        case_id=case.id,
        prompt_name=prompt_name,
        prediction=prediction,
        success=success,
        similarity=round(sim, 4),
        key_recall=round(key, 4),
        fmt=round(fmt, 4),
        length=round(length, 4),
        overall=round(total, 4),
    )


def decide(
    baseline: OneCaseScore,
    candidate: OneCaseScore,
    min_delta: float,
    no_regress_format: bool,
    no_regress_key: bool,
    win_rate: float,
    min_win_rate: float,
) -> tuple[bool, str]:
    if min_win_rate < 0 or min_win_rate > 1:
        return False, f"min_win_rate 超出范围：{min_win_rate}"

    delta = round(candidate.overall - baseline.overall, 4)

    if delta < min_delta:
        return False, f"总分提升不足：delta={delta} < min_delta={min_delta}"

    if win_rate < min_win_rate:
        return False, f"逐次胜率不足：win_rate={round(win_rate,4)} < min_win_rate={min_win_rate}"

    if no_regress_format and candidate.fmt < baseline.fmt:
        return False, f"格式分退化：{candidate.fmt} < {baseline.fmt}"

    if no_regress_key and candidate.key_recall < baseline.key_recall:
        return False, f"关键要素召回退化：{candidate.key_recall} < {baseline.key_recall}"

    return True, f"通过：delta={delta}"


def _aggregate_value(values: list[float], mode: str) -> float:
    if mode == "median":
        return float(median(values))
    return float(mean(values))


def aggregate_scores(case_id: int, prompt_name: str, runs: list[OneCaseScore], mode: str) -> OneCaseScore:
    if not runs:
        raise RuntimeError("runs为空，无法聚合分数")

    best_run = max(runs, key=lambda item: item.overall)

    return OneCaseScore(
        case_id=case_id,
        prompt_name=prompt_name,
        prediction=best_run.prediction,
        success=any(item.success for item in runs),
        similarity=round(_aggregate_value([item.similarity for item in runs], mode), 4),
        key_recall=round(_aggregate_value([item.key_recall for item in runs], mode), 4),
        fmt=round(_aggregate_value([item.fmt for item in runs], mode), 4),
        length=round(_aggregate_value([item.length for item in runs], mode), 4),
        overall=round(_aggregate_value([item.overall for item in runs], mode), 4),
    )


def save_report(
    output_dir: Path,
    case: Case,
    baseline: OneCaseScore,
    candidate: OneCaseScore,
    accepted: bool,
    reason: str,
    args: argparse.Namespace,
    baseline_runs: list[OneCaseScore],
    candidate_runs: list[OneCaseScore],
    win_rate: float,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    run_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_name = f"greedy_case_{case.id}_{run_time}"
    report_path = output_dir / f"{run_name}.json"

    data = {
        "meta": {
            "run_name": run_name,
            "run_time": run_time,
            "case_id": case.id,
            "case_name": case.name,
            "case_sort": case.sort,
            "method": args.method,
            "repeats": args.repeats,
            "aggregate": args.aggregate,
            "min_delta": args.min_delta,
            "min_win_rate": args.min_win_rate,
            "no_regress_format": args.no_regress_format,
            "no_regress_key": args.no_regress_key,
            "max_content_len": args.max_content_len,
            "decision_mode": args.decision_mode,
            "baseline_prompt_file": args.baseline_prompt_file,
            "candidate_prompt_file": args.candidate_prompt_file,
        },
        "decision": {
            "accepted": accepted,
            "reason": reason,
            "delta_overall": round(candidate.overall - baseline.overall, 4),
            "win_rate": round(win_rate, 4),
        },
        "baseline": baseline.__dict__,
        "candidate": candidate.__dict__,
        "baseline_runs": [item.__dict__ for item in baseline_runs],
        "candidate_runs": [item.__dict__ for item in candidate_runs],
    }

    report_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return report_path


def _update_report_with_review_gate(
    report_path: Path,
    accepted: bool,
    reason: str,
    review_result: Optional[dict[str, Any]],
    review_report_path: Optional[Path],
) -> None:
    if not report_path.exists():
        return

    data = json.loads(report_path.read_text(encoding="utf-8"))
    decision = data.get("decision", {})
    decision["accepted"] = accepted
    decision["reason"] = reason
    if review_result is not None:
        issues = review_result.get("issues", []) or []
        suggestions = review_result.get("prompt_optimization_suggestions", []) or []
        top_issues: list[str] = []
        for item in issues[:3]:
            if isinstance(item, dict):
                issue_type = item.get("type", "未知类型")
                severity = item.get("severity", "unknown")
                detail = item.get("detail", "")
                top_issues.append(f"[{severity}] {issue_type}: {detail}")
            else:
                top_issues.append(str(item))

        decision["review_success"] = bool(review_result.get("success", False))
        decision["review_acceptable"] = bool(review_result.get("acceptable", False))
        decision["review_overall_score"] = int(review_result.get("overall_score", 0) or 0)
        decision["review_recommendation"] = "accept" if bool(review_result.get("acceptable", False)) else "reject"
        decision["review_issue_count"] = len(issues)
        decision["review_top_issues"] = top_issues
        decision["review_top_suggestions"] = [str(item) for item in suggestions[:3]]

    if review_report_path is not None and str(review_report_path) != "DRY_RUN":
        decision["review_report_file"] = str(review_report_path)
        decision["review_summary_file"] = str(review_report_path.with_suffix(".md"))

    data["decision"] = decision
    report_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def auto_adopt_if_needed(args: argparse.Namespace, accepted: bool, report_path: Path) -> Optional[Path]:
    if not args.auto_adopt or not accepted:
        return None

    if args.dry_run:
        return Path("DRY_RUN")

    source_path = resolve_existing_path(args.candidate_prompt_file)
    if not source_path:
        raise RuntimeError(f"候选提示词不存在，无法采纳: {args.candidate_prompt_file}")

    target_path_str = args.adopt_to.strip() if args.adopt_to.strip() else args.baseline_prompt_file.strip()
    if not target_path_str:
        raise RuntimeError("开启 --auto-adopt 时必须提供 --baseline-prompt-file 或 --adopt-to")

    target_path = resolve_path(target_path_str)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source_path, target_path)

    adopt_log_path = report_path.parent / "adoption_log.jsonl"
    log_item = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "report_file": str(report_path),
        "source_prompt": str(source_path),
        "adopted_to": str(target_path),
    }
    with adopt_log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(log_item, ensure_ascii=False) + "\n")

    return target_path


def run_reviewer_if_needed(
    args: argparse.Namespace,
    case: Case,
    candidate: OneCaseScore,
    candidate_prompt: Optional[str],
    report_path: Path,
) -> tuple[Optional[Path], Optional[dict[str, Any]]]:
    if not args.run_review_agent:
        return None, None

    if args.dry_run:
        return Path("DRY_RUN"), None

    from app.reviewer_agent import review_prediction_with_agent

    review_result: dict[str, Any] = review_prediction_with_agent(
        {
            "case_id": case.id,
            "case_type": infer_case_type(case),
            "full_case_content": case.content or "",
            "actual_result": case.get_actual_result() or "",
            "predicted_result": candidate.prediction or "",
            "predictor_prompt_template": candidate_prompt or "",
            "predictor_method": args.method,
        }
    )

    review_path = report_path.with_name(f"{report_path.stem}_review.json")
    review_path.write_text(json.dumps(review_result, ensure_ascii=False, indent=2), encoding="utf-8")

    summary_lines = [
        "# 评审智能体摘要",
        "",
        f"- 评审执行成功: {'是' if bool(review_result.get('success', False)) else '否'}",
        f"- 是否可采纳: {'是' if bool(review_result.get('acceptable', False)) else '否'}",
        f"- 评审总分: {int(review_result.get('overall_score', 0) or 0)}",
        "",
        "## 主要问题",
    ]

    issues = review_result.get("issues", []) or []
    if issues:
        for item in issues:
            if isinstance(item, dict):
                issue_type = item.get("type", "未知类型")
                severity = item.get("severity", "unknown")
                detail = item.get("detail", "")
                summary_lines.append(f"- [{severity}] {issue_type}: {detail}")
            else:
                summary_lines.append(f"- {item}")
    else:
        summary_lines.append("- 无")

    suggestions = review_result.get("prompt_optimization_suggestions", []) or []
    summary_lines.extend(["", "## 提示词优化建议"])
    if suggestions:
        for suggestion in suggestions:
            summary_lines.append(f"- {suggestion}")
    else:
        summary_lines.append("- 无")

    revised_prompt = (review_result.get("revised_prompt_template") or "").strip()
    summary_lines.extend(["", "## 建议替换提示词（如有）"])
    if revised_prompt:
        summary_lines.extend(["", "```text", revised_prompt, "```"])
    else:
        summary_lines.append("- 无")

    review_md_path = report_path.with_name(f"{report_path.stem}_review.md")
    review_md_path.write_text("\n".join(summary_lines), encoding="utf-8")

    return review_path, review_result


def evaluate_review_gate(
    review_result: Optional[dict[str, Any]],
    args: argparse.Namespace,
    default_require_acceptable: bool,
) -> tuple[bool, str]:
    if review_result is None:
        return False, "评审门禁未通过：未执行评审智能体"

    if not bool(review_result.get("success", False)):
        return False, f"评审门禁未通过：{review_result.get('message', '评审执行失败')}"

    require_acceptable = args.require_review_acceptable or default_require_acceptable
    if require_acceptable and not bool(review_result.get("acceptable", False)):
        return False, "评审门禁未通过：acceptable=false"

    if args.review_min_score > 0:
        review_score = int(review_result.get("overall_score", 0) or 0)
        if review_score < args.review_min_score:
            return False, f"评审门禁未通过：overall_score={review_score} < review_min_score={args.review_min_score}"

    return True, "评审门禁通过"


def finalize_decision(
    args: argparse.Namespace,
    score_accepted: bool,
    score_reason: str,
    review_result: Optional[dict[str, Any]],
) -> tuple[bool, str]:
    mode = args.decision_mode

    if mode == "score":
        if args.run_review_agent and (args.require_review_acceptable or args.review_min_score > 0):
            review_ok, review_reason = evaluate_review_gate(
                review_result=review_result,
                args=args,
                default_require_acceptable=False,
            )
            if not review_ok:
                return False, f"{score_reason}; {review_reason}"
        return score_accepted, score_reason

    if mode == "review":
        review_ok, review_reason = evaluate_review_gate(
            review_result=review_result,
            args=args,
            default_require_acceptable=True,
        )
        if not review_ok:
            return False, review_reason
        return True, "通过：评审门禁通过"

    if not score_accepted:
        return False, score_reason

    review_ok, review_reason = evaluate_review_gate(
        review_result=review_result,
        args=args,
        default_require_acceptable=True,
    )
    if not review_ok:
        return False, f"分数通过但{review_reason}"
    return True, f"{score_reason}; 评审门禁通过"


def main() -> None:
    args = parse_args()

    if args.repeats < 1:
        raise RuntimeError("--repeats 必须 >= 1")

    if args.decision_mode in {"review", "hybrid"} and not args.run_review_agent:
        raise RuntimeError(f"decision_mode={args.decision_mode} 需要同时开启 --run-review-agent")

    baseline_prompt = load_prompt(args.baseline_prompt_file)
    candidate_prompt = load_prompt(args.candidate_prompt_file)

    app = create_app()
    with app.app_context():
        case = Case.query.get(args.case_id)
        if not case:
            raise RuntimeError(f"案件不存在: case_id={args.case_id}")

        if not (case.content or "").strip():
            raise RuntimeError("该案件content为空，无法评测")

        if not (case.get_actual_result() or "").strip():
            raise RuntimeError("该案件actual_result为空，无法评测")

        baseline_name = Path(args.baseline_prompt_file).stem if args.baseline_prompt_file else "system_default"
        candidate_name = Path(args.candidate_prompt_file).stem

        baseline_runs: list[OneCaseScore] = []
        candidate_runs: list[OneCaseScore] = []

        for run_index in range(1, args.repeats + 1):
            print(f"[baseline {run_index}/{args.repeats}] evaluating...")
            baseline_runs.append(
                score_one(
                    case=case,
                    prompt_name=baseline_name,
                    prompt_template=baseline_prompt,
                    method=args.method,
                    max_content_len=args.max_content_len,
                )
            )

            print(f"[candidate {run_index}/{args.repeats}] evaluating...")
            candidate_runs.append(
                score_one(
                    case=case,
                    prompt_name=candidate_name,
                    prompt_template=candidate_prompt,
                    method=args.method,
                    max_content_len=args.max_content_len,
                )
            )

        baseline_score = aggregate_scores(case_id=case.id, prompt_name=baseline_name, runs=baseline_runs, mode=args.aggregate)
        candidate_score = aggregate_scores(case_id=case.id, prompt_name=candidate_name, runs=candidate_runs, mode=args.aggregate)

    wins = sum(1 for idx in range(len(baseline_runs)) if candidate_runs[idx].overall > baseline_runs[idx].overall)
    win_rate = wins / len(baseline_runs)

    score_accepted, score_reason = decide(
        baseline=baseline_score,
        candidate=candidate_score,
        min_delta=args.min_delta,
        no_regress_format=args.no_regress_format,
        no_regress_key=args.no_regress_key,
        win_rate=win_rate,
        min_win_rate=args.min_win_rate,
    )

    report_path = save_report(
        output_dir=ROOT_DIR / args.output_dir,
        case=case,
        baseline=baseline_score,
        candidate=candidate_score,
        accepted=score_accepted,
        reason=score_reason,
        args=args,
        baseline_runs=baseline_runs,
        candidate_runs=candidate_runs,
        win_rate=win_rate,
    )

    review_report, review_result = run_reviewer_if_needed(
        args=args,
        case=case,
        candidate=candidate_score,
        candidate_prompt=candidate_prompt,
        report_path=report_path,
    )
    accepted, reason = finalize_decision(
        args=args,
        score_accepted=score_accepted,
        score_reason=score_reason,
        review_result=review_result,
    )
    _update_report_with_review_gate(
        report_path=report_path,
        accepted=accepted,
        reason=reason,
        review_result=review_result,
        review_report_path=review_report,
    )

    adopted_target = auto_adopt_if_needed(args=args, accepted=accepted, report_path=report_path)

    print("单案件贪心评测完成")
    print(f"case_id={case.id}, case_name={case.name}")
    print(f"repeats={args.repeats}")
    print(f"aggregate={args.aggregate}, win_rate={round(win_rate,4)}")
    print(f"decision_mode={args.decision_mode}")
    print(f"baseline overall={baseline_score.overall}, candidate overall={candidate_score.overall}")
    print(f"decision: {'ACCEPT' if accepted else 'REJECT'} ({reason})")
    print(f"report: {report_path}")
    if args.dry_run:
        print("dry-run: 本次未执行任何覆盖写入")
    if adopted_target:
        if str(adopted_target) == "DRY_RUN":
            print("auto-adopt: [dry-run] 已命中采纳条件，但未执行文件覆盖")
        else:
            print(f"auto-adopt: 已采纳到 {adopted_target}")
    if review_report:
        if str(review_report) == "DRY_RUN":
            print("review-agent: [dry-run] 已跳过评审结果写入")
        else:
            print(f"review-agent: 评审结果已输出到 {review_report}")
            review_md = review_report.with_suffix(".md")
            if review_md.exists():
                print(f"review-agent: 可读摘要已输出到 {review_md}")


if __name__ == "__main__":
    main()
