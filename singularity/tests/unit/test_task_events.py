"""
Tests for TaskEventBus (Fáze 11).
"""
import asyncio

import pytest

from core.task_events import TaskEventBus


@pytest.fixture
def bus():
    return TaskEventBus()


async def test_subscribe_and_publish(bus):
    q = await bus.subscribe("task-1")
    event = {"status": "running", "task_id": "task-1"}
    await bus.publish("task-1", event)
    received = await asyncio.wait_for(q.get(), timeout=1.0)
    assert received == event


async def test_multiple_subscribers_each_receive(bus):
    q1 = await bus.subscribe("t2")
    q2 = await bus.subscribe("t2")
    event = {"status": "completed", "task_id": "t2"}
    await bus.publish("t2", event)
    r1 = await asyncio.wait_for(q1.get(), timeout=1.0)
    r2 = await asyncio.wait_for(q2.get(), timeout=1.0)
    assert r1 == event
    assert r2 == event


async def test_unsubscribe_stops_delivery(bus):
    q = await bus.subscribe("t3")
    await bus.unsubscribe("t3", q)
    assert bus.subscriber_count("t3") == 0
    # publish after unsubscribe must not raise
    await bus.publish("t3", {"status": "running"})
    assert q.empty()


async def test_subscriber_count(bus):
    assert bus.subscriber_count("t4") == 0
    q1 = await bus.subscribe("t4")
    q2 = await bus.subscribe("t4")
    assert bus.subscriber_count("t4") == 2
    await bus.unsubscribe("t4", q1)
    assert bus.subscriber_count("t4") == 1
    await bus.unsubscribe("t4", q2)
    assert bus.subscriber_count("t4") == 0


async def test_publish_to_different_tasks_isolated(bus):
    qa = await bus.subscribe("tA")
    qb = await bus.subscribe("tB")
    await bus.publish("tA", {"task_id": "tA"})
    # tB queue must remain empty
    assert qb.empty()
    received = await asyncio.wait_for(qa.get(), timeout=1.0)
    assert received["task_id"] == "tA"
