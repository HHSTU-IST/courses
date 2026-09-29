import os

import openpyxl
import pandas as pd

file = input("file: ")

path = os.path.abspath(file)
print(f"path: {path}")
dirname = os.path.dirname(path)
print(f"dirname: {dirname}")
wb = openpyxl.load_workbook(file)
sheets = wb.sheetnames


def sendTofile(sheets):
    for sheet in sheets:
        df = pd.read_excel(file, sheet_name=sheet)
        df.to_csv(f"{dirname}/{sheet}.csv")


sendTofile(sheets)
