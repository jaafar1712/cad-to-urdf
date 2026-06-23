"""
QTreeWidget that displays the assembly hierarchy.
"""
from PyQt5.QtWidgets import QTreeWidget, QTreeWidgetItem
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QIcon, QColor, QBrush


class AssemblyTreeWidget(QTreeWidget):
    part_selected = pyqtSignal(str)   # emits part name when clicked

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderLabels(['Part / Assembly', 'Index'])
        self.setColumnWidth(0, 200)
        self.setColumnWidth(1, 50)
        self.setAlternatingRowColors(True)
        self.itemClicked.connect(self._on_item_clicked)
        self._items: dict = {}

    def populate(self, parts: list):
        self.clear()
        self._items = {}
        for p in parts:
            item = QTreeWidgetItem([p['name'], str(p['index'])])
            item.setData(0, Qt.UserRole, p['name'])
            self._items[p['name']] = item
            parent_name = p.get('parent')
            if parent_name and parent_name in self._items:
                self._items[parent_name].addChild(item)
            else:
                self.addTopLevelItem(item)
        self.expandAll()

    def highlight_part(self, name: str, color: QColor = QColor(255, 200, 0)):
        for n, item in self._items.items():
            item.setBackground(0, QBrush(
                color if n == name else QColor(255, 255, 255)
            ))

    def _on_item_clicked(self, item, col):
        name = item.data(0, Qt.UserRole)
        if name:
            self.part_selected.emit(name)
