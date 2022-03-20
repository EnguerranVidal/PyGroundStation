######################## IMPORTS ########################
import os
import shutil
import signal
import sys
import time as t
import datetime as dt
import subprocess

# ------------------- PyQt Modules -------------------- #
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import pyqtSlot, QTimer, Qt
import pyqtgraph as pg

# ----------------- General Modules ------------------- #
import numpy as np
import pandas as pd


######################## CLASSES ########################

class Balloon_GUI(QMainWindow):
    def __init__(self):
        super().__init__()
        ##################  PARAMETERS  ###################
        self.pid = None
        self.serial = None
        self.current_dir = os.path.dirname(os.path.abspath(__file__))
        self.setGeometry(500, 500, 1000, 600)
        self.setWindowTitle('Balloon Ground Station')
        self.setWindowIcon(QIcon('icons\\logo.jpg'))
        self.statusBar().showMessage('Ready')
        self.center()
        self.parameters = {}
        self.load_parameters()
        ##################  MENUBAR  ##################
        self.menubar = self.menuBar()
        # FILE MENU
        self.fileMenu = self.menubar.addMenu('&File')
        self.fileMenu.aboutToShow.connect(self.check_file_menu)
        # new format
        new_formatAct = QAction('&New Format', self)
        new_formatAct.setStatusTip('Create New Packet Format')
        new_formatAct.triggered.connect(self.new_format)
        self.fileMenu.addAction(new_formatAct)
        # edit format
        open_formatAct = QAction('&Open Format', self)
        open_formatAct.setStatusTip('Edit Existing Packet Format')
        open_formatAct.triggered.connect(self.open_format)
        self.fileMenu.addAction(open_formatAct)
        self.fileMenu.addSeparator()
        # Archive Data
        self.archiveMenu = QMenu('&Archive', self)
        self.fileMenu.addMenu(self.archiveMenu)
        self.fileMenu.addSeparator()
        # exit action
        exitAct = QAction(QIcon('exit.png'), '&Exit', self)
        exitAct.setShortcut('Ctrl+Q')
        exitAct.setStatusTip('Exit application')
        exitAct.triggered.connect(self.close)
        self.fileMenu.addAction(exitAct)
        # EDIT MENU
        self.editMenu = self.menubar.addMenu('&Edit')
        # change header
        change_headerAct = QAction('&Change Header', self)
        change_headerAct.setStatusTip('Change Packets Header')
        change_headerAct.triggered.connect(self.change_header)
        self.editMenu.addAction(change_headerAct)
        # TOOLS MENU
        self.toolsMenu = self.menubar.addMenu('&Tools')
        # Run Serial Code
        self.run_serialAct = QAction('&Run', self)
        self.run_serialAct.setStatusTip('Run Serial Listener')
        self.run_serialAct.triggered.connect(self.start_serial)
        self.toolsMenu.addAction(self.run_serialAct)
        # Stop Serial Code
        self.stop_serialAct = QAction('&Stop', self)
        self.stop_serialAct.setStatusTip('Stop Serial Listener')
        self.stop_serialAct.triggered.connect(self.stop_serial)
        self.toolsMenu.addAction(self.stop_serialAct)
        # Opening Serial Monitor
        openmonitorAct = QAction('&Open Serial Monitor', self)
        openmonitorAct.setStatusTip('Open Serial Monitor')
        openmonitorAct.triggered.connect(self.open_serial_monitor)
        self.toolsMenu.addAction(openmonitorAct)
        self.toolsMenu.addSeparator()
        # Port Menu
        self.portMenu = QMenu('&Port', self)
        self.toolsMenu.addMenu(self.portMenu)
        self.available_ports = None
        self.toolsMenu.aboutToShow.connect(self.check_tools_menu)
        # Baud Menu
        baud_rates = self.parameters["available_bauds"]
        id_baud = baud_rates.index(str(self.parameters["selected_baud"]))
        self.baudMenu = QMenu('&Baud    ' + baud_rates[id_baud], self)
        baud_group = QActionGroup(self.baudMenu)
        for baud in baud_rates:
            action = QAction(baud, self.baudMenu, checkable=True, checked=baud == baud_rates[id_baud])
            self.baudMenu.addAction(action)
            baud_group.addAction(action)
        baud_group.setExclusive(True)
        baud_group.triggered.connect(self.select_baud)
        self.toolsMenu.addMenu(self.baudMenu)
        # Rssi
        self.rssiAct = QAction('&RSSI', self, checkable=True, checked=self.parameters["rssi"])
        self.rssiAct.setStatusTip('Toggle RSSI Retrieval')
        self.rssiAct.triggered.connect(self.set_rssi)
        self.toolsMenu.addAction(self.rssiAct)
        # HELP MENU
        self.helpMenu = self.menubar.addMenu('&Help')
        # Visit github page
        githubAct = QAction('&Visit Github', self)
        githubAct.setStatusTip('Visit Github Page')
        githubAct.triggered.connect(self.github_page)
        self.helpMenu.addAction(githubAct)

        ##################  VARIABLES  ##################
        if not os.path.exists("output"):
            file = open("output", "w").close()
        self.serial_window = SerialWindow(self)
        self.serial_window.textedit.setDisabled(True)
        self.serial_window.textedit.setReadOnly(True)
        self.serial_monitor_timer = QTimer()
        self.serial_monitor_timer.timeout.connect(self.check_subprocess)
        self.output_lines = 0
        self.serial_monitor_timer.start(100)
        self.table_widget = CentralWidget(self)
        self.setCentralWidget(self.table_widget)
        self.show()

    def center(self):
        qr = self.frameGeometry()
        cp = QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

    def load_parameters(self):
        self.parameters = {}
        with open("parameters", "r") as file:
            lines = file.readlines()
        for i in range(len(lines)):
            line = lines[i].split(';')
            if line[0] == "available_bauds" or line[0] == "format_files" or line[0] == "save_files":
                bauds = line[1].split(',')
                for j in range(len(bauds)):
                    bauds[j] = bauds[j].rstrip("\n")
                self.parameters[line[0]] = bauds
            elif line[0] == "rssi" or line[0] == "autoscroll":
                self.parameters[line[0]] = bool(int(line[1].rstrip("\n")))
            else:
                self.parameters[line[0]] = line[1].rstrip("\n")

    def save_parameters(self):
        with open("parameters", "r") as file:
            lines = file.readlines()
        with open("parameters", "w") as file:
            for i in range(len(lines)):
                line = lines[i].split(';')
                if line[0] == "available_bauds" or line[0] == "format_files" or line[0] == "save_files":
                    file.write(lines[i])
                elif line[0] == "rssi" or line[0] == "autoscroll":
                    file.write(line[0] + ';' + str(int(self.parameters[line[0]])) + '\n')
                else:
                    file.write(line[0] + ';' + str(self.parameters[line[0]]) + '\n')

    def check_file_menu(self):
        self.portMenu.setTitle('&Port')
        directory = os.path.join(self.current_dir, "data")
        file_names = [name for name in os.listdir(directory) if os.path.isfile(os.path.join(directory, name))]
        if len(file_names) == 0:
            self.archiveMenu.setDisabled(True)
        else:
            self.archiveMenu.clear()
            for i in range(len(file_names)):
                archiveAct = QAction('&' + file_names[i], self)
                archiveAct.setStatusTip('Archive ' + file_names[i])
                archiveAct.triggered.connect(lambda: self.archive_save(i))
                self.archiveMenu.addAction(archiveAct)

    def check_tools_menu(self):
        self.portMenu.setTitle('&Port')
        self.portMenu.setDisabled(False)
        import serial.tools.list_ports
        self.available_ports = [comport.device for comport in serial.tools.list_ports.comports()]
        if len(self.available_ports) == 0:
            self.stop_serialAct.setDisabled(True)
            self.portMenu.setDisabled(True)
            self.parameters["selected_port"] = ""
            self.save_parameters()
        else:
            self.portMenu.clear()
            port_group = QActionGroup(self.portMenu)
            selection = self.parameters["selected_port"]
            if selection in self.available_ports:
                for port in self.available_ports:
                    action = QAction(port, self.portMenu, checkable=True, checked=port == selection)
                    self.portMenu.addAction(action)
                    port_group.addAction(action)
                self.portMenu.setTitle('&Port    ' + selection)
            else:
                for port in self.available_ports:
                    action = QAction(port, self.portMenu, checkable=True, checked=port == self.available_ports[0])
                    self.portMenu.addAction(action)
                    port_group.addAction(action)
                self.portMenu.setTitle('&Port    ' + self.available_ports[0])
                self.parameters["selected_port"] = self.available_ports[0]
                self.save_parameters()
            port_group.setExclusive(True)
            port_group.triggered.connect(self.select_port)
        if self.serial is None:
            self.stop_serialAct.setDisabled(True)
            self.run_serialAct.setDisabled(False)
        else:
            self.stop_serialAct.setDisabled(False)
            self.run_serialAct.setDisabled(True)

    def select_baud(self, action):
        self.baudMenu.setTitle('&Baud    ' + action.text())
        self.parameters["selected_baud"] = action.text()
        self.save_parameters()
        # Restart Serial Connection if on
        if self.serial is not None:
            self.stop_serial()
            self.start_serial()

    def change_header(self):
        header_dialog = QInputDialog(self)
        header_dialog.setInputMode(QInputDialog.TextInput)
        header_dialog.setWindowTitle("Changing Header")
        header_dialog.setLabelText("Current  Header -> " + self.parameters["header"])
        header_dialog.resize(500, 100)
        okPressed = header_dialog.exec_()
        text = header_dialog.textValue()
        if okPressed and text != "":
            self.parameters["header"] = text
            self.save_parameters()
        elif okPressed and text == "":
            print("bruh")

    def new_format(self):
        pass

    def open_format(self):
        f_name = QFileDialog.getOpenFileName(self, "Open Format File", os.path.join(self.current_dir, "formats"))
        print(f_name[0])

    def save_format(self):
        pass

    def preferences(self):
        pass

    @staticmethod
    def archive_save(i):
        print(i)

    def select_port(self, action):
        self.portMenu.setTitle('&Port    ' + action.text())
        self.parameters["selected_port"] = action.text()
        self.save_parameters()
        # Stop Serial Connection if on
        if self.serial is not None:
            self.stop_serial()

    def set_rssi(self, action):
        self.parameters["rssi"] = action
        self.save_parameters()
        # Restart Serial Connection if on
        if self.serial is not None:
            self.stop_serial()
            self.start_serial()

    def open_serial_monitor(self):
        self.serial_window.show()

    def start_serial(self):
        message = "Port : " + self.parameters["selected_port"] + "  Baud : " + \
                  self.parameters["selected_baud"] + "\nDo you wish to continue ?"
        msg = MessageBox()
        msg.setWindowIcon(QIcon('icons\\logo.jpg'))
        msg.setWindowTitle("Running Warning")
        msg.setText(message)
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.Cancel)
        msg.setStyleSheet("QLabel{min-width: 200px;}")
        msg.exec_()
        button = msg.clickedButton()
        sb = msg.standardButton(button)
        if sb == QMessageBox.Yes:
            if os.path.exists(os.path.join(self.current_dir, "Balloon_Serial.py")):
                self.serial = subprocess.Popen([sys.executable, os.path.join(self.current_dir, "Balloon_Serial.py")])
                self.pid = self.serial.pid
                self.serial_window.textedit.setDisabled(False)
            else:
                cancelling = MessageBox()
                cancelling.setWindowIcon(QIcon('icons\\logo.jpg'))
                cancelling.setWindowTitle("Error")
                cancelling.setText("Balloon_Serial.py not found.")
                cancelling.setStandardButtons(QMessageBox.Ok)
                cancelling.setStyleSheet("QLabel{min-width: 200px;}")
                cancelling.exec_()

    def stop_serial(self):
        if self.serial is not None:
            self.serial.kill()
            self.serial.terminate()
            t.sleep(0.5)
            self.serial_window.textedit.setDisabled(True)
            self.serial = None

    def check_subprocess(self):
        self.load_parameters()
        if self.serial is not None and self.serial.poll() is not None:
            self.stop_serial()
            self.serial_window.textedit.setDisabled(True)
        elif self.serial is not None and self.serial.poll() is None:
            with open(self.parameters["output_file"], "r") as file:
                lines = file.readlines()
            if len(lines) != self.output_lines:
                self.serial_window.textedit.append(lines[-1])
                self.output_lines = len(lines)
            if bool(self.parameters["autoscroll"]):
                self.serial_window.textedit.moveCursor(QTextCursor.End)
            else:
                self.serial_window.textedit.moveCursor(QTextCursor.Start)
        else:
            pass

    @staticmethod
    def github_page():
        import webbrowser
        webbrowser.open("https://github.com/EnguerranVidal/WeatherBalloon-GroundStation")

    def closeEvent(self, event):
        reply = QMessageBox.question(self, 'Message', "Are you sure to quit?", QMessageBox.Yes |
                                     QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.stop_serial()
            os.remove("output")
            for window in QApplication.topLevelWidgets():
                window.close()
            event.accept()

        else:
            event.ignore()


class SerialWindow(QWidget):
    def __init__(self, parent=None):
        super(SerialWindow, self).__init__()
        self.resize(450, 350)
        self.setWindowTitle('Serial Monitor')
        self.setWindowIcon(QIcon('icons\\logo.jpg'))
        # General Layout
        self.layout = QGridLayout(self)
        self.setLayout(self.layout)
        # Loading parameters
        self.parameters = {}
        self.load_parameters()
        # Text edit box
        self.textedit = QTextEdit(self)
        self.textedit.setText('Run Serial listening to display incoming info ...')
        self.textedit.setStyleSheet('font-size:15px')
        self.layout.addWidget(self.textedit, 1, 1, 1, 2)
        # Autoscroll Che-box
        self.autoscroll_box = QCheckBox("Autoscroll")
        self.autoscroll_box.setChecked(bool(self.parameters["autoscroll"]))
        self.autoscroll_box.stateChanged.connect(self.change_autoscroll)
        self.layout.addWidget(self.autoscroll_box, 2, 1)
        # Clearing Output Button
        self.clearButton = QPushButton("Clear Output")
        self.clearButton.clicked.connect(self.clear_output)
        self.layout.addWidget(self.clearButton, 2, 2)

    def load_parameters(self):
        self.parameters = {}
        with open("parameters", "r") as file:
            lines = file.readlines()
        for i in range(len(lines)):
            line = lines[i].split(';')
            if line[0] == "available_bauds" or line[0] == "format_files" or line[0] == "save_files":
                bauds = line[1].split(',')
                for j in range(len(bauds)):
                    bauds[j] = bauds[j].rstrip("\n")
                self.parameters[line[0]] = bauds
            elif line[0] == "rssi" or line[0] == "autoscroll":
                self.parameters[line[0]] = bool(int(line[1].rstrip("\n")))
            else:
                self.parameters[line[0]] = line[1].rstrip("\n")

    def save_parameters(self):
        with open("parameters", "r") as file:
            lines = file.readlines()
        with open("parameters", "w") as file:
            for i in range(len(lines)):
                line = lines[i].split(';')
                if line[0] == "available_bauds" or line[0] == "format_files" or line[0] == "save_files":
                    file.write(lines[i])
                elif line[0] == "rssi" or line[0] == "autoscroll":
                    file.write(line[0] + ';' + str(int(self.parameters[line[0]])) + '\n')
                else:
                    file.write(line[0] + ';' + str(self.parameters[line[0]]) + '\n')

    def change_autoscroll(self):
        self.parameters["autoscroll"] = int(not bool(self.parameters["autoscroll"]))
        self.save_parameters()
        self.autoscroll_box.setChecked(bool(self.parameters["autoscroll"]))

    @staticmethod
    def clear_output(self):
        file = open("output", "w").close()


class CentralWidget(QWidget):
    def __init__(self, parent=None):
        super(QWidget, self).__init__(parent)
        print(self.parent)
        self.layout = QVBoxLayout(self)
        # Initialize tab screen
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet('QTabBar { font-size: 12pt; font-family: Arial; }')
        self.A_tab = QWidget()
        self.B_tab = QWidget()
        self.tabs.resize(300, 200)
        # Add tabs
        self.tabs.addTab(self.A_tab, "Balloon A")
        self.tabs.addTab(self.B_tab, "Balloon B")
        # Create first tab
        self.A_tab.layout = QGridLayout(self)
        self.A_tab.setLayout(self.A_tab.layout)
        # Temperature, Pressure, Humidity
        self.A_TPH_plots = pg.GraphicsLayoutWidget(show=True)
        y = np.random.normal(size=100)
        self.A_ex_T = self.A_TPH_plots.addPlot(title="T External", y=y, pen=(255, 0, 0))
        self.A_TPH_plots.nextRow()
        self.A_P = self.A_TPH_plots.addPlot(title="Pressure", y=y, pen=(255, 0, 0))
        self.A_TPH_plots.nextRow()
        self.A_H = self.A_TPH_plots.addPlot(title="Humidity Percentage", y=y, pen=(255, 0, 0))

        # Random Gases
        self.A_Gases_plots = pg.GraphicsLayoutWidget(show=True)
        gases = ["CO", "O3", "CO2", "HCOH", "CH4", "NH3", "NO2", "H2", "C3H8", "C4H10", "C2H6OH"]
        offset = np.random.normal(size=len(gases))
        from matplotlib.pyplot import cm
        color = cm.rainbow(np.linspace(0, 1, len(gases))) * 255
        self.A_Gases = self.A_Gases_plots.addPlot(title="Trace Gases Levels")
        for i in range(len(gases)):
            y = np.random.normal(size=100)
            self.A_Gases.plot(y + offset[i], pen=color[i][:-1], name=gases[i])

        # Adding widgets
        self.A_tab.layout.addWidget(self.A_TPH_plots, 1, 1, 1, 1)
        self.A_tab.layout.addWidget(self.A_Gases_plots, 1, 2, 1, 2)
        # Add tabs to widget
        self.layout.addWidget(self.tabs)
        self.setLayout(self.layout)

    def select_data(self, i, column, start_date, finish_date=""):
        date_format = "%Y-%m-%d %H:%M:%S"
        today = dt.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        if finish_date == "":
            finish_date = today
        try:
            df = pd.read_csv(os.path.join(self.data_path, self.parameters["save_files"][i]))
        except FileNotFoundError:  # creating a "false" datafile if the file is non existent
            time = dt.datetime.strftime(today, date_format)
            df = {"Reception Time": np.array([time]), column: np.array([0])}
        df["Reception Time"] = pd.to_datetime(df["Reception Time"], format=date_format)
        time_mask = (df["Reception Time"] > start_date) & (df["Reception Time"] < finish_date)
        data = df.loc[time_mask]
        zeros_mask = data[column] == 0.0
        data = data.loc[zeros_mask]
        return np.array(data["Reception Time"]), np.array(data[column])

    @pyqtSlot()
    def on_click(self):
        print("\n")
        for currentQTableWidgetItem in self.tableWidget.selectedItems():
            print(currentQTableWidgetItem.row(), currentQTableWidgetItem.column(), currentQTableWidgetItem.text())


class MessageBox(QMessageBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        grid_layout = self.layout()
        qt_msgboxex_icon_label = self.findChild(QLabel, "qt_msgboxex_icon_label")
        qt_msgboxex_icon_label.deleteLater()
        qt_msgbox_label = self.findChild(QLabel, "qt_msgbox_label")
        qt_msgbox_label.setAlignment(Qt.AlignCenter)
        grid_layout.removeWidget(qt_msgbox_label)
        qt_msgbox_buttonbox = self.findChild(QDialogButtonBox, "qt_msgbox_buttonbox")
        grid_layout.removeWidget(qt_msgbox_buttonbox)
        grid_layout.addWidget(qt_msgbox_label, 0, 0, alignment=Qt.AlignCenter)
        grid_layout.addWidget(qt_msgbox_buttonbox, 1, 0, alignment=Qt.AlignCenter)
