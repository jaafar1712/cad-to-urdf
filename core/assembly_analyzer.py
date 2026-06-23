"""
Builds a structured assembly tree from the raw parts list produced by StepReader.
Determines parent-child relationships and produces an ordered list suitable
for kinematic chain construction.
"""
from collections import Counter
from typing import List, Dict, Optional
from utils.logger import get_logger

log = get_logger(__name__)


class AssemblyNode:
    def __init__(self, part: Dict):
        self.part     = part
        self.name:    str = part['name']
        self.index:   int = part['index']
        self.parent:  Optional['AssemblyNode'] = None
        self.children: List['AssemblyNode'] = []


class AssemblyAnalyzer:

    @staticmethod
    def _deduplicate_names(parts: List[Dict]) -> List[Dict]:
        """Append _1 _2 … to any name that appears more than once."""
        counts = Counter(p['name'] for p in parts)
        seen: Dict[str, int] = {}
        for p in parts:
            n = p['name']
            if counts[n] > 1:
                seen[n] = seen.get(n, 0) + 1
                p['name'] = f"{n}_{seen[n]}"
        return parts

    def analyze(self, parts: List[Dict]) -> List[AssemblyNode]:
        """
        Build a tree of AssemblyNode objects from the flat parts list.
        Parts with parent=None are roots.
        Returns a flattened ordered list (breadth-first).
        """
        parts = self._deduplicate_names(parts)
        nodes: Dict[str, AssemblyNode] = {}
        for p in parts:
            nodes[p['name']] = AssemblyNode(p)

        roots: List[AssemblyNode] = []
        for p in parts:
            node = nodes[p['name']]
            parent_name = p.get('parent')
            if parent_name and parent_name in nodes:
                parent_node = nodes[parent_name]
                node.parent = parent_node
                parent_node.children.append(node)
            else:
                roots.append(node)

        log.info(
            f"Assembly tree: {len(parts)} parts, {len(roots)} root(s)"
        )

        # Return breadth-first ordering
        ordered: List[AssemblyNode] = []
        queue = list(roots)
        while queue:
            node = queue.pop(0)
            ordered.append(node)
            queue.extend(node.children)

        return ordered

    def get_kinematic_chain(self, nodes: List[AssemblyNode]) -> List[Dict]:
        """Return the flat list of parts in kinematic order."""
        return [n.part for n in nodes]

    def print_tree(self, nodes: List[AssemblyNode], indent: int = 0):
        for node in nodes:
            if node.parent is None:
                self._print_node(node, 0)

    def _print_node(self, node: AssemblyNode, depth: int):
        log.debug("  " * depth + f"└─ {node.name}")
        for child in node.children:
            self._print_node(child, depth + 1)
