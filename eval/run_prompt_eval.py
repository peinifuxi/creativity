import argparse
import csv
import json
import random
import re
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Dict, List, Optional, Sequence, Tuple

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import create_app
from app.api import predict_judgement_with_api
from app.database import Case


@dataclass
class CaseEvalResult:
    case_id: int
    case_name: str
    case_sort: str
    success: bool
    prediction: str
    reference: str
    score_overall: float
    score_similarity: float
    score_key_recall: float
    score_format: float
    score_length: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="离线提示词评测（基于真实裁判文书）")
    parser.add_argument("--limit", type=int, default=20, help="评测样本数量，默认20")
    parser.add_argument("--seed", type=int, default=42, help="抽样随机种子")
    parser.add_argument("--method", type=str, default="official_step", help="预测方法，默认official_step")
    parser.add_argument("--prompt-file", type=str, default="", help="提示词模板文件路径，留空则用系统默认模板")
    parser.add_argument("--prompt-version", type=str, default="", help="提示词版本名，例如v1/v2")
    parser.add_argument("--case-ids", type=str, default="", help="指定案件ID列表，如 12,19,25")
    parser.add_argument("--min-content-len", type=int, default=80, help="最小文书长度过滤")
    parser.add_argument("--max-content-len", type=int, default=1800, help="评测时裁剪文书长度，降低token消耗")
    parser.add_argument("--use-existing-prediction", action="store_true", help="使用库中已有predict_result，不调用模型")
    parser.add_argument("--stop-on-error", action="store_true", help="任一样本报错时立即停止")
    parser.add_argument("--output-dir", type=str, default="eval/results", help="输出目录")
    return parser.parse_args()


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def char_f1(reference: str, prediction: str) -> float:
    reference_norm = normalize_text(reference)
    prediction_norm = normalize_text(prediction)
    if not reference_norm and not prediction_norm:
        return 1.0
    if not reference_norm or not prediction_norm:
        return 0.0

    reference_counter = Counter(reference_norm)
    prediction_counter = Counter(prediction_norm)
    overlap = sum((reference_counter & prediction_counter).values())
    precision = overlap / len(prediction_norm) if prediction_norm else 0.0
    recall = overlap / len(reference_norm) if reference_norm else 0.0
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def extract_key_elements(text: str) -> Dict[str, set]:
    text = text or ""
    crime_names = set(re.findall(r"犯([^，。；；\n]{1,18}?罪)", text))
    prison_terms = set(re.findall(r"(有期徒刑[^，。；\n]{0,20}|拘役[^，。；\n]{0,20}|管制[^，。；\n]{0,20}|无期徒刑|死刑)", text))
    monetary = set(re.findall(r"\d+(?:\.\d+)?元", text))

    legal_actions = set()
    for keyword in ["驳回上诉", "维持原判", "撤销", "改判", "赔偿", "退赔", "没收", "罚金"]:
        if keyword in text:
            legal_actions.add(keyword)

    return {
        "crime": crime_names,
        "term": prison_terms,
        "money": monetary,
        "action": legal_actions,
    }


def key_element_recall(reference: str, prediction: str) -> float:
    ref = extract_key_elements(reference)
    pred = extract_key_elements(prediction)

    recalls: List[float] = []
    for key in ["crime", "term", "money", "action"]:
        ref_set = ref[key]
        pred_set = pred[key]
        if not ref_set:
            recalls.append(1.0)
        else:
            recalls.append(len(ref_set & pred_set) / len(ref_set))

    return mean(recalls) if recalls else 0.0


def format_score(prediction: str) -> float:
    prediction = prediction or ""
    if not prediction.strip():
        return 0.0

    score = 1.0
    if "判决如下" in prediction:
        score -= 0.3
    if "```" in prediction:
        score -= 0.3
    if re.search(r"^\s*[-*#]", prediction, re.MULTILINE):
        score -= 0.2
    if re.search(r"^\s*\d+[\.、]", prediction, re.MULTILINE):
        score -= 0.2
    if "作为AI" in prediction or "抱歉" in prediction:
        score -= 0.3

    return max(0.0, min(score, 1.0))


def length_score(reference: str, prediction: str) -> float:
    reference_len = len(normalize_text(reference))
    prediction_len = len(normalize_text(prediction))
    if reference_len == 0 and prediction_len == 0:
        return 1.0
    if reference_len == 0 or prediction_len == 0:
        return 0.0
    ratio_gap = abs(prediction_len - reference_len) / max(reference_len, 1)
    return max(0.0, 1.0 - ratio_gap)


def overall_score(similarity: float, key_recall: float, fmt: float, length: float) -> float:
    return 0.35 * similarity + 0.30 * key_recall + 0.20 * fmt + 0.15 * length


def load_prompt_template(prompt_file: str) -> Optional[str]:
    if not prompt_file:
        return None
    path = Path(prompt_file)
    if not path.is_absolute():
        path = ROOT_DIR / path
    if not path.exists():
        raise FileNotFoundError(f"提示词文件不存在: {path}")
    return path.read_text(encoding="utf-8")


