"""Sostituto minimale di PySide6 per eseguire la logica della GUI senza Qt.

Non verifica l'aspetto della finestra né l'API reale di Qt: serve a far girare
tutto il codice Python della GUI (callback, flussi di dati, grafici matplotlib
veri su canvas Agg) e a trovare errori di logica. Va installato in sys.modules
prima di importare flight_analyzer.gui.
"""

from __future__ import annotations

import sys
import types

from matplotlib.backends.backend_agg import FigureCanvasAgg


# ------------------------------------------------------------------- segnali
class _BoundSignal:
    def __init__(self):
        self._slots = []

    def connect(self, fn):
        self._slots.append(fn)

    def disconnect(self, *a):
        self._slots.clear()

    def emit(self, *args):
        for fn in list(self._slots):
            fn(*args)

    def __call__(self, *a, **k):  # usato come metodo generico
        return _Any()


class Signal:
    def __init__(self, *types_):
        self.name = None

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, obj, owner=None):
        if obj is None:
            return self
        key = "_sig_" + self.name
        if key not in obj.__dict__:
            obj.__dict__[key] = _BoundSignal()
        return obj.__dict__[key]


def Slot(*a, **k):
    return lambda fn: fn


# --------------------------------------------------------------------- enum
class _Enum:
    def __init__(self, name):
        self.name = name

    def __getattr__(self, item):
        if item.startswith("__"):
            raise AttributeError(item)
        return _Enum(f"{self.name}.{item}")

    def __or__(self, other):
        return _Enum(f"{self.name}|{getattr(other, 'name', other)}")

    __ror__ = __or__

    def __and__(self, other):
        return self

    def __invert__(self):
        return self

    def __eq__(self, other):
        return isinstance(other, _Enum) and other.name == self.name

    def __hash__(self):
        return hash(self.name)

    def __repr__(self):
        return f"<enum {self.name}>"


class _Meta(type):
    def __getattr__(cls, item):
        if item.startswith("__"):
            raise AttributeError(item)
        return _Enum(f"{cls.__name__}.{item}")


# -------------------------------------------------------------------- generico
class _Any:
    """Oggetto che accetta qualunque chiamata/attributo."""

    def __init__(self, *a, **k):
        pass

    def __getattr__(self, item):
        if item.startswith("__"):
            raise AttributeError(item)
        if item.startswith("_sig_"):
            raise AttributeError(item)
        sig = _BoundSignal()
        object.__setattr__(self, item, sig)
        return sig

    def __call__(self, *a, **k):
        return _Any()

    def __bool__(self):
        return True


class Stub(metaclass=_Meta):
    def __init__(self, *a, **k):
        self._visible = True

    def __getattr__(self, item):
        if item.startswith("_"):
            raise AttributeError(item)
        sig = _BoundSignal()
        object.__setattr__(self, item, sig)
        return sig

    def isVisible(self):
        return getattr(self, "_visible", True)

    def setVisible(self, v):
        self._visible = bool(v)


# ------------------------------------------------------------------- QtCore
class QObject(Stub):
    pass


class QRunnable(Stub):
    pass


class QThreadPool(Stub):
    _inst = None

    @classmethod
    def globalInstance(cls):
        cls._inst = cls._inst or cls()
        return cls._inst

    def start(self, task):
        task.run()


class QTimer(Stub):
    timeout = Signal()

    def __init__(self, *a, **k):
        super().__init__()
        self._active = False

    def start(self, *a):
        self.timeout.emit()

    def isActive(self):
        return False

    @staticmethod
    def singleShot(ms, fn):
        fn()


class QSettings(Stub):
    store = {}

    def value(self, key, default=None, type=None):  # noqa: A002 - stessa firma di Qt
        v = self.store.get(key, default)
        if type is bool and isinstance(v, str):
            return v.lower() in ("1", "true")
        return v

    def setValue(self, key, value):
        self.store[key] = value

    def remove(self, key):
        self.store.pop(key, None)


class QSortFilterProxyModel(Stub):
    def mapFromSource(self, idx):
        return idx


class QUrl(Stub):
    @staticmethod
    def fromLocalFile(p):
        return p


class Qt(metaclass=_Meta):
    pass


class QProcess(Stub):
    started = []

    @classmethod
    def startDetached(cls, program, args=()):
        cls.started.append((program, list(args)))
        return True


