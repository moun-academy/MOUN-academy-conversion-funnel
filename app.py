"""Command-line tool to track speaker gym funnel contacts.

The app persists data in ``data/funnel.json`` (created automatically) and
provides subcommands to add contacts, update their progress, list entries,
and show summary counts for each funnel stage.
"""

from __future__ import annotations

import argparse
import http.server
import importlib
import json
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional

DATA_DIR = Path("data")
DATA_FILE = DATA_DIR / "funnel.json"
WEB_DATA_FILE = DATA_DIR / "web_contacts.json"


def _ensure_store() -> None:
    """Create the data directory and file if they do not exist."""

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not DATA_FILE.exists():
        DATA_FILE.write_text(json.dumps({"contacts": []}, indent=2))


def _ensure_web_store() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not WEB_DATA_FILE.exists():
        WEB_DATA_FILE.write_text(json.dumps({"contacts": []}, indent=2))


def _load_data() -> Dict[str, Any]:
    _ensure_store()
    with DATA_FILE.open() as f:
        return json.load(f)


def _save_data(data: Dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with DATA_FILE.open("w") as f:
        json.dump(data, f, indent=2)


def _load_web_data() -> Dict[str, Any]:
    _ensure_web_store()
    with WEB_DATA_FILE.open() as f:
        return json.load(f)


def _save_web_data(data: Dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with WEB_DATA_FILE.open("w") as f:
        json.dump(data, f, indent=2)


def _require_openpyxl():
    if importlib.util.find_spec("openpyxl") is None:
        raise RuntimeError(
            "The openpyxl package is required for Excel import/export. "
            "Install it with `pip install openpyxl`."
        )

    module = importlib.import_module("openpyxl")
    return module.Workbook, module.load_workbook


def _find_contact(data: Dict[str, Any], name: str) -> Optional[Dict[str, Any]]:
    name_lower = name.strip().lower()
    for contact in data.get("contacts", []):
        if contact["name"].strip().lower() == name_lower:
            return contact
    return None


class ContactsRequestHandler(http.server.BaseHTTPRequestHandler):
    """Minimal JSON API for persisting web UI contacts to disk."""

    server_version = "FunnelTracker/1.0"

    def _set_common_headers(self, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, format: str, *args: Any) -> None:  # pragma: no cover - keep server quiet
        return

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._set_common_headers()

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/api/contacts/export":
            self._handle_export_contacts()
            return
        if self.path.startswith("/api/contacts"):
            self._handle_get_contacts()
            return

        self._set_common_headers(404)
        self.wfile.write(json.dumps({"error": "Not found"}).encode())

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/api/contacts/import":
            self._handle_import_contacts()
            return
        if self.path == "/api/contacts":
            self._handle_create_contact()
            return

        self._set_common_headers(404)
        self.wfile.write(json.dumps({"error": "Not found"}).encode())

    def do_PUT(self) -> None:  # noqa: N802
        if self.path.startswith("/api/contacts/"):
            self._handle_update_contact()
            return

        self._set_common_headers(404)
        self.wfile.write(json.dumps({"error": "Not found"}).encode())

    def do_DELETE(self) -> None:  # noqa: N802
        if self.path.startswith("/api/contacts/"):
            self._handle_delete_contact()
            return

        self._set_common_headers(404)
        self.wfile.write(json.dumps({"error": "Not found"}).encode())

    def _read_json(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        raw_body = self.rfile.read(length)
        try:
            return json.loads(raw_body)
        except json.JSONDecodeError:
            return {}

    def _handle_get_contacts(self) -> None:
        data = _load_web_data()
        contacts = data.get("contacts", [])

        if self.path != "/api/contacts":
            contact_id = self.path.rsplit("/", 1)[-1]
            try:
                contact_id_int = int(contact_id)
            except ValueError:
                self._set_common_headers(400)
                self.wfile.write(json.dumps({"error": "Invalid contact id"}).encode())
                return

            match = next((c for c in contacts if c.get("id") == contact_id_int), None)
            if not match:
                self._set_common_headers(404)
                self.wfile.write(json.dumps({"error": "Contact not found"}).encode())
                return

            self._set_common_headers(200)
            self.wfile.write(json.dumps(match).encode())
            return

        self._set_common_headers(200)
        self.wfile.write(json.dumps(contacts).encode())

    def _handle_export_contacts(self) -> None:
        try:
            Workbook, _ = _require_openpyxl()
        except RuntimeError as exc:
            self._set_common_headers(500)
            self.wfile.write(json.dumps({"error": str(exc)}).encode())
            return

        data = _load_web_data()
        contacts = data.get("contacts", [])

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Contacts"
        sheet.append(
            [
                "id",
                "name",
                "notes",
                "joinedCommunity",
                "tookChallenge",
                "submittedPaid",
                "customer",
                "dateAdded",
            ]
        )

        for contact in contacts:
            sheet.append(
                [
                    contact.get("id"),
                    contact.get("name"),
                    contact.get("notes"),
                    bool(contact.get("joinedCommunity")),
                    bool(contact.get("tookChallenge")),
                    bool(contact.get("submittedPaid")),
                    bool(contact.get("customer")),
                    contact.get("dateAdded"),
                ]
            )

        output = BytesIO()
        workbook.save(output)
        binary = output.getvalue()

        self.send_response(200)
        self.send_header(
            "Content-Type",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.send_header("Content-Disposition", "attachment; filename=contacts.xlsx")
        self.send_header("Content-Length", str(len(binary)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(binary)

    def _handle_create_contact(self) -> None:
        payload = self._read_json()
        name = (payload.get("name") or "").strip()
        if not name:
            self._set_common_headers(400)
            self.wfile.write(json.dumps({"error": "Name is required"}).encode())
            return

        data = _load_web_data()
        contacts = data.setdefault("contacts", [])
        new_contact = {
            "id": int(datetime.utcnow().timestamp() * 1000),
            "name": name,
            "notes": payload.get("notes") or "",
            "joinedCommunity": bool(payload.get("joinedCommunity")),
            "tookChallenge": bool(payload.get("tookChallenge")),
            "submittedPaid": bool(payload.get("submittedPaid")),
            "customer": bool(payload.get("customer")),
            "dateAdded": datetime.utcnow().isoformat() + "Z",
        }

        contacts.append(new_contact)
        _save_web_data(data)

        self._set_common_headers(201)
        self.wfile.write(json.dumps(new_contact).encode())

    def _handle_import_contacts(self) -> None:
        try:
            _, load_workbook = _require_openpyxl()
        except RuntimeError as exc:
            self._set_common_headers(500)
            self.wfile.write(json.dumps({"error": str(exc)}).encode())
            return

        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            self._set_common_headers(400)
            self.wfile.write(json.dumps({"error": "Missing file content"}).encode())
            return

        raw_body = self.rfile.read(length)

        try:
            workbook = load_workbook(BytesIO(raw_body))
            sheet = workbook.active
        except Exception:
            self._set_common_headers(400)
            self.wfile.write(json.dumps({"error": "Invalid Excel file"}).encode())
            return

        headers = [cell.value for cell in next(sheet.iter_rows(min_row=1, max_row=1))]
        expected_headers = {
            "id",
            "name",
            "notes",
            "joinedCommunity",
            "tookChallenge",
            "submittedPaid",
            "customer",
            "dateAdded",
        }

        def _to_bool(value: Any) -> bool:
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.strip().lower() in {"true", "1", "yes", "y"}
            return bool(value)

        if not headers or set(headers) != expected_headers:
            self._set_common_headers(400)
            self.wfile.write(
                json.dumps({"error": "Excel sheet must contain the correct headers"}).encode()
            )
            return

        new_contacts = []
        for row in sheet.iter_rows(min_row=2, values_only=True):
            if not any(row):
                continue
            contact_map = dict(zip(headers, row))
            new_contacts.append(
                {
                    "id": int(contact_map.get("id") or int(datetime.utcnow().timestamp() * 1000)),
                    "name": str(contact_map.get("name") or "").strip(),
                    "notes": contact_map.get("notes") or "",
                    "joinedCommunity": _to_bool(contact_map.get("joinedCommunity")),
                    "tookChallenge": _to_bool(contact_map.get("tookChallenge")),
                    "submittedPaid": _to_bool(contact_map.get("submittedPaid")),
                    "customer": _to_bool(contact_map.get("customer")),
                    "dateAdded": contact_map.get("dateAdded") or datetime.utcnow().isoformat() + "Z",
                }
            )

        _save_web_data({"contacts": new_contacts})

        self._set_common_headers(200)
        self.wfile.write(json.dumps({"imported": len(new_contacts)}).encode())

    def _handle_update_contact(self) -> None:
        contact_id = self.path.rsplit("/", 1)[-1]
        try:
            contact_id_int = int(contact_id)
        except ValueError:
            self._set_common_headers(400)
            self.wfile.write(json.dumps({"error": "Invalid contact id"}).encode())
            return

        payload = self._read_json()
        data = _load_web_data()
        contacts = data.get("contacts", [])

        for contact in contacts:
            if contact.get("id") == contact_id_int:
                for key in ["name", "notes", "joinedCommunity", "tookChallenge", "submittedPaid", "customer"]:
                    if key in payload:
                        contact[key] = payload[key]
                _save_web_data(data)
                self._set_common_headers(200)
                self.wfile.write(json.dumps(contact).encode())
                return

        self._set_common_headers(404)
        self.wfile.write(json.dumps({"error": "Contact not found"}).encode())

    def _handle_delete_contact(self) -> None:
        contact_id = self.path.rsplit("/", 1)[-1]
        try:
            contact_id_int = int(contact_id)
        except ValueError:
            self._set_common_headers(400)
            self.wfile.write(json.dumps({"error": "Invalid contact id"}).encode())
            return

        data = _load_web_data()
        contacts = data.get("contacts", [])
        new_contacts = [c for c in contacts if c.get("id") != contact_id_int]

        if len(new_contacts) == len(contacts):
            self._set_common_headers(404)
            self.wfile.write(json.dumps({"error": "Contact not found"}).encode())
            return

        data["contacts"] = new_contacts
        _save_web_data(data)
        self._set_common_headers(204)
        self.wfile.write(b"")


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


def serve_api(args: argparse.Namespace) -> None:
    """Run a small JSON API so the web UI persists to disk/server."""

    _ensure_web_store()

    address = ("", args.port)
    httpd = http.server.ThreadingHTTPServer(address, ContactsRequestHandler)

    print(f"Serving contact API on http://0.0.0.0:{args.port}")
    print("Use Ctrl+C to stop the server.")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
    finally:
        httpd.server_close()


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

    serve_parser = subparsers.add_parser(
        "serve", help="Run a JSON API for the web UI so contacts persist across devices"
    )
    serve_parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind the web contact API (default: 8000)",
    )
    serve_parser.set_defaults(func=serve_api)

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
