# Speaker Gym Funnel Tracker

This repository contains a lightweight command-line application for tracking
outreach to your Speaker's Gym community. The tool stores contacts locally in a
JSON file and helps you keep counts of how many people:

- Were contacted
- Joined the community
- Took the 7-day challenge
- Submitted their contact information for the paid 90-day program

## Getting started

1. **Install Python 3.9+** (already available in most environments).
2. Run commands from the repository root:

   ```bash
   python app.py --help
   ```

The app will create `data/funnel.json` automatically on first run.

## Commands

### Add a contact

```bash
python app.py add "Alex Lee" --notes "Met at networking event"
```

### Update a contact's progress

```bash
# Mark someone as joining, finishing the challenge, and submitting 90-day details
python app.py update "Alex Lee" --joined --challenge --contact-submitted

# Remove a flag or replace notes
python app.py update "Alex Lee" --no-challenge --notes "Rescheduled challenge for next week"
```

### List contacts (optionally filtered)

```bash
python app.py list
python app.py list --filter joined
python app.py list --filter challenge
python app.py list --filter contact_submitted
```

### View summary counts

```bash
python app.py summary
```

### Reset the data store

```bash
python app.py reset
```

## Data format

Contacts are saved in `data/funnel.json` with the following schema:

```json
{
  "contacts": [
    {
      "name": "Alex Lee",
      "contacted_at": "2024-05-23T18:05:00Z",
      "joined": true,
      "challenge": true,
      "contact_submitted": false,
      "notes": "Met at networking event"
    }
  ]
}
```

You can safely edit this file manually if you need to make bulk changes.