def parse_case_ids(case_ids: str) -> List[int]:
    if not case_ids.strip():
        return []
    values = []
    for part in case_ids.split(","):
        part = part.strip()
        if not part:
            continue
        values.append(int(part))
    return values


def select_cases(limit: int, seed: int, case_ids: Sequence[int], min_content_len: int) -> List[Case]:
    if case_ids:
        cases = Case.query.filter(Case.id.in_(case_ids)).all()
    else:
        candidates = Case.query.order_by(Case.id.desc()).limit(max(limit * 8, 160)).all()
        candidates = [
            c for c in candidates
            if (c.content or "").strip()
            and len((c.content or "").strip()) >= min_content_len
            and (c.get_actual_result() or "").strip()
        ]
        random.seed(seed)
        random.shuffle(candidates)
        cases = candidates[:limit]

    valid_cases = [
        c for c in cases
        if (c.content or "").strip()
        and len((c.content or "").strip()) >= min_content_len
        and (c.get_actual_result() or "").strip()
    ]
    return valid_cases


def evaluate_one_case(
    case: Case,
    method: str,
    prompt_template: Optional[str],
    max_content_len: int,
    use_existing_prediction: bool,
) -> CaseEvalResult:
    content = (case.content or "")[:max_content_len]
    reference = case.get_actual_result() or ""

    if use_existing_prediction:
        prediction = (case.predict_result or "").strip()
        success = bool(prediction)
    else:
        prediction_payload = predict_judgement_with_api(
            content=content,
            case_type=case.sort or "其他",
            prompt_template=prompt_template,
            method=method,
        )
        prediction = (prediction_payload.get("prediction") or "").strip()
        success = bool(prediction_payload.get("success", False))

    sim = char_f1(reference, prediction)
    key_recall = key_element_recall(reference, prediction)
    fmt = format_score(prediction)
    length = length_score(reference, prediction)
    total = overall_score(sim, key_recall, fmt, length)

    return CaseEvalResult(
        case_id=case.id,
        case_name=case.name or f"case_{case.id}",
        case_sort=case.sort or "其他",
        success=success,
        prediction=prediction,
        reference=reference,
        score_overall=round(total, 4),
        score_similarity=round(sim, 4),
        score_key_recall=round(key_recall, 4),
        score_format=round(fmt, 4),
        score_length=round(length, 4),
    )


def aggregate(results: Sequence[CaseEvalResult]) -> Dict[str, float]:
    if not results:
        return {
            "avg_overall": 0.0,
            "avg_similarity": 0.0,
            "avg_key_recall": 0.0,
            "avg_format": 0.0,
            "avg_length": 0.0,
            "success_rate": 0.0,
        }

    return {
        "avg_overall": round(mean(r.score_overall for r in results), 4),
        "avg_similarity": round(mean(r.score_similarity for r in results), 4),
        "avg_key_recall": round(mean(r.score_key_recall for r in results), 4),
        "avg_format": round(mean(r.score_format for r in results), 4),
        "avg_length": round(mean(r.score_length for r in results), 4),
        "success_rate": round(sum(1 for r in results if r.success) / len(results), 4),
    }


def to_jsonable(result: CaseEvalResult) -> Dict[str, object]:
    return {
        "case_id": result.case_id,
        "case_name": result.case_name,
        "case_sort": result.case_sort,
        "success": result.success,
        "scores": {
            "overall": result.score_overall,
            "similarity": result.score_similarity,
            "key_recall": result.score_key_recall,
            "format": result.score_format,
            "length": result.score_length,
        },
        "reference": result.reference,
        "prediction": result.prediction,
    }