class QStandardPaths(Stub):
    @staticmethod
    def writableLocation(*a):
        return ""


# -------------------------------------------------------------------- QtGui
class QAction(Stub):
    triggered = Signal()


class QKeySequence(Stub):
    pass


class QColor(Stub):
    pass


class QBrush(Stub):
    pass


class QFont(Stub):
    pass


class QDesktopServices(Stub):
    opened = []

    @classmethod
    def openUrl(cls, url):
        cls.opened.append(url)


class _Index:
    def __init__(self, row):
        self._row = row

    def row(self):
        return self._row


class QStandardItem(Stub):
    def __init__(self, text=""):
        super().__init__()
        self._text = text


class QStandardItemModel(Stub):
    def __init__(self, *a):
        super().__init__()
        self.rows = []

    def appendRow(self, items):
        self.rows.append(items)

    def rowCount(self):
        return len(self.rows)

    def removeRows(self, start, n):
        del self.rows[start:start + n]

    def index(self, row, col):
        return _Index(row)


# ---------------------------------------------------------------- QtWidgets
class QWidget(Stub):
    def isHidden(self):
        return getattr(self, "_hidden_flag", False)

    def setHidden(self, h):
        self._hidden_flag = bool(h)

    def width(self):
        return 1400

    def height(self):
        return 900


class QApplication(Stub):
    _inst = None

    def __init__(self, *a):
        super().__init__()
        QApplication._inst = self

    @classmethod
    def instance(cls):
        return cls._inst

    @staticmethod
    def setOverrideCursor(*a):
        pass

    @staticmethod
    def restoreOverrideCursor(*a):
        pass

    @staticmethod
    def quit():
        pass

    def exec(self):
        return 0


class _StatusBar(Stub):
    def __init__(self):
        super().__init__()
        self.last = ""

    def showMessage(self, text, *a):
        self.last = text

    def clearMessage(self):
        self.last = ""


class QMenu(Stub):
    def __init__(self, *a):
        super().__init__()
        self.actions = []

    def addAction(self, a):
        act = a if isinstance(a, QAction) else QAction(a)
        self.actions.append(act)
        return act

    def addMenu(self, name):
        m = QMenu(name)
        self.actions.append(m)
        return m

    def clear(self):
        self.actions = []


class _MenuBar(Stub):
    def __init__(self):
        super().__init__()
        self.menus = []

    def addMenu(self, name):
        m = QMenu(name)
        self.menus.append(m)
        return m


class QMainWindow(QWidget):
    def menuBar(self):
        if "_mb" not in self.__dict__:
            self._mb = _MenuBar()
        return self._mb

    def statusBar(self):
        if "_sb" not in self.__dict__:
            self._sb = _StatusBar()
        return self._sb

    def addToolBar(self, *a):
        return QMenu()


class QLabel(QWidget):
    def __init__(self, text="", *a):
        super().__init__()
        self._text = text

    def setText(self, t):
        self._text = t

    def text(self):
        return self._text


class QPushButton(QWidget):
    clicked = Signal()


class QCheckBox(QWidget):
    toggled = Signal(bool)

    def __init__(self, *a):
        super().__init__()
        self._on = False

    def isChecked(self):
        return self._on

    def setChecked(self, v):
        self._on = bool(v)
        self.toggled.emit(self._on)


class QLineEdit(QWidget):
    textChanged = Signal(str)

    def __init__(self, text="", *a):
        super().__init__()
        self._text = text

    def text(self):
        return self._text

    def setText(self, t):
        self._text = t
        self.textChanged.emit(t)


class QComboBox(QWidget):
    currentIndexChanged = Signal(int)

    def __init__(self, *a):
        super().__init__()
        self.items = []
        self._idx = -1

    def addItem(self, text, data=None):
        self.items.append((text, data))
        if self._idx < 0:
            self._idx = 0

    def currentIndex(self):
        return self._idx

    def setCurrentIndex(self, i):
        self._idx = i
        self.currentIndexChanged.emit(i)

    def currentData(self):
        return self.items[self._idx][1] if self._idx >= 0 else None

    def currentText(self):
        return self.items[self._idx][0] if self._idx >= 0 else ""

    def count(self):
        return len(self.items)

    def clear(self):
        self.items = []
        self._idx = -1

    def itemData(self, i):
        return self.items[i][1]

    def findData(self, data):
        for i, (_t, d) in enumerate(self.items):
            if d == data:
                return i
        return -1

    def itemText(self, i):
        return self.items[i][0]


