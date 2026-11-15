"""Agent recovery must never replay prints or hide a failed OS inventory scan."""
import asyncio
import json
from unittest.mock import patch

import pytest

from deviceshare.agent import connected_session, reconnect_delay, receive_jobs, refresh_inventory


class RecordingSocket:
    def __init__(self):
        self.sent = []

    async def send(self, value):
        self.sent.append(json.loads(value))


def test_transient_scan_failure_recovers_without_restarting_agent():
    async def scenario():
        socket = RecordingSocket()
        requested = asyncio.Event()
        config = {"allowed_printers": ["HP"]}
        with patch("deviceshare.agent.discover", side_effect=[
            OSError("private-local-path-should-not-go-to-hub"),
            [{"id": "printer:HP", "kind": "printer", "label": "HP"}],
        ]):
            task = asyncio.create_task(refresh_inventory(socket, config, requested))
            try:
                for _ in range(80):
                    if socket.sent:
                        break
                    await asyncio.sleep(0.01)
                assert socket.sent == [{"type": "inventory_error"}]
                requested.set()
                for _ in range(80):
                    if len(socket.sent) == 2:
                        break
                    await asyncio.sleep(0.01)
                assert socket.sent[1]["type"] == "inventory"
                assert socket.sent[1]["devices"][0]["allowed"] is True
                assert "private-local-path" not in str(socket.sent)
            finally:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

    asyncio.run(scenario())


def test_failed_inventory_socket_send_terminates_session_for_reconnect():
    class BrokenSocket(RecordingSocket):
        async def send(self, value):
            raise OSError("socket closed")

        def __aiter__(self):
            return self

        async def __anext__(self):
            await asyncio.Future()

    async def scenario():
        with patch("deviceshare.agent.discover", return_value=[]):
            with pytest.raises(OSError, match="socket closed"):
                await asyncio.wait_for(connected_session(BrokenSocket(), {}), timeout=1)

    asyncio.run(scenario())


def test_malformed_hub_messages_do_not_kill_agent_or_print():
    class InputSocket(RecordingSocket):
        async def __aiter__(self):
            for message in ("{broken", "[]", "null", '{"type":"refresh_inventory"}'):
                yield message

    async def scenario():
        requested = asyncio.Event()
        socket = InputSocket()
        with patch("deviceshare.agent.execute") as execute:
            await receive_jobs(socket, {}, requested)
            execute.assert_not_called()
        assert requested.is_set()
        assert not socket.sent

    asyncio.run(scenario())


def test_reconnect_backoff_is_bounded_and_not_a_tight_loop():
    with patch("deviceshare.agent.random.uniform", return_value=0.25):
        assert [reconnect_delay(n) for n in range(1, 8)] == [
            1.25, 2.25, 4.25, 8.25, 16.25, 16.25, 16.25,
        ]
