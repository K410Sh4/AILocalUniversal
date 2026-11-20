"""NeuralMap visual graph editor (PySide6 / QGraphicsScene)."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QMimeData, QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QPainter,
    QPainterPath,
    QPen,
    QUndoCommand,
    QUndoStack,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QGraphicsEllipseItem,
    QGraphicsObject,
    QGraphicsPathItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QInputDialog,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from workflows.graph import (
    NODE_SPECS,
    EdgeType,
    GraphEdge,
    GraphError,
    GraphNode,
    WorkflowGraph,
    validate_graph,
)
from workflows.package_io import (
    GRAPH_PATH,
    load_graph_from_package,
    save_graph_to_package,
)


NODE_LABELS = {
    "input.text": "Entrada de texto",
    "input.attachment": "Anexo",
    "specialist.code": "Especialista de código",
    "specialist.chat": "Especialista de conversa",
    "specialist.image": "Especialista de imagem",
    "specialist.review": "Revisor",
    "control.loop": "Loop controlado",
    "filter.context": "Filtro de contexto",
    "hardware.profile": "Perfil de hardware",
    "merge.outputs": "Combinar saídas",
    "output.response": "Resposta final",
    "output.trace": "Rastro de execução",
}

CATEGORY_COLORS = {
    "input": QColor("#315b78"),
    "specialist": QColor("#62508b"),
    "control": QColor("#90602f"),
    "filter": QColor("#376f62"),
    "hardware": QColor("#7a5936"),
    "output": QColor("#3c6d42"),
}


class GraphSnapshotCommand(QUndoCommand):
    def __init__(self, view: NeuralMapView, before: str, after: str, text: str) -> None:
        super().__init__(text)
        self.view = view
        self.before = before
        self.after = after

    def undo(self) -> None:
        self.view._restore_snapshot(self.before)

    def redo(self) -> None:
        self.view._restore_snapshot(self.after)


class PortItem(QGraphicsEllipseItem):
    def __init__(
        self,
        parent: NodeGraphicsItem,
        canvas: GraphCanvas,
        node_id: str,
        port_name: str,
        direction: str,
    ) -> None:
        super().__init__(-5, -5, 10, 10, parent)
        self.canvas = canvas
        self.node_id = node_id
        self.port_name = port_name
        self.direction = direction
        self.setBrush(QBrush(QColor("#e8edf2")))
        self.setPen(QPen(QColor("#18212a"), 1.2))
        self.setZValue(4)
        self.setAcceptHoverEvents(True)
        self.setToolTip(f"{direction}: {port_name}")

    def hoverEnterEvent(self, event) -> None:
        self.setBrush(QBrush(QColor("#70d7bd")))
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:
        self.setBrush(QBrush(QColor("#e8edf2")))
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if self.direction == "out" and event.button() == Qt.MouseButton.LeftButton:
            self.canvas.begin_connection(self)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self.canvas.pending_port is self:
            self.canvas.update_pending_connection(event.scenePos())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self.canvas.pending_port is self:
            self.canvas.finish_connection(event.scenePos())
            event.accept()
            return
        super().mouseReleaseEvent(event)


class NodeGraphicsItem(QGraphicsObject):
    WIDTH = 220

    def __init__(self, node: GraphNode, canvas: GraphCanvas) -> None:
        super().__init__()
        self.node = node
        self.canvas = canvas
        spec = NODE_SPECS[node.node_type]
        self.inputs = sorted(spec.inputs)
        self.outputs = sorted(spec.outputs)
        self.height = max(100, 56 + max(len(self.inputs), len(self.outputs), 1) * 22)
        self.input_ports: dict[str, PortItem] = {}
        self.output_ports: dict[str, PortItem] = {}
        self._press_position = QPointF()
        self.setFlags(
            QGraphicsObject.GraphicsItemFlag.ItemIsMovable
            | QGraphicsObject.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsObject.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setCacheMode(QGraphicsObject.CacheMode.DeviceCoordinateCache)

        for index, port in enumerate(self.inputs):
            y = 58 + index * 22
            item = PortItem(self, canvas, node.node_id, port, "in")
            item.setPos(0, y)
            self.input_ports[port] = item
            label = self._text(port, 12, y - 8)
            label.setBrush(QBrush(QColor("#cbd5e1")))

        for index, port in enumerate(self.outputs):
            y = 58 + index * 22
            item = PortItem(self, canvas, node.node_id, port, "out")
            item.setPos(self.WIDTH, y)
            self.output_ports[port] = item
            label = self._text(port, self.WIDTH - 86, y - 8)
            label.setBrush(QBrush(QColor("#cbd5e1")))

        self.setPos(node.position["x"], node.position["y"])

    def _text(self, value: str, x: float, y: float):
        from PySide6.QtWidgets import QGraphicsSimpleTextItem

        text = QGraphicsSimpleTextItem(value, self)
        text.setBrush(QBrush(QColor("#d8e0e8")))
        text.setPos(x, y)
        text.setFont(self.canvas.port_font)
        return text

    def boundingRect(self) -> QRectF:
        return QRectF(-8, -6, self.WIDTH + 16, self.height + 12)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        spec = NODE_SPECS[self.node.node_type]
        color = CATEGORY_COLORS.get(spec.category, QColor("#45515e"))
        if not self.node.enabled:
            color = QColor("#4b5563")
        outline = QColor("#8be0c5") if self.isSelected() else QColor("#1d2935")
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(outline, 2 if self.isSelected() else 1))
        painter.setBrush(QBrush(color))
        painter.drawRoundedRect(QRectF(0, 0, self.WIDTH, self.height), 10, 10)
        painter.setPen(QPen(QColor("#ffffff")))
        painter.setFont(self.canvas.title_font)
        painter.drawText(QRectF(14, 10, self.WIDTH - 28, 22), Qt.AlignmentFlag.AlignLeft, self.node.label)
        painter.setPen(QPen(QColor("#e3eaf0")))
        painter.setFont(self.canvas.port_font)
        painter.drawText(
            QRectF(14, 34, self.WIDTH - 28, 16),
            Qt.AlignmentFlag.AlignLeft,
            self.node.node_type,
        )
        if not self.node.enabled:
            painter.setPen(QPen(QColor("#facc15")))
            painter.drawText(
                QRectF(14, self.height - 22, self.WIDTH - 28, 16),
                Qt.AlignmentFlag.AlignLeft,
                "DESABILITADO",
            )

    def itemChange(self, change, value):
        result = super().itemChange(change, value)
        if change == QGraphicsObject.GraphicsItemChange.ItemPositionHasChanged:
            self.canvas.refresh_connection_paths()
        return result

    def mousePressEvent(self, event) -> None:
        self._press_position = QPointF(self.pos())
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        super().mouseReleaseEvent(event)
        current = QPointF(self.pos())
        if current != self._press_position:
            self.canvas.node_moved.emit(
                self.node.node_id,
                self._press_position,
                current,
            )


class ConnectionGraphicsItem(QGraphicsPathItem):
    def __init__(self, edge: GraphEdge, source: PortItem, target: PortItem) -> None:
        super().__init__()
        self.edge = edge
        self.source_port = source
        self.target_port = target
        color = {
            EdgeType.ALWAYS: QColor("#9ca3af"),
            EdgeType.ON_SUCCESS: QColor("#55c58a"),
            EdgeType.ON_FAILURE: QColor("#e4a45f"),
        }[edge.edge_type]
        self.setPen(QPen(color, 2.0, Qt.PenStyle.SolidLine))
        self.setZValue(-2)
        self.update_path()

    def update_path(self, target_position: QPointF | None = None) -> None:
        start = self.source_port.scenePos()
        end = target_position or self.target_port.scenePos()
        delta = max(48.0, abs(end.x() - start.x()) * 0.45)
        path = QPainterPath(start)
        path.cubicTo(
            QPointF(start.x() + delta, start.y()),
            QPointF(end.x() - delta, end.y()),
            end,
        )
        self.setPath(path)


class NodeLibraryList(QListWidget):
    NODE_MIME = "application/x-ailocal-neuralmap-node"

    def __init__(self) -> None:
        super().__init__()
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        self.setDefaultDropAction(Qt.DropAction.CopyAction)
        for node_type, label in NODE_LABELS.items():
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, node_type)
            self.addItem(item)

    def mimeData(self, items: list[QListWidgetItem]) -> QMimeData:
        mime = QMimeData()
        if items:
            node_type = str(items[0].data(Qt.ItemDataRole.UserRole))
            mime.setData(self.NODE_MIME, node_type.encode("utf-8"))
            mime.setText(node_type)
        return mime

    def supportedDropActions(self):
        return Qt.DropAction.CopyAction


class GraphCanvas(QGraphicsView):
    node_selected = Signal(str)
    node_moved = Signal(str, QPointF, QPointF)
    connection_requested = Signal(str, str, str, str)
    node_dropped = Signal(str, QPointF)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.graph_scene = QGraphicsScene(self)
        self.setScene(self.graph_scene)
        self.graph_scene.selectionChanged.connect(self._selection_changed)
        self.setSceneRect(-6000, -6000, 12000, 12000)
        self.setRenderHints(
            QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.TextAntialiasing
            | QPainter.RenderHint.SmoothPixmapTransform
        )
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.BoundingRectViewportUpdate)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setAcceptDrops(True)
        self.grid_visible = True
        self.pending_port: PortItem | None = None
        self.pending_path: QGraphicsPathItem | None = None
        self.node_items: dict[str, NodeGraphicsItem] = {}
        self._panning = False
        self._pan_position = QPoint()
        self.connection_items: list[ConnectionGraphicsItem] = []
        self.title_font = self.font()
        self.title_font.setBold(True)
        self.title_font.setPointSize(9)
        self.port_font = self.font()
        self.port_font.setPointSize(8)
        self.port_font.setBold(False)

    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:
        painter.fillRect(rect, QColor("#101820"))
        if not self.grid_visible:
            return
        grid = 24
        left = int(rect.left()) - (int(rect.left()) % grid)
        top = int(rect.top()) - (int(rect.top()) % grid)
        lines = []
        x = left
        while x < rect.right():
            lines.append((x, rect.top(), x, rect.bottom()))
            x += grid
        y = top
        while y < rect.bottom():
            lines.append((rect.left(), y, rect.right(), y))
            y += grid
        pen = QPen(QColor("#243240"), 0.7)
        painter.setPen(pen)
        from PySide6.QtCore import QLineF

        painter.drawLines([QLineF(*line) for line in lines])

    def wheelEvent(self, event) -> None:
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        current = self.transform().m11()
        if 0.25 <= current * factor <= 2.5:
            self.scale(factor, factor)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasFormat(NodeLibraryList.NODE_MIME):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasFormat(NodeLibraryList.NODE_MIME):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:
        if event.mimeData().hasFormat(NodeLibraryList.NODE_MIME):
            node_type = bytes(event.mimeData().data(NodeLibraryList.NODE_MIME)).decode("utf-8")
            self.node_dropped.emit(node_type, self.mapToScene(event.position().toPoint()))
            event.acceptProposedAction()
        else:
            super().dropEvent(event)

    def load_graph(self, graph: WorkflowGraph) -> None:
        self.graph_scene.clear()
        self.node_items.clear()
        self.connection_items.clear()
        self.pending_port = None
        self.pending_path = None

        for node in graph.nodes:
            item = NodeGraphicsItem(node, self)
            self.graph_scene.addItem(item)
            self.node_items[node.node_id] = item
            item.setVisible(True)

        for edge in graph.edges:
            source_node = self.node_items.get(edge.source)
            target_node = self.node_items.get(edge.target)
            if not source_node or not target_node:
                continue
            source = source_node.output_ports.get(edge.source_port)
            target = target_node.input_ports.get(edge.target_port)
            if source and target:
                connection = ConnectionGraphicsItem(edge, source, target)
                self.graph_scene.addItem(connection)
                self.connection_items.append(connection)
        self.refresh_connection_paths()

    def refresh_connection_paths(self) -> None:
        for connection in self.connection_items:
            connection.update_path()

    def begin_connection(self, source: PortItem) -> None:
        self.pending_port = source
        self.pending_path = QGraphicsPathItem()
        self.pending_path.setPen(QPen(QColor("#70d7bd"), 2, Qt.PenStyle.DashLine))
        self.pending_path.setZValue(-1)
        self.graph_scene.addItem(self.pending_path)

    def update_pending_connection(self, point: QPointF) -> None:
        if self.pending_port is None or self.pending_path is None:
            return
        start = self.pending_port.scenePos()
        delta = max(48.0, abs(point.x() - start.x()) * 0.45)
        path = QPainterPath(start)
        path.cubicTo(
            QPointF(start.x() + delta, start.y()),
            QPointF(point.x() - delta, point.y()),
            point,
        )
        self.pending_path.setPath(path)

    def _port_at(self, point: QPointF) -> PortItem | None:
        for item in self.graph_scene.items(point):
            if isinstance(item, PortItem):
                return item
        return None

    def finish_connection(self, point: QPointF) -> None:
        source = self.pending_port
        target = self._port_at(point)
        if self.pending_path is not None:
            self.graph_scene.removeItem(self.pending_path)
        self.pending_port = None
        self.pending_path = None
        if (
            source is not None
            and target is not None
            and target.direction == "in"
            and source.node_id != target.node_id
        ):
            self.connection_requested.emit(
                source.node_id,
                source.port_name,
                target.node_id,
                target.port_name,
            )

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = True
            self._pan_position = event.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.MiddleButton and self._panning:
            self._panning = False
            self.unsetCursor()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._panning:
            current = event.position().toPoint()
            delta = current - self._pan_position
            self._pan_position = current
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - delta.x()
            )
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - delta.y()
            )
            event.accept()
            return
        if self.pending_port is not None:
            self.update_pending_connection(self.mapToScene(event.position().toPoint()))
        super().mouseMoveEvent(event)

    def _selection_changed(self) -> None:
        selected = next(
            (
                item for item in self.graph_scene.selectedItems()
                if isinstance(item, NodeGraphicsItem)
            ),
            None,
        )
        self.node_selected.emit(selected.node.node_id if selected else "")


class NeuralMapView(QWidget):
    dry_run_requested = Signal()
    execute_requested = Signal()
    graph_changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.graph = WorkflowGraph(
            graph_id="new-workflow",
            name="Novo NeuralMap",
            description="",
            nodes=[
                GraphNode.create(
                    "input",
                    "input.text",
                    label="Entrada do usuário",
                    position=(80, 180),
                ),
                GraphNode.create(
                    "response",
                    "output.response",
                    label="Resposta final",
                    position=(520, 180),
                ),
            ],
            edges=[],
        )
        self.package_path: Path | None = None
        self.undo_stack = QUndoStack(self)
        self._counter = 0
        self._build_ui()
        self._wire_events()
        self.canvas.load_graph(self.graph)
        self._set_validation_status()

    def _build_ui(self) -> None:
        toolbar = QHBoxLayout()
        self.new_button = QPushButton("Novo")
        self.open_button = QPushButton("Abrir")
        self.save_package_button = QPushButton("Salvar no pacote")
        self.save_json_button = QPushButton("Salvar JSON")
        self.template_button = QPushButton("Aplicar template")
        self.validate_button = QPushButton("Validar")
        self.dry_run_button = QPushButton("Executar · dry-run")
        self.execute_button = QPushButton("Executar real")
        self.clear_button = QPushButton("Limpar")
        self.grid_button = QToolButton()
        self.grid_button.setText("Grade")
        self.grid_button.setCheckable(True)
        self.grid_button.setChecked(True)
        self.undo_button = self.undo_stack.createUndoAction(self, "Desfazer")
        self.redo_button = self.undo_stack.createRedoAction(self, "Refazer")
        for widget in (
            self.new_button,
            self.open_button,
            self.save_package_button,
            self.save_json_button,
            self.template_button,
            self.validate_button,
            self.dry_run_button,
            self.execute_button,
            self.undo_button,
            self.redo_button,
            self.clear_button,
            self.grid_button,
        ):
            toolbar.addWidget(widget)

        self.library = NodeLibraryList()
        self.canvas = GraphCanvas()
        self.canvas.setMinimumSize(560, 400)

        self.node_title = QLineEdit()
        self.node_enabled = QCheckBox("Nó habilitado")
        self.config_editor = QPlainTextEdit()
        self.config_editor.setPlaceholderText("Configuração JSON do nó selecionado")
        self.config_editor.setMinimumHeight(210)
        self.apply_properties_button = QPushButton("Aplicar propriedades")
        self.validation_details = QLabel("Valide o mapa para conferir conexões.")
        self.validation_details.setWordWrap(True)
        self.resource_status = QLabel("Hardware: automático · Proteção: protected")
        self.resource_status.setWordWrap(True)

        properties = QWidget()
        props_layout = QVBoxLayout(properties)
        props_layout.addWidget(QLabel("Propriedades do nó"))
        props_form = QFormLayout()
        props_form.addRow("Rótulo", self.node_title)
        props_form.addRow("", self.node_enabled)
        props_layout.addLayout(props_form)
        props_layout.addWidget(QLabel("Configuração"))
        props_layout.addWidget(self.config_editor)
        props_layout.addWidget(self.apply_properties_button)
        props_layout.addWidget(QLabel("Validação do grafo"))
        props_layout.addWidget(self.validation_details)
        props_layout.addStretch(1)
        props_layout.addWidget(self.resource_status)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(QLabel("Biblioteca de nós · arraste para o canvas"))
        left_layout.addWidget(self.library)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left)
        splitter.addWidget(self.canvas)
        splitter.addWidget(properties)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([190, 760, 300])

        layout = QVBoxLayout(self)
        layout.addLayout(toolbar)
        layout.addWidget(splitter)

    def _wire_events(self) -> None:
        self.new_button.clicked.connect(self.new_graph)
        self.open_button.clicked.connect(self.open_graph)
        self.save_package_button.clicked.connect(self.save_in_package)
        self.save_json_button.clicked.connect(self.save_json)
        self.template_button.clicked.connect(self.apply_template)
        self.validate_button.clicked.connect(self.validate_current_graph)
        self.dry_run_button.clicked.connect(self.dry_run_requested.emit)
        self.execute_button.clicked.connect(self.execute_requested.emit)
        self.clear_button.clicked.connect(self.clear_graph)
        self.grid_button.toggled.connect(self.canvas_grid_changed)
        self.library.itemDoubleClicked.connect(self._library_double_click)
        self.canvas.node_selected.connect(self._select_node)
        self.canvas.node_dropped.connect(self._drop_node)
        self.canvas.connection_requested.connect(self._connect_nodes)
        self.canvas.node_moved.connect(self._node_moved)
        self.apply_properties_button.clicked.connect(self.apply_node_properties)

    def set_hardware_status(self, profile: str, protection_mode: str) -> None:
        self.resource_status.setText(
            f"Perfil de hardware: {profile} · Proteção: {protection_mode}"
        )

    def _snapshot(self) -> str:
        return json.dumps(self.graph.to_dict(), ensure_ascii=False)

    def _push_snapshot(self, before: str, label: str) -> None:
        after = self._snapshot()
        if before != after:
            self.undo_stack.push(GraphSnapshotCommand(self, before, after, label))
            self.graph_changed.emit()
            self._set_validation_status()

    def _restore_snapshot(self, serialized: str) -> None:
        data = json.loads(serialized)
        self.graph = WorkflowGraph.from_dict(data, validate=False)
        self.canvas.load_graph(self.graph)
        self._select_node("")
        self.graph_changed.emit()
        self._set_validation_status()

    def _set_validation_status(self) -> None:
        try:
            validate_graph(self.graph)
        except GraphError as exc:
            self.validation_details.setText(
                f"Inválido · {exc.reason_code}: {exc.message}"
            )
            return
        self.validation_details.setText("Válido · grafo sem ciclos não controlados.")

    def validate_current_graph(self) -> bool:
        try:
            validate_graph(self.graph)
        except GraphError as exc:
            details = exc.message
            if exc.alternatives:
                details += "\n\nAlternativas:\n" + "\n".join(
                    f"• {item}" for item in exc.alternatives
                )
            self.validation_details.setText(
                f"Inválido · {exc.reason_code}: {exc.message}"
            )
            QMessageBox.warning(self, "NeuralMap inválido", details)
            return False
        self.validation_details.setText("Válido · pronto para execução.")
        return True

    def _make_node(self, node_type: str, point: QPointF) -> None:
        self._counter += 1
        base = node_type.replace(".", "_")
        node_id = f"{base}_{self._counter}"
        before = self._snapshot()
        node = GraphNode.create(
            node_id,
            node_type,
            label=NODE_LABELS.get(node_type, node_type),
            position=(point.x(), point.y()),
        )
        self.graph.nodes.append(node)
        after = self._snapshot()
        self.undo_stack.push(
            GraphSnapshotCommand(self, before, after, f"Adicionar {node.label}")
        )
        self.graph_changed.emit()

    def _library_double_click(self, item: QListWidgetItem) -> None:
        node_type = str(item.data(Qt.ItemDataRole.UserRole))
        point = self.canvas.mapToScene(self.canvas.viewport().rect().center())
        self._make_node(node_type, point)

    def _drop_node(self, node_type: str, point: QPointF) -> None:
        self._make_node(node_type, point)

    def _connect_nodes(
        self,
        source: str,
        source_port: str,
        target: str,
        target_port: str,
    ) -> None:
        before = self._snapshot()
        choices = ["Sempre", "Ao sucesso", "Ao falhar"]
        selected, accepted = QInputDialog.getItem(
            self,
            "Tipo de conexão",
            "Quando esta conexão deve ser percorrida?",
            choices,
            0,
            False,
        )
        if not accepted:
            return
        edge_type = {
            "Sempre": EdgeType.ALWAYS,
            "Ao sucesso": EdgeType.ON_SUCCESS,
            "Ao falhar": EdgeType.ON_FAILURE,
        }[selected]
        edge = GraphEdge(
            edge_id=f"edge_{uuid4().hex[:12]}",
            source=source,
            source_port=source_port,
            target=target,
            target_port=target_port,
            edge_type=edge_type,
        )
        self.graph.edges.append(edge)
        self.undo_stack.push(
            GraphSnapshotCommand(
                self,
                before,
                self._snapshot(),
                f"Conectar {source}.{source_port} → {target}.{target_port}",
            )
        )
        self.graph_changed.emit()

    def _node_moved(self, node_id: str, old_position: QPointF, new_position: QPointF) -> None:
        node = next((item for item in self.graph.nodes if item.node_id == node_id), None)
        if node is None:
            return
        before = self._snapshot()
        node.position = {"x": old_position.x(), "y": old_position.y()}
        before = self._snapshot()
        node.position = {"x": new_position.x(), "y": new_position.y()}
        self._push_snapshot(before, f"Mover {node.label}")

    def _select_node(self, node_id: str) -> None:
        node = next((item for item in self.graph.nodes if item.node_id == node_id), None)
        if node is None:
            self.node_title.clear()
            self.node_enabled.setChecked(False)
            self.config_editor.clear()
            return
        self.node_title.setText(node.label)
        self.node_enabled.setChecked(node.enabled)
        self.config_editor.setPlainText(
            json.dumps(node.config, ensure_ascii=False, indent=2)
        )

    def apply_node_properties(self) -> None:
        selected = self.canvas.graph_scene.selectedItems()
        node_item = next(
            (item for item in selected if isinstance(item, NodeGraphicsItem)),
            None,
        )
        if node_item is None:
            QMessageBox.information(self, "NeuralMap", "Selecione um nó no canvas.")
            return
        try:
            config = json.loads(self.config_editor.toPlainText() or "{}")
            if not isinstance(config, dict):
                raise ValueError("A configuração precisa ser um objeto JSON.")
        except (json.JSONDecodeError, ValueError) as exc:
            QMessageBox.warning(self, "Configuração inválida", str(exc))
            return

        before = self._snapshot()
        node = next(item for item in self.graph.nodes if item.node_id == node_item.node.node_id)
        node.label = self.node_title.text().strip() or node.node_type
        node.enabled = self.node_enabled.isChecked()
        node.config = config
        after = self._snapshot()
        try:
            WorkflowGraph.from_dict(json.loads(after), validate=False)
        except GraphError as exc:
            self.graph = WorkflowGraph.from_dict(json.loads(before))
            self.canvas.load_graph(self.graph)
            QMessageBox.warning(
                self,
                "Propriedades inválidas",
                f"{exc.reason_code}: {exc.message}",
            )
            return
        self.undo_stack.push(
            GraphSnapshotCommand(self, before, after, f"Editar {node.label}")
        )

    def canvas_grid_changed(self, visible: bool) -> None:
        self.canvas.grid_visible = visible
        self.canvas.viewport().update()

    def new_graph(self) -> None:
        before = self._snapshot()
        self.graph = WorkflowGraph(
            graph_id=f"workflow-{uuid4().hex[:8]}",
            name="Novo NeuralMap",
            nodes=[
                GraphNode.create(
                    "input", "input.text", label="Entrada do usuário", position=(100, 180)
                ),
                GraphNode.create(
                    "response", "output.response", label="Resposta final", position=(520, 180)
                ),
            ],
            edges=[],
        )
        self.package_path = None
        self.undo_stack.push(
            GraphSnapshotCommand(self, before, self._snapshot(), "Novo NeuralMap")
        )

    def clear_graph(self) -> None:
        if QMessageBox.question(
            self,
            "Limpar NeuralMap",
            "Remover todos os nós e conexões do mapa atual?",
        ) != QMessageBox.StandardButton.Yes:
            return
        before = self._snapshot()
        self.graph.nodes = []
        self.graph.edges = []
        self.undo_stack.push(
            GraphSnapshotCommand(self, before, self._snapshot(), "Limpar NeuralMap")
        )

    def apply_template(self) -> None:
        root = Path(__file__).resolve().parents[2]
        template_path = root / "examples" / "workflows" / "multi_specialist.pipeline.graph.json"
        try:
            graph = WorkflowGraph.load(template_path)
        except GraphError as exc:
            QMessageBox.warning(self, "Template indisponível", exc.message)
            return
        before = self._snapshot()
        self.graph = graph
        self.package_path = None
        self.undo_stack.push(
            GraphSnapshotCommand(self, before, self._snapshot(), "Aplicar fluxo multi-especialista")
        )

    def open_graph(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Abrir NeuralMap",
            "",
            "NeuralMap e pacotes (*.pipeline.graph.json *.json *.neuralinjector)",
        )
        if not path:
            return
        try:
            if path.lower().endswith(".neuralinjector"):
                graph = load_graph_from_package(path)
                self.package_path = Path(path)
            else:
                graph = WorkflowGraph.load(path)
                self.package_path = None
        except GraphError as exc:
            QMessageBox.warning(self, "Falha ao abrir NeuralMap", f"{exc.reason_code}: {exc.message}")
            return
        before = self._snapshot()
        self.graph = graph
        self.undo_stack.push(
            GraphSnapshotCommand(self, before, self._snapshot(), "Abrir NeuralMap")
        )

    def save_json(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Salvar NeuralMap JSON",
            f"{self.graph.graph_id}.pipeline.graph.json",
            "NeuralMap (*.pipeline.graph.json *.json)",
        )
        if not path:
            return
        try:
            self.graph.save(path)
        except GraphError as exc:
            QMessageBox.warning(self, "Falha ao salvar", f"{exc.reason_code}: {exc.message}")
            return
        self.validation_details.setText(f"Mapa salvo em {path}")

    def save_in_package(self) -> None:
        path = str(self.package_path) if self.package_path else ""
        if not path:
            path, _ = QFileDialog.getOpenFileName(
                self,
                "Selecionar pacote NeuralInjector",
                "",
                "NeuralInjector (*.neuralinjector)",
            )
        if not path:
            return
        try:
            saved = save_graph_to_package(path, self.graph)
            self.package_path = saved
        except GraphError as exc:
            QMessageBox.warning(
                self,
                "Não foi possível salvar no pacote",
                f"{exc.reason_code}: {exc.message}",
            )
            return
        self.validation_details.setText(
            f"NeuralMap salvo em {saved.name} · {GRAPH_PATH}"
        )