class QTabWidget(QWidget):
    currentChanged = Signal(int)

    def __init__(self, *a):
        super().__init__()
        self.pages = []
        self._idx = -1

    def addTab(self, w, name):
        self.pages.append((w, name))
        if self._idx < 0:
            self._idx = 0
        return len(self.pages) - 1

    def currentWidget(self):
        return self.pages[self._idx][0] if self._idx >= 0 else None

    def currentIndex(self):
        return self._idx

    def setCurrentIndex(self, i):
        self._idx = i
        self.currentChanged.emit(i)

    def setCurrentWidget(self, w):
        for i, (p, _) in enumerate(self.pages):
            if p is w:
                self.setCurrentIndex(i)

    def count(self):
        return len(self.pages)

    def removeTab(self, i):
        del self.pages[i]
        if self._idx >= len(self.pages):
            self._idx = len(self.pages) - 1

    def indexOf(self, w):
        for i, (p, _) in enumerate(self.pages):
            if p is w:
                return i
        return -1

    def tabText(self, i):
        return self.pages[i][1]

    def widget(self, i):
        return self.pages[i][0]


class QTableWidgetItem(Stub):
    def __init__(self, text=""):
        super().__init__()
        self._text = text
        self._data = {}

    def text(self):
        return self._text

    def setText(self, t):
        self._text = t

    def flags(self):
        return _Enum("flags")

    def setData(self, role, v):
        self._data[role] = v

    def data(self, role):
        return self._data.get(role)


class _SelectionModel:
    def __init__(self, table):
        self.table = table

    def selectedRows(self):
        r = getattr(self.table, "_sel", None)
        return [] if r is None else [_Index(r)]


class QTableWidget(QWidget):
    cellDoubleClicked = Signal(int, int)
    itemSelectionChanged = Signal()

    def selectRow(self, r):
        self._sel = r
        self.itemSelectionChanged.emit()

    def selectionModel(self):
        return _SelectionModel(self)

    def __init__(self, rows=0, cols=0, *a):
        super().__init__()
        self._rows = rows
        self.cells = {}

    def setRowCount(self, n):
        self._rows = n

    def rowCount(self):
        return self._rows

    def setItem(self, r, c, item):
        self.cells[(r, c)] = item

    def item(self, r, c):
        return self.cells.get((r, c))


class QTreeWidgetItem(Stub):
    def __init__(self, texts=None):
        super().__init__()
        self.texts = list(texts or [])
        self.children = []
        self._check = {}
        self._data = {}
        self._hidden = False

    def addChild(self, it):
        self.children.append(it)

    def childCount(self):
        return len(self.children)

    def child(self, j):
        return self.children[j]

    def text(self, col):
        return self.texts[col] if col < len(self.texts) else ""

    def flags(self):
        return _Enum("flags")

    def setCheckState(self, col, st):
        self._check[col] = st

    def checkState(self, col):
        return self._check.get(col, Qt.CheckState.Unchecked)

    def setData(self, col, role, v):
        self._data[(col, role)] = v

    def data(self, col, role):
        return self._data.get((col, role))

    def setHidden(self, h):
        self._hidden = h


class QTreeWidget(QWidget):
    itemChanged = Signal(object, int)

    def __init__(self, *a):
        super().__init__()
        self.items = []

    def addTopLevelItem(self, it):
        self.items.append(it)

    def topLevelItemCount(self):
        return len(self.items)

    def topLevelItem(self, i):
        return self.items[i]

    def clear(self):
        self.items = []


class QTextBrowser(QWidget):
    def setHtml(self, h):
        self.html = h


class QDoubleSpinBox(QWidget):
    def __init__(self, *a):
        super().__init__()
        self._v = 0.0

    def setValue(self, v):
        self._v = float(v)

    def value(self):
        return self._v


class QSpinBox(QDoubleSpinBox):
    def setValue(self, v):
        self._v = int(v)


class QDialog(QWidget):
    exec_result = None

    def exec(self):
        return QDialog.exec_result


class QDialogButtonBox(QWidget):
    accepted = Signal()
    rejected = Signal()

    def addButton(self, *a):
        return QPushButton()


