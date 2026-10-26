"""Layanan latar belakang: notifikasi WA, media Windows, lirik (LRCLIB)."""
import asyncio
import bisect  # noqa: F401  (dipakai modul lain lewat services)
import io
import json
import queue
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone


# ---------- Notifikasi WA: Windows Notification Listener ----------
def winrt_listener(q):
    try:
        from winrt.windows.ui.notifications.management import (
            UserNotificationListener, UserNotificationListenerAccessStatus)
        from winrt.windows.ui.notifications import (
            NotificationKinds, KnownNotificationBindings)
    except Exception:
        q.put(("status", "missing"))
        return

    async def main():
        listener = UserNotificationListener.current
        status = await listener.request_access_async()
        if status != UserNotificationListenerAccessStatus.ALLOWED:
            q.put(("status", "denied"))
            return
        q.put(("status", "ok"))
        seen, first = set(), True
        while True:
            try:
                items = await listener.get_notifications_async(NotificationKinds.TOAST)
                for n in items:
                    if n.id in seen:
                        continue
                    seen.add(n.id)
                    if first:
                        continue
                    try:
                        app = n.app_info.display_info.display_name or ""
                        binding = n.notification.visual.get_binding(
                            KnownNotificationBindings.get_toast_generic())
                        texts = [t.text for t in binding.get_text_elements()]
                    except Exception:
                        continue
                    if "whatsapp" in (app + " " + " ".join(texts)).lower():
                        title = texts[0] if texts else "WhatsApp"
                        body = texts[1] if len(texts) > 1 else ""
                        q.put(("notif", title, body))
                first = False
                if len(seen) > 500:
                    seen = set(list(seen)[-200:])
            except Exception:
                pass
            await asyncio.sleep(1.5)

    try:
        asyncio.run(main())
    except Exception:
        q.put(("status", "error"))


# ---------- Musik: Windows Media Controls ----------
def media_listener(q, cmd_q):
    try:
        from winrt.windows.media.control import (
            GlobalSystemMediaTransportControlsSessionManager as Manager,
            GlobalSystemMediaTransportControlsSessionPlaybackStatus as PStatus)
        from winrt.windows.storage.streams import DataReader
    except Exception:
        q.put(("mstatus", "missing"))
        return

    async def read_thumb(ref):
        stream = await ref.open_read_async()
        size = int(stream.size)
        reader = DataReader(stream)
        await reader.load_async(size)
        buf = bytearray(size)
        reader.read_bytes(buf)
        return bytes(buf)

    async def main():
        mgr = await Manager.request_async()
        q.put(("mstatus", "ok"))
        last_key = None
        while True:
            try:
                s = mgr.get_current_session()
                if s is None:
                    last_key = None
                    q.put(("nomedia",))
                    await asyncio.sleep(1)
                    continue
                try:
                    while True:
                        cmd = cmd_q.get_nowait()
                        if cmd == "toggle":
                            await s.try_toggle_play_pause_async()
                        elif cmd == "next":
                            await s.try_skip_next_async()
                        elif cmd == "prev":
                            await s.try_skip_previous_async()
                        elif isinstance(cmd, tuple) and cmd[0] == "seek":
                            await s.try_change_playback_position_async(int(cmd[1] * 10_000_000))
                except queue.Empty:
                    pass
                props = await s.try_get_media_properties_async()
                title, artist = props.title or "", props.artist or ""
                if not title:
                    await asyncio.sleep(1)
                    continue
                tl = s.get_timeline_properties()
                playing = s.get_playback_info().playback_status == PStatus.PLAYING
                pos = tl.position.total_seconds()
                try:
                    age = (datetime.now(timezone.utc) - tl.last_updated_time).total_seconds()
                    age = max(0.0, min(age, 3600.0))
                except Exception:
                    age = 0.0
                dur = tl.end_time.total_seconds()
                key = (title, artist)
                if key != last_key:
                    last_key = key
                    thumb = None
                    try:
                        if props.thumbnail:
                            thumb = await read_thumb(props.thumbnail)
                    except Exception:
                        thumb = None
                    q.put(("track", title, artist, dur, thumb))
                q.put(("play", playing, pos + (age if playing else 0.0), time.time()))
            except Exception:
                pass
            await asyncio.sleep(0.5)

    try:
        asyncio.run(main())
    except Exception:
        q.put(("mstatus", "error"))


# ---------- Lirik tersinkron (LRCLIB) ----------
LRC = re.compile(r"\[(\d+):(\d+(?:\.\d+)?)\]")


def parse_lrc(text):
    out = []
    for line in (text or "").splitlines():
        stamps = LRC.findall(line)
        if not stamps:
            continue
        lyric = LRC.sub("", line).strip()
        for m, s in stamps:
            out.append((int(m) * 60 + float(s), lyric))
    out.sort(key=lambda x: x[0])
    return out


def fetch_lyrics(artist, title, dur, q, key):
    base = "https://lrclib.net/api/"

    def get(url):
        req = urllib.request.Request(url, headers={"User-Agent": "NotchIsland/1.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            return json.loads(r.read().decode("utf-8"))

    synced = None
    try:
        params = {"artist_name": artist, "track_name": title}
        if dur > 0:
            params["duration"] = int(round(dur))
        try:
            data = get(base + "get?" + urllib.parse.urlencode(params))
            synced = data.get("syncedLyrics") if isinstance(data, dict) else None
        except Exception:
            synced = None
        if not synced:
            res = get(base + "search?" + urllib.parse.urlencode(
                {"track_name": title, "artist_name": artist}))
            for item in res or []:
                if item.get("syncedLyrics"):
                    synced = item["syncedLyrics"]
                    break
    except Exception:
        pass
    q.put(("lyrics", key, parse_lrc(synced or "")))


def make_art(data, size):
    """Cover album -> PhotoImage persegi bersudut membulat (butuh Pillow)."""
    try:
        from PIL import Image, ImageDraw, ImageTk
        img = Image.open(io.BytesIO(data)).convert("RGB")
        s = min(img.size)
        left, top = (img.width - s) // 2, (img.height - s) // 2
        img = img.crop((left, top, left + s, top + s)).resize((size, size), Image.LANCZOS)
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            (0, 0, size - 1, size - 1), radius=max(3, size // 6), fill=255)
        out = Image.new("RGB", (size, size), (0, 0, 0))
        out.paste(img, mask=mask)
        return ImageTk.PhotoImage(out)
    except Exception:
        return None
