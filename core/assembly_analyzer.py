"""
Builds a structured assembly tree from the raw parts list produced by StepReader.
Determines parent-child relationships and produces an ordered list suitable
for kinematic chain construction.
"""
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

    def analyze(self, parts: List[Dict]) -> List[AssemblyNode]:
        """
        Build a tree of AssemblyNode objects from the flat parts list.
        Parts with parent=None are roots.
        Returns a flattened ordered list (breadth-first).
        """
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
