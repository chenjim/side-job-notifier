# tests/test_scraper_http_client.py
# 确认基于 HTTP 的抓取器统一用 curl_cffi（复刻 Chrome TLS/HTTP2 指纹），
# 避免回退到 requests 而暴露 Python/OpenSSL 指纹。

import importlib

import pytest

CURL_CFFI_MODULES = [
    "scrapers.eleduck_scraper",
    "scrapers.sxsoft_scraper",
    "scrapers.v2ex_scraper",
    "scrapers.epwk_scraper",
    "scrapers.shixian_scraper",
]


@pytest.mark.parametrize("module_name", CURL_CFFI_MODULES)
def test_requests_scrapers_use_curl_cffi(module_name):
    module = importlib.import_module(module_name)
    assert module.requests.__name__ == "curl_cffi.requests"


@pytest.mark.parametrize("module_name", CURL_CFFI_MODULES)
def test_catchable_error_class_is_curl_cffi_base(module_name):
    module = importlib.import_module(module_name)
    # 抓取器捕获 requests.RequestsError，须存在且能兜住子类
    assert hasattr(module.requests, "RequestsError")
    from curl_cffi.requests.exceptions import HTTPError
    assert issubclass(HTTPError, module.requests.RequestsError)
