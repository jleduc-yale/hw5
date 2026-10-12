"""Run the Campus Customs agent team.

    .venv/bin/python backend/cli.py                         # Boss works the whole open-ticket queue
    .venv/bin/python backend/cli.py --ticket 102            # Boss works one ticket
    .venv/bin/python backend/cli.py --approver "Your Name"  # allow payments, each confirmed at the terminal
    .venv/bin/python backend/cli.py --agent inventory --prompt "Which SKUs are out of stock?"

Every run appends to output/audit_trail.json.
"""

import argparse
import asyncio
import json
import sys

from shop_agents import build_team


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ticket", type=int, help="work only this ticket id")
    parser.add_argument("--agent", default="boss",
                        choices=["boss", "inventory", "accounting", "facilities", "customer_service"],
                        help="which agent receives the request (default: boss)")
    parser.add_argument("--prompt", help="custom request for the entry agent")
    parser.add_argument("--approver", help="name of the human approving payments; omit to block all payments")
    args = parser.parse_args()

    if args.prompt:
        prompt = args.prompt
    elif args.ticket:
        prompt = f"Work ticket {args.ticket} from start to finish following the shop rules."
    else:
        prompt = "Start the shift: work every open ticket in the queue following the shop rules."

    team = build_team()
    result = asyncio.run(team.run(
        prompt,
        entry_agent=args.agent,
        approver=args.approver,
        approval_mode="terminal" if args.approver and sys.stdin.isatty() else "queue",
    ))
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
