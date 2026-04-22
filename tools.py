import json
from datetime import datetime
from pathlib import Path


LEADS_FILE = Path("leads.json")


def mock_lead_capture(name: str, email: str, platform: str) -> None:
	if not LEADS_FILE.exists():
		with LEADS_FILE.open("w", encoding="utf-8") as f:
			json.dump([], f)

	try:
		with LEADS_FILE.open("r", encoding="utf-8") as f:
			leads = json.load(f)
		if not isinstance(leads, list):
			leads = []
	except (json.JSONDecodeError, OSError):
		leads = []

	leads.append(
		{
			"name": name,
			"email": email,
			"platform": platform,
			"timestamp": datetime.now().isoformat(),
		}
	)

	with LEADS_FILE.open("w", encoding="utf-8") as f:
		json.dump(leads, f, indent=2)

	print(f"\n✅ Lead captured successfully: {name}, {email}, {platform}\n")
