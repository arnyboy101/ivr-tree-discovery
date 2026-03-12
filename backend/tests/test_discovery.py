"""Tests for discovery logic — fingerprinting, depth, cycle detection."""

from __future__ import annotations

import pytest

from discovery import options_fingerprint, get_node_depth, is_cycle, _core_label
from models import Node, NodeStatus


class TestOptionsFingerprint:
    def test_basic(self):
        options = [
            {"dtmf_key": "1", "label": "Billing"},
            {"dtmf_key": "2", "label": "Support"},
        ]
        fp = options_fingerprint(options)
        assert fp == frozenset({"billing", "support"})

    def test_strips_parenthetical_descriptions(self):
        """Labels with parenthetical descriptions should fingerprint to core label."""
        fp1 = options_fingerprint([
            {"dtmf_key": "1", "label": "Package (track status, delivery issues)"},
            {"dtmf_key": "2", "label": "Mail (daily services, pickup, change of address)"},
        ])
        fp2 = options_fingerprint([
            {"dtmf_key": "1", "label": "Package (track, re-delivery, service requests)"},
            {"dtmf_key": "2", "label": "Mail (delivery, hold mail, service requests)"},
        ])
        assert fp1 == fp2
        assert fp1 == frozenset({"package", "mail"})

    def test_case_insensitive(self):
        fp1 = options_fingerprint([{"dtmf_key": "1", "label": "Billing"}])
        fp2 = options_fingerprint([{"dtmf_key": "1", "label": "billing"}])
        assert fp1 == fp2

    def test_order_independent(self):
        fp1 = options_fingerprint([
            {"dtmf_key": "1", "label": "Billing"},
            {"dtmf_key": "2", "label": "Support"},
        ])
        fp2 = options_fingerprint([
            {"dtmf_key": "2", "label": "Support"},
            {"dtmf_key": "1", "label": "Billing"},
        ])
        assert fp1 == fp2

    def test_strips_whitespace(self):
        fp1 = options_fingerprint([{"dtmf_key": "1", "label": "  Billing  "}])
        fp2 = options_fingerprint([{"dtmf_key": "1", "label": "Billing"}])
        assert fp1 == fp2

    def test_different_menus_differ(self):
        fp1 = options_fingerprint([{"dtmf_key": "1", "label": "Billing"}])
        fp2 = options_fingerprint([{"dtmf_key": "1", "label": "Support"}])
        assert fp1 != fp2

    def test_same_labels_different_keys(self):
        """Same labels with different DTMF keys should still match (fingerprint is label-based)."""
        fp1 = options_fingerprint([{"dtmf_key": "1", "label": "Billing"}])
        fp2 = options_fingerprint([{"dtmf_key": "5", "label": "Billing"}])
        assert fp1 == fp2

    def test_empty(self):
        fp = options_fingerprint([])
        assert fp == frozenset()


class TestGetNodeDepth:
    def test_root_is_zero(self):
        root = Node(id="root", session_id="s1")
        nodes_by_id = {"root": root}
        assert get_node_depth(root, nodes_by_id) == 0

    def test_child_is_one(self):
        root = Node(id="root", session_id="s1")
        child = Node(id="child", session_id="s1", parent_id="root")
        nodes_by_id = {"root": root, "child": child}
        assert get_node_depth(child, nodes_by_id) == 1

    def test_grandchild_is_two(self):
        root = Node(id="root", session_id="s1")
        child = Node(id="child", session_id="s1", parent_id="root")
        grandchild = Node(id="gc", session_id="s1", parent_id="child")
        nodes_by_id = {"root": root, "child": child, "gc": grandchild}
        assert get_node_depth(grandchild, nodes_by_id) == 2

    def test_missing_parent_stops(self):
        """If parent_id references a node not in the dict, stop counting."""
        node = Node(id="orphan", session_id="s1", parent_id="missing")
        nodes_by_id = {"orphan": node}
        assert get_node_depth(node, nodes_by_id) == 0


class TestCoreLabel:
    def test_strips_parenthetical(self):
        assert _core_label("Package (track status, delivery issues)") == "package"

    def test_multiple_parentheticals(self):
        assert _core_label("Mail (daily services, pickup) (extra)") == "mail"

    def test_no_parenthetical(self):
        assert _core_label("Billing") == "billing"

    def test_only_parenthetical(self):
        assert _core_label("(something)") == "(something)"


class TestIsCycle:
    def test_exact_match(self):
        seen = {frozenset({"billing", "support"})}
        assert is_cycle(frozenset({"billing", "support"}), seen)

    def test_no_match(self):
        seen = {frozenset({"billing", "support"})}
        assert not is_cycle(frozenset({"shipping", "returns"}), seen)

    def test_fuzzy_match_usps_scenario(self):
        """Simulates the USPS bug: same menu parsed with different parenthetical descriptions."""
        seen = {frozenset({"package", "mail", "tools", "stamps", "alerts", "other"})}
        # Claude parsed the same menu with only 4 options this time
        fp = frozenset({"package", "mail", "tools", "stamps"})
        # 4/6 overlap = 0.67 > 0.6 threshold
        assert is_cycle(fp, seen)

    def test_below_threshold(self):
        seen = {frozenset({"billing", "support", "shipping", "returns", "account"})}
        fp = frozenset({"billing", "complaints", "orders", "tracking", "help"})
        # Only 1/9 overlap = 0.11 < 0.6
        assert not is_cycle(fp, seen)

    def test_empty_seen(self):
        assert not is_cycle(frozenset({"billing"}), set())

    def test_empty_fingerprint(self):
        seen = {frozenset({"billing"})}
        assert not is_cycle(frozenset(), seen)


