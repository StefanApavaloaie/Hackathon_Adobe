# Owned by feature/delivery. Only /webhooks/resend is left: it's optional and first on the
# design's cut list. Delete this file if it gets built.
def test_resend_webhook_is_stubbed(client):
    assert client.post("/webhooks/resend").status_code == 501