class QMessageBox(QWidget):
    shown = []

    def __init__(self, *a, **k):
        super().__init__()
        self.args = a
        self._detailed = ""

    def setDetailedText(self, t):
        self._detailed = t

    def addButton(self, *a):
        return QPushButton()

    def clickedButton(self):
        return None

    def exec(self):
        QMessageBox.shown.append(self)
        return 0

    @staticmethod
    def question(*a, **k):
        return _Enum("QMessageBox.StandardButton.No")

    @staticmethod
    def warning(*a, **k):
        QMessageBox.shown.append(a)

    @staticmethod
    def information(*a, **k):
        pass


class QFileDialog(Stub):
    next_open = ("", "")
    next_save = ("", "")
    next_open_many = ([], "")

    @classmethod
    def getOpenFileName(cls, *a, **k):
        return cls.next_open

    @classmethod
    def getSaveFileName(cls, *a, **k):
        return cls.next_save

    @classmethod
    def getOpenFileNames(cls, *a, **k):
        return cls.next_open_many


class QProgressBar(QWidget):
    pass


class QSplitter(QWidget):
    def __init__(self, orientation=None, *a):
        super().__init__()
        self._orient = orientation

    def orientation(self):
        return self._orient

    def setOrientation(self, o):
        self._orient = o


class _Layout(Stub):
    pass


def _module(name, **attrs):
    m = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(m, k, v)

    def __getattr__(item):
        if item.startswith("__"):
            raise AttributeError(item)
        cls = _Meta(item, (QWidget,), {})
        setattr(m, item, cls)
        return cls

    m.__getattr__ = __getattr__
    return m


class FigureCanvasQTAgg(FigureCanvasAgg):
    def __init__(self, fig):
        super().__init__(fig)
        self.draws = 0

    def draw_idle(self, *a, **k):
        self.draws += 1
        self.draw()

    def setSizePolicy(self, *a):
        pass

    def setFocusPolicy(self, *a):
        pass


class NavigationToolbar2QT(Stub):
    mode = ""


def install():
    core = _module("PySide6.QtCore", QObject=QObject, QRunnable=QRunnable, QThreadPool=QThreadPool, QTimer=QTimer,
                   QSettings=QSettings, QSortFilterProxyModel=QSortFilterProxyModel, QUrl=QUrl, Qt=Qt, Signal=Signal,
                   Slot=Slot, QProcess=QProcess, QStandardPaths=QStandardPaths)
    gui = _module("PySide6.QtGui", QAction=QAction, QKeySequence=QKeySequence, QColor=QColor, QBrush=QBrush, QFont=QFont,
                  QDesktopServices=QDesktopServices, QStandardItem=QStandardItem, QStandardItemModel=QStandardItemModel)
    widgets = _module(
        "PySide6.QtWidgets", QWidget=QWidget, QApplication=QApplication, QMainWindow=QMainWindow, QLabel=QLabel,
        QPushButton=QPushButton, QCheckBox=QCheckBox, QLineEdit=QLineEdit, QComboBox=QComboBox, QTabWidget=QTabWidget,
        QTableWidget=QTableWidget, QTableWidgetItem=QTableWidgetItem, QTreeWidget=QTreeWidget,
        QTreeWidgetItem=QTreeWidgetItem, QTextBrowser=QTextBrowser, QDoubleSpinBox=QDoubleSpinBox, QDialog=QDialog,
        QDialogButtonBox=QDialogButtonBox, QMessageBox=QMessageBox, QSpinBox=QSpinBox, QFileDialog=QFileDialog, QProgressBar=QProgressBar,
        QSplitter=QSplitter, QHBoxLayout=_Layout, QVBoxLayout=_Layout, QFormLayout=_Layout, QMenu=QMenu)
    pyside = types.ModuleType("PySide6")
    pyside.QtCore, pyside.QtGui, pyside.QtWidgets = core, gui, widgets
    sys.modules.update({"PySide6": pyside, "PySide6.QtCore": core, "PySide6.QtGui": gui, "PySide6.QtWidgets": widgets})
    qtagg = types.ModuleType("matplotlib.backends.backend_qtagg")
    qtagg.FigureCanvasQTAgg = FigureCanvasQTAgg
    qtagg.NavigationToolbar2QT = NavigationToolbar2QT
    sys.modules["matplotlib.backends.backend_qtagg"] = qtagg
