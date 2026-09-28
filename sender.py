import asyncio
import re
import time
import json
import aiohttp
from datetime import datetime
from PySide6.QtCore import QThread, Signal


def format_phone(phone):
    phone = re.sub(r"[\s\-()]+", "", str(phone).strip())
    if phone.startswith("+"):
        return phone
    if phone.startswith("251"):
        return "+" + phone
    if phone.startswith("0"):
        return "+251" + phone[1:]
    return "+251" + phone


class SendingWorker(QThread):
    progress = Signal(str, int, int, int)          # name, current, total, failed
    log = Signal(str, str)                          # level, text
    finished = Signal(str, dict, str)                # name, report, mode
    phone_result = Signal(str, str, bool, str)       # name, phone, success, detail

    def __init__(self, segment_name, phones, message, api_url, api_key,
                 mode="batch", concurrency=5, parent=None):
        super().__init__(parent)
        self.segment_name = segment_name
        self.phones = list(phones)
        self.message = message
        self.api_url = api_url.strip()
        self.api_key = api_key.strip()
        self.mode = mode
        self.concurrency = max(1, min(int(concurrency), 50))
        self.running = True
        self.processed = 0
        self.failed = 0
        self.unsent = []
        self.errors = []

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Catch BaseException to prevent silent thread death on network drops
            loop.run_until_complete(self.send_all())
        except BaseException as exc:
            self.log.emit("error", f"Worker crashed: {type(exc).__name__}: {exc}")
        finally:
            loop.close()

    async def send_all(self):
        total = len(self.phones)
        started = time.time()
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json; charset=utf-8",
            "prepaid-api-key": self.api_key,
        }
        timeout = aiohttp.ClientTimeout(total=20, connect=5, sock_connect=5, sock_read=15)
        connector = aiohttp.TCPConnector(limit=self.concurrency, limit_per_host=self.concurrency, ttl_dns_cache=300)
        semaphore = asyncio.Semaphore(self.concurrency)

        try:
            async with aiohttp.ClientSession(headers=headers, timeout=timeout, connector=connector) as session:
                tasks = [asyncio.create_task(self.send_one(session, phone, semaphore)) for phone in self.phones]
                completed = 0
                for task in asyncio.as_completed(tasks):
                    if not self.running:
                        for pending in tasks:
                            if not pending.done():
                                pending.cancel()
                        break
                    try:
                        ok, phone, detail = await task
                    except asyncio.CancelledError:
                        continue
                    except Exception as e:
                        ok, phone, detail = False, "Unknown", str(e)

                    completed += 1
                    if ok:
                        self.processed += 1
                        self.log.emit("success", f"Sent -> {phone}")
                    else:
                        self.failed += 1
                        self.unsent.append(phone)
                        self.errors.append({"phone": phone, "error": detail})
                        self.log.emit("error", f"Failed -> {phone}: {detail}")
                    self.phone_result.emit(self.segment_name, phone, ok, detail)
                    self.progress.emit(self.segment_name, completed, total, self.failed)
        except Exception as e:
            self.log.emit("error", f"Session error: {e}")

        elapsed = time.time() - started
        report = {
            "summary": {
                "processed": self.processed, "failed": self.failed, "total": total,
                "took_seconds": round(elapsed, 2),
                "rate_msg_per_sec": round(self.processed / elapsed, 2) if elapsed else 0,
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "segment": self.segment_name, "mode": self.mode, "api_url": self.api_url,
            },
            "unsent": self.unsent, "errors": self.errors,
        }
        self.finished.emit(self.segment_name, report, self.mode)

    async def send_one(self, session, phone, semaphore):
        async with semaphore:
            if not self.running:
                return False, phone, "Cancelled"
            payload = {"to": format_phone(phone), "message": self.message}
            try:
                async with session.post(self.api_url, json=payload, allow_redirects=True) as response:
                    body = (await response.text()).strip()
                    if 200 <= response.status < 300:
                        try:
                            parsed = json.loads(body) if body else None
                        except json.JSONDecodeError:
                            parsed = None
                        if isinstance(parsed, dict):
                            if parsed.get("success") is False:
                                return False, phone, f"HTTP {response.status}: {body[:500]}"
                            if str(parsed.get("status", "")).lower() in {"failed", "error", "failure"}:
                                return False, phone, f"HTTP {response.status}: {body[:500]}"
                        detail = f"HTTP {response.status}"
                        if body:
                            detail += f" -- {body[:250]}"
                        return True, phone, detail
                    return False, phone, f"HTTP {response.status}: {body[:800] if body else 'empty response'}"
            except asyncio.TimeoutError:
                return False, phone, "Request timed out"
            except aiohttp.ClientError as exc:
                return False, phone, f"Network Error: {type(exc).__name__}"
            except OSError as exc:
                return False, phone, f"Connection Error: {exc}"
            except Exception as exc:
                return False, phone, f"{type(exc).__name__}: {exc}"
