"""Tests for database CRUD and model integrity."""

from __future__ import annotations

import pytest

import database as db
from models import Session, Node, Edge, NodeStatus, SessionStatus


@pytest.mark.asyncio
class TestSessionCRUD:
    async def test_create_and_get(self):
        session = Session(phone_number="+18002758777", status=SessionStatus.RUNNING)
        await db.create_session(session)

        fetched = await db.get_session(session.id)
        assert fetched is not None
        assert fetched.phone_number == "+18002758777"
        assert fetched.status == SessionStatus.RUNNING

    async def test_update(self):
        session = Session(phone_number="+18002758777")
        await db.create_session(session)

        await db.update_session(session.id, status=SessionStatus.COMPLETED, total_cost=1.23)

        fetched = await db.get_session(session.id)
        assert fetched.status == SessionStatus.COMPLETED
        assert fetched.total_cost == 1.23

    async def test_get_nonexistent(self):
        result = await db.get_session("nonexistent-id")
        assert result is None


@pytest.mark.asyncio
class TestNodeCRUD:
    async def test_create_and_get(self):
        session = Session(phone_number="+18002758777")
        await db.create_session(session)

        node = Node(session_id=session.id, dtmf_path="1w2", status=NodeStatus.PENDING)
        await db.create_node(node)

        fetched = await db.get_node(node.id)
        assert fetched is not None
        assert fetched.dtmf_path == "1w2"
        assert fetched.status == NodeStatus.PENDING

    async def test_update_node(self):
        session = Session(phone_number="+18002758777")
        await db.create_session(session)

        node = Node(session_id=session.id, status=NodeStatus.PENDING)
        await db.create_node(node)

        await db.update_node(node.id, status=NodeStatus.COMPLETED, prompt_text="Main menu", cost=0.05)

        fetched = await db.get_node(node.id)
        assert fetched.status == NodeStatus.COMPLETED
        assert fetched.prompt_text == "Main menu"
        assert fetched.cost == 0.05

    async def test_get_nodes_by_session(self):
        session = Session(phone_number="+18002758777")
        await db.create_session(session)

        for i in range(3):
            node = Node(session_id=session.id, dtmf_path=str(i))
            await db.create_node(node)

        nodes = await db.get_nodes_by_session(session.id)
        assert len(nodes) == 3

    async def test_nodes_isolated_by_session(self):
        s1 = Session(phone_number="+11111111111")
        s2 = Session(phone_number="+12222222222")
        await db.create_session(s1)
        await db.create_session(s2)

        await db.create_node(Node(session_id=s1.id))
        await db.create_node(Node(session_id=s1.id))
        await db.create_node(Node(session_id=s2.id))

        assert len(await db.get_nodes_by_session(s1.id)) == 2
        assert len(await db.get_nodes_by_session(s2.id)) == 1


@pytest.mark.asyncio
class TestEdgeCRUD:
    async def test_create_and_get_by_session(self):
        session = Session(phone_number="+18002758777")
        await db.create_session(session)

        root = Node(session_id=session.id)
        child = Node(session_id=session.id, parent_id=root.id, dtmf_path="1")
        await db.create_node(root)
        await db.create_node(child)

        edge = Edge(from_node_id=root.id, to_node_id=child.id, dtmf_key="1", label="Billing")
        await db.create_edge(edge)

        edges = await db.get_edges_by_session(session.id)
        assert len(edges) == 1
        assert edges[0].label == "Billing"
        assert edges[0].dtmf_key == "1"


@pytest.mark.asyncio
class TestDeleteSubtree:
    async def test_deletes_children_and_edges(self):
        session = Session(phone_number="+18002758777")
        await db.create_session(session)

        root = Node(session_id=session.id)
        child1 = Node(session_id=session.id, parent_id=root.id, dtmf_path="1")
        child2 = Node(session_id=session.id, parent_id=root.id, dtmf_path="2")
        grandchild = Node(session_id=session.id, parent_id=child1.id, dtmf_path="1w1")
        await db.create_node(root)
        await db.create_node(child1)
        await db.create_node(child2)
        await db.create_node(grandchild)

        e1 = Edge(from_node_id=root.id, to_node_id=child1.id, dtmf_key="1", label="A")
        e2 = Edge(from_node_id=root.id, to_node_id=child2.id, dtmf_key="2", label="B")
        e3 = Edge(from_node_id=child1.id, to_node_id=grandchild.id, dtmf_key="1", label="C")
        await db.create_edge(e1)
        await db.create_edge(e2)
        await db.create_edge(e3)

        deleted_nodes, deleted_edges = await db.delete_subtree(root.id)

        # Should delete child1, child2, grandchild (not root)
        assert len(deleted_nodes) == 3
        # Should delete all 3 edges (from root and from child1)
        assert len(deleted_edges) == 3

        # Root should still exist but be reset
        root_after = await db.get_node(root.id)
        assert root_after is not None
        assert root_after.status == NodeStatus.PENDING
        assert root_after.prompt_text == ""

        # Children should be gone
        assert await db.get_node(child1.id) is None
        assert await db.get_node(grandchild.id) is None

    async def test_no_children(self):
        session = Session(phone_number="+18002758777")
        await db.create_session(session)

        leaf = Node(session_id=session.id)
        await db.create_node(leaf)

        deleted_nodes, deleted_edges = await db.delete_subtree(leaf.id)
        assert deleted_nodes == []
        assert deleted_edges == []
