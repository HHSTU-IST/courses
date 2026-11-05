# 环境配置

## 1. Python

opencv pillow scikit-learn torchvision ultralytics

## 2. VSCode

### 2.1. 扩展

charliermarsh.ruff
ms-toolsai.jupyter
ms-toolsai.jupyter-renderers
ms-python.python

### 2.2. 配置文件

```json
{
  // editor
  "editor.fontSize": 18,
  "editor.formatOnSave": true,
  "editor.lineNumbers": "interval",
  "editor.linkedEditing": true,
  "editor.minimap.enabled": false,
  "editor.suggest.preview": true,
  "editor.suggest.shareSuggestSelections": true,
  "editor.tabCompletion": "on",
  "editor.unicodeHighlight.ambiguousCharacters": false,
  "editor.unicodeHighlight.nonBasicASCII": false,
  "editor.wordBasedSuggestions": "matchingDocuments",
  "editor.wordWrap": "on",
  "editor.quickSuggestions": {
    "comments": true,
    "strings": true,
    "other": true
  },
  // explorer
  "explorer.compactFolders": true,
  "explorer.confirmDelete": false,
  "explorer.confirmDragAndDrop": false,
  "explorer.confirmPasteNative": false,
  "explorer.fileNesting.enabled": true,
  "explorer.incrementalNaming": "smart",
  "explorer.sortOrder": "type",
  // files
  "files.associations": {
    "*.condarc": "yaml",
    "*.h": "cpp",
  },
  "files.exclude": {
    "**/.DS_Store": true,
    "**/.git": true,
    "**/.ipynb_checkpoints": true,
    "**/.svn": true,
    "**/Thumbs.db": true
  },
  "files.autoGuessEncoding": true,
  "files.defaultLanguage": "markdown",
  "files.eol": "\n",
  "files.insertFinalNewline": true,
  "files.trimTrailingWhitespace": true,
  // terminal
  "terminal.integrated.fontSize": 16,
  "terminal.integrated.hideOnStartup": "always",
  // workbench
  "workbench.activityBar.location": "top",
  "workbench.colorTheme": "Visual Studio Light",
  "workbench.editor.highlightModifiedTabs": true,
  "workbench.editor.pinnedTabSizing": "compact",
  "workbench.editor.wrapTabs": true,
  "workbench.editorAssociations": {
    "*.md": "default",
    "*.drawio.png": "hediet.vscode-drawio",
    "*.csv": "default",
    "*.plist": "default"
  },
  "workbench.iconTheme": "material-icon-theme",
  "workbench.sideBar.location": "right",
  "workbench.startupEditor": "none",
  // notebook
  "notebook.codeActionsOnSave": {
    "notebook.source.fixAll": "never",
    "notebook.source.organizeImports": "explicit"
  },
  "notebook.compactView": true,
  "notebook.consolidatedRunButton": true,
  "notebook.diff.experimental.toggleInline": true,
  "notebook.diff.ignoreOutputs": true,
  "notebook.formatOnSave.enabled": true,
  "notebook.lineNumbers": "on",
  "notebook.markup.fontSize": 18,
  "notebook.multiCursor.enabled": true,
  "notebook.output.minimalErrorRendering": true,
  "notebook.output.wordWrap": true,
  "notebook.variablesView": true,
  // python
  "[python]": {
    "editor.codeActionsOnSave": {
      "source.fixAll": "explicit",
      "source.organizeImports": "explicit"
    }
  },
  "python.languageServer": "None",
  "python.terminal.activateEnvironment": false,
  "ruff.configuration": "pyproject.toml",
  // jupyter
  "jupyter.exportWithOutputEnabled": true,
  "jupyter.pythonExportMethod": "nbconvert",
}
```
