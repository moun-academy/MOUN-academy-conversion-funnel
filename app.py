"""Command-line tool to track speaker gym funnel contacts.

The app persists data in ``data/funnel.json`` (created automatically) and
provides subcommands to add contacts, update their progress, list entries,
and show summary counts for each funnel stage.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


DATA_DIR = Path("data")
DATA_FILE = DATA_DIR / "funnel.json"


def _ensure_store() -> None:
    """Create the data directory and file if they do not exist."""

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not DATA_FILE.exists():
        DATA_FILE.write_text(json.dumps({"contacts": []}, indent=2))


def _load_data() -> Dict[str, Any]:
    _ensure_store()
    with DATA_FILE.open() as f:
        return json.load(f)


def _save_data(data: Dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with DATA_FILE.open("w") as f:
        json.dump(data, f, indent=2)


def _find_contact(data: Dict[str, Any], name: str) -> Optional[Dict[str, Any]]:
    name_lower = name.strip().lower()
    for contact in data.get("contacts", []):
        if contact["name"].strip().lower() == name_lower:
            return contact
    return None


def add_contact(args: argparse.Namespace) -> None:
    data = _load_data()
    existing = _find_contact(data, args.name)
    if existing:
        print(f"Contact '{args.name}' already exists. Use the update command instead.")
        return

    record = {
        "name": args.name.strip(),
        "contacted_at": datetime.utcnow().isoformat() + "Z",
        "joined": False,
        "challenge": False,
        "contact_submitted": False,
        "notes": args.notes or "",
    }
    data.setdefault("contacts", []).append(record)
    _save_data(data)
    print(f"Added contact: {record['name']}")


def update_contact(args: argparse.Namespace) -> None:
    data = _load_data()
    contact = _find_contact(data, args.name)
    if not contact:
        print(f"Contact '{args.name}' not found. Add them first.")
        return

    changed = False
    for field in ["joined", "challenge", "contact_submitted"]:
        value = getattr(args, field)
        if value is not None and contact[field] != value:
            contact[field] = value
            changed = True

    if args.notes is not None:
        contact["notes"] = args.notes
        changed = True

    if changed:
        _save_data(data)
        print(f"Updated contact: {contact['name']}")
    else:
        print("No updates were applied.")


def list_contacts(args: argparse.Namespace) -> None:
    data = _load_data()
    contacts: List[Dict[str, Any]] = data.get("contacts", [])

    if args.filter == "joined":
        contacts = [c for c in contacts if c["joined"]]
    elif args.filter == "challenge":
        contacts = [c for c in contacts if c["challenge"]]
    elif args.filter == "contact_submitted":
        contacts = [c for c in contacts if c["contact_submitted"]]

    if not contacts:
        print("No contacts found.")
        return

    for contact in contacts:
        markers = [
            "✔ joined" if contact["joined"] else "✖ joined",
            "✔ challenge" if contact["challenge"] else "✖ challenge",
            "✔ 90-day contact" if contact["contact_submitted"] else "✖ 90-day contact",
        ]
        marker_str = ", ".join(markers)
        notes_str = f" | notes: {contact['notes']}" if contact.get("notes") else ""
        print(f"- {contact['name']} ({marker_str}){notes_str}")


def summary_contacts(_: argparse.Namespace) -> None:
    data = _load_data()
    contacts = data.get("contacts", [])
    total = len(contacts)
    joined = sum(1 for c in contacts if c["joined"])
    challenge = sum(1 for c in contacts if c["challenge"])
    contact_submitted = sum(1 for c in contacts if c["contact_submitted"])

    print("Funnel summary:")
    print(f"- Total contacted: {total}")
    print(f"- Joined community: {joined}")
    print(f"- Took 7-day challenge: {challenge}")
    print(f"- Submitted contact for 90-day program: {contact_submitted}")


def reset_store(_: argparse.Namespace) -> None:
    _save_data({"contacts": []})
    print("Data store reset. All contacts removed.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Track your speaker gym funnel")
    subparsers = parser.add_subparsers(dest="command")

    add_parser = subparsers.add_parser("add", help="Add a new contact")
    add_parser.add_argument("name", help="Name of the person you contacted")
    add_parser.add_argument("--notes", help="Optional notes about the contact")
    add_parser.set_defaults(func=add_contact)

    update_parser = subparsers.add_parser("update", help="Update an existing contact")
    update_parser.add_argument("name", help="Name of the person to update")
    update_parser.add_argument("--joined", dest="joined", action="store_true", help="Mark as joined the community")
    update_parser.add_argument(
        "--no-joined", dest="joined", action="store_false", help="Mark as not joined"
    )
    update_parser.add_argument(
        "--challenge",
        dest="challenge",
        action="store_true",
        help="Mark as took the 7-day challenge",
    )
    update_parser.add_argument(
        "--no-challenge",
        dest="challenge",
        action="store_false",
        help="Mark as not taking the 7-day challenge",
    )
    update_parser.add_argument(
        "--contact-submitted",
        dest="contact_submitted",
        action="store_true",
        help="Mark as submitted contact for the 90-day program",
    )
    update_parser.add_argument(
        "--no-contact-submitted",
        dest="contact_submitted",
        action="store_false",
        help="Mark as not submitted contact",
    )
    update_parser.add_argument("--notes", help="Replace notes for the contact")
    update_parser.set_defaults(func=update_contact)

    list_parser = subparsers.add_parser("list", help="List contacts")
    list_parser.add_argument(
        "--filter",
        choices=["joined", "challenge", "contact_submitted"],
        help="Only show contacts at a specific stage",
    )
    list_parser.set_defaults(func=list_contacts)

    summary_parser = subparsers.add_parser("summary", help="Show counts for each stage")
    summary_parser.set_defaults(func=summary_contacts)

    reset_parser = subparsers.add_parser("reset", help="Remove all contacts")
    reset_parser.set_defaults(func=reset_store)

    return parser


def main(argv: Optional[List[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
