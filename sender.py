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
    network_lost = Signal(str, str, object)          # name, detail, lost_datetime
    network_restored = Signal(str)                   # name

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
        self.paused = False
        self._network_paused = False
        self.processed = 0
        self.failed = 0
        self.unsent = []
        self.errors = []
        self.cancelled = 0

    def pause(self):
        self.paused = True

    def resume(self):
        self.paused = False

    def set_network_paused(self, state: bool):
        self._network_paused = bool(state)

    def stop(self):
        self.running = False
        self.paused = False
        self._network_paused = False

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
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

        queue = asyncio.Queue()
        for p in self.phones:
            queue.put_nowait(p)

        completed = 0
        reconnect_lock = asyncio.Lock()
        is_reconnecting = False

        async def check_reconnect(session):
            """Tests if the API server can be reached."""
            try:
                ping_payload = {"ping": True}
                async with session.post(
                    self.api_url,
                    json=ping_payload,
                    timeout=aiohttp.ClientTimeout(total=5, connect=4)
                ) as resp:
                    return True
            except (aiohttp.ClientConnectorError, aiohttp.ServerDisconnectedError,
                    aiohttp.ClientOSError, aiohttp.ClientPayloadError,
                    aiohttp.ClientConnectionError, asyncio.TimeoutError, OSError):
                return False
            except Exception:
                # Any HTTP response (including 400, 401, 404, 405, 500) proves server is reachable!
                return True

        async def worker_loop(session):
            nonlocal completed, is_reconnecting
            while self.running:
                # 1. Wait if paused by user or network hold
                while (self.paused or self._network_paused) and self.running:
                    await asyncio.sleep(0.2)
                if not self.running:
                    break

                # 2. Get next phone
                try:
                    phone = queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

                # 3. Send phone with network retry
                while self.running:
                    while (self.paused or self._network_paused) and self.running:
                        await asyncio.sleep(0.2)
                    if not self.running:
                        self.cancelled += 1
                        self.unsent.append(phone)
                        break

                    ok, phone_out, detail, is_net_err = await self.send_one(session, phone)

                    if is_net_err:
                        # Network error detected!
                        async with reconnect_lock:
                            if not is_reconnecting and self.running:
                                is_reconnecting = True
                                self._network_paused = True
                                lost_time = datetime.now()
                                self.log.emit("error", f"Network connection lost: {detail}. Retrying connection...")
                                self.network_lost.emit(self.segment_name, detail, lost_time)

                                # Reconnection loop
                                while self.running:
                                    # If paused by user while reconnecting, wait until user resumes
                                    while self.paused and self.running:
                                        await asyncio.sleep(0.3)
                                    if not self.running:
                                        break

                                    if await check_reconnect(session):
                                        is_reconnecting = False
                                        self._network_paused = False
                                        self.log.emit("success", "Connection to API server restored! Resuming send...")
                                        self.network_restored.emit(self.segment_name)
                                        break
                                    await asyncio.sleep(2.0)

                        if not self.running:
                            self.cancelled += 1
                            self.unsent.append(phone)
                            break
                        # Retry this same phone
                        continue
                    else:
                        # Finished sending this phone
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
                        break

        try:
            async with aiohttp.ClientSession(headers=headers, timeout=timeout, connector=connector) as session:
                num_workers = min(self.concurrency, max(1, total))
                worker_tasks = [asyncio.create_task(worker_loop(session)) for _ in range(num_workers)]
                await asyncio.gather(*worker_tasks, return_exceptions=True)
        except Exception as e:
            self.log.emit("error", f"Session error: {e}")

        # If interrupted, gather remaining phones
        while not queue.empty():
            try:
                p = queue.get_nowait()
                self.cancelled += 1
                self.unsent.append(p)
            except asyncio.QueueEmpty:
                break

        elapsed = time.time() - started
        report = {
            "summary": {
                "processed": self.processed, "failed": self.failed, "total": total,
                "cancelled": self.cancelled, "interrupted": not self.running,
                "took_seconds": round(elapsed, 2),
                "rate_msg_per_sec": round(self.processed / elapsed, 2) if elapsed else 0,
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "segment": self.segment_name, "mode": self.mode, "api_url": self.api_url,
            },
            "unsent": self.unsent, "errors": self.errors,
        }
        self.finished.emit(self.segment_name, report, self.mode)

    async def send_one(self, session, phone):
        if not self.running:
            return False, phone, "Cancelled", False
        payload = {"to": format_phone(phone), "message": self.message}
        try:
            async with session.post(self.api_url, json=payload, allow_redirects=True) as response:
                body = (await response.text()).strip()
                # 502, 503, 504 are server down / network gateway issues
                if response.status in (502, 503, 504):
                    return False, phone, f"HTTP {response.status} Server Unavailable", True

                if 200 <= response.status < 300:
                    try:
                        parsed = json.loads(body) if body else None
                    except json.JSONDecodeError:
                        parsed = None
                    if isinstance(parsed, dict):
                        if parsed.get("success") is False:
                            return False, phone, f"HTTP {response.status}: {body[:500]}", False
                        if str(parsed.get("status", "")).lower() in {"failed", "error", "failure"}:
                            return False, phone, f"HTTP {response.status}: {body[:500]}", False
                    detail = f"HTTP {response.status}"
                    if body:
                        detail += f" -- {body[:250]}"
                    return True, phone, detail, False
                return False, phone, f"HTTP {response.status}: {body[:800] if body else 'empty response'}", False
        except asyncio.TimeoutError:
            return False, phone, "Request timed out", True
        except (aiohttp.ClientConnectorError, aiohttp.ServerDisconnectedError,
                aiohttp.ClientOSError, aiohttp.ClientPayloadError,
                aiohttp.ClientConnectionError) as exc:
            return False, phone, f"Network Error: {type(exc).__name__}", True
        except OSError as exc:
            return False, phone, f"Connection Error: {exc}", True
        except Exception as exc:
            err_str = str(exc).lower()
            is_net = any(w in err_str for w in ["connect", "network", "timeout", "refused", "reset", "unreachable", "winerror"])
            return False, phone, f"{type(exc).__name__}: {exc}", is_net
