from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from jobagent import sheets
from jobagent.models import Job


def test_write_sheet_skips_links_already_present():
    ws = MagicMock()
    ws.get_all_values.return_value = [sheets.HEADER, [""] * sheets.LINK_COL + ["https://a/1", "New"]]
    gc = MagicMock()
    gc.open_by_key.return_value.worksheet.return_value = ws
    jobs = [Job("Community Manager", "A", "https://a/1", "t", "Worldwide", datetime.now(timezone.utc)),
            Job("Video Editor", "B", "https://b/2", "t", "Worldwide", datetime.now(timezone.utc))]
    with patch("gspread.authorize", return_value=gc), patch.object(sheets, "_credentials"):
        added = sheets.write_sheet(jobs, "sheet-id")
    assert added == 1
    (rows,), _ = ws.append_rows.call_args
    assert rows[0][sheets.LINK_COL] == "https://b/2"
