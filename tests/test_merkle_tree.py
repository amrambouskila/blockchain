"""Merkle roots duplicate the last leaf when a row is odd."""

from __future__ import annotations

import pytest

from edu_node.double_sha256 import double_sha256
from edu_node.merkle_tree import MerkleTree
from edu_node.node_constants import BLOCK_ERROR, HASH_BYTES


def test_one_leaf_is_its_own_root() -> None:
    """A single transaction id is not hashed again."""
    leaf = b"\x11" * HASH_BYTES
    assert MerkleTree().root([leaf]) == leaf


def test_odd_rows_duplicate_the_last_leaf() -> None:
    """Three leaves hash as a pair plus the last leaf duplicated."""
    leaves = [bytes([index]) * HASH_BYTES for index in (1, 2, 3)]
    pair = double_sha256(leaves[0] + leaves[1])
    sibling = double_sha256(leaves[2] + leaves[2])
    assert MerkleTree().root(leaves) == double_sha256(pair + sibling)


@pytest.mark.parametrize("leaves", [[], b"\x11" * HASH_BYTES, [b"\x11"], [b"\x11" * HASH_BYTES, "zz"]])
def test_empty_or_short_leaves_are_rejected(leaves: list[bytes]) -> None:
    """The root needs at least one 32-byte leaf."""
    with pytest.raises(ValueError, match=BLOCK_ERROR):
        MerkleTree().root(leaves)  # type: ignore[arg-type]  # a leaf list is bytes, not a bare bytes object
