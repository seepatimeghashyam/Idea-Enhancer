import unittest
from unittest.mock import patch, Mock
import github


def make_response(status, payload, headers=None):
    response = Mock()
    response.status_code = status
    response.headers = headers or {}
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


class GitHubRetryTests(unittest.TestCase):
    @patch("github.time.sleep")
    @patch("github.requests.get")
    def test_rate_limit_then_success_retries_once(self, mock_get, mock_sleep):
        rate_limited = make_response(
            429,
            {"message": "API rate limit exceeded"},
            {"Retry-After": "2"},
        )
        success = make_response(
            200,
            {"items": [{
                "id": 123,
                "name": "demo",
                "full_name": "example/demo",
                "html_url": "https://github.com/example/demo",
                "owner": {"login": "example"},
                "stargazers_count": 7,
            }]},
        )
        mock_get.side_effect = [rate_limited, success]

        results = github.search_github_repositories("test query")

        self.assertEqual(mock_get.call_count, 2)
        mock_sleep.assert_called_once_with(2)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["full_name"], "example/demo")

    @patch("github.time.sleep")
    @patch("github.requests.get")
    def test_immediate_success_does_not_retry(self, mock_get, mock_sleep):
        mock_get.return_value = make_response(200, {"items": []})

        results = github.search_github_repositories("test query")

        self.assertEqual(results, [])
        self.assertEqual(mock_get.call_count, 1)
        mock_sleep.assert_not_called()

    @patch("github.time.sleep")
    @patch("github.requests.get")
    def test_rate_limit_does_not_retry_without_safe_wait(self, mock_get, mock_sleep):
        rate_limited = make_response(
            429,
            {"message": "API rate limit exceeded"},
            {"Retry-After": "120"},
        )
        mock_get.return_value = rate_limited

        results = github.search_github_repositories("test query")

        self.assertEqual(results, [])
        self.assertEqual(mock_get.call_count, 1)
        mock_sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
