Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
strScriptPath = fso.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = strScriptPath

' Find pythonw.exe path (custom per-user path or fallback to PATH)
userPythonw = WshShell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Programs\Python\Python314\pythonw.exe"
If fso.FileExists(userPythonw) Then
    pythonwCmd = """" & userPythonw & """"
Else
    pythonwCmd = "pythonw.exe"
End If

WshShell.Run pythonwCmd & " """ & strScriptPath & "\blob.py""", 0, False
Set WshShell = Nothing
Set fso = Nothing
