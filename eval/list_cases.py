import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import create_app
from app.database import Case


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="列出数据库案件，便于选择评测 case_id")
    parser.add_argument("--limit", type=int, default=20, help="最多显示条数，默认20")
    parser.add_argument("--only-with-actual", action="store_true", help="仅显示有真实判决结果的案件")
    parser.add_argument("--keyword", type=str, default="", help="按案件名称关键词过滤")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    app = create_app()
    with app.app_context():
        query = Case.query.order_by(Case.id.desc())

        if args.keyword.strip():
            query = query.filter(Case.name.like(f"%{args.keyword.strip()}%"))

        cases = query.limit(max(args.limit, 1) * 4).all()

        if args.only_with_actual:
            cases = [c for c in cases if (c.get_actual_result() or "").strip()]

        cases = cases[: max(args.limit, 1)]

    if not cases:
        print("未找到符合条件的案件。")
        return

    print("case_id | sort | has_actual | name")
    print("-" * 100)
    for case in cases:
        has_actual = bool((case.get_actual_result() or "").strip())
        sort = (case.sort or "其他")[:8]
        name = (case.name or "")
        print(f"{case.id:<7} | {sort:<8} | {str(has_actual):<10} | {name}")


if __name__ == "__main__":
    main()
