from PyQt5 import QtWidgets, QtCore

def show_msgbox(title, msg, type):
    msgbox = QtWidgets.QMessageBox()
    msgbox.setIcon(type)
    msgbox.setWindowTitle(title)
    msgbox.setText(msg)
    msgbox.exec_()

def show_msgbox_richtext(title, msg, type):
    msgbox = QtWidgets.QMessageBox()
    msgbox.setIcon(type)
    msgbox.setWindowTitle(title)
    msgbox.setTextFormat(QtCore.Qt.RichText)
    msgbox.setText(msg)
    msgbox.exec_()

def show_msgbox_info(title, msg):
    msgbox = QtWidgets.QMessageBox()
    msgbox.setIcon(QtWidgets.QMessageBox.Information)
    msgbox.setWindowTitle(title)
    msgbox.setText(msg)
    msgbox.setStandardButtons(QtWidgets.QMessageBox.Ok)
    msgbox.exec_()