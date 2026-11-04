from types import SimpleNamespace

import pytest

from hivelens import config, meta_client


@pytest.mark.parametrize('ipv6', [False, True])
def test_ipv6_is_opt_in_and_scoped_to_model_client(monkeypatch, ipv6):
    import httpx2
    import openai

    calls = {}
    def fake_openai(**kwargs):
        calls.update(kwargs)
        return SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kw: None)),
            responses=SimpleNamespace(create=lambda **kw: None),
        )
    monkeypatch.setattr(config, 'API_KEY', 'test-not-a-secret')
    monkeypatch.setattr(config, 'API_IPV6', ipv6)
    monkeypatch.setattr(openai, 'OpenAI', fake_openai)
    transports = []
    transport = httpx2.HTTPTransport
    def capture_transport(**kwargs):
        transports.append(kwargs)
        return transport(**kwargs)
    monkeypatch.setattr(httpx2, 'HTTPTransport', capture_transport)
    meta_client.client.cache_clear()
    try:
        meta_client.client()
        assert ('http_client' in calls) is ipv6
        assert transports == ([{'local_address': '::'}] if ipv6 else [])
        assert calls['base_url'] == config.API_BASE
        assert calls['timeout'] == 180
    finally:
        if 'http_client' in calls:
            calls['http_client'].close()
        meta_client.client.cache_clear()
