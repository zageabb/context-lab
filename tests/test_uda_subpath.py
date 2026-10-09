"""UDA proxy prefix and LAN fallback checks."""
from app import app

def test_dashboard_routing():
    client=app.test_client()
    local=client.get("/")
    assert local.status_code==200
    assert '<base href="/">' in local.get_data(as_text=True)
    forwarded={"X-Forwarded-Prefix":"/apps/context-lab","X-Forwarded-Host":"tanyaanne.ddns.net","X-Forwarded-Proto":"https"}
    proxied=client.get("/",headers=forwarded)
    assert proxied.status_code==200
    html=proxied.get_data(as_text=True)
    assert '<base href="/apps/context-lab/">' in html
    assert '/apps/context-lab/static/js/chat.js' in html
    assert '/apps/context-lab/environments' in html
