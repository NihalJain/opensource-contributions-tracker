"""
The logger every module writes to, and the filter that keeps private names out of it.
"""
import logging
import re
from urllib.parse import quote, quote_plus


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tracker")


class NameScrubber(logging.Filter):
    """
    Replaces given names in every log message with `<private>`.

    Used when private work is redacted: the repositories are processed in memory so their numbers can be
    counted, and a log line (a progress message, a failed request's URL, an exception) must not name them,
    because CI logs of a public repository are public. Names are matched case-insensitively and also in
    their URL-encoded forms, as they appear in search queries.
    """

    def __init__(self):
        super().__init__()
        self._pattern = None

    def hide(self, names):
        forms = set()
        for name in names:
            if name and len(name) >= 3:
                forms.update({name, quote(name, safe=""), quote_plus(name)})
        ordered = sorted(forms, key=len, reverse=True)
        self._pattern = re.compile("|".join(re.escape(f) for f in ordered), re.IGNORECASE) if ordered else None

    def clear(self):
        self._pattern = None

    def filter(self, record):
        if self._pattern is not None:
            record.msg, record.args = self._pattern.sub("<private>", record.getMessage()), None
        return True


_scrubber = NameScrubber()
logger.addFilter(_scrubber)
