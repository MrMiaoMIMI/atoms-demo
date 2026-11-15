import unittest

import public_pages


class PublicPageTests(unittest.TestCase):
    def test_paused_page_is_a_standalone_document(self) -> None:
        page = public_pages.paused_page("abc123")
        self.assertIn("<!doctype html>", page)
        self.assertIn("应用已暂停", page)
        self.assertIn("这个应用正在休息", page)
        self.assertIn('href="/s/abc123/"', page)
        self.assertIn('href="/discover"', page)
        self.assertIn("noindex", page)
        self.assertNotIn("<script", page)

    def test_not_found_page_distinguishes_the_link_failure(self) -> None:
        page = public_pages.not_found_page()
        self.assertIn("页面不存在", page)
        self.assertIn("页面走丢了", page)
        self.assertIn("404", page)
        self.assertIn('href="/"', page)
        self.assertNotIn("<script", page)

    def test_pid_is_escaped_in_the_refresh_link(self) -> None:
        page = public_pages.paused_page('"><script>alert(1)</script>')
        self.assertNotIn("<script", page)
        self.assertIn("%3Cscript%3E", page)


if __name__ == "__main__":
    unittest.main()
