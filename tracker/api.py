"""
Talking to the GitHub REST API: authentication, one shared session, pagination, retries and rate limits.
"""
import os
import time

import requests
import urllib3

from .log import logger


MAX_SEARCH_RESULT_SIZE = 1000

# Suppress the insecure warning from urllib3.
urllib3.disable_warnings(category=urllib3.exceptions.InsecureRequestWarning)

# GitHub API base URL
GITHUB_API_URL = "https://api.github.com"

# Proxies configuration
proxies = {
    "http": os.getenv("HTTP_PROXY"),
    "https": os.getenv("HTTPS_PROXY")
}

# GitHub token for authentication
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

# Headers for authentication
HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

# Every request goes through one session. It keeps the connection to api.github.com open between
# requests, so the TCP and TLS handshake is paid once per run instead of once per request.
SESSION = requests.Session()

# GitHub's guidance when a request is refused for going too fast and the response says nothing about
# how long to wait (no Retry-After, and the rate limit is not exhausted): wait at least a minute, and
# wait longer each time it continues.
SECONDARY_LIMIT_FIRST_WAIT = 60
SECONDARY_LIMIT_MAX_WAIT = 300


def _says_secondary_limit(response):
    try:
        message = str(response.json().get('message', '')).lower()
    except Exception:
        return False
    return 'secondary rate limit' in message or 'abuse detection' in message


def rate_limit_wait(response, secondary_waits=0):
    """
    Work out whether a response is a rate limit and how long to wait before asking again.

    Returns (seconds, reason) or None when the response is not a rate limit. In order of preference:
    the `Retry-After` header; the primary limit's reset time, when none of the allowance is left;
    otherwise a secondary limit, for which GitHub says to wait at least a minute and then longer.
    Retrying a secondary limit quickly is harmful: every retry spends from the same allowance
    (a search 403 was seen to cost one of the 30 searches a minute each time) while GitHub is
    asking for less traffic.
    """
    if response.status_code not in (403, 429):
        return None
    headers = response.headers
    remaining, reset_ts = headers.get('X-RateLimit-Remaining'), headers.get('X-RateLimit-Reset')

    retry_after = headers.get('Retry-After')
    if retry_after:
        try:
            return int(retry_after) + 1, 'retry-after'
        except ValueError:
            pass
    if remaining == '0' and reset_ts:
        return max(int(reset_ts) - int(time.time()) + 1, 1), 'primary'
    if response.status_code == 429 or _says_secondary_limit(response):
        return min(SECONDARY_LIMIT_FIRST_WAIT * 2 ** secondary_waits, SECONDARY_LIMIT_MAX_WAIT), 'secondary'
    if remaining == '0':
        return SECONDARY_LIMIT_FIRST_WAIT, 'primary'
    return None  # an ordinary 403: forbidden, not a rate limit


def get_all_pages(url, params, max_retries=10, backoff_factor=0.3, with_pagination=True, meta=None,
                  give_up_over=None, no_retry_on=(), redact_url=False):
    """
    Retrieve all pages of results from a paginated GitHub API endpoint.

    Args:
        url (str): The API endpoint URL.
        params (dict): The query parameters for the request.
        max_retries (int): The maximum number of retries for failed requests.
        backoff_factor (float): The factor for exponential backoff between retries.
        with_pagination (bool): Whether to handle pagination. Defaults to True.
        meta (dict): Optional. For search endpoints it receives `total_count` (how many results exist,
            which can exceed what the API will return) and `incomplete_results`. The Search API stops
            at MAX_SEARCH_RESULT_SIZE results without saying so, so a caller that needs every result
            must compare `total_count` with what it received.
        give_up_over (int): Optional. For search endpoints: if the first page shows more than this many
            matching results, stop at once and return that first page. Paging to the API's cap only to
            discover the result set was truncated costs ten requests; `total_count` is on page one.
        no_retry_on (tuple): Optional. HTTP status codes that are final answers, such as 404 for a
            repository the token cannot see. The error is raised at once, without retries and without
            being logged, because the logged URL would name the repository.
        redact_url (bool): Optional. Keep the URL and the exception text out of the log, for a request
            whose URL names something that must not be logged yet (a repository whose visibility is not
            known). Failures are then logged by HTTP status or exception type only.

    Returns:
        list: A list of results from all pages.
    """
    params = dict(params)  # avoid mutating the caller's dict
    results = []
    page = 1
    secondary_waits = 0
    while True:
        if with_pagination:
            params['page'] = page
        for attempt in range(max_retries):
            try:
                response = SESSION.get(url, headers=HEADERS, params=params, proxies=proxies, verify=False)

                # Handle rate-limit responses before raise_for_status so we can inspect headers.
                limited = rate_limit_wait(response, secondary_waits)
                if limited is not None:
                    wait, reason = limited
                    if reason == 'secondary':
                        secondary_waits += 1
                    logger.warning(f"Rate limited (HTTP {response.status_code}, {reason}). "
                                   f"Sleeping {wait}s (attempt {attempt + 1}/{max_retries}).")
                    time.sleep(wait)
                    continue  # retry this attempt
                # Anything else, including a real 403 (auth/forbidden), goes to raise_for_status
                response.raise_for_status()
                data = response.json()

                # Proactively back off when the rate-limit window is exhausted so the
                # next request doesn't immediately get a 429/403.
                rl_remaining = response.headers.get('X-RateLimit-Remaining')
                reset_ts = response.headers.get('X-RateLimit-Reset')
                if rl_remaining is not None and int(rl_remaining) == 0 and reset_ts:
                    wait = max(int(reset_ts) - int(time.time()) + 1, 1)
                    logger.warning(f"Rate limit exhausted after this request. Sleeping {wait}s until reset.")
                    time.sleep(wait)

                if not data:
                    return results

                if with_pagination:
                    if url.startswith(f"{GITHUB_API_URL}/search/"):
                        # For search API, check if there are more pages
                        total_count = data.get('total_count', 0)
                        items = data.get('items', [])
                        results.extend(items)
                        if meta is not None and page == 1:
                            meta['total_count'] = total_count
                            meta['incomplete_results'] = bool(data.get('incomplete_results', False))
                        if give_up_over is not None and page == 1 and total_count > give_up_over:
                            return results
                        # Check if there are more pages based on the total_count and current page
                        # NOTE: In search "Only the first 1000 search results are available"
                        total_until_now = page * params.get('per_page', 100)
                        if len(items) > 0 and total_count > total_until_now and total_until_now < MAX_SEARCH_RESULT_SIZE:
                            page += 1
                            break  # exit retry loop; outer while fetches next page
                        else:
                            return results
                    else:
                        results.extend(data)
                    page += 1
                else:
                    return data
                # Exit retry loop on success
                break
            except requests.exceptions.RequestException as e:
                if getattr(getattr(e, 'response', None), 'status_code', None) in no_retry_on:
                    raise
                if redact_url:
                    status = getattr(getattr(e, 'response', None), 'status_code', None)
                    what = f"HTTP {status}" if status else type(e).__name__
                    logger.error(f"Request failed: {what}, attempt {attempt + 1} of {max_retries}")
                else:
                    logger.error(f"Request failed: {e}, attempt {attempt + 1} of {max_retries}")
                if attempt < max_retries - 1:
                    time.sleep(backoff_factor * (2 ** attempt))  # Exponential backoff
                else:
                    logger.critical("Max retries exceeded (URL withheld)" if redact_url
                                    else f"Max retries exceeded for URL: {url}")
                    raise
    return results
