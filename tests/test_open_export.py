"""Open event export, webhooks, and the stream adapter. No live calls."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from xml.etree import ElementTree

from rastro import api
from rastro.feeds import cifs_feed, cifs_xml, reset_feeds, subscribe_webhook, waze_ul
from rastro.field_note import decide_note, reset_field_notes
from rastro.streams import classify_stream


def setup_function():
    reset_feeds()
    reset_field_notes()


def test_cifs_export_is_example_data_and_not_a_partnership():
    feed = cifs_feed()
    assert feed["partnership"] is False
    assert feed["submit_to_waze"] is False
    assert feed["not_verified"] is True
    assert feed["example_data"] is True
    assert "compatible with Waze for Cities" in feed["description"]
    assert "partnership" in feed["description"].lower()
    blob = json.dumps(feed).lower()
    for banned in ("uber", "didi", "google maps", "official partner"):
        assert banned not in blob
    assert len(feed["incidents"]) == 2
    required = {"id", "type", "description", "street", "direction", "polyline", "starttime", "creationtime"}
    for row in feed["incidents"]:
        assert required <= set(row)
        assert row["street"] == "Example road"
        assert row["polyline"].startswith("9.928069 -84.090725")
        assert " " in row["polyline"]
    types = {row["type"] for row in feed["incidents"]}
    assert types == {"HAZARD", "JAM"}
    link = feed["links"][0]["waze_ul"]
    assert link == waze_ul()
    assert link.startswith("https://www.waze.com/ul?ll=9.928069,-84.090725")


def test_cifs_xml_carries_the_same_incidents():
    root = ElementTree.fromstring(cifs_xml())
    rows = root.findall("incident")
    assert len(rows) == 2
    assert rows[0].findtext("type") == "HAZARD"
    assert rows[1].findtext("type") == "JAM"
    assert "Example road" in rows[0].findtext("street")


def test_webhook_queues_without_delivery_and_rejects_secrets():
    try:
        subscribe_webhook("http://user:secret@example.com/hook")
        raise AssertionError("secret in url must fail")
    except ValueError:
        pass
    try:
        subscribe_webhook("http://127.0.0.1/hook")
        raise AssertionError("localhost must fail")
    except ValueError:
        pass
    row = subscribe_webhook("https://example.com/rastro")
    assert row["delivery"] == "off"
    decide_note("clip:DSCF0112", "confirm")
    listed = api_list = __import__("rastro.feeds", fromlist=["list_webhooks"]).list_webhooks()
    assert listed["outbox"]
    assert listed["outbox"][0]["delivered"] is False
    assert listed["outbox"][0]["event"]["engine"]["unique_count"] == 2
    assert listed["outbox"][0]["event"]["engine_count"].startswith("90 raw detections")
    assert api_list["webhooks"][0]["url"] == "https://example.com/rastro"


def test_stream_adapter_classifies_and_stays_simulated():
    rtsp = classify_stream("rtsp://cams.example.com/live")
    assert rtsp["kind"] == "rtsp"
    assert rtsp["connected"] is False
    assert rtsp["mode"] == "simulated"
    assert rtsp["not_verified"] is True
    hls = classify_stream("https://cdn.example.com/stream/index.m3u8")
    assert hls["kind"] == "hls"
    mjpeg = classify_stream("https://cdn.example.com/axis/mjpg/video.mjpg")
    assert mjpeg["kind"] == "mjpeg"
    try:
        classify_stream("https://user:pass@cams.example.com/video.mjpg")
        raise AssertionError("secret must fail")
    except ValueError:
        pass
    try:
        classify_stream("https://cdn.example.com/file.mp4")
        raise AssertionError("plain file must fail")
    except ValueError:
        pass


def test_http_open_endpoints():
    server = ThreadingHTTPServer(("127.0.0.1", 0), api.Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}"
    try:
        with urllib.request.urlopen(f"{base}/api/field-note?clip=DSCF0112", timeout=5) as res:
            note = json.loads(res.read().decode())["note"]
        assert note["engine_count"] == "90 raw detections → 2 unique coyotes"
        assert note["paid_call"] is False
        req = urllib.request.Request(
            f"{base}/api/field-note",
            data=json.dumps({"id": "clip:DSCF0112", "action": "dismiss"}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as res:
            body = json.loads(res.read().decode())
        assert body["note"]["status"] == "dismissed"
        with urllib.request.urlopen(f"{base}/api/open/events", timeout=5) as res:
            feed = json.loads(res.read().decode())
        assert feed["partnership"] is False
        assert feed["example_data"] is True
        with urllib.request.urlopen(f"{base}/api/open/events.xml", timeout=5) as res:
            xml = res.read().decode()
        assert "<type>HAZARD</type>" in xml
        req = urllib.request.Request(
            f"{base}/api/streams",
            data=json.dumps({"url": "rtsp://cams.example.com/a"}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as res:
            stream = json.loads(res.read().decode())
        assert stream["connected"] is False
        assert stream["kind"] == "rtsp"
        bad = urllib.request.Request(
            f"{base}/api/webhooks",
            data=json.dumps({"url": "http://127.0.0.1/hook"}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(bad, timeout=5)
            raise AssertionError("localhost webhook should be rejected")
        except urllib.error.HTTPError as exc:
            assert exc.code == 400
    finally:
        server.shutdown()