def write_outputs(
    output_dir: Path,
    run_name: str,
    summary: Dict[str, float],
    results: Sequence[CaseEvalResult],
    meta: Dict[str, object],
) -> Tuple[Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / f"{run_name}.json"
    report_path = output_dir / f"{run_name}.md"
    leaderboard_path = output_dir / "leaderboard.csv"

    payload = {
        "meta": meta,
        "summary": summary,
        "cases": [to_jsonable(r) for r in results],
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"# Prompt Eval Report: {run_name}",
        "",
        f"- prompt_version: {meta['prompt_version']}",
        f"- method: {meta['method']}",
        f"- sample_count: {meta['sample_count']}",
        f"- use_existing_prediction: {meta['use_existing_prediction']}",
        "",
        "## Summary",
        "",
        f"- avg_overall: {summary['avg_overall']}",
        f"- avg_similarity: {summary['avg_similarity']}",
        f"- avg_key_recall: {summary['avg_key_recall']}",
        f"- avg_format: {summary['avg_format']}",
        f"- avg_length: {summary['avg_length']}",
        f"- success_rate: {summary['success_rate']}",
        "",
        "## Per Case",
        "",
        "| case_id | case_name | overall | sim | key | format | len | success |",
        "|---:|---|---:|---:|---:|---:|---:|---:|",
    ]

    for item in sorted(results, key=lambda r: r.score_overall, reverse=True):
        lines.append(
            f"| {item.case_id} | {item.case_name} | {item.score_overall} | {item.score_similarity} | {item.score_key_recall} | {item.score_format} | {item.score_length} | {int(item.success)} |"
        )

    report_path.write_text("\n".join(lines), encoding="utf-8")

    header = [
        "run_name",
        "run_time",
        "prompt_version",
        "method",
        "sample_count",
        "avg_overall",
        "avg_similarity",
        "avg_key_recall",
        "avg_format",
        "avg_length",
        "success_rate",
    ]
    row = [
        run_name,
        meta["run_time"],
        meta["prompt_version"],
        meta["method"],
        meta["sample_count"],
        summary["avg_overall"],
        summary["avg_similarity"],
        summary["avg_key_recall"],
        summary["avg_format"],
        summary["avg_length"],
        summary["success_rate"],
    ]

    if not leaderboard_path.exists():
        with leaderboard_path.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(header)
            writer.writerow(row)
    else:
        with leaderboard_path.open("a", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(row)

    return json_path, report_path, leaderboard_path


def main() -> None:
    args = parse_args()

    prompt_template = load_prompt_template(args.prompt_file)
    prompt_version = args.prompt_version.strip() if args.prompt_version.strip() else "default"
    if args.prompt_file:
        prompt_version = args.prompt_version.strip() if args.prompt_version.strip() else Path(args.prompt_file).stem

    app = create_app()

    with app.app_context():
        target_ids = parse_case_ids(args.case_ids)
        selected_cases = select_cases(
            limit=args.limit,
            seed=args.seed,
            case_ids=target_ids,
            min_content_len=args.min_content_len,
        )

        if not selected_cases:
            raise RuntimeError("未找到可评测案件。请确认cases表里有content与actual_result数据。")

        results: List[CaseEvalResult] = []
        interrupted = False

        for index, item in enumerate(selected_cases, start=1):
            print(f"[{index}/{len(selected_cases)}] evaluating case_id={item.id}")
            try:
                eval_result = evaluate_one_case(
                    case=item,
                    method=args.method,
                    prompt_template=prompt_template,
                    max_content_len=args.max_content_len,
                    use_existing_prediction=args.use_existing_prediction,
                )
                results.append(eval_result)
            except KeyboardInterrupt:
                interrupted = True
                print("检测到手动中断，正在保存已完成样本的部分评测结果...")
                break
            except Exception as error:
                print(f"case_id={item.id} 评测失败: {error}")
                if args.stop_on_error:
                    raise
                results.append(
                    CaseEvalResult(
                        case_id=item.id,
                        case_name=item.name or f"case_{item.id}",
                        case_sort=item.sort or "其他",
                        success=False,
                        prediction=f"[EVAL_ERROR] {error}",
                        reference=item.get_actual_result() or "",
                        score_overall=0.0,
                        score_similarity=0.0,
                        score_key_recall=0.0,
                        score_format=0.0,
                        score_length=0.0,
                    )
                )

    if not results:
        raise RuntimeError("评测未生成任何结果（可能被提前中断且未完成首条样本）。")

    summary = aggregate(results)
    run_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_suffix = "_partial" if 'interrupted' in locals() and interrupted else ""
    run_name = f"prompt_eval_{prompt_version}_{run_time}{run_suffix}"

    meta = {
        "run_time": run_time,
        "run_name": run_name,
        "prompt_version": prompt_version,
        "method": args.method,
        "sample_count": len(results),
        "target_sample_count": len(selected_cases),
        "use_existing_prediction": args.use_existing_prediction,
        "interrupted": bool('interrupted' in locals() and interrupted),
        "stop_on_error": args.stop_on_error,
        "seed": args.seed,
        "limit": args.limit,
        "min_content_len": args.min_content_len,
        "max_content_len": args.max_content_len,
        "case_ids": parse_case_ids(args.case_ids),
        "prompt_file": args.prompt_file,
    }

    output_dir = ROOT_DIR / args.output_dir
    json_path, report_path, leaderboard_path = write_outputs(
        output_dir=output_dir,
        run_name=run_name,
        summary=summary,
        results=results,
        meta=meta,
    )

    print("评测完成")
    print(f"样本数: {len(results)}")
    print(f"avg_overall: {summary['avg_overall']}")
    print(f"avg_similarity: {summary['avg_similarity']}")
    print(f"avg_key_recall: {summary['avg_key_recall']}")
    print(f"avg_format: {summary['avg_format']}")
    print(f"avg_length: {summary['avg_length']}")
    print(f"success_rate: {summary['success_rate']}")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")
    print(f"Leaderboard: {leaderboard_path}")


if __name__ == "__main__":
    main()
